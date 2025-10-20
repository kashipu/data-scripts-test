#!/usr/bin/env python3
"""
Optimizador de Categorías - Análisis y Sugerencias
===================================================

Este script analiza:
1. Textos rechazados incorrectamente por los filtros
2. Textos categorizados como "Otros"
3. Genera sugerencias de palabras clave y nuevas categorías

Uso:
    python 9_optimizar_categorias.py --db-name nps_analitycs --limit 50000
"""

import argparse
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import pandas as pd
from sqlalchemy import text

# Imports del proyecto
sys.path.append(os.path.join(os.path.dirname(__file__), 'nueva_etl'))
from nueva_etl.utils import get_engine, load_yaml, normalize_text

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

CATEGORIAS_YAML = "nueva_etl/categorias.yml"
LOG_FILE = "optimizacion_categorias.log"

# Stopwords para filtrar palabras irrelevantes
STOPWORDS = {
    'el', 'la', 'los', 'las', 'un', 'una', 'unos', 'unas',
    'de', 'del', 'a', 'al', 'en', 'es', 'por', 'para', 'con', 'sin',
    'que', 'se', 'lo', 'le', 'su', 'sus', 'mi', 'mis', 'tu', 'tus',
    'muy', 'mas', 'pero', 'si', 'no', 'ya', 'solo', 'todo', 'toda',
    'o', 'y', 'e', 'ni', 'como', 'cuando', 'donde', 'porque',
    'me', 'te', 'nos', 'les', 'ha', 'he', 'han', 'hemos',
    'esta', 'este', 'estos', 'estas', 'esa', 'ese', 'esos', 'esas',
    'bueno', 'buena', 'buenos', 'buenas', 'bien', 'mal', 'malo', 'mala',
    'excelente', 'perfecto', 'genial', 'ok', 'gracias'
}

# ============================================================================
# CONFIGURACIÓN DE LOGGING
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
# FUNCIONES DE ANÁLISIS
# ============================================================================

def extract_ngrams(texts: List[str], n: int = 2, min_freq: int = 10) -> List[Tuple[str, int]]:
    """
    Extrae n-gramas (bigramas, trigramas) más frecuentes de los textos.

    Args:
        texts: Lista de textos a analizar
        n: Tamaño del n-grama (2 = bigrama, 3 = trigrama)
        min_freq: Frecuencia mínima para incluir

    Returns:
        Lista de (ngrama, frecuencia) ordenada por frecuencia descendente
    """
    ngrams = Counter()

    for text in texts:
        if not text:
            continue

        # Normalizar
        text_norm = normalize_text(text)

        # Extraer palabras
        palabras = re.findall(r'\b[a-záéíóúñ]+\b', text_norm)

        # Filtrar stopwords
        palabras = [p for p in palabras if p not in STOPWORDS and len(p) >= 3]

        # Generar n-gramas
        for i in range(len(palabras) - n + 1):
            ngram = ' '.join(palabras[i:i+n])
            ngrams[ngram] += 1

    # Filtrar por frecuencia mínima
    return [(ngram, freq) for ngram, freq in ngrams.most_common() if freq >= min_freq]


def extract_keywords(texts: List[str], min_freq: int = 20) -> List[Tuple[str, int]]:
    """
    Extrae palabras clave individuales más frecuentes.
    """
    keywords = Counter()

    for text in texts:
        if not text:
            continue

        text_norm = normalize_text(text)
        palabras = re.findall(r'\b[a-záéíóúñ]{3,}\b', text_norm)

        for palabra in palabras:
            if palabra not in STOPWORDS:
                keywords[palabra] += 1

    return [(kw, freq) for kw, freq in keywords.most_common() if freq >= min_freq]


