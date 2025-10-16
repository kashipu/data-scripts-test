#!/usr/bin/env python3
"""
======================================================================================
SCRIPT: 1_extractor.py
======================================================================================
PROPÓSITO:
    Extrae datos de encuestas NPS desde archivos Excel originales y los convierte
    a formato CSV para su posterior limpieza e inserción en PostgreSQL.

QUÉ HACE:
    1. Escanea el directorio 'data-cruda/' buscando archivos Excel organizados por mes
    2. Identifica automáticamente archivos de Banco Móvil (BM) y Banco Virtual (BV)
    3. Lee los archivos Excel completos (hasta 300,000 registros por defecto)
    4. Guarda los datos extraídos en formato Excel en el directorio 'datos_raw/'
    5. Genera un análisis detallado de cada archivo procesado

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
    ├── Agosto_BV_2025_extracted_200.xlsx
    └── ... (un archivo por cada mes procesado)

CUÁNDO EJECUTAR:
    - Primera vez al configurar el pipeline
    - Cada mes cuando lleguen nuevos archivos Excel con encuestas NPS
    - Después de agregar nuevos datos a 'data-cruda/'

RESULTADO ESPERADO:
    ✅ Extraídos 50,000 registros de Agosto_BM_2025.xlsx → datos_raw/Agosto_BM_2025_extracted_50000.xlsx
    ✅ Extraídos 200 registros de Agosto_BV_2025.xlsx → datos_raw/Agosto_BV_2025_extracted_200.xlsx

SIGUIENTE PASO:
    Ejecutar: python 2_limpieza.py
======================================================================================
"""

import pandas as pd
import os
from pathlib import Path

# ======================================================================================
# CONFIGURACIÓN
# ======================================================================================

# Número máximo de registros a extraer por archivo (300,000 = dataset completo)
MAX_REGISTROS = 300000

# Directorio donde están los archivos Excel originales
DIRECTORIO_ENTRADA = "data-cruda"

# Directorio donde se guardarán los datos extraídos
DIRECTORIO_SALIDA = "datos_raw"

# ======================================================================================
# FUNCIONES DE EXTRACCIÓN
# ======================================================================================

def extraer_datos(ruta_archivo, max_registros=MAX_REGISTROS, directorio_salida=DIRECTORIO_SALIDA):
    """
    Extrae datos de un archivo Excel y los guarda en formato Excel para procesamiento

    Args:
        ruta_archivo (str): Ruta completa al archivo Excel de entrada
        max_registros (int): Número máximo de registros a extraer
        directorio_salida (str): Carpeta donde guardar los datos extraídos

    Returns:
        tuple: (ruta_archivo_salida, cantidad_registros) o (None, 0) si hay error
    """
    print(f"\n📂 Procesando: {ruta_archivo}")

    try:
        # Leer archivo Excel completo
        print("   ⏳ Leyendo archivo Excel...")
        df_completo = pd.read_excel(ruta_archivo)
        total_filas = len(df_completo)

        print(f"   📊 Total de registros en archivo: {total_filas:,}")
        print(f"   📋 Columnas disponibles: {len(df_completo.columns)}")

        # Decidir cuántos registros extraer
        if total_filas <= max_registros:
            print(f"   ℹ️  Archivo tiene {total_filas:,} registros, extrayendo todos")
            datos_extraidos = df_completo
        else:
            print(f"   ⚠️  Limitando extracción a {max_registros:,} registros")
            datos_extraidos = df_completo.head(max_registros)

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

        # Mostrar información básica de los datos
        print(f"\n   📊 INFORMACIÓN DE LOS DATOS:")
        print(f"      Dimensiones: {datos_extraidos.shape[0]:,} filas × {datos_extraidos.shape[1]} columnas")

        # Identificar y mostrar columnas importantes
        columnas_importantes = []
        for col in datos_extraidos.columns:
            if any(palabra in col.lower() for palabra in ['answer', 'nps', 'score', 'timestamp', 'date', 'recomien']):
                columnas_importantes.append(col)

        if columnas_importantes:
            print(f"      Columnas clave detectadas: {len(columnas_importantes)}")
            for col in columnas_importantes[:5]:  # Mostrar máximo 5
                print(f"         • {col}")

        return archivo_salida, len(datos_extraidos)

    except Exception as e:
        print(f"   ❌ Error procesando {ruta_archivo}: {str(e)}")
        return None, 0


