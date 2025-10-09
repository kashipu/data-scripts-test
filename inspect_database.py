#!/usr/bin/env python3
"""
Script para inspeccionar la estructura de la base de datos
Genera documentación completa de tablas, columnas, constraints e índices
"""

import psycopg2
from psycopg2 import sql
import pandas as pd
from tabulate import tabulate

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'test_nps',
    'user': 'postgres',
    'password': 'postgres'  # CAMBIA ESTO
}

def inspect_database():
    """Inspecciona y documenta la estructura completa de la base de datos"""

    print("="*80)
    print("INSPECCIÓN DE BASE DE DATOS - test_nps")
    print("="*80)

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        # 1. Listar todas las tablas
        print("\n[TABLAS EN LA BASE DE DATOS]")
        print("-"*80)
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)
        tables = cursor.fetchall()

        if not tables:
            print("No hay tablas en la base de datos")
            return

        for (table_name,) in tables:
            print(f"\n{'='*80}")
            print(f"TABLA: {table_name}")
            print('='*80)

            # 2. Información de columnas
            cursor.execute("""
                SELECT
                    column_name,
                    data_type,
                    character_maximum_length,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_name = %s
                ORDER BY ordinal_position
            """, (table_name,))

            columns = cursor.fetchall()

            print("\n[COLUMNAS]")
            print("-"*80)

            col_data = []
            for col in columns:
                col_name, data_type, max_length, nullable, default = col

                # Formatear tipo de dato
                if max_length:
                    type_str = f"{data_type}({max_length})"
                else:
                    type_str = data_type

                # Formatear nullable
                null_str = "NULL" if nullable == "YES" else "NOT NULL"

                # Formatear default
                default_str = default if default else "-"

                col_data.append([col_name, type_str, null_str, default_str])

            print(tabulate(col_data,
                          headers=['Columna', 'Tipo', 'Nullable', 'Default'],
                          tablefmt='grid'))

            # 3. Constraints (PRIMARY KEY, UNIQUE, FOREIGN KEY)
            cursor.execute("""
                SELECT
                    tc.constraint_name,
                    tc.constraint_type,
                    kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                    ON tc.constraint_name = kcu.constraint_name
                WHERE tc.table_name = %s
                ORDER BY tc.constraint_type, tc.constraint_name
            """, (table_name,))

            constraints = cursor.fetchall()

            if constraints:
                print(f"\n[CONSTRAINTS]")
                print("-"*80)

                const_data = []
                for const_name, const_type, col_name in constraints:
                    const_data.append([const_name, const_type, col_name])

                print(tabulate(const_data,
                              headers=['Constraint', 'Tipo', 'Columna(s)'],
                              tablefmt='grid'))

            # 4. Índices
            cursor.execute("""
                SELECT
                    indexname,
                    indexdef
                FROM pg_indexes
                WHERE tablename = %s
                ORDER BY indexname
            """, (table_name,))

            indexes = cursor.fetchall()

            if indexes:
                print(f"\n[INDICES]")
                print("-"*80)
                for idx_name, idx_def in indexes:
                    # Extrae solo la parte relevante de la definición
                    if 'USING' in idx_def:
                        idx_short = idx_def.split('USING')[1].strip()
                    else:
                        idx_short = idx_def
                    print(f"  • {idx_name}")
                    print(f"    {idx_short[:100]}")

            # 5. Estadísticas de la tabla
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            row_count = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{table_name}'))
            """)
            table_size = cursor.fetchone()[0]

            print(f"\n[ESTADISTICAS]")
            print("-"*80)
            print(f"  Registros: {row_count:,}")
            print(f"  Tamaño: {table_size}")

            # 6. Muestra de datos (primeras 3 filas)
            print(f"\n[MUESTRA DE DATOS - primeras 3 filas]")
            print("-"*80)

            try:
                df_sample = pd.read_sql(f"SELECT * FROM {table_name} LIMIT 3", conn)

                # Muestra solo las primeras 8 columnas para que quepa en pantalla
                if len(df_sample.columns) > 8:
                    cols_to_show = df_sample.columns[:8].tolist()
                    print(f"Mostrando primeras 8 de {len(df_sample.columns)} columnas")
                    print(df_sample[cols_to_show].to_string(index=False, max_colwidth=30))
                    print(f"... y {len(df_sample.columns) - 8} columnas más")
                else:
                    print(df_sample.to_string(index=False, max_colwidth=30))
            except Exception as e:
                print(f"No se pudo mostrar muestra: {e}")

            # 7. Archivos únicos procesados (si existe columna source_file)
            cursor.execute("""
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = %s AND column_name = 'source_file'
            """, (table_name,))

            if cursor.fetchone():
                cursor.execute(f"""
                    SELECT
                        source_file,
                        COUNT(*) as registros,
                        MAX(inserted_at) as ultima_insercion
                    FROM {table_name}
                    GROUP BY source_file
                    ORDER BY ultima_insercion DESC
                    LIMIT 5
                """)

                files = cursor.fetchall()

                if files:
                    print(f"\n[ARCHIVOS PROCESADOS - ultimos 5]")
                    print("-"*80)

                    file_data = []
                    for file_name, count, last_insert in files:
                        file_data.append([file_name, f"{count:,}", str(last_insert)])

                    print(tabulate(file_data,
                                  headers=['Archivo', 'Registros', 'Última Inserción'],
                                  tablefmt='grid'))

        # Resumen general
        print(f"\n{'='*80}")
        print("[RESUMEN GENERAL]")
        print('='*80)

        cursor.execute("""
            SELECT
                schemaname,
                COUNT(*) as num_tables,
                pg_size_pretty(SUM(pg_total_relation_size(schemaname||'.'||tablename))) as total_size
            FROM pg_tables
            WHERE schemaname = 'public'
            GROUP BY schemaname
        """)

        summary = cursor.fetchone()
        if summary:
            schema, num_tables, total_size = summary
            print(f"Schema: {schema}")
            print(f"Total de tablas: {num_tables}")
            print(f"Tamaño total: {total_size}")

        cursor.close()
        conn.close()

        print("\n[OK] Inspeccion completada")

    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] No se pudo conectar a PostgreSQL")
        print(f"  Verifica configuración en DB_CONFIG")
        print(f"  Detalle: {e}")

    except Exception as e:
        print(f"\n[ERROR]: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        inspect_database()
    except ModuleNotFoundError:
        print("\n[ADVERTENCIA] Falta el modulo 'tabulate'")
        print("Instala con: pip install tabulate")
        print("\nEjecutando versión simplificada...\n")

        # Versión simplificada sin tabulate
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """)

        print("Tablas encontradas:")
        for (table,) in cursor.fetchall():
            print(f"  - {table}")

            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"    Registros: {count:,}")

        cursor.close()
        conn.close()
