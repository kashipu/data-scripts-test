#!/usr/bin/env python3
"""
======================================================================================
SCRIPT: 1_extractor.py
======================================================================================
PROPÓSITO:
    Extrae datos de encuestas NPS desde archivos Excel originales y los convierte
    a formato Excel para su posterior limpieza e inserción en PostgreSQL.

QUÉ HACE:
    1. Escanea el directorio 'data-cruda/' buscando archivos Excel organizados por mes
    2. Verifica si un archivo ya fue procesado (usando archivo de tracking)
    3. Identifica automáticamente archivos de Banco Móvil (BM) y Banco Virtual (BV)
    4. Lee los archivos Excel completos o limitados según configuración
    5. Guarda los datos extraídos en formato Excel en el directorio 'datos_raw/'
    6. Genera un log individual (.txt) por cada archivo procesado
    7. Actualiza archivo de tracking para evitar reprocesamiento

ESTRUCTURA DE ENTRADA ESPERADA:
    data-cruda/
    ├── Agosto/
    │   ├── Agosto_BM_2025.xlsx  # Archivo Banco Móvil
    │   └── Agosto_BV_2025.xlsx  # Archivo Banco Virtual
    ├── Septiembre/
    │   ├── Septiembre_BM_2025.xlsx
    │   └── Septiembre_BV_2025.xlsx

ARCHIVOS DE SALIDA:
    datos_raw/
    ├── Agosto_BM_2025_extracted_50000.xlsx
    ├── Agosto_BM_2025_extracted_50000.txt  ← LOG individual
    ├── Agosto_BV_2025_extracted_200.xlsx
    ├── Agosto_BV_2025_extracted_200.txt    ← LOG individual
    └── .processed_files.txt                ← TRACKING de archivos procesados

SISTEMA DE TRACKING:
    - Archivo '.processed_files.txt' registra todos los archivos ya procesados
    - Evita reprocesar archivos que ya fueron extraídos exitosamente
    - Se puede forzar reprocesamiento con flag --force

OPCIONES DE USO:
    python 1_extractor.py                              # Procesa todos los archivos nuevos
    python 1_extractor.py --full                       # Procesa archivos completos (sin límite)
    python 1_extractor.py --limit 5000                 # Limita a 5000 registros por archivo
    python 1_extractor.py --file "Agosto_BM_2025.xlsx" # Procesa solo un archivo específico
    python 1_extractor.py --force                      # Fuerza reprocesamiento de todos

CUÁNDO EJECUTAR:
    - Primera vez al configurar el pipeline
    - Cada mes cuando lleguen nuevos archivos Excel con encuestas NPS
    - Después de agregar nuevos datos a 'data-cruda/'

RESULTADO ESPERADO:
    ✅ Extraídos 50,000 registros de Agosto_BM_2025.xlsx → datos_raw/Agosto_BM_2025_extracted_50000.xlsx
    ✅ Log generado: datos_raw/Agosto_BM_2025_extracted_50000.txt
    ⏭️  Omitiendo Septiembre_BM_2025.xlsx (ya procesado anteriormente)

SIGUIENTE PASO:
    Ejecutar: python 2_limpieza.py
======================================================================================
"""

import pandas as pd
import os
import argparse
import logging
from pathlib import Path
from datetime import datetime
import hashlib

# ======================================================================================
# CONFIGURACIÓN
# ======================================================================================

# Directorio donde están los archivos Excel originales
DIRECTORIO_ENTRADA = "data-cruda"

# Directorio donde se guardarán los datos extraídos
DIRECTORIO_SALIDA = "datos_raw"

# Archivo de tracking para evitar reprocesamiento
ARCHIVO_TRACKING = os.path.join(DIRECTORIO_SALIDA, ".processed_files.txt")

# Configuración de logging global
LOG_GENERAL = "extraccion_datos.log"

# ======================================================================================
# CONFIGURACIÓN DE LOGGING
# ======================================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_GENERAL, encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================================================================================
# SISTEMA DE TRACKING DE ARCHIVOS PROCESADOS
# ======================================================================================

