#!/usr/bin/env python3
"""
======================================================================================
SCRIPT: 2_limpieza.py
======================================================================================
PROPÓSITO:
    Limpia y transforma los datos extraídos de encuestas NPS preparándolos para su
    inserción en PostgreSQL. Maneja las estructuras diferentes de Banco Móvil (BM)
    y Banco Virtual (BV).

QUÉ HACE:
    1. Lee archivos Excel desde 'datos/procesados/' (generados por 1_extractor.py)
    2. Corrige problemas de encoding UTF-8 (Ã³→ó, Ã¡→á, Ã©→é, etc.)
    3. Convierte JSON malformado (comillas simples → comillas dobles)
    4. **BM**: Expande el campo JSON 'answers' en columnas separadas (NPS, CSAT)
    5. **BV**: Normaliza nombres de columnas y limpia URLs/feedback
    6. Categoriza scores NPS (0-6: Detractor, 7-8: Neutral, 9-10: Promotor)
    7. Remueve timezones de fechas para compatibilidad con Excel
    8. Guarda datos limpios en 'datos/clean/' listos para inserción

TRANSFORMACIONES PRINCIPALES:
    - Encoding UTF-8: Corrige caracteres malformados en español
    - JSON de respuestas (BM): Expande métricas anidadas en columnas planas
    - Fechas: Normaliza formatos y remueve timezones
    - NPS: Calcula categorías basadas en score (Detractor/Neutral/Promotor)

ARCHIVOS DE ENTRADA:
    datos/procesados/Agosto_BM_2025_extracted_50000.xlsx
    datos/procesados/Agosto_BV_2025_extracted_200.xlsx

ARCHIVOS DE SALIDA:
    datos/clean/Agosto_BM_2025_extracted_50000_LIMPIO.xlsx
    datos/clean/Agosto_BV_2025_extracted_200_LIMPIO.xlsx

LOG:
    data_cleaning.log - Registro detallado de todas las operaciones

CUÁNDO EJECUTAR:
    Después de ejecutar 1_extractor.py y antes de 3_insercion.py

RESULTADO ESPERADO:
    ✅ BM: Agosto_BM_2025_extracted_50000.xlsx → ...LIMPIO.xlsx (50,000 registros)
    ✅ BV: Agosto_BV_2025_extracted_200.xlsx → ...LIMPIO.xlsx (200 registros)
    📈 ESTADÍSTICAS: encoding_fixed: 1,250, json_fixed: 950, etc.

SIGUIENTE PASO:
    Ejecutar: python 3_insercion.py
======================================================================================
"""

import pandas as pd
import json
import re
import logging
from datetime import datetime
import os
from pathlib import Path
import numpy as np

