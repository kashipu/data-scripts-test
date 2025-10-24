#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Refinamiento de sentimientos - Sistema simple de validación
"""

import argparse
import sys
from sqlalchemy import create_engine, text
import pandas as pd
import yaml
from pathlib import Path

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

def get_engine():
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)

def cargar_palabras():
    """Carga palabras del YML"""
    yml_path = Path('palabras_clave_sentimientos.yml')
    if yml_path.exists():
        with open(yml_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    return {}

def validar_consistencia_score(row):
    """Valida sentimiento vs score"""
    sentimiento = row.get('sentimiento_py')
    score = row.get('score')
    metrica = row.get('metrica')

    if pd.isna(score) or pd.isna(sentimiento):
        return True, None

    recomendacion = None

    if metrica == 'NPS':
        if score <= 6 and sentimiento != 'NEGATIVO':
            recomendacion = 'NEGATIVO'
        elif score >= 9 and sentimiento != 'POSITIVO':
            recomendacion = 'POSITIVO'
    elif metrica == 'CSAT':
        if score <= 2 and sentimiento != 'NEGATIVO':
            recomendacion = 'NEGATIVO'
        elif score >= 4 and sentimiento != 'POSITIVO':
            recomendacion = 'POSITIVO'

    return (recomendacion is None), recomendacion

def analizar(engine):
    """Analiza inconsistencias"""
    print("\n" + "=" * 70)
    print("ANÁLISIS DE INCONSISTENCIAS")
    print("=" * 70)

    # Inconsistencias score
    query = """
        SELECT
            id, metrica, score, sentimiento_py, motivo_texto
        FROM respuestas_nps_csat
        WHERE sentimiento_py IS NOT NULL
          AND (
              (metrica = 'NPS' AND score <= 6 AND sentimiento_py != 'NEGATIVO')
              OR (metrica = 'NPS' AND score >= 9 AND sentimiento_py != 'POSITIVO')
              OR (metrica = 'CSAT' AND score <= 2 AND sentimiento_py != 'NEGATIVO')
              OR (metrica = 'CSAT' AND score >= 4 AND sentimiento_py != 'POSITIVO')
          )
        LIMIT 20
    """

    df = pd.read_sql(text(query), engine)

    print(f"\nInconsistencias encontradas: {len(df)}")
    if len(df) > 0:
        print("\nEjemplos:")
        for _, row in df.head(10).iterrows():
            _, rec = validar_consistencia_score(row)
            print(f"  ID {row['id']}: {row['metrica']} score={row['score']}")
            print(f"    Actual: {row['sentimiento_py']} → Recomendado: {rec}")
            print(f"    '{row['motivo_texto'][:80]}...'")

def validar(engine):
    """Valida calidad general"""
    print("\n" + "=" * 70)
    print("VALIDACIÓN DE CALIDAD")
    print("=" * 70)

    query = """
        SELECT
            COUNT(*) as total,
            COUNT(CASE WHEN sentimiento_py IS NOT NULL THEN 1 END) as analizados,
            COUNT(CASE WHEN es_ofensivo = TRUE THEN 1 END) as ofensivos,
            AVG(confianza_py) as confianza_promedio
        FROM respuestas_nps_csat
        WHERE motivo_texto IS NOT NULL
    """

    result = pd.read_sql(text(query), engine).iloc[0]

    print(f"\nTotal con texto: {result['total']:,}")
    print(f"Analizados: {result['analizados']:,} ({result['analizados']/result['total']*100:.1f}%)")
    print(f"Ofensivos: {result['ofensivos']:,} ({result['ofensivos']/result['total']*100:.1f}%)")
    print(f"Confianza promedio: {result['confianza_promedio']:.2f}")

    # Distribución
    dist_query = """
        SELECT
            sentimiento_py,
            COUNT(*) as total
        FROM respuestas_nps_csat
        WHERE sentimiento_py IS NOT NULL
        GROUP BY sentimiento_py
    """

    dist = pd.read_sql(text(dist_query), engine)
    total_dist = dist['total'].sum()

    print(f"\nDistribución:")
    for _, row in dist.iterrows():
        pct = (row['total'] / total_dist * 100) if total_dist > 0 else 0
        print(f"  {row['sentimiento_py']:10s}: {row['total']:,} ({pct:.1f}%)")

def exportar(engine, output):
    """Exporta casos para revisión"""
    print(f"\nExportando casos dudosos a {output}...")

    query = """
        SELECT
            id, metrica, score, motivo_texto,
            sentimiento_py, confianza_py, emocion, intensidad_emocional,
            es_ofensivo
        FROM respuestas_nps_csat
        WHERE sentimiento_py IS NOT NULL
          AND (
              confianza_py < 0.6
              OR (metrica = 'NPS' AND score <= 6 AND sentimiento_py != 'NEGATIVO')
              OR (metrica = 'NPS' AND score >= 9 AND sentimiento_py != 'POSITIVO')
              OR (sentimiento_py = 'NEUTRAL' AND (score <= 3 OR score >= 9))
          )
        LIMIT 500
    """

    df = pd.read_sql(text(query), engine)

    # Agregar sugerencia
    df['sugerencia'] = df.apply(lambda row: validar_consistencia_score(row)[1], axis=1)

    df.to_excel(output, index=False)
    print(f"✅ Exportados {len(df):,} casos a {output}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', type=str, default='analyze',
                        choices=['analyze', 'validate', 'export'])
    parser.add_argument('--output', type=str, default='casos_revisar.xlsx')
    args = parser.parse_args()

    try:
        engine = get_engine()
    except Exception as e:
        print(f"❌ Error BD: {e}")
        sys.exit(1)

    if args.mode == 'analyze':
        analizar(engine)
    elif args.mode == 'validate':
        validar(engine)
    elif args.mode == 'export':
        exportar(engine, args.output)

    print("\n✅ Completado")

if __name__ == "__main__":
    main()
