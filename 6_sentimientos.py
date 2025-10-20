"""
======================================================================================
SCRIPT: 6_sentimientos.py
======================================================================================
PROPÓSITO:
    Analiza sentimientos de comentarios NPS/CSAT usando Ollama e inserta resultados
    en PostgreSQL de forma incremental.

QUÉ HACE:
    1. Conecta a PostgreSQL y extrae comentarios NO ANALIZADOS (incremental)
    2. Analiza sentimientos (POS/NEU/NEG) con Ollama
    3. Inserta resultados en tabla sentimientos_analisis
    4. Reutiliza análisis de comentarios duplicados (por hash SHA256)
    5. Permite procesamiento por lotes sin reprocesar

CARACTERÍSTICAS:
    ✅ Procesamiento incremental: solo analiza comentarios nuevos
    ✅ Deduplicación por hash: reutiliza análisis de comentarios idénticos
    ✅ Protección anti-duplicados: constraint UNIQUE en BD
    ✅ Procesamiento paralelo: múltiples requests a Ollama simultáneos
    ✅ Batch processing: procesa en lotes configurables

TABLAS ANALIZADAS:
    Banco Móvil (banco_movil_clean):
        - nps_recomendacion_motivo (canal='BM', tipo='NPS')
        - csat_satisfaccion_motivo (canal='BM', tipo='CSAT')

    Banco Virtual (banco_virtual_clean):
        - motivo_calificacion (canal='BV', tipo='NPS')

TABLA DE DESTINO:
    sentimientos_analisis (debe existir previamente)

USO:
    python 6_sentimientos.py                    # 1000 comentarios
    python 6_sentimientos.py --limit 5000       # 5000 comentarios
    python 6_sentimientos.py --limit 0          # TODOS los pendientes
    python 6_sentimientos.py --sin-limite       # Alias para TODOS

REQUISITOS:
    - pip install pandas sqlalchemy psycopg2-binary requests
    - Ollama instalado y corriendo: ollama serve
    - Modelo descargado: ollama pull llama3.1:8b
======================================================================================
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
import argparse
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib
import requests
import json
import time
import sys

# ======================================================================================
# CONFIGURACIÓN
# ======================================================================================

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('analisis_sentimientos.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

# Configuración de Ollama (optimizada para velocidad)
OLLAMA_CONFIG = {
    'base_url': 'http://localhost:11434',
    'model': 'llama3.1:8b',
    'timeout': 60,  # Timeout por request (aumentado a 60s para comentarios complejos)
    'num_predict': 150,  # Tokens máximos (aumentado para JSON completo)
    'temperature': 0.1,  # Baja para consistencia
}

# Configuración del procesamiento (OPTIMIZADO)
BATCH_SIZE = 50  # Lotes para Ollama (aumentado para mejor throughput)
MIN_LONGITUD_PALABRAS = 2  # Mínimo de palabras para analizar
MAX_WORKERS = 6  # Threads paralelos (reducido para evitar saturación)

# ======================================================================================
# CLASE PRINCIPAL
# ======================================================================================

class AnalizadorSentimientos:
    """Analizador de sentimientos usando Ollama"""

    def __init__(self, db_config):
        self.db_config = db_config
        self.engine = None
        self.df_results = None
        self.hash_cache = {}  # Caché local para hashes ya analizados

    # ==================================================================================
    # CONEXIÓN A BASE DE DATOS
    # ==================================================================================

    def conectar_db(self):
        """Conecta a PostgreSQL"""
        try:
            connection_string = (
                f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
                f"?client_encoding=utf8"
            )
            self.engine = create_engine(connection_string)
            logger.info(f"[OK] Conectado a: {self.db_config['database']}")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Conexión BD: {e}")
            return False

    # ==================================================================================
    # OLLAMA
    # ==================================================================================

    def verificar_ollama(self):
        """Verifica que Ollama esté disponible"""
        try:
            logger.info("Verificando Ollama...")
            logger.info(f"  URL: {OLLAMA_CONFIG['base_url']}")
            logger.info(f"  Modelo: {OLLAMA_CONFIG['model']}")

            # Verificar servicio
            response = requests.get(f"{OLLAMA_CONFIG['base_url']}/api/tags", timeout=5)
            response.raise_for_status()
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if OLLAMA_CONFIG['model'] not in model_names:
                logger.error(f"[ERROR] Modelo '{OLLAMA_CONFIG['model']}' no encontrado")
                logger.info(f"  Disponibles: {', '.join(model_names)}")
                return False

            logger.info(f"[OK] Ollama conectado ({len(models)} modelos)")

            # Test rápido
            test_result = self._analizar_texto("Test")
            if test_result and test_result.get('sentimiento'):
                logger.info(f"[OK] Test exitoso: {test_result['sentimiento']}")

            return True

        except requests.exceptions.ConnectionError:
            logger.error("[ERROR] Ollama no está corriendo")
            logger.info("  Ejecuta: ollama serve")
            return False
        except Exception as e:
            logger.error(f"[ERROR] Ollama: {e}")
            return False

    def _analizar_texto(self, texto):
        """Analiza sentimiento de un texto con Ollama"""
        if not texto or pd.isna(texto):
            return {
                'sentimiento': 'SIN_ANALISIS',
                'confianza': None,
                'prob_positivo': None,
                'prob_neutral': None,
                'prob_negativo': None
            }

        # Validar longitud mínima
        texto_limpio = str(texto).strip()
        num_palabras = len(texto_limpio.split())

        if num_palabras < MIN_LONGITUD_PALABRAS:
            return {
                'sentimiento': 'TEXTO_CORTO',
                'confianza': None,
                'prob_positivo': None,
                'prob_neutral': None,
                'prob_negativo': None
            }

        # Prompt optimizado para respuestas rápidas
        prompt = f"""Analiza el sentimiento del siguiente comentario en español:
