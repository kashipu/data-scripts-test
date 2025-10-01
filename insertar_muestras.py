#!/usr/bin/env python3
"""
Script Completo: Insertar Muestras Limpias en PostgreSQL
Crea tablas separadas para Banco Móvil y Banco Virtual
"""

import pandas as pd
from sqlalchemy import create_engine, text
import psycopg2
import logging
from datetime import datetime
import os
from pathlib import Path

class NPSInserter:
    """Clase para insertar datos NPS limpios en PostgreSQL"""
    
    def __init__(self, db_config):
        self.db_config = db_config
        self.engine = None
        self.setup_logging()
        self.stats = {
            'bm_inserted': 0,
            'bv_inserted': 0,
            'errors': 0,
            'start_time': None,
            'end_time': None
        }
    
    def setup_logging(self):
        """Configura logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('insercion_datos.log', encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def connect_database(self):
        """Establece conexión con PostgreSQL"""
        try:
            # Primero prueba conexión básica con parámetros de encoding
            conn = psycopg2.connect(
                host=self.db_config['host'],
                port=self.db_config['port'],
                database=self.db_config['database'],
                user=self.db_config['username'],
                password=self.db_config['password'],
                client_encoding='utf8'
            )
            conn.close()
            self.logger.info("Conexión PostgreSQL exitosa")
            
            # Crea engine SQLAlchemy con parámetros adicionales
            connection_string = (
                f"postgresql://{self.db_config['username']}:"
                f"{self.db_config['password']}@{self.db_config['host']}:"
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
            self.logger.error(f"Error conectando a PostgreSQL: {str(e)}")
            return False
    
    def create_tables_if_needed(self):
        """Crea tablas optimizadas si no existen"""
        if not self.engine:
            self.logger.error("Engine no disponible para crear tablas")
            return False
            
        try:
            with self.engine.connect() as conn:
                # Tabla para Banco Móvil
                bm_table_sql = """
                CREATE TABLE IF NOT EXISTS banco_movil_clean (
                    id SERIAL PRIMARY KEY,
                    timestamp TIMESTAMP,
                    customer_id VARCHAR(100),
                    channel VARCHAR(50),
                    nps_recomendacion_score INTEGER,
                    nps_recomendacion_motivo TEXT,
                    csat_satisfaccion_score INTEGER,
                    csat_satisfaccion_motivo TEXT,
                    nps_score_original INTEGER,
                    nps_score INTEGER,
                    nps_category VARCHAR(20),
                    cleaned_date TIMESTAMP,
                    file_type VARCHAR(10),
                    month_year VARCHAR(7),
                    processed_date TIMESTAMP DEFAULT NOW()
                );
                """
                
                # Tabla para Banco Virtual  
                bv_table_sql = """
                CREATE TABLE IF NOT EXISTS banco_virtual_clean (
                    id SERIAL PRIMARY KEY,
                    date_submitted_original TIMESTAMP,
                    date_submitted TIMESTAMP,
                    country VARCHAR(50),
                    source_url TEXT,
                    device VARCHAR(50),
                    browser VARCHAR(100),
                    operating_system VARCHAR(100),
                    nps_score_bv INTEGER,
                    nps_score INTEGER,
                    nps_category VARCHAR(20),
                    calificacion_acerca TEXT,
                    motivo_calificacion TEXT,
                    tags_nps TEXT,
                    tags_calificacion TEXT,
                    tags_motivo TEXT,
                    sentiment_motivo VARCHAR(20),
                    cleaned_date TIMESTAMP,
                    file_type VARCHAR(10),
                    month_year VARCHAR(7),
                    processed_date TIMESTAMP DEFAULT NOW()
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
        """Inserta datos de Banco Móvil"""
        if not self.engine:
            self.logger.error("Engine no disponible para insertar BM")
            return False
            
        try:
            self.logger.info(f"Insertando Banco Móvil desde: {file_path}")
            
            # Lee archivo
            df = pd.read_excel(file_path)
            original_count = len(df)
            
            # Log de columnas disponibles
            self.logger.info(f"Columnas en BM: {list(df.columns)}")
            
            # FILTRAR SOLO COLUMNAS RELEVANTES PARA LA TABLA
            columns_to_keep = [
                'timestamp', 'customer_id', 'channel',
                'nps_recomendacion_score', 'nps_recomendacion_motivo',
                'csat_satisfaccion_score', 'csat_satisfaccion_motivo',
                'nps_score', 'nps_category', 'cleaned_date', 'file_type', 'month_year'
            ]
            
            # Filtrar solo columnas que existen
            available_columns = [col for col in columns_to_keep if col in df.columns]
            df_filtered = df[available_columns].copy()
            
            self.logger.info(f"Columnas filtradas para inserción: {available_columns}")
            
            # Limpia datos antes de insertar
            df_filtered = df_filtered.dropna(how='all')  # Remueve filas completamente vacías
            
            # Convierte fechas
            if 'timestamp' in df_filtered.columns:
                df_filtered['timestamp'] = pd.to_datetime(df_filtered['timestamp'], errors='coerce')
            if 'cleaned_date' in df_filtered.columns:
                df_filtered['cleaned_date'] = pd.to_datetime(df_filtered['cleaned_date'], errors='coerce')
            
            # Inserta en PostgreSQL
            rows_inserted = df_filtered.to_sql(
                'banco_movil_clean', 
                self.engine, 
                if_exists='append',
                index=False,
                method='multi',
                chunksize=1000
            )
            
            self.stats['bm_inserted'] = len(df_filtered)
            self.logger.info(f"Banco Móvil insertado: {len(df_filtered)} registros (original: {original_count})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error insertando Banco Móvil: {str(e)}")
            self.stats['errors'] += 1
            return False
    
    def insert_banco_virtual(self, file_path):
        """Inserta datos de Banco Virtual"""
        if not self.engine:
            self.logger.error("Engine no disponible para insertar BV")
            return False
            
        try:
            self.logger.info(f"Insertando Banco Virtual desde: {file_path}")
            
            # Lee archivo
            df = pd.read_excel(file_path)
            original_count = len(df)
            
            # Log de columnas disponibles
            self.logger.info(f"Columnas en BV: {list(df.columns)}")
            
            # FILTRAR SOLO COLUMNAS RELEVANTES PARA LA TABLA
            columns_to_keep = [
                'date_submitted', 'country', 'source_url', 'device', 'browser', 'operating_system',
                'nps_score_bv', 'nps_score', 'nps_category', 'cleaned_date', 'file_type', 'month_year'
            ]
            
            # Agregar columnas de feedback si existen (con nombres largos)
            feedback_cols = [col for col in df.columns if 'calificación' in col.lower() or 'motivo' in col.lower() or 'tags' in col.lower() or 'sentiment' in col.lower()]
            columns_to_keep.extend(feedback_cols)
            
            # Filtrar solo columnas que existen
            available_columns = [col for col in columns_to_keep if col in df.columns]
            df_filtered = df[available_columns].copy()
            
            self.logger.info(f"Columnas filtradas para inserción: {available_columns}")
            
            # Limpia datos antes de insertar
            df_filtered = df_filtered.dropna(how='all')
            
            # Convierte fechas
            if 'date_submitted' in df_filtered.columns:
                df_filtered['date_submitted'] = pd.to_datetime(df_filtered['date_submitted'], errors='coerce')
            if 'cleaned_date' in df_filtered.columns:
                df_filtered['cleaned_date'] = pd.to_datetime(df_filtered['cleaned_date'], errors='coerce')
            
            # Inserta en PostgreSQL usando if_exists='replace' para recrear tabla con columnas correctas
            rows_inserted = df_filtered.to_sql(
                'banco_virtual_clean',
                self.engine,
                if_exists='replace',  # Cambiado a replace para que cree tabla con columnas correctas 
                index=False,
                method='multi',
                chunksize=1000
            )
            
            self.stats['bv_inserted'] = len(df_filtered)
            self.logger.info(f"Banco Virtual insertado: {len(df_filtered)} registros (original: {original_count})")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error insertando Banco Virtual: {str(e)}")
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
                
                # Muestra ejemplos de datos
                bm_sample = conn.execute(text("""
                    SELECT nps_score, nps_category, nps_recomendacion_score 
                    FROM banco_movil_clean 
                    WHERE nps_score IS NOT NULL 
                    LIMIT 3
                """))
                
                self.logger.info("Muestra BM:")
                for row in bm_sample:
                    self.logger.info(f"  NPS: {row[0]}, Categoría: {row[1]}, Recomendación: {row[2]}")
                
                bv_sample = conn.execute(text("""
                    SELECT nps_score, device, country 
                    FROM banco_virtual_clean 
                    WHERE nps_score IS NOT NULL 
                    LIMIT 3
                """))
                
                self.logger.info("Muestra BV:")
                for row in bv_sample:
                    self.logger.info(f"  NPS: {row[0]}, Dispositivo: {row[1]}, País: {row[2]}")
                
                return True
                
        except Exception as e:
            self.logger.error(f"Error verificando datos: {str(e)}")
            return False
    
    def create_indexes(self):
        """Crea índices para optimizar queries"""
        try:
            with self.engine.connect() as conn:
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_bm_nps_score ON banco_movil_clean(nps_score);",
                    "CREATE INDEX IF NOT EXISTS idx_bm_category ON banco_movil_clean(nps_category);", 
                    "CREATE INDEX IF NOT EXISTS idx_bm_month ON banco_movil_clean(month_year);",
                    "CREATE INDEX IF NOT EXISTS idx_bv_nps_score ON banco_virtual_clean(nps_score);",
                    "CREATE INDEX IF NOT EXISTS idx_bv_device ON banco_virtual_clean(device);",
                    "CREATE INDEX IF NOT EXISTS idx_bv_country ON banco_virtual_clean(country);"
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
        
        self.logger.info("=" * 50)
        self.logger.info("RESUMEN DE INSERCIÓN")
        self.logger.info("=" * 50)
        self.logger.info(f"Banco Móvil insertado: {self.stats['bm_inserted']} registros")
        self.logger.info(f"Banco Virtual insertado: {self.stats['bv_inserted']} registros")
        self.logger.info(f"Total insertado: {self.stats['bm_inserted'] + self.stats['bv_inserted']} registros")
        self.logger.info(f"Errores: {self.stats['errors']}")
        self.logger.info(f"Tiempo total: {duration}")
        self.logger.info("=" * 50)
        
        if self.stats['errors'] == 0:
            self.logger.info("PIPELINE VALIDADO - Listo para archivos grandes")
        else:
            self.logger.info("Revisar errores antes de procesar archivos grandes")

def main():
    """Función principal"""
    print("INSERCION DE MUESTRAS NPS EN POSTGRESQL")
    print("=" * 50)
    
    # Configuración de base de datos
    DB_CONFIG = {
        'host': 'localhost',
        'port': '5432',
        'database': 'test_nps',
        'username': 'postgres',
        'password': 'postgres'  # CAMBIA ESTO
    }
    
    # Archivos a procesar - ACTUALIZAR ESTAS RUTAS
    files = {
        'bm': 'muestras_limpias/agosto_bm_2025_muestra_281230_LIMPIO.xlsx',  # Cambia por tu archivo BM limpio
        'bv': 'muestras_limpias/agosto_bv_2025_muestra_1904_LIMPIO.xlsx'   # Cambia por tu archivo BV limpio
    }
    
    # Verifica que existan los archivos
    for file_type, file_path in files.items():
        if not os.path.exists(file_path):
            print(f"ERROR: Archivo no encontrado: {file_path}")
            return
    
    # Crea inserter
    inserter = NPSInserter(DB_CONFIG)
    inserter.stats['start_time'] = datetime.now()
    
    try:
        # Conecta a base de datos
        if not inserter.connect_database():
            print("ERROR: No se pudo conectar a PostgreSQL")
            return
        
        # Inserta datos (las tablas se crean automáticamente)
        success_bm = inserter.insert_banco_movil(files['bm'])
        success_bv = inserter.insert_banco_virtual(files['bv'])
        
        if success_bm and success_bv:
            # Verifica inserción
            inserter.verify_data()
            
            # Crea índices
            inserter.create_indexes()
            
            # Resumen final
            inserter.print_summary()
            
        else:
            print("ERROR: Falló la inserción de algunos archivos")
    
    except Exception as e:
        inserter.logger.error(f"Error en proceso principal: {str(e)}")
        
    finally:
        if inserter.engine:
            inserter.engine.dispose()

if __name__ == "__main__":
    main()