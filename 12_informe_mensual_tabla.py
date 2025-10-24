#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Informe Mensual Detallado: Categorías + Sentimientos + Métricas por mes
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

def query_resumen_mensual(engine):
    """Resumen general por mes, canal y métrica"""
    query = """
        SELECT
            mes_anio,
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
        WHERE mes_anio IS NOT NULL
        GROUP BY mes_anio, canal, metrica
        ORDER BY mes_anio DESC, canal, metrica
    """
    return pd.read_sql(text(query), engine)

def query_sentimientos_mensual(engine):
    """Distribución de sentimientos por mes"""
    query = """
        SELECT
            mes_anio,
            canal,
            metrica,
            sentimiento_py,
            COUNT(*) as total,
            ROUND(AVG(score)::numeric, 2) as score_promedio
        FROM respuestas_nps_csat
        WHERE sentimiento_py IS NOT NULL
          AND mes_anio IS NOT NULL
        GROUP BY mes_anio, canal, metrica, sentimiento_py
        ORDER BY mes_anio DESC, canal, metrica, sentimiento_py
    """
    return pd.read_sql(text(query), engine)

def query_categorias_mensual(engine, limit=10):
    """Top categorías por mes"""
    query = f"""
        SELECT
            mes_anio,
            categoria,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE sentimiento_py = 'POSITIVO') as positivos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEGATIVO') as negativos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEUTRAL') as neutrales
        FROM respuestas_nps_csat
        WHERE categoria IS NOT NULL
          AND mes_anio IS NOT NULL
        GROUP BY mes_anio, categoria
        ORDER BY mes_anio DESC, total DESC
    """
    df = pd.read_sql(text(query), engine)

    # Top N por cada mes
    result = df.groupby('mes_anio').head(limit)
    return result

def query_emociones_mensual(engine):
    """Distribución de emociones por mes"""
    query = """
        SELECT
            mes_anio,
            emocion,
            COUNT(*) as total,
            ROUND(AVG(intensidad_emocional)::numeric, 2) as intensidad_prom
        FROM respuestas_nps_csat
        WHERE emocion IS NOT NULL
          AND mes_anio IS NOT NULL
        GROUP BY mes_anio, emocion
        ORDER BY mes_anio DESC, total DESC
    """
    return pd.read_sql(text(query), engine)