def analizar_datos_extraidos(archivo_datos):
    """
    Genera un análisis detallado de los datos extraídos

    Args:
        archivo_datos (str): Ruta al archivo Excel con datos extraídos

    Returns:
        bool: True si el análisis fue exitoso, False en caso contrario
    """
    print(f"\n🔍 ANÁLISIS DETALLADO: {archivo_datos}")
    print("=" * 80)

    try:
        df = pd.read_excel(archivo_datos)

        print(f"📊 Total registros: {len(df):,}")
        print(f"📋 Total columnas: {len(df.columns)}")

        print(f"\n📝 COLUMNAS DISPONIBLES:")
        for i, col in enumerate(df.columns, 1):
            tipo_dato = df[col].dtype
            no_nulos = df[col].notna().sum()
            print(f"   {i:2d}. {col:<40} (Tipo: {tipo_dato}, No nulos: {no_nulos:,})")

        # Analizar columna 'answers' si existe (específico de BM)
        if 'answers' in df.columns:
            print(f"\n🔎 ANÁLISIS COLUMNA 'answers' (Banco Móvil):")
            respuestas_muestra = df['answers'].dropna().head(3)

            for i, respuesta in enumerate(respuestas_muestra, 1):
                print(f"\n   Ejemplo {i}:")
                print(f"      Tipo: {type(respuesta)}")
                print(f"      Contenido (primeros 150 chars): {str(respuesta)[:150]}...")

                # Detectar problemas potenciales
                if isinstance(respuesta, str):
                    if 'Ã' in respuesta:
                        print(f"      ⚠️  ADVERTENCIA: Encoding UTF-8 malformado detectado")
                    if respuesta.startswith("[{'"):
                        print(f"      ⚠️  ADVERTENCIA: JSON con comillas simples (necesita corrección)")
                    if respuesta.startswith('[{"'):
                        print(f"      ✅ JSON con formato correcto")

        # Buscar columnas con información NPS
        columnas_nps = [col for col in df.columns if 'nps' in col.lower() or 'recomien' in col.lower()]
        if columnas_nps:
            print(f"\n📈 COLUMNAS NPS ENCONTRADAS:")
            for col in columnas_nps:
                valores = df[col].dropna()
                if len(valores) > 0:
                    print(f"   • {col}:")
                    print(f"      Min: {valores.min()}, Max: {valores.max()}, Promedio: {valores.mean():.2f}")

        # Buscar columnas de fecha
        columnas_fecha = [col for col in df.columns if any(palabra in col.lower() for palabra in ['date', 'time', 'fecha'])]
        if columnas_fecha:
            print(f"\n📅 COLUMNAS DE FECHA ENCONTRADAS:")
            for col in columnas_fecha:
                print(f"   • {col}")

        return True

    except Exception as e:
        print(f"❌ Error analizando datos: {str(e)}")
        return False


