#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Generador de Informes Mensuales NPS/CSAT

Uso:
    python 13_informe_mensual.py --mes 06                  # Solo junio 2025
    python 13_informe_mensual.py --mes 2025-07             # Julio con formato completo
    python 13_informe_mensual.py --todos                   # Todos los meses disponibles
    python 13_informe_mensual.py --mes 06 --output informes/custom/
"""

import argparse
import base64
import json
import pandas as pd
from pathlib import Path
from datetime import datetime

from utils import get_engine
from utils.db_queries import *
from utils.csv_exports import export_excel_mensual
from utils.graficas_plotly import *
from utils.graficas_estaticas import *


def imagen_to_base64(image_path):
    """Convierte imagen PNG a base64 para embeber en HTML"""
    with open(image_path, 'rb') as f:
        return base64.b64encode(f.read()).decode('utf-8')


def generar_tabla_metricas_html(df_tabla_metricas):
    """
    Genera tabla HTML con métricas consolidadas (separada por canal/metrica)

    Args:
        df_tabla_metricas: DataFrame con métricas detalladas por canal/metrica

    Returns:
        String HTML con tabla de métricas
    """
    html = """
    <div style="margin: 30px 0; padding: 20px; background: #f9f9f9; border-radius: 8px;">
        <h2 style="color: #2c3e50; margin-top: 0;">Métricas Consolidadas por Canal y Métrica</h2>
"""

    for _, row in df_tabla_metricas.iterrows():
        canal = row['canal']
        metrica = row['metrica']
        total = int(row['total'])
        con_texto = int(row['con_texto'])
        categorizados = int(row['categorizados'])
        con_sentimiento = int(row['con_sentimiento'])
        score_promedio = row['score_promedio']

        # Calcular porcentajes
        pct_texto = (con_texto / total * 100) if total > 0 else 0
        pct_categorizados = (categorizados / total * 100) if total > 0 else 0
        pct_sentimiento = (con_sentimiento / total * 100) if total > 0 else 0

        # Color según canal
        color_header = '#3498db' if canal == 'BM' else '#1abc9c'

        html += f"""
        <div style="margin: 20px 0; border: 2px solid {color_header}; border-radius: 5px; overflow: hidden;">
            <div style="background: {color_header}; color: white; padding: 15px; font-size: 18px; font-weight: bold;">
                {canal} - {metrica}
            </div>
            <div style="padding: 15px; background: white;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Total Registros:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{total:,}</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Score Promedio:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{score_promedio:.2f}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Con Texto:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{con_texto:,} ({pct_texto:.1f}%)</td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;"><strong>Categorizados:</strong></td>
                        <td style="padding: 8px; border-bottom: 1px solid #ddd;">{categorizados:,} ({pct_categorizados:.1f}%)</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;"><strong>Con Sentimiento:</strong></td>
                        <td style="padding: 8px;">{con_sentimiento:,} ({pct_sentimiento:.1f}%)</td>
                        <td style="padding: 8px;"></td>
                        <td style="padding: 8px;"></td>
                    </tr>
                </table>
"""

        # Desglose específico NPS
        if metrica == 'NPS':
            detractores = int(row['nps_detractores'])
            pasivos = int(row['nps_pasivos'])
            promotores = int(row['nps_promotores'])

            pct_detractores = (detractores / total * 100) if total > 0 else 0
            pct_pasivos = (pasivos / total * 100) if total > 0 else 0
            pct_promotores = (promotores / total * 100) if total > 0 else 0

            html += f"""
                <h4 style="margin: 15px 0 10px 0; color: #34495e;">Desglose NPS:</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #f8d7da;">
                        <td style="padding: 8px;"><strong>Detractores (0-6):</strong></td>
                        <td style="padding: 8px;">{detractores:,} ({pct_detractores:.1f}%)</td>
                    </tr>
                    <tr style="background: #fff3cd;">
                        <td style="padding: 8px;"><strong>Pasivos (7-8):</strong></td>
                        <td style="padding: 8px;">{pasivos:,} ({pct_pasivos:.1f}%)</td>
                    </tr>
                    <tr style="background: #d4edda;">
                        <td style="padding: 8px;"><strong>Promotores (9-10):</strong></td>
                        <td style="padding: 8px;">{promotores:,} ({pct_promotores:.1f}%)</td>
                    </tr>
                </table>
"""

        # Desglose específico CSAT
        elif metrica == 'CSAT':
            bajo = int(row['csat_bajo'])
            medio = int(row['csat_medio'])
            alto = int(row['csat_alto'])

            pct_bajo = (bajo / total * 100) if total > 0 else 0
            pct_medio = (medio / total * 100) if total > 0 else 0
            pct_alto = (alto / total * 100) if total > 0 else 0

            html += f"""
                <h4 style="margin: 15px 0 10px 0; color: #34495e;">Desglose CSAT:</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: #f8d7da;">
                        <td style="padding: 8px;"><strong>Bajo (1-2):</strong></td>
                        <td style="padding: 8px;">{bajo:,} ({pct_bajo:.1f}%)</td>
                    </tr>
                    <tr style="background: #fff3cd;">
                        <td style="padding: 8px;"><strong>Medio (3):</strong></td>
                        <td style="padding: 8px;">{medio:,} ({pct_medio:.1f}%)</td>
                    </tr>
                    <tr style="background: #d4edda;">
                        <td style="padding: 8px;"><strong>Alto (4-5):</strong></td>
                        <td style="padding: 8px;">{alto:,} ({pct_alto:.1f}%)</td>
                    </tr>
                </table>