def cluster_texts_by_similarity(texts: List[str], sample_size: int = 1000) -> Dict[str, List[str]]:
    """
    Agrupa textos similares basándose en palabras clave compartidas.
    Retorna clusters de textos relacionados.
    """
    # Limitar muestra para eficiencia
    import random
    if len(texts) > sample_size:
        texts = random.sample(texts, sample_size)

    clusters = defaultdict(list)

    for text in texts:
        text_norm = normalize_text(text)
        palabras = set(re.findall(r'\b[a-záéíóúñ]{4,}\b', text_norm))
        palabras = palabras - STOPWORDS

        if not palabras:
            continue

        # Usar las primeras 2-3 palabras significativas como clave del cluster
        cluster_key = ' '.join(sorted(list(palabras)[:3]))
        clusters[cluster_key].append(text[:100])  # Guardar solo primeros 100 chars

    # Filtrar clusters pequeños
    return {k: v for k, v in clusters.items() if len(v) >= 5}


def analyze_rejected_texts(engine, limit: int = 10000) -> pd.DataFrame:
    """
    Analiza textos que fueron rechazados por los filtros.
    Identifica posibles falsos positivos.
    """
    logger.info("Analizando textos rechazados...")

    # Obtener muestra de textos
    samples = []

    # BM - NPS
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT nps_recomendacion_motivo as texto
            FROM banco_movil_clean
            WHERE nps_recomendacion_motivo IS NOT NULL
            AND LENGTH(TRIM(nps_recomendacion_motivo)) > 0
            ORDER BY RANDOM()
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        samples.extend([r[0] for r in result])

    # BM - CSAT
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT csat_satisfaccion_motivo as texto
            FROM banco_movil_clean
            WHERE csat_satisfaccion_motivo IS NOT NULL
            AND LENGTH(TRIM(csat_satisfaccion_motivo)) > 0
            ORDER BY RANDOM()
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        samples.extend([r[0] for r in result])

    logger.info(f"Muestra obtenida: {len(samples)} textos")

    # Analizar con filtros actuales
    from nueva_etl.utils import get_engine
    sys.path.append(os.path.dirname(__file__))

    # Importar TextCleaner del script 8
    exec(open('8_limpieza_categoria.py', encoding='utf-8').read(), globals())
    cleaner = TextCleaner()

    rejected = []
    rejection_reasons = Counter()

    for text in samples:
        is_valid, reason = cleaner.is_valid(text)
        if not is_valid:
            rejected.append({
                'texto': text,
                'razon': reason,
                'longitud': len(text)
            })
            rejection_reasons[reason] += 1

    logger.info(f"Rechazados: {len(rejected)} de {len(samples)} ({len(rejected)/len(samples)*100:.1f}%)")

    return pd.DataFrame(rejected), rejection_reasons


