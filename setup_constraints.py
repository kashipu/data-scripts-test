#!/usr/bin/env python3
"""
Script para aplicar constraints UNIQUE en la base de datos (UNA SOLA VEZ)
Alternativa simple al comando psql
"""

import psycopg2
from psycopg2 import sql
import logging

# Configuración de base de datos (CAMBIA LA CONTRASEÑA)
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'test_nps',
    'user': 'postgres',
    'password': 'postgres'  # CAMBIA ESTO
}

def setup_constraints():
    """Aplica constraints UNIQUE para prevenir duplicados"""

    print("="*60)
    print("CONFIGURANDO PROTECCIÓN ANTI-DUPLICADOS")
    print("="*60)
    print("\nEste script se ejecuta UNA SOLA VEZ")
    print("Aplicará constraints UNIQUE en las tablas para prevenir duplicados\n")

    try:
        # Conecta a PostgreSQL
        print("→ Conectando a PostgreSQL...")
        conn = psycopg2.connect(**DB_CONFIG)
        cursor = conn.cursor()
        print("✓ Conexión exitosa\n")

        # Paso 1: Eliminar duplicados existentes en Banco Móvil
        print("→ Limpiando duplicados existentes en banco_movil_clean...")
        cursor.execute("""
            DELETE FROM banco_movil_clean
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY record_id, source_file
                               ORDER BY id ASC
                           ) AS row_num
                    FROM banco_movil_clean
                ) t
                WHERE row_num > 1
            )
        """)
        bm_deleted = cursor.rowcount
        print(f"✓ Eliminados {bm_deleted} registros duplicados en BM\n")

        # Paso 2: Eliminar duplicados existentes en Banco Virtual
        print("→ Limpiando duplicados existentes en banco_virtual_clean...")
        cursor.execute("""
            DELETE FROM banco_virtual_clean
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY date_submitted, nps_score_bv, source_file
                               ORDER BY id ASC
                           ) AS row_num
                    FROM banco_virtual_clean
                ) t
                WHERE row_num > 1
            )
        """)
        bv_deleted = cursor.rowcount
        print(f"✓ Eliminados {bv_deleted} registros duplicados en BV\n")

        conn.commit()

        # Paso 3: Agregar constraint UNIQUE en Banco Móvil
        print("→ Agregando constraint UNIQUE en banco_movil_clean...")
        try:
            cursor.execute("""
                ALTER TABLE banco_movil_clean
                ADD CONSTRAINT unique_bm_record
                UNIQUE (record_id, source_file)
            """)
            print("✓ Constraint 'unique_bm_record' creado\n")
        except psycopg2.errors.DuplicateObject:
            print("⊘ Constraint 'unique_bm_record' ya existe (omitiendo)\n")

        # Paso 4: Agregar constraint UNIQUE en Banco Virtual
        print("→ Agregando constraint UNIQUE en banco_virtual_clean...")
        try:
            cursor.execute("""
                ALTER TABLE banco_virtual_clean
                ADD CONSTRAINT unique_bv_record
                UNIQUE (date_submitted, nps_score_bv, source_file)
            """)
            print("✓ Constraint 'unique_bv_record' creado\n")
        except psycopg2.errors.DuplicateObject:
            print("⊘ Constraint 'unique_bv_record' ya existe (omitiendo)\n")

        # Paso 5: Crear índices en source_file
        print("→ Creando índices en source_file...")
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bm_source_file
            ON banco_movil_clean(source_file)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_bv_source_file
            ON banco_virtual_clean(source_file)
        """)
        print("✓ Índices creados\n")

        conn.commit()

        # Verificación final
        print("="*60)
        print("VERIFICACIÓN FINAL")
        print("="*60)

        cursor.execute("SELECT COUNT(*) FROM banco_movil_clean")
        bm_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM banco_virtual_clean")
        bv_count = cursor.fetchone()[0]

        print(f"\nBanco Móvil: {bm_count} registros")
        print(f"Banco Virtual: {bv_count} registros")

        print("\n" + "="*60)
        print("✅ PROTECCIÓN ANTI-DUPLICADOS ACTIVADA")
        print("="*60)
        print("\nAhora puedes ejecutar insertar_muestras.py sin riesgo de duplicados")
        print("Este script NO necesita ejecutarse nuevamente\n")

        cursor.close()
        conn.close()

    except psycopg2.OperationalError as e:
        print(f"\n✗ ERROR: No se pudo conectar a PostgreSQL")
        print(f"  Verifica que:")
        print(f"  1. PostgreSQL esté corriendo")
        print(f"  2. La contraseña en DB_CONFIG sea correcta")
        print(f"  3. La base de datos 'test_nps' exista")
        print(f"\n  Detalle: {e}\n")

    except Exception as e:
        print(f"\n✗ ERROR: {e}\n")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    setup_constraints()
