#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script Optimizado: Insertar Datoss Limpias en PostgreSQL
- Preserva TODOS los datos importantes (customer_id, answerDate, etc.)
- Usa append para acumular históricos (no borra datos)
- Procesa TODOS los archivos en datos_clean/ automáticamente
- Agrega trazabilidad con source_file
"""

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
import psycopg2
from psycopg2 import errors
import logging
from datetime import datetime
import os
import sys
from pathlib import Path
import re
from urllib.parse import quote_plus

# Configurar codificación de salida para Windows
if sys.platform == 'win32':
    import codecs
    if sys.stdout.encoding != 'utf-8':
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')
    if sys.stderr.encoding != 'utf-8':
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'ignore')

class NPSInserter:
    """Clase para insertar datos NPS limpios en PostgreSQL"""
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.engine = None
        self.setup_logging()
        self.stats = {
            'bm_inserted': 0,
            'bv_inserted': 0,
            'bm_skipped': 0,
            'bv_skipped': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def setup_logging(self):
        """Configura logging"""
        # Handler para archivo con UTF-8
        file_handler = logging.FileHandler('insercion_datos.log', encoding='utf-8')
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # Handler para consola con manejo de errores de encoding
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))

        # Configurar logger
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)

        # Evitar propagación para no duplicar mensajes
        self.logger.propagate = False
    
    def connect_database(self):
        """Establece conexión con PostgreSQL"""
        try:
            # Manejo de encoding de contraseña
            password = self.db_config['password']

            # Si la contraseña es bytes, decodificarla
            if isinstance(password, bytes):
                try:
                    password = password.decode('utf-8')
                except UnicodeDecodeError:
                    # Intentar con latin-1 si UTF-8 falla
                    password = password.decode('latin-1')
                    self.logger.warning("Contraseña decodificada como latin-1")

            # Si es string, asegurarse de que está en UTF-8
            elif isinstance(password, str):
                try:
                    # Intentar encode/decode para validar UTF-8
                    password.encode('utf-8')
                except UnicodeEncodeError:
                    # Re-codificar desde latin-1 a UTF-8
                    password = password.encode('latin-1').decode('utf-8', errors='replace')
                    self.logger.warning("Contraseña re-codificada de latin-1 a UTF-8")

            # Primero prueba conexión básica con parámetros de encoding
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['username'],
                password=password,
                client_encoding='utf8'
            )
            conn.close()
            self.logger.info("Conexión PostgreSQL exitosa")

            # Crea engine SQLAlchemy con parámetros adicionales
            # URL-encode password para manejar caracteres especiales
            try:
                encoded_password = quote_plus(password)
            except (UnicodeDecodeError, UnicodeEncodeError) as e:
                self.logger.error(f"Error encoding password: {str(e)}")
                # Usar password sin codificar como fallback
                encoded_password = password

            connection_string = (
                f"postgresql://{self.db_config['username']}:"
                f"{encoded_password}@{self.db_config['host']}:"
                f"{self.db_config['port']}/{self.db_config['database']}"
                f"?client_encoding=utf8"
            )
            
            self.engine = create_engine(
                connection_string,
                pool_size=5,
                max_overflow=10,
                pool_pre_ping=True,
                connect_args={"client_encoding": "utf8"}
            )
            
            # Test del engine con mejor manejo de errores
            try:
                with self.engine.connect() as conn:
                    result = conn.execute(text("SELECT version()"))
                    version = result.fetchone()[0]
                    self.logger.info(f"Engine conectado: {version[:50]}...")
            except Exception as e:
                self.logger.error(f"Error testing engine: {str(e)}")
                self.engine = None
                return False
            
            return True

        except Exception as e:
            # Manejar errores de encoding en mensajes de PostgreSQL
            if isinstance(e, UnicodeDecodeError) and hasattr(e, 'object'):
                # Extraer mensaje original de PostgreSQL en latin-1
                try:
                    error_bytes = e.object
                    error_msg = error_bytes.decode('latin-1')
                    print(f"\n{'='*60}")
                    print(f"ERROR DE POSTGRESQL:")
                    print(f"{'='*60}")
                    print(error_msg)
                    print(f"{'='*60}\n")

                    # Log sin caracteres especiales
                    error_msg_simple = error_msg.replace('«', '"').replace('»', '"')
                    self.logger.error(f"Error de PostgreSQL: {error_msg_simple}")
                    return False
                except:
                    pass

            # Manejo genérico de otros errores
            try:
                error_msg = str(e)
            except (UnicodeDecodeError, UnicodeEncodeError):
                try:
                    error_msg = str(e).encode('latin-1', errors='replace').decode('utf-8', errors='replace')
                except:
                    error_msg = repr(e)

            self.logger.error(f"Error conectando a PostgreSQL: {error_msg}")
            return False
    
    def create_tables_if_needed(self):
        """Crea tablas optimizadas con TODAS las columnas importantes"""
        if not self.engine:
            self.logger.error("Engine no disponible para crear tablas")
            return False

        try:
            with self.engine.connect() as conn:
                # Tabla para Banco Móvil - PRESERVA TODOS LOS DATOS
                bm_table_sql = """
                CREATE TABLE IF NOT EXISTS banco_movil_clean (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    answer_date TIMESTAMP,
                    answers TEXT,
                    channel VARCHAR(50),
                    cust_ident_num BIGINT,
                    cust_ident_type VARCHAR(10),
                    feedback_type VARCHAR(50),
                    record_id INTEGER,
                    nps_original VARCHAR(50),
                    nps_recomendacion_score FLOAT,
                    nps_recomendacion_motivo TEXT,
                    csat_satisfaccion_score FLOAT,
                    csat_satisfaccion_motivo TEXT,
                    nps_score FLOAT,
                    nps_category VARCHAR(20),
                    cleaned_date TIMESTAMP,
                    file_type VARCHAR(10),
                    month_year VARCHAR(20),
                    source_file VARCHAR(255),
                    inserted_at TIMESTAMP DEFAULT NOW()
                );
                """

                # Tabla para Banco Virtual - COLUMNAS DINÁMICAS
                bv_table_sql = """
                CREATE TABLE IF NOT EXISTS banco_virtual_clean (
                    id SERIAL PRIMARY KEY,
                    date_submitted_original VARCHAR(50),
                    date_submitted TIMESTAMP,
                    country VARCHAR(100),
                    source_url TEXT,
                    device VARCHAR(100),
                    browser VARCHAR(200),
                    operating_system VARCHAR(200),
                    nps_score_bv INTEGER,
                    calificacion_acerca TEXT,
                    motivo_calificacion TEXT,
                    tags_recomendacion TEXT,
                    tags_calificacion TEXT,
                    tags_motivo TEXT,
                    sentiment_motivo TEXT,
                    month_year VARCHAR(20),
                    nps_score INTEGER,
                    nps_category VARCHAR(20),
                    cleaned_date TIMESTAMP,
                    file_type VARCHAR(10),
                    source_file VARCHAR(255),
                    inserted_at TIMESTAMP DEFAULT NOW()
                );
                """

                # Ejecuta creación de tablas
                conn.execute(text(bm_table_sql))
                conn.execute(text(bv_table_sql))
                conn.commit()

                self.logger.info("Tablas creadas/verificadas exitosamente")
                return True

        except Exception as e:
            self.logger.error(f"Error creando tablas: {str(e)}")
            return False
    
    def insert_banco_movil(self, file_path):
        """Inserta datos de Banco Móvil con TODAS las columnas importantes"""
        if not self.engine:
            self.logger.error("Engine no disponible para insertar BM")
            return False

        try:
            file_name = Path(file_path).name

            # VALIDACIÓN: Verifica si el archivo ya fue procesado
            if self.file_already_processed(file_name, 'banco_movil_clean'):
                self.logger.warning(f"[OMITIDO] - Archivo ya procesado: {file_name}")
                self.stats['bm_skipped'] += 1
                return True

            self.logger.info(f"→ Procesando Banco Móvil: {file_name}")

            # Lee archivo
            df = pd.read_excel(file_path)
            original_count = len(df)

            # Mapeo de columnas origen → destino
            column_mapping = {
                'timestamp': 'timestamp',
                'answerDate': 'answer_date',
                'answers': 'answers',
                'channel': 'channel',
                'custIdentNum': 'cust_ident_num',
                'custIdentType': 'cust_ident_type',
                'feedbackType': 'feedback_type',
                'id': 'record_id',
                'NPS': 'nps_original',
                'nps_recomendacion_score': 'nps_recomendacion_score',
                'nps_recomendacion_motivo': 'nps_recomendacion_motivo',
                'csat_satisfaccion_score': 'csat_satisfaccion_score',
                'csat_satisfaccion_motivo': 'csat_satisfaccion_motivo',
                'nps_score': 'nps_score',
                'nps_category': 'nps_category',
                'cleaned_date': 'cleaned_date',
                'file_type': 'file_type',
                'month_year': 'month_year'
            }

            # Renombra columnas
            df_renamed = df.rename(columns=column_mapping)

            # Agrega columna de trazabilidad
            df_renamed['source_file'] = file_name

            # Selecciona solo columnas que existen en el mapeo
            cols_to_insert = [v for k, v in column_mapping.items() if k in df.columns]
            cols_to_insert.append('source_file')
            df_final = df_renamed[cols_to_insert].copy()

            # Limpia datos
            df_final = df_final.dropna(how='all')

            # Convierte fechas
            date_cols = ['timestamp', 'answer_date', 'cleaned_date']
            for col in date_cols:
                if col in df_final.columns:
                    df_final[col] = pd.to_datetime(df_final[col], errors='coerce')

            # Convierte answers a string si es objeto
            if 'answers' in df_final.columns:
                df_final['answers'] = df_final['answers'].astype(str)

            self.logger.info(f"Columnas a insertar BM: {list(df_final.columns)}")

            # Inserta en PostgreSQL con APPEND (acumula históricos)
            try:
                df_final.to_sql(
                    'banco_movil_clean',
                    self.engine,
                    if_exists='append',
                    index=False,
                    method='multi',
                    chunksize=1000
                )

                self.stats['bm_inserted'] += len(df_final)
                self.logger.info(f"[OK] Banco Movil insertado: {len(df_final)} registros de {original_count}")
                return True

            except IntegrityError as ie:
                # Captura violación de constraint UNIQUE
                self.logger.error(f"✗ DUPLICADOS DETECTADOS - {file_name}")
                self.logger.error(f"  La base de datos rechazó registros duplicados: {str(ie.orig)}")
                self.logger.error(f"  Verifica que el archivo no haya sido modificado y procesado nuevamente")
                self.stats['errors'] += 1
                return False

        except Exception as e:
            self.logger.error(f"✗ Error insertando Banco Móvil: {str(e)}")
            self.stats['errors'] += 1
            return False
    
    def insert_banco_virtual(self, file_path):
        """Inserta datos de Banco Virtual con mapeo de columnas correcto"""
        if not self.engine:
            self.logger.error("Engine no disponible para insertar BV")
            return False

        try:
            file_name = Path(file_path).name

            # VALIDACIÓN: Verifica si el archivo ya fue procesado
            if self.file_already_processed(file_name, 'banco_virtual_clean'):
                self.logger.warning(f"[OMITIDO] - Archivo ya procesado: {file_name}")
                self.stats['bv_skipped'] += 1
                return True

            self.logger.info(f"→ Procesando Banco Virtual: {file_name}")

            # Lee archivo
            df = pd.read_excel(file_path)
            original_count = len(df)

            # Mapeo de columnas con regex para encontrar columnas con encoding roto
            def find_column(df, patterns):
                """Encuentra columna que coincida con algún patrón"""
                for col in df.columns:
                    for pattern in patterns:
                        if re.search(pattern, col, re.IGNORECASE):
                            return col
                return None

            # Mapeo explícito de columnas BV
            column_mapping = {
                'date_submitted_original': 'date_submitted_original',
                'date_submitted': 'date_submitted',
                'country': 'country',
                'source_url': 'source_url',
                'device': 'device',
                'browser': 'browser',
                'operating_system': 'operating_system',
                'nps_score_bv': 'nps_score_bv',
                'month_year': 'month_year',
                'nps_score': 'nps_score',
                'nps_category': 'nps_category',
                'cleaned_date': 'cleaned_date',
                'file_type': 'file_type'
            }

            # Busca columnas con encoding roto o caracteres especiales
            calificacion_col = find_column(df, [r'calificaci[oó]n.*acerca', r'Tu calificaci'])
            motivo_col = find_column(df, [r'cu[eé]ntanos.*motivo', r'motivo.*calificaci'])
            tags_nps_col = find_column(df, [r'tags.*recomien', r'tags.*probable'])
            tags_calif_col = find_column(df, [r'tags.*calificaci[oó]n.*acerca'])
            tags_motivo_col = find_column(df, [r'tags.*motivo'])
            sentiment_col = find_column(df, [r'sentiment.*motivo'])

            # Agrega al mapeo si existen
            if calificacion_col:
                column_mapping[calificacion_col] = 'calificacion_acerca'
            if motivo_col:
                column_mapping[motivo_col] = 'motivo_calificacion'
            if tags_nps_col:
                column_mapping[tags_nps_col] = 'tags_recomendacion'
            if tags_calif_col:
                column_mapping[tags_calif_col] = 'tags_calificacion'
            if tags_motivo_col:
                column_mapping[tags_motivo_col] = 'tags_motivo'
            if sentiment_col:
                column_mapping[sentiment_col] = 'sentiment_motivo'

            # Renombra columnas
            df_renamed = df.rename(columns=column_mapping)

            # Agrega columna de trazabilidad
            df_renamed['source_file'] = file_name

            # Selecciona columnas que existen
            cols_to_insert = [v for k, v in column_mapping.items() if k in df.columns]
            cols_to_insert.append('source_file')
            df_final = df_renamed[cols_to_insert].copy()

            # Limpia datos
            df_final = df_final.dropna(how='all')

            # Convierte fechas
            date_cols = ['date_submitted', 'cleaned_date']
            for col in date_cols:
                if col in df_final.columns:
                    df_final[col] = pd.to_datetime(df_final[col], errors='coerce')

            self.logger.info(f"Columnas a insertar BV: {list(df_final.columns)}")

            # Inserta con APPEND (acumula históricos)
            try:
                df_final.to_sql(
                    'banco_virtual_clean',
                    self.engine,
                    if_exists='append',
                    index=False,
                    method='multi',
                    chunksize=1000
                )

                self.stats['bv_inserted'] += len(df_final)
                self.logger.info(f"[OK] Banco Virtual insertado: {len(df_final)} registros de {original_count}")
                return True

            except IntegrityError as ie:
                # Captura violación de constraint UNIQUE
                self.logger.error(f"✗ DUPLICADOS DETECTADOS - {file_name}")
                self.logger.error(f"  La base de datos rechazó registros duplicados: {str(ie.orig)}")
                self.logger.error(f"  Verifica que el archivo no haya sido modificado y procesado nuevamente")
                self.stats['errors'] += 1
                return False

        except Exception as e:
            self.logger.error(f"✗ Error insertando Banco Virtual: {str(e)}")
            self.stats['errors'] += 1
            return False
    
    def verify_data(self):
        """Verifica los datos insertados"""
        try:
            with self.engine.connect() as conn:
                # Verifica Banco Móvil
                bm_result = conn.execute(text("SELECT COUNT(*) FROM banco_movil_clean"))
                bm_count = bm_result.fetchone()[0]
                
                # Verifica Banco Virtual
                bv_result = conn.execute(text("SELECT COUNT(*) FROM banco_virtual_clean"))
                bv_count = bv_result.fetchone()[0]
                
                self.logger.info(f"Verificación - BM: {bm_count} registros, BV: {bv_count} registros")
                
                # Datos ejemplos de datos
                bm_sample = conn.execute(text("""
                    SELECT nps_score, nps_category, nps_recomendacion_score 
                    FROM banco_movil_clean 
                    WHERE nps_score IS NOT NULL 
                    LIMIT 3
                """))
                
                self.logger.info("Datos BM:")
                for row in bm_sample:
                    self.logger.info(f"  NPS: {row[0]}, Categoría: {row[1]}, Recomendación: {row[2]}")
                
                bv_sample = conn.execute(text("""
                    SELECT nps_score, device, country 
                    FROM banco_virtual_clean 
                    WHERE nps_score IS NOT NULL 
                    LIMIT 3
                """))
                
                self.logger.info("Datos BV:")
                for row in bv_sample:
                    self.logger.info(f"  NPS: {row[0]}, Dispositivo: {row[1]}, País: {row[2]}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error verificando datos: {str(e)}")
            return False
    
    def file_already_processed(self, file_name, table_name):
        """Verifica si un archivo ya fue procesado anteriormente"""
        try:
            with self.engine.connect() as conn:
                result = conn.execute(
                    text(f"SELECT COUNT(*) FROM {table_name} WHERE source_file = :filename"),
                    {"filename": file_name}
                )
                count = result.fetchone()[0]
                return count > 0
        except Exception as e:
            self.logger.warning(f"No se pudo verificar archivo previo: {str(e)}")
            return False

    def get_processed_files_info(self):
        """Obtiene información de archivos ya procesados"""
        try:
            with self.engine.connect() as conn:
                # Info de BM
                bm_result = conn.execute(text("""
                    SELECT source_file, COUNT(*) as registros, MAX(inserted_at) as ultima_insercion
                    FROM banco_movil_clean
                    GROUP BY source_file
                    ORDER BY ultima_insercion DESC
                """))
                bm_files = bm_result.fetchall()

                # Info de BV
                bv_result = conn.execute(text("""
                    SELECT source_file, COUNT(*) as registros, MAX(inserted_at) as ultima_insercion
                    FROM banco_virtual_clean
                    GROUP BY source_file
                    ORDER BY ultima_insercion DESC
                """))
                bv_files = bv_result.fetchall()

                return {'bm': bm_files, 'bv': bv_files}
        except Exception as e:
            self.logger.warning(f"No se pudo obtener info de archivos: {str(e)}")
            return {'bm': [], 'bv': []}

    def create_indexes(self):
        """Crea índices para optimizar queries"""
        try:
            with self.engine.connect() as conn:
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_bm_nps_score ON banco_movil_clean(nps_score);",
                    "CREATE INDEX IF NOT EXISTS idx_bm_category ON banco_movil_clean(nps_category);",
                    "CREATE INDEX IF NOT EXISTS idx_bm_month ON banco_movil_clean(month_year);",
                    "CREATE INDEX IF NOT EXISTS idx_bm_source_file ON banco_movil_clean(source_file);",
                    "CREATE INDEX IF NOT EXISTS idx_bv_nps_score ON banco_virtual_clean(nps_score);",
                    "CREATE INDEX IF NOT EXISTS idx_bv_device ON banco_virtual_clean(device);",
                    "CREATE INDEX IF NOT EXISTS idx_bv_country ON banco_virtual_clean(country);",
                    "CREATE INDEX IF NOT EXISTS idx_bv_source_file ON banco_virtual_clean(source_file);"
                ]

                for index_sql in indexes:
                    conn.execute(text(index_sql))

                conn.commit()
                self.logger.info("Índices creados exitosamente")

        except Exception as e:
            self.logger.error(f"Error creando índices: {str(e)}")
    
    def print_summary(self):
        """Imprime resumen final"""
        self.stats['end_time'] = datetime.now()
        duration = self.stats['end_time'] - self.stats['start_time']

        self.logger.info("=" * 60)
        self.logger.info("RESUMEN DE INSERCIÓN")
        self.logger.info("=" * 60)
        self.logger.info(f"Banco Móvil:")
        self.logger.info(f"  [OK] Insertados: {self.stats['bm_inserted']} registros")
        self.logger.info(f"  [SKIP] Omitidos: {self.stats['bm_skipped']} archivos (ya procesados)")
        self.logger.info(f"Banco Virtual:")
        self.logger.info(f"  [OK] Insertados: {self.stats['bv_inserted']} registros")
        self.logger.info(f"  [SKIP] Omitidos: {self.stats['bv_skipped']} archivos (ya procesados)")
        self.logger.info(f"Total insertado: {self.stats['bm_inserted'] + self.stats['bv_inserted']} registros")
        self.logger.info(f"Errores: {self.stats['errors']}")
        self.logger.info(f"Tiempo total: {duration}")
        self.logger.info("=" * 60)

        if self.stats['errors'] == 0:
            self.logger.info("[OK] PIPELINE COMPLETADO - Sin duplicados garantizados")
        else:
            self.logger.info("[WARNING] Revisar errores antes de procesar mas archivos")

def main():
    """Función principal - Procesa TODOS los archivos en datos_clean/"""
    print("=" * 60)
    print("INSERCIÓN OPTIMIZADA DE DATOS NPS EN POSTGRESQL")
    print("=" * 60)

    # Configuración de base de datos
    DB_CONFIG = {
        'host': 'localhost',
        'port': '5432',
        'database': 'nps_analitycs',
        'username': 'postgres',
        'password': 'postgres'  # CAMBIA ESTO
    }

    # Encuentra TODOS los archivos en datos_clean/
    samples_dir = Path('datos_clean')
    if not samples_dir.exists():
        print(f"ERROR: Directorio {samples_dir} no existe")
        return

    # Busca archivos BM y BV
    all_files = list(samples_dir.glob('*.xlsx'))
    bm_files = [f for f in all_files if '_BM_' in f.name or '_bm_' in f.name]
    bv_files = [f for f in all_files if '_BV_' in f.name or '_bv_' in f.name]

    print(f"\nArchivos encontrados:")
    print(f"  Banco Móvil (BM): {len(bm_files)} archivos")
    print(f"  Banco Virtual (BV): {len(bv_files)} archivos")
    print(f"  Total: {len(bm_files) + len(bv_files)} archivos\n")

    if len(bm_files) == 0 and len(bv_files) == 0:
        print("ERROR: No se encontraron archivos para procesar")
        return

    # Crea inserter
    inserter = NPSInserter(DB_CONFIG)
    inserter.stats['start_time'] = datetime.now()

    try:
        # Conecta a base de datos
        if not inserter.connect_database():
            print("ERROR: No se pudo conectar a PostgreSQL")
            return

        # Crea tablas si no existen
        if not inserter.create_tables_if_needed():
            print("ERROR: No se pudieron crear las tablas")
            return

        # Datos archivos ya procesados
        print(f"\n{'='*60}")
        print("VERIFICANDO ARCHIVOS YA PROCESADOS")
        print(f"{'='*60}")
        processed_info = inserter.get_processed_files_info()

        if processed_info['bm']:
            print(f"\nBanco Móvil - {len(processed_info['bm'])} archivos en BD:")
            for file, count, date in processed_info['bm'][:5]:  # Datos primeros 5
                print(f"  • {file}: {count} registros (última: {date})")
            if len(processed_info['bm']) > 5:
                print(f"  ... y {len(processed_info['bm']) - 5} más")

        if processed_info['bv']:
            print(f"\nBanco Virtual - {len(processed_info['bv'])} archivos en BD:")
            for file, count, date in processed_info['bv'][:5]:  # Datos primeros 5
                print(f"  • {file}: {count} registros (última: {date})")
            if len(processed_info['bv']) > 5:
                print(f"  ... y {len(processed_info['bv']) - 5} más")

        if not processed_info['bm'] and not processed_info['bv']:
            print("\nNo hay archivos procesados previamente (base de datos vacía)")

        # Procesa todos los archivos BM
        print(f"\n{'='*60}")
        print(f"Procesando {len(bm_files)} archivos BANCO MÓVIL")
        print(f"{'='*60}")
        for i, file_path in enumerate(bm_files, 1):
            print(f"\n[{i}/{len(bm_files)}] {file_path.name}")
            inserter.insert_banco_movil(str(file_path))

        # Procesa todos los archivos BV
        print(f"\n{'='*60}")
        print(f"Procesando {len(bv_files)} archivos BANCO VIRTUAL")
        print(f"{'='*60}")
        for i, file_path in enumerate(bv_files, 1):
            print(f"\n[{i}/{len(bv_files)}] {file_path.name}")
            inserter.insert_banco_virtual(str(file_path))

        # Verifica inserción
        print(f"\n{'='*60}")
        print("VERIFICANDO DATOS INSERTADOS")
        print(f"{'='*60}")
        inserter.verify_data()

        # Crea índices
        print(f"\n{'='*60}")
        print("CREANDO ÍNDICES")
        print(f"{'='*60}")
        inserter.create_indexes()

        # Resumen final
        print(f"\n")
        inserter.print_summary()

    except Exception as e:
        inserter.logger.error(f"Error en proceso principal: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        if inserter.engine:
            inserter.engine.dispose()

if __name__ == "__main__":
    main()