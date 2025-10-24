"""
Utilidades modulares para generación de informes NPS/CSAT

Módulos:
- db_queries: Queries SQL reutilizables
- csv_exports: Exportación de archivos CSV
- graficas_plotly: Gráficas interactivas HTML (Plotly)
- graficas_estaticas: Imágenes estáticas PNG (Matplotlib/Seaborn)
- anomalias: Detección de anomalías estadísticas
"""

from pathlib import Path
from sqlalchemy import create_engine

__version__ = '1.0.0'

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

def get_engine():
    """Retorna engine de SQLAlchemy para PostgreSQL"""
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)