def obtener_hash_archivo(ruta_archivo):
    """
    Genera un hash único del archivo para verificar si cambió

    Args:
        ruta_archivo (str): Ruta al archivo

    Returns:
        str: Hash MD5 del archivo
    """
    hash_md5 = hashlib.md5()
    try:
        with open(ruta_archivo, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_md5.update(chunk)
        return hash_md5.hexdigest()
    except Exception as e:
        logger.warning(f"No se pudo calcular hash de {ruta_archivo}: {e}")
        return None


def cargar_archivos_procesados():
    """
    Carga el registro de archivos ya procesados

    Returns:
        dict: Diccionario con {ruta_archivo: hash}
    """
    if not os.path.exists(ARCHIVO_TRACKING):
        return {}

    archivos_procesados = {}
    try:
        with open(ARCHIVO_TRACKING, 'r', encoding='utf-8') as f:
            for linea in f:
                linea = linea.strip()
                if linea and '|' in linea:
                    ruta, hash_archivo = linea.split('|', 1)
                    archivos_procesados[ruta] = hash_archivo
    except Exception as e:
        logger.error(f"Error leyendo archivo de tracking: {e}")

    return archivos_procesados


def registrar_archivo_procesado(ruta_archivo, hash_archivo):
    """
    Registra un archivo como procesado en el tracking

    Args:
        ruta_archivo (str): Ruta del archivo procesado
        hash_archivo (str): Hash del archivo
    """
    try:
        # Crear directorio si no existe
        Path(DIRECTORIO_SALIDA).mkdir(exist_ok=True)

        with open(ARCHIVO_TRACKING, 'a', encoding='utf-8') as f:
            f.write(f"{ruta_archivo}|{hash_archivo}\n")

        logger.info(f"📝 Archivo registrado en tracking: {os.path.basename(ruta_archivo)}")
    except Exception as e:
        logger.error(f"Error registrando archivo en tracking: {e}")


def archivo_ya_procesado(ruta_archivo, archivos_procesados):
    """
    Verifica si un archivo ya fue procesado

    Args:
        ruta_archivo (str): Ruta del archivo a verificar
        archivos_procesados (dict): Diccionario de archivos procesados

    Returns:
        bool: True si ya fue procesado y no cambió, False en caso contrario
    """
    if ruta_archivo not in archivos_procesados:
        return False

    # Verificar si el archivo cambió (comparando hash)
    hash_actual = obtener_hash_archivo(ruta_archivo)
    hash_registrado = archivos_procesados.get(ruta_archivo)

    if hash_actual == hash_registrado:
        return True
    else:
        logger.info(f"⚠️  Archivo modificado detectado: {os.path.basename(ruta_archivo)}")
        return False


# ======================================================================================
# FUNCIONES DE EXTRACCIÓN
# ======================================================================================

def generar_log_individual(ruta_archivo_salida, info_extraccion):
    """
    Genera un archivo .txt con información detallada de la extracción

    Args:
        ruta_archivo_salida (str): Ruta del archivo Excel de salida
        info_extraccion (dict): Diccionario con información de la extracción
    """
    ruta_log = ruta_archivo_salida.replace('.xlsx', '.txt')

    try:
        with open(ruta_log, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("LOG DE EXTRACCIÓN - 1_extractor.py\n")
            f.write("="*80 + "\n\n")

            f.write(f"Fecha de extracción: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Archivo original: {info_extraccion.get('archivo_original', 'N/A')}\n")
            f.write(f"Archivo de salida: {os.path.basename(ruta_archivo_salida)}\n")
            f.write(f"Tipo de archivo: {info_extraccion.get('tipo', 'N/A')}\n\n")

            f.write(f"ESTADÍSTICAS:\n")
            f.write(f"  - Total registros en archivo original: {info_extraccion.get('total_original', 0):,}\n")
            f.write(f"  - Registros extraídos: {info_extraccion.get('registros_extraidos', 0):,}\n")
            f.write(f"  - Total columnas: {info_extraccion.get('total_columnas', 0)}\n\n")

            if info_extraccion.get('columnas_importantes'):
                f.write(f"COLUMNAS CLAVE DETECTADAS:\n")
                for col in info_extraccion['columnas_importantes']:
                    f.write(f"  • {col}\n")
                f.write("\n")

            if info_extraccion.get('advertencias'):
                f.write(f"ADVERTENCIAS:\n")
                for adv in info_extraccion['advertencias']:
                    f.write(f"  ⚠️  {adv}\n")
                f.write("\n")

            f.write(f"ESTADO: {'✅ Exitoso' if info_extraccion.get('exitoso') else '❌ Con errores'}\n")
            f.write("="*80 + "\n")

        logger.info(f"📄 Log individual generado: {os.path.basename(ruta_log)}")

    except Exception as e:
        logger.error(f"Error generando log individual: {e}")


def extraer_datos(ruta_archivo, max_registros=None, directorio_salida=DIRECTORIO_SALIDA):
    """
    Extrae datos de un archivo Excel y los guarda en formato Excel para procesamiento

    Args:
        ruta_archivo (str): Ruta completa al archivo Excel de entrada
        max_registros (int): Número máximo de registros a extraer (None = todos)
        directorio_salida (str): Carpeta donde guardar los datos extraídos

    Returns:
        tuple: (ruta_archivo_salida, cantidad_registros, info_extraccion) o (None, 0, {}) si hay error
    """
    info_extraccion = {
        'archivo_original': os.path.basename(ruta_archivo),
        'exitoso': False,
        'advertencias': []
    }

    print(f"\n📂 Procesando: {ruta_archivo}")
    logger.info(f"Iniciando extracción: {ruta_archivo}")

    try:
        # Leer archivo Excel completo
        print("   ⏳ Leyendo archivo Excel...")
        df_completo = pd.read_excel(ruta_archivo)
        total_filas = len(df_completo)

        info_extraccion['total_original'] = total_filas
        info_extraccion['total_columnas'] = len(df_completo.columns)

        print(f"   📊 Total de registros en archivo: {total_filas:,}")
        print(f"   📋 Columnas disponibles: {len(df_completo.columns)}")

        # Decidir cuántos registros extraer
        if max_registros is None or max_registros == 0:
            print(f"   ℹ️  Extrayendo TODOS los registros ({total_filas:,})")
            datos_extraidos = df_completo
        elif total_filas <= max_registros:
            print(f"   ℹ️  Archivo tiene {total_filas:,} registros, extrayendo todos")
            datos_extraidos = df_completo
        else:
            print(f"   ⚠️  Limitando extracción a {max_registros:,} registros")
            datos_extraidos = df_completo.head(max_registros)
            info_extraccion['advertencias'].append(f"Archivo limitado a {max_registros:,} registros")

        info_extraccion['registros_extraidos'] = len(datos_extraidos)

        # Crear directorio de salida si no existe
        Path(directorio_salida).mkdir(exist_ok=True)

        # Generar nombre de archivo de salida
        nombre_base = Path(ruta_archivo).stem
        archivo_salida = Path(directorio_salida) / f"{nombre_base}_extracted_{len(datos_extraidos)}.xlsx"

        # Guardar datos extraídos
        print(f"   💾 Guardando datos extraídos...")
        datos_extraidos.to_excel(archivo_salida, index=False)

        print(f"   ✅ Datos guardados: {archivo_salida}")
        print(f"   📈 Registros extraídos: {len(datos_extraidos):,}")

        # Identificar y mostrar columnas importantes
        columnas_importantes = []
        for col in datos_extraidos.columns:
            if any(palabra in col.lower() for palabra in ['answer', 'nps', 'score', 'timestamp', 'date', 'recomien']):
                columnas_importantes.append(col)

        info_extraccion['columnas_importantes'] = columnas_importantes

        if columnas_importantes:
            print(f"\n   📊 COLUMNAS CLAVE DETECTADAS:")
            for col in columnas_importantes[:5]:  # Mostrar máximo 5
                print(f"      • {col}")

        # Detectar problemas potenciales
        if 'answers' in datos_extraidos.columns:
            # Verificar si hay JSON malformado (específico de BM)
            muestra_answers = datos_extraidos['answers'].dropna().head(3)
            for answer in muestra_answers:
                if isinstance(answer, str) and 'Ã' in answer:
                    info_extraccion['advertencias'].append("Encoding UTF-8 malformado detectado en columna 'answers'")
                    break

        info_extraccion['exitoso'] = True
        info_extraccion['tipo'] = 'BM' if '_bm_' in nombre_base.lower() or 'bm_' in nombre_base.lower() else 'BV'

        # Generar log individual
        generar_log_individual(str(archivo_salida), info_extraccion)

        logger.info(f"Extracción exitosa: {archivo_salida} ({len(datos_extraidos):,} registros)")

        return archivo_salida, len(datos_extraidos), info_extraccion

    except Exception as e:
        print(f"   ❌ Error procesando {ruta_archivo}: {str(e)}")
        logger.error(f"Error en extracción de {ruta_archivo}: {e}")
        info_extraccion['advertencias'].append(f"Error: {str(e)}")
        return None, 0, info_extraccion


def buscar_archivos_datos(directorio_base=DIRECTORIO_ENTRADA, archivo_especifico=None):
    """
    Escanea el directorio base y encuentra todos los archivos Excel organizados por mes

    Args:
        directorio_base (str): Ruta al directorio que contiene las carpetas de meses
        archivo_especifico (str): Nombre de archivo específico a procesar (opcional)

    Returns:
        dict: Diccionario con estructura {mes: {'bm': ruta, 'bv': ruta}}
    """
    archivos_por_mes = {}

    if not os.path.exists(directorio_base):
        logger.error(f"Directorio '{directorio_base}' no encontrado")
        print(f"❌ Directorio '{directorio_base}' no encontrado")
        print(f"   💡 Crea el directorio y organiza los archivos por mes")
        return archivos_por_mes

    print(f"\n🔍 Escaneando directorio: {directorio_base}")
    logger.info(f"Escaneando directorio: {directorio_base}")

    # Escanear subdirectorios (cada uno representa un mes)
    for carpeta_mes in os.listdir(directorio_base):
        ruta_mes = os.path.join(directorio_base, carpeta_mes)

        if os.path.isdir(ruta_mes):
            print(f"\n📁 Escaneando mes: {carpeta_mes}")
            archivos_por_mes[carpeta_mes] = {}

            # Buscar archivos Excel en la carpeta del mes
            for archivo in os.listdir(ruta_mes):
                if archivo.endswith(('.xlsx', '.xls')):
                    # Si se especificó un archivo, solo procesar ese
                    if archivo_especifico and archivo != archivo_especifico:
                        continue

                    ruta_archivo = os.path.join(ruta_mes, archivo)

                    # Identificar tipo de archivo (BM o BV)
                    if '_BM_' in archivo or 'BM_' in archivo or '_bm_' in archivo.lower():
                        archivos_por_mes[carpeta_mes]['bm'] = ruta_archivo
                        print(f"   ✅ Banco Móvil (BM): {archivo}")
                        logger.info(f"Encontrado BM: {ruta_archivo}")
                    elif '_BV_' in archivo or 'BV_' in archivo or '_bv_' in archivo.lower():
                        archivos_por_mes[carpeta_mes]['bv'] = ruta_archivo
                        print(f"   ✅ Banco Virtual (BV): {archivo}")
                        logger.info(f"Encontrado BV: {ruta_archivo}")
                    else:
                        print(f"   ⚠️  Archivo no identificado: {archivo}")
                        logger.warning(f"Archivo sin tipo identificado: {archivo}")

    return archivos_por_mes


# ======================================================================================
# FUNCIÓN PRINCIPAL
# ======================================================================================

def main():
    """
    Función principal que coordina la extracción de datos de todos los meses
    """
    # Parsear argumentos de línea de comandos
    parser = argparse.ArgumentParser(
        description='Extractor de Datos NPS - Pipeline de Producción',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python 1_extractor.py                              # Procesa archivos nuevos
  python 1_extractor.py --full                       # Procesa archivos completos
  python 1_extractor.py --limit 5000                 # Limita a 5000 registros
  python 1_extractor.py --file "Agosto_BM_2025.xlsx" # Solo un archivo
  python 1_extractor.py --force                      # Fuerza reprocesamiento
        """
    )

    parser.add_argument(
        '--full',
        action='store_true',
        help='Procesar archivos completos sin límite de registros'
    )

    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Número máximo de registros a extraer por archivo'
    )

    parser.add_argument(
        '--file',
        type=str,
        default=None,
        help='Nombre específico de archivo a procesar (ej: Agosto_BM_2025.xlsx)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Forzar reprocesamiento de archivos ya procesados'
    )

    args = parser.parse_args()

    # Determinar límite de registros
    if args.full:
        max_registros = None
        modo_extraccion = "COMPLETO (sin límite)"
    elif args.limit:
        max_registros = args.limit
        modo_extraccion = f"LIMITADO a {max_registros:,} registros"
    else:
        max_registros = None
        modo_extraccion = "COMPLETO (sin límite)"

    print("\n" + "="*80)
    print("🚀 EXTRACTOR DE DATOS NPS - PIPELINE DE PRODUCCIÓN")
    print("="*80)
    print(f"\n⚙️  MODO: {modo_extraccion}")

    if args.file:
        print(f"📄 Procesando solo: {args.file}")

    if args.force:
        print(f"⚠️  MODO FORZADO: Se reprocesarán todos los archivos")

    logger.info(f"Iniciando extracción - Modo: {modo_extraccion}")

    # Cargar archivos ya procesados
    archivos_procesados = cargar_archivos_procesados()
    print(f"\n📝 Archivos previamente procesados: {len(archivos_procesados)}")
    logger.info(f"Archivos en tracking: {len(archivos_procesados)}")

    # Buscar archivos organizados por mes
    archivos_por_mes = buscar_archivos_datos(DIRECTORIO_ENTRADA, args.file)

    if not archivos_por_mes:
        print(f"\n❌ No se encontraron archivos en '{DIRECTORIO_ENTRADA}/'")
        print(f"\n💡 ESTRUCTURA ESPERADA:")
        print(f"   {DIRECTORIO_ENTRADA}/")
        print(f"   ├── Agosto/")
        print(f"   │   ├── Agosto_BM_2025.xlsx")
        print(f"   │   └── Agosto_BV_2025.xlsx")
        print(f"   ├── Septiembre/")
        print(f"   │   ├── Septiembre_BM_2025.xlsx")
        print(f"   │   └── Septiembre_BV_2025.xlsx")
        logger.warning("No se encontraron archivos para procesar")
        return

    resultados = []
    omitidos = []
    errores = []

    # Procesar cada mes encontrado
    for mes, archivos in archivos_por_mes.items():
        print(f"\n" + "="*80)
        print(f"📅 PROCESANDO MES: {mes}")
        print("="*80)

        # Procesar archivo de Banco Móvil (BM)
        if 'bm' in archivos:
            ruta_bm = archivos['bm']

            # Verificar si ya fue procesado
            if not args.force and archivo_ya_procesado(ruta_bm, archivos_procesados):
                print(f"\n🏦 Banco Móvil - {mes}")
                print(f"   ⏭️  Omitiendo: {os.path.basename(ruta_bm)} (ya procesado)")
                logger.info(f"Omitido (ya procesado): {ruta_bm}")
                omitidos.append((mes, 'BM', ruta_bm))
            else:
                print(f"\n🏦 Banco Móvil - {mes}")
                archivo_salida, cantidad, info = extraer_datos(ruta_bm, max_registros=max_registros)

                if archivo_salida:
                    resultados.append((mes, 'BM', ruta_bm, archivo_salida, cantidad))

                    # Registrar en tracking
                    hash_archivo = obtener_hash_archivo(ruta_bm)
                    if hash_archivo:
                        registrar_archivo_procesado(ruta_bm, hash_archivo)
                else:
                    errores.append((mes, 'BM', ruta_bm))

        # Procesar archivo de Banco Virtual (BV)
        if 'bv' in archivos:
            ruta_bv = archivos['bv']

            # Verificar si ya fue procesado
            if not args.force and archivo_ya_procesado(ruta_bv, archivos_procesados):
                print(f"\n💻 Banco Virtual - {mes}")
                print(f"   ⏭️  Omitiendo: {os.path.basename(ruta_bv)} (ya procesado)")
                logger.info(f"Omitido (ya procesado): {ruta_bv}")
                omitidos.append((mes, 'BV', ruta_bv))
            else:
                print(f"\n💻 Banco Virtual - {mes}")
                archivo_salida, cantidad, info = extraer_datos(ruta_bv, max_registros=max_registros)

                if archivo_salida:
                    resultados.append((mes, 'BV', ruta_bv, archivo_salida, cantidad))

                    # Registrar en tracking
                    hash_archivo = obtener_hash_archivo(ruta_bv)
                    if hash_archivo:
                        registrar_archivo_procesado(ruta_bv, hash_archivo)
                else:
                    errores.append((mes, 'BV', ruta_bv))

    # Mostrar resumen final
    print("\n" + "="*80)
    print("📊 RESUMEN DE EXTRACCIÓN")
    print("="*80)

    if resultados:
        total_registros = 0
        print(f"\n✅ ARCHIVOS PROCESADOS EXITOSAMENTE ({len(resultados)}):")

        for mes, tipo, original, archivo_salida, cantidad in resultados:
            print(f"\n   {tipo} - {mes}:")
            print(f"      Original: {os.path.basename(original)}")
            print(f"      Extraído: {os.path.basename(archivo_salida)}")
            print(f"      Registros: {cantidad:,}")
            total_registros += cantidad

        print(f"\n📈 TOTAL: {len(resultados)} archivos procesados, {total_registros:,} registros extraídos")
        logger.info(f"Extracción completada: {len(resultados)} archivos, {total_registros:,} registros")

    if omitidos:
        print(f"\n⏭️  ARCHIVOS OMITIDOS (ya procesados): {len(omitidos)}")
        for mes, tipo, original in omitidos:
            print(f"   • {tipo} - {mes}: {os.path.basename(original)}")
        logger.info(f"Archivos omitidos: {len(omitidos)}")

    if errores:
        print(f"\n❌ ARCHIVOS CON ERRORES: {len(errores)}")
        for mes, tipo, original in errores:
            print(f"   • {tipo} - {mes}: {os.path.basename(original)}")
        logger.error(f"Archivos con errores: {len(errores)}")

    if not resultados and not omitidos:
        print("\n❌ No se procesaron archivos")
        print(f"\n💡 Verifica:")
        print(f"   • La estructura de carpetas en '{DIRECTORIO_ENTRADA}/'")
        print(f"   • Que los archivos tengan '_BM_' o '_BV_' en el nombre")
        print(f"   • Que los archivos sean formato Excel (.xlsx o .xls)")
        logger.warning("No se procesaron archivos")
    else:
        print(f"\n🎯 PRÓXIMOS PASOS:")
        print(f"   1. Revisar logs individuales (.txt) en '{DIRECTORIO_SALIDA}/'")
        print(f"   2. python 2_limpieza.py      # Limpiar y transformar datos")
        print(f"   3. python 3_insercion.py     # Insertar en PostgreSQL")
        print(f"   4. python 4_visualizacion.py # Generar dashboard")

        print(f"\n📝 Archivo de tracking actualizado: {ARCHIVO_TRACKING}")
        print(f"   Total de archivos registrados: {len(cargar_archivos_procesados())}")


if __name__ == "__main__":
    main()
