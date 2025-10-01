#!/usr/bin/env python3
"""
Extractor de Muestra de Datos Reales
Toma 1000 registros de cada archivo para testing
"""

import pandas as pd
import os
from pathlib import Path
import random

def extract_sample(file_path, sample_size=300000, output_dir="muestras"):
    """
    Extrae muestra aleatoria de archivo Excel
    
    Args:
        file_path: Ruta al archivo Excel
        sample_size: Número de registros a extraer
        output_dir: Carpeta donde guardar muestras
    """
    
    print(f"📂 Procesando: {file_path}")
    
    try:
        # Lee información básica del archivo
        df_info = pd.read_excel(file_path, nrows=1)
        
        # Lee archivo completo para obtener total de filas
        print("📊 Leyendo archivo completo para contar registros...")
        df_full = pd.read_excel(file_path)
        total_rows = len(df_full)
        
        print(f"📈 Total de registros en archivo: {total_rows:,}")
        print(f"📋 Columnas disponibles: {list(df_full.columns)}")
        
        # Extrae muestra aleatoria
        if total_rows <= sample_size:
            print(f"⚠️  Archivo tiene menos de {sample_size} registros, tomando todos")
            sample_df = df_full
        else:
            print(f"🎲 Extrayendo muestra aleatoria de {sample_size} registros...")
            sample_df = df_full.sample(n=sample_size, random_state=42)
        
        # Crear directorio de salida
        Path(output_dir).mkdir(exist_ok=True)
        
        # Generar nombre de archivo de muestra
        base_name = Path(file_path).stem
        sample_file = Path(output_dir) / f"{base_name}_muestra_{len(sample_df)}.xlsx"
        
        # Guardar muestra
        sample_df.to_excel(sample_file, index=False)
        print(f"✅ Muestra guardada: {sample_file}")
        print(f"📊 Registros en muestra: {len(sample_df):,}")
        
        # Mostrar información de la muestra
        print("\n📋 INFORMACIÓN DE LA MUESTRA:")
        print(f"Forma: {sample_df.shape}")
        print("\nPrimeras 3 filas de columnas importantes:")
        
        # Mostrar columnas relevantes
        important_cols = []
        for col in sample_df.columns:
            if any(keyword in col.lower() for keyword in ['answer', 'nps', 'score', 'timestamp', 'date']):
                important_cols.append(col)
        
        if important_cols:
            print(sample_df[important_cols].head(3))
        else:
            print(sample_df.head(3))
        
        return sample_file, len(sample_df)
        
    except Exception as e:
        print(f"❌ Error procesando {file_path}: {str(e)}")
        return None, 0

def analyze_sample_data(sample_file):
    """Analiza la muestra extraída"""
    print(f"\n🔍 ANÁLISIS DETALLADO: {sample_file}")
    print("=" * 60)
    
    try:
        df = pd.read_excel(sample_file)
        
        print(f"📊 Total registros: {len(df):,}")
        print(f"📊 Total columnas: {len(df.columns)}")
        
        print("\n📋 COLUMNAS DISPONIBLES:")
        for i, col in enumerate(df.columns):
            print(f"  {i+1:2d}. {col}")
        
        # Analizar columna answers si existe
        if 'answers' in df.columns:
            print("\n🔍 ANÁLISIS COLUMNA 'answers':")
            answers_sample = df['answers'].dropna().head(3)
            for i, answer in enumerate(answers_sample):
                print(f"\nEjemplo {i+1}:")
                print(f"  Tipo: {type(answer)}")
                print(f"  Contenido: {str(answer)[:150]}...")
                
                # Intentar detectar problemas
                if isinstance(answer, str):
                    if 'Ã' in answer:
                        print("  ⚠️  PROBLEMA: Encoding UTF-8 detectado")
                    if answer.startswith("[{'"):
                        print("  ⚠️  PROBLEMA: JSON con comillas simples")
                    if answer.startswith('[{"'):
                        print("  ✅ JSON parece correcto")
        
        # Buscar columnas con NPS
        nps_columns = [col for col in df.columns if 'nps' in col.lower() or 'recomien' in col.lower()]
        if nps_columns:
            print(f"\n📈 COLUMNAS NPS ENCONTRADAS: {nps_columns}")
            for col in nps_columns:
                values = df[col].dropna()
                if len(values) > 0:
                    print(f"  {col}: min={values.min()}, max={values.max()}, promedio={values.mean():.1f}")
        
        # Buscar columnas de fecha
        date_columns = [col for col in df.columns if any(word in col.lower() for word in ['date', 'time', 'fecha'])]
        if date_columns:
            print(f"\n📅 COLUMNAS DE FECHA: {date_columns}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error analizando muestra: {str(e)}")
        return False

def main():
    """Función principal"""
    print("🚀 EXTRACTOR DE MUESTRAS - DATOS REALES NPS")
    print("=" * 50)
    
    # Archivos a procesar (ajusta las rutas según tu ubicación)
    files_to_process = [
        "agosto_bm_2025.xlsx",  # Banco Móvil
        "agosto_bv_2025.xlsx"   # Banco Virtual
    ]
    
    results = []
    
    for file_path in files_to_process:
        if os.path.exists(file_path):
            print(f"\n📁 Procesando: {file_path}")
            sample_file, sample_size = extract_sample(file_path, sample_size=999999)
            
            if sample_file:
                results.append((file_path, sample_file, sample_size))
                
                # Analizar muestra
                analyze_sample_data(sample_file)
            
        else:
            print(f"❌ Archivo no encontrado: {file_path}")
            print(f"📂 Directorio actual: {os.getcwd()}")
            print("📋 Archivos en directorio:")
            for f in os.listdir("."):
                if f.endswith(('.xlsx', '.xls')):
                    print(f"   - {f}")
    
    # Resumen final
    print(f"\n{'='*50}")
    print("📊 RESUMEN DE MUESTRAS EXTRAÍDAS:")
    
    if results:
        for original, sample, size in results:
            print(f"✅ {original} → {sample} ({size:,} registros)")
        
        print(f"\n🎯 SIGUIENTE PASO:")
        print("1. Ejecutar script de limpieza en las muestras")
        print("2. Insertar datos limpios en PostgreSQL")
        print("3. Validar calidad de datos")
        print("4. Si todo está bien, procesar archivos completos")
        
    else:
        print("❌ No se procesaron archivos")
        print("💡 Verifica que los archivos Excel estén en el directorio actual")

if __name__ == "__main__":
    main()