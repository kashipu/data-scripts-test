#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gráficas interactivas HTML usando Plotly
Estilo ejecutivo sobrio - Paleta corporativa limitada
Retornan HTML strings para embeber en reportes
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import numpy as np

# PALETA CORPORATIVA SOBRIA
COLORES = {
    'POSITIVO': '#27ae60',
    'NEGATIVO': '#c0392b',
    'NEUTRAL': '#95a5a6',
    'BM': '#2c3e50',
    'BV': '#34495e',
    'NPS': '#3498db',
    'CSAT': '#2980b9',
    'PRIMARIO': '#2c3e50',
    'SECUNDARIO': '#7f8c8d',
    'ACENTO': '#3498db'
}

# Template de layout sobrio para todas las gráficas
def get_layout_template():
    return {
        'font': {'family': 'Arial, sans-serif', 'size': 11, 'color': '#2c3e50'},
        'plot_bgcolor': 'white',
        'paper_bgcolor': 'white',
        'margin': {'l': 60, 'r': 30, 't': 50, 'b': 50},
        'hovermode': 'closest',
        'showlegend': True,
        'legend': {
            'orientation': 'h',
            'yanchor': 'bottom',
            'y': -0.15,
            'xanchor': 'center',
            'x': 0.5,
            'bgcolor': 'rgba(255,255,255,0)',
            'font': {'size': 10}
        },
        'xaxis': {
            'showgrid': False,
            'showline': True,
            'linecolor': '#bdc3c7',
            'linewidth': 1,
            'tickfont': {'size': 10}
        },
        'yaxis': {
            'showgrid': True,
            'gridcolor': '#ecf0f1',
            'gridwidth': 1,
            'showline': True,
            'linecolor': '#bdc3c7',
            'linewidth': 1,
            'tickfont': {'size': 10}
        }
    }


# =============================================================================
# GRÁFICAS PARA INFORME MENSUAL
# =============================================================================

def grafica_volumenes_comparativa(df_resumen):
    """
    Barras agrupadas - Estilo sobrio ejecutivo
    Solo muestra: Total y Con Texto (simplificado)

    Returns: HTML string
    """
    df_resumen['combinacion'] = df_resumen['canal'] + '-' + df_resumen['metrica']

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Total',
        x=df_resumen['combinacion'],
        y=df_resumen['total'],
        marker_color=COLORES['PRIMARIO'],
        marker_line_color='white',
        marker_line_width=1.5
    ))

    fig.add_trace(go.Bar(
        name='Con Texto',
        x=df_resumen['combinacion'],
        y=df_resumen['con_texto'],
        marker_color=COLORES['ACENTO'],
        marker_line_color='white',
        marker_line_width=1.5
    ))

    layout = get_layout_template()
    layout.update({
        'title': {'text': 'Volúmenes por Canal y Métrica', 'font': {'size': 14, 'color': '#2c3e50'}},
        'xaxis_title': 'Canal - Métrica',
        'yaxis_title': 'Cantidad',
        'barmode': 'group',
        'height': 400
    })

    fig.update_layout(layout)
    return fig.to_html(include_plotlyjs=False, div_id='grafica_volumenes', config={'displayModeBar': False})


def grafica_sentimientos_distribucion(df_sent):
    """
    Barras horizontales de sentimientos - Estilo sobrio

    Args:
        df_sent: DataFrame con canal, metrica, sentimientos

    Returns: HTML string
    """
    # Agrupar por sentimiento
    if 'positivos' in df_sent.columns:
        sent_data = {
            'Positivos': df_sent['positivos'].sum(),
            'Negativos': df_sent['negativos'].sum(),
            'Neutrales': df_sent['neutrales'].sum()
        }
    else:
        sent_data = df_sent.groupby('sentimiento_py')['total'].sum().to_dict()

    labels = list(sent_data.keys())
    values = list(sent_data.values())
    colores = [COLORES.get(label.upper().rstrip('S'), COLORES['NEUTRAL']) for label in labels]

    fig = go.Figure(data=[go.Bar(
        y=labels,
        x=values,
        orientation='h',
        marker_color=colores,
        marker_line_color='white',
        marker_line_width=1.5,
        text=values,
        textposition='outside'
    )])

    layout = get_layout_template()
    layout.update({
        'title': {'text': 'Distribución de Sentimientos', 'font': {'size': 14}},
        'xaxis_title': 'Cantidad',
        'yaxis_title': '',
        'height': 300,
        'showlegend': False
    })

    fig.update_layout(layout)
    return fig.to_html(include_plotlyjs=False, div_id='grafica_sentimientos', config={'displayModeBar': False})


