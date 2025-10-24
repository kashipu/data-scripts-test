#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
======================================================================================
SCRIPT: 00_inicializar_bd.py
======================================================================================
PROPÓSITO:
    Inicializa la base de datos PostgreSQL con toda la estructura necesaria para
    el análisis de encuestas NPS/CSAT.

QUÉ HACE:
    1. Verifica conexión a PostgreSQL
    2. Crea la base de datos 'nps_analitycs' si no existe
    3. Ejecuta scripts SQL en el orden correcto:
       - 02_create_new_structure.sql: Tabla principal particionada
       - 03_create_views.sql: Vistas materializadas
    4. Verifica que las tablas se crearon correctamente
    5. Genera reporte de inicialización

CUÁNDO EJECUTAR:
    - Primera vez que configuras el sistema
    - Después de resetear la base de datos
    - Si encuentras error "no existe la relación respuestas_nps_csat"

SIGUIENTE PASO:
    Ejecutar: python 04_insercion.py
======================================================================================
"""

import psycopg2
from psycopg2 import sql
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from pathlib import Path
import sys

# ======================================================================================
# CONFIGURACIÓN
# ======================================================================================

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

LOG_FILE = "inicializacion_bd.log"

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

# ======================================================================================
# FUNCIONES
# ======================================================================================

def check_postgres_connection():
    """Verifica que PostgreSQL esté corriendo"""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database='postgres'  # Conectar a DB por defecto
        )
        conn.close()
        logger.info("Conexion a PostgreSQL exitosa")
        return True
    except Exception as e:
        logger.error(f"Error conectando a PostgreSQL: {str(e)}")
        logger.error("Verifica que PostgreSQL este corriendo y las credenciales sean correctas")
        return False

def create_database_if_not_exists():
    """Crea la base de datos si no existe"""
    try:
        # Conectar a postgres DB para crear la nueva DB
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Verificar si la DB existe
        cursor.execute(
            "SELECT 1 FROM pg_database WHERE datname = %s",
            (DB_CONFIG['database'],)
        )
        exists = cursor.fetchone()

        if exists:
            logger.info(f"Base de datos '{DB_CONFIG['database']}' ya existe")
        else:
            # Crear la base de datos
            cursor.execute(
                sql.SQL("CREATE DATABASE {}").format(
                    sql.Identifier(DB_CONFIG['database'])
                )
            )
            logger.info(f"Base de datos '{DB_CONFIG['database']}' creada exitosamente")

        cursor.close()
        conn.close()
        return True

    except Exception as e:
        logger.error(f"Error creando base de datos: {str(e)}")
        return False

def execute_sql_file(filepath):
    """Ejecuta un archivo SQL completo"""
    try:
        logger.info(f"\nEjecutando: {filepath.name}")

        # Leer el archivo SQL
        with open(filepath, 'r', encoding='utf-8') as f:
            sql_content = f.read()

        # Conectar a la BD
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Ejecutar el SQL (dividir por comandos si es necesario)
        # Remover comandos \c y \echo que son específicos de psql
        sql_lines = []
        for line in sql_content.split('\n'):
            line = line.strip()
            if line.startswith('\\c') or line.startswith('\\echo'):
                continue
            sql_lines.append(line)

        clean_sql = '\n'.join(sql_lines)

        # Ejecutar el SQL
        cursor.execute(clean_sql)

        cursor.close()
        conn.close()

        logger.info(f"  Completado exitosamente")
        return True

    except Exception as e:
        error_msg = str(e)
        logger.error(f"  Error ejecutando {filepath.name}: {error_msg}")

        # Dar información adicional si es un error de objeto ya existente
        if 'ya existe' in error_msg or 'already exists' in error_msg.lower():
            logger.error("  Causa: Intentando crear un objeto que ya existe")
            logger.error("  Solución: Ejecuta el script nuevamente y selecciona 's' para eliminar la estructura anterior")

        return False

def verify_tables_created():
    """Verifica que las tablas principales fueron creadas"""
    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        cursor = conn.cursor()

        # Verificar tabla principal
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'respuestas_nps_csat'
        """)
        table_exists = cursor.fetchone()[0] > 0

        # Contar particiones
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name LIKE 'respuestas_nps_csat_%'
        """)
        partitions_count = cursor.fetchone()[0]

        # Contar vistas materializadas
        cursor.execute("""
            SELECT COUNT(*)
            FROM pg_matviews
            WHERE schemaname = 'public'
        """)
        views_count = cursor.fetchone()[0]

        # Verificar catálogo de categorías
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'catalogo_categorias'
        """)
        catalog_exists = cursor.fetchone()[0] > 0

        cursor.close()
        conn.close()

        logger.info("\n" + "=" * 70)
        logger.info("VERIFICACION DE ESTRUCTURA")
        logger.info("=" * 70)
        logger.info(f"Tabla principal 'respuestas_nps_csat': {'OK' if table_exists else 'FALTA'}")
        logger.info(f"Particiones creadas: {partitions_count}")
        logger.info(f"Vistas materializadas: {views_count}")
        logger.info(f"Catalogo de categorias: {'OK' if catalog_exists else 'FALTA'}")
        logger.info("=" * 70)

        return table_exists and partitions_count > 0 and catalog_exists

    except Exception as e:
        logger.error(f"Error verificando tablas: {str(e)}")
        return False

