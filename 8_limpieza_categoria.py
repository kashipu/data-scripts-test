#!/usr/bin/env python3
"""
Sistema de Limpieza y Categorizaci�n de Motivos NPS/CSAT
=========================================================

M�dulo optimizado para:
1. Detectar y filtrar textos sin sentido (ruido)
2. Categorizar motivos usando Aho-Corasick (10-20x m�s r�pido)
3. Calcular scores de confianza para revisi�n humana
4. Explorar y validar categor�as existentes

Uso:
    # Exploraci�n inicial (recomendado primero)
    python 8_limpieza_categoria.py --mode explore --limit 10000

    # Procesamiento completo con actualizaci�n de BD
    python 8_limpieza_categoria.py --mode process --batch-size 5000

    # Procesar solo motivos sin categorizar
    python 8_limpieza_categoria.py --mode process --only-uncategorized
"""

import argparse
import logging
import math
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ahocorasick
import pandas as pd
from sqlalchemy import text

# Imports del proyecto
sys.path.append(os.path.join(os.path.dirname(__file__), 'nueva_etl'))
from nueva_etl.utils import get_engine, load_yaml, normalize_text

# ============================================================================
# CONFIGURACI�N
# ============================================================================

CATEGORIAS_YAML = "nueva_etl/categorias.yml"
MIN_CONFIDENCE_THRESHOLD = 0.3  # Score m�nimo para aceptar categorizaci�n
LOG_FILE = "limpieza_categoria.log"


# ============================================================================
# FUNCIONES HELPER
# ============================================================================

def clasificar_texto_por_longitud(texto: str) -> str:
    """
    Clasifica el texto según su longitud.

    Rangos:
    - muy_corto: < 10 caracteres
    - corto: 10-29 caracteres
    - mediano: 30-79 caracteres
    - largo: 80+ caracteres
    """
    if not texto:
        return 'muy_corto'

    longitud = len(texto)

    if longitud < 10:
        return 'muy_corto'
    elif longitud < 30:
        return 'corto'
    elif longitud < 80:
        return 'mediano'
    else:
        return 'largo'


# Stopwords sem�nticas (respuestas vac�as)
SEMANTIC_STOPWORDS = {
    "na", "n/a", "no aplica", "ninguno", "ninguna", "nada", "no tengo",
    "no se", "no se", "ok", "bien", "bueno", "buena", "si", "no",
    "x", ".", "..", "...", "....", ".....", "-", "--", "---",
    "s/d", "sin datos", "vacio", "vac�o", "no hay", "no tiene"
}

# Patrones de teclado aleatorio
KEYBOARD_PATTERNS = [
    "qwerty", "asdf", "zxcv", "qwertyuiop", "asdfghjkl", "zxcvbnm",
    "1234", "12345", "123456", "abcd", "abcde", "abc123"
]

# ============================================================================
# CONFIGURACI�N DE LOGGING
# ============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ============================================================================
# CLASE: FILTRO DE LIMPIEZA
# ============================================================================

