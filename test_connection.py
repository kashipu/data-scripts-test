#!/usr/bin/env python3
"""
HELLO WORLD: Python + PostgreSQL + Datos NPS
Test básico antes de procesar 300k registros
"""

import pandas as pd
import psycopg2
from sqlalchemy import create_engine
import json
import re
from datetime import datetime

# ===========================================
# CONFIGURACIÓN DE CONEXIÓN
# ===========================================

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'username': 'postgres',
    'password': 'postgres'  # ⚠️ CAMBIA ESTO POR TU PASSWORD
}

def test_connection():
    """Test básico de conexión"""
    print("Probando conexión a PostgreSQL...")
    
    try:
        # Test con psycopg2
        conn = psycopg2.connect(
            host=DB_CONFIG['host'],
            database=DB_CONFIG['database'],
            user=DB_CONFIG['username'],
            password=DB_CONFIG['password']
        )
        
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        print(f"✅ Conexión exitosa!")
        print(f"📊 PostgreSQL: {version[:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return False

def test_sqlalchemy():
    """Test con SQLAlchemy para pandas"""
    print("\nProbando SQLAlchemy...")

    try:
        engine = create_engine(
            f"postgresql://{DB_CONFIG['username']}:{DB_CONFIG['password']}"
            f"@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}"
        )

        # Test simple query
        pd.read_sql("SELECT 1 as test", engine)
        print(f"OK - SQLAlchemy funciona!")
        print(f"Conexion establecida con {DB_CONFIG['database']}")

        return engine

    except Exception as e:
        print(f"Error SQLAlchemy: {e}")
        return None

def simulate_nps_cleaning():
    """Simula limpieza de datos NPS como tendremos en datos reales"""
    print("\n🧹 Simulando limpieza de datos NPS...")
    
    # Datos simulados que imitan problemas reales de tus archivos
    fake_json_data = [
        "['questionTitle': 'Teniendo en cuenta tu experiencia con el uso de la Banca mÃ³vil del Banco de BogotÃ¡, Â¿Recomiendas App Banca MÃ³vil a un colega, amigo o familiar?', 'answerValue': 9, 'subQuestionId': 'nps_rate_recomendation', 'questionType': 'rate']",
        "['questionTitle': 'Describe las razones de tu calificaciÃ³n', 'answerValue': 'ExcelenteÂ aplicaciÃ³n', 'subQuestionId': 'nps_text_recomendation', 'questionType': 'text']"
    ]
    
    def fix_encoding(text):
        """Corrige encoding UTF-8"""
        fixes = {
            'Ã³': 'ó', 'Ã¡': 'á', 'Ã©': 'é', 'Ã­': 'í', 'Ãº': 'ú', 'Ã±': 'ñ',
            'Â¿': '¿', 'Â¡': '¡', 'Â': ''
        }
        for wrong, right in fixes.items():
            text = text.replace(wrong, right)
        return text
    
    def fix_json_format(json_text):
        """Convierte comillas simples a dobles"""
        # Reemplaza comillas simples por dobles
        fixed = json_text.replace("'", '"')
        return fixed
    
    print("📝 Datos originales (con problemas):")
    for i, data in enumerate(fake_json_data):
        print(f"  {i+1}: {data[:60]}...")
    
    print("\n🔧 Aplicando limpieza...")
    cleaned_data = []
    for data in fake_json_data:
        # Paso 1: Corregir encoding
        step1 = fix_encoding(data)
        # Paso 2: Corregir JSON
        step2 = fix_json_format(step1)
        
        try:
            # Paso 3: Parsear JSON
            parsed = json.loads(step2)
            cleaned_data.append(parsed)
            print(f"✅ JSON parseado exitosamente")
        except Exception as e:
            print(f" Error parseando: {e}")
    
    print(f"\n✅ Limpieza completada: {len(cleaned_data)} registros limpios")
    return cleaned_data

def test_data_insertion(engine):
    """Test inserción de datos simulados"""
    print("\n Probando inserción de datos...")
    
    # Crear datos de prueba simulando estructura real
    test_data = pd.DataFrame({
        'timestamp': [datetime.now() for _ in range(3)],
        'customer_id': ['CUST001', 'CUST002', 'CUST003'],
        'nps_score': [9, 7, 10],
        'channel': ['mobile', 'mobile', 'web'],
        'q1_title': ['¿Recomiendas la app?', '¿Recomiendas la app?', '¿Recomiendas el sitio?'],
        'q1_value': [9, 7, 10],
        'month_year': ['2024-08', '2024-08', '2024-08']
    })
    
    try:
        # Inserta en PostgreSQL
        test_data.to_sql(
            'test_nps_data', 
            engine, 
            if_exists='replace',
            index=False
        )
        print("✅ Datos insertados exitosamente!")
        
        # Verifica inserción
        verify_df = pd.read_sql("SELECT * FROM test_nps_data", engine)
        print(f"📊 Verificación: {len(verify_df)} registros en BD")
        
        # Calcula NPS
        nps_calc = pd.read_sql("""
            SELECT 
                channel,
                AVG(nps_score) as avg_nps,
                COUNT(*) as total,
                COUNT(CASE WHEN nps_score >= 9 THEN 1 END) as promoters,
                COUNT(CASE WHEN nps_score <= 6 THEN 1 END) as detractors
            FROM test_nps_data 
            GROUP BY channel
        """, engine)
        
        print("\n📈 Análisis NPS por canal:")
        print(nps_calc)
        
        return True
        
    except Exception as e:
        print(f"❌ Error insertando datos: {e}")
        return False

def main():
    """Función principal - Hello World completo"""
    print("🚀 HELLO WORLD: Python + PostgreSQL + NPS")
    print("=" * 50)
    
    # Test 1: Conexión básica
    if not test_connection():
        print("❌ Falló conexión básica. Verifica configuración.")
        return
    
    # Test 2: SQLAlchemy
    engine = test_sqlalchemy()
    if not engine:
        print("❌ Falló SQLAlchemy. Verifica configuración.")
        return
    
    # Test 3: Simulación de limpieza
    cleaned_data = simulate_nps_cleaning()
    
    # Test 4: Inserción de datos
    if test_data_insertion(engine):
        print("\n🎉 ¡HELLO WORLD COMPLETADO EXITOSAMENTE!")
        print("✅ Todo listo para procesar tus 300k registros reales")
    else:
        print("\n❌ Falló inserción de datos")
    
    print("\n📋 PRÓXIMOS PASOS:")
    print("1. Extraer muestra de 1000 registros de tus archivos Excel")
    print("2. Aplicar limpieza real con el script NPSCleaner")
    print("3. Insertar muestra en PostgreSQL")
    print("4. Validar resultados")
    print("5. Procesar archivos completos (300k registros)")

if __name__ == "__main__":
    main()