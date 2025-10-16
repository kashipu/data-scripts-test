#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script: visualizacion_consolidada.py
Genera 5 tablas HTML consolidadas diferenciando BM-NPS, BM-CSAT y BV-NPS
"""

import pandas as pd
from sqlalchemy import create_engine
from datetime import datetime
import sys

if sys.platform == 'win32':
    import codecs
    sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'ignore')

# Configuración de base de datos
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

def conectar_db():
    """Conecta a PostgreSQL"""
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)

def query_bm_nps(engine):
    """Query para BM-NPS"""
    query = """
    SELECT
        month_year AS mes,
        COUNT(*) AS volumen,
        ROUND(AVG(nps_recomendacion_score)::numeric, 2) AS promedio_nps,
        COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) AS detractores,
        ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_detractores,
        COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) AS neutrales,
        ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_neutrales,
        COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) AS promotores,
        ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_promotores
    FROM banco_movil_clean
    WHERE nps_recomendacion_score IS NOT NULL
      AND month_year IS NOT NULL
    GROUP BY month_year
    ORDER BY month_year DESC;
    """
    return pd.read_sql(query, engine)

def query_bm_csat(engine):
    """Query para BM-CSAT"""
    query = """
    SELECT
        month_year AS mes,
        COUNT(*) AS volumen,
        ROUND(AVG(csat_satisfaccion_score)::numeric, 2) AS promedio_csat,
        MIN(csat_satisfaccion_score) AS min_csat,
        MAX(csat_satisfaccion_score) AS max_csat,
        COUNT(CASE WHEN csat_satisfaccion_score <= 2 THEN 1 END) AS insatisfechos,
        ROUND(COUNT(CASE WHEN csat_satisfaccion_score <= 2 THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_insatisfechos,
        COUNT(CASE WHEN csat_satisfaccion_score = 3 THEN 1 END) AS neutrales,
        ROUND(COUNT(CASE WHEN csat_satisfaccion_score = 3 THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_neutrales,
        COUNT(CASE WHEN csat_satisfaccion_score >= 4 THEN 1 END) AS satisfechos,
        ROUND(COUNT(CASE WHEN csat_satisfaccion_score >= 4 THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_satisfechos
    FROM banco_movil_clean
    WHERE csat_satisfaccion_score IS NOT NULL
      AND month_year IS NOT NULL
    GROUP BY month_year
    ORDER BY month_year DESC;
    """
    return pd.read_sql(query, engine)

def query_bv_nps(engine):
    """Query para BV-NPS"""
    query = """
    SELECT
        month_year AS mes,
        COUNT(*) AS volumen,
        ROUND(AVG(nps_score)::numeric, 2) AS promedio_nps,
        COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) AS detractores,
        ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_detractores,
        COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) AS neutrales,
        ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_neutrales,
        COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) AS promotores,
        ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_promotores
    FROM banco_virtual_clean
    WHERE nps_score IS NOT NULL
      AND month_year IS NOT NULL
    GROUP BY month_year
    ORDER BY month_year DESC;
    """
    return pd.read_sql(query, engine)

def query_consolidado(engine):
    """Query consolidado general"""
    query = """
    WITH datos AS (
        SELECT 'BM' as canal, 'NPS' as metrica, COUNT(*) as volumen, AVG(nps_recomendacion_score) as promedio
        FROM banco_movil_clean WHERE nps_recomendacion_score IS NOT NULL
        UNION ALL
        SELECT 'BM' as canal, 'CSAT' as metrica, COUNT(*) as volumen, AVG(csat_satisfaccion_score) as promedio
        FROM banco_movil_clean WHERE csat_satisfaccion_score IS NOT NULL
        UNION ALL
        SELECT 'BV' as canal, 'NPS' as metrica, COUNT(*) as volumen, AVG(nps_score) as promedio
        FROM banco_virtual_clean WHERE nps_score IS NOT NULL
    )
    SELECT
        canal,
        metrica,
        volumen AS total_registros,
        ROUND(promedio::numeric, 2) AS promedio_general,
        ROUND(volumen * 100.0 / SUM(volumen) OVER (), 1) AS porcentaje_del_total
    FROM datos
    ORDER BY canal, metrica;
    """
    return pd.read_sql(query, engine)

def query_evolucion_nps(engine):
    """Query evolución mensual - Solo NPS"""
    query = """
    SELECT
        COALESCE(bm_nps.month_year, bv_nps.month_year) AS mes,
        COALESCE(bm_nps.volumen, 0) AS bm_nps_vol,
        ROUND(COALESCE(bm_nps.promedio, 0)::numeric, 2) AS bm_nps_prom,
        COALESCE(bv_nps.volumen, 0) AS bv_nps_vol,
        ROUND(COALESCE(bv_nps.promedio, 0)::numeric, 2) AS bv_nps_prom,
        COALESCE(bm_nps.volumen, 0) + COALESCE(bv_nps.volumen, 0) AS total_nps
    FROM (
        SELECT month_year, COUNT(*) as volumen, AVG(nps_recomendacion_score) as promedio
        FROM banco_movil_clean WHERE nps_recomendacion_score IS NOT NULL AND month_year IS NOT NULL
        GROUP BY month_year
    ) bm_nps
    FULL OUTER JOIN (
        SELECT month_year, COUNT(*) as volumen, AVG(nps_score) as promedio
        FROM banco_virtual_clean WHERE nps_score IS NOT NULL AND month_year IS NOT NULL
        GROUP BY month_year
    ) bv_nps ON bm_nps.month_year = bv_nps.month_year
    ORDER BY mes DESC;
    """
    df = pd.read_sql(query, engine)

    # Calcular variación porcentual vs mes anterior
    df['variacion_pct'] = df['total_nps'].pct_change(periods=-1) * 100
    df['variacion_pct'] = df['variacion_pct'].round(1)

    return df

def query_evolucion_csat(engine):
    """Query evolución mensual - Solo CSAT"""
    query = """
    SELECT
        month_year AS mes,
        COUNT(*) AS volumen,
        ROUND(AVG(csat_satisfaccion_score)::numeric, 2) AS promedio_csat
    FROM banco_movil_clean
    WHERE csat_satisfaccion_score IS NOT NULL AND month_year IS NOT NULL
    GROUP BY month_year
    ORDER BY mes DESC;
    """
    df = pd.read_sql(query, engine)

    # Calcular variación porcentual vs mes anterior
    df['variacion_pct'] = df['volumen'].pct_change(periods=-1) * 100
    df['variacion_pct'] = df['variacion_pct'].round(1)

    return df

def generar_html(df_bm_nps, df_bm_csat, df_bv_nps, df_consolidado, df_evol_nps, df_evol_csat):
    """Genera HTML con 6 tablas (NPS y CSAT separados)"""

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Reporte Consolidado NPS/CSAT</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2c3e50;
            text-align: center;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #34495e;
            margin-top: 30px;
            padding: 10px;
            background-color: #ecf0f1;
            border-left: 4px solid #3498db;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 3px rgba(0,0,0,0.1);
        }}
        th {{
            background-color: #3498db;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: bold;
        }}
        td {{
            padding: 10px;
            border-bottom: 1px solid #ddd;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .numero {{
            text-align: right;
            font-family: 'Courier New', monospace;
        }}
        .detractor {{ color: #e74c3c; font-weight: bold; }}
        .neutral {{ color: #f39c12; }}
        .promotor {{ color: #27ae60; font-weight: bold; }}
        .footer {{
            text-align: center;
            margin-top: 30px;
            color: #7f8c8d;
            font-size: 12px;
        }}
        .badge {{
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-size: 12px;
            font-weight: bold;
        }}
        .badge-nps {{ background-color: #3498db; color: white; }}
        .badge-csat {{ background-color: #9b59b6; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>REPORTE CONSOLIDADO DE MÉTRICAS NPS Y CSAT</h1>
        <p style="text-align: center; color: #7f8c8d;">
            Generado: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>

        <!-- TABLA 1: BM-NPS -->
        <h2>1. BANCO MÓVIL - NET PROMOTER SCORE (NPS)</h2>
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th>Volumen</th>
                    <th>Promedio NPS</th>
                    <th>Detractores</th>
                    <th>%</th>
                    <th>Neutrales</th>
                    <th>%</th>
                    <th>Promotores</th>
                    <th>%</th>
                </tr>
            </thead>
            <tbody>
"""

    # Llenar tabla BM-NPS
    for _, row in df_bm_nps.iterrows():
        html += f"""
                <tr>
                    <td>{row['mes']}</td>
                    <td class="numero">{int(row['volumen']):,}</td>
                    <td class="numero"><strong>{row['promedio_nps']}</strong></td>
                    <td class="numero detractor">{int(row['detractores']):,}</td>
                    <td class="numero detractor">{row['pct_detractores']}%</td>
                    <td class="numero neutral">{int(row['neutrales']):,}</td>
                    <td class="numero neutral">{row['pct_neutrales']}%</td>
                    <td class="numero promotor">{int(row['promotores']):,}</td>
                    <td class="numero promotor">{row['pct_promotores']}%</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <!-- TABLA 2: BM-CSAT -->
        <h2>2. BANCO MÓVIL - CUSTOMER SATISFACTION (CSAT)</h2>
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th>Volumen</th>
                    <th>Promedio CSAT</th>
                    <th>Rango</th>
                    <th>Insatisfechos (≤2)</th>
                    <th>%</th>
                    <th>Neutrales (3)</th>
                    <th>%</th>
                    <th>Satisfechos (≥4)</th>
                    <th>%</th>
                </tr>
            </thead>
            <tbody>
"""

    # Llenar tabla BM-CSAT
    for _, row in df_bm_csat.iterrows():
        html += f"""
                <tr>
                    <td>{row['mes']}</td>
                    <td class="numero">{int(row['volumen']):,}</td>
                    <td class="numero"><strong>{row['promedio_csat']}</strong></td>
                    <td class="numero">{row['min_csat']} - {row['max_csat']}</td>
                    <td class="numero detractor">{int(row['insatisfechos']):,}</td>
                    <td class="numero detractor">{row['pct_insatisfechos']}%</td>
                    <td class="numero neutral">{int(row['neutrales']):,}</td>
                    <td class="numero neutral">{row['pct_neutrales']}%</td>
                    <td class="numero promotor">{int(row['satisfechos']):,}</td>
                    <td class="numero promotor">{row['pct_satisfechos']}%</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <!-- TABLA 3: BV-NPS -->
        <h2>3. BANCO VIRTUAL - NET PROMOTER SCORE (NPS)</h2>
"""

    if len(df_bv_nps) > 0:
        html += """
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th>Volumen</th>
                    <th>Promedio NPS</th>
                    <th>Detractores</th>
                    <th>%</th>
                    <th>Neutrales</th>
                    <th>%</th>
                    <th>Promotores</th>
                    <th>%</th>
                </tr>
            </thead>
            <tbody>
"""

        for _, row in df_bv_nps.iterrows():
            html += f"""
                <tr>
                    <td>{row['mes']}</td>
                    <td class="numero">{int(row['volumen']):,}</td>
                    <td class="numero"><strong>{row['promedio_nps']}</strong></td>
                    <td class="numero detractor">{int(row['detractores']):,}</td>
                    <td class="numero detractor">{row['pct_detractores']}%</td>
                    <td class="numero neutral">{int(row['neutrales']):,}</td>
                    <td class="numero neutral">{row['pct_neutrales']}%</td>
                    <td class="numero promotor">{int(row['promotores']):,}</td>
                    <td class="numero promotor">{row['pct_promotores']}%</td>
                </tr>
"""

        html += """
            </tbody>
        </table>
"""
    else:
        html += """
        <p style="color: #e74c3c; padding: 20px; background-color: #ffeaa7; border-radius: 5px;">
            Sin datos disponibles para Banco Virtual
        </p>
"""

    html += """
        <!-- TABLA 4: CONSOLIDADO -->
        <h2>4. CONSOLIDADO GENERAL</h2>
        <table>
            <thead>
                <tr>
                    <th>Canal</th>
                    <th>Métrica</th>
                    <th>Total Registros</th>
                    <th>Promedio General</th>
                    <th>% del Total</th>
                </tr>
            </thead>
            <tbody>
"""

    # Llenar tabla consolidado
    for _, row in df_consolidado.iterrows():
        badge_class = 'badge-nps' if row['metrica'] == 'NPS' else 'badge-csat'
        html += f"""
                <tr>
                    <td><strong>{row['canal']}</strong></td>
                    <td><span class="badge {badge_class}">{row['metrica']}</span></td>
                    <td class="numero"><strong>{int(row['total_registros']):,}</strong></td>
                    <td class="numero">{row['promedio_general']}</td>
                    <td class="numero">{row['porcentaje_del_total']}%</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <!-- TABLA 5: EVOLUCIÓN MENSUAL NPS -->
        <h2>5. EVOLUCIÓN MENSUAL - NPS (Banco Móvil + Banco Virtual)</h2>
        <table>
            <thead>
                <tr>
                    <th rowspan="2">Mes</th>
                    <th colspan="2" style="background-color: #3498db;">BM-NPS</th>
                    <th colspan="2" style="background-color: #1abc9c;">BV-NPS</th>
                    <th rowspan="2">Total NPS</th>
                    <th rowspan="2">Variación %</th>
                </tr>
                <tr>
                    <th style="background-color: #5dade2;">Vol</th>
                    <th style="background-color: #5dade2;">Prom</th>
                    <th style="background-color: #76d7c4;">Vol</th>
                    <th style="background-color: #76d7c4;">Prom</th>
                </tr>
            </thead>
            <tbody>
"""

    # Llenar tabla evolución NPS
    for _, row in df_evol_nps.iterrows():
        variacion = row['variacion_pct']
        variacion_color = '#27ae60' if variacion > 0 else '#e74c3c' if variacion < 0 else '#95a5a6'
        variacion_text = f"+{variacion}%" if variacion > 0 else f"{variacion}%" if pd.notna(variacion) else "-"

        html += f"""
                <tr>
                    <td><strong>{row['mes']}</strong></td>
                    <td class="numero">{int(row['bm_nps_vol']):,}</td>
                    <td class="numero">{row['bm_nps_prom']}</td>
                    <td class="numero">{int(row['bv_nps_vol']):,}</td>
                    <td class="numero">{row['bv_nps_prom']}</td>
                    <td class="numero"><strong>{int(row['total_nps']):,}</strong></td>
                    <td class="numero" style="color: {variacion_color}; font-weight: bold;">{variacion_text}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <!-- TABLA 6: EVOLUCIÓN MENSUAL CSAT -->
        <h2>6. EVOLUCIÓN MENSUAL - CSAT (Solo Banco Móvil)</h2>
        <table>
            <thead>
                <tr>
                    <th>Mes</th>
                    <th style="background-color: #9b59b6;">Volumen</th>
                    <th style="background-color: #9b59b6;">Promedio CSAT</th>
                    <th>Variación %</th>
                </tr>
            </thead>
            <tbody>
"""

    # Llenar tabla evolución CSAT
    for _, row in df_evol_csat.iterrows():
        variacion = row['variacion_pct']
        variacion_color = '#27ae60' if variacion > 0 else '#e74c3c' if variacion < 0 else '#95a5a6'
        variacion_text = f"+{variacion}%" if variacion > 0 else f"{variacion}%" if pd.notna(variacion) else "-"

        html += f"""
                <tr>
                    <td><strong>{row['mes']}</strong></td>
                    <td class="numero">{int(row['volumen']):,}</td>
                    <td class="numero">{row['promedio_csat']}</td>
                    <td class="numero" style="color: {variacion_color}; font-weight: bold;">{variacion_text}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>

        <div class="footer">
            <p>Generado por 5_visualizacion.py | Base de datos: nps_analitycs</p>
        </div>
    </div>
</body>
</html>
"""

    return html

def main():
    """Función principal"""
    print("Generando reporte consolidado NPS/CSAT...")

    # Conectar a BD
    print("Conectando a base de datos...")
    engine = conectar_db()

    # Ejecutar queries
    print("Cargando datos BM-NPS...")
    df_bm_nps = query_bm_nps(engine)

    print("Cargando datos BM-CSAT...")
    df_bm_csat = query_bm_csat(engine)

    print("Cargando datos BV-NPS...")
    df_bv_nps = query_bv_nps(engine)

    print("Cargando consolidado...")
    df_consolidado = query_consolidado(engine)

    print("Cargando evolucion NPS...")
    df_evol_nps = query_evolucion_nps(engine)

    print("Cargando evolucion CSAT...")
    df_evol_csat = query_evolucion_csat(engine)

    # Cerrar conexión
    engine.dispose()

    # Generar HTML
    print("Generando HTML...")
    html_content = generar_html(df_bm_nps, df_bm_csat, df_bv_nps, df_consolidado, df_evol_nps, df_evol_csat)

    # Guardar archivo
    output_file = "visualizaciones/reporte_consolidado.html"
    import os
    os.makedirs("visualizaciones", exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\nReporte generado: {output_file}")
    print("\nRESUMEN:")
    print(f"  - BM-NPS: {len(df_bm_nps)} meses")
    print(f"  - BM-CSAT: {len(df_bm_csat)} meses")
    print(f"  - BV-NPS: {len(df_bv_nps)} meses")
    print(f"  - Total canales: {len(df_consolidado)}")

if __name__ == "__main__":
    main()
