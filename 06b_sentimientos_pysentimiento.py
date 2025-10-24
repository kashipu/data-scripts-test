#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Análisis de sentimientos con pysentimiento
Ventaja: 300-500x más rápido que Ollama, detecta intensidad emocional
"""

import argparse
import logging
import sys
from datetime import datetime
from sqlalchemy import create_engine, text
import pandas as pd
import yaml
from pathlib import Path

# Config
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

BATCH_SIZE = 1000
PALABRAS_YML = "palabras_clave_sentimientos.yml"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('sentimientos_py.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================================================================================
# FUNCIONES
# ======================================================================================

def get_engine():
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)

def cargar_palabras_clave():
    """Carga palabras clave desde YML"""
    yml_path = Path(PALABRAS_YML)
    if not yml_path.exists():
        logger.warning(f"Archivo {PALABRAS_YML} no encontrado, usando palabras por defecto")
        return {
            'positivas': ['excelente', 'bueno', 'genial'],
            'negativas': ['malo', 'pésimo', 'horrible'],
            'ofensivas': ['mierda', 'idiota', 'ladrones']
        }

    with open(yml_path, 'r', encoding='utf-8') as f:
        palabras = yaml.safe_load(f)

    logger.info(f"✅ Palabras clave cargadas: {len(palabras.get('ofensivas', []))} ofensivas")
    return palabras

def verificar_columnas(engine):
    """Crea columnas necesarias si no existen"""
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE respuestas_nps_csat
            ADD COLUMN IF NOT EXISTS sentimiento_py TEXT,
            ADD COLUMN IF NOT EXISTS confianza_py NUMERIC(5,4),
            ADD COLUMN IF NOT EXISTS emocion TEXT,
            ADD COLUMN IF NOT EXISTS intensidad_emocional NUMERIC(5,4),
            ADD COLUMN IF NOT EXISTS metodo_analisis TEXT
        """))
        conn.commit()
        logger.info("✅ Columnas verificadas")

def cargar_modelos():
    """Carga modelos de pysentimiento"""
    try:
        from pysentimiento import create_analyzer

        logger.info("Cargando modelos pysentimiento...")
        sentiment_analyzer = create_analyzer(task="sentiment", lang="es")
        emotion_analyzer = create_analyzer(task="emotion", lang="es")
        hate_analyzer = create_analyzer(task="hate_speech", lang="es")

        logger.info("✅ Modelos cargados")
        return sentiment_analyzer, emotion_analyzer, hate_analyzer

    except ImportError:
        logger.error("❌ Instala: pip install pysentimiento transformers torch")
        raise

def detectar_ofensivo(texto, palabras_ofensivas):
    """Detecta palabras ofensivas"""
    texto_lower = texto.lower()
    return any(palabra in texto_lower for palabra in palabras_ofensivas)

def analizar_texto(texto, analyzers, palabras_ofensivas):
    """
    Analiza texto con pysentimiento
    Returns: (sentimiento, confianza, emocion, intensidad, es_ofensivo)
    """
    sentiment_analyzer, emotion_analyzer, hate_analyzer = analyzers

    try:
        # Sentimiento
        sent_result = sentiment_analyzer.predict(texto)
        sentiment_map = {'POS': 'POSITIVO', 'NEG': 'NEGATIVO', 'NEU': 'NEUTRAL'}
        sentimiento = sentiment_map[sent_result.output]
        confianza = float(sent_result.probas[sent_result.output])

        # Emoción e intensidad
        emo_result = emotion_analyzer.predict(texto)
        emocion = emo_result.output  # joy, anger, sadness, fear, etc.
        intensidad = float(emo_result.probas[emo_result.output])

        # Ofensivo (AI + keywords)
        hate_result = hate_analyzer.predict(texto)
        es_ofensivo_ai = (hate_result.output == 'hateful')
        es_ofensivo_kw = detectar_ofensivo(texto, palabras_ofensivas)
        es_ofensivo = es_ofensivo_ai or es_ofensivo_kw

        return (sentimiento, confianza, emocion, intensidad, es_ofensivo)

    except Exception as e:
        logger.warning(f"Error analizando: {str(e)[:50]}")
        es_ofensivo = detectar_ofensivo(texto, palabras_ofensivas)
        return ('NEUTRAL', 0.5, None, 0.0, es_ofensivo)

def procesar_lote(df, analyzers, palabras_ofensivas):
    """Procesa un lote de registros"""
    resultados = []

    for _, row in df.iterrows():
        texto = row['motivo_texto']

        if pd.isna(texto) or len(str(texto).strip()) < 2:
            resultados.append({
                'id': row['id'],
                'sentimiento': 'NEUTRAL',
                'confianza': 0.5,
                'emocion': None,
                'intensidad': 0.0,
                'es_ofensivo': False
            })
            continue

        sent, conf, emo, inten, ofensivo = analizar_texto(
            str(texto), analyzers, palabras_ofensivas
        )

        resultados.append({
            'id': row['id'],
            'sentimiento': sent,
            'confianza': conf,
            'emocion': emo,
            'intensidad': inten,
            'es_ofensivo': ofensivo
        })

    return pd.DataFrame(resultados)

