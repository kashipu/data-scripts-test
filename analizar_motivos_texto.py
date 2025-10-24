#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analiza cuántos registros tienen motivo_texto vs cuántos no
"""

from sqlalchemy import create_engine, text

def get_engine():
    """Crea conexión a PostgreSQL"""
    conn_string = f"postgresql://postgres:postgres@localhost:5432/nps_analitycs?client_encoding=utf8"
    return create_engine(conn_string)

def main():
    print("=" * 80)
    print("ANALISIS DE MOTIVOS_TEXTO EN BASE DE DATOS")
    print("=" * 80)

    engine = get_engine()

    with engine.connect() as conn:
        # Total de registros
        total_result = conn.execute(text("SELECT COUNT(*) FROM respuestas_nps_csat"))
        total = total_result.fetchone()[0]

        print(f"\nTotal de registros en BD: {total:,}")
        print("-" * 80)

        # Registros con motivo_texto NOT NULL y no vacío
        con_texto_result = conn.execute(text("""
            SELECT COUNT(*)
            FROM respuestas_nps_csat
            WHERE motivo_texto IS NOT NULL
              AND LENGTH(TRIM(motivo_texto)) > 0
        """))
        con_texto = con_texto_result.fetchone()[0]

        # Registros con motivo_texto NULL
        null_result = conn.execute(text("""
            SELECT COUNT(*)
            FROM respuestas_nps_csat
            WHERE motivo_texto IS NULL
        """))
        sin_texto_null = null_result.fetchone()[0]

        # Registros con motivo_texto vacío (solo espacios)
        vacio_result = conn.execute(text("""
            SELECT COUNT(*)
            FROM respuestas_nps_csat
            WHERE motivo_texto IS NOT NULL
              AND LENGTH(TRIM(motivo_texto)) = 0
        """))
        sin_texto_vacio = vacio_result.fetchone()[0]

        sin_texto_total = sin_texto_null + sin_texto_vacio

        print(f"\nRegistros CON motivo_texto:     {con_texto:,} ({con_texto/total*100:.2f}%)")
        print(f"Registros SIN motivo_texto:     {sin_texto_total:,} ({sin_texto_total/total*100:.2f}%)")
        print(f"  - motivo_texto IS NULL:       {sin_texto_null:,}")
        print(f"  - motivo_texto vacio:         {sin_texto_vacio:,}")

        print("\n" + "=" * 80)
        print("DESGLOSE POR METRICA")
        print("=" * 80)

        # Desglose por métrica
        metricas_result = conn.execute(text("""
            SELECT
                metrica,
                COUNT(*) as total,
                COUNT(CASE WHEN motivo_texto IS NOT NULL AND LENGTH(TRIM(motivo_texto)) > 0 THEN 1 END) as con_texto,
                COUNT(CASE WHEN motivo_texto IS NULL OR LENGTH(TRIM(motivo_texto)) = 0 THEN 1 END) as sin_texto
            FROM respuestas_nps_csat
            GROUP BY metrica
            ORDER BY metrica
        """))

        for row in metricas_result:
            metrica, total_m, con_texto_m, sin_texto_m = row
            print(f"\n{metrica}:")
            print(f"  Total:           {total_m:,}")
            print(f"  Con motivo:      {con_texto_m:,} ({con_texto_m/total_m*100:.2f}%)")
            print(f"  Sin motivo:      {sin_texto_m:,} ({sin_texto_m/total_m*100:.2f}%)")

        print("\n" + "=" * 80)
        print("DESGLOSE POR CANAL Y METRICA")
        print("=" * 80)

        canal_result = conn.execute(text("""
            SELECT
                canal,
                metrica,
                COUNT(*) as total,
                COUNT(CASE WHEN motivo_texto IS NOT NULL AND LENGTH(TRIM(motivo_texto)) > 0 THEN 1 END) as con_texto,
                COUNT(CASE WHEN motivo_texto IS NULL OR LENGTH(TRIM(motivo_texto)) = 0 THEN 1 END) as sin_texto
            FROM respuestas_nps_csat
            GROUP BY canal, metrica
            ORDER BY canal, metrica
        """))

        for row in canal_result:
            canal, metrica, total_m, con_texto_m, sin_texto_m = row
            print(f"\n{canal} - {metrica}:")
            print(f"  Total:           {total_m:,}")
            print(f"  Con motivo:      {con_texto_m:,} ({con_texto_m/total_m*100:.2f}%)")
            print(f"  Sin motivo:      {sin_texto_m:,} ({sin_texto_m/total_m*100:.2f}%)")

        print("\n" + "=" * 80)
        print("ESTADO DE CATEGORIZACION")
        print("=" * 80)

        # Verificar cuántos ya están categorizados
        cat_result = conn.execute(text("""
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN categoria IS NOT NULL THEN 1 END) as categorizados,
                COUNT(CASE WHEN categoria IS NULL THEN 1 END) as sin_categorizar
            FROM respuestas_nps_csat
            WHERE motivo_texto IS NOT NULL
              AND LENGTH(TRIM(motivo_texto)) > 0
        """))

        row = cat_result.fetchone()
        total_con_texto, categorizados, sin_cat = row

        print(f"\nRegistros con motivo_texto:     {total_con_texto:,}")
        print(f"  Categorizados:                {categorizados:,} ({categorizados/total_con_texto*100:.2f}%)")
        print(f"  Sin categorizar:              {sin_cat:,} ({sin_cat/total_con_texto*100:.2f}%)")

        # Top categorías
        if categorizados > 0:
            print("\n" + "-" * 80)
            print("Top 10 Categorias Actuales:")
            print("-" * 80)

            top_cat_result = conn.execute(text("""
                SELECT categoria, COUNT(*) as total
                FROM respuestas_nps_csat
                WHERE categoria IS NOT NULL
                GROUP BY categoria
                ORDER BY total DESC
                LIMIT 10
            """))

            for row in top_cat_result:
                cat, count = row
                print(f"  {cat:50s}: {count:,}")

        print("\n" + "=" * 80)
        print("\nCONCLUSION:")
        diferencia = total - con_texto
        print(f"Faltan procesar {diferencia:,} registros porque NO TIENEN motivo_texto")
        print(f"Esto es NORMAL: no todos los encuestados escriben un comentario")
        print("=" * 80)

if __name__ == "__main__":
    main()