"""

        # Sentimientos con intensidad
        positivos = int(row['positivos'])
        negativos = int(row['negativos'])
        neutrales = int(row['neutrales'])
        total_sentimientos = positivos + negativos + neutrales

        # Intensidades
        int_pos = row.get('intensidad_positiva', None)
        int_neg = row.get('intensidad_negativa', None)
        int_neu = row.get('intensidad_neutral', None)

        if total_sentimientos > 0:
            pct_pos = (positivos / total_sentimientos * 100)
            pct_neg = (negativos / total_sentimientos * 100)
            pct_neu = (neutrales / total_sentimientos * 100)

            # Función para color según intensidad
            def color_intensidad(intensidad):
                if intensidad is None or pd.isna(intensidad):
                    return '#ecf0f1'
                elif intensidad >= 0.7:
                    return '#e8f5e9'  # Verde claro
                elif intensidad >= 0.4:
                    return '#fff9e6'  # Amarillo claro
                else:
                    return '#fdecea'  # Rojo claro

            bg_pos = color_intensidad(int_pos)
            bg_neg = color_intensidad(int_neg)
            bg_neu = color_intensidad(int_neu)

            int_pos_str = f"{int_pos:.2f}" if int_pos and not pd.isna(int_pos) else "N/A"
            int_neg_str = f"{int_neg:.2f}" if int_neg and not pd.isna(int_neg) else "N/A"
            int_neu_str = f"{int_neu:.2f}" if int_neu and not pd.isna(int_neu) else "N/A"

            html += f"""
                <h4 style="margin: 15px 0 10px 0; color: #34495e;">Distribución de Sentimientos:</h4>
                <table style="width: 100%; border-collapse: collapse;">
                    <tr style="background: {bg_pos};">
                        <td style="padding: 8px;"><strong>Positivos:</strong> {positivos:,} ({pct_pos:.1f}%)</td>
                        <td style="padding: 8px;"><em>Intensidad: {int_pos_str}</em></td>
                    </tr>
                    <tr style="background: {bg_neg};">
                        <td style="padding: 8px;"><strong>Negativos:</strong> {negativos:,} ({pct_neg:.1f}%)</td>
                        <td style="padding: 8px;"><em>Intensidad: {int_neg_str}</em></td>
                    </tr>
                    <tr style="background: {bg_neu};">
                        <td style="padding: 8px;"><strong>Neutrales:</strong> {neutrales:,} ({pct_neu:.1f}%)</td>
                        <td style="padding: 8px;"><em>Intensidad: {int_neu_str}</em></td>
                    </tr>
                </table>
"""

        html += """
            </div>
        </div>
"""

    html += """
    </div>
