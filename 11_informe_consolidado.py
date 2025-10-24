#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Informe consolidado: Categorías + Sentimientos + Métricas
Usa tabla unificada respuestas_nps_csat
"""

import pandas as pd
from sqlalchemy import create_engine, text
from datetime import datetime
from pathlib import Path

DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}

def get_engine():
    conn_string = f"postgresql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?client_encoding=utf8"
    return create_engine(conn_string)

def query_resumen_general(engine):
    """Resumen general por canal y métrica"""
    query = """
        SELECT
            canal,
            metrica,
            COUNT(*) as total,
            COUNT(motivo_texto) FILTER (WHERE LENGTH(TRIM(motivo_texto)) > 0) as con_texto,
            COUNT(categoria) as categorizados,
            COUNT(sentimiento_py) as con_sentimiento,
            COUNT(*) FILTER (WHERE es_ofensivo = TRUE) as ofensivos,
            COUNT(*) FILTER (WHERE es_ruido = TRUE) as ruido,
            ROUND(AVG(score)::numeric, 2) as promedio_score
        FROM respuestas_nps_csat
        GROUP BY canal, metrica
        ORDER BY canal, metrica
    """
    return pd.read_sql(text(query), engine)

def query_categorias_top(engine, limit=15):
    """Top categorías con sentimientos"""
    query = f"""
        SELECT
            categoria,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE sentimiento_py = 'POSITIVO') as positivos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEGATIVO') as negativos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEUTRAL') as neutrales,
            COUNT(*) FILTER (WHERE es_ofensivo = TRUE) as ofensivos,
            ROUND(AVG(confianza_py)::numeric, 2) as confianza_prom
        FROM respuestas_nps_csat
        WHERE categoria IS NOT NULL
        GROUP BY categoria
        ORDER BY total DESC
        LIMIT {limit}
    """
    return pd.read_sql(text(query), engine)

def query_sentimientos_por_canal(engine):
    """Distribución de sentimientos por canal y métrica"""
    query = """
        SELECT
            canal,
            metrica,
            sentimiento_py,
            COUNT(*) as total,
            ROUND(AVG(score)::numeric, 2) as score_promedio
        FROM respuestas_nps_csat
        WHERE sentimiento_py IS NOT NULL
        GROUP BY canal, metrica, sentimiento_py
        ORDER BY canal, metrica, sentimiento_py
    """
    return pd.read_sql(text(query), engine)

def query_emociones_top(engine, limit=10):
    """Top emociones detectadas"""
    query = f"""
        SELECT
            emocion,
            COUNT(*) as total,
            ROUND(AVG(intensidad_emocional)::numeric, 2) as intensidad_prom,
            COUNT(*) FILTER (WHERE intensidad_emocional > 0.8) as muy_intensas
        FROM respuestas_nps_csat
        WHERE emocion IS NOT NULL
        GROUP BY emocion
        ORDER BY total DESC
        LIMIT {limit}
    """
    return pd.read_sql(text(query), engine)

def generar_html(df_resumen, df_categorias, df_sentimientos, df_emociones):
    """Genera HTML consolidado"""

    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe Consolidado - NPS/CSAT</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1400px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; background: #ecf0f1; padding: 10px; border-left: 4px solid #3498db; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th {{ background: #3498db; color: white; padding: 12px; text-align: left; }}
        td {{ padding: 10px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
        .num {{ text-align: right; font-family: monospace; }}
        .positivo {{ color: #27ae60; font-weight: bold; }}
        .negativo {{ color: #e74c3c; font-weight: bold; }}
        .neutral {{ color: #f39c12; }}
        .badge {{ display: inline-block; padding: 3px 8px; border-radius: 3px; font-size: 11px; font-weight: bold; }}
        .badge-bm {{ background: #3498db; color: white; }}
        .badge-bv {{ background: #1abc9c; color: white; }}
        .badge-nps {{ background: #9b59b6; color: white; }}
        .badge-csat {{ background: #e67e22; color: white; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 INFORME CONSOLIDADO - CATEGORÍAS + SENTIMIENTOS + MÉTRICAS</h1>
        <p style="text-align: center; color: #7f8c8d;">Generado: {fecha}</p>

        <h2>1. RESUMEN GENERAL POR CANAL Y MÉTRICA</h2>
        <table>
            <tr>
                <th>Canal</th>
                <th>Métrica</th>
                <th>Total</th>
                <th>Con Texto</th>
                <th>Categorizados</th>
                <th>Con Sentimiento</th>
                <th>Ofensivos</th>
                <th>Ruido</th>
                <th>Score Prom.</th>
            </tr>
"""

    for _, row in df_resumen.iterrows():
        canal_badge = f'<span class="badge badge-{row["canal"].lower()}">{row["canal"]}</span>'
        metrica_badge = f'<span class="badge badge-{row["metrica"].lower()}">{row["metrica"]}</span>'
        html += f"""
            <tr>
                <td>{canal_badge}</td>
                <td>{metrica_badge}</td>
                <td class="num">{int(row['total']):,}</td>
                <td class="num">{int(row['con_texto']):,}</td>
                <td class="num">{int(row['categorizados']):,}</td>
                <td class="num">{int(row['con_sentimiento']):,}</td>
                <td class="num negativo">{int(row['ofensivos']):,}</td>
                <td class="num neutral">{int(row['ruido']):,}</td>
                <td class="num">{row['promedio_score']}</td>
            </tr>
"""

    html += """
        </table>

        <h2>2. TOP CATEGORÍAS CON DISTRIBUCIÓN DE SENTIMIENTOS</h2>
        <table>
            <tr>
                <th>Categoría</th>
                <th>Total</th>
                <th>Positivos</th>
                <th>Negativos</th>
                <th>Neutrales</th>
                <th>Ofensivos</th>
                <th>Confianza</th>
            </tr>
"""

    for _, row in df_categorias.iterrows():
        total = int(row['total'])
        pos = int(row['positivos'])
        neg = int(row['negativos'])
        neu = int(row['neutrales'])
        ofens = int(row['ofensivos'])

        pct_pos = (pos/total*100) if total > 0 else 0
        pct_neg = (neg/total*100) if total > 0 else 0
        pct_neu = (neu/total*100) if total > 0 else 0

        html += f"""
            <tr>
                <td>{row['categoria']}</td>
                <td class="num">{total:,}</td>
                <td class="num positivo">{pos:,} ({pct_pos:.1f}%)</td>
                <td class="num negativo">{neg:,} ({pct_neg:.1f}%)</td>
                <td class="num neutral">{neu:,} ({pct_neu:.1f}%)</td>
                <td class="num negativo">{ofens:,}</td>
                <td class="num">{row['confianza_prom']}</td>
            </tr>
"""

    html += """
        </table>

        <h2>3. DISTRIBUCIÓN DE SENTIMIENTOS POR CANAL Y MÉTRICA</h2>
        <table>
            <tr>
                <th>Canal</th>
                <th>Métrica</th>
                <th>Sentimiento</th>
                <th>Total</th>
                <th>%</th>
                <th>Score Prom.</th>
            </tr>
"""

    # Calcular totales por canal-métrica para %
    totales = df_sentimientos.groupby(['canal', 'metrica'])['total'].sum().to_dict()

    for _, row in df_sentimientos.iterrows():
        canal_badge = f'<span class="badge badge-{row["canal"].lower()}">{row["canal"]}</span>'
        metrica_badge = f'<span class="badge badge-{row["metrica"].lower()}">{row["metrica"]}</span>'

        key = (row['canal'], row['metrica'])
        total_grupo = totales.get(key, 1)
        pct = (row['total'] / total_grupo * 100) if total_grupo > 0 else 0

        sent_class = row['sentimiento_py'].lower()

        html += f"""
            <tr>
                <td>{canal_badge}</td>
                <td>{metrica_badge}</td>
                <td class="{sent_class}">{row['sentimiento_py']}</td>
                <td class="num">{int(row['total']):,}</td>
                <td class="num">{pct:.1f}%</td>
                <td class="num">{row['score_promedio']}</td>
            </tr>
"""

    html += """
        </table>

        <h2>4. TOP EMOCIONES DETECTADAS</h2>
        <table>
            <tr>
                <th>Emoción</th>
                <th>Total</th>
                <th>Intensidad Promedio</th>
                <th>Muy Intensas (>0.8)</th>
            </tr>
"""

    for _, row in df_emociones.iterrows():
        html += f"""
            <tr>
                <td>{row['emocion'].upper()}</td>
                <td class="num">{int(row['total']):,}</td>
                <td class="num">{row['intensidad_prom']}</td>
                <td class="num negativo">{int(row['muy_intensas']):,}</td>
            </tr>
"""

    html += """
        </table>

        <div style="text-align: center; margin-top: 30px; color: #7f8c8d; font-size: 12px;">
            <p>Generado por 11_informe_consolidado.py | Base: respuestas_nps_csat</p>
        </div>
    </div>
</body>
</html>
"""

    return html

def main():
    print("Generando informe consolidado...")

    engine = get_engine()

    print("Cargando resumen general...")
    df_resumen = query_resumen_general(engine)

    print("Cargando top categorías...")
    df_categorias = query_categorias_top(engine)

    print("Cargando sentimientos por canal...")
    df_sentimientos = query_sentimientos_por_canal(engine)

    print("Cargando emociones...")
    df_emociones = query_emociones_top(engine)

    engine.dispose()

    print("Generando HTML...")
    html = generar_html(df_resumen, df_categorias, df_sentimientos, df_emociones)

    output_dir = Path('visualizaciones')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / 'informe_consolidado.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n[OK] Informe generado: {output_file}")
    print("\nRESUMEN:")
    print(f"  Total canales/métricas: {len(df_resumen)}")
    print(f"  Top categorías: {len(df_categorias)}")
    print(f"  Combinaciones sentimiento: {len(df_sentimientos)}")
    print(f"  Emociones detectadas: {len(df_emociones)}")

if __name__ == "__main__":
    main()