class TextCleaner:
    """
    Detecta y filtra textos sin sentido o ruido.

    Filtros implementados:
    - Longitud m�nima
    - Alto ratio de caracteres repetidos
    - Patrones de teclado aleatorio
    - Alta entrop�a (texto aleatorio)
    - Solo puntuaci�n
    - Stopwords sem�nticas
    """

    def __init__(self, min_length: int = 3, min_alpha_ratio: float = 0.5):
        self.min_length = min_length
        self.min_alpha_ratio = min_alpha_ratio

    def is_valid(self, text: str) -> Tuple[bool, str]:
        """
        Valida si el texto tiene contenido �til.

        Returns:
            (es_valido, razon_rechazo)
        """
        if not text or not isinstance(text, str):
            return False, "empty"

        text_clean = text.strip()
        text_norm = normalize_text(text_clean)

        # 1. Muy corto
        if len(text_norm) < self.min_length:
            return False, "too_short"

        # 2. Stopwords sem�nticas
        if text_norm in SEMANTIC_STOPWORDS:
            return False, "semantic_stopword"

        # 3. Solo puntuaci�n/espacios
        alpha_chars = sum(c.isalpha() for c in text_norm)
        if alpha_chars == 0:
            return False, "no_alpha"

        # 4. Ratio de caracteres alfab�ticos muy bajo
        alpha_ratio = alpha_chars / len(text_norm) if text_norm else 0
        if alpha_ratio < self.min_alpha_ratio:
            return False, "low_alpha_ratio"

        # 5. Caracteres repetidos (aaaa, 1111, ....)
        if self._is_repetitive(text_norm):
            return False, "repetitive"

        # 6. Patrones de teclado (qwerty, asdf)
        if self._is_keyboard_pattern(text_norm):
            return False, "keyboard_pattern"

        # 7. Entrop�a muy baja (texto aleatorio tipo "asdjalskd")
        if self._is_random_text(text_norm):
            return False, "random_text"

        return True, "valid"

    def _is_repetitive(self, text: str, threshold: float = 0.85) -> bool:
        """Detecta si hay demasiados caracteres repetidos."""
        if len(text) < 4:
            return False

        # Calcular ratio de caracteres �nicos
        unique_ratio = len(set(text)) / len(text)

        # Muy permisivo: solo rechazar si es MUY repetitivo (aaaa, 1111)
        if unique_ratio < (1 - threshold):
            # Verificación adicional: si tiene palabras válidas, no rechazar
            palabras = re.findall(r'\b[a-z������]{4,}\b', text)
            if len(palabras) >= 2:  # Si tiene al menos 2 palabras de 4+ letras, es válido
                return False
            return True

        return False

    def _is_keyboard_pattern(self, text: str) -> bool:
        """Detecta patrones comunes de teclado."""
        return any(pattern in text for pattern in KEYBOARD_PATTERNS)

    def _is_random_text(self, text: str, min_entropy: float = 2.5) -> bool:
        """
        Detecta texto aleatorio usando múltiples heurísticas.
        Entrop�a muy alta = caracteres aleatorios.
        """
        if len(text) < 6:
            return False

        # Dividir en tokens (palabras)
        tokens = re.findall(r'\b[a-z������]{2,}\b', text)

        # Si no hay palabras, es basura
        if not tokens:
            return True

        # Si hay 2+ palabras de 3+ letras, probablemente es texto válido
        palabras_validas = [t for t in tokens if len(t) >= 3]
        if len(palabras_validas) >= 2:
            return False

        # Si tiene 1 palabra válida de 5+ letras, es válido
        if len(palabras_validas) == 1 and len(palabras_validas[0]) >= 5:
            return False

        # Si llegamos aquí, verificar entrop�a solo para textos cortos (< 20 chars)
        if len(text) >= 20:
            # Textos largos con al menos 1 palabra son válidos
            return False

        # Calcular entrop�a de bigramas solo para casos dudosos
        bigrams = [text[i:i+2] for i in range(len(text)-1)]
        freq = Counter(bigrams)
        entropy = 0
        total = len(bigrams)

        for count in freq.values():
            p = count / total
            entropy -= p * math.log2(p)

        # Umbral más alto: solo rechazar entrop�a MUY alta (texto realmente aleatorio)
        return entropy > 5.5


# ============================================================================
# CLASE: CATEGORIZADOR CON AHO-CORASICK
# ============================================================================

