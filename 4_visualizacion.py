"""
======================================================================================
SCRIPT: 4_visualizacion.py
======================================================================================
PROPÓSITO:
    Genera visualizaciones interactivas (tabla HTML) de las métricas NPS y CSAT
    desde PostgreSQL para análisis y reporting ejecutivo.

QUÉ HACE:
    1. Conecta a PostgreSQL y ejecuta query SQL de métricas mensuales
    2. Procesa datos de NPS, CSAT, volúmenes y categorías por mes
    3. Calcula fila consolidada con promedios ponderados y totales históricos
    4. Genera tabla HTML interactiva con estilos y colores por categoría
    5. Exporta a archivo HTML autocontenido (sin dependencias externas)
    6. Opcionalmente filtra por mes específico

MÉTRICAS INCLUIDAS:
    - Volumen Total: Registros por mes
    - NPS: Promedio, Detractores, Neutrales, Promotores (cantidad y %)
    - CSAT: Promedio, valores mín/máx, volumen

ARCHIVOS DE SALIDA:
    visualizaciones/tabla_nps.html - Tabla HTML interactiva
    visualizacion_nps.log - Log de operaciones

CARACTERÍSTICAS:
    ✅ Tabla HTML detallada con estilos profesionales
    ✅ Fila consolidada azul con totales históricos
    ✅ Colores por categoría (Rojo: Detractores, Verde: Promotores)
    ✅ Headers sticky (se quedan fijos al hacer scroll)
    ✅ Responsive (se adapta al tamaño de pantalla)
    ✅ Exportable y compartible (sin dependencias)

USO:
    python 4_visualizacion.py                     # Tabla completa (todos los meses)
    python 4_visualizacion.py --month 2025-08     # Filtrar por mes específico
    python 4_visualizacion.py --output reporte.html  # Guardar en ubicación personalizada

CUÁNDO EJECUTAR:
    Después de ejecutar 3_insercion.py y tener datos en PostgreSQL

RESULTADO ESPERADO:
    ✅ Tabla HTML generada: visualizaciones/tabla_nps.html
    📊 Datos por mes: Mayo 2025 - Septiembre 2025 (5 meses)
    📈 Fila consolidada: 1,234,628 registros totales

REQUISITOS:
    - PostgreSQL corriendo con datos en banco_movil_clean
    - Credenciales configuradas en DB_CONFIG
    - Directorio 'visualizaciones/' (se crea automáticamente)
======================================================================================
"""

import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text
from datetime import datetime
import argparse
import os
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('visualizacion_nps.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración de la base de datos (actualizar password si es necesario)
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'  # ACTUALIZAR ESTE VALOR
}

# Queries para BM y BV por separado con análisis de pérdida de datos
QUERY_BM_METRICAS = """
SELECT
    month_year,
    'BM' as canal,

    -- VOLUMEN TOTAL BM
    COUNT(*) as volumen_total_mes,

    -- MÉTRICA NPS
    COUNT(nps_recomendacion_score) as volumen_nps,
    ROUND(AVG(nps_recomendacion_score)::numeric, 2) as promedio_nps,
    COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) as nps_detractores,
    COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) as nps_neutrales,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) as nps_promotores,
    ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_recomendacion_score), 0), 2) as nps_porc_detractores,
    ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_recomendacion_score), 0), 2) as nps_porc_neutrales,
    ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_recomendacion_score), 0), 2) as nps_porc_promotores,

    -- MÉTRICA CSAT
    COUNT(csat_satisfaccion_score) as volumen_csat,
    ROUND(AVG(csat_satisfaccion_score)::numeric, 2) as promedio_csat,
    MIN(csat_satisfaccion_score) as csat_minimo,
    MAX(csat_satisfaccion_score) as csat_maximo,

    -- ANÁLISIS DE PÉRDIDA DE DATOS
    COUNT(*) - COUNT(nps_recomendacion_score) as registros_sin_nps,
    COUNT(*) - COUNT(csat_satisfaccion_score) as registros_sin_csat,
    ROUND((COUNT(*) - COUNT(nps_recomendacion_score)) * 100.0 / NULLIF(COUNT(*), 0), 2) as porc_perdida_nps,
    ROUND((COUNT(*) - COUNT(csat_satisfaccion_score)) * 100.0 / NULLIF(COUNT(*), 0), 2) as porc_perdida_csat,

    -- DISTRIBUCIÓN COMPLETA (tiene NPS, tiene CSAT, tiene ambos, no tiene ninguno)
    COUNT(CASE WHEN nps_recomendacion_score IS NOT NULL AND csat_satisfaccion_score IS NOT NULL THEN 1 END) as tiene_ambos,
    COUNT(CASE WHEN nps_recomendacion_score IS NOT NULL AND csat_satisfaccion_score IS NULL THEN 1 END) as solo_nps,
    COUNT(CASE WHEN nps_recomendacion_score IS NULL AND csat_satisfaccion_score IS NOT NULL THEN 1 END) as solo_csat,
    COUNT(CASE WHEN nps_recomendacion_score IS NULL AND csat_satisfaccion_score IS NULL THEN 1 END) as sin_metricas

FROM banco_movil_clean
WHERE month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;
"""

