#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
======================================================================================
SCRIPT: 04_insercion.py
======================================================================================
PROPÓSITO:
    Inserta datos limpios de encuestas NPS/CSAT desde archivos Excel en la tabla
    unificada 'respuestas_nps_csat' de PostgreSQL.

QUÉ HACE:
    1. Lee archivos limpios desde 'datos/clean/' (generados por 03_limpieza.py)
    2. Identifica automáticamente canal (BM/BV) y métrica (NPS/CSAT)
    3. Transforma datos al esquema unificado
    4. Inserta en tabla particionada por mes
    5. Previene duplicados con índice único
    6. Genera logs detallados

NUEVA ESTRUCTURA:
    - Tabla única: respuestas_nps_csat (particionada por mes)
    - Categorización y sentimiento se agregan en pasos posteriores (UPDATE)
    - Metad ata mínima almacenada inline

ARCHIVOS DE ENTRADA:
    datos/clean/*_LIMPIO.xlsx

SALIDA:
    - Registros en respuestas_nps_csat
    - Log: insercion_datos.log

SIGUIENTE PASO:
    Ejecutar: python 05_categorizar_motivos.py
======================================================================================
"""

import pandas as pd
import logging
from pathlib import Path
from datetime import datetime
from sqlalchemy import create_engine, text
import sys
import uuid

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

LOG_FILE = "insercion_datos.log"

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

def get_engine():
    """Crea conexión a PostgreSQL"""
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)

def identify_file_type(filename):
    """
    Identifica canal y métrica del archivo
    Returns: (canal, metrica) o None si no se puede identificar
    """
    filename_upper = filename.upper()

    # Identificar canal
    if '_BM_' in filename_upper:
        canal = 'BM'
    elif '_BV_' in filename_upper:
        canal = 'BV'
    else:
        return None

    # BV solo tiene NPS
    if canal == 'BV':
        return ('BV', 'NPS')

    # BM puede tener NPS o CSAT (dependerá de las columnas del archivo)
    return (canal, None)  # Métrica se determinará al leer las columnas

def file_already_processed(engine, filename):
    """Verifica si un archivo ya fue procesado"""
    try:
        with engine.connect() as conn:
            result = conn.execute(
                text("SELECT COUNT(*) FROM respuestas_nps_csat WHERE archivo_origen = :filename"),
                {"filename": filename}
            )
            count = result.fetchone()[0]
            return count > 0
    except Exception as e:
        logger.warning(f"No se pudo verificar archivo: {str(e)}")
        return False

def extract_mes_anio(fecha):
    """Extrae mes_anio en formato YYYY-MM de una fecha"""
    if pd.isna(fecha):
        return None
    if isinstance(fecha, str):
        try:
            fecha = pd.to_datetime(fecha)
        except:
            return None
    return fecha.strftime('%Y-%m')

def categorize_nps_score(score):
    """Categoriza score NPS en Detractor/Neutral/Promotor"""
    if pd.isna(score):
        return None
    score = float(score)
    if score <= 6:
        return 'Detractor'
    elif score <= 8:
        return 'Neutral'
    else:
        return 'Promotor'

def process_bm_nps(df, filename):
    """
    Procesa datos de Banco Móvil - NPS
    Returns: DataFrame preparado para inserción
    """
    logger.info(f"  Procesando como BM-NPS ({len(df)} registros)")

    # Crear record_id ÚNICO usando UUID para garantizar unicidad absoluta
    # Cada registro tendrá un identificador irrepetible incluso entre ejecuciones
    record_ids = ['BM_NPS_' + filename.replace('.xlsx', '').replace(' ', '_').replace('_LIMPIO', '') + '_' + str(idx) + '_' + str(uuid.uuid4())[:8] for idx in df.index]

    # Mapeo de columnas (usando nombres reales del archivo: camelCase)
    data = pd.DataFrame({
        'record_id': record_ids,
        'canal': 'BM',
        'metrica': 'NPS',
        'mes_anio': df['answerDate'].apply(extract_mes_anio),
        'fecha_respuesta': pd.to_datetime(df['answerDate']),
        'fecha_procesamiento': datetime.now(),
        'cliente_id': df.get('custIdentNum'),
        'cliente_tipo': df.get('custIdentType'),
        'score': df['nps_recomendacion_score'],
        'categoria_score': df['nps_recomendacion_score'].apply(categorize_nps_score),
        'motivo_texto': df.get('nps_recomendacion_motivo'),
        'categoria': None,  # Se llenará en paso 5
        'categoria_confianza': None,
        'es_ruido': False,
        'razon_ruido': None,
        'sentimiento': None,  # Se llenará en paso 6
        'sentimiento_confianza': None,
        'feedback_type': df.get('feedbackType'),
        'canal_respuesta': df.get('channel'),
        'dispositivo': None,
        'pais': None,
        'archivo_origen': filename
    })

    return data

def process_bm_csat(df, filename):
    """
    Procesa datos de Banco Móvil - CSAT
    Returns: DataFrame preparado para inserción
    """
    logger.info(f"  Procesando como BM-CSAT ({len(df)} registros)")

    # Crear record_id ÚNICO usando UUID para garantizar unicidad absoluta
    # Cada registro tendrá un identificador irrepetible incluso entre ejecuciones
    record_ids = ['BM_CSAT_' + filename.replace('.xlsx', '').replace(' ', '_').replace('_LIMPIO', '') + '_' + str(idx) + '_' + str(uuid.uuid4())[:8] for idx in df.index]

    # Mapeo de columnas (usando nombres reales del archivo: camelCase)
    data = pd.DataFrame({
        'record_id': record_ids,
        'canal': 'BM',
        'metrica': 'CSAT',
        'mes_anio': df['answerDate'].apply(extract_mes_anio),
        'fecha_respuesta': pd.to_datetime(df['answerDate']),
        'fecha_procesamiento': datetime.now(),
        'cliente_id': df.get('custIdentNum'),
        'cliente_tipo': df.get('custIdentType'),
        'score': df['csat_satisfaccion_score'],
        'categoria_score': None,  # CSAT no tiene categorías Promotor/Detractor
        'motivo_texto': df.get('csat_satisfaccion_motivo'),
        'categoria': None,  # Se llenará en paso 5
        'categoria_confianza': None,
        'es_ruido': False,
        'razon_ruido': None,
        'sentimiento': None,  # Se llenará en paso 6
        'sentimiento_confianza': None,
        'feedback_type': df.get('feedbackType'),
        'canal_respuesta': df.get('channel'),
        'dispositivo': None,
        'pais': None,
        'archivo_origen': filename
    })

    return data

def process_bv_nps(df, filename):
    """
    Procesa datos de Banco Virtual - NPS
    Returns: DataFrame preparado para inserción
    """
    logger.info(f"  Procesando como BV-NPS ({len(df)} registros)")

    # Identificar columna de motivo (puede tener caracteres especiales)
    motivo_col = None
    for col in df.columns:
        if 'motivo' in col.lower() and 'calificaci' in col.lower():
            motivo_col = col
            break

    # Mapeo de columnas
    # Crear record_id ÚNICO usando UUID para garantizar unicidad absoluta
    record_ids = ['BV_NPS_' + filename.replace('.xlsx', '').replace(' ', '_').replace('_LIMPIO', '') + '_' + str(idx) + '_' + str(uuid.uuid4())[:8] for idx in df.index]

    data = pd.DataFrame({
        'record_id': record_ids,
        'canal': 'BV',
        'metrica': 'NPS',
        'mes_anio': df['date_submitted'].apply(extract_mes_anio),
        'fecha_respuesta': pd.to_datetime(df['date_submitted']),
        'fecha_procesamiento': datetime.now(),
        'cliente_id': None,
        'cliente_tipo': None,
        'score': df['nps_score_bv'],
        'categoria_score': df['nps_score_bv'].apply(categorize_nps_score),
        'motivo_texto': df.get(motivo_col) if motivo_col else None,
        'categoria': None,  # Se llenará en paso 5
        'categoria_confianza': None,
        'es_ruido': False,
        'razon_ruido': None,
        'sentimiento': None,  # Se llenará en paso 6
        'sentimiento_confianza': None,
        'feedback_type': None,
        'canal_respuesta': None,
        'dispositivo': df.get('device'),
        'pais': df.get('country'),
        'archivo_origen': filename
    })

    return data

def insert_data(engine, data, filename):
    """
    Inserta datos en respuestas_nps_csat
    Retorna: (registros_insertados, duplicados)
    """
    try:
        # Eliminar registros con fecha o score nulos
        data_clean = data.dropna(subset=['fecha_respuesta', 'score', 'mes_anio'])

        # Filtrar scores inválidos según la métrica
        # NPS: debe estar entre 0 y 10
        # CSAT: debe estar entre 1 y 5
        mask_valid = pd.Series(True, index=data_clean.index)

        # Filtrar NPS inválidos
        nps_mask = data_clean['metrica'] == 'NPS'
        mask_valid[nps_mask] = (data_clean.loc[nps_mask, 'score'] >= 0) & (data_clean.loc[nps_mask, 'score'] <= 10)

        # Filtrar CSAT inválidos
        csat_mask = data_clean['metrica'] == 'CSAT'
        mask_valid[csat_mask] = (data_clean.loc[csat_mask, 'score'] >= 1) & (data_clean.loc[csat_mask, 'score'] <= 5)

        # Aplicar filtro
        invalid_count = (~mask_valid).sum()
        if invalid_count > 0:
            logger.warning(f"  Omitiendo {invalid_count} registros con scores inválidos")

        data_clean = data_clean[mask_valid]

        if len(data_clean) == 0:
            logger.warning(f"  No hay registros válidos para insertar")
            return (0, 0)

        # Insertar datos
        registros_iniciales = len(data_clean)
        data_clean.to_sql(
            'respuestas_nps_csat',
            engine,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )

        logger.info(f"  ✅ Insertados {registros_iniciales} registros")
        return (registros_iniciales, 0)

    except Exception as e:
        error_msg = str(e)
        if 'duplicate key' in error_msg.lower() or 'unique' in error_msg.lower():
            logger.warning(f"  ⚠️  Archivo ya procesado (duplicados detectados)")
            return (0, len(data))
        else:
            logger.error(f"  ❌ Error insertando: {error_msg}")
            raise

def process_file(engine, file_path):
    """
    Procesa un archivo Excel y lo inserta en la BD
    Returns: (canal, metrica, insertados, duplicados)
    """
    filename = file_path.name
    logger.info(f"\n📄 Procesando: {filename}")

    # Verificar si ya fue procesado
    if file_already_processed(engine, filename):
        logger.warning(f"  ⏭️  Archivo ya procesado anteriormente (omitido)")
        return (None, None, 0, len(pd.read_excel(file_path, nrows=1)))

    # Identificar tipo
    file_info = identify_file_type(filename)
    if not file_info:
        logger.error(f"  ❌ No se puede identificar canal del archivo")
        return (None, None, 0, 0)

    canal, metrica = file_info

    # Leer archivo
    try:
        df = pd.read_excel(file_path)
        logger.info(f"  Archivo leído: {len(df)} filas")
    except Exception as e:
        logger.error(f"  ❌ Error leyendo archivo: {str(e)}")
        return (canal, metrica, 0, 0)

    # Procesar según canal y métrica
    results = []

    if canal == 'BM':
        # BM puede tener NPS y/o CSAT
        # Procesar NPS si existe
        if 'nps_recomendacion_score' in df.columns:
            df_nps = df[df['nps_recomendacion_score'].notna()].copy()
            if len(df_nps) > 0:
                data_nps = process_bm_nps(df_nps, filename)
                insertados, duplicados = insert_data(engine, data_nps, filename)
                results.append(('BM', 'NPS', insertados, duplicados))

        # Procesar CSAT si existe
        if 'csat_satisfaccion_score' in df.columns:
            df_csat = df[df['csat_satisfaccion_score'].notna()].copy()
            if len(df_csat) > 0:
                data_csat = process_bm_csat(df_csat, filename)
                insertados, duplicados = insert_data(engine, data_csat, filename)
                results.append(('BM', 'CSAT', insertados, duplicados))

    elif canal == 'BV':
        # BV solo tiene NPS
        if 'nps_score_bv' in df.columns:
            df_nps = df[df['nps_score_bv'].notna()].copy()
            if len(df_nps) > 0:
                data_nps = process_bv_nps(df_nps, filename)
                insertados, duplicados = insert_data(engine, data_nps, filename)
                results.append(('BV', 'NPS', insertados, duplicados))

    # Consolidar resultados
    if not results:
        logger.warning(f"  ⚠️  No se encontraron datos válidos para insertar")
        return (canal, None, 0, 0)

    # Sumar todos los resultados
    total_insertados = sum(r[2] for r in results)
    total_duplicados = sum(r[3] for r in results)

    return (canal, 'MIXED' if len(results) > 1 else results[0][1], total_insertados, total_duplicados)

def main():
    """Función principal"""
    print("=" * 70)
    print("INSERCIÓN DE DATOS NPS/CSAT EN POSTGRESQL - TABLA UNIFICADA")
    print("=" * 70)

    # Conectar a BD
    try:
        engine = get_engine()
        logger.info("✅ Conexión a PostgreSQL exitosa")
    except Exception as e:
        logger.error(f"❌ Error conectando a PostgreSQL: {str(e)}")
        sys.exit(1)

    # Buscar archivos limpios
    data_dir = Path('datos/clean')
    if not data_dir.exists():
        logger.error(f"❌ Directorio 'datos/clean' no encontrado")
        logger.info("💡 Ejecuta primero 03_limpieza.py")
        sys.exit(1)

    files = sorted(data_dir.glob('*_LIMPIO.xlsx'))
    if not files:
        logger.error("❌ No se encontraron archivos *_LIMPIO.xlsx")
        sys.exit(1)

    logger.info(f"📂 Archivos encontrados: {len(files)}")

    # Procesar archivos
    stats = {
        'total_archivos': len(files),
        'procesados': 0,
        'omitidos': 0,
        'insertados': 0,
        'duplicados': 0,
        'errores': 0,
        'por_canal': {'BM': {'NPS': 0, 'CSAT': 0}, 'BV': {'NPS': 0}}
    }

    for file_path in files:
        try:
            canal, metrica, insertados, duplicados = process_file(engine, file_path)

            if insertados > 0:
                stats['procesados'] += 1
                stats['insertados'] += insertados
                if canal and metrica and metrica != 'MIXED':
                    stats['por_canal'][canal][metrica] += insertados
            elif duplicados > 0:
                stats['omitidos'] += 1
                stats['duplicados'] += duplicados
            else:
                stats['errores'] += 1

        except Exception as e:
            logger.error(f"❌ Error procesando {file_path.name}: {str(e)}")
            stats['errores'] += 1

    # Resumen final
    print("\n" + "=" * 70)
    print("RESUMEN DE INSERCION")
    print("=" * 70)
    print(f"Archivos procesados: {stats['procesados']}/{stats['total_archivos']}")
    print(f"Archivos omitidos (duplicados): {stats['omitidos']}")
    print(f"Errores: {stats['errores']}")
    print(f"\nTotal de registros insertados: {stats['insertados']:,}")
    print(f"   - BM NPS: {stats['por_canal']['BM']['NPS']:,}")
    print(f"   - BM CSAT: {stats['por_canal']['BM']['CSAT']:,}")
    print(f"   - BV NPS: {stats['por_canal']['BV']['NPS']:,}")
    print("=" * 70)

    if stats['errores'] == 0 and stats['procesados'] > 0:
        print("\nSIGUIENTE PASO:")
        print("   python 05_categorizar_motivos.py --mode process")
    elif stats['omitidos'] == stats['total_archivos']:
        print("\nTodos los archivos ya fueron procesados anteriormente")
    elif stats['errores'] > 0:
        print("\nRevisar errores en el log antes de continuar")

    logger.info(f"Log guardado en: {LOG_FILE}")

if __name__ == "__main__":
    main()