"""

    return html


def generar_cards_confianza(df_resumen):
    """
    Genera cards HTML con porcentajes de confianza de categorización y sentimiento

    Args:
        df_resumen: DataFrame con confianza_categoria y confianza_sentimiento

    Returns:
        String HTML con dos cards de confianza
    """
    # Calcular promedios ponderados por total de registros
    total_registros = df_resumen['total'].sum()

    # Confianza categorización
    confianza_cat = (df_resumen['confianza_categoria'] * df_resumen['total']).sum() / total_registros
    pct_cat = confianza_cat * 100

    # Confianza sentimiento
    confianza_sent = (df_resumen['confianza_sentimiento'] * df_resumen['total']).sum() / total_registros
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


def generar_tabla_comparativa_mes_anterior(mes_anio, df_resumen_actual, df_resumen_anterior):
    """
    Genera tabla HTML comparando métricas del mes actual vs mes anterior

    Args:
        mes_anio: String 'YYYY-MM' mes actual
        df_resumen_actual: DataFrame con resumen del mes actual
        df_resumen_anterior: DataFrame con resumen del mes anterior (puede ser None)

    Returns: HTML string
    """
    if df_resumen_anterior is None or df_resumen_anterior.empty:
        return """
        <div style="margin: 30px 0; padding: 20px; background: #e8f4f8; border-left: 4px solid #3498db; border-radius: 4px;">
            <p style="margin: 0; color: #2c3e50;"><strong>ℹ️ Comparación Mensual:</strong> No hay datos del mes anterior para comparar.</p>
        </div>
        """

    html = """
    <div style="margin: 30px 0;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            Comparación con Mes Anterior
        </h3>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 15px;">
            <thead>
                <tr style="background: #2c3e50; color: white;">
                    <th style="padding: 12px; text-align: left;">Canal - Métrica</th>
                    <th style="padding: 12px; text-align: right;">Mes Actual</th>
                    <th style="padding: 12px; text-align: right;">Mes Anterior</th>
                    <th style="padding: 12px; text-align: right;">Variación</th>
                    <th style="padding: 12px; text-align: right;">% Cambio</th>
                    <th style="padding: 12px; text-align: right;">Score Actual</th>
                    <th style="padding: 12px; text-align: right;">Score Anterior</th>
                </tr>
            </thead>
            <tbody>
    """

    # Merge datos actual con anterior
    for _, row_actual in df_resumen_actual.iterrows():
        canal = row_actual['canal']
        metrica = row_actual['metrica']

        # Buscar correspondiente en mes anterior
        row_anterior = df_resumen_anterior[
            (df_resumen_anterior['canal'] == canal) &
            (df_resumen_anterior['metrica'] == metrica)
        ]

        total_actual = int(row_actual['total'])
        score_actual = row_actual['promedio_score']

        if not row_anterior.empty:
            total_anterior = int(row_anterior.iloc[0]['total'])
            score_anterior = row_anterior.iloc[0]['promedio_score']

            variacion = total_actual - total_anterior
            cambio_pct = (variacion / total_anterior * 100) if total_anterior > 0 else 0

            # Color según cambio
            if cambio_pct > 10:
                color_cambio = '#27ae60'
                icono = '▲'
            elif cambio_pct < -10:
                color_cambio = '#c0392b'
                icono = '▼'
            else:
                color_cambio = '#7f8c8d'
                icono = '→'

            cambio_str = f'<span style="color: {color_cambio};">{icono} {cambio_pct:+.1f}%</span>'
            variacion_str = f'{variacion:+,}'

            # Color score según métrica
            if metrica == 'NPS':
                color_score_actual = '#27ae60' if score_actual >= 7 else '#c0392b' if score_actual < 6 else '#7f8c8d'
                color_score_anterior = '#27ae60' if score_anterior >= 7 else '#c0392b' if score_anterior < 6 else '#7f8c8d'
            else:  # CSAT
                color_score_actual = '#27ae60' if score_actual >= 4 else '#c0392b' if score_actual < 3 else '#7f8c8d'
                color_score_anterior = '#27ae60' if score_anterior >= 4 else '#c0392b' if score_anterior < 3 else '#7f8c8d'
        else:
            # No hay datos anteriores
            variacion_str = '-'
            cambio_str = '-'
            score_anterior = None
            color_score_actual = '#7f8c8d'
            color_score_anterior = '#7f8c8d'

        html += f"""
                <tr style="border-bottom: 1px solid #e0e0e0;">
                    <td style="padding: 12px;"><strong>{canal} - {metrica}</strong></td>
                    <td style="padding: 12px; text-align: right;">{total_actual:,}</td>
                    <td style="padding: 12px; text-align: right;">{total_anterior:,}</td>
                    <td style="padding: 12px; text-align: right;">{variacion_str}</td>
                    <td style="padding: 12px; text-align: right;">{cambio_str}</td>
                    <td style="padding: 12px; text-align: right;"><strong style="color: {color_score_actual};">{score_actual:.2f}</strong></td>
                    <td style="padding: 12px; text-align: right;"><strong style="color: {color_score_anterior};">{ f'{score_anterior:.2f}' if score_anterior is not None else '-'}</strong></td>
                </tr>
        """

    html += """
            </tbody>
        </table>
    </div>
    """

    return html


def generar_tabla_sentimientos_detallada(df_categorias, df_emociones):
    """
    Genera tabla HTML exclusiva de sentimientos con intensidad, ofensivos y emociones

    Args:
        df_categorias: DataFrame con categorías y sentimientos
        df_emociones: DataFrame con emociones del mes

    Returns: HTML string
    """
    # Calcular totales por sentimiento
    total_positivos = int(df_categorias['positivos'].sum())
    total_negativos = int(df_categorias['negativos'].sum())
    total_neutrales = int(df_categorias['neutrales'].sum())
    total_ofensivos = int(df_categorias['ofensivos'].sum())
    total_general = total_positivos + total_negativos + total_neutrales

    html = """
    <div style="margin: 30px 0;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            Análisis Detallado de Sentimientos y Emociones
        </h3>

        <!-- Resumen General -->
        <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 15px; margin: 20px 0;">
            <div style="background: #e8f5e9; border-left: 4px solid #27ae60; padding: 15px; border-radius: 4px;">
                <div style="font-size: 11px; color: #7f8c8d; text-transform: uppercase;">Positivos</div>
                <div style="font-size: 28px; font-weight: 600; color: #27ae60; margin: 8px 0;">{:,}</div>
                <div style="font-size: 12px; color: #7f8c8d;">{:.1f}%</div>
            </div>
            <div style="background: #fdecea; border-left: 4px solid #c0392b; padding: 15px; border-radius: 4px;">
                <div style="font-size: 11px; color: #7f8c8d; text-transform: uppercase;">Negativos</div>
                <div style="font-size: 28px; font-weight: 600; color: #c0392b; margin: 8px 0;">{:,}</div>
                <div style="font-size: 12px; color: #7f8c8d;">{:.1f}%</div>
            </div>
            <div style="background: #ecf0f1; border-left: 4px solid #95a5a6; padding: 15px; border-radius: 4px;">
                <div style="font-size: 11px; color: #7f8c8d; text-transform: uppercase;">Neutrales</div>
                <div style="font-size: 28px; font-weight: 600; color: #95a5a6; margin: 8px 0;">{:,}</div>
                <div style="font-size: 12px; color: #7f8c8d;">{:.1f}%</div>
            </div>
            <div style="background: #fff3cd; border-left: 4px solid #f39c12; padding: 15px; border-radius: 4px;">
                <div style="font-size: 11px; color: #7f8c8d; text-transform: uppercase;">Ofensivos</div>
                <div style="font-size: 28px; font-weight: 600; color: #f39c12; margin: 8px 0;">{:,}</div>
                <div style="font-size: 12px; color: #7f8c8d;">{:.1f}%</div>
            </div>
        </div>
    """.format(
        total_positivos, (total_positivos/total_general*100) if total_general > 0 else 0,
        total_negativos, (total_negativos/total_general*100) if total_general > 0 else 0,
        total_neutrales, (total_neutrales/total_general*100) if total_general > 0 else 0,
        total_ofensivos, (total_ofensivos/total_general*100) if total_general > 0 else 0
    )

    # Tabla de emociones
    if not df_emociones.empty:
        html += """
        <h4 style="color: #2c3e50; margin-top: 30px; padding: 10px 0; border-bottom: 1px solid #e0e0e0;">
            Distribución por Emoción
        </h4>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 15px;">
            <thead>
                <tr style="background: #f8f9fa; border-bottom: 2px solid #dee2e6;">
                    <th style="padding: 10px; text-align: left;">Emoción</th>
                    <th style="padding: 10px; text-align: right;">Total</th>
                    <th style="padding: 10px; text-align: right;">%</th>
                    <th style="padding: 10px; text-align: right;">Intensidad Promedio</th>
                    <th style="padding: 10px; text-align: right;">Muy Intensas (>0.8)</th>
                    <th style="padding: 10px; text-align: right;">Score Promedio</th>
                </tr>
            </thead>
            <tbody>
        """

        total_emociones = df_emociones['total'].sum()
        for _, row in df_emociones.iterrows():
            emocion = row['emocion']
            total = int(row['total'])
            intensidad = row['intensidad_promedio']
            muy_intensas = int(row['muy_intensas'])
            score = row['score_promedio']
            pct = (total / total_emociones * 100) if total_emociones > 0 else 0

            # Color según intensidad
            if intensidad >= 0.7:
                bg_color = '#e8f5e9'
            elif intensidad >= 0.5:
                bg_color = '#fff9e6'
            else:
                bg_color = '#fdecea'

            html += f"""
                <tr style="border-bottom: 1px solid #f0f0f0; background: {bg_color};">
                    <td style="padding: 10px;"><strong>{emocion}</strong></td>
                    <td style="padding: 10px; text-align: right;">{total:,}</td>
                    <td style="padding: 10px; text-align: right;">{pct:.1f}%</td>
                    <td style="padding: 10px; text-align: right;"><strong>{intensidad:.3f}</strong></td>
                    <td style="padding: 10px; text-align: right;">{muy_intensas:,}</td>
                    <td style="padding: 10px; text-align: right;">{score:.2f}</td>
                </tr>
            """

        html += """
            </tbody>
        </table>
        """

    html += """
    </div>
    """

    return html


def generar_grafica_oportunidades_d3(df_categorias, top_n=20):
    """
    Genera gráfica D3.js scatter plot de categorías mostrando oportunidades y críticos
    Eje X: Score promedio
    Eje Y: % Negativos

    Args:
        df_categorias: DataFrame con categorías, scores y sentimientos
        top_n: Número de categorías a mostrar

    Returns: HTML string con gráfica D3
    """
    # Preparar datos: calcular % negativos y scores por categoría
    df_viz = df_categorias.groupby('categoria').agg({
        'total': 'sum',
        'positivos': 'sum',
        'negativos': 'sum',
        'neutrales': 'sum',
        'score_promedio': 'mean'
    }).reset_index()

    df_viz['pct_negativos'] = (df_viz['negativos'] / df_viz['total'] * 100).round(1)
    df_viz = df_viz.nlargest(top_n, 'total')

    # Convertir a JSON para D3
    datos_json = df_viz[['categoria', 'total', 'score_promedio', 'pct_negativos']].to_dict(orient='records')

    html = f"""
    <div style="margin: 30px 0;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            Matriz de Oportunidades y Temas Críticos
        </h3>
        <p style="color: #7f8c8d; font-size: 13px; margin: 10px 0;">
            Categorías posicionadas por Score vs % Negativos. <strong style="color: #c0392b;">Críticos</strong> (alto % negativos + bajo score),
            <strong style="color: #f39c12;">Oportunidad</strong> (bajo score + bajo % negativos),
            <strong style="color: #27ae60;">Fortaleza</strong> (alto score + bajo % negativos)
        </p>
        <div id="scatter-oportunidades" style="margin: 20px 0;"></div>
    </div>

    <script>
        const datosOportunidades = {json.dumps(datos_json)};

        // Configuración del gráfico
        const marginScatter = {{top: 40, right: 20, bottom: 60, left: 60}};
        const widthScatter = 1000 - marginScatter.left - marginScatter.right;
        const heightScatter = 500 - marginScatter.top - marginScatter.bottom;

        const svgScatter = d3.select('#scatter-oportunidades')
            .append('svg')
            .attr('width', widthScatter + marginScatter.left + marginScatter.right)
            .attr('height', heightScatter + marginScatter.top + marginScatter.bottom)
            .append('g')
            .attr('transform', `translate(${{marginScatter.left}},${{marginScatter.top}})`);

        // Escalas
        const xScaleScatter = d3.scaleLinear()
            .domain([0, d3.max(datosOportunidades, d => d.score_promedio) * 1.1])
            .range([0, widthScatter]);

        const yScaleScatter = d3.scaleLinear()
            .domain([0, d3.max(datosOportunidades, d => d.pct_negativos) * 1.1])
            .range([heightScatter, 0]);

        const sizeScale = d3.scaleSqrt()
            .domain([0, d3.max(datosOportunidades, d => d.total)])
            .range([5, 30]);

        // Función de color basada en cuadrante
        function getColor(score, pctNeg) {{
            if (pctNeg > 30 && score < 5) return '#c0392b';  // Crítico
            if (pctNeg < 20 && score < 5) return '#f39c12';  // Oportunidad
            if (pctNeg < 20 && score >= 5) return '#27ae60'; // Fortaleza
            return '#3498db';  // Neutral
        }}

        // Líneas de referencia
        svgScatter.append('line')
            .attr('x1', xScaleScatter(5))
            .attr('x2', xScaleScatter(5))
            .attr('y1', 0)
            .attr('y2', heightScatter)
            .attr('stroke', '#bdc3c7')
            .attr('stroke-dasharray', '5,5')
            .attr('stroke-width', 1);

        svgScatter.append('line')
            .attr('x1', 0)
            .attr('x2', widthScatter)
            .attr('y1', yScaleScatter(30))
            .attr('y2', yScaleScatter(30))
            .attr('stroke', '#bdc3c7')
            .attr('stroke-dasharray', '5,5')
            .attr('stroke-width', 1);

        // Tooltip
        const tooltipScatter = d3.select('body').append('div')
            .style('position', 'absolute')
            .style('padding', '10px')
            .style('background', 'rgba(44, 62, 80, 0.95)')
            .style('color', 'white')
            .style('border-radius', '4px')
            .style('font-size', '12px')
            .style('pointer-events', 'none')
            .style('opacity', 0);

        // Círculos
        svgScatter.selectAll('circle')
            .data(datosOportunidades)
            .enter()
            .append('circle')
            .attr('cx', d => xScaleScatter(d.score_promedio))
            .attr('cy', d => yScaleScatter(d.pct_negativos))
            .attr('r', d => sizeScale(d.total))
            .attr('fill', d => getColor(d.score_promedio, d.pct_negativos))
            .attr('opacity', 0.7)
            .attr('stroke', 'white')
            .attr('stroke-width', 2)
            .on('mouseover', function(event, d) {{
                tooltipScatter
                    .style('opacity', 1)
                    .html(`
                        <strong>${{d.categoria.substring(0, 40)}}</strong><br/>
                        Score: ${{d.score_promedio.toFixed(2)}}<br/>
                        % Negativos: ${{d.pct_negativos.toFixed(1)}}%<br/>
                        Total: ${{d.total.toLocaleString()}}
                    `);
                d3.select(this)
                    .attr('opacity', 1)
                    .attr('stroke-width', 3);
            }})
            .on('mousemove', function(event) {{
                tooltipScatter
                    .style('left', (event.pageX + 15) + 'px')
                    .style('top', (event.pageY - 15) + 'px');
            }})
            .on('mouseout', function() {{
                tooltipScatter.style('opacity', 0);
                d3.select(this)
                    .attr('opacity', 0.7)
                    .attr('stroke-width', 2);
            }});

        // Ejes
        svgScatter.append('g')
            .attr('transform', `translate(0,${{heightScatter}})`)
            .call(d3.axisBottom(xScaleScatter))
            .style('font-size', '11px');

        svgScatter.append('g')
            .call(d3.axisLeft(yScaleScatter))
            .style('font-size', '11px');

        // Etiquetas de ejes
        svgScatter.append('text')
            .attr('x', widthScatter / 2)
            .attr('y', heightScatter + 45)
            .attr('text-anchor', 'middle')
            .style('font-size', '12px')
            .style('fill', '#7f8c8d')
            .text('Score Promedio');

        svgScatter.append('text')
            .attr('transform', 'rotate(-90)')
            .attr('x', -heightScatter / 2)
            .attr('y', -45)
            .attr('text-anchor', 'middle')
            .style('font-size', '12px')
            .style('fill', '#7f8c8d')
            .text('% Comentarios Negativos');

        // Leyenda de cuadrantes
        const legendData = [
            {{label: 'Crítico (Alto % Neg + Bajo Score)', color: '#c0392b'}},
            {{label: 'Oportunidad (Bajo % Neg + Bajo Score)', color: '#f39c12'}},
            {{label: 'Fortaleza (Bajo % Neg + Alto Score)', color: '#27ae60'}},
            {{label: 'Neutral', color: '#3498db'}}
        ];

        const legend = svgScatter.append('g')
            .attr('transform', `translate(${{widthScatter - 250}}, 10)`);

        legendData.forEach((item, i) => {{
            const g = legend.append('g')
                .attr('transform', `translate(0, ${{i * 20}})`);

            g.append('circle')
                .attr('cx', 0)
                .attr('cy', 0)
                .attr('r', 6)
                .attr('fill', item.color)
                .attr('opacity', 0.7);

            g.append('text')
                .attr('x', 12)
                .attr('y', 4)
                .style('font-size', '10px')
                .style('fill', '#2c3e50')
                .text(item.label);
        }});
    </script>
    """

    return html


def generar_tabla_mensajes_largos(df_largos, limit=30, min_chars=50):
    """
    Genera tabla HTML con mensajes largos mostrando calificación y sentimiento

    Args:
        df_largos: DataFrame con mensajes largos
        limit: Número máximo de mensajes a mostrar
        min_chars: Longitud mínima de caracteres

    Returns: HTML string
    """
    # Filtrar por longitud mínima y limitar
    df_filtered = df_largos[df_largos['longitud_motivo'] >= min_chars].head(limit)

    html = f"""
    <div style="margin: 30px 0;">
        <h3 style="color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 8px;">
            Mensajes Extensos ({limit} mensajes más largos >={min_chars} caracteres)
        </h3>
        <p style="color: #7f8c8d; font-size: 13px; margin: 10px 0;">
            Comentarios detallados que requieren atención especial por su extensión y contenido.
        </p>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px; margin-top: 15px;">
            <thead>
                <tr style="background: #2c3e50; color: white;">
                    <th style="padding: 10px; text-align: left; width: 50%;">Comentario</th>
                    <th style="padding: 10px; text-align: center;">Canal</th>
                    <th style="padding: 10px; text-align: center;">Métrica</th>
                    <th style="padding: 10px; text-align: center;">Score</th>
                    <th style="padding: 10px; text-align: center;">Sentimiento</th>
                    <th style="padding: 10px; text-align: center;">Intensidad</th>
                    <th style="padding: 10px; text-align: right;">Caracteres</th>
                </tr>
            </thead>
            <tbody>
    """

    for idx, row in df_filtered.iterrows():
        motivo = row['motivo_texto'][:200] + '...' if len(row['motivo_texto']) > 200 else row['motivo_texto']
        canal = row['canal']
        metrica = row['metrica']
        score = row['score']
        sentimiento = row['sentimiento']
        intensidad = row.get('intensidad_emocional', 0)
        longitud = int(row['longitud_motivo'])

        # Color según score
        if metrica == 'NPS':
            color_score = '#27ae60' if score >= 7 else '#c0392b' if score <= 6 else '#7f8c8d'
        else:  # CSAT
            color_score = '#27ae60' if score >= 4 else '#c0392b' if score < 3 else '#7f8c8d'

        # Color según sentimiento
        if sentimiento == 'POSITIVO':
            color_sent = '#27ae60'
            bg_sent = '#e8f5e9'
        elif sentimiento == 'NEGATIVO':
            color_sent = '#c0392b'
            bg_sent = '#fdecea'
        else:
            color_sent = '#95a5a6'
            bg_sent = '#ecf0f1'

        # Background altern ado
        bg_row = '#fafafa' if idx % 2 == 0 else 'white'

        html += f"""
            <tr style="border-bottom: 1px solid #e0e0e0; background: {bg_row};">
                <td style="padding: 10px; line-height: 1.4;"><em>{motivo}</em></td>
                <td style="padding: 10px; text-align: center;"><strong>{canal}</strong></td>
                <td style="padding: 10px; text-align: center;"><strong>{metrica}</strong></td>
                <td style="padding: 10px; text-align: center;"><strong style="color: {color_score};">{score:.0f}</strong></td>
                <td style="padding: 10px; text-align: center;">
                    <span style="background: {bg_sent}; color: {color_sent}; padding: 4px 8px; border-radius: 3px; font-size: 11px; font-weight: 600;">
                        {sentimiento}
                    </span>
                </td>
                <td style="padding: 10px; text-align: center;">{intensidad:.2f}</td>
                <td style="padding: 10px; text-align: right; color: #7f8c8d;">{longitud}</td>
            </tr>
        """

    html += """
            </tbody>
        </table>
    </div>
    """

    return html


def generar_html_mensual(mes_anio, df_resumen, df_resumen_anterior, df_tabla_metricas, df_categorias, df_emociones, df_largos, graficas_html, imagenes_paths):
    """
    Genera HTML consolidado con todas las gráficas e imágenes embebidas

    Args:
        mes_anio: String 'YYYY-MM'
        df_resumen: DataFrame con resumen general
        df_resumen_anterior: DataFrame con resumen del mes anterior (puede ser None)
        df_tabla_metricas: DataFrame con métricas detalladas
        df_categorias: DataFrame con categorías y sentimientos
        df_emociones: DataFrame con emociones
        df_largos: DataFrame con mensajes largos
        graficas_html: Dict con HTML de gráficas Plotly
        imagenes_paths: Dict con paths de imágenes estáticas

    Returns: HTML string
    """
    fecha_generacion = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # Convertir imágenes a base64
    imgs_b64 = {}
    for key, path in imagenes_paths.items():
        if path and Path(path).exists():
            imgs_b64[key] = imagen_to_base64(path)

    # Calcular totales
    total_registros = int(df_resumen['total'].sum())
    total_con_texto = int(df_resumen['con_texto'].sum())
    total_categorizados = int(df_resumen['categorizados'].sum())
    total_sentimientos = int(df_resumen['con_sentimiento'].sum())

    # Generar nuevas secciones HTML
    cards_confianza = generar_cards_confianza(df_resumen)
    tabla_comparativa = generar_tabla_comparativa_mes_anterior(mes_anio, df_resumen, df_resumen_anterior)
    tabla_sentimientos = generar_tabla_sentimientos_detallada(df_categorias, df_emociones)
    grafica_oportunidades = generar_grafica_oportunidades_d3(df_categorias)
    tabla_mensajes_largos = generar_tabla_mensajes_largos(df_largos, limit=30, min_chars=50)

    html = f"""
