#!/usr/bin/env python3
"""
Script de análisis completo de estructura y métricas NPS
Base de datos: test_nps
Tablas: banco_movil_clean, banco_virtual_clean
"""

import psycopg2
from tabulate import tabulate

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'test_nps',
    'user': 'postgres',
    'password': 'postgres'  # CAMBIA ESTO
}

def analizar_estructura():
    """Analiza estructura detallada de las tablas de producción"""

    conn = psycopg2.connect(**DB_CONFIG)
    cursor = conn.cursor()

    print("="*100)
    print("ANÁLISIS COMPLETO DE ESTRUCTURA Y DATOS - test_nps")
    print("="*100)

    tablas = ['banco_movil_clean', 'banco_virtual_clean']

    for tabla in tablas:
        print(f"\n{'='*100}")
        print(f"TABLA: {tabla}")
        print('='*100)

        # 1. Columnas
        cursor.execute("""
            SELECT
                column_name,
                data_type,
                character_maximum_length,
                is_nullable
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
        """, (tabla,))

        columnas = cursor.fetchall()

        print(f"\n[COLUMNAS] ({len(columnas)} columnas)")
        print("-"*100)

        col_data = []
        for col_name, data_type, max_length, nullable in columnas:
            if max_length:
                tipo = f"{data_type}({max_length})"
            else:
                tipo = data_type
            null_str = "NULL" if nullable == "YES" else "NOT NULL"
            col_data.append([col_name, tipo, null_str])

        print(tabulate(col_data, headers=['Columna', 'Tipo', 'Nullable'], tablefmt='grid'))

        # 2. Estadísticas básicas
        cursor.execute(f"SELECT COUNT(*) FROM {tabla}")
        total = cursor.fetchone()[0]

        cursor.execute(f"SELECT pg_size_pretty(pg_total_relation_size('{tabla}'))")
        tamano = cursor.fetchone()[0]

        print(f"\n[ESTADÍSTICAS]")
        print("-"*100)
        print(f"Registros totales: {total:,}")
        print(f"Tamaño: {tamano}")

        # 3. Distribución NPS
        print(f"\n[DISTRIBUCIÓN NPS]")
        print("-"*100)

        cursor.execute(f"""
            SELECT
                nps_category,
                COUNT(*) as cantidad,
                ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as porcentaje
            FROM {tabla}
            WHERE nps_category IS NOT NULL
            GROUP BY nps_category
            ORDER BY
                CASE nps_category
                    WHEN 'Detractor' THEN 1
                    WHEN 'Neutral' THEN 2
                    WHEN 'Promotor' THEN 3
                END
        """)

        dist = cursor.fetchall()
        if dist:
            dist_data = [[cat, f"{cant:,}", f"{porc}%"] for cat, cant, porc in dist]
            print(tabulate(dist_data, headers=['Categoría', 'Cantidad', '%'], tablefmt='grid'))

        # 4. Rango de fechas
        print(f"\n[RANGO DE FECHAS]")
        print("-"*100)

        if tabla == 'banco_movil_clean':
            cursor.execute(f"""
                SELECT
                    MIN(answer_date) as primera,
                    MAX(answer_date) as ultima,
                    COUNT(DISTINCT month_year) as meses
                FROM {tabla}
            """)
        else:
            cursor.execute(f"""
                SELECT
                    MIN(date_submitted) as primera,
                    MAX(date_submitted) as ultima,
                    COUNT(DISTINCT month_year) as meses
                FROM {tabla}
            """)

        primera, ultima, meses = cursor.fetchone()
        print(f"Primera fecha: {primera}")
        print(f"Última fecha: {ultima}")
        print(f"Meses únicos: {meses}")

        # 5. Top archivos
        cursor.execute(f"""
            SELECT source_file, COUNT(*) as registros
            FROM {tabla}
            GROUP BY source_file
            ORDER BY registros DESC
            LIMIT 5
        """)

        archivos = cursor.fetchall()
        if archivos:
            print(f"\n[TOP 5 ARCHIVOS FUENTE]")
            print("-"*100)
            arch_data = [[arch, f"{reg:,}"] for arch, reg in archivos]
            print(tabulate(arch_data, headers=['Archivo', 'Registros'], tablefmt='grid'))

    # Resumen comparativo
    print(f"\n{'='*100}")
    print("[RESUMEN COMPARATIVO BM vs BV]")
    print('='*100)

    cursor.execute("""
        SELECT
            'Banco Móvil' as fuente,
            COUNT(*) as registros,
            AVG(nps_score) as nps_promedio,
            pg_size_pretty(pg_total_relation_size('banco_movil_clean')) as tamano
        FROM banco_movil_clean
        UNION ALL
        SELECT
            'Banco Virtual',
            COUNT(*),
            AVG(nps_score),
            pg_size_pretty(pg_total_relation_size('banco_virtual_clean'))
        FROM banco_virtual_clean
    """)

    resumen = cursor.fetchall()
    resumen_data = [[f, f"{r:,}", f"{nps:.2f}" if nps else "N/A", t]
                    for f, r, nps, t in resumen]
    print(tabulate(resumen_data,
                  headers=['Fuente', 'Registros', 'NPS Promedio', 'Tamaño'],
                  tablefmt='grid'))

    cursor.close()
    conn.close()

    print("\n[OK] Análisis completado")

if __name__ == "__main__":
    try:
        analizar_estructura()
    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] No se pudo conectar a PostgreSQL")
        print(f"Verifica DB_CONFIG y que PostgreSQL esté corriendo")
        print(f"Detalle: {e}")
    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()