class CategorizerAhoCorasick:
    """
    Categorizador optimizado usando Aho-Corasick.

    Ventajas:
    - 10-20x m�s r�pido que b�squeda secuencial
    - Encuentra todas las palabras clave en una sola pasada
    - Calcula score de confianza basado en:
      * N�mero de matches
      * Longitud de matches (frases > palabras sueltas)
      * Especificidad de las palabras clave
    """

    def __init__(self, categorias_config: Dict):
        self.categorias = categorias_config.get("categorias", [])
        self.otros_label = categorias_config.get("otros", "Otros")

        # Construir automaton Aho-Corasick
        self.automaton = ahocorasick.Automaton()
        self.keyword_to_category = {}

        self._build_automaton()

        logger.info(f"Categorizador inicializado con {len(self.categorias)} categor�as")

    def _build_automaton(self):
        """Construye el automaton con todas las palabras clave."""
        keyword_id = 0

        for categoria in self.categorias:
            nombre = categoria.get("nombre")
            palabras = categoria.get("palabras_clave", [])
            min_len = categoria.get("min_len", 0)

            for palabra in palabras:
                palabra_norm = normalize_text(palabra)

                # Agregar al automaton
                self.automaton.add_word(palabra_norm, (keyword_id, nombre, palabra, len(palabra_norm)))
                self.keyword_to_category[keyword_id] = {
                    "categoria": nombre,
                    "keyword": palabra,
                    "min_len": min_len,
                    "keyword_len": len(palabra_norm)
                }
                keyword_id += 1

        # Finalizar construcci�n
        self.automaton.make_automaton()
        logger.info(f"Automaton construido con {keyword_id} palabras clave")

    def categorize(self, text: str) -> Tuple[str, float, Dict]:
        """
        Categoriza el texto y retorna la categor�a con mayor score.

        Returns:
            (categoria, confidence_score, metadata)
        """
        if not text or not isinstance(text, str):
            return self.otros_label, 0.0, {"reason": "empty_text"}

        text_norm = normalize_text(text)

        # Buscar todos los matches
        matches = list(self.automaton.iter(text_norm))

        if not matches:
            return self.otros_label, 0.0, {"reason": "no_matches"}

        # Calcular scores por categor�a
        category_scores = defaultdict(lambda: {"score": 0.0, "matches": [], "match_count": 0})

        for end_index, (keyword_id, categoria, keyword, keyword_len) in matches:
            # Validar min_len si existe
            info = self.keyword_to_category[keyword_id]
            if info["min_len"] > 0 and len(text_norm) < info["min_len"]:
                continue

            # Score base: longitud de keyword (frases valen m�s que palabras)
            score = keyword_len * 1.0

            # Bonus: palabra completa (no substring)
            start_index = end_index - keyword_len + 1
            is_word_boundary = self._check_word_boundary(text_norm, start_index, end_index)
            if is_word_boundary:
                score *= 1.5

            # Acumular score
            category_scores[categoria]["score"] += score
            category_scores[categoria]["matches"].append(keyword)
            category_scores[categoria]["match_count"] += 1

        if not category_scores:
            return self.otros_label, 0.0, {"reason": "no_valid_matches"}

        # Encontrar categor�a con mayor score
        best_category = max(category_scores.items(), key=lambda x: x[1]["score"])
        categoria_final = best_category[0]
        metadata = best_category[1]

        # Calcular confidence normalizado (0-1)
        total_score = sum(cat["score"] for cat in category_scores.values())
        confidence = metadata["score"] / total_score if total_score > 0 else 0.0

        # Ajustar confidence por n�mero de matches
        match_count = metadata["match_count"]
        if match_count >= 3:
            confidence = min(1.0, confidence * 1.2)
        elif match_count == 1:
            confidence *= 0.8

        return categoria_final, confidence, {
            "matches": metadata["matches"][:5],  # Top 5 matches
            "match_count": match_count,
            "raw_score": metadata["score"],
            "total_categories_matched": len(category_scores)
        }

    def _check_word_boundary(self, text: str, start: int, end: int) -> bool:
        """Verifica si el match est� en l�mite de palabra."""
        # Verificar inicio
        if start > 0 and text[start-1].isalnum():
            return False

        # Verificar fin
        if end < len(text) - 1 and text[end+1].isalnum():
            return False

        return True


# ============================================================================
# FUNCIONES DE EXPLORACI�N
# ============================================================================

