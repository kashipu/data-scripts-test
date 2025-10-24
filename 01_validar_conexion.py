#!/usr/bin/env python3
"""
======================================================================================
SCRIPT: 0_validar_conexion.py
======================================================================================
PROPÓSITO:
    Valida que PostgreSQL esté activo y que la conexión a la base de datos funcione
    correctamente antes de ejecutar el pipeline de procesamiento de datos NPS.

QUÉ HACE:
    1. Verifica que PostgreSQL esté corriendo y accesible
    2. Valida las credenciales de conexión (host, puerto, usuario, contraseña)
    3. Prueba la conexión a la base de datos especificada
    4. Muestra la versión de PostgreSQL instalada
    5. Verifica encoding UTF-8 para caracteres especiales en español

CUÁNDO EJECUTAR:
    - Primera vez que configuras el sistema
    - Después de cambiar credenciales de base de datos
    - Si tienes problemas de conexión con los otros scripts
    - Antes de ejecutar el pipeline completo

RESULTADO ESPERADO:
    ✅ Conexión exitosa a PostgreSQL
    PostgreSQL version: 16.x
    ✅ Base de datos 'nps_analitycs' accesible
    ✅ Encoding UTF-8 configurado correctamente

CONFIGURACIÓN:
    Edita la variable DB_CONFIG abajo con tus credenciales de PostgreSQL
======================================================================================
"""

import psycopg2
from sqlalchemy import create_engine, text
import sys

# ======================================================================================
# CONFIGURACIÓN DE BASE DE DATOS
# ======================================================================================
# IMPORTANTE: Actualiza estos valores con tus credenciales de PostgreSQL
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'  # ⚠️ CAMBIAR ESTE VALOR
}

# ======================================================================================
# FUNCIONES DE VALIDACIÓN
# ======================================================================================

def validar_conexion_psycopg2():
    """
    Valida conexión usando psycopg2 (driver nativo de PostgreSQL)
    """
    print("\n" + "="*80)
    print("VALIDACIÓN 1: Conexión con psycopg2")
    print("="*80)

    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )

        cursor = conn.cursor()

        # Obtener versión de PostgreSQL
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Conexión exitosa a PostgreSQL")
        print(f"📊 Versión: {version.split(',')[0]}")

        # Verificar encoding
        cursor.execute("SHOW client_encoding;")
        encoding = cursor.fetchone()[0]
        print(f"🔤 Encoding: {encoding}")

        cursor.close()
        conn.close()

        return True

    except psycopg2.OperationalError as e:
        print(f"❌ Error de conexión: {e}")
        print("\n💡 Posibles soluciones:")
        print("   1. Verifica que PostgreSQL esté corriendo")
        print("   2. Revisa las credenciales en DB_CONFIG")
        print("   3. Confirma que la base de datos existe")
        return False
    except Exception as e:
        print(f"❌ Error inesperado: {e}")
        return False


def validar_conexion_sqlalchemy():
    """
    Valida conexión usando SQLAlchemy (usado por el pipeline)
    """
    print("\n" + "="*80)
    print("VALIDACIÓN 2: Conexión con SQLAlchemy")
    print("="*80)

    try:
        # Crear cadena de conexión con encoding UTF-8
        connection_string = (
            f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
            f"?client_encoding=utf8"
        )

        engine = create_engine(connection_string)

        # Probar conexión
        with engine.connect() as conn:
            result = conn.execute(text("SELECT current_database(), current_user;"))
            db_name, user_name = result.fetchone()
            print(f"✅ SQLAlchemy conectado exitosamente")
            print(f"📊 Base de datos: {db_name}")
            print(f"👤 Usuario: {user_name}")

        return True

    except Exception as e:
        print(f"❌ Error de conexión SQLAlchemy: {e}")
        return False


