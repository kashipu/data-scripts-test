#!/usr/bin/env python3
"""
Agregar columna para clasificar comentarios por longitud
"""
import sys
import os
sys.path.append('nueva_etl')

from utils import get_engine
from sqlalchemy import text
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    engine = get_engine('nps_analitycs')

    logger.info("Iniciando proceso de agregar columna de clasificación por longitud")

    with engine.connect() as conn:
        # 1. Verificar si la columna ya existe
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'motivos_categorizados'
            AND column_name = 'texto_tipo'
        """))

        if result.fetchone():
            logger.info("La columna 'texto_tipo' ya existe")
            # Preguntar si quiere recalcular
            response = input("¿Quieres recalcular los valores? (yes/no): ")
            if response.lower() != "yes":
                logger.info("Operación cancelada")
                return
        else:
            # 2. Agregar columna
            logger.info("Agregando columna 'texto_tipo'...")
            conn.execute(text("BEGIN"))
            try:
                conn.execute(text("""
                    ALTER TABLE motivos_categorizados
                    ADD COLUMN texto_tipo VARCHAR(20)
                """))
                conn.execute(text("COMMIT"))
                logger.info("✓ Columna agregada exitosamente")
            except Exception as e:
                conn.execute(text("ROLLBACK"))
                logger.error(f"Error agregando columna: {e}")
                return

        # 3. Calcular y actualizar valores
        logger.info("Actualizando valores de texto_tipo...")

        # Clasificación:
        # - 'muy_corto': < 10 caracteres
        # - 'corto': 10-29 caracteres
        # - 'mediano': 30-79 caracteres
        # - 'largo': 80+ caracteres

        conn.execute(text("BEGIN"))
        try:
            # Muy cortos
            result = conn.execute(text("""
                UPDATE motivos_categorizados
                SET texto_tipo = 'muy_corto'
                WHERE LENGTH(texto_motivo) < 10
            """))
            logger.info(f"  Muy cortos (< 10): {result.rowcount:,} registros")

            # Cortos
            result = conn.execute(text("""
                UPDATE motivos_categorizados
                SET texto_tipo = 'corto'
                WHERE LENGTH(texto_motivo) >= 10
                AND LENGTH(texto_motivo) < 30
            """))
            logger.info(f"  Cortos (10-29): {result.rowcount:,} registros")

            # Medianos
            result = conn.execute(text("""
                UPDATE motivos_categorizados
                SET texto_tipo = 'mediano'
                WHERE LENGTH(texto_motivo) >= 30
                AND LENGTH(texto_motivo) < 80
            """))
            logger.info(f"  Medianos (30-79): {result.rowcount:,} registros")

            # Largos
            result = conn.execute(text("""
                UPDATE motivos_categorizados
                SET texto_tipo = 'largo'
                WHERE LENGTH(texto_motivo) >= 80
            """))
            logger.info(f"  Largos (80+): {result.rowcount:,} registros")

            conn.execute(text("COMMIT"))
            logger.info("✓ Valores actualizados exitosamente")

        except Exception as e:
            conn.execute(text("ROLLBACK"))
            logger.error(f"Error actualizando valores: {e}")
            return

        # 4. Crear índice para optimizar consultas
        logger.info("Creando índice en texto_tipo...")
        conn.execute(text("BEGIN"))
        try:
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_motivos_cat_texto_tipo
                ON motivos_categorizados(texto_tipo)
            """))
            conn.execute(text("COMMIT"))
            logger.info("✓ Índice creado exitosamente")
        except Exception as e:
            conn.execute(text("ROLLBACK"))
            logger.error(f"Error creando índice: {e}")

        # 5. Mostrar estadísticas
        logger.info("\nEstadísticas de distribución:")
        result = conn.execute(text("""
            SELECT
                texto_tipo,
                COUNT(*) as cantidad,
                ROUND(AVG(LENGTH(texto_motivo)), 1) as longitud_promedio,
                MIN(LENGTH(texto_motivo)) as min,
                MAX(LENGTH(texto_motivo)) as max
            FROM motivos_categorizados
            WHERE texto_tipo IS NOT NULL
            GROUP BY texto_tipo
            ORDER BY
                CASE texto_tipo
                    WHEN 'muy_corto' THEN 1
                    WHEN 'corto' THEN 2
                    WHEN 'mediano' THEN 3
                    WHEN 'largo' THEN 4
                END
        """))

        print("\n" + "=" * 80)
        print("DISTRIBUCIÓN POR TIPO DE TEXTO")
        print("=" * 80)
        print(f"{'Tipo':<15} {'Cantidad':>12} {'Promedio':>12} {'Min':>8} {'Max':>8}")
        print("-" * 80)

        total = 0
        for row in result:
            tipo, cantidad, promedio, min_len, max_len = row
            total += cantidad
            print(f"{tipo:<15} {cantidad:>12,} {promedio:>12.1f} {min_len:>8} {max_len:>8}")

        print("-" * 80)
        print(f"{'TOTAL':<15} {total:>12,}")
        print("=" * 80)

        # 6. Estadísticas por categoría y tipo de texto
        print("\n" + "=" * 80)
        print("TOP 10 CATEGORÍAS POR TIPO DE TEXTO")
        print("=" * 80)

        for tipo in ['muy_corto', 'corto', 'mediano', 'largo']:
            print(f"\n{tipo.upper().replace('_', ' ')}:")
            result = conn.execute(text(f"""
                SELECT categoria, COUNT(*) as cantidad
                FROM motivos_categorizados
                WHERE texto_tipo = :tipo
                AND categoria IS NOT NULL
                GROUP BY categoria
                ORDER BY cantidad DESC
                LIMIT 10
            """), {"tipo": tipo})

            for cat, cant in result:
                print(f"  {cat:<40} -> {cant:>7,}")

    logger.info("\n✓ Proceso completado exitosamente")

if __name__ == "__main__":
    main()