def grafica_canal_metrica_stacked(df_resumen):
    """
    Barras stacked mostrando distribución por canal/métrica

    Returns: HTML string
    """
    df_resumen['combinacion'] = df_resumen['canal'] + '-' + df_resumen['metrica']

    fig = go.Figure()

    # Con texto
    fig.add_trace(go.Bar(
        name='Con Texto',
        x=df_resumen['combinacion'],
        y=df_resumen['con_texto'],
        marker_color='#3498db',
        text=df_resumen['con_texto'],
        textposition='inside'
    ))

    # Sin texto
    fig.add_trace(go.Bar(
        name='Sin Texto',
        x=df_resumen['combinacion'],
        y=df_resumen['sin_texto'],
        marker_color='#ecf0f1',
        text=df_resumen['sin_texto'],
        textposition='inside'
    ))

    fig.update_layout(
        title='Composición de Datos: Con Texto vs Sin Texto',
        xaxis_title='Canal - Métrica',
        yaxis_title='Cantidad',
        barmode='stack',
        height=450,
        template='plotly_white'
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_stacked')


def grafica_categorias_top_barras(df_categorias, top_n=15):
    """
    Barras horizontales con top categorías (sentimientos en stack)

    Returns: HTML string
    """
    df_top = df_categorias.head(top_n).sort_values('total', ascending=True)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name='Positivos',
        y=df_top['categoria'],
        x=df_top['positivos'],
        orientation='h',
        marker_color=COLORES['POSITIVO'],
        text=df_top['positivos'],
        textposition='inside'
    ))

    fig.add_trace(go.Bar(
        name='Negativos',
        y=df_top['categoria'],
        x=df_top['negativos'],
        orientation='h',
        marker_color=COLORES['NEGATIVO'],
        text=df_top['negativos'],
        textposition='inside'
    ))

    fig.add_trace(go.Bar(
        name='Neutrales',
        y=df_top['categoria'],
        x=df_top['neutrales'],
        orientation='h',
        marker_color=COLORES['NEUTRAL'],
        text=df_top['neutrales'],
        textposition='inside'
    ))

    fig.update_layout(
        title=f'Top {top_n} Categorías con Distribución de Sentimientos',
        xaxis_title='Cantidad',
        yaxis_title='Categoría',
        barmode='stack',
        height=600,
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_categorias_top')


def grafica_emociones_intensidad_scatter(df_emociones):
    """
    Scatter plot: Score promedio vs Intensidad emocional (tamaño = volumen)

    Returns: HTML string
    """
    if df_emociones.empty:
        return '<p>No hay datos de emociones para visualizar.</p>'

    fig = px.scatter(
        df_emociones,
        x='score_promedio',
        y='intensidad_promedio',
        size='total',
        color='emocion',
        hover_data=['emocion', 'total', 'muy_intensas'],
        labels={
            'score_promedio': 'Score Promedio',
            'intensidad_promedio': 'Intensidad Emocional',
            'total': 'Volumen',
            'emocion': 'Emoción'
        },
        title='Relación entre Score e Intensidad Emocional'
    )

    fig.update_layout(
        height=500,
        template='plotly_white'
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_emociones_scatter')


def grafica_heatmap_emocion_categoria(df_cruces):
    """
    Heatmap: Emoción x Categoría

    Args:
        df_cruces: DataFrame con categoria, emocion, total

    Returns: HTML string
    """
    if df_cruces.empty or 'emocion' not in df_cruces.columns:
        return '<p>No hay datos suficientes para el heatmap emoción-categoría.</p>'

    # Pivotar datos
    df_pivot = df_cruces.pivot_table(
        index='categoria',
        columns='emocion',
        values='total',
        fill_value=0
    )

    # Top 10 categorías
    top_cats = df_pivot.sum(axis=1).nlargest(10).index
    df_pivot = df_pivot.loc[top_cats]

    fig = go.Figure(data=go.Heatmap(
        z=df_pivot.values,
        x=df_pivot.columns,
        y=df_pivot.index,
        colorscale='YlOrRd',
        text=df_pivot.values,
        texttemplate='%{text}',
        textfont={'size': 10},
        colorbar=dict(title='Volumen')
    ))

    fig.update_layout(
        title='Heatmap: Top 10 Categorías x Emoción',
        xaxis_title='Emoción',
        yaxis_title='Categoría',
        height=500,
        template='plotly_white'
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_heatmap_emocion')


def tabla_interactiva_ofensivos(df_ofensivos, top_n=20):
    """
    Tabla HTML interactiva con motivos ofensivos

    Returns: HTML string
    """
    if df_ofensivos.empty:
        return '<p>No se detectaron mensajes ofensivos en este período.</p>'

    df_top = df_ofensivos.head(top_n).copy()

    # Truncar texto largo
    df_top['motivo_corto'] = df_top['motivo_texto'].apply(lambda x: (x[:100] + '...') if len(str(x)) > 100 else x)

    html = f"""
    <div style="overflow-x: auto;">
        <h4>Top {top_n} Mensajes Ofensivos Detectados</h4>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
            <thead>
                <tr style="background: #e74c3c; color: white;">
                    <th style="padding: 8px; text-align: left;">Canal</th>
                    <th style="padding: 8px; text-align: left;">Métrica</th>
                    <th style="padding: 8px; text-align: left;">Motivo (parcial)</th>
                    <th style="padding: 8px; text-align: left;">Categoría</th>
                    <th style="padding: 8px; text-align: right;">Score</th>
                    <th style="padding: 8px; text-align: right;">Intensidad</th>
                </tr>
            </thead>
            <tbody>
"""

    for _, row in df_top.iterrows():
        intensidad = f"{row['intensidad_emocional']:.2f}" if pd.notna(row.get('intensidad_emocional')) else '-'
        html += f"""
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 8px;">{row['canal']}</td>
                    <td style="padding: 8px;">{row['metrica']}</td>
                    <td style="padding: 8px;">{row['motivo_corto']}</td>
                    <td style="padding: 8px;">{row['categoria'] if pd.notna(row['categoria']) else '-'}</td>
                    <td style="padding: 8px; text-align: right;">{row['score']}</td>
                    <td style="padding: 8px; text-align: right;">{intensidad}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>
"""

    return html


def tabla_interactiva_largos(df_largos):
    """
    Tabla HTML con los mensajes más largos

    Returns: HTML string
    """
    if df_largos.empty:
        return '<p>No hay datos de longitud de mensajes.</p>'

    html = """
    <div style="overflow-x: auto;">
        <h4>Top 10 Mensajes Más Largos del Mes</h4>
        <table style="width: 100%; border-collapse: collapse; font-size: 12px;">
            <thead>
                <tr style="background: #3498db; color: white;">
                    <th style="padding: 8px; text-align: left;">Canal</th>
                    <th style="padding: 8px; text-align: left;">Motivo (parcial)</th>
                    <th style="padding: 8px; text-align: right;">Longitud</th>
                    <th style="padding: 8px; text-align: left;">Categoría</th>
                    <th style="padding: 8px; text-align: left;">Sentimiento</th>
                    <th style="padding: 8px; text-align: right;">Score</th>
                </tr>
            </thead>
            <tbody>
"""

    for _, row in df_largos.iterrows():
        motivo_corto = (row['motivo_texto'][:80] + '...') if len(str(row['motivo_texto'])) > 80 else row['motivo_texto']

        html += f"""
                <tr style="border-bottom: 1px solid #ddd;">
                    <td style="padding: 8px;">{row['canal']}-{row['metrica']}</td>
                    <td style="padding: 8px;">{motivo_corto}</td>
                    <td style="padding: 8px; text-align: right; font-weight: bold;">{int(row['longitud_motivo'])}</td>
                    <td style="padding: 8px;">{row['categoria'] if pd.notna(row['categoria']) else '-'}</td>
                    <td style="padding: 8px;">{row['sentimiento'] if pd.notna(row['sentimiento']) else '-'}</td>
                    <td style="padding: 8px; text-align: right;">{row['score']}</td>
                </tr>
"""

    html += """
            </tbody>
        </table>
    </div>
"""

    return html


# =============================================================================
# GRÁFICAS PARA INFORME CONSOLIDADO
# =============================================================================

def grafica_timeline_volumenes(df_evolucion, anomalias=None):
    """
    Line chart con evolución temporal de volúmenes (con bandas de anomalías)

    Args:
        df_evolucion: DataFrame con mes_anio, canal, metrica, total
        anomalias: Lista de dicts con anomalías de volumen

    Returns: HTML string
    """
    fig = go.Figure()

    # Línea por cada canal-métrica
    for (canal, metrica), df_grupo in df_evolucion.groupby(['canal', 'metrica']):
        df_grupo = df_grupo.sort_values('mes_anio')

        fig.add_trace(go.Scatter(
            x=df_grupo['mes_anio'],
            y=df_grupo['total'],
            mode='lines+markers',
            name=f'{canal}-{metrica}',
            line=dict(width=2),
            marker=dict(size=8)
        ))

    # Marcar anomalías si existen
    if anomalias:
        for a in anomalias:
            fig.add_vline(
                x=a['mes'],
                line_dash='dash',
                line_color='red' if a['tipo'] == 'pico' else 'orange',
                annotation_text=f"{a['tipo']}: {a['volumen']:,}",
                annotation_position='top'
            )

    fig.update_layout(
        title='Evolución Temporal de Volúmenes por Canal y Métrica',
        xaxis_title='Mes',
        yaxis_title='Cantidad de Registros',
        height=500,
        template='plotly_white',
        legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='right', x=1)
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_timeline_vol')


def grafica_timeline_sentimientos(df_sentimientos):
    """
    Área stacked con evolución de sentimientos por mes

    Returns: HTML string
    """
    # Pivotar datos
    df_pivot = df_sentimientos.pivot_table(
        index='mes_anio',
        columns='sentimiento',
        values='total',
        fill_value=0
    ).reset_index()

    df_pivot = df_pivot.sort_values('mes_anio')

    fig = go.Figure()

    for sent in ['POSITIVO', 'NEUTRAL', 'NEGATIVO']:
        if sent in df_pivot.columns:
            fig.add_trace(go.Scatter(
                x=df_pivot['mes_anio'],
                y=df_pivot[sent],
                mode='lines',
                name=sent,
                stackgroup='one',
                fillcolor=COLORES.get(sent, '#95a5a6')
            ))

    fig.update_layout(
        title='Evolución Temporal de Sentimientos (Área Stacked)',
        xaxis_title='Mes',
        yaxis_title='Cantidad',
        height=500,
        template='plotly_white'
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_timeline_sent')


def grafica_heatmap_categorias_meses(df_categorias_mes, top_n=15):
    """
    Heatmap: Categorías (rows) x Meses (columns)

    Returns: HTML string
    """
    # Pivotar
    df_pivot = df_categorias_mes.pivot_table(
        index='categoria',
        columns='mes_anio',
        values='total',
        fill_value=0
    )

    # Top N categorías por volumen total
    top_cats = df_pivot.sum(axis=1).nlargest(top_n).index
    df_pivot = df_pivot.loc[top_cats]

    fig = go.Figure(data=go.Heatmap(
        z=df_pivot.values,
        x=df_pivot.columns,
        y=df_pivot.index,
        colorscale='YlOrRd',
        text=df_pivot.values,
        texttemplate='%{text}',
        textfont={'size': 9},
        colorbar=dict(title='Volumen')
    ))

    fig.update_layout(
        title=f'Heatmap Temporal: Top {top_n} Categorías por Mes',
        xaxis_title='Mes',
        yaxis_title='Categoría',
        height=600,
        template='plotly_white'
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_heatmap_cat_mes')


def grafica_boxplot_scores_categorias(df_scores, top_n=15):
    """
    Boxplot de distribución de scores por categoría

    Args:
        df_scores: DataFrame con categoria, score (un registro por fila)

    Returns: HTML string
    """
    # Top categorías por volumen
    top_cats = df_scores['categoria'].value_counts().head(top_n).index
    df_top = df_scores[df_scores['categoria'].isin(top_cats)]

    fig = go.Figure()

    for cat in top_cats:
        df_cat = df_top[df_top['categoria'] == cat]

        fig.add_trace(go.Box(
            y=df_cat['score'],
            name=cat,
            boxmean='sd'
        ))

    fig.update_layout(
        title=f'Distribución de Scores por Categoría (Top {top_n})',
        yaxis_title='Score',
        height=600,
        template='plotly_white',
        showlegend=False
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_boxplot_scores')


def grafica_treemap_jerarquico(df_treemap):
    """
    Treemap jerárquico: Canal → Métrica → Categoría

    Returns: HTML string
    """
    # Filtrar categorías pequeñas
    df_treemap = df_treemap[df_treemap['total'] >= 100].copy()

    fig = px.treemap(
        df_treemap,
        path=['canal', 'metrica', 'categoria'],
        values='total',
        color='score_promedio',
        color_continuous_scale='RdYlGn',
        labels={'total': 'Volumen', 'score_promedio': 'Score Promedio'},
        title='Vista Jerárquica: Canal → Métrica → Categoría'
    )

    fig.update_layout(
        height=600,
        template='plotly_white'
    )

    return fig.to_html(include_plotlyjs=False, div_id='grafica_treemap')