class DataCleaner:
    """Limpiador especializado para datos NPS"""
    
    def __init__(self):
        self.setup_logging()
        self.stats = {
            'bm_processed': 0,
            'bv_processed': 0,
            'json_fixed': 0,
            'encoding_fixed': 0,
            'timezone_fixed': 0,
            'json_corrupted': 0,
            'errors': 0
        }
        
        # Mapeo de caracteres mal codificados
        self.encoding_fixes = {
            'Ã³': 'ó', 
            'Ã¡': 'á', 
            'Ã©': 'é', 
            'Ã­': 'í', 
            'Ãº': 'ú', 
            'Ã±': 'ñ',
            'Ã': 'Á', 
            'Ã‰': 'É', 
            'Ã': 'Í', 
            'Ã"': 'Ó', 
            'Ãš': 'Ú', 
            'ÃÑ': 'Ñ',
            'Â¿': '¿', 
            'Â¡': '¡', 
            'Â': ''
        }
    
    def setup_logging(self):
        """Configura logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('data_cleaning.log'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def fix_utf8_encoding(self, text):
        """Corrige problemas de encoding UTF-8"""
        if not isinstance(text, str) or pd.isna(text):
            return text
        
        fixed_text = text
        for wrong, right in self.encoding_fixes.items():
            if wrong in fixed_text:
                fixed_text = fixed_text.replace(wrong, right)
                self.stats['encoding_fixed'] += 1
        
        return fixed_text
    
    def fix_json_format(self, json_text):
        """Convierte JSON con comillas simples a formato válido - solución robusta"""
        if not isinstance(json_text, str) or pd.isna(json_text):
            return json_text

        try:
            # Intenta parsear primero (por si ya está bien)
            json.loads(json_text)
            return json_text
        except:
            pass

        try:
            import ast
            fixed = json_text.replace('\\', '')

            # Agrega comas donde faltan - muy específico para evitar tocar valores
            # 1. Después de números antes de comilla
            fixed = re.sub(r"(\d)\s+'", r"\1, '", fixed)
            # 2. Entre comillas solo si el siguiente char es letra (nuevo campo)
            fixed = re.sub(r"'\s+'(\w)", r"', '\1", fixed)
            # 3. Entre objetos
            fixed = re.sub(r"}\s+{", r"}, {", fixed)

            # Ahora ast.literal_eval debería funcionar
            parsed = ast.literal_eval(fixed)
            fixed_json = json.dumps(parsed, ensure_ascii=False)
            self.stats['json_fixed'] += 1
            return fixed_json

        except Exception as e:
            self.stats['json_corrupted'] += 1
            self.logger.warning(f"JSON irrecuperable: {str(e)[:50]}")
            return '[]'
    
    def parse_bm_answers(self, answers_json):
        """Parsea y mapea JSON de respuestas BM a columnas específicas por métrica - versión robusta"""
        if pd.isna(answers_json) or not answers_json:
            return {}
        
        try:
            # Corrige encoding y formato
            fixed_json = self.fix_utf8_encoding(str(answers_json))
            fixed_json = self.fix_json_format(fixed_json)
            
            # Si el JSON se marcó como irrecuperable, devuelve vacío
            if fixed_json == '[]':
                return {}
            
            # Parsea JSON
            answers_list = json.loads(fixed_json)
            
            if not isinstance(answers_list, list):
                return {}
            
            # Mapea respuestas a columnas específicas basado en subQuestionId
            result = {}
            
            for answer in answers_list:
                if isinstance(answer, dict):
                    try:
                        sub_id = answer.get('subQuestionId', '')
                        answer_value = self.fix_utf8_encoding(str(answer.get('answerValue', '')))
                        
                        # Mapeo específico por tipo de métrica
                        if sub_id == 'nps_rate_recomendation':
                            result['nps_recomendacion_score'] = answer_value
                        elif sub_id == 'nps_text_recomendation':
                            result['nps_recomendacion_motivo'] = answer_value
                        elif sub_id == 'csat_rate_satisfied':
                            result['csat_satisfaccion_score'] = answer_value
                        elif sub_id == 'csat_text_satisfied':
                            result['csat_satisfaccion_motivo'] = answer_value
                        else:
                            # Para otros tipos futuros, usar el subQuestionId como nombre
                            result[f"metric_{sub_id}"] = answer_value
                    except Exception as inner_e:
                        # Si falla un elemento individual, continúa con los demás
                        self.logger.warning(f"Error procesando elemento JSON individual: {str(inner_e)}")
                        continue
            
            return result
            
        except Exception as e:
            self.logger.warning(f"Error parseando JSON completo, devolviendo vacío: {str(e)}")
            return {}
    
    def fix_timezone_for_excel(self, dt_series):
        """Remueve timezone para compatibilidad con Excel"""
        if dt_series is None:
            return dt_series
        
        try:
            if pd.api.types.is_datetime64_any_dtype(dt_series):
                if hasattr(dt_series.dtype, 'tz') and dt_series.dtype.tz is not None:
                    dt_series = dt_series.dt.tz_localize(None)
                    self.stats['timezone_fixed'] += 1
            return dt_series
        except:
            return dt_series
    
    def categorize_nps(self, score):
        """Categoriza score NPS"""
        if pd.isna(score):
            return 'Unknown'
        try:
            score = float(score)
            if score <= 6:
                return 'Detractor'
            elif score <= 8:
                return 'Neutral'
            else:
                return 'Promotor'
        except:
            return 'Unknown'
    
    def clean_bm_data(self, df):
        """Limpia datos de BM (Banco Móvil)"""
        self.logger.info(f"Limpiando datos BM: {len(df)} registros")
        
        cleaned = df.copy()
        
        # Corrige encoding en columnas de texto
        text_columns = cleaned.select_dtypes(include=['object']).columns
        for col in text_columns:
            if col != 'answers':  # answers se procesa especialmente
                cleaned[col] = cleaned[col].astype(str).apply(self.fix_utf8_encoding)
        
        # Procesa fechas
        date_columns = ['timestamp', 'answerDate']
        for col in date_columns:
            if col in cleaned.columns:
                cleaned[col] = pd.to_datetime(cleaned[col], errors='coerce')
                cleaned[col] = self.fix_timezone_for_excel(cleaned[col])
        
        # Expande JSON de answers
        if 'answers' in cleaned.columns:
            self.logger.info("Expandiendo JSON de respuestas...")
            
            expanded_data = []
            for idx, answers in enumerate(cleaned['answers']):
                if idx % 100 == 0:
                    self.logger.info(f"  Procesado {idx}/{len(cleaned)}")
                
                parsed = self.parse_bm_answers(answers)
                expanded_data.append(parsed)
            
            # Combina datos expandidos
            expanded_df = pd.DataFrame(expanded_data)
            cleaned = pd.concat([cleaned, expanded_df], axis=1)
        
        # Procesa NPS usando las columnas limpias
        if 'nps_recomendacion_score' in cleaned.columns:
            cleaned['nps_score'] = pd.to_numeric(cleaned['nps_recomendacion_score'], errors='coerce')
            cleaned['nps_score'] = cleaned['nps_score'].clip(0, 10)
            cleaned['nps_category'] = cleaned['nps_score'].apply(self.categorize_nps)
        elif 'nps_score_original' in cleaned.columns:
            # Fallback al NPS original si no hay expandido
            cleaned['nps_score'] = pd.to_numeric(cleaned['nps_score_original'], errors='coerce')
            cleaned['nps_score'] = cleaned['nps_score'].clip(0, 10)
            cleaned['nps_category'] = cleaned['nps_score'].apply(self.categorize_nps)
        
        # Agrega metadatos
        cleaned['cleaned_date'] = datetime.now()
        cleaned['file_type'] = 'BM'
        cleaned['month_year'] = cleaned['timestamp'].dt.strftime('%Y-%m') if 'timestamp' in cleaned.columns else '2024-08'
        
        self.stats['bm_processed'] += len(cleaned)
        self.logger.info(f"BM limpieza completada: {len(cleaned)} registros")
        
        return cleaned
    
    def clean_bv_data(self, df):
        """Limpia datos de BV (Banco Virtual)"""
        self.logger.info(f"Limpiando datos BV: {len(df)} registros")
        
        cleaned = df.copy()
        
        # Corrige encoding en todas las columnas de texto
        text_columns = cleaned.select_dtypes(include=['object']).columns
        for col in text_columns:
            cleaned[col] = cleaned[col].astype(str).apply(self.fix_utf8_encoding)
        
        # Procesa fechas
        if 'Date Submitted' in cleaned.columns:
            cleaned['date_submitted'] = pd.to_datetime(cleaned['Date Submitted'], errors='coerce')
            cleaned['date_submitted'] = self.fix_timezone_for_excel(cleaned['date_submitted'])
            cleaned['month_year'] = cleaned['date_submitted'].dt.strftime('%Y-%m')
        
        # Encuentra y procesa columna NPS
        nps_col = None
        for col in cleaned.columns:
            if 'recomien' in col.lower() and 'probable' in col.lower():
                nps_col = col
                break
        
        if nps_col:
            cleaned['nps_score'] = pd.to_numeric(cleaned[nps_col], errors='coerce')
            cleaned['nps_score'] = cleaned['nps_score'].clip(0, 10)
            cleaned['nps_category'] = cleaned['nps_score'].apply(self.categorize_nps)
        
        # Normaliza URLs
        url_columns = [col for col in cleaned.columns if 'URL' in col or 'url' in col.lower()]
        for col in url_columns:
            if col in cleaned.columns:
                cleaned[col] = cleaned[col].apply(self.clean_url)
        
        # Limpia comentarios de feedback
        feedback_columns = [col for col in cleaned.columns if 'motiv' in col.lower() or 'calific' in col.lower()]
        for col in feedback_columns:
            if col in cleaned.columns:
                cleaned[col] = cleaned[col].apply(self.clean_feedback_text)
        
        # Elimina columnas redundantes y renombra para claridad
        columns_to_drop = ['Number', 'User', 'Hotjar User ID', 'Response URL']
        for col in columns_to_drop:
            if col in cleaned.columns:
                cleaned = cleaned.drop(columns=[col])
        
        # Renombra columnas largas
        nps_col = None
        for col in cleaned.columns:
            if 'recomien' in col.lower() and 'probable' in col.lower():
                nps_col = col
                break
        
        if nps_col:
            cleaned = cleaned.rename(columns={
                nps_col: 'nps_score_bv',
                'Date Submitted': 'date_submitted_original'
            })
        
        # Simplifica nombres de otras columnas
        column_rename = {
            'Country': 'country',
            'Device': 'device', 
            'Browser': 'browser',
            'OS': 'operating_system',
            'Source URL': 'source_url'
        }
        cleaned = cleaned.rename(columns=column_rename)
        
        # Agrega metadatos
        cleaned['cleaned_date'] = datetime.now()
        cleaned['file_type'] = 'BV'
        
        self.stats['bv_processed'] += len(cleaned)
        self.logger.info(f"BV limpieza completada: {len(cleaned)} registros")
        
        return cleaned
    
    def generar_log_limpieza(self, archivo_original, archivo_limpio, entrada, salida, tipo):
        """Genera log compacto de limpieza"""
        try:
            log_file = str(archivo_limpio).replace('.xlsx', '.summary')
            registros_error = self.stats.get('json_corrupted', 0)
            diferencia = entrada - salida

            with open(log_file, 'w', encoding='utf-8') as f:
                f.write("="*70 + "\n")
                f.write("LOG DE LIMPIEZA\n")
                f.write("="*70 + "\n\n")

                f.write(f"Nombre del archivo:      {Path(archivo_original).name}\n")
                f.write(f"Tipo:                    {tipo}\n")
                f.write(f"Fecha:                   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")

                f.write(f"Registros iniciales:     {entrada:,}\n")
                f.write(f"Registros procesados:    {salida:,}\n")
                f.write(f"Registros con errores:   {registros_error:,}\n")
                f.write(f"Diferencia:              {diferencia:,}\n\n")

                # Log de errores
                if registros_error > 0:
                    f.write("-"*70 + "\n")
                    f.write("ERRORES DETECTADOS:\n")
                    f.write("-"*70 + "\n")
                    f.write(f"• JSON irrecuperable: {registros_error} registros\n")
                    f.write("  Razón: Formato de JSON corrupto o no parseable\n")
                    f.write("  Acción: Se omitieron estos registros del output\n")
                else:
                    f.write("✅ No se detectaron errores\n")

                f.write("\n" + "="*70 + "\n")

        except Exception as e:
            self.logger.warning(f"Error generando log: {e}")

    def clean_url(self, url):
        """Limpia URLs"""
        if pd.isna(url) or not url or url == 'nan':
            return ''

        url = str(url).strip()
        if '?' in url:
            return url.split('?')[0]
        return url
    
    def clean_feedback_text(self, text):
        """Limpia texto de feedback"""
        if pd.isna(text) or not text or text == 'nan':
            return ''
        
        text = str(text).strip()
        # Remueve caracteres extraños pero mantiene tildes y ñ
        text = re.sub(r'[^\w\s\.\,\!\?\:\;\-\ñáéíóúÁÉÍÓÚ]', '', text)
        return text
    
    def process_data_file(self, file_path):
        """Procesa un archivo de datos"""
        self.logger.info(f"Procesando datos: {file_path}")

        registros_iniciales = 0
        registros_procesados = 0

        try:
            # Lee archivo
            df = pd.read_excel(file_path)
            registros_iniciales = len(df)

            # Determina tipo por nombre de archivo
            file_name = Path(file_path).name.lower()
            if 'bm' in file_name:
                cleaned_df = self.clean_bm_data(df)
                file_type = 'BM'
            elif 'bv' in file_name:
                cleaned_df = self.clean_bv_data(df)
                file_type = 'BV'
            else:
                raise ValueError(f"No se pudo determinar tipo de archivo: {file_name}")

            registros_procesados = len(cleaned_df)

            # Genera nombre de archivo limpio
            output_dir = Path("datos/clean")
            output_dir.mkdir(parents=True, exist_ok=True)

            base_name = Path(file_path).stem
            clean_file = output_dir / f"{base_name}_LIMPIO.xlsx"

            # Guarda archivo limpio
            cleaned_df.to_excel(clean_file, index=False)

            # Genera log de limpieza
            self.generar_log_limpieza(file_path, clean_file, registros_iniciales, registros_procesados, file_type)

            self.logger.info(f"Datos limpios guardados: {clean_file}")

            return clean_file, cleaned_df, file_type

        except Exception as e:
            self.logger.error(f"Error procesando {file_path}: {str(e)}")
            self.stats['errors'] += 1
            return None, None, None
    
    def analyze_cleaned_data(self, df, file_type):
        """Analiza calidad de los datos limpios"""
        self.logger.info(f"\nANALISIS DE CALIDAD - {file_type}")
        self.logger.info("=" * 40)
        
        # Información básica
        self.logger.info(f"Total registros: {len(df)}")
        self.logger.info(f"Total columnas: {len(df.columns)}")
        
        # Análisis de NPS
        if 'nps_score' in df.columns:
            nps_data = df['nps_score'].dropna()
            if len(nps_data) > 0:
                self.logger.info(f"\nANALISIS NPS:")
                self.logger.info(f"  Registros con NPS: {len(nps_data)}")
                self.logger.info(f"  Promedio NPS: {nps_data.mean():.2f}")
                self.logger.info(f"  Rango: {nps_data.min()} - {nps_data.max()}")
                
                if 'nps_category' in df.columns:
                    categories = df['nps_category'].value_counts()
                    self.logger.info(f"  Categorías: {dict(categories)}")
        
        # Análisis específico por tipo
        if file_type == 'BM':
            # Análisis de métricas expandidas
            metric_cols = [col for col in df.columns if col.startswith('nps_') or col.startswith('csat_')]
            if metric_cols:
                self.logger.info(f"\nMETRICAS EXPANDIDAS:")
                self.logger.info(f"  Columnas creadas: {len(metric_cols)}")
                self.logger.info(f"  Métricas: {metric_cols}")
                
                # Análisis específico de NPS vs CSAT
                if 'nps_recomendacion_score' in df.columns:
                    nps_data = pd.to_numeric(df['nps_recomendacion_score'], errors='coerce').dropna()
                    if len(nps_data) > 0:
                        self.logger.info(f"  NPS Recomendación: promedio {nps_data.mean():.2f}, registros {len(nps_data)}")
                
                if 'csat_satisfaccion_score' in df.columns:
                    csat_data = pd.to_numeric(df['csat_satisfaccion_score'], errors='coerce').dropna()
                    if len(csat_data) > 0:
                        self.logger.info(f"  CSAT Satisfacción: promedio {csat_data.mean():.2f}, registros {len(csat_data)}")
        
        elif file_type == 'BV':
            # Análisis de feedback
            if 'date_submitted' in df.columns:
                dates = df['date_submitted'].dropna()
                if len(dates) > 0:
                    self.logger.info(f"\nFECHAS:")
                    self.logger.info(f"  Rango: {dates.min()} - {dates.max()}")
                    
            # Análisis de dispositivos
            if 'device' in df.columns:
                devices = df['device'].value_counts().head(3)
                self.logger.info(f"\nDISPOSITIVOS MAS COMUNES:")
                for device, count in devices.items():
                    self.logger.info(f"  {device}: {count} registros")
        
        return True

def main():
    """Función principal"""
    print("🚀 LIMPIEZA DE DATOS NPS")
    print("=" * 50)
    
    cleaner = DataCleaner()

    # Busca archivos de datos
    data_dir = Path("datos/procesados")
    if not data_dir.exists():
        print("❌ Carpeta 'datos/procesados' no encontrada")
        print("💡 Ejecuta primero 02_extractor.py")
        return
    
    data_files = list(data_dir.glob("*.xlsx"))
    
    if not data_files:
        print("❌ No se encontraron archivos de datos")
        return
    
    print(f"📂 Archivos de datos encontrados: {len(data_files)}")
    
    results = []
    
    for data_file in data_files:
        print(f"\n📄 Procesando: {data_file.name}")
        
        clean_file, clean_df, file_type = cleaner.process_data_file(data_file)
        
        if clean_file and clean_df is not None:
            # Analiza calidad
            cleaner.analyze_cleaned_data(clean_df, file_type)
            results.append((data_file, clean_file, len(clean_df), file_type))
    
    # Resumen final
    print(f"\n{'='*50}")
    print("📊 RESUMEN DE LIMPIEZA DE DATOS:")
    
    if results:
        for original, cleaned, size, ftype in results:
            print(f"✅ {ftype}: {original.name} → {cleaned.name} ({size:,} registros)")
        
        print(f"\n📈 ESTADÍSTICAS:")
        for key, value in cleaner.stats.items():
            print(f"  {key}: {value:,}")
        
        print(f"\n🎯 SIGUIENTE PASO:")
        print("1. Revisar archivos en carpeta 'datos/clean/'")
        print("2. Insertar datos limpios en PostgreSQL")
        print("3. Validar resultados en base de datos")
        print("4. Si todo está correcto, procesar archivos completos")

    else:
        print("❌ No se procesaron datos exitosamente")

if __name__ == "__main__":
    main()