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
from sqlalchemy import create_engine
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

# Queries para BM y BV por separado
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
    MAX(csat_satisfaccion_score) as csat_maximo

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
    NULL as csat_maximo

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
            with self.engine.connect() as conn:
                # Cargar BM
                query_bm = QUERY_BM_METRICAS
                if month_filter:
                    query_bm = query_bm.replace(
                        "WHERE month_year IS NOT NULL",
                        f"WHERE month_year = '{month_filter}'"
                    )
                df_bm = pd.read_sql(query_bm, conn)

                # Cargar BV
                query_bv = QUERY_BV_METRICAS
                if month_filter:
                    query_bv = query_bv.replace(
                        "WHERE month_year IS NOT NULL",
                        f"WHERE month_year = '{month_filter}'"
                    )
                df_bv = pd.read_sql(query_bv, conn)

                # Combinar ambos DataFrames
                self.df = pd.concat([df_bm, df_bv], ignore_index=True)

                # Ordenar por mes y canal
                self.df = self.df.sort_values(['month_year', 'canal'])

                # Calcular porcentaje del total
                total_general = self.df['volumen_total_mes'].sum()
                self.df['porcentaje_del_total'] = (self.df['volumen_total_mes'] / total_general * 100).round(2)

                logger.info(f"[OK] Datos cargados: {len(self.df)} registros (BM + BV)")
                logger.info(f"  BM: {len(df_bm)} meses, BV: {len(df_bv)} meses")
                if len(self.df) > 0:
                    logger.info(f"  Rango: {self.df['month_year'].min()} a {self.df['month_year'].max()}")

                # Calcular totales consolidados
                self._calculate_consolidated()

                return True
        except Exception as e:
            logger.error(f"[ERROR] Error al cargar datos: {e}")
            return False

    def _calculate_consolidated(self):
        """Calcula fila de totales consolidados"""
        total_volumen = self.df['volumen_total_mes'].sum()

        # Promedios ponderados
        promedio_nps = (self.df['promedio_nps'] * self.df['volumen_nps']).sum() / self.df['volumen_nps'].sum()
        promedio_csat = (self.df['promedio_csat'] * self.df['volumen_csat']).sum() / self.df['volumen_csat'].sum()

        # Totales de categorías
        total_detractores = self.df['nps_detractores'].sum()
        total_neutrales = self.df['nps_neutrales'].sum()
        total_promotores = self.df['nps_promotores'].sum()
        total_volumen_nps = self.df['volumen_nps'].sum()

        # Porcentajes totales
        porc_detractores = (total_detractores / total_volumen_nps * 100) if total_volumen_nps > 0 else 0
        porc_neutrales = (total_neutrales / total_volumen_nps * 100) if total_volumen_nps > 0 else 0
        porc_promotores = (total_promotores / total_volumen_nps * 100) if total_volumen_nps > 0 else 0

        # CSAT min/max globales
        csat_min = self.df['csat_minimo'].min()
        csat_max = self.df['csat_maximo'].max()

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
            'volumen_csat': self.df['volumen_csat'].sum(),
            'promedio_csat': round(promedio_csat, 2),
            'csat_minimo': csat_min,
            'csat_maximo': csat_max
        }

    def generate_html_table(self):
        """Genera tabla HTML con los datos"""
        logger.info("Generando tabla HTML...")

        # Crear HTML
        html_parts = []

        # Header
        # Generar header HTML con CSS
        periodo = f"{self.df['month_year'].min()} a {self.df['month_year'].max()}"
        total = self.df['volumen_total_mes'].sum()
        fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        html_parts.append(f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Métricas NPS/CSAT - BM y BV</title>
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
        .table-container {{
            background-color: white;
            padding: 20px;
            border-radius: 10px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            overflow-x: auto;
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
            position: sticky;
            top: 0;
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
        .consolidated-row {{
            background-color: #3498db !important;
            color: white;
            font-weight: bold;
        }}
        .consolidated-row td {{
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
        .percentage {{
            color: #27ae60;
            font-weight: 500;
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
        .section-header {{
            background-color: #2c3e50 !important;
            color: white;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
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
        <h1>Métricas NPS/CSAT - Banco Móvil y Banco Virtual</h1>
        <p>Análisis Detallado por Canal y Mes</p>
        <p><strong>Período:</strong> {periodo} |
           <strong>Total Registros:</strong> {total:,} |
           <strong>Generado:</strong> {fecha}</p>
    </div>

    <div class="table-container">
        <table>
            <thead>
                <tr>
                    <th rowspan="2" style="vertical-align: middle;">Mes</th>
                    <th rowspan="2" style="vertical-align: middle;">Canal</th>
                    <th colspan="2" class="section-header">Volumen General</th>
                    <th colspan="8" class="section-header">Métricas NPS</th>
                    <th colspan="4" class="section-header">Métricas CSAT</th>
                </tr>
                <tr>
                    <!-- Volumen General -->
                    <th>Vol. Total</th>
                    <th>% del Total</th>

                    <!-- NPS -->
                    <th>Vol. NPS</th>
                    <th>Promedio NPS</th>
                    <th>Detractores</th>
                    <th>Neutrales</th>
                    <th>Promotores</th>
                    <th>% Detractores</th>
                    <th>% Neutrales</th>
                    <th>% Promotores</th>

                    <!-- CSAT -->
                    <th>Vol. CSAT</th>
                    <th>Promedio CSAT</th>
                    <th>CSAT Mín</th>
                    <th>CSAT Máx</th>
                </tr>
            </thead>
            <tbody>
""")

        # Filas de datos mensuales
        for _, row in self.df.iterrows():
            canal_badge = f'<span style="background-color: #3498db; color: white; padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 11px;">{row["canal"]}</span>' if row['canal'] == 'BM' else f'<span style="background-color: #1abc9c; color: white; padding: 2px 8px; border-radius: 3px; font-weight: bold; font-size: 11px;">{row["canal"]}</span>'

            # Formatear CSAT (puede ser NULL para BV)
            csat_vol = f"{int(row['volumen_csat']):,}" if row['volumen_csat'] > 0 else "-"
            csat_prom = f"{row['promedio_csat']:.2f}" if pd.notna(row['promedio_csat']) else "-"
            csat_min = f"{row['csat_minimo']:.2f}" if pd.notna(row['csat_minimo']) else "-"
            csat_max = f"{row['csat_maximo']:.2f}" if pd.notna(row['csat_maximo']) else "-"

            html_parts.append(f"""
                <tr>
                    <td class="month-col">{row['month_year']}</td>
                    <td style="text-align: center;">{canal_badge}</td>
                    <td class="number">{int(row['volumen_total_mes']):,}</td>
                    <td class="percentage">{row['porcentaje_del_total']:.2f}%</td>

                    <td class="number">{int(row['volumen_nps']):,}</td>
                    <td class="number">{row['promedio_nps']:.2f}</td>
                    <td class="number detractor">{int(row['nps_detractores']):,}</td>
                    <td class="number neutral">{int(row['nps_neutrales']):,}</td>
                    <td class="number promoter">{int(row['nps_promotores']):,}</td>
                    <td class="detractor">{row['nps_porc_detractores']:.2f}%</td>
                    <td class="neutral">{row['nps_porc_neutrales']:.2f}%</td>
                    <td class="promoter">{row['nps_porc_promotores']:.2f}%</td>

                    <td class="number">{csat_vol}</td>
                    <td class="number">{csat_prom}</td>
                    <td class="number">{csat_min}</td>
                    <td class="number">{csat_max}</td>
                </tr>
            """)

        # Fila consolidada
        c = self.df_consolidated
        csat_vol_cons = f"{int(c['volumen_csat']):,}" if c['volumen_csat'] > 0 else "-"
        csat_prom_cons = f"{c['promedio_csat']:.2f}" if pd.notna(c['promedio_csat']) and c['volumen_csat'] > 0 else "-"
        csat_min_cons = f"{c['csat_minimo']:.2f}" if pd.notna(c['csat_minimo']) else "-"
        csat_max_cons = f"{c['csat_maximo']:.2f}" if pd.notna(c['csat_maximo']) else "-"

        html_parts.append(f"""
                <tr class="consolidated-row">
                    <td style="text-align: left; padding-left: 15px;">{c['month_year']}</td>
                    <td style="text-align: center;">BM+BV</td>
                    <td class="number">{int(c['volumen_total_mes']):,}</td>
                    <td>{c['porcentaje_del_total']:.2f}%</td>

                    <td class="number">{int(c['volumen_nps']):,}</td>
                    <td class="number">{c['promedio_nps']:.2f}</td>
                    <td class="number">{int(c['nps_detractores']):,}</td>
                    <td class="number">{int(c['nps_neutrales']):,}</td>
                    <td class="number">{int(c['nps_promotores']):,}</td>
                    <td>{c['nps_porc_detractores']:.2f}%</td>
                    <td>{c['nps_porc_neutrales']:.2f}%</td>
                    <td>{c['nps_porc_promotores']:.2f}%</td>

                    <td class="number">{csat_vol_cons}</td>
                    <td class="number">{csat_prom_cons}</td>
                    <td class="number">{csat_min_cons}</td>
                    <td class="number">{csat_max_cons}</td>
                </tr>
            """)

        # Footer
        html_parts.append(f"""
            </tbody>
        </table>
    </div>

    <div class="footer">
        <p>Tabla generada por visualize_nps.py | Base de datos: {self.db_config['database']}</p>
        <p>Datos extraídos de la tabla banco_movil_clean</p>
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
    logger.info("Tabla NPS/CSAT - Banco Movil")
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