def explore_categories(engine, categorizer: CategorizerAhoCorasick,
                      cleaner: TextCleaner, limit: int = 10000):
    """
    Explora una muestra de motivos y genera reporte de categorizaci�n.
    """
    logger.info(f"Iniciando exploraci�n con l�mite de {limit} registros por fuente")

    # Extraer muestra de datos
    samples = []

    # BM - NPS
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, 'BM' as canal, 'NPS' as metrica,
                   nps_recomendacion_motivo as texto,
                   nps_score as score
            FROM banco_movil_clean
            WHERE nps_recomendacion_motivo IS NOT NULL
            AND LENGTH(TRIM(nps_recomendacion_motivo)) > 0
            ORDER BY RANDOM()
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        samples.extend(result)

    # BM - CSAT
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, 'BM' as canal, 'CSAT' as metrica,
                   csat_satisfaccion_motivo as texto,
                   csat_satisfaccion_score as score
            FROM banco_movil_clean
            WHERE csat_satisfaccion_motivo IS NOT NULL
            AND LENGTH(TRIM(csat_satisfaccion_motivo)) > 0
            ORDER BY RANDOM()
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        samples.extend(result)

    # BV - NPS
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, 'BV' as canal, 'NPS' as metrica,
                   motivo_calificacion as texto,
                   nps_score as score
            FROM banco_virtual_clean
            WHERE motivo_calificacion IS NOT NULL
            AND LENGTH(TRIM(motivo_calificacion)) > 0
            ORDER BY RANDOM()
            LIMIT :lim
        """), {"lim": min(limit, 2000)}).fetchall()
        samples.extend(result)

    logger.info(f"Muestra extra�da: {len(samples)} registros")

    # Procesar muestra
    results = []
    rejected_reasons = Counter()
    category_distribution = Counter()
    low_confidence_samples = []

    for row in samples:
        registro_id, canal, metrica, texto, score = row

        # 1. Validar limpieza
        is_valid, reason = cleaner.is_valid(texto)

        if not is_valid:
            # Categorizar como "Texto Sin Sentido / Ruido" en lugar de rechazar
            rejected_reasons[reason] += 1
            categoria = "Texto Sin Sentido / Ruido"
            category_distribution[categoria] += 1

            results.append({
                "id": registro_id,
                "canal": canal,
                "metrica": metrica,
                "texto": texto[:100],
                "score_metrica": score,
                "es_valido": False,
                "razon_rechazo": reason,
                "categoria": categoria,
                "confidence": 1.0,  # Alta confianza de que es ruido
                "matches": f"ruido:{reason}",
                "match_count": 1
            })
            continue

        # 2. Categorizar
        categoria, confidence, metadata = categorizer.categorize(texto)
        category_distribution[categoria] += 1

        result_dict = {
            "id": registro_id,
            "canal": canal,
            "metrica": metrica,
            "texto": texto[:100],
            "score_metrica": score,
            "es_valido": True,
            "razon_rechazo": None,
            "categoria": categoria,
            "confidence": confidence,
            "matches": "; ".join(metadata.get("matches", [])),
            "match_count": metadata.get("match_count", 0)
        }

        results.append(result_dict)

        # Guardar muestras de baja confianza para revisi�n
        if confidence < MIN_CONFIDENCE_THRESHOLD and categoria != "Otros":
            low_confidence_samples.append(result_dict)

    # Crear DataFrame
    df = pd.DataFrame(results)

    # Generar reporte
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("outputs")
    output_dir.mkdir(exist_ok=True)

    # 1. CSV completo
    csv_path = output_dir / f"exploracion_categorias_{timestamp}.csv"
    df.to_csv(csv_path, index=False, encoding='utf-8')
    logger.info(f"CSV completo guardado: {csv_path}")

    # 2. Reporte de estad�sticas
    report_path = output_dir / f"reporte_categorias_{timestamp}.txt"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("=" * 80 + "\n")
        f.write("REPORTE DE EXPLORACI�N DE CATEGOR�AS\n")
        f.write("=" * 80 + "\n\n")

        f.write(f"Fecha: {datetime.now()}\n")
        f.write(f"Total registros analizados: {len(samples)}\n\n")

        # Textos categorizados como ruido
        total_ruido = sum(rejected_reasons.values())
        tasa_ruido = (total_ruido / len(samples)) * 100 if samples else 0
        f.write(f"CALIDAD DE DATOS:\n")
        f.write(f"  Textos sin sentido (ruido): {total_ruido} ({tasa_ruido:.1f}%)\n")
        f.write(f"  Textos con contenido útil: {len(samples) - total_ruido} ({100-tasa_ruido:.1f}%)\n\n")

        f.write(f"  Tipos de ruido identificado:\n")
        for reason, count in rejected_reasons.most_common():
            pct = (count / total_ruido) * 100 if total_ruido > 0 else 0
            f.write(f"    {reason:20} -> {count:6} ({pct:5.1f}%)\n")

        # Distribución de categorías
        f.write(f"\nDISTRIBUCIÓN DE CATEGORÍAS (TODOS LOS TEXTOS):\n")
        for categoria, count in category_distribution.most_common():
            pct = (count / len(samples)) * 100 if len(samples) > 0 else 0
            f.write(f"  {categoria:40} -> {count:6} ({pct:5.1f}%)\n")

        # Estad�sticas de confianza
        df_valid = df[df["es_valido"] == True]
        if not df_valid.empty:
            f.write(f"\nESTAD�STICAS DE CONFIANZA:\n")
            f.write(f"  Media: {df_valid['confidence'].mean():.3f}\n")
            f.write(f"  Mediana: {df_valid['confidence'].median():.3f}\n")
            f.write(f"  Desv. est�ndar: {df_valid['confidence'].std():.3f}\n")
            f.write(f"  Min: {df_valid['confidence'].min():.3f}\n")
            f.write(f"  Max: {df_valid['confidence'].max():.3f}\n")

            # Distribuci�n por rangos
            f.write(f"\n  Distribuci�n por confianza:\n")
            ranges = [
                (0.0, 0.3, "Muy baja"),
                (0.3, 0.5, "Baja"),
                (0.5, 0.7, "Media"),
                (0.7, 0.9, "Alta"),
                (0.9, 1.0, "Muy alta")
            ]
            for low, high, label in ranges:
                count = ((df_valid['confidence'] >= low) & (df_valid['confidence'] < high)).sum()
                if low == 0.9:  # Incluir 1.0 en el �ltimo rango
                    count = (df_valid['confidence'] >= low).sum()
                pct = (count / len(df_valid)) * 100 if len(df_valid) > 0 else 0
                f.write(f"    {label:12} ({low:.1f}-{high:.1f}): {count:6} ({pct:5.1f}%)\n")

        # Muestras de baja confianza
        f.write(f"\n\nMUESTRAS DE BAJA CONFIANZA (< {MIN_CONFIDENCE_THRESHOLD}):\n")
        f.write(f"Total: {len(low_confidence_samples)}\n\n")
        for i, sample in enumerate(low_confidence_samples[:20], 1):
            f.write(f"{i}. [{sample['categoria']}] (conf: {sample['confidence']:.2f})\n")
            f.write(f"   Texto: {sample['texto']}\n")
            f.write(f"   Matches: {sample.get('matches', 'N/A')}\n\n")

    logger.info(f"Reporte guardado: {report_path}")

    # 3. CSV de baja confianza para revisi�n humana
    if low_confidence_samples:
        low_conf_path = output_dir / f"baja_confianza_{timestamp}.csv"
        pd.DataFrame(low_confidence_samples).to_csv(low_conf_path, index=False, encoding='utf-8')
        logger.info(f"Casos de baja confianza guardados: {low_conf_path}")

    print("\n" + "=" * 80)
    print("RESUMEN DE EXPLORACIÓN")
    print("=" * 80)
    print(f"\nArchivos generados:")
    print(f"  1. {csv_path}")
    print(f"  2. {report_path}")
    if low_confidence_samples:
        print(f"  3. {low_conf_path}")

    print(f"\nEstadísticas clave:")
    print(f"  Total analizado: {len(samples)}")
    print(f"  Ruido (sin sentido): {total_ruido} ({tasa_ruido:.1f}%)")
    print(f"  Textos útiles: {len(samples) - total_ruido} ({100-tasa_ruido:.1f}%)")
    print(f"  Baja confianza: {len(low_confidence_samples)}")

    print(f"\nTop 5 categorías:")
    for i, (cat, count) in enumerate(category_distribution.most_common(5), 1):
        pct = (count / len(samples)) * 100 if len(samples) > 0 else 0
        print(f"  {i}. {cat:40} -> {count:6} ({pct:5.1f}%)")

    return df


# ============================================================================
# FUNCIONES DE PROCESAMIENTO
# ============================================================================

def process_and_update_database(engine, categorizer: CategorizerAhoCorasick,
                               cleaner: TextCleaner, batch_size: int = 5000,
                               only_uncategorized: bool = False):
    """
    Procesa todos los motivos y actualiza la base de datos.
    """
    logger.info("Iniciando procesamiento de base de datos")

    # Verificar tabla de categorías
    _ensure_category_table(engine)

    # Procesar cada tabla/campo
    tables_to_process = [
        {
            "table": "banco_movil_clean",
            "canal": "BM",
            "fields": [
                ("nps_recomendacion_motivo", "NPS", "nps_score"),
                ("csat_satisfaccion_motivo", "CSAT", "csat_satisfaccion_score")
            ]
        },
        {
            "table": "banco_virtual_clean",
            "canal": "BV",
            "fields": [
                ("motivo_calificacion", "NPS", "nps_score")
            ]
        }
    ]

    total_processed = 0
    total_updated = 0
    total_rejected = 0

    for table_config in tables_to_process:
        table = table_config["table"]
        canal = table_config["canal"]

        for field, metrica, score_field in table_config["fields"]:
            logger.info(f"Procesando {table}.{field}...")

            # Construir query
            where_clause = f"WHERE {field} IS NOT NULL AND LENGTH(TRIM({field})) > 0"
            if only_uncategorized:
                # Excluir registros ya categorizados
                where_clause += f"""
                    AND NOT EXISTS (
                        SELECT 1 FROM motivos_categorizados mc
                        WHERE mc.tabla_origen = '{table}'
                        AND mc.registro_id = {table}.id
                        AND mc.campo_motivo = '{field}'
                    )
                """

            # Contar total
            with engine.connect() as conn:
                count_result = conn.execute(text(f"SELECT COUNT(*) FROM {table} {where_clause}")).fetchone()
                total = count_result[0]

            logger.info(f"  Total a procesar: {total:,}")

            # Procesar en batches
            offset = 0
            while offset < total:
                with engine.connect() as conn:
                    # Leer batch
                    query = f"""
                        SELECT id, {field} as texto, {score_field} as score
                        FROM {table}
                        {where_clause}
                        ORDER BY id
                        LIMIT :lim OFFSET :off
                    """
                    rows = conn.execute(text(query), {"lim": batch_size, "off": offset}).fetchall()

                    # Procesar batch
                    inserts = []
                    for row in rows:
                        registro_id, texto, score = row

                        # Validar
                        is_valid, reason = cleaner.is_valid(texto)

                        if not is_valid:
                            # Categorizar como ruido
                            inserts.append({
                                "tabla_origen": table,
                                "registro_id": registro_id,
                                "campo_motivo": field,
                                "texto_motivo": texto[:1000],  # Limitar tamaño
                                "texto_tipo": clasificar_texto_por_longitud(texto),
                                "canal": canal,
                                "metrica": metrica,
                                "score_metrica": int(score) if score is not None else None,
                                "categoria": "Texto Sin Sentido / Ruido",
                                "confidence": 1.0,
                                "metadata_categoria": f'{{"ruido_tipo": "{reason}"}}',
                                "es_ruido": True,
                                "razon_ruido": reason
                            })
                            total_rejected += 1
                        else:
                            # Categorizar
                            categoria, confidence, metadata_dict = categorizer.categorize(texto)

                            inserts.append({
                                "tabla_origen": table,
                                "registro_id": registro_id,
                                "campo_motivo": field,
                                "texto_motivo": texto[:1000],  # Limitar tamaño
                                "texto_tipo": clasificar_texto_por_longitud(texto),
                                "canal": canal,
                                "metrica": metrica,
                                "score_metrica": int(score) if score is not None else None,
                                "categoria": categoria,
                                "confidence": round(confidence, 4),
                                "metadata_categoria": str(metadata_dict).replace("'", '"')[:500],
                                "es_ruido": False,
                                "razon_ruido": None
                            })
                            total_updated += 1

                        total_processed += 1

                    # Ejecutar inserts
                    if inserts:
                        conn.execute(text("BEGIN"))
                        try:
                            for ins in inserts:
                                conn.execute(text("""
                                    INSERT INTO motivos_categorizados (
                                        tabla_origen, registro_id, campo_motivo,
                                        texto_motivo, texto_tipo, canal, metrica, score_metrica,
                                        categoria, confidence, metadata_categoria,
                                        es_ruido, razon_ruido
                                    ) VALUES (
                                        :tabla_origen, :registro_id, :campo_motivo,
                                        :texto_motivo, :texto_tipo, :canal, :metrica, :score_metrica,
                                        :categoria, :confidence, :metadata_categoria,
                                        :es_ruido, :razon_ruido
                                    )
                                    ON CONFLICT (tabla_origen, registro_id, campo_motivo)
                                    DO UPDATE SET
                                        texto_tipo = EXCLUDED.texto_tipo,
                                        categoria = EXCLUDED.categoria,
                                        confidence = EXCLUDED.confidence,
                                        metadata_categoria = EXCLUDED.metadata_categoria,
                                        es_ruido = EXCLUDED.es_ruido,
                                        razon_ruido = EXCLUDED.razon_ruido,
                                        categorizado_en = NOW()
                                """), ins)
                            conn.execute(text("COMMIT"))
                        except Exception as e:
                            conn.execute(text("ROLLBACK"))
                            logger.error(f"Error insertando batch: {e}")
                            raise

                    offset += batch_size
                    if offset % 10000 == 0:
                        logger.info(f"  Progreso: {offset:,} / {total:,} ({(offset/total)*100:.1f}%)")

    logger.info("Procesamiento completado")
    print("\n" + "=" * 80)
    print("RESUMEN DE PROCESAMIENTO")
    print("=" * 80)
    print(f"Total procesado: {total_processed:,}")
    print(f"Categorizados: {total_updated:,}")
    print(f"Rechazados: {total_rejected:,}")


def _ensure_category_table(engine):
    """Verifica que la tabla motivos_categorizados exista."""
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'motivos_categorizados'
        """)).fetchone()

        if not result:
            logger.error("La tabla motivos_categorizados NO existe!")
            logger.error("Ejecuta primero: python 10_crear_tabla_categorias.py")
            raise Exception("Tabla motivos_categorizados no encontrada")

        logger.info("✓ Tabla motivos_categorizados verificada")


