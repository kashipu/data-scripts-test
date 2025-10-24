#!/usr/bin/env python3
"""
Creación de Tabla de Categorización de Motivos
===============================================

Crea la tabla motivos_categorizados que almacena las categorizaciones
de motivos NPS/CSAT relacionándose con las tablas originales.

Uso:
    python 10_crear_tabla_categorias.py --db-name nps_analitycs
"""

import argparse
import logging
import os
import sys
from datetime import datetime

from sqlalchemy import create_engine, text

# ============================================================================
# FUNCIONES HELPER BÁSICAS
# ============================================================================

def get_engine(db_name='nps_analitycs'):
    """Crea conexión a PostgreSQL"""
    conn_string = f"postgresql://postgres:postgres@localhost:5432/{db_name}?client_encoding=utf8"
    return create_engine(conn_string)

# ============================================================================
# CONFIGURACIÓN
# ============================================================================

LOG_FILE = "crear_tabla_categorias.log"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def crear_tabla_categorias(engine):
    """
    Crea la tabla motivos_categorizados con sus índices.
    """
    logger.info("Creando tabla motivos_categorizados...")

    with engine.connect() as conn:
        conn.execute(text("BEGIN"))
        try:
            # Crear tabla
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS motivos_categorizados (
                    id SERIAL PRIMARY KEY,

                    -- Relación con tabla origen
                    tabla_origen VARCHAR(50) NOT NULL,
                    registro_id INTEGER NOT NULL,
                    campo_motivo VARCHAR(50) NOT NULL,

                    -- Datos del motivo
                    texto_motivo TEXT,
                    texto_tipo VARCHAR(20),  -- Clasificación por longitud: muy_corto, corto, mediano, largo
                    canal VARCHAR(10),
                    metrica VARCHAR(10),
                    score_metrica INTEGER,

                    -- Categorización
                    categoria VARCHAR(100),
                    confidence NUMERIC(5, 4),
                    metadata_categoria TEXT,
                    es_ruido BOOLEAN DEFAULT FALSE,
                    razon_ruido VARCHAR(50),

                    -- Timestamp
                    categorizado_en TIMESTAMP DEFAULT NOW(),

                    -- Constraint único: una categorización por registro+campo
                    CONSTRAINT unique_registro_campo UNIQUE(tabla_origen, registro_id, campo_motivo)
                )
            """))
            logger.info("✓ Tabla motivos_categorizados creada")

            # Crear índices para performance
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_motivos_cat_tabla_origen
                ON motivos_categorizados(tabla_origen)
            """))
            logger.info("✓ Índice idx_motivos_cat_tabla_origen creado")

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_motivos_cat_registro_id
                ON motivos_categorizados(registro_id)
            """))
            logger.info("✓ Índice idx_motivos_cat_registro_id creado")

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_motivos_cat_categoria
                ON motivos_categorizados(categoria)
            """))
            logger.info("✓ Índice idx_motivos_cat_categoria creado")

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_motivos_cat_es_ruido
                ON motivos_categorizados(es_ruido)
            """))
            logger.info("✓ Índice idx_motivos_cat_es_ruido creado")

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_motivos_cat_canal_metrica
                ON motivos_categorizados(canal, metrica)
            """))
            logger.info("✓ Índice idx_motivos_cat_canal_metrica creado")

            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_motivos_cat_texto_tipo
                ON motivos_categorizados(texto_tipo)
            """))
            logger.info("✓ Índice idx_motivos_cat_texto_tipo creado")

            conn.execute(text("COMMIT"))
            logger.info("✓ Tabla e índices creados exitosamente")

        except Exception as e:
            conn.execute(text("ROLLBACK"))
            logger.error(f"Error creando tabla: {e}")
            raise


def verificar_estructura(engine):
    """
    Verifica que la tabla se haya creado correctamente.
    """
    logger.info("Verificando estructura de la tabla...")

    with engine.connect() as conn:
        # Verificar tabla
        result = conn.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_name = 'motivos_categorizados'
        """)).fetchone()

        if result:
            logger.info("✓ Tabla motivos_categorizados existe")
        else:
            logger.error("✗ Tabla motivos_categorizados NO existe")
            return False

        # Verificar columnas
        result = conn.execute(text("""
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'motivos_categorizados'
            ORDER BY ordinal_position
        """)).fetchall()

        logger.info(f"✓ Columnas encontradas: {len(result)}")
        for col_name, col_type in result:
            logger.info(f"  - {col_name}: {col_type}")

        # Verificar índices
        result = conn.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE tablename = 'motivos_categorizados'
        """)).fetchall()

        logger.info(f"✓ Índices encontrados: {len(result)}")
        for idx in result:
            logger.info(f"  - {idx[0]}")

    return True


def main():
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    parser = argparse.ArgumentParser(
        description="Creación de tabla motivos_categorizados"
    )

    parser.add_argument(
        "--db-name",
        default="nps_analitycs",
        help="Nombre de la base de datos (default: nps_analitycs)"
    )

    args = parser.parse_args()

    # Banner
    print("=" * 80)
    print("CREACIÓN DE TABLA MOTIVOS_CATEGORIZADOS")
    print("=" * 80)
    print(f"Base de datos: {args.db_name}")
    print("=" * 80 + "\n")

    # Conectar
    engine = get_engine(args.db_name)

    # Crear tabla
    crear_tabla_categorias(engine)

    # Verificar
    if verificar_estructura(engine):
        print("\n" + "=" * 80)
        print("✓ TABLA CREADA EXITOSAMENTE")
        print("=" * 80)
        print("\nPróximo paso:")
        print("  python 8_limpieza_categoria.py --mode process --batch-size 5000")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("✗ ERROR EN LA CREACIÓN")
        print("=" * 80)
        sys.exit(1)


if __name__ == "__main__":
    main()