"{texto_limpio}"

Responde SOLO con JSON válido (sin texto adicional):
{{"sentimiento":"POS/NEU/NEG","confianza":0.X,"prob_positivo":0.X,"prob_neutral":0.X,"prob_negativo":0.X}}"""

        try:
            inicio = time.time()

            response = requests.post(
                f"{OLLAMA_CONFIG['base_url']}/api/generate",
                json={
                    "model": OLLAMA_CONFIG['model'],
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": OLLAMA_CONFIG['temperature'],
                        "top_p": 0.9,
                        "num_predict": OLLAMA_CONFIG['num_predict'],
                        "num_ctx": 1024,  # Contexto aumentado
                    }
                },
                timeout=OLLAMA_CONFIG['timeout']
            )
            response.raise_for_status()

            tiempo_ms = (time.time() - inicio) * 1000

            # Extraer JSON de la respuesta
            respuesta_texto = response.json().get('response', '').strip()

            # Buscar JSON en la respuesta
            inicio_json = respuesta_texto.find('{')
            fin_json = respuesta_texto.rfind('}') + 1

            if inicio_json >= 0 and fin_json > inicio_json:
                json_str = respuesta_texto[inicio_json:fin_json]
                resultado = json.loads(json_str)

                # Normalizar sentimiento
                sent_raw = resultado.get('sentimiento', '').upper()
                if 'POS' in sent_raw:
                    sentimiento = 'POS'
                elif 'NEG' in sent_raw:
                    sentimiento = 'NEG'
                else:
                    sentimiento = 'NEU'

                return {
                    'sentimiento': sentimiento,
                    'confianza': float(resultado.get('confianza', 0.5)),
                    'prob_positivo': float(resultado.get('prob_positivo', 0.0)),
                    'prob_neutral': float(resultado.get('prob_neutral', 0.0)),
                    'prob_negativo': float(resultado.get('prob_negativo', 0.0)),
                    'tiempo_procesamiento_ms': tiempo_ms
                }
            else:
                # Fallback: análisis por palabras clave
                return self._analisis_fallback(respuesta_texto)

        except requests.exceptions.Timeout:
            logger.warning(f"Timeout al analizar (>{OLLAMA_CONFIG['timeout']}s)")
            return {'sentimiento': 'ERROR', 'confianza': None, 'prob_positivo': None, 'prob_neutral': None, 'prob_negativo': None}
        except Exception as e:
            logger.warning(f"Error Ollama: {str(e)[:100]}")
            return {'sentimiento': 'ERROR', 'confianza': None, 'prob_positivo': None, 'prob_neutral': None, 'prob_negativo': None}

    def _analisis_fallback(self, respuesta_texto):
        """Análisis simple cuando Ollama no retorna JSON válido"""
        resp_lower = respuesta_texto.lower()

        if any(p in resp_lower for p in ['positivo', 'bueno', 'excelente', 'satisfecho']):
            return {'sentimiento': 'POS', 'confianza': 0.6, 'prob_positivo': 0.7, 'prob_neutral': 0.2, 'prob_negativo': 0.1}
        elif any(p in resp_lower for p in ['negativo', 'malo', 'problema', 'insatisfecho']):
            return {'sentimiento': 'NEG', 'confianza': 0.6, 'prob_positivo': 0.1, 'prob_neutral': 0.2, 'prob_negativo': 0.7}
        else:
            return {'sentimiento': 'NEU', 'confianza': 0.5, 'prob_positivo': 0.3, 'prob_neutral': 0.4, 'prob_negativo': 0.3}

    def analizar_batch(self, textos):
        """Analiza múltiples textos en paralelo"""
        resultados = [None] * len(textos)

        def analizar_con_indice(idx_texto):
            idx, texto = idx_texto
            return idx, self._analizar_texto(texto)

        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = executor.map(analizar_con_indice, enumerate(textos))
            for idx, resultado in futures:
                resultados[idx] = resultado

        return resultados

    # ==================================================================================
    # EXTRACCIÓN DE DATOS (INCREMENTAL - SOLO NO ANALIZADOS)
    # ==================================================================================

    def extraer_datos_bm(self, limit=1000, fecha_desde=None, fecha_hasta=None):
        """Extrae comentarios de Banco Móvil NO ANALIZADOS"""
        query = """
        -- BM - NPS NO ANALIZADOS
        SELECT
            bm.id as registro_id,
            bm.answer_date as fecha,
            bm.month_year,
            'BM' as canal,
            'NPS' as tipo_metrica,
            bm.nps_recomendacion_score as calificacion,
            bm.nps_category as categoria,
            bm.nps_recomendacion_motivo as comentario,
            'banco_movil_clean' as tabla_origen,
            'nps_recomendacion_motivo' as columna_origen
        FROM banco_movil_clean bm
        LEFT JOIN sentimientos_analisis sa
            ON sa.tabla_origen = 'banco_movil_clean'
            AND sa.registro_origen_id = bm.id
            AND sa.columna_origen = 'nps_recomendacion_motivo'
        WHERE bm.nps_recomendacion_motivo IS NOT NULL
          AND LENGTH(TRIM(bm.nps_recomendacion_motivo)) > 0
          AND sa.id IS NULL  -- ← SOLO NO ANALIZADOS
          {fecha_filter}

        UNION ALL

        -- BM - CSAT NO ANALIZADOS
        SELECT
            bm.id as registro_id,
            bm.answer_date as fecha,
            bm.month_year,
            'BM' as canal,
            'CSAT' as tipo_metrica,
            bm.csat_satisfaccion_score as calificacion,
            NULL as categoria,
            bm.csat_satisfaccion_motivo as comentario,
            'banco_movil_clean' as tabla_origen,
            'csat_satisfaccion_motivo' as columna_origen
        FROM banco_movil_clean bm
        LEFT JOIN sentimientos_analisis sa
            ON sa.tabla_origen = 'banco_movil_clean'
            AND sa.registro_origen_id = bm.id
            AND sa.columna_origen = 'csat_satisfaccion_motivo'
        WHERE bm.csat_satisfaccion_motivo IS NOT NULL
          AND LENGTH(TRIM(bm.csat_satisfaccion_motivo)) > 0
          AND sa.id IS NULL  -- ← SOLO NO ANALIZADOS
          {fecha_filter}

        ORDER BY fecha DESC
        {limit_clause}
        """

        fecha_filter = ""
        if fecha_desde:
            fecha_filter += f"AND answer_date >= '{fecha_desde}' "
        if fecha_hasta:
            fecha_filter += f"AND answer_date <= '{fecha_hasta}' "

        limit_clause = f"LIMIT {limit}" if limit > 0 else ""
        query = query.format(fecha_filter=fecha_filter, limit_clause=limit_clause)

        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        return df

    def extraer_datos_bv(self, limit=1000, fecha_desde=None, fecha_hasta=None):
        """Extrae comentarios de Banco Virtual NO ANALIZADOS"""
        query = """
        -- BV - NPS NO ANALIZADOS
        SELECT
            bv.id as registro_id,
            bv.date_submitted as fecha,
            bv.month_year,
            'BV' as canal,
            'NPS' as tipo_metrica,
            bv.nps_score as calificacion,
            bv.nps_category as categoria,
            bv.motivo_calificacion as comentario,
            'banco_virtual_clean' as tabla_origen,
            'motivo_calificacion' as columna_origen
        FROM banco_virtual_clean bv
        LEFT JOIN sentimientos_analisis sa
            ON sa.tabla_origen = 'banco_virtual_clean'
            AND sa.registro_origen_id = bv.id
            AND sa.columna_origen = 'motivo_calificacion'
        WHERE bv.motivo_calificacion IS NOT NULL
          AND LENGTH(TRIM(bv.motivo_calificacion)) > 0
          AND sa.id IS NULL  -- ← SOLO NO ANALIZADOS
          {fecha_filter}

        ORDER BY date_submitted DESC
        {limit_clause}
        """

        fecha_filter = ""
        if fecha_desde:
            fecha_filter += f"AND date_submitted >= '{fecha_desde}' "
        if fecha_hasta:
            fecha_filter += f"AND date_submitted <= '{fecha_hasta}' "

        limit_clause = f"LIMIT {limit}" if limit > 0 else ""
        query = query.format(fecha_filter=fecha_filter, limit_clause=limit_clause)

        with self.engine.connect() as conn:
            df = pd.read_sql(text(query), conn)

        return df

    def extraer_datos_paralelo(self, limit=1000, fecha_desde=None, fecha_hasta=None):
        """Extrae datos de BM y BV en paralelo"""
        logger.info("Extrayendo datos en paralelo...")

        with ThreadPoolExecutor(max_workers=2) as executor:
            future_bm = executor.submit(self.extraer_datos_bm, limit, fecha_desde, fecha_hasta)
            future_bv = executor.submit(self.extraer_datos_bv, limit, fecha_desde, fecha_hasta)

            df_bm = future_bm.result()
            df_bv = future_bv.result()

        logger.info(f"  BM: {len(df_bm)} | BV: {len(df_bv)}")

        df_completo = pd.concat([df_bm, df_bv], ignore_index=True)
        logger.info(f"[OK] Total: {len(df_completo)} comentarios pendientes")

        return df_completo

    # ==================================================================================
    # PROCESAMIENTO Y DEDUPLICACIÓN
    # ==================================================================================

    def calcular_hash(self, texto):
        """Calcula SHA256 hash para deduplicación"""
        return hashlib.sha256(texto.encode('utf-8')).hexdigest()

    def buscar_analisis_por_hash(self, comentario_hash):
        """Busca análisis previo por hash (reutilización) - MÉTODO INDIVIDUAL (deprecado)"""
        query = """
            SELECT sentimiento, confianza, prob_positivo, prob_neutral, prob_negativo
            FROM sentimientos_analisis
            WHERE comentario_hash = :hash
            LIMIT 1
        """
        with self.engine.connect() as conn:
            result = conn.execute(text(query), {'hash': comentario_hash})
            row = result.fetchone()
            if row:
                return {
                    'sentimiento': row[0],
                    'confianza': float(row[1]) if row[1] else None,
                    'prob_positivo': float(row[2]) if row[2] else None,
                    'prob_neutral': float(row[3]) if row[3] else None,
                    'prob_negativo': float(row[4]) if row[4] else None
                }
            return None

    def buscar_analisis_por_hashes_batch(self, hashes_list):
        """Busca análisis previos para múltiples hashes en UNA SOLA QUERY (OPTIMIZADO)"""
        if not hashes_list:
            return {}

        # Crear placeholders para IN clause
        placeholders = ','.join([f':hash_{i}' for i in range(len(hashes_list))])
        query = f"""
            SELECT comentario_hash, sentimiento, confianza, prob_positivo, prob_neutral, prob_negativo
            FROM sentimientos_analisis
            WHERE comentario_hash IN ({placeholders})
        """

        # Crear parámetros
        params = {f'hash_{i}': hash_val for i, hash_val in enumerate(hashes_list)}

        resultados = {}
        with self.engine.connect() as conn:
            result = conn.execute(text(query), params)
            for row in result:
                resultados[row[0]] = {
                    'sentimiento': row[1],
                    'confianza': float(row[2]) if row[2] else None,
                    'prob_positivo': float(row[3]) if row[3] else None,
                    'prob_neutral': float(row[4]) if row[4] else None,
                    'prob_negativo': float(row[5]) if row[5] else None
                }

        return resultados

    def procesar_datos(self, df):
        """Procesa comentarios: analiza e inserta en PostgreSQL (OPTIMIZADO)"""
        logger.info(f"\nProcesando {len(df)} comentarios...")
        logger.info(f"  Modelo: {OLLAMA_CONFIG['model']}")
        logger.info(f"  Batch: {BATCH_SIZE} | Workers: {MAX_WORKERS}")

        resultados = []
        total = len(df)
        total_nuevos = 0
        total_reutilizados = 0
        total_cache_local = 0

        datos = df.to_dict('records')

        # Procesar en lotes
        for i in range(0, total, BATCH_SIZE):
            batch_end = min(i + BATCH_SIZE, total)
            batch = datos[i:batch_end]

            comentarios_a_analizar = []
            indices_analizar = []
            registros_db = []

            # PASO 1: Calcular todos los hashes del batch
            hashes_batch = []
            hash_to_idx = {}
            for idx, row in enumerate(batch):
                comentario_texto = row['comentario']
                comentario_hash = self.calcular_hash(comentario_texto)
                hashes_batch.append(comentario_hash)
                hash_to_idx[comentario_hash] = idx

                registros_db.append({
                    'row': row,
                    'hash': comentario_hash,
                    'analisis': None,
                    'idx': idx
                })

            # PASO 2: Buscar todos los hashes en UNA SOLA QUERY (en lugar de N queries)
            analisis_previos = self.buscar_analisis_por_hashes_batch(hashes_batch)

            # PASO 3: Verificar caché local y asignar análisis previos
            for idx, row in enumerate(batch):
                comentario_texto = row['comentario']
                comentario_hash = hashes_batch[idx]
                analisis = None

                # Verificar caché local primero
                if comentario_hash in self.hash_cache:
                    analisis = self.hash_cache[comentario_hash]
                    total_cache_local += 1
                # Luego verificar BD
                elif comentario_hash in analisis_previos:
                    analisis = analisis_previos[comentario_hash]
                    total_reutilizados += 1
                    # Guardar en caché local
                    self.hash_cache[comentario_hash] = analisis

                if analisis:
                    # Asignar análisis existente
                    registros_db[idx]['analisis'] = analisis
                else:
                    # Marcar para analizar
                    comentarios_a_analizar.append(comentario_texto)
                    indices_analizar.append(idx)

            # PASO 4: Analizar nuevos en batch
            if comentarios_a_analizar:
                analisis_batch = self.analizar_batch(comentarios_a_analizar)
                total_nuevos += len(analisis_batch)

                # Asignar análisis y guardar en caché
                for idx_analizar, analisis in zip(indices_analizar, analisis_batch):
                    for reg in registros_db:
                        if reg['idx'] == idx_analizar:
                            reg['analisis'] = analisis
                            # Guardar en caché local
                            self.hash_cache[reg['hash']] = analisis
                            break

            # Preparar para inserción
            registros_insertar = []
            for reg in registros_db:
                row = reg['row']
                analisis = reg['analisis']

                registro_db = {
                    'canal': row['canal'],
                    'tipo_comentario': row['tipo_metrica'],
                    'tabla_origen': row['tabla_origen'],
                    'registro_origen_id': int(row['registro_id']),
                    'columna_origen': row['columna_origen'],
                    'score_metrica': float(row['calificacion']) if pd.notna(row['calificacion']) else None,
                    'categoria_metrica': row.get('categoria'),
                    'comentario_texto': row['comentario'],
                    'comentario_hash': reg['hash'],
                    'longitud_caracteres': len(row['comentario']),
                    'longitud_palabras': len(row['comentario'].split()),
                    'sentimiento': analisis['sentimiento'],
                    'confianza': analisis.get('confianza'),
                    'prob_positivo': analisis.get('prob_positivo'),
                    'prob_neutral': analisis.get('prob_neutral'),
                    'prob_negativo': analisis.get('prob_negativo'),
                    'modelo_version': f"ollama/{OLLAMA_CONFIG['model']}",
                    'dispositivo': 'ollama',
                    'tiempo_procesamiento_ms': analisis.get('tiempo_procesamiento_ms')
                }
                registros_insertar.append(registro_db)

                resultados.append({
                    'canal': row['canal'],
                    'tipo_metrica': row['tipo_metrica'],
                    'sentimiento': analisis['sentimiento'],
                    'confianza': analisis.get('confianza')
                })

            # Insertar batch
            self.insertar_analisis_batch(registros_insertar)

            # Progreso
            porcentaje = batch_end / total * 100
            logger.info(f"  {batch_end}/{total} ({porcentaje:.1f}%) - Nuevos: {total_nuevos} | BD: {total_reutilizados} | Cache: {total_cache_local}")

        self.df_results = pd.DataFrame(resultados)
        logger.info(f"[OK] Completado - Nuevos: {total_nuevos} | Reutilizados BD: {total_reutilizados} | Cache local: {total_cache_local}")
        logger.info(f"[INFO] Cache local contiene {len(self.hash_cache)} hashes")

        return self.df_results

    def insertar_analisis_batch(self, registros):
        """Inserta batch en sentimientos_analisis"""
        if not registros:
            return

        query = """
            INSERT INTO sentimientos_analisis (
                canal, tipo_comentario, tabla_origen, registro_origen_id, columna_origen,
                score_metrica, categoria_metrica, comentario_texto, comentario_hash,
                longitud_caracteres, longitud_palabras,
                sentimiento, confianza, prob_positivo, prob_neutral, prob_negativo,
                modelo_version, dispositivo, tiempo_procesamiento_ms
            ) VALUES (
                :canal, :tipo_comentario, :tabla_origen, :registro_origen_id, :columna_origen,
                :score_metrica, :categoria_metrica, :comentario_texto, :comentario_hash,
                :longitud_caracteres, :longitud_palabras,
                :sentimiento, :confianza, :prob_positivo, :prob_neutral, :prob_negativo,
                :modelo_version, :dispositivo, :tiempo_procesamiento_ms
            )
            ON CONFLICT (tabla_origen, registro_origen_id, columna_origen) DO NOTHING
        """

        with self.engine.connect() as conn:
            conn.execute(text(query), registros)
            conn.commit()

    def generar_resumen(self):
        """Genera resumen de resultados"""
        if self.df_results is None or len(self.df_results) == 0:
            return None

        df_valido = self.df_results[~self.df_results['sentimiento'].isin(['SIN_ANALISIS', 'TEXTO_CORTO', 'ERROR'])]

        resumen = {
            'total': len(self.df_results),
            'analizados': len(df_valido),
            'omitidos': len(self.df_results) - len(df_valido)
        }

        if len(df_valido) > 0:
            dist = df_valido['sentimiento'].value_counts()
            resumen['positivos'] = dist.get('POS', 0)
            resumen['neutrales'] = dist.get('NEU', 0)
            resumen['negativos'] = dist.get('NEG', 0)

            resumen['porc_pos'] = round(resumen['positivos'] / len(df_valido) * 100, 2)
            resumen['porc_neu'] = round(resumen['neutrales'] / len(df_valido) * 100, 2)
            resumen['porc_neg'] = round(resumen['negativos'] / len(df_valido) * 100, 2)

            resumen['confianza_promedio'] = round(df_valido['confianza'].mean(), 4)

        return resumen


# ======================================================================================
# MAIN
# ======================================================================================

def main():
    """Función principal"""
    # Encoding UTF-8 para Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')

    parser = argparse.ArgumentParser(description='Análisis de Sentimientos NPS/CSAT con Ollama')
    parser.add_argument('--limit', type=int, default=1000,
                       help='Comentarios a procesar (default: 1000, 0=todos)')
    parser.add_argument('--sin-limite', action='store_true',
                       help='Procesar TODOS los pendientes')
    parser.add_argument('--fecha-desde', type=str, help='Fecha inicial (YYYY-MM-DD)')
    parser.add_argument('--fecha-hasta', type=str, help='Fecha final (YYYY-MM-DD)')

    args = parser.parse_args()
    if args.sin_limite:
        args.limit = 0

    print("\n" + "=" * 70)
    print("    ANÁLISIS DE SENTIMIENTOS - OLLAMA → PostgreSQL")
    print("=" * 70 + "\n")

    analizador = AnalizadorSentimientos(DB_CONFIG)

    # 1. Conectar BD
    if not analizador.conectar_db():
        return

    # 2. Verificar Ollama
    if not analizador.verificar_ollama():
        logger.error("\nSolución:")
        logger.error("  1. Ejecuta: ollama serve")
        logger.error("  2. Descarga modelo: ollama pull llama3.1:8b")
        return

    # 3. Extraer datos NO ANALIZADOS
    logger.info(f"\n{'='*70}")
    logger.info(f"Buscando comentarios NO ANALIZADOS")
    logger.info(f"Límite: {args.limit if args.limit > 0 else 'sin límite'}")
    logger.info(f"{'='*70}")

    df_completo = analizador.extraer_datos_paralelo(
        limit=args.limit,
        fecha_desde=args.fecha_desde,
        fecha_hasta=args.fecha_hasta
    )

    if len(df_completo) == 0:
        logger.info("\n[OK] No hay comentarios pendientes")
        logger.info("  Todos los comentarios ya fueron analizados")
        return

    # 4. Analizar e insertar
    logger.info(f"\n{'='*70}")
    logger.info("Analizando e insertando...")
    logger.info(f"{'='*70}")

    inicio = datetime.now()
    df_resultados = analizador.procesar_datos(df_completo)
    fin = datetime.now()
    tiempo_total = (fin - inicio).total_seconds()

    # 5. Resumen
    resumen = analizador.generar_resumen()

    print(f"\n{'='*70}")
    print("RESULTADOS")
    print(f"{'='*70}")
    print(f"  Total procesados:   {resumen['total']:,}")
    print(f"  Analizados:         {resumen['analizados']:,}")
    print(f"  Omitidos:           {resumen['omitidos']:,}")
    print()
    print(f"  Positivos:  {resumen.get('positivos', 0):,} ({resumen.get('porc_pos', 0):.2f}%)")
    print(f"  Neutrales:  {resumen.get('neutrales', 0):,} ({resumen.get('porc_neu', 0):.2f}%)")
    print(f"  Negativos:  {resumen.get('negativos', 0):,} ({resumen.get('porc_neg', 0):.2f}%)")
    print()
    print(f"  Confianza promedio: {resumen.get('confianza_promedio', 0):.4f}")
    print()
    print(f"Tiempo: {tiempo_total:.1f}s ({tiempo_total/60:.1f} min)")
    print(f"Velocidad: {len(df_completo)/tiempo_total:.1f} comentarios/seg")
    print(f"{'='*70}\n")

    # 6. Verificar BD
    with analizador.engine.connect() as conn:
        result = conn.execute(text("""
            SELECT canal, tipo_comentario, COUNT(*) as total
            FROM sentimientos_analisis
            GROUP BY canal, tipo_comentario
            ORDER BY canal, tipo_comentario
        """))
        print("Estado de sentimientos_analisis:")
        for row in result:
            print(f"  {row[0]}-{row[1]}: {row[2]:,} análisis")

    print(f"\n[OK] Proceso completado!\n{'='*70}\n")


if __name__ == '__main__':
    main()