def generar_html(df_resumen, df_sentimientos, df_categorias, df_emociones):
    """Genera HTML con reporte mensual"""

    fecha = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Obtener lista de meses únicos ordenados
    meses = sorted(df_resumen['mes_anio'].unique(), reverse=True)

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Informe Mensual Detallado - NPS/CSAT</title>
    <style>
        body {{ font-family: 'Segoe UI', sans-serif; margin: 20px; background: #f5f5f5; }}
        .container {{ max-width: 1600px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; }}
        h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 40px; background: #ecf0f1; padding: 12px; border-left: 4px solid #3498db; }}
        h3 {{ color: #7f8c8d; margin-top: 20px; padding-left: 10px; border-left: 3px solid #95a5a6; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; font-size: 13px; }}
        th {{ background: #3498db; color: white; padding: 10px; text-align: left; position: sticky; top: 0; }}
        td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
        tr:hover {{ background: #f5f5f5; }}
        .num {{ text-align: right; font-family: monospace; }}
        .positivo {{ color: #27ae60; font-weight: bold; }}
        .negativo {{ color: #e74c3c; font-weight: bold; }}
        .neutral {{ color: #f39c12; }}
        .badge {{ display: inline-block; padding: 2px 6px; border-radius: 3px; font-size: 10px; font-weight: bold; }}
        .badge-bm {{ background: #3498db; color: white; }}
        .badge-bv {{ background: #1abc9c; color: white; }}
        .badge-nps {{ background: #9b59b6; color: white; }}
        .badge-csat {{ background: #e67e22; color: white; }}
        .mes-section {{ margin-top: 40px; padding: 20px; background: #fafafa; border-radius: 5px; }}
        .mes-titulo {{ color: #2c3e50; font-size: 24px; font-weight: bold; margin-bottom: 20px; }}
        .grid-2 {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }}
        .card {{ background: white; padding: 15px; border-radius: 5px; border: 1px solid #ddd; }}
        .card-title {{ font-weight: bold; color: #34495e; margin-bottom: 10px; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>INFORME MENSUAL DETALLADO - NPS/CSAT</h1>
        <p style="text-align: center; color: #7f8c8d;">Generado: {fecha}</p>
"""

    # Por cada mes, generar sección completa
    for mes in meses:
        html += f"""
        <div class="mes-section">
            <div class="mes-titulo">{mes}</div>
"""

        # 1. Resumen general del mes
        df_mes = df_resumen[df_resumen['mes_anio'] == mes]

        html += """
            <h3>1. Resumen General</h3>
            <table>
                <tr>
                    <th>Canal</th>
                    <th>Métrica</th>
                    <th>Total</th>
                    <th>Con Texto</th>
                    <th>%</th>
                    <th>Categorizados</th>
                    <th>%</th>
                    <th>Con Sentimiento</th>
                    <th>%</th>
                    <th>Ofensivos</th>
                    <th>Score Prom.</th>
                </tr>
"""

        for _, row in df_mes.iterrows():
            total = int(row['total'])
            con_texto = int(row['con_texto'])
            categorizados = int(row['categorizados'])
            con_sentimiento = int(row['con_sentimiento'])
            ofensivos = int(row['ofensivos'])

            pct_texto = (con_texto/total*100) if total > 0 else 0
            pct_categ = (categorizados/total*100) if total > 0 else 0
            pct_sent = (con_sentimiento/total*100) if total > 0 else 0

            canal_badge = f'<span class="badge badge-{row["canal"].lower()}">{row["canal"]}</span>'
            metrica_badge = f'<span class="badge badge-{row["metrica"].lower()}">{row["metrica"]}</span>'

            html += f"""
                <tr>
                    <td>{canal_badge}</td>
                    <td>{metrica_badge}</td>
                    <td class="num">{total:,}</td>
                    <td class="num">{con_texto:,}</td>
                    <td class="num">{pct_texto:.1f}%</td>
                    <td class="num">{categorizados:,}</td>
                    <td class="num">{pct_categ:.1f}%</td>
                    <td class="num">{con_sentimiento:,}</td>
                    <td class="num">{pct_sent:.1f}%</td>
                    <td class="num negativo">{ofensivos:,}</td>
                    <td class="num">{row['promedio_score']}</td>
                </tr>
"""

        html += "</table>"

        # 2. Sentimientos del mes
        df_sent_mes = df_sentimientos[df_sentimientos['mes_anio'] == mes]

        if not df_sent_mes.empty:
            html += """
            <div class="grid-2">
                <div class="card">
                    <div class="card-title">2. Distribución de Sentimientos</div>
                    <table>
                        <tr>
                            <th>Canal</th>
                            <th>Métrica</th>
                            <th>Sentimiento</th>
                            <th>Total</th>
                            <th>%</th>
                        </tr>
"""

            # Calcular totales por canal-métrica para %
            totales_sent = df_sent_mes.groupby(['canal', 'metrica'])['total'].sum().to_dict()

            for _, row in df_sent_mes.iterrows():
                key = (row['canal'], row['metrica'])
                total_grupo = totales_sent.get(key, 1)
                pct = (row['total'] / total_grupo * 100) if total_grupo > 0 else 0

                canal_badge = f'<span class="badge badge-{row["canal"].lower()}">{row["canal"]}</span>'
                metrica_badge = f'<span class="badge badge-{row["metrica"].lower()}">{row["metrica"]}</span>'
                sent_class = row['sentimiento_py'].lower()

                html += f"""
                        <tr>
                            <td>{canal_badge}</td>
                            <td>{metrica_badge}</td>
                            <td class="{sent_class}">{row['sentimiento_py']}</td>
                            <td class="num">{int(row['total']):,}</td>
                            <td class="num">{pct:.1f}%</td>
                        </tr>
"""

            html += """
                    </table>
                </div>
"""

        # 3. Top emociones del mes
        df_emo_mes = df_emociones[df_emociones['mes_anio'] == mes].head(5)

        if not df_emo_mes.empty:
            html += """
                <div class="card">
                    <div class="card-title">3. Top 5 Emociones</div>
                    <table>
                        <tr>
                            <th>Emoción</th>
                            <th>Total</th>
                            <th>%</th>
                            <th>Intensidad</th>
                        </tr>
"""

            total_emociones = df_emo_mes['total'].sum()

            for _, row in df_emo_mes.iterrows():
                pct = (row['total'] / total_emociones * 100) if total_emociones > 0 else 0

                html += f"""
                        <tr>
                            <td>{row['emocion'].upper()}</td>
                            <td class="num">{int(row['total']):,}</td>
                            <td class="num">{pct:.1f}%</td>
                            <td class="num">{row['intensidad_prom']}</td>
                        </tr>
"""

            html += """
                    </table>
                </div>
            </div>
"""

        # 4. Top categorías del mes
        df_cat_mes = df_categorias[df_categorias['mes_anio'] == mes]

        if not df_cat_mes.empty:
            html += """
            <h3>4. Top Categorías del Mes</h3>
            <table>
                <tr>
                    <th>Categoría</th>
                    <th>Total</th>
                    <th>Positivos</th>
                    <th>Negativos</th>
                    <th>Neutrales</th>
                </tr>
"""

            for _, row in df_cat_mes.iterrows():
                total = int(row['total'])
                pos = int(row['positivos'])
                neg = int(row['negativos'])
                neu = int(row['neutrales'])

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
                </tr>
"""

            html += "</table>"

        html += """
        </div>
"""

    html += """
        <div style="text-align: center; margin-top: 30px; color: #7f8c8d; font-size: 12px;">
            <p>Generado por 12_informe_mensual.py | Base: respuestas_nps_csat</p>
        </div>
    </div>
</body>
</html>
"""

    return html

def main():
    print("Generando informe mensual detallado...")

    engine = get_engine()

    print("Cargando resumen mensual...")
    df_resumen = query_resumen_mensual(engine)

    print("Cargando sentimientos por mes...")
    df_sentimientos = query_sentimientos_mensual(engine)

    print("Cargando categorías por mes...")
    df_categorias = query_categorias_mensual(engine)

    print("Cargando emociones por mes...")
    df_emociones = query_emociones_mensual(engine)

    engine.dispose()

    print("Generando HTML...")
    html = generar_html(df_resumen, df_sentimientos, df_categorias, df_emociones)

    output_dir = Path('visualizaciones')
    output_dir.mkdir(exist_ok=True)

    output_file = output_dir / 'informe_mensual.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f"\n[OK] Informe generado: {output_file}")
    print("\nRESUMEN:")
    print(f"  Meses analizados: {len(df_resumen['mes_anio'].unique())}")
    print(f"  Total registros: {df_resumen['total'].sum():,}")
    print(f"  Categorias unicas: {len(df_categorias['categoria'].unique())}")
    print(f"  Emociones detectadas: {len(df_emociones['emocion'].unique())}")

if __name__ == "__main__":
    main()
