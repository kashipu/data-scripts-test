#!/usr/bin/env python3
"""
======================================================================================
SCRIPT: 05_categorizar_motivos.py
======================================================================================
Sistema de Categorización de Motivos NPS/CSAT

PROPÓSITO:
    Categoriza automáticamente los motivos de respuestas NPS/CSAT y actualiza
    los campos de categorización en la tabla unificada.

QUÉ HACE:
    1. Lee motivos sin categorizar de respuestas_nps_csat
    2. Aplica filtros de ruido (textos sin sentido)
    3. Categoriza usando algoritmo Aho-Corasick (rápido)
    4. Calcula scores de confianza
    5. Actualiza campos: categoria, categoria_confianza, es_ruido, razon_ruido

CATEGORÍAS:
    Definidas en: categorias/categorias.yml

USO:
    # Exploración inicial (recomendado primero)
    python 05_categorizar_motivos.py --mode explore --limit 10000

    # Procesamiento completo con actualización de BD
    python 05_categorizar_motivos.py --mode process --batch-size 5000

    # Procesar solo motivos sin categorizar
    python 05_categorizar_motivos.py --mode process --only-uncategorized

SIGUIENTE PASO:
    python 06_analisis_sentimientos.py
======================================================================================
"""

import argparse
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import ahocorasick
import pandas as pd
import yaml
from sqlalchemy import create_engine, text

# ============================================================================
# FUNCIONES HELPER BÁSICAS
# ============================================================================

def get_engine(db_name='nps_analitycs'):
    """Crea conexión a PostgreSQL"""
    conn_string = f"postgresql://postgres:postgres@localhost:5432/{db_name}?client_encoding=utf8"
    return create_engine(conn_string)

def load_yaml(file_path):
    """Carga archivo YAML"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def normalize_text(text):
    """Normaliza texto: lowercase, sin acentos, sin puntuación extra"""
    if pd.isna(text) or text is None:
        return ""
    text = str(text).lower().strip()
    # Remover acentos
    text = text.replace('á', 'a').replace('é', 'e').replace('í', 'i')
    text = text.replace('ó', 'o').replace('ú', 'u').replace('ñ', 'n')
    # Normalizar espacios
    text = re.sub(r'\s+', ' ', text)
    return text

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CATEGORIAS_YAML = "categorias/categorias.yml"
MIN_CONFIDENCE_THRESHOLD = 0.3  # Score mínimo para aceptar categorización
LOG_FILE = "categorizacion_datos.log"

# Configuración de logging
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
# CLASES
# ============================================================================

class TextCleaner:
    """Detecta y filtra textos sin sentido (ruido)"""

    def __init__(self, min_length=3, min_alpha_ratio=0.5):
        self.min_length = min_length
        self.min_alpha_ratio = min_alpha_ratio

    def is_valid(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Valida si un texto es válido o es ruido
        Returns: (is_valid, reason_if_invalid)
        """
        if pd.isna(text) or not text or not str(text).strip():
            return (False, "texto_vacio")

        text_clean = str(text).strip()

        # Muy corto
        if len(text_clean) < self.min_length:
            return (False, "muy_corto")

        # Demasiados caracteres no alfabéticos
        alpha_chars = sum(c.isalpha() for c in text_clean)
        if alpha_chars == 0:
            return (False, "sin_letras")

        ratio = alpha_chars / len(text_clean)
        if ratio < self.min_alpha_ratio:
            return (False, "pocos_caracteres_alfabeticos")

        # Caracteres repetidos (ej: "aaaaaaa", "......")
        if re.search(r'(.)\1{5,}', text_clean):
            return (False, "caracteres_repetidos")

        # Solo puntuación
        if re.match(r'^[^\w\s]+$', text_clean):
            return (False, "solo_puntuacion")

        return (True, None)


class CategorizerAhoCorasick:
    """Categorizador usando Aho-Corasick (algoritmo rápido para matching de patrones)"""

    def __init__(self, categorias_config: dict):
        self.categorias = categorias_config.get('categorias', [])
        self.automaton = self._build_automaton()

    def _build_automaton(self):
        """Construye el autómata de Aho-Corasick"""
        A = ahocorasick.Automaton()

        for categoria in self.categorias:
            nombre = categoria['nombre']
            palabras_clave = categoria.get('palabras_clave', [])

            for palabra in palabras_clave:
                palabra_norm = normalize_text(palabra)
                if palabra_norm:
                    # Almacenar tupla (nombre_categoria, palabra_original)
                    A.add_word(palabra_norm, (nombre, palabra))

        A.make_automaton()
        return A

    def categorize(self, text: str) -> Tuple[str, float, dict]:
        """
        Categoriza un texto
        Returns: (categoria, confidence, metadata)
        """
        if not text or pd.isna(text):
            return ("Otros", 0.0, {})

        text_norm = normalize_text(text)
        if not text_norm:
            return ("Otros", 0.0, {})

        # Buscar coincidencias
        matches = defaultdict(list)
        for end_index, (categoria, palabra) in self.automaton.iter(text_norm):
            matches[categoria].append(palabra)

        if not matches:
            return ("Otros", 0.0, {})

        # Calcular score por categoría
        categoria_scores = {}
        for categoria, palabras in matches.items():
            # Score = número de palabras clave encontradas
            score = len(palabras)
            categoria_scores[categoria] = score

        # Categoría ganadora
        best_categoria = max(categoria_scores, key=categoria_scores.get)
        best_score = categoria_scores[best_categoria]

        # Calcular confianza (normalizada)
        total_matches = sum(categoria_scores.values())
        confidence = best_score / total_matches if total_matches > 0 else 0.0

        metadata = {
            "palabras_encontradas": matches[best_categoria][:5],  # Primeras 5
            "total_coincidencias": best_score
        }

        return (best_categoria, confidence, metadata)