<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Informe Mensual {mes_anio} - NPS/CSAT</title>
    <script src="https://cdn.plot.ly/plotly-2.26.0.min.js"></script>
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
        .seccion {{
            margin: 30px 0;
            padding: 20px;
            background: #fafafa;
            border-radius: 5px;
        }}
        .imagen-estatica {{
            margin: 30px 0;
            text-align: center;
        }}
        .imagen-estatica img {{
            max-width: 100%;
            border-radius: 5px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.15);
        }}
        .footer {{
            text-align: center;
            margin-top: 50px;
            padding: 20px;
            color: #7f8c8d;
            font-size: 12px;
            border-top: 1px solid #ddd;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>INFORME MENSUAL NPS/CSAT - {mes_anio}</h1>
        <div class="fecha">Generado: {fecha_generacion}</div>

        <!-- TABLA DE MÉTRICAS CONSOLIDADAS -->
        {generar_tabla_metricas_html(df_tabla_metricas)}

        <!-- COMPARACIÓN CON MES ANTERIOR -->
        {tabla_comparativa}

        <!-- KPIs Resumen -->
        <div class="kpis">
            <div class="kpi">
                <div class="kpi-label">Total Registros</div>
                <div class="kpi-valor">{total_registros:,}</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Con Texto</div>
                <div class="kpi-valor">{total_con_texto:,}</div>
                <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">{(total_con_texto/total_registros*100):.1f}%</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Categorizados</div>
                <div class="kpi-valor">{total_categorizados:,}</div>
                <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">{(total_categorizados/total_registros*100):.1f}%</div>
            </div>
            <div class="kpi">
                <div class="kpi-label">Con Sentimiento</div>
                <div class="kpi-valor">{total_sentimientos:,}</div>
                <div style="font-size: 12px; color: #7f8c8d; margin-top: 5px;">{(total_sentimientos/total_registros*100):.1f}%</div>
            </div>
            {cards_confianza}
        </div>

        <!-- TABLA SENTIMIENTOS DETALLADA -->
        {tabla_sentimientos}

        <!-- Gráficas Interactivas -->
        <h2>Análisis de Volúmenes</h2>
        <div class="seccion">
            {graficas_html.get('volumenes', '')}
        </div>

        <div class="seccion">
            {graficas_html.get('stacked', '')}
        </div>

        <h2>💭 Análisis de Sentimientos</h2>
        <div class="seccion">
            {graficas_html.get('sentimientos', '')}
        </div>

        <h2>🏷️ Análisis de Categorías</h2>
        <div class="seccion">
            {graficas_html.get('categorias_top', '')}
        </div>

        <h2>😊 Análisis de Emociones</h2>
        <div class="seccion">
            {graficas_html.get('emociones_scatter', '')}
        </div>

        <!-- GRÁFICA D3.JS: OPORTUNIDADES Y CRÍTICOS -->
        {grafica_oportunidades}

        <h2>⚠️ Contenido Sensible</h2>
        <div class="seccion">
            {graficas_html.get('tabla_ofensivos', '')}
        </div>

        <!-- Imágenes Estáticas -->
        <h2>📊 Visualizaciones Estáticas (Alta Resolución)</h2>

        {"<div class='imagen-estatica'><h3>NPS/CSAT Interpretado por Categoría</h3><img src='data:image/png;base64," + imgs_b64['nps_csat'] + "' /></div>" if 'nps_csat' in imgs_b64 else ""}

        {"<div class='imagen-estatica'><h3>Heatmap Temporal</h3><img src='data:image/png;base64," + imgs_b64['heatmap'] + "' /></div>" if 'heatmap' in imgs_b64 else ""}

        {"<div class='imagen-estatica'><h3>Matriz de Priorización</h3><img src='data:image/png;base64," + imgs_b64['matriz'] + "' /></div>" if 'matriz' in imgs_b64 else ""}

        <!-- TABLA MENSAJES LARGOS -->
        {tabla_mensajes_largos}

        <div class="footer">
            <p><strong>Informe Mensual Automático - NPS/CSAT Analytics</strong></p>
            <p>Generado por 13_informe_mensual.py | Base de datos: respuestas_nps_csat</p>
        </div>
    </div>
</body>
</html>
"""

    return html


def procesar_mes(mes_anio, output_base_dir):
    """
    Procesa un mes completo: CSVs + Gráficas + HTML

    Args:
        mes_anio: String 'YYYY-MM'
        output_base_dir: Path base para outputs

    Returns: Path del HTML generado
    """
    print(f"\n{'='*70}")
    print(f"Procesando mes: {mes_anio}")
    print(f"{'='*70}\n")

    engine = get_engine()

    # Crear directorio del mes
    mes_dir = Path(output_base_dir) / mes_anio
    mes_dir.mkdir(parents=True, exist_ok=True)

    # 1. Queries
    print("1. Ejecutando queries SQL...")
    df_resumen = query_resumen_mes(engine, mes_anio)
    df_tabla_metricas = query_tabla_metricas_mes(engine, mes_anio)
    df_detalle = query_detalle_mes(engine, mes_anio)
    df_categorias = query_categorias_sentimientos_mes(engine, mes_anio)
    df_emociones = query_emociones_mes(engine, mes_anio)
    df_ofensivos = query_ofensivos_mes(engine, mes_anio)
    df_largos = query_top_largos_mes(engine, mes_anio)
    df_categorias_mes = query_categorias_por_mes(engine)  # Para heatmap temporal

    if df_resumen.empty:
        print(f"[WARN] No hay datos para el mes {mes_anio}")
        engine.dispose()
        return None

    # 2. Exportar Excel (reemplaza CSVs)
    print("2. Exportando datos a Excel...")
    export_excel_mensual(df_detalle, df_tabla_metricas, df_categorias, df_resumen, mes_dir / f'datos_{mes_anio}.xlsx')

    # 3. Gráficas Plotly (HTML strings)
    print("3. Generando gráficas interactivas...")
    graficas_html = {
        'volumenes': grafica_volumenes_comparativa(df_resumen),
        'stacked': grafica_canal_metrica_stacked(df_resumen),
        'sentimientos': grafica_sentimientos_distribucion(df_categorias),
        'categorias_top': grafica_categorias_top_barras(df_categorias),
        'emociones_scatter': grafica_emociones_intensidad_scatter(df_emociones),
        'tabla_ofensivos': tabla_interactiva_ofensivos(df_ofensivos),
        'tabla_largos': tabla_interactiva_largos(df_largos)
    }

    # 4. Imágenes estáticas
    print("4. Generando imágenes estáticas...")
    imagenes_paths = {}

    try:
        imagenes_paths['nps_csat'] = imagen_nps_csat_interpretado(
            df_categorias, mes_dir / 'nps_csat_interpretado.png'
        )
    except Exception as e:
        print(f"[WARN] Error generando imagen NPS/CSAT: {e}")

    try:
        imagenes_paths['heatmap'] = imagen_heatmap_temporal(
            df_categorias_mes[df_categorias_mes['mes_anio'] <= mes_anio],
            mes_dir / 'heatmap_temporal.png'
        )
    except Exception as e:
        print(f"[WARN] Error generando heatmap temporal: {e}")

    try:
        imagenes_paths['matriz'] = imagen_matriz_priorizacion(
            df_categorias, mes_dir / 'matriz_priorizacion.png'
        )
    except Exception as e:
        print(f"[WARN] Error generando matriz de priorización: {e}")

    # 5. Obtener datos del mes anterior (si existe)
    print("5. Obteniendo datos del mes anterior para comparación...")
    try:
        from datetime import datetime
        from dateutil.relativedelta import relativedelta

        # Calcular mes anterior
        fecha_actual = datetime.strptime(mes_anio, '%Y-%m')
        fecha_anterior = fecha_actual - relativedelta(months=1)
        mes_anterior = fecha_anterior.strftime('%Y-%m')

        # Query del mes anterior
        df_resumen_anterior = query_resumen_mes(engine, mes_anterior)
        if df_resumen_anterior.empty:
            print(f"   [INFO] No hay datos del mes anterior ({mes_anterior})")
            df_resumen_anterior = None
        else:
            print(f"   [OK] Datos del mes anterior ({mes_anterior}) obtenidos")
    except Exception as e:
        print(f"   [WARN] Error obteniendo datos del mes anterior: {e}")
        df_resumen_anterior = None

    # 6. HTML consolidado
    print("6. Generando HTML consolidado...")
    html = generar_html_mensual(mes_anio, df_resumen, df_resumen_anterior, df_tabla_metricas, df_categorias, df_emociones, df_largos, graficas_html, imagenes_paths)

    output_html = mes_dir / f'informe_{mes_anio}.html'
    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)

    engine.dispose()

    print(f"\n{'='*70}")
    print(f"[OK] Informe generado exitosamente")
    print(f"     Directorio: {mes_dir}")
    print(f"     HTML: {output_html.name}")
    print(f"     Excel: datos_{mes_anio}.xlsx (4 hojas)")
    print(f"     Imagenes: {len(imagenes_paths)} generadas")
    print(f"{'='*70}\n")

    return output_html


def main():
    parser = argparse.ArgumentParser(
        description='Generador de Informes Mensuales NPS/CSAT',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python 13_informe_mensual.py --mes 06
  python 13_informe_mensual.py --mes 2025-07
  python 13_informe_mensual.py --todos
  python 13_informe_mensual.py --mes 06 --output informes/custom/
        """
    )

    parser.add_argument('--mes', type=str, help='Mes específico (formato: 06 o 2025-06)')
    parser.add_argument('--todos', action='store_true', help='Generar informes para todos los meses disponibles')
    parser.add_argument('--output', type=str, default='informes/mensuales', help='Directorio base de salida')

    args = parser.parse_args()

    if not args.mes and not args.todos:
        parser.error("Debes especificar --mes o --todos")

    print("\n" + "="*70)
    print("GENERADOR DE INFORMES MENSUALES NPS/CSAT")
    print("="*70)

    engine = get_engine()

    if args.todos:
        # Obtener todos los meses disponibles
        meses = query_meses_disponibles(engine)
        print(f"\nMeses disponibles: {len(meses)}")
        for m in meses:
            print(f"  - {m}")
    else:
        # Normalizar formato mes
        mes = args.mes
        if len(mes) == 2:  # Solo número (ej: '06')
            mes = f'2025-{mes}'
        meses = [mes]

    engine.dispose()

    # Procesar cada mes
    for mes in meses:
        try:
            procesar_mes(mes, args.output)
        except Exception as e:
            print(f"\n[ERROR] Error procesando {mes}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print("[OK] Proceso completado")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
