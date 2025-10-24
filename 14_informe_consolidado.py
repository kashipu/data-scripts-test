#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Informe Consolidado NPS/CSAT (Todos los meses)

Incluye:
- Detección automática de anomalías
- Evolución temporal
- Análisis comparativo

Uso:
    python 14_informe_consolidado.py
    python 14_informe_consolidado.py --output informes/consolidado/
"""

import argparse
from pathlib import Path
from datetime import datetime

from utils import get_engine
from utils.db_queries import *
from utils.anomalias import *
import json
import pandas as pd
import numpy as np


def generar_tabla_resumen_mensual(df_evolucion):
    """
    Genera tabla HTML con resumen mensual por canal/metrica
    Muestra evolución de métricas clave con % de cambio

    Args:
        df_evolucion: DataFrame con mes_anio, canal, metrica, total, con_texto, etc.

    Returns: HTML string
    """
    html = """
    <div style="margin: 30px 0;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            Resumen Mensual por Canal y Métrica
        </h3>
    """

    # Agrupar por canal y metrica
    for (canal, metrica), grupo in df_evolucion.groupby(['canal', 'metrica']):
        grupo = grupo.sort_values('mes_anio')

        html += f"""
        <div style="margin: 20px 0; border: 1px solid #e0e0e0; border-radius: 4px; overflow: hidden;">
            <div style="background: #2c3e50; color: white; padding: 12px; font-weight: 600;">
                {canal} - {metrica}
            </div>
            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <thead>
                    <tr style="background: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                        <th style="padding: 10px; text-align: left;">Mes</th>
                        <th style="padding: 10px; text-align: right;">Total</th>
                        <th style="padding: 10px; text-align: right;">Con Texto</th>
                        <th style="padding: 10px; text-align: right;">Categorizados</th>
                        <th style="padding: 10px; text-align: right;">Score Prom.</th>
                        <th style="padding: 10px; text-align: right;">% Cambio</th>
                    </tr>
                </thead>
                <tbody>
        """

        total_anterior = None
        for idx, row in grupo.iterrows():
            mes = row['mes_anio']
            total = int(row['total'])
            con_texto = int(row['con_texto'])
            categorizados = int(row['categorizados'])
            score = row['score_promedio']

            # Calcular % cambio
            if total_anterior is not None:
                cambio_pct = ((total - total_anterior) / total_anterior * 100)
                if cambio_pct > 5:
                    cambio_str = f'<span style="color: #27ae60;">▲ {cambio_pct:.1f}%</span>'
                elif cambio_pct < -5:
                    cambio_str = f'<span style="color: #c0392b;">▼ {cambio_pct:.1f}%</span>'
                else:
                    cambio_str = f'<span style="color: #7f8c8d;">→ {cambio_pct:.1f}%</span>'
            else:
                cambio_str = '-'

            html += f"""
                    <tr style="border-bottom: 1px solid #f0f0f0;">
                        <td style="padding: 10px;"><strong>{mes}</strong></td>
                        <td style="padding: 10px; text-align: right;">{total:,}</td>
                        <td style="padding: 10px; text-align: right;">{con_texto:,}</td>
                        <td style="padding: 10px; text-align: right;">{categorizados:,}</td>
                        <td style="padding: 10px; text-align: right;">{score:.2f}</td>
                        <td style="padding: 10px; text-align: right;">{cambio_str}</td>
                    </tr>
            """
            total_anterior = total

        html += """
                </tbody>
            </table>
        </div>
        """

    html += """
    </div>
    """

    return html


def generar_tabla_top_categorias(df_categorias_mes, top_n=10):
    """
    Genera tabla con top categorías y su evolución mensual

    Args:
        df_categorias_mes: DataFrame con mes_anio, canal, metrica, categoria, total

    Returns: HTML string
    """
    # Calcular top categorías globales
    top_cats = df_categorias_mes.groupby('categoria')['total'].sum().nlargest(top_n).index.tolist()

    html = """
    <div style="margin: 30px 0;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            Top 10 Categorías con Evolución Mensual
        </h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 15px;">
            <thead>
                <tr style="background: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                    <th style="padding: 10px; text-align: left;">Categoría</th>
    """

    # Obtener meses únicos ordenados
    meses = sorted(df_categorias_mes['mes_anio'].unique())
    for mes in meses:
        html += f'<th style="padding: 10px; text-align: right;">{mes}</th>'

    html += """
                    <th style="padding: 10px; text-align: right;">Total</th>
                    <th style="padding: 10px; text-align: center;">Tendencia</th>
                </tr>
            </thead>
            <tbody>
    """

    for cat in top_cats:
        df_cat = df_categorias_mes[df_categorias_mes['categoria'] == cat]

        html += f"""
                <tr style="border-bottom: 1px solid #f0f0f0;">
                    <td style="padding: 10px;"><strong>{cat[:50]}</strong></td>
        """

        # Volúmenes por mes
        volumenes = []
        for mes in meses:
            vol = df_cat[df_cat['mes_anio'] == mes]['total'].sum()
            volumenes.append(vol)
            html += f'<td style="padding: 10px; text-align: right;">{int(vol):,}</td>'

        # Total
        total = sum(volumenes)
        html += f'<td style="padding: 10px; text-align: right;"><strong>{int(total):,}</strong></td>'

        # Tendencia
        if len(volumenes) >= 2:
            if volumenes[-1] > volumenes[0] * 1.1:
                tendencia = '<span style="color: #27ae60; font-size: 16px;">▲</span>'
            elif volumenes[-1] < volumenes[0] * 0.9:
                tendencia = '<span style="color: #c0392b; font-size: 16px;">▼</span>'
            else:
                tendencia = '<span style="color: #7f8c8d; font-size: 16px;">→</span>'
        else:
            tendencia = '-'

        html += f'<td style="padding: 10px; text-align: center;">{tendencia}</td>'
        html += """
                </tr>
        """

    html += """
            </tbody>
        </table>
    </div>
    """

    return html


def generar_tabla_categorias_detalladas(df_categorias_detalladas, top_n=15):
    """
    Genera tabla HTML con análisis detallado de categorías para detección de datos atípicos
    Incluye: evolutivo mensual, sentimientos, ofensivos, alertas de anomalías

    Args:
        df_categorias_detalladas: DataFrame con categoria, mes_anio, canal, metrica, total,
                                  positivos, negativos, neutrales, ofensivos, score_promedio, intensidades
        top_n: Número de categorías a mostrar (default: 15)

    Returns: HTML string con tabla detallada
    """
    # Calcular totales globales por categoría
    df_global = df_categorias_detalladas.groupby('categoria').agg({
        'total': 'sum',
        'positivos': 'sum',
        'negativos': 'sum',
        'neutrales': 'sum',
        'ofensivos': 'sum'
    }).reset_index()

    # Calcular scores separados por métrica (NPS y CSAT)
    df_scores = df_categorias_detalladas.groupby(['categoria', 'metrica']).agg({
        'total': 'sum',
        'score_promedio': 'mean'
    }).reset_index()

    # Pivot para tener score_nps y score_csat en columnas separadas
    df_scores_pivot = df_scores.pivot(index='categoria', columns='metrica', values='score_promedio').reset_index()
    df_scores_pivot.columns.name = None

    # Renombrar columnas (puede que no existan todas las métricas para todas las categorías)
    if 'NPS' in df_scores_pivot.columns:
        df_scores_pivot.rename(columns={'NPS': 'score_nps'}, inplace=True)
    else:
        df_scores_pivot['score_nps'] = None

    if 'CSAT' in df_scores_pivot.columns:
        df_scores_pivot.rename(columns={'CSAT': 'score_csat'}, inplace=True)
    else:
        df_scores_pivot['score_csat'] = None

    # Merge con datos globales
    df_global = df_global.merge(df_scores_pivot[['categoria', 'score_nps', 'score_csat']], on='categoria', how='left')

    # Calcular porcentajes
    df_global['pct_positivos'] = (df_global['positivos'] / df_global['total'] * 100).round(1)
    df_global['pct_negativos'] = (df_global['negativos'] / df_global['total'] * 100).round(1)
    df_global['pct_neutrales'] = (df_global['neutrales'] / df_global['total'] * 100).round(1)
    df_global['pct_ofensivos'] = (df_global['ofensivos'] / df_global['total'] * 100).round(1)

    # Top N categorías por volumen
    df_global = df_global.nlargest(top_n, 'total')

    # Obtener meses únicos ordenados
    meses = sorted(df_categorias_detalladas['mes_anio'].unique())

    html = """
    <div style="margin: 30px 0;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            Análisis Detallado de Categorías - Detección de Datos Atípicos
        </h3>
        <p style="color: #7f8c8d; font-size: 13px; margin-top: 10px;">
            Top 15 categorías con análisis de sentimientos, ofensivos y evolutivo mensual. Las alertas indican datos atípicos que requieren atención.
        </p>

        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 20px;">
            <thead>
                <tr style="background: #2c3e50; color: white;">
                    <th style="padding: 12px; text-align: left;">Categoría</th>
                    <th style="padding: 12px; text-align: right;">Total</th>
                    <th style="padding: 12px; text-align: center;">Distribución Sentimientos</th>
                    <th style="padding: 12px; text-align: center;">Ofensivos</th>
                    <th style="padding: 12px; text-align: center;">Score NPS</th>
                    <th style="padding: 12px; text-align: center;">Score CSAT</th>
                    <th style="padding: 12px; text-align: center;">Alertas</th>
                    <th style="padding: 12px; text-align: center;">Ver Detalle</th>
                </tr>
            </thead>
            <tbody>
    """

    # Procesar cada categoría
    for idx, row_global in df_global.iterrows():
        categoria = row_global['categoria']
        total = int(row_global['total'])
        pct_pos = row_global['pct_positivos']
        pct_neg = row_global['pct_negativos']
        pct_neu = row_global['pct_neutrales']
        pct_ofe = row_global['pct_ofensivos']
        score_nps = row_global['score_nps']
        score_csat = row_global['score_csat']
        ofensivos = int(row_global['ofensivos'])

        # Detectar anomalías (considerar ambos scores si existen)
        alertas = []
        if pct_neg > 50 or pct_ofe > 10:
            alertas.append('🔴 Crítico')
        elif pct_neg > 30 or pct_ofe > 5:
            alertas.append('🟠 Advertencia')
        # Alertas por score bajo
        elif (pd.notna(score_nps) and score_nps < 6) or (pd.notna(score_csat) and score_csat < 3):
            alertas.append('🟠 Advertencia')

        # Obtener datos mensuales de esta categoría
        df_cat = df_categorias_detalladas[df_categorias_detalladas['categoria'] == categoria].sort_values('mes_anio')

        # Calcular evolutivo de volumen para detectar picos
        volumenes_mes = []
        for mes in meses:
            vol = df_cat[df_cat['mes_anio'] == mes]['total'].sum()
            volumenes_mes.append(vol)

        # Detectar picos/caídas >50%
        for i in range(1, len(volumenes_mes)):
            if volumenes_mes[i-1] > 0:
                cambio_pct = ((volumenes_mes[i] - volumenes_mes[i-1]) / volumenes_mes[i-1] * 100)
                if abs(cambio_pct) > 50:
                    alertas.append('🟡 Pico/Caída')
                    break

        alertas_str = ' '.join(alertas) if alertas else '-'

        # ID único para expandir
        row_id = f"cat_{idx}"

        # Fila resumen
        html += f"""
                <tr style="border-bottom: 1px solid #e0e0e0; background: {'#fff3cd' if alertas else 'white'};">
                    <td style="padding: 12px;"><strong>{categoria[:60]}</strong></td>
                    <td style="padding: 12px; text-align: right;">{total:,}</td>
                    <td style="padding: 12px;">
                        <div style="display: flex; height: 20px; border-radius: 3px; overflow: hidden; border: 1px solid #e0e0e0;">
                            <div style="width: {pct_pos}%; background: #27ae60;" title="Positivos: {pct_pos}%"></div>
                            <div style="width: {pct_neu}%; background: #95a5a6;" title="Neutrales: {pct_neu}%"></div>
                            <div style="width: {pct_neg}%; background: #c0392b;" title="Negativos: {pct_neg}%"></div>
                        </div>
                        <div style="font-size: 11px; color: #7f8c8d; margin-top: 4px;">
                            <span style="color: #27ae60;">▲{pct_pos}%</span> |
                            <span style="color: #95a5a6;">●{pct_neu}%</span> |
                            <span style="color: #c0392b;">▼{pct_neg}%</span>
                        </div>
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        <strong style="color: {'#c0392b' if pct_ofe > 5 else '#7f8c8d'};">{ofensivos}</strong><br>
                        <span style="font-size: 11px; color: #7f8c8d;">({pct_ofe}%)</span>
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        {'<strong style="color: ' + ('#27ae60' if pd.notna(score_nps) and score_nps >= 7 else '#c0392b' if pd.notna(score_nps) and score_nps < 6 else '#7f8c8d') + ';">' + f'{score_nps:.2f}' + '</strong>' if pd.notna(score_nps) else '<span style="color: #bdc3c7;">-</span>'}
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        {'<strong style="color: ' + ('#27ae60' if pd.notna(score_csat) and score_csat >= 4 else '#c0392b' if pd.notna(score_csat) and score_csat < 3 else '#7f8c8d') + ';">' + f'{score_csat:.2f}' + '</strong>' if pd.notna(score_csat) else '<span style="color: #bdc3c7;">-</span>'}
                    </td>
                    <td style="padding: 12px; text-align: center; font-size: 12px;">
                        {alertas_str}
                    </td>
                    <td style="padding: 12px; text-align: center;">
                        <button onclick="toggleDetail('{row_id}')" style="background: #3498db; color: white; border: none; padding: 6px 12px; border-radius: 3px; cursor: pointer; font-size: 12px;">
                            Ver
                        </button>
                    </td>
                </tr>
        """

        # Fila detalle (oculta inicialmente)
        html += f"""
                <tr id="{row_id}" style="display: none; background: #f8f9fa;">
                    <td colspan="8" style="padding: 20px;">
                        <h4 style="margin: 0 0 15px 0; color: #2c3e50;">Evolutivo Mensual: {categoria[:60]}</h4>
                        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
                            <thead>
                                <tr style="background: #e9ecef;">
                                    <th style="padding: 8px; text-align: left;">Mes</th>
                                    <th style="padding: 8px; text-align: right;">Total</th>
                                    <th style="padding: 8px; text-align: right;">Positivos</th>
                                    <th style="padding: 8px; text-align: right;">Negativos</th>
                                    <th style="padding: 8px; text-align: right;">Neutrales</th>
                                    <th style="padding: 8px; text-align: right;">Ofensivos</th>
                                    <th style="padding: 8px; text-align: right;">Score NPS</th>
                                    <th style="padding: 8px; text-align: right;">Score CSAT</th>
                                    <th style="padding: 8px; text-align: center;">Cambio</th>
                                </tr>
                            </thead>
                            <tbody>
        """

        # Datos mensuales
        total_anterior = None
        for mes in meses:
            df_mes = df_cat[df_cat['mes_anio'] == mes]

            if df_mes.empty:
                continue

            total_mes = int(df_mes['total'].sum())
            pos_mes = int(df_mes['positivos'].sum())
            neg_mes = int(df_mes['negativos'].sum())
            neu_mes = int(df_mes['neutrales'].sum())
            ofe_mes = int(df_mes['ofensivos'].sum())

            # Calcular scores separados por métrica
            df_mes_nps = df_mes[df_mes['metrica'] == 'NPS']
            df_mes_csat = df_mes[df_mes['metrica'] == 'CSAT']

            score_nps_mes = df_mes_nps['score_promedio'].mean() if not df_mes_nps.empty else None
            score_csat_mes = df_mes_csat['score_promedio'].mean() if not df_mes_csat.empty else None

            # Calcular cambio
            if total_anterior is not None and total_anterior > 0:
                cambio_pct = ((total_mes - total_anterior) / total_anterior * 100)
                if cambio_pct > 15:
                    cambio_str = f'<span style="color: #27ae60;">▲{cambio_pct:.0f}%</span>'
                elif cambio_pct < -15:
                    cambio_str = f'<span style="color: #c0392b;">▼{cambio_pct:.0f}%</span>'
                else:
                    cambio_str = f'<span style="color: #7f8c8d;">→{cambio_pct:.0f}%</span>'
            else:
                cambio_str = '-'

            html += f"""
                                <tr style="border-bottom: 1px solid #dee2e6;">
                                    <td style="padding: 8px;"><strong>{mes}</strong></td>
                                    <td style="padding: 8px; text-align: right;">{total_mes:,}</td>
                                    <td style="padding: 8px; text-align: right; color: #27ae60;">{pos_mes:,}</td>
                                    <td style="padding: 8px; text-align: right; color: #c0392b;">{neg_mes:,}</td>
                                    <td style="padding: 8px; text-align: right; color: #95a5a6;">{neu_mes:,}</td>
                                    <td style="padding: 8px; text-align: right; color: {'#c0392b' if ofe_mes > total_mes * 0.05 else '#7f8c8d'};">{ofe_mes:,}</td>
                                    <td style="padding: 8px; text-align: right;">{f'{score_nps_mes:.2f}' if score_nps_mes is not None else '-'}</td>
                                    <td style="padding: 8px; text-align: right;">{f'{score_csat_mes:.2f}' if score_csat_mes is not None else '-'}</td>
                                    <td style="padding: 8px; text-align: center;">{cambio_str}</td>
                                </tr>
            """
            total_anterior = total_mes

        html += """
                            </tbody>
                        </table>
                    </td>
                </tr>
        """

    html += """
            </tbody>
        </table>
    </div>

    <script>
        function toggleDetail(rowId) {
            var row = document.getElementById(rowId);
            if (row.style.display === 'none') {
                row.style.display = 'table-row';
            } else {
                row.style.display = 'none';
            }
        }
    </script>
    """

    return html


def generar_cards_confianza(df_evolucion):
    """
    Genera cards HTML con porcentajes de confianza de categorización y sentimiento

    Args:
        df_evolucion: DataFrame con confianza_categoria y confianza_sentimiento

    Returns:
        String HTML con dos cards de confianza
    """
    # Calcular promedios ponderados por total de registros
    total_registros = df_evolucion['total'].sum()

    # Confianza categorización
    confianza_cat = (df_evolucion['confianza_categoria'] * df_evolucion['total']).sum() / total_registros
    pct_cat = confianza_cat * 100

    # Confianza sentimiento
    confianza_sent = (df_evolucion['confianza_sentimiento'] * df_evolucion['total']).sum() / total_registros
    pct_sent = confianza_sent * 100

    html = f"""
            <div class="kpi">
                <div class="kpi-label">Confianza Categorización</div>
                <div class="kpi-valor">{pct_cat:.1f}%</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Confianza Sentimiento</div>
                <div class="kpi-valor">{pct_sent:.1f}%</div>
            </div>
    """

    return html


def generar_html_consolidado(df_evolucion, df_categorias_mes, df_categorias_detalladas, anomalias_dict):
    """
    Genera HTML consolidado con tablas y gráficas D3.js
    Estilo ejecutivo sobrio

    Args:
        df_evolucion: DataFrame con evolución mensual
        df_categorias_mes: DataFrame con categorías por mes
        df_categorias_detalladas: DataFrame con categorías detalladas (sentimientos, ofensivos, evolutivo)
        anomalias_dict: Dict con anomalías detectadas

    Returns: HTML string
    """
    fecha_generacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Calcular estadísticas globales
    total_registros = int(df_evolucion['total'].sum())
    total_meses = len(df_evolucion['mes_anio'].unique())
    promedio_mensual = int(total_registros / total_meses) if total_meses > 0 else 0

    # Preparar datos JSON para D3.js
    # Datos para gráfica de volúmenes
    datos_volumenes = df_evolucion[['mes_anio', 'canal', 'metrica', 'total']].to_dict(orient='records')

    # Datos para gráfica de scores
    datos_scores = df_evolucion[['mes_anio', 'canal', 'metrica', 'score_promedio']].to_dict(orient='records')

    # Generar tablas y cards
    cards_confianza = generar_cards_confianza(df_evolucion)
    tabla_resumen = generar_tabla_resumen_mensual(df_evolucion)
    tabla_categorias = generar_tabla_top_categorias(df_categorias_mes)
    tabla_categorias_detalladas = generar_tabla_categorias_detalladas(df_categorias_detalladas)

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe Consolidado - NPS/CSAT</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        /* Estilo Ejecutivo Sobrio */
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f8f9fa;
            color: #2c3e50;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background-color: white;
            padding: 30px 40px;
            border-radius: 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.08);
        }}
        h1 {{
            color: #2c3e50;
            text-align: left;
            font-size: 28px;
            font-weight: 600;
            border-bottom: 2px solid #3498db;
            padding-bottom: 12px;
            margin-bottom: 8px;
        }}
        .fecha {{
            color: #7f8c8d;
            font-size: 13px;
            margin-bottom: 30px;
        }}
        .kpis {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 15px;
            margin: 25px 0;
        }}
        .kpi {{
            background: white;
            border: 1px solid #e0e0e0;
            border-left: 4px solid #3498db;
            padding: 18px;
            border-radius: 3px;
        }}
        .kpi-valor {{
            font-size: 32px;
            font-weight: 600;
            color: #2c3e50;
            margin: 8px 0;
        }}
        .kpi-label {{
            font-size: 13px;
            color: #7f8c8d;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        h2 {{
            color: #2c3e50;
            margin-top: 40px;
            padding: 12px 0;
            font-size: 18px;
            font-weight: 600;
            border-bottom: 1px solid #e0e0e0;
        }}
        .chart-container {{
            margin: 20px 0;
            padding: 20px;
            background: white;
            border: 1px solid #e0e0e0;
            border-radius: 4px;
        }}
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #7f8c8d;
            font-size: 12px;
            border-top: 1px solid #e0e0e0;
        }}
        /* Estilos D3.js */
        .line {{
            fill: none;
            stroke-width: 2px;
        }}
        .dot {{
            stroke: white;
            stroke-width: 1.5px;
        }}
        .axis {{
            font-size: 11px;
            color: #7f8c8d;
        }}
        .grid line {{
            stroke: #e0e0e0;
            stroke-opacity: 0.7;
        }}
        .tooltip {{
            position: absolute;
            padding: 8px 12px;
            background: rgba(44, 62, 80, 0.95);
            color: white;
            border-radius: 4px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.2s;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>INFORME CONSOLIDADO NPS/CSAT</h1>
        <div class="fecha">Generado: {fecha_generacion}</div>

        <!-- KPIs Globales -->
        <div class="kpis">
            <div class="kpi">
                <div class="kpi-label">Total Registros</div>
                <div class="kpi-valor">{total_registros:,}</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Meses Analizados</div>
                <div class="kpi-valor">{total_meses}</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Promedio Mensual</div>
                <div class="kpi-valor">{promedio_mensual:,}</div>
            </div>
            {cards_confianza}
        </div>

        <!-- Alertas de Anomalías -->
        {generar_seccion_alertas_html(anomalias_dict)}

        <!-- TABLA: Resumen Mensual -->
        {tabla_resumen}

        <!-- GRÁFICA D3: Evolución de Volúmenes -->
        <h2>Evolución Temporal de Volúmenes</h2>
        <div class="chart-container">
            <div id="chart-volumenes"></div>
        </div>

        <!-- GRÁFICA D3: Evolución de Scores -->
        <h2>Tendencia de Scores Promedio</h2>
        <div class="chart-container">
            <div id="chart-scores"></div>
        </div>

        <!-- TABLA: Top Categorías -->
        {tabla_categorias}

        <!-- TABLA: Análisis Detallado de Categorías -->
        {tabla_categorias_detalladas}

        <div class="footer">
            <p><strong>Informe Consolidado Automático - NPS/CSAT Analytics</strong></p>
            <p>Generado por 14_informe_consolidado.py | Base de datos: respuestas_nps_csat</p>
            <p>Total de meses analizados: {total_meses} | Total de registros: {total_registros:,}</p>
        </div>
    </div>

    <!-- DATOS JSON PARA D3.JS -->
    <script>
        const datosVolumenes = {json.dumps(datos_volumenes)};
        const datosScores = {json.dumps(datos_scores)};

        // GRÁFICA 1: Evolución de Volúmenes (Líneas)
        createLineChart('chart-volumenes', datosVolumenes, 'total', 'Cantidad de Registros');

        // GRÁFICA 2: Evolución de Scores (Líneas)
        createLineChart('chart-scores', datosScores, 'score_promedio', 'Score Promedio');

        function createLineChart(containerId, data, valueKey, yLabel) {{
            const margin = {{top: 20, right: 120, bottom: 50, left: 60}};
            const width = 1200 - margin.left - margin.right;
            const height = 400 - margin.top - margin.bottom;

            const svg = d3.select(`#${{containerId}}`)
                .append('svg')
                .attr('width', width + margin.left + margin.right)
                .attr('height', height + margin.top + margin.bottom)
                .append('g')
                .attr('transform', `translate(${{margin.left}},${{margin.top}})`);

            // Agrupar datos por canal-metrica
            const nested = d3.group(data, d => `${{d.canal}}-${{d.metrica}}`);

            // Escala X (meses)
            const xScale = d3.scaleBand()
                .domain([...new Set(data.map(d => d.mes_anio))].sort())
                .range([0, width])
                .padding(0.1);

            // Escala Y
            const yScale = d3.scaleLinear()
                .domain([0, d3.max(data, d => d[valueKey]) * 1.1])
                .range([height, 0]);

            // Línea generadora
            const line = d3.line()
                .x(d => xScale(d.mes_anio) + xScale.bandwidth() / 2)
                .y(d => yScale(d[valueKey]));

            // Colores
            const colorScale = d3.scaleOrdinal()
                .domain(['BM-NPS', 'BM-CSAT', 'BV-NPS', 'BV-CSAT'])
                .range(['#2c3e50', '#3498db', '#34495e', '#2980b9']);

            // Dibujar líneas
            nested.forEach((values, key) => {{
                svg.append('path')
                    .datum(values)
                    .attr('class', 'line')
                    .attr('d', line)
                    .attr('stroke', colorScale(key))
                    .attr('stroke-width', 2);

                // Puntos
                svg.selectAll(`.dot-${{key.replace('-', '')}}`)
                    .data(values)
                    .enter().append('circle')
                    .attr('class', 'dot')
                    .attr('cx', d => xScale(d.mes_anio) + xScale.bandwidth() / 2)
                    .attr('cy', d => yScale(d[valueKey]))
                    .attr('r', 4)
                    .attr('fill', colorScale(key));
            }});

            // Ejes
            svg.append('g')
                .attr('class', 'axis')
                .attr('transform', `translate(0,${{height}})`)
                .call(d3.axisBottom(xScale));

            svg.append('g')
                .attr('class', 'axis')
                .call(d3.axisLeft(yScale));

            // Etiqueta Y
            svg.append('text')
                .attr('transform', 'rotate(-90)')
                .attr('y', 0 - margin.left)
                .attr('x', 0 - (height / 2))
                .attr('dy', '1em')
                .style('text-anchor', 'middle')
                .style('font-size', '12px')
                .style('fill', '#7f8c8d')
                .text(yLabel);

            // Leyenda
            const legend = svg.append('g')
                .attr('transform', `translate(${{width + 10}}, 20)`);

            let yPos = 0;
            nested.forEach((values, key) => {{
                const g = legend.append('g')
                    .attr('transform', `translate(0, ${{yPos}})`);

                g.append('line')
                    .attr('x1', 0)
                    .attr('x2', 20)
                    .attr('y1', 5)
                    .attr('y2', 5)
                    .attr('stroke', colorScale(key))
                    .attr('stroke-width', 2);

                g.append('text')
                    .attr('x', 25)
                    .attr('y', 9)
                    .style('font-size', '11px')
                    .text(key);

                yPos += 25;
            }});
        }}
    </script>
</body>
</html>
"""

    return html