# ============================================================================
# FUNCIONES PRINCIPALES
# ============================================================================

def explore_categories(engine, categorizer, cleaner, limit=1000):
    """
    Modo exploración: muestra estadísticas sin actualizar la BD
    """
    logger.info("=" * 70)
    logger.info("MODO EXPLORACIÓN - Análisis de Categorización")
    logger.info("=" * 70)

    # Leer muestra de motivos sin categorizar
    query = """
        SELECT id, canal, metrica, motivo_texto, score
        FROM respuestas_nps_csat
        WHERE motivo_texto IS NOT NULL
          AND LENGTH(TRIM(motivo_texto)) > 0
          AND categoria IS NULL
        ORDER BY RANDOM()
        LIMIT :limit
    """

    with engine.connect() as conn:
        result = conn.execute(text(query), {"limit": limit})
        rows = result.fetchall()

    if not rows:
        logger.info("No hay motivos sin categorizar")
        return

    logger.info(f"Analizando {len(rows)} motivos...")

    # Estadísticas
    stats = {
        'total': len(rows),
        'validos': 0,
        'ruido': 0,
        'categorias': Counter(),
        'ruido_razones': Counter(),
        'confianza_promedio': 0.0
    }

    confidencias = []

    for row in rows:
        registro_id, canal, metrica, texto, score = row

        # Validar
        is_valid, reason = cleaner.is_valid(texto)

        if not is_valid:
            stats['ruido'] += 1
            stats['ruido_razones'][reason] += 1
        else:
            stats['validos'] += 1
            categoria, confidence, metadata = categorizer.categorize(texto)
            stats['categorias'][categoria] += 1
            confidencias.append(confidence)

    stats['confianza_promedio'] = sum(confidencias) / len(confidencias) if confidencias else 0.0

    # Mostrar resultados
    print("\n" + "=" * 70)
    print("📊 RESULTADOS DE EXPLORACIÓN")
    print("=" * 70)
    print(f"Total analizado: {stats['total']:,}")
    print(f"Textos válidos: {stats['validos']:,} ({stats['validos']/stats['total']*100:.1f}%)")
    print(f"Textos ruido: {stats['ruido']:,} ({stats['ruido']/stats['total']*100:.1f}%)")
    print(f"\n📈 Confianza promedio: {stats['confianza_promedio']:.3f}")

    print(f"\n🏷️  Top 10 Categorías:")
    for categoria, count in stats['categorias'].most_common(10):
        pct = count / stats['validos'] * 100 if stats['validos'] > 0 else 0
        print(f"  {categoria:40s}: {count:6,} ({pct:5.1f}%)")

    print(f"\n🗑️  Razones de Rechazo (Ruido):")
    for razon, count in stats['ruido_razones'].most_common():
        pct = count / stats['ruido'] * 100 if stats['ruido'] > 0 else 0
        print(f"  {razon:30s}: {count:6,} ({pct:5.1f}%)")

    print("\n" + "=" * 70)
    print("💡 Para procesar y actualizar la BD:")
    print("   python 05_categorizar_motivos.py --mode process")
    print("=" * 70)