def actualizar_bd(engine, resultados_df):
    """Actualiza BD con resultados"""
    actualizados = 0

    with engine.connect() as conn:
        for _, row in resultados_df.iterrows():
            try:
                conn.execute(text("""
                    UPDATE respuestas_nps_csat
                    SET sentimiento_py = :sentimiento,
                        confianza_py = :confianza,
                        emocion = :emocion,
                        intensidad_emocional = :intensidad,
                        es_ofensivo = :es_ofensivo,
                        metodo_analisis = 'pysentimiento'
                    WHERE id = :id
                """), {
                    "id": row['id'],
                    "sentimiento": row['sentimiento'],
                    "confianza": round(row['confianza'], 4),
                    "emocion": row['emocion'],
                    "intensidad": round(row['intensidad'], 4) if row['intensidad'] else None,
                    "es_ofensivo": bool(row['es_ofensivo'])
                })
                actualizados += 1
            except Exception as e:
                logger.error(f"Error actualizando {row['id']}: {e}")

        conn.commit()

    return actualizados

def main():
    parser = argparse.ArgumentParser(description='Análisis con pysentimiento')
    parser.add_argument('--limit', type=int, default=1000,
                        help='Registros a procesar (0 = todos)')
    args = parser.parse_args()

    print("=" * 70)
    print("ANÁLISIS DE SENTIMIENTOS - PYSENTIMIENTO")
    print("=" * 70)

    # Conectar
    try:
        engine = get_engine()
        logger.info("✅ Conectado a PostgreSQL")
    except Exception as e:
        logger.error(f"❌ Error BD: {e}")
        sys.exit(1)

    # Setup
    verificar_columnas(engine)
    palabras = cargar_palabras_clave()
    palabras_ofensivas = palabras.get('ofensivas', [])

    # Cargar modelos
    try:
        analyzers = cargar_modelos()
    except Exception:
        sys.exit(1)

    # Contar pendientes
    with engine.connect() as conn:
        total_pendientes = conn.execute(text("""
            SELECT COUNT(*) FROM respuestas_nps_csat
            WHERE motivo_texto IS NOT NULL
              AND LENGTH(TRIM(motivo_texto)) > 0
              AND sentimiento_py IS NULL
              AND es_ruido = FALSE
        """)).fetchone()[0]

    if total_pendientes == 0:
        logger.info("✅ No hay pendientes")
        sys.exit(0)

    limit = total_pendientes if args.limit == 0 else min(args.limit, total_pendientes)
    logger.info(f"📊 Procesando: {limit:,} de {total_pendientes:,}")

    # Estadísticas
    stats = {
        'procesados': 0,
        'positivos': 0,
        'negativos': 0,
        'neutrales': 0,
        'ofensivos': 0,
        'inicio': datetime.now()
    }

    # Procesar
    offset = 0
    while offset < limit:
        batch_limit = min(BATCH_SIZE, limit - offset)

        query = """
            SELECT id, motivo_texto
            FROM respuestas_nps_csat
            WHERE motivo_texto IS NOT NULL
              AND LENGTH(TRIM(motivo_texto)) > 0
              AND sentimiento_py IS NULL
              AND es_ruido = FALSE
            ORDER BY id
            LIMIT :lim OFFSET :off
        """

        with engine.connect() as conn:
            df = pd.read_sql(text(query), conn, params={"lim": batch_limit, "off": offset})

        if len(df) == 0:
            break

        logger.info(f"Lote {offset:,} - {offset + len(df):,}")

        # Analizar
        resultados_df = procesar_lote(df, analyzers, palabras_ofensivas)

        # Guardar
        actualizados = actualizar_bd(engine, resultados_df)

        # Stats
        stats['procesados'] += actualizados
        stats['positivos'] += (resultados_df['sentimiento'] == 'POSITIVO').sum()
        stats['negativos'] += (resultados_df['sentimiento'] == 'NEGATIVO').sum()
        stats['neutrales'] += (resultados_df['sentimiento'] == 'NEUTRAL').sum()
        stats['ofensivos'] += resultados_df['es_ofensivo'].sum()

        progreso = (offset + len(df)) / limit * 100
        logger.info(f"  {progreso:.1f}% ({stats['procesados']} ok)")

        offset += len(df)

    # Resumen
    duracion = datetime.now() - stats['inicio']
    velocidad = stats['procesados'] / duracion.total_seconds() if duracion.total_seconds() > 0 else 0

    print("\n" + "=" * 70)
    print("📊 RESUMEN")
    print("=" * 70)
    print(f"Procesados: {stats['procesados']:,}")
    total_validos = stats['positivos'] + stats['negativos'] + stats['neutrales']
    if total_validos > 0:
        print(f"\nSentimientos:")
        print(f"  POSITIVO: {stats['positivos']:,} ({stats['positivos']/total_validos*100:.1f}%)")
        print(f"  NEGATIVO: {stats['negativos']:,} ({stats['negativos']/total_validos*100:.1f}%)")
        print(f"  NEUTRAL:  {stats['neutrales']:,} ({stats['neutrales']/total_validos*100:.1f}%)")
    print(f"\nOfensivos: {stats['ofensivos']:,} ({stats['ofensivos']/stats['procesados']*100:.1f}%)")
    print(f"\nTiempo: {duracion}")
    print(f"Velocidad: {velocidad:.1f} reg/seg")
    print("=" * 70)

    print("\n✅ Completado")

if __name__ == "__main__":
    main()