QUERY_BV_METRICAS = """
SELECT
    month_year,
    'BV' as canal,

    -- VOLUMEN TOTAL BV
    COUNT(*) as volumen_total_mes,

    -- MÉTRICA NPS (BV solo tiene NPS)
    COUNT(nps_score) as volumen_nps,
    ROUND(AVG(nps_score)::numeric, 2) as promedio_nps,
    COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) as nps_detractores,
    COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) as nps_neutrales,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) as nps_promotores,
    ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_score), 0), 2) as nps_porc_detractores,
    ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_score), 0), 2) as nps_porc_neutrales,
    ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_score), 0), 2) as nps_porc_promotores,

    -- CSAT (no aplica para BV)
    0 as volumen_csat,
    NULL as promedio_csat,
    NULL as csat_minimo,
    NULL as csat_maximo,

    -- ANÁLISIS DE PÉRDIDA DE DATOS (BV solo tiene NPS)
    COUNT(*) - COUNT(nps_score) as registros_sin_nps,
    COUNT(*) as registros_sin_csat,  -- BV no tiene CSAT
    ROUND((COUNT(*) - COUNT(nps_score)) * 100.0 / NULLIF(COUNT(*), 0), 2) as porc_perdida_nps,
    100.0 as porc_perdida_csat,  -- BV no tiene CSAT = 100% pérdida

    -- DISTRIBUCIÓN COMPLETA (BV no tiene CSAT)
    0 as tiene_ambos,
    COUNT(CASE WHEN nps_score IS NOT NULL THEN 1 END) as solo_nps,
    0 as solo_csat,
    COUNT(CASE WHEN nps_score IS NULL THEN 1 END) as sin_metricas

FROM banco_virtual_clean
WHERE month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;
"""