def process_and_update_database(engine, categorizer, cleaner, batch_size=5000, only_uncategorized=False):
    """
    Modo procesamiento: categoriza y actualiza la BD
    """
    logger.info("=" * 70)
    logger.info("MODO PROCESAMIENTO - Categorizando y Actualizando BD")
    logger.info("=" * 70)

    # Construir WHERE clause
    where_clause = """
        WHERE motivo_texto IS NOT NULL
          AND LENGTH(TRIM(motivo_texto)) > 0
    """
    if only_uncategorized:
        where_clause += " AND categoria IS NULL"

    # Contar total
    with engine.connect() as conn:
        count_result = conn.execute(text(f"SELECT COUNT(*) FROM respuestas_nps_csat {where_clause}")).fetchone()
        total = count_result[0]

    if total == 0:
        logger.info("No hay motivos para procesar")
        return

    logger.info(f"Total a procesar: {total:,}")

    # Estadísticas
    stats = {
        'total': total,
        'procesados': 0,
        'actualizados': 0,
        'ruido': 0,
        'errores': 0,
        'categorias': Counter()
    }

    # Procesar en lotes
    offset = 0
    while offset < total:
        logger.info(f"Procesando lote {offset:,} - {min(offset + batch_size, total):,} de {total:,}")

        # Leer lote
        query = f"""
            SELECT id, motivo_texto
            FROM respuestas_nps_csat
            {where_clause}
            ORDER BY id
            LIMIT :lim OFFSET :off
        """

        with engine.connect() as conn:
            rows = conn.execute(text(query), {"lim": batch_size, "off": offset}).fetchall()

            # Procesar cada registro
            for row in rows:
                registro_id, texto = row

                try:
                    # Validar
                    is_valid, reason = cleaner.is_valid(texto)

                    if not is_valid:
                        # Marcar como ruido
                        update_query = """
                            UPDATE respuestas_nps_csat
                            SET categoria = 'Texto Sin Sentido / Ruido',
                                categoria_confianza = 1.0,
                                es_ruido = TRUE,
                                razon_ruido = :razon
                            WHERE id = :id
                        """
                        conn.execute(text(update_query), {"id": registro_id, "razon": reason})
                        stats['ruido'] += 1
                    else:
                        # Categorizar
                        categoria, confidence, metadata = categorizer.categorize(texto)

                        update_query = """
                            UPDATE respuestas_nps_csat
                            SET categoria = :categoria,
                                categoria_confianza = :confidence,
                                es_ruido = FALSE,
                                razon_ruido = NULL
                            WHERE id = :id
                        """
                        conn.execute(text(update_query), {
                            "id": registro_id,
                            "categoria": categoria,
                            "confidence": round(confidence, 4)
                        })
                        stats['actualizados'] += 1
                        stats['categorias'][categoria] += 1

                    stats['procesados'] += 1

                except Exception as e:
                    logger.error(f"Error procesando registro {registro_id}: {str(e)}")
                    stats['errores'] += 1

            # Commit del lote
            conn.commit()

        offset += batch_size

        # Mostrar progreso
        if stats['procesados'] % 10000 == 0:
            logger.info(f"  Progreso: {stats['procesados']:,}/{total:,} ({stats['procesados']/total*100:.1f}%)")

    # Resumen final
    print("\n" + "=" * 70)
    print("📊 RESUMEN DE CATEGORIZACIÓN")
    print("=" * 70)
    print(f"Total procesados: {stats['procesados']:,}")
    print(f"Categorizados: {stats['actualizados']:,}")
    print(f"Marcados como ruido: {stats['ruido']:,}")
    print(f"Errores: {stats['errores']:,}")

    print(f"\n🏷️  Top 15 Categorías:")
    for categoria, count in stats['categorias'].most_common(15):
        pct = count / stats['actualizados'] * 100 if stats['actualizados'] > 0 else 0
        print(f"  {categoria:40s}: {count:6,} ({pct:5.1f}%)")

    print("\n" + "=" * 70)
    print("✅ Categorización completada")
    print("\n🎯 SIGUIENTE PASO:")
    print("   python 06_analisis_sentimientos.py")
    print("=" * 70)


# ============================================================================
# MAIN
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description='Categorización de motivos NPS/CSAT')
    parser.add_argument('--mode', choices=['explore', 'process'], required=True,
                        help='Modo de ejecución: explore (solo análisis) o process (actualizar BD)')
    parser.add_argument('--db-name', default='nps_analitycs', help='Nombre de la base de datos')
    parser.add_argument('--limit', type=int, default=10000,
                        help='Límite de registros para modo explore')
    parser.add_argument('--batch-size', type=int, default=5000,
                        help='Tamaño de lote para procesamiento')
    parser.add_argument('--only-uncategorized', action='store_true',
                        help='Procesar solo motivos sin categorizar')
    parser.add_argument('--yes', action='store_true',
                        help='No pedir confirmación (modo automatizado)')

    args = parser.parse_args()

    # Cargar configuración
    if not os.path.exists(CATEGORIAS_YAML):
        logger.error(f"No se encontró el archivo de categorías: {CATEGORIAS_YAML}")
        sys.exit(1)

    categorias_config = load_yaml(CATEGORIAS_YAML)

    # Inicializar componentes
    engine = get_engine(args.db_name)
    cleaner = TextCleaner(min_length=3, min_alpha_ratio=0.5)
    categorizer = CategorizerAhoCorasick(categorias_config)

    logger.info(f"Categorías cargadas: {len(categorizer.categorias)}")

    # Ejecutar según modo
    if args.mode == "explore":
        explore_categories(engine, categorizer, cleaner, limit=args.limit)

    elif args.mode == "process":
        if args.yes:
            response = "yes"
        else:
            response = input("Esto actualizará los campos de categorización en la BD. ¿Continuar? (yes/no): ")

        if response.lower() == "yes":
            process_and_update_database(
                engine,
                categorizer,
                cleaner,
                batch_size=args.batch_size,
                only_uncategorized=args.only_uncategorized
            )
        else:
            logger.info("Operación cancelada por el usuario")


if __name__ == "__main__":
    main()