def main():
    parser = argparse.ArgumentParser(
        description='Generador de Informe Consolidado NPS/CSAT (todos los meses)',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--output', type=str, default='informes/consolidado',
                       help='Directorio de salida (default: informes/consolidado)')

    args = parser.parse_args()

    print("\n" + "="*70)
    print("GENERADOR DE INFORME CONSOLIDADO NPS/CSAT")
    print("="*70)

    engine = get_engine()

    # 1. Queries consolidadas
    print("\n1. Ejecutando queries consolidadas...")
    df_evolucion = query_evolucion_mensual(engine)
    df_sentimientos = query_sentimientos_por_mes(engine)
    df_categorias_mes = query_categorias_por_mes(engine)
    df_categorias_detalladas = query_categorias_detalladas_consolidado(engine)
    df_scores = query_distribucion_scores_global(engine)
    df_treemap = query_treemap_jerarquia(engine)

    if df_evolucion.empty:
        print("[ERROR] No hay datos disponibles en la base de datos")
        engine.dispose()
        return

    print(f"   Meses encontrados: {len(df_evolucion['mes_anio'].unique())}")
    print(f"   Total registros: {df_evolucion['total'].sum():,}")

    # 2. Detección de anomalías
    print("\n2. Detectando anomalías...")

    anomalias = {
        'volumen': detectar_anomalias_volumen(df_evolucion),
        'sentimientos': detectar_anomalias_sentimientos(df_sentimientos),
        'ofensivos': detectar_anomalias_ofensivos(df_evolucion),
        'categorias': detectar_categorias_nuevas_perdidas(df_categorias_mes)
    }

    total_anomalias = sum(len(v) for v in anomalias.values())
    print(f"   Anomalías detectadas: {total_anomalias}")
    print(f"      Volumen: {len(anomalias['volumen'])}")
    print(f"      Sentimientos: {len(anomalias['sentimientos'])}")
    print(f"      Ofensivos: {len(anomalias['ofensivos'])}")
    print(f"      Categorías: {len(anomalias['categorias'])}")

    # 3. Generar HTML consolidado con tablas y D3.js
    print("\n3. Generando informe HTML con tablas y gráficas D3.js...")
    html = generar_html_consolidado(df_evolucion, df_categorias_mes, df_categorias_detalladas, anomalias)

    # 5. Guardar archivo
    output_path = Path(args.output)
    output_path.mkdir(parents=True, exist_ok=True)

    output_file = output_path / 'informe_consolidado.html'
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    engine.dispose()

    print(f"\n{'='*70}")
    print(f"[OK] INFORME CONSOLIDADO GENERADO EXITOSAMENTE")
    print(f"{'='*70}")
    print(f"\nUbicacion: {output_file.absolute()}")
    print(f"Meses analizados: {len(df_evolucion['mes_anio'].unique())}")
    print(f"Total registros: {df_evolucion['total'].sum():,}")
    print(f"Anomalias detectadas: {total_anomalias}")
    print(f"\n{'='*70}\n")


if __name__ == "__main__":
    main()