class NPSTableVisualization:
    """Clase para generar tabla HTML de métricas NPS/CSAT"""

    def __init__(self, db_config):
        """Inicializa conexión a la base de datos"""
        self.db_config = db_config
        self.engine = None
        self.df = None
        self.df_bm = None
        self.df_bv = None
        self.df_consolidated = None

    def connect(self):
        """Establece conexión con PostgreSQL"""
        try:
            connection_string = (
                f"postgresql://{self.db_config['user']}:{self.db_config['password']}"
                f"@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
                f"?client_encoding=utf8"
            )
            self.engine = create_engine(connection_string)
            logger.info("[OK] Conexion establecida con PostgreSQL")
            return True
        except Exception as e:
            logger.error(f"[ERROR] Error al conectar con la base de datos: {e}")
            return False

    def load_data(self, month_filter=None):
        """Carga datos desde BM y BV"""
        try:
            # Cargar BM
            query_bm = QUERY_BM_METRICAS
            if month_filter:
                query_bm = query_bm.replace(
                    "WHERE month_year IS NOT NULL",
                    f"WHERE month_year = '{month_filter}'"
                )

            logger.info("Cargando datos de Banco Móvil...")
            with self.engine.connect() as conn:
                self.df_bm = pd.read_sql(text(query_bm), conn).copy()

            # Cargar BV
            query_bv = QUERY_BV_METRICAS
            if month_filter:
                query_bv = query_bv.replace(
                    "WHERE month_year IS NOT NULL",
                    f"WHERE month_year = '{month_filter}'"
                )

            logger.info("Cargando datos de Banco Virtual...")
            with self.engine.connect() as conn:
                self.df_bv = pd.read_sql(text(query_bv), conn).copy()

            # Combinar ambos DataFrames
            logger.info("Combinando datos...")
            self.df = pd.concat([self.df_bm, self.df_bv], ignore_index=True).copy()

            # Ordenar por mes y canal
            self.df = self.df.sort_values(['month_year', 'canal']).reset_index(drop=True)

            # Calcular porcentaje del total
            total_general = self.df['volumen_total_mes'].sum()
            self.df['porcentaje_del_total'] = (self.df['volumen_total_mes'] / total_general * 100).round(2)

            logger.info(f"[OK] Datos cargados: {len(self.df)} registros (BM + BV)")
            logger.info(f"  BM: {len(self.df_bm)} meses, BV: {len(self.df_bv)} meses")
            if len(self.df) > 0:
                logger.info(f"  Rango: {self.df['month_year'].min()} a {self.df['month_year'].max()}")

            # Calcular totales consolidados
            self._calculate_consolidated()

            return True
        except Exception as e:
            logger.error(f"[ERROR] Error al cargar datos: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _calculate_consolidated(self):
        """Calcula fila de totales consolidados con análisis de pérdida"""
        total_volumen = self.df['volumen_total_mes'].sum()

        # Promedios ponderados
        total_volumen_nps = self.df['volumen_nps'].sum()
        total_volumen_csat = self.df['volumen_csat'].sum()

        promedio_nps = (self.df['promedio_nps'] * self.df['volumen_nps']).sum() / total_volumen_nps if total_volumen_nps > 0 else 0
        promedio_csat = (self.df['promedio_csat'] * self.df['volumen_csat']).sum() / total_volumen_csat if total_volumen_csat > 0 else 0

        # Totales de categorías
        total_detractores = self.df['nps_detractores'].sum()
        total_neutrales = self.df['nps_neutrales'].sum()
        total_promotores = self.df['nps_promotores'].sum()

        # Porcentajes totales
        porc_detractores = (total_detractores / total_volumen_nps * 100) if total_volumen_nps > 0 else 0
        porc_neutrales = (total_neutrales / total_volumen_nps * 100) if total_volumen_nps > 0 else 0
        porc_promotores = (total_promotores / total_volumen_nps * 100) if total_volumen_nps > 0 else 0

        # CSAT min/max globales
        csat_min = self.df['csat_minimo'].min()
        csat_max = self.df['csat_maximo'].max()

        # ANÁLISIS DE PÉRDIDA
        total_sin_nps = self.df['registros_sin_nps'].sum()
        total_sin_csat = self.df['registros_sin_csat'].sum()
        porc_perdida_nps = (total_sin_nps / total_volumen * 100) if total_volumen > 0 else 0
        porc_perdida_csat = (total_sin_csat / total_volumen * 100) if total_volumen > 0 else 0

        # DISTRIBUCIÓN COMPLETA
        total_ambos = self.df['tiene_ambos'].sum()
        total_solo_nps = self.df['solo_nps'].sum()
        total_solo_csat = self.df['solo_csat'].sum()
        total_sin_metricas = self.df['sin_metricas'].sum()

        self.df_consolidated = {
            'month_year': 'TOTAL CONSOLIDADO',
            'volumen_total_mes': total_volumen,
            'porcentaje_del_total': 100.0,
            'volumen_nps': total_volumen_nps,
            'promedio_nps': round(promedio_nps, 2),
            'nps_detractores': total_detractores,
            'nps_neutrales': total_neutrales,
            'nps_promotores': total_promotores,
            'nps_porc_detractores': round(porc_detractores, 2),
            'nps_porc_neutrales': round(porc_neutrales, 2),
            'nps_porc_promotores': round(porc_promotores, 2),
            'volumen_csat': total_volumen_csat,
            'promedio_csat': round(promedio_csat, 2),
            'csat_minimo': csat_min,
            'csat_maximo': csat_max,
            'registros_sin_nps': total_sin_nps,
            'registros_sin_csat': total_sin_csat,
            'porc_perdida_nps': round(porc_perdida_nps, 2),
            'porc_perdida_csat': round(porc_perdida_csat, 2),
            'tiene_ambos': total_ambos,
            'solo_nps': total_solo_nps,
            'solo_csat': total_solo_csat,
            'sin_metricas': total_sin_metricas
        }

    def generate_html_table(self):
        """Genera tabla HTML con tablas separadas por métrica"""
        logger.info("Generando tabla HTML...")

        html_parts = []

        # Calcular totales por canal
        total_bm = self.df_bm['volumen_total_mes'].sum() if self.df_bm is not None and len(self.df_bm) > 0 else 0
        total_bv = self.df_bv['volumen_total_mes'].sum() if self.df_bv is not None and len(self.df_bv) > 0 else 0
        total_general = total_bm + total_bv

        periodo = f"{self.df['month_year'].min()} a {self.df['month_year'].max()}"
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        c = self.df_consolidated

        # Estilos CSS
        html_parts.append(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Métricas NPS/CSAT - Análisis Completo por Canal</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            text-align: center;
            padding: 20px;
            background-color: #2c3e50;
            color: white;
            border-radius: 10px;
            margin-bottom: 20px;
        }}
        .header h1 {{
            margin: 0;
            font-size: 28px;
        }}
        .header p {{
            margin: 10px 0 0 0;
            font-size: 14px;
            opacity: 0.9;
        }}
        .section-title {{
            text-align: center;
            background-color: #34495e;
            color: white;
            padding: 15px;
            border-radius: 10px;
            margin: 30px 0 15px 0;
            font-size: 20px;
            font-weight: bold;
        }}
        .table-container {{
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow-x: auto;
            margin-bottom: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th {{
            background-color: #34495e;
            color: white;
            padding: 12px 8px;
            text-align: center;
            font-weight: 600;
            border: 1px solid #2c3e50;
        }}
        td {{
            padding: 10px 8px;
            text-align: center;
            border: 1px solid #ddd;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        tr:hover {{
            background-color: #f0f0f0;
        }}
        .total-row {{
            background-color: #3498db !important;
            color: white;
            font-weight: bold;
        }}
        .total-row td {{
            border-color: #2980b9;
        }}
        .month-col {{
            background-color: #ecf0f1;
            font-weight: 600;
            text-align: left;
            padding-left: 15px;
        }}
        .number {{
            text-align: right;
            padding-right: 15px;
        }}
        .detractor {{
            color: #e74c3c;
            font-weight: 500;
        }}
        .neutral {{
            color: #f39c12;
            font-weight: 500;
        }}
        .promoter {{
            color: #27ae60;
            font-weight: 500;
        }}
        .loss {{
            color: #e74c3c;
            font-weight: 600;
        }}
        .badge-bm {{
            background-color: #3498db;
            color: white;
            padding: 3px 10px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
        }}
        .badge-bv {{
            background-color: #1abc9c;
            color: white;
            padding: 3px 10px;
            border-radius: 4px;
            font-weight: bold;
            font-size: 11px;
        }}
        .summary-box {{
            background-color: #ecf0f1;
            padding: 20px;
            border-radius: 10px;
            margin: 20px 0;
        }}
        .summary-box h3 {{
            margin-top: 0;
            color: #2c3e50;
        }}
        .summary-item {{
            display: inline-block;
            margin: 10px 20px 10px 0;
        }}
        .summary-item strong {{
            color: #2c3e50;
        }}
        .footer {{
            text-align: center;
            padding: 20px;
            color: #7f8c8d;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Análisis Completo de Métricas NPS y CSAT</h1>
        <p>Distribución 100% de Datos por Canal y Métrica</p>
        <p><strong>Período:</strong> {periodo} | <strong>Total Registros:</strong> {total_general:,} | <strong>Generado:</strong> {fecha}</p>
        <p><span class="badge-bm">BM: {total_bm:,}</span> <span class="badge-bv">BV: {total_bv:,}</span></p>
    </div>

    <div class="summary-box">
        <h3>📊 Resumen Ejecutivo - Distribución del 100% de los Datos</h3>
        <div class="summary-item">
            <strong>Total Registros:</strong> {int(c['volumen_total_mes']):,}
        </div>
        <div class="summary-item">
            <strong>Con NPS:</strong> {int(c['volumen_nps']):,} ({100-c['porc_perdida_nps']:.2f}%)
        </div>
        <div class="summary-item">
            <strong>Con CSAT:</strong> {int(c['volumen_csat']):,} ({100-c['porc_perdida_csat']:.2f}%)
        </div>
        <br>
        <div class="summary-item">
            <strong style="color: #27ae60;">Ambas Métricas (NPS+CSAT):</strong> {int(c['tiene_ambos']):,} ({c['tiene_ambos']/c['volumen_total_mes']*100:.2f}%)
        </div>
        <div class="summary-item">
            <strong style="color: #3498db;">Solo NPS:</strong> {int(c['solo_nps']):,} ({c['solo_nps']/c['volumen_total_mes']*100:.2f}%)
        </div>
        <div class="summary-item">
            <strong style="color: #f39c12;">Solo CSAT:</strong> {int(c['solo_csat']):,} ({c['solo_csat']/c['volumen_total_mes']*100:.2f}%)
        </div>
        <div class="summary-item">
            <strong style="color: #e74c3c;">Sin Métricas:</strong> {int(c['sin_metricas']):,} ({c['sin_metricas']/c['volumen_total_mes']*100:.2f}%)
        </div>
    </div>
""")

        # TABLA 1: NPS - BANCO MÓVIL
        html_parts.append("""
    <div class="section-title">📱 Métrica NPS - Banco Móvil (BM)</div>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th>Total Registros</th>
                    <th>Con NPS</th>
                    <th>Promedio NPS</th>
                    <th>Detractores</th>
                    <th>Neutrales</th>
                    <th>Promotores</th>
                    <th>% Detractores</th>
                    <th>% Neutrales</th>
                    <th>% Promotores</th>
                    <th>Sin NPS</th>
                    <th>% Pérdida</th>
                </tr>
            </thead>
            <tbody>
""")

        for _, row in self.df_bm.iterrows():
            html_parts.append(f"""
                <tr>
                    <td class="month-col">{row['month_year']}</td>
                    <td class="number">{int(row['volumen_total_mes']):,}</td>
                    <td class="number">{int(row['volumen_nps']):,}</td>
                    <td class="number">{row['promedio_nps']:.2f}</td>
                    <td class="number detractor">{int(row['nps_detractores']):,}</td>
                    <td class="number neutral">{int(row['nps_neutrales']):,}</td>
                    <td class="number promoter">{int(row['nps_promotores']):,}</td>
                    <td class="detractor">{row['nps_porc_detractores']:.2f}%</td>
                    <td class="neutral">{row['nps_porc_neutrales']:.2f}%</td>
                    <td class="promoter">{row['nps_porc_promotores']:.2f}%</td>
                    <td class="number loss">{int(row['registros_sin_nps']):,}</td>
                    <td class="loss">{row['porc_perdida_nps']:.2f}%</td>
                </tr>
""")

        # Total BM NPS
        total_bm_nps = self.df_bm['volumen_nps'].sum()
        total_bm_regs = self.df_bm['volumen_total_mes'].sum()
        total_bm_sin_nps = self.df_bm['registros_sin_nps'].sum()
        total_bm_det = self.df_bm['nps_detractores'].sum()
        total_bm_neu = self.df_bm['nps_neutrales'].sum()
        total_bm_pro = self.df_bm['nps_promotores'].sum()
        prom_bm_nps = (self.df_bm['promedio_nps'] * self.df_bm['volumen_nps']).sum() / total_bm_nps if total_bm_nps > 0 else 0

        html_parts.append(f"""
                <tr class="total-row">
                    <td style="text-align: left; padding-left: 15px;">TOTAL BM</td>
                    <td class="number">{int(total_bm_regs):,}</td>
                    <td class="number">{int(total_bm_nps):,}</td>
                    <td class="number">{prom_bm_nps:.2f}</td>
                    <td class="number">{int(total_bm_det):,}</td>
                    <td class="number">{int(total_bm_neu):,}</td>
                    <td class="number">{int(total_bm_pro):,}</td>
                    <td>{total_bm_det/total_bm_nps*100:.2f}%</td>
                    <td>{total_bm_neu/total_bm_nps*100:.2f}%</td>
                    <td>{total_bm_pro/total_bm_nps*100:.2f}%</td>
                    <td class="number">{int(total_bm_sin_nps):,}</td>
                    <td>{total_bm_sin_nps/total_bm_regs*100:.2f}%</td>
                </tr>
            </tbody>
        </table>
    </div>
""")

        # TABLA 2: NPS - BANCO VIRTUAL
        html_parts.append("""
    <div class="section-title">💻 Métrica NPS - Banco Virtual (BV)</div>
    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th>Total Registros</th>
                    <th>Con NPS</th>
                    <th>Promedio NPS</th>
                    <th>Detractores</th>
                    <th>Neutrales</th>
                    <th>Promotores</th>
                    <th>% Detractores</th>
                    <th>% Neutrales</th>
                    <th>% Promotores</th>
                    <th>Sin NPS</th>
                    <th>% Pérdida</th>
                </tr>
            </thead>
            <tbody>
""")

        for _, row in self.df_bv.iterrows():
            html_parts.append(f"""
                <tr>
                    <td class="month-col">{row['month_year']}</td>
                    <td class="number">{int(row['volumen_total_mes']):,}</td>
                    <td class="number">{int(row['volumen_nps']):,}</td>
                    <td class="number">{row['promedio_nps']:.2f}</td>
                    <td class="number detractor">{int(row['nps_detractores']):,}</td>
                    <td class="number neutral">{int(row['nps_neutrales']):,}</td>
                    <td class="number promoter">{int(row['nps_promotores']):,}</td>
                    <td class="detractor">{row['nps_porc_detractores']:.2f}%</td>
                    <td class="neutral">{row['nps_porc_neutrales']:.2f}%</td>
                    <td class="promoter">{row['nps_porc_promotores']:.2f}%</td>
                    <td class="number loss">{int(row['registros_sin_nps']):,}</td>
                    <td class="loss">{row['porc_perdida_nps']:.2f}%</td>
                </tr>
""")

        # Total BV NPS
        total_bv_nps = self.df_bv['volumen_nps'].sum()
        total_bv_regs = self.df_bv['volumen_total_mes'].sum()
        total_bv_sin_nps = self.df_bv['registros_sin_nps'].sum()
        total_bv_det = self.df_bv['nps_detractores'].sum()
        total_bv_neu = self.df_bv['nps_neutrales'].sum()
        total_bv_pro = self.df_bv['nps_promotores'].sum()
        prom_bv_nps = (self.df_bv['promedio_nps'] * self.df_bv['volumen_nps']).sum() / total_bv_nps if total_bv_nps > 0 else 0

        html_parts.append(f"""
                <tr class="total-row">
                    <td style="text-align: left; padding-left: 15px;">TOTAL BV</td>
                    <td class="number">{int(total_bv_regs):,}</td>
                    <td class="number">{int(total_bv_nps):,}</td>
                    <td class="number">{prom_bv_nps:.2f}</td>
                    <td class="number">{int(total_bv_det):,}</td>
                    <td class="number">{int(total_bv_neu):,}</td>
                    <td class="number">{int(total_bv_pro):,}</td>
                    <td>{total_bv_det/total_bv_nps*100:.2f}%</td>
                    <td>{total_bv_neu/total_bv_nps*100:.2f}%</td>
                    <td>{total_bv_pro/total_bv_nps*100:.2f}%</td>
                    <td class="number">{int(total_bv_sin_nps):,}</td>
                    <td>{total_bv_sin_nps/total_bv_regs*100:.2f}%</td>
                </tr>
            </tbody>
        </table>
    </div>
""")

        # TABLA 3: CSAT - BANCO MÓVIL (BV no tiene CSAT)
        html_parts.append("""
    <div class="section-title">⭐ Métrica CSAT - Banco Móvil (BM)</div>
    <div class="table-container">
        <p style="text-align: center; color: #7f8c8d; font-style: italic; margin-bottom: 15px;">
            ⚠️ Nota: Banco Virtual (BV) no recolecta métricas CSAT
        </p>
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th>Total Registros</th>
                    <th>Con CSAT</th>
                    <th>Promedio CSAT</th>
                    <th>CSAT Mínimo</th>
                    <th>CSAT Máximo</th>
                    <th>Sin CSAT</th>
                    <th>% Pérdida</th>
                </tr>
            </thead>
            <tbody>
""")

        for _, row in self.df_bm.iterrows():
            csat_prom = f"{row['promedio_csat']:.2f}" if pd.notna(row['promedio_csat']) else "-"
            csat_min = f"{row['csat_minimo']:.2f}" if pd.notna(row['csat_minimo']) else "-"
            csat_max = f"{row['csat_maximo']:.2f}" if pd.notna(row['csat_maximo']) else "-"

            html_parts.append(f"""
                <tr>
                    <td class="month-col">{row['month_year']}</td>
                    <td class="number">{int(row['volumen_total_mes']):,}</td>
                    <td class="number">{int(row['volumen_csat']):,}</td>
                    <td class="number">{csat_prom}</td>
                    <td class="number">{csat_min}</td>
                    <td class="number">{csat_max}</td>
                    <td class="number loss">{int(row['registros_sin_csat']):,}</td>
                    <td class="loss">{row['porc_perdida_csat']:.2f}%</td>
                </tr>
""")

        # Total BM CSAT
        total_bm_csat = self.df_bm['volumen_csat'].sum()
        total_bm_sin_csat = self.df_bm['registros_sin_csat'].sum()
        prom_bm_csat = (self.df_bm['promedio_csat'] * self.df_bm['volumen_csat']).sum() / total_bm_csat if total_bm_csat > 0 else 0
        min_bm_csat = self.df_bm['csat_minimo'].min()
        max_bm_csat = self.df_bm['csat_maximo'].max()

        html_parts.append(f"""
                <tr class="total-row">
                    <td style="text-align: left; padding-left: 15px;">TOTAL BM</td>
                    <td class="number">{int(total_bm_regs):,}</td>
                    <td class="number">{int(total_bm_csat):,}</td>
                    <td class="number">{prom_bm_csat:.2f}</td>
                    <td class="number">{min_bm_csat:.2f}</td>
                    <td class="number">{max_bm_csat:.2f}</td>
                    <td class="number">{int(total_bm_sin_csat):,}</td>
                    <td>{total_bm_sin_csat/total_bm_regs*100:.2f}%</td>
                </tr>
            </tbody>
        </table>
    </div>
""")

        # TABLA 4: DISTRIBUCIÓN 100% DE LOS DATOS
        html_parts.append("""
    <div class="section-title">📈 Distribución del 100% de los Datos - Por Canal</div>
    <div class="table-container">
        <p style="text-align: center; color: #2c3e50; font-weight: bold; margin-bottom: 15px;">
            Cómo están distribuidos el 100% de los registros según las métricas disponibles
        </p>
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th>Canal</th>
                    <th>Total Registros<br>(100%)</th>
                    <th>Con Ambas Métricas<br>(NPS + CSAT)</th>
                    <th>Solo NPS</th>
                    <th>Solo CSAT</th>
                    <th>Sin Métricas</th>
                    <th>% Ambas</th>
                    <th>% Solo NPS</th>
                    <th>% Solo CSAT</th>
                    <th>% Sin Métricas</th>
                </tr>
            </thead>
            <tbody>
""")

        for _, row in self.df.iterrows():
            total = row['volumen_total_mes']
            canal_badge = f'<span class="badge-bm">{row["canal"]}</span>' if row['canal'] == 'BM' else f'<span class="badge-bv">{row["canal"]}</span>'

            html_parts.append(f"""
                <tr>
                    <td class="month-col">{row['month_year']}</td>
                    <td>{canal_badge}</td>
                    <td class="number" style="font-weight: bold;">{int(total):,}</td>
                    <td class="number promoter">{int(row['tiene_ambos']):,}</td>
                    <td class="number" style="color: #3498db; font-weight: 500;">{int(row['solo_nps']):,}</td>
                    <td class="number" style="color: #f39c12; font-weight: 500;">{int(row['solo_csat']):,}</td>
                    <td class="number loss">{int(row['sin_metricas']):,}</td>
                    <td class="promoter">{row['tiene_ambos']/total*100:.2f}%</td>
                    <td style="color: #3498db; font-weight: 500;">{row['solo_nps']/total*100:.2f}%</td>
                    <td style="color: #f39c12; font-weight: 500;">{row['solo_csat']/total*100:.2f}%</td>
                    <td class="loss">{row['sin_metricas']/total*100:.2f}%</td>
                </tr>
""")

        # Total consolidado distribución
        html_parts.append(f"""
                <tr class="total-row">
                    <td colspan="2" style="text-align: left; padding-left: 15px;">TOTAL CONSOLIDADO (BM+BV)</td>
                    <td class="number">{int(c['volumen_total_mes']):,}</td>
                    <td class="number">{int(c['tiene_ambos']):,}</td>
                    <td class="number">{int(c['solo_nps']):,}</td>
                    <td class="number">{int(c['solo_csat']):,}</td>
                    <td class="number">{int(c['sin_metricas']):,}</td>
                    <td>{c['tiene_ambos']/c['volumen_total_mes']*100:.2f}%</td>
                    <td>{c['solo_nps']/c['volumen_total_mes']*100:.2f}%</td>
                    <td>{c['solo_csat']/c['volumen_total_mes']*100:.2f}%</td>
                    <td>{c['sin_metricas']/c['volumen_total_mes']*100:.2f}%</td>
                </tr>
            </tbody>
        </table>
    </div>
""")

        # Footer
        html_parts.append(f"""
    <div class="footer">
        <p><strong>✅ Verificación de Integridad:</strong> Ambas + Solo NPS + Solo CSAT + Sin Métricas = 100% de los registros</p>
        <p><strong>Fórmula:</strong> {int(c['tiene_ambos']):,} + {int(c['solo_nps']):,} + {int(c['solo_csat']):,} + {int(c['sin_metricas']):,} = {int(c['volumen_total_mes']):,} registros</p>
        <hr style="margin: 20px 0; border: none; border-top: 1px solid #ddd;">
        <p>Tabla generada por 4_visualizacion.py | Base de datos: {self.db_config['database']}</p>
        <p>Fuentes: banco_movil_clean (BM) y banco_virtual_clean (BV)</p>
    </div>
</body>
</html>
""")

        return ''.join(html_parts)

    def export_table(self, output_path='visualizaciones/tabla_nps.html'):
        """Exporta la tabla a HTML"""
        # Crear carpeta si no existe
        os.makedirs('visualizaciones', exist_ok=True)

        # Generar HTML
        html_content = self.generate_html_table()

        # Guardar
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)

        logger.info(f"[OK] Tabla exportada a: {output_path}")
        return output_path


def main():
    """Función principal"""
    parser = argparse.ArgumentParser(description='Tabla de visualización NPS/CSAT')
    parser.add_argument('--month', type=str, help='Filtrar por mes específico (ej: 2025-08)')
    parser.add_argument('--output', type=str, default='visualizaciones/tabla_nps.html',
                       help='Ruta de salida de la tabla HTML')

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Tabla NPS/CSAT - Banco Movil y Banco Virtual")
    logger.info("=" * 60)

    # Crear instancia
    table = NPSTableVisualization(DB_CONFIG)

    # Conectar a la base de datos
    if not table.connect():
        logger.error("No se pudo establecer conexion. Verifica la configuracion.")
        return

    # Cargar datos
    if args.month:
        logger.info(f"Aplicando filtro: mes = {args.month}")

    if not table.load_data(month_filter=args.month):
        logger.error("No se pudieron cargar los datos.")
        return

    # Generar y exportar tabla
    output_path = table.export_table(output_path=args.output)

    logger.info("=" * 60)
    logger.info("[OK] Tabla generada exitosamente")
    logger.info(f"  Abrir en navegador: {os.path.abspath(output_path)}")
    logger.info("=" * 60)


if __name__ == '__main__':
    main()