def drop_existing_structure():
    """Elimina la estructura existente (CUIDADO: borra todos los datos)"""
    try:
        logger.warning("\nELIMINANDO ESTRUCTURA EXISTENTE...")
        logger.warning("Esto borrara todos los datos en la base de datos!")

        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()

        # Eliminar vistas materializadas
        cursor.execute("""
            SELECT matviewname FROM pg_matviews WHERE schemaname = 'public'
        """)
        views = cursor.fetchall()
        for view in views:
            cursor.execute(f"DROP MATERIALIZED VIEW IF EXISTS {view[0]} CASCADE")
            logger.info(f"  Vista eliminada: {view[0]}")

        # Eliminar tablas
        cursor.execute("DROP TABLE IF EXISTS respuestas_nps_csat CASCADE")
        cursor.execute("DROP TABLE IF EXISTS catalogo_categorias CASCADE")
        logger.info("  Tablas principales eliminadas")

        cursor.close()
        conn.close()

        logger.info("Estructura anterior eliminada exitosamente")
        return True

    except Exception as e:
        logger.error(f"Error eliminando estructura: {str(e)}")
        return False

def main():
    """Función principal"""
    print("=" * 70)
    print("INICIALIZACION DE BASE DE DATOS - NPS/CSAT ANALYTICS")
    print("=" * 70)

    # Verificar directorio SQL
    sql_dir = Path('sql')
    if not sql_dir.exists():
        logger.error("Directorio 'sql/' no encontrado")
        logger.error("Asegurate de ejecutar este script desde el directorio raiz del proyecto")
        sys.exit(1)

    # Paso 1: Verificar conexión a PostgreSQL
    print("\n[1/5] Verificando conexion a PostgreSQL...")
    if not check_postgres_connection():
        sys.exit(1)

    # Paso 2: Crear base de datos
    print("\n[2/5] Creando base de datos...")
    if not create_database_if_not_exists():
        sys.exit(1)

    # Paso 3: Verificar estructura existente y preguntar si recrear
    print("\n[3/5] Verificando estructura existente...")
    estructura_existe = False
    estructura_completa = False

    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database']
        )
        cursor = conn.cursor()

        # Verificar tabla principal
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'respuestas_nps_csat'
        """)
        tabla_principal_existe = cursor.fetchone()[0] > 0

        # Verificar catálogo
        cursor.execute("""
            SELECT COUNT(*)
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_name = 'catalogo_categorias'
        """)
        catalogo_existe = cursor.fetchone()[0] > 0

        # Verificar vistas materializadas
        cursor.execute("""
            SELECT COUNT(*)
            FROM pg_matviews
            WHERE schemaname = 'public'
        """)
        vistas_count = cursor.fetchone()[0]

        cursor.close()
        conn.close()

        estructura_existe = tabla_principal_existe or catalogo_existe
        estructura_completa = tabla_principal_existe and catalogo_existe and vistas_count >= 5

        if estructura_existe:
            if estructura_completa:
                logger.info("Estructura de base de datos detectada (COMPLETA)")
                print("\n✓ Base de datos ya tiene estructura completa:")
                print(f"  - Tabla principal: {'✓' if tabla_principal_existe else '✗'}")
                print(f"  - Catálogo de categorías: {'✓' if catalogo_existe else '✗'}")
                print(f"  - Vistas materializadas: {vistas_count}/5")
            else:
                logger.warning("Estructura de base de datos detectada (INCOMPLETA)")
                print("\n⚠️  Base de datos tiene estructura INCOMPLETA:")
                print(f"  - Tabla principal: {'✓' if tabla_principal_existe else '✗'}")
                print(f"  - Catálogo de categorías: {'✓' if catalogo_existe else '✗'}")
                print(f"  - Vistas materializadas: {vistas_count}/5")

            print("\n¡ADVERTENCIA! Se detectó estructura existente en la base de datos.")
            print("Opciones:")
            print("  [s] - ELIMINAR Y RECREAR (borrará todos los datos)")
            print("  [n] - CANCELAR (mantener estructura actual)")
            response = input("\n¿Qué deseas hacer? (s/n): ").strip().lower()

            if response == 's':
                print("\n⚠️  CONFIRMACIÓN FINAL:")
                confirm = input("¿Estás SEGURO de eliminar todos los datos? Escribe 'SI' para confirmar: ").strip()
                if confirm == 'SI':
                    if not drop_existing_structure():
                        logger.error("Error al eliminar estructura existente")
                        sys.exit(1)
                    print("\n✓ Estructura anterior eliminada. Continuando con la creación...")
                else:
                    logger.info("Operación cancelada por el usuario")
                    print("\n✗ Operación cancelada")
                    sys.exit(0)
            else:
                if estructura_completa:
                    logger.info("Manteniendo estructura existente")
                    print("\n✓ Base de datos ya está inicializada")
                    print("\nPuedes proceder con:")
                    print("  python 04_insercion.py")
                    return
                else:
                    logger.error("La estructura está incompleta y no se puede usar")
                    print("\n✗ La estructura está incompleta. Debes recrearla.")
                    sys.exit(1)
    except Exception as e:
        # Si hay error conectando, asumimos que no hay estructura
        logger.debug(f"No se pudo verificar estructura (probablemente no existe): {str(e)}")
        print("  No se detectó estructura previa")

    # Paso 4: Ejecutar scripts SQL
    print("\n[4/5] Creando estructura de base de datos...")

    scripts = [
        sql_dir / '02_create_new_structure.sql',
        sql_dir / '03_create_views.sql'
    ]

    for script in scripts:
        if not script.exists():
            logger.error(f"Script no encontrado: {script}")
            logger.error(f"Ruta esperada: {script.absolute()}")
            sys.exit(1)

        # Ejecutar script - si falla, detener inmediatamente
        if not execute_sql_file(script):
            logger.error(f"\n✗ Error ejecutando {script.name}")
            logger.error("La creación de la estructura se detuvo")
            logger.error("\nPosibles causas:")
            logger.error("  1. La estructura anterior no se eliminó completamente")
            logger.error("  2. Hay un error en el script SQL")
            logger.error("\nSolución:")
            logger.error("  Ejecuta nuevamente este script y selecciona 's' para recrear la estructura")
            sys.exit(1)

    logger.info("\n✓ Todos los scripts SQL ejecutados exitosamente")

    # Paso 5: Verificar
    print("\n[5/5] Verificando estructura creada...")
    if not verify_tables_created():
        logger.error("\nLa estructura no se creo correctamente")
        sys.exit(1)

    # Preguntar si desea insertar datos de prueba
    sample_data_script = sql_dir / '04_insert_sample_data.sql'
    if sample_data_script.exists():
        print("\n" + "-" * 70)
        response = input("¿Deseas insertar datos de prueba para validar la estructura? (s/n): ").strip().lower()
        if response == 's':
            if execute_sql_file(sample_data_script):
                logger.info("✓ Datos de prueba insertados exitosamente")
                print("\n✓ Se insertaron 18 registros de prueba")
                print("  Puedes eliminarlos después con:")
                print("  DELETE FROM respuestas_nps_csat WHERE archivo_origen = 'DATOS_PRUEBA';")
            else:
                logger.warning("No se pudieron insertar los datos de prueba")
        print("-" * 70)

    # Resumen final
    print("\n" + "=" * 70)
    print("BASE DE DATOS INICIALIZADA EXITOSAMENTE")
    print("=" * 70)
    print("\nEstructura creada:")
    print("  - Tabla principal: respuestas_nps_csat (particionada por mes)")
    print("  - Catalogo de categorias")
    print("  - 5 vistas materializadas para reportes")
    print("  - Indices optimizados")
    print("\nSiguiente paso:")
    print("  python 04_insercion.py")
    print("=" * 70)

    logger.info(f"\nLog guardado en: {LOG_FILE}")

if __name__ == "__main__":
    main()