# ============================================================================
# FUNCI�N PRINCIPAL
# ============================================================================

def parse_args():
    parser = argparse.ArgumentParser(
        description="Sistema de Limpieza y Categorizaci�n de Motivos NPS/CSAT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:

  # Exploraci�n inicial (recomendado primero)
  python 8_limpieza_categoria.py --mode explore --limit 10000

  # Procesamiento completo
  python 8_limpieza_categoria.py --mode process --batch-size 5000

  # Procesar solo sin categor�a
  python 8_limpieza_categoria.py --mode process --only-uncategorized
        """
    )

    parser.add_argument(
        "--mode",
        choices=["explore", "process"],
        required=True,
        help="Modo de operaci�n: explore (an�lisis) o process (actualizar BD)"
    )

    parser.add_argument(
        "--db-name",
        default="nps_analitycs",
        help="Nombre de la base de datos (default: nps_analitycs)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=10000,
        help="L�mite de registros para modo explore (default: 10000)"
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Tama�o de batch para modo process (default: 5000)"
    )

    parser.add_argument(
        "--only-uncategorized",
        action="store_true",
        help="Solo procesar registros sin categor�a"
    )

    parser.add_argument(
        "--min-confidence",
        type=float,
        default=MIN_CONFIDENCE_THRESHOLD,
        help=f"Score m�nimo de confianza (default: {MIN_CONFIDENCE_THRESHOLD})"
    )

    parser.add_argument(
        "--yes",
        action="store_true",
        help="Saltar confirmación y procesar directamente"
    )

    return parser.parse_args()


def main():
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    args = parse_args()

    # Banner
    print("=" * 80)
    print("SISTEMA DE LIMPIEZA Y CATEGORIZACIÓN DE MOTIVOS")
    print("=" * 80)
    print(f"Modo: {args.mode}")
    print(f"Base de datos: {args.db_name}")
    print(f"Confianza mínima: {args.min_confidence}")
    print("=" * 80 + "\n")

    # Cargar configuraci�n
    if not os.path.exists(CATEGORIAS_YAML):
        logger.error(f"No se encontr� el archivo de categor�as: {CATEGORIAS_YAML}")
        sys.exit(1)

    categorias_config = load_yaml(CATEGORIAS_YAML)

    # Inicializar componentes
    engine = get_engine(args.db_name)
    cleaner = TextCleaner(min_length=3, min_alpha_ratio=0.5)
    categorizer = CategorizerAhoCorasick(categorias_config)

    # Ejecutar seg�n modo
    if args.mode == "explore":
        explore_categories(engine, categorizer, cleaner, limit=args.limit)

    elif args.mode == "process":
        if args.yes:
            response = "yes"
        else:
            response = input("Esto insertara en motivos_categorizados. Continuar? (yes/no): ")
        if response.lower() == "yes":
            process_and_update_database(
                engine,
                categorizer,
                cleaner,
                batch_size=args.batch_size,
                only_uncategorized=args.only_uncategorized
            )
        else:
            print("Operaci�n cancelada")

    logger.info("Proceso finalizado")


if __name__ == "__main__":
    main()