def analyze_otros_category(engine, limit: int = 20000) -> Tuple[List[str], Dict]:
    """
    Analiza todos los textos para identificar patrones.
    Identifica patrones y posibles nuevas categorías.
    """
    logger.info("Analizando textos de motivos...")

    textos_otros = []

    # BM - NPS (todos los textos largos)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT nps_recomendacion_motivo
            FROM banco_movil_clean
            WHERE nps_recomendacion_motivo IS NOT NULL
            AND LENGTH(TRIM(nps_recomendacion_motivo)) > 10
            ORDER BY RANDOM()
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        textos_otros.extend([r[0] for r in result if r[0]])

    # BM - CSAT (todos los textos largos)
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT csat_satisfaccion_motivo
            FROM banco_movil_clean
            WHERE csat_satisfaccion_motivo IS NOT NULL
            AND LENGTH(TRIM(csat_satisfaccion_motivo)) > 10
            ORDER BY RANDOM()
            LIMIT :lim
        """), {"lim": limit}).fetchall()
        textos_otros.extend([r[0] for r in result if r[0]])

    logger.info(f"Textos 'Otros' encontrados: {len(textos_otros)}")

    # Extraer patrones
    keywords = extract_keywords(textos_otros, min_freq=50)
    bigrams = extract_ngrams(textos_otros, n=2, min_freq=30)
    trigrams = extract_ngrams(textos_otros, n=3, min_freq=20)

    return textos_otros, {
        'keywords': keywords[:50],
        'bigrams': bigrams[:30],
        'trigrams': trigrams[:20]
    }


def generate_yaml_suggestions(patterns: Dict, categorias_actuales: List[str]) -> str:
    """
    Genera sugerencias de mejoras para el YAML basándose en patrones encontrados.
    """
    suggestions = []

    suggestions.append("=" * 80)
    suggestions.append("SUGERENCIAS PARA MEJORAR categorias.yml")
    suggestions.append("=" * 80)
    suggestions.append("")
    suggestions.append(f"Generado: {datetime.now()}")
    suggestions.append("")

    # Palabras clave más frecuentes
    suggestions.append("PALABRAS CLAVE MÁS FRECUENTES EN 'OTROS':")
    suggestions.append("-" * 80)
    for keyword, freq in patterns['keywords'][:30]:
        suggestions.append(f"  {keyword:30} -> {freq:6} ocurrencias")
    suggestions.append("")

    # Bigramas (frases de 2 palabras)
    suggestions.append("FRASES DE 2 PALABRAS MÁS FRECUENTES:")
    suggestions.append("-" * 80)
    for bigram, freq in patterns['bigrams'][:20]:
        suggestions.append(f"  {bigram:40} -> {freq:6} ocurrencias")
    suggestions.append("")

    # Trigramas (frases de 3 palabras)
    suggestions.append("FRASES DE 3 PALABRAS MÁS FRECUENTES:")
    suggestions.append("-" * 80)
    for trigram, freq in patterns['trigrams'][:15]:
        suggestions.append(f"  {trigram:50} -> {freq:6} ocurrencias")
    suggestions.append("")

    # Sugerencias de categorías
    suggestions.append("POSIBLES NUEVAS CATEGORÍAS:")
    suggestions.append("-" * 80)

    # Analizar patrones y sugerir categorías
    categoria_sugerencias = analyze_patterns_for_categories(patterns)

    for categoria, palabras in categoria_sugerencias.items():
        suggestions.append(f"\n- nombre: {categoria}")
        suggestions.append("  palabras_clave:")
        for palabra in palabras[:15]:
            suggestions.append(f"  - {palabra}")

    suggestions.append("")
    suggestions.append("=" * 80)
    suggestions.append("RECOMENDACIONES:")
    suggestions.append("=" * 80)
    suggestions.append("")
    suggestions.append("1. Revisar las palabras clave más frecuentes")
    suggestions.append("2. Agregar bigramas/trigramas relevantes al YAML")
    suggestions.append("3. Considerar crear nuevas categorías para patrones no cubiertos")
    suggestions.append("4. Validar que las palabras clave no sean demasiado genéricas")
    suggestions.append("")

    return '\n'.join(suggestions)


def analyze_patterns_for_categories(patterns: Dict) -> Dict[str, List[str]]:
    """
    Analiza patrones y agrupa en posibles categorías nuevas.
    """
    categorias = defaultdict(list)

    # Analizar keywords y bigramas para identificar temas
    all_terms = []

    # Agregar keywords
    for keyword, freq in patterns['keywords'][:50]:
        all_terms.append((keyword, freq))

    # Agregar bigramas
    for bigram, freq in patterns['bigrams'][:30]:
        all_terms.append((bigram, freq))

    # Temas comunes en banca
    temas = {
        'Tarjetas': ['tarjeta', 'credito', 'debito', 'plastico', 'cupo'],
        'Productos': ['cuenta', 'ahorro', 'corriente', 'credito', 'prestamo', 'crédito'],
        'Canales': ['sucursal', 'oficina', 'cajero', 'corresponsal', 'punto'],
        'Aplicación Móvil': ['app', 'aplicacion', 'movil', 'celular', 'actualizacion', 'interfaz', 'diseño'],
        'Atención': ['atencion', 'servicio', 'asesor', 'llamada', 'respuesta', 'espera'],
        'Transacciones': ['transaccion', 'operacion', 'transferencia', 'pago', 'retiro', 'consignacion'],
        'Tasas y Tarifas': ['tasa', 'interes', 'tarifa', 'costo', 'cuota manejo', 'comision'],
        'Problemas Técnicos': ['error', 'falla', 'problema', 'funciona', 'carga', 'lento', 'caida'],
        'Seguridad': ['seguridad', 'fraude', 'robo', 'clave', 'bloqueo', 'autorizacion']
    }

    # Clasificar términos en temas
    for term, freq in all_terms:
        term_norm = normalize_text(term)

        for tema, keywords in temas.items():
            if any(kw in term_norm for kw in keywords):
                if term not in categorias[tema]:
                    categorias[tema].append(term)
                break

    return dict(categorias)


# ============================================================================
# FUNCIÓN PRINCIPAL
# ============================================================================

def main():
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    parser = argparse.ArgumentParser(
        description="Optimizador de Categorías - Análisis y Sugerencias"
    )

    parser.add_argument(
        "--db-name",
        default="nps_analitycs",
        help="Nombre de la base de datos (default: nps_analitycs)"
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=20000,
        help="Límite de registros a analizar (default: 20000)"
    )

    parser.add_argument(
        "--output-dir",
        default="outputs",
        help="Directorio de salida (default: outputs)"
    )

    args = parser.parse_args()

    # Banner
    print("=" * 80)
    print("OPTIMIZADOR DE CATEGORÍAS - ANÁLISIS Y SUGERENCIAS")
    print("=" * 80)
    print(f"Base de datos: {args.db_name}")
    print(f"Límite: {args.limit:,}")
    print("=" * 80 + "\n")

    # Crear directorio de salida
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)

    # Conectar a BD
    engine = get_engine(args.db_name)

    # Cargar YAML actual
    if not os.path.exists(CATEGORIAS_YAML):
        logger.error(f"No se encontró el archivo: {CATEGORIAS_YAML}")
        sys.exit(1)

    categorias_config = load_yaml(CATEGORIAS_YAML)
    categorias_actuales = [cat['nombre'] for cat in categorias_config.get('categorias', [])]

    logger.info(f"Categorías actuales: {len(categorias_actuales)}")

    # Analizar textos en "Otros"
    textos_otros, patterns = analyze_otros_category(engine, limit=args.limit)

    # Generar sugerencias
    suggestions = generate_yaml_suggestions(patterns, categorias_actuales)

    # Guardar reporte
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"sugerencias_yaml_{timestamp}.txt"

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(suggestions)

    logger.info(f"Reporte guardado: {report_path}")

    # Guardar muestras de textos "Otros"
    samples_path = output_dir / f"muestras_otros_{timestamp}.csv"
    df_samples = pd.DataFrame({
        'texto': textos_otros[:1000],
        'longitud': [len(t) for t in textos_otros[:1000]]
    })
    df_samples.to_csv(samples_path, index=False, encoding='utf-8')
    logger.info(f"Muestras guardadas: {samples_path}")

    # Resumen en consola
    print("\n" + "=" * 80)
    print("RESUMEN")
    print("=" * 80)
    print(f"\nArchivos generados:")
    print(f"  1. {report_path}")
    print(f"  2. {samples_path}")
    print(f"\nTextos analizados: {len(textos_otros):,}")
    print(f"Keywords únicos: {len(patterns['keywords'])}")
    print(f"Bigramas únicos: {len(patterns['bigrams'])}")
    print(f"\nTop 5 keywords:")
    for keyword, freq in patterns['keywords'][:5]:
        print(f"  - {keyword:20} ({freq:,} ocurrencias)")

    print("\n" + "=" * 80)
    print(f"Revisar el archivo: {report_path}")
    print("=" * 80)


if __name__ == "__main__":
    main()