def buscar_archivos_datos(directorio_base=DIRECTORIO_ENTRADA):
    """
    Escanea el directorio base y encuentra todos los archivos Excel organizados por mes

    Args:
        directorio_base (str): Ruta al directorio que contiene las carpetas de meses

    Returns:
        dict: Diccionario con estructura {mes: {'bm': ruta, 'bv': ruta}}
    """
    archivos_por_mes = {}

    if not os.path.exists(directorio_base):
        print(f"❌ Directorio '{directorio_base}' no encontrado")
        print(f"   💡 Crea el directorio y organiza los archivos por mes")
        return archivos_por_mes

    print(f"\n🔍 Escaneando directorio: {directorio_base}")

    # Escanear subdirectorios (cada uno representa un mes)
    for carpeta_mes in os.listdir(directorio_base):
        ruta_mes = os.path.join(directorio_base, carpeta_mes)

        if os.path.isdir(ruta_mes):
            print(f"\n📁 Escaneando mes: {carpeta_mes}")
            archivos_por_mes[carpeta_mes] = {}

            # Buscar archivos Excel en la carpeta del mes
            for archivo in os.listdir(ruta_mes):
                if archivo.endswith(('.xlsx', '.xls')):
                    ruta_archivo = os.path.join(ruta_mes, archivo)

                    # Identificar tipo de archivo (BM o BV)
                    if '_BM_' in archivo or 'BM_' in archivo or '_bm_' in archivo.lower():
                        archivos_por_mes[carpeta_mes]['bm'] = ruta_archivo
                        print(f"   ✅ Banco Móvil (BM): {archivo}")
                    elif '_BV_' in archivo or 'BV_' in archivo or '_bv_' in archivo.lower():
                        archivos_por_mes[carpeta_mes]['bv'] = ruta_archivo
                        print(f"   ✅ Banco Virtual (BV): {archivo}")
                    else:
                        print(f"   ⚠️  Archivo no identificado: {archivo}")

    return archivos_por_mes


# ======================================================================================
# FUNCIÓN PRINCIPAL
# ======================================================================================

def main():
    """
    Función principal que coordina la extracción de datos de todos los meses
    """
    print("\n" + "="*80)
    print("🚀 EXTRACTOR DE DATOS NPS - PIPELINE DE PRODUCCIÓN")
    print("="*80)

    # Buscar archivos organizados por mes
    archivos_por_mes = buscar_archivos_datos(DIRECTORIO_ENTRADA)

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
        return

    resultados = []

    # Procesar cada mes encontrado
    for mes, archivos in archivos_por_mes.items():
        print(f"\n" + "="*80)
        print(f"📅 PROCESANDO MES: {mes}")
        print("="*80)

        # Procesar archivo de Banco Móvil (BM)
        if 'bm' in archivos:
            print(f"\n🏦 Banco Móvil - {mes}")
            archivo_salida, cantidad = extraer_datos(archivos['bm'], max_registros=MAX_REGISTROS)

            if archivo_salida:
                resultados.append((mes, 'BM', archivos['bm'], archivo_salida, cantidad))
                analizar_datos_extraidos(archivo_salida)

        # Procesar archivo de Banco Virtual (BV)
        if 'bv' in archivos:
            print(f"\n💻 Banco Virtual - {mes}")
            archivo_salida, cantidad = extraer_datos(archivos['bv'], max_registros=MAX_REGISTROS)

            if archivo_salida:
                resultados.append((mes, 'BV', archivos['bv'], archivo_salida, cantidad))
                analizar_datos_extraidos(archivo_salida)

    # Mostrar resumen final
    print("\n" + "="*80)
    print("📊 RESUMEN DE EXTRACCIÓN")
    print("="*80)

    if resultados:
        total_registros = 0

        for mes, tipo, original, archivo_salida, cantidad in resultados:
            print(f"✅ {mes} - {tipo}: {os.path.basename(original)}")
            print(f"   → {archivo_salida} ({cantidad:,} registros)")
            total_registros += cantidad

        print(f"\n📈 TOTAL: {len(resultados)} archivos procesados, {total_registros:,} registros extraídos")

        print(f"\n🎯 PRÓXIMOS PASOS:")
        print(f"   1. python 2_limpieza.py      # Limpiar y transformar datos")
        print(f"   2. python 3_insercion.py     # Insertar en PostgreSQL")
        print(f"   3. python 4_visualizacion.py # Generar dashboard")

    else:
        print("❌ No se procesaron archivos")
        print(f"\n💡 Verifica:")
        print(f"   • La estructura de carpetas en '{DIRECTORIO_ENTRADA}/'")
        print(f"   • Que los archivos tengan '_BM_' o '_BV_' en el nombre")
        print(f"   • Que los archivos sean formato Excel (.xlsx o .xls)")


if __name__ == "__main__":
    main()
