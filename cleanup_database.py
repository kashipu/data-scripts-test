#!/usr/bin/env python3
"""
Script para eliminar tablas obsoletas de desarrollo/testing de la base de datos
SOLO elimina tablas que NO se usan en producción
"""

import psycopg2
from psycopg2 import sql
import sys

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'  # CAMBIA ESTO
}

# Tablas obsoletas que se pueden eliminar de forma segura
OBSOLETE_TABLES = [
    'bm_sample_clean',
    'bv_sample_clean',
    'hello_nps',
    'test_nps_data'
]

# Tablas de producción que NUNCA deben eliminarse
PRODUCTION_TABLES = [
    'banco_movil_clean',
    'banco_virtual_clean'
]

def cleanup_database(dry_run=True):
    """
    Elimina tablas obsoletas de la base de datos

    Args:
        dry_run: Si es True, solo muestra qué se haría sin ejecutarlo
    """

    print("="*70)
    print("LIMPIEZA DE TABLAS OBSOLETAS - Base de datos test_nps")
    print("="*70)

    if dry_run:
        print("\n[MODO DRY-RUN] - Solo se mostrará qué se haría, sin ejecutar cambios")
    else:
        print("\n[MODO EJECUCION] - Se eliminarán las tablas obsoletas")
        response = input("\n¿Estás seguro? (escribe 'SI' para confirmar): ")
        if response != 'SI':
            print("Operación cancelada")
            return

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()

        print("\n[OK] Conectado a PostgreSQL")

        # Listar todas las tablas existentes
        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name
        """)

        existing_tables = [row[0] for row in cursor.fetchall()]

        print(f"\n[TABLAS ACTUALES EN LA BASE DE DATOS]")
        print("-"*70)

        for table in existing_tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{table}'))
            """)
            size = cursor.fetchone()[0]

            status = ""
            if table in PRODUCTION_TABLES:
                status = "[PRODUCCION - PROTEGIDA]"
            elif table in OBSOLETE_TABLES:
                status = "[OBSOLETA - SE ELIMINARA]"
            else:
                status = "[DESCONOCIDA]"

            print(f"  {table:30} {count:>10,} registros  {size:>10}  {status}")

        # Identificar tablas obsoletas que existen
        tables_to_drop = [t for t in OBSOLETE_TABLES if t in existing_tables]

        if not tables_to_drop:
            print(f"\n[OK] No hay tablas obsoletas para eliminar")
            cursor.close()
            conn.close()
            return

        print(f"\n[TABLAS A ELIMINAR]")
        print("-"*70)

        for table in tables_to_drop:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]

            cursor.execute(f"""
                SELECT pg_size_pretty(pg_total_relation_size('{table}'))
            """)
            size = cursor.fetchone()[0]

            print(f"  {table:30} {count:>10,} registros  {size:>10}")

        if dry_run:
            print(f"\n[DRY-RUN] Comandos que se ejecutarían:")
            for table in tables_to_drop:
                print(f"  DROP TABLE IF EXISTS {table};")

            print(f"\nPara ejecutar realmente, corre:")
            print(f"  python cleanup_database.py --execute")
        else:
            print(f"\n[EJECUTANDO] Eliminando {len(tables_to_drop)} tablas obsoletas...")

            for table in tables_to_drop:
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                    print(f"  [OK] Eliminada: {table}")
                except Exception as e:
                    print(f"  [ERROR] Error eliminando {table}: {e}")

            conn.commit()

            print(f"\n[VERIFICACION FINAL]")
            print("-"*70)

            cursor.execute("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
                ORDER BY table_name
            """)

            remaining_tables = [row[0] for row in cursor.fetchall()]

            print(f"\nTablas restantes en la base de datos:")
            for table in remaining_tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]

                status = "[PRODUCCION]" if table in PRODUCTION_TABLES else ""
                print(f"  * {table:30} {count:>10,} registros  {status}")

            # Calcular espacio liberado
            cursor.execute("""
                SELECT pg_size_pretty(SUM(pg_total_relation_size(schemaname||'.'||tablename)))
                FROM pg_tables
                WHERE schemaname = 'public'
            """)
            total_size = cursor.fetchone()[0]

            print(f"\nTamaño total de la base de datos: {total_size}")
            print(f"\n[OK] Limpieza completada exitosamente")

        cursor.close()
        conn.close()

    except psycopg2.OperationalError as e:
        print(f"\n[ERROR] No se pudo conectar a PostgreSQL")
        print(f"  Verifica que PostgreSQL esté corriendo y las credenciales sean correctas")
        print(f"  Detalle: {e}")
        sys.exit(1)

    except Exception as e:
        print(f"\n[ERROR] {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

def show_help():
    """Muestra ayuda de uso"""
    print("""
LIMPIEZA DE BASE DE DATOS - Eliminar tablas obsoletas

Uso:
  python cleanup_database.py              # Modo dry-run (solo muestra cambios)
  python cleanup_database.py --execute    # Ejecuta la limpieza real
  python cleanup_database.py --help       # Muestra esta ayuda

Tablas que se eliminarán:
  - bm_sample_clean        (tabla de pruebas BM)
  - bv_sample_clean        (tabla de pruebas BV)
  - hello_nps              (tabla demo)
  - test_nps_data          (tabla demo)

Tablas de producción (PROTEGIDAS, NO se eliminan):
  - banco_movil_clean      (1.2M+ registros)
  - banco_virtual_clean    (5K+ registros)

IMPORTANTE: Este script SOLO elimina tablas de desarrollo/testing.
Las tablas de producción están protegidas y nunca se eliminarán.
""")

if __name__ == "__main__":
    import sys

    if '--help' in sys.argv or '-h' in sys.argv:
        show_help()
    elif '--execute' in sys.argv:
        cleanup_database(dry_run=False)
    else:
        cleanup_database(dry_run=True)