def validar_tablas_produccion():
    """
    Verifica si las tablas de producción existen
    """
    print("\n" + "="*80)
    print("VALIDACIÓN 3: Tablas de Producción")
    print("="*80)

    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )

        cursor = conn.cursor()

        # Verificar tablas de producción
        tablas_esperadas = ['banco_movil_clean', 'banco_virtual_clean']

        cursor.execute("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)

        tablas_existentes = [row[0] for row in cursor.fetchall()]

        print(f"📋 Tablas encontradas en la base de datos: {len(tablas_existentes)}")

        for tabla in tablas_esperadas:
            if tabla in tablas_existentes:
                cursor.execute(f"SELECT COUNT(*) FROM {tabla};")
                count = cursor.fetchone()[0]
                print(f"   ✅ {tabla}: {count:,} registros")
            else:
                print(f"   ⚠️  {tabla}: NO EXISTE (será creada al insertar datos)")

        if len(tablas_existentes) > len(tablas_esperadas):
            otras_tablas = [t for t in tablas_existentes if t not in tablas_esperadas]
            print(f"\n📌 Otras tablas encontradas: {', '.join(otras_tablas)}")

        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Error al verificar tablas: {e}")
        return False


def validar_encoding_espanol():
    """
    Prueba inserción y lectura de caracteres especiales del español
    """
    print("\n" + "="*80)
    print("VALIDACIÓN 4: Caracteres Especiales (Español)")
    print("="*80)

    try:
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password']
        )

        cursor = conn.cursor()

        # Crear tabla temporal
        cursor.execute("""
            CREATE TEMP TABLE test_encoding (
                id SERIAL PRIMARY KEY,
                texto TEXT
            );
        """)

        # Insertar texto con caracteres especiales
        texto_prueba = "Recomendación: ñ, á, é, í, ó, ú, ¿, ¡"
        cursor.execute("INSERT INTO test_encoding (texto) VALUES (%s);", (texto_prueba,))

        # Leer texto
        cursor.execute("SELECT texto FROM test_encoding;")
        texto_leido = cursor.fetchone()[0]

        if texto_leido == texto_prueba:
            print(f"✅ Encoding UTF-8 funcionando correctamente")
            print(f"   Texto insertado: {texto_prueba}")
            print(f"   Texto leído: {texto_leido}")
        else:
            print(f"⚠️  Advertencia: Encoding podría tener problemas")
            print(f"   Esperado: {texto_prueba}")
            print(f"   Obtenido: {texto_leido}")

        conn.commit()
        cursor.close()
        conn.close()

        return True

    except Exception as e:
        print(f"❌ Error al validar encoding: {e}")
        return False


# ======================================================================================
# FUNCIÓN PRINCIPAL
# ======================================================================================

def main():
    """
    Ejecuta todas las validaciones en secuencia
    """
    print("\n" + "="*80)
    print("VALIDADOR DE CONEXIÓN - Pipeline NPS")
    print("="*80)
    print(f"\n📍 Intentando conectar a:")
    print(f"   Host: {DB_CONFIG['host']}")
    print(f"   Puerto: {DB_CONFIG['port']}")
    print(f"   Base de datos: {DB_CONFIG['database']}")
    print(f"   Usuario: {DB_CONFIG['user']}")

    # Ejecutar validaciones
    resultados = []

    resultados.append(("Conexión psycopg2", validar_conexion_psycopg2()))
    resultados.append(("Conexión SQLAlchemy", validar_conexion_sqlalchemy()))
    resultados.append(("Tablas de producción", validar_tablas_produccion()))
    resultados.append(("Encoding UTF-8", validar_encoding_espanol()))

    # Resumen final
    print("\n" + "="*80)
    print("RESUMEN DE VALIDACIONES")
    print("="*80)

    exitosas = 0
    for nombre, resultado in resultados:
        icono = "✅" if resultado else "❌"
        print(f"{icono} {nombre}")
        if resultado:
            exitosas += 1

    print("\n" + "="*80)

    if exitosas == len(resultados):
        print("✅ TODAS LAS VALIDACIONES EXITOSAS")
        print("🚀 El sistema está listo para ejecutar el pipeline")
        print("\nPróximos pasos:")
        print("   1. python 1_extractor.py     # Extraer datos de Excel")
        print("   2. python 2_limpieza.py      # Limpiar y transformar datos")
        print("   3. python 3_insercion.py     # Insertar en PostgreSQL")
        print("   4. python 4_visualizacion.py # Generar dashboard")
        return 0
    else:
        print(f"⚠️  VALIDACIONES EXITOSAS: {exitosas}/{len(resultados)}")
        print("❌ Corrige los errores antes de ejecutar el pipeline")
        return 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n⚠️  Validación interrumpida por el usuario")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
