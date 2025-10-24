#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Detección de anomalías estadísticas en datos NPS/CSAT
"""

import pandas as pd
import numpy as np


def detectar_anomalias_volumen(df_evolucion, umbral_sigma=2.0):
    """
    Detecta meses con volumen anómalo (±N desviaciones estándar)

    Args:
        df_evolucion: DataFrame con columnas mes_anio, total
        umbral_sigma: Número de desviaciones estándar (default 2.0)

    Returns:
        Lista de dicts: [{'mes': 'YYYY-MM', 'volumen': int, 'tipo': 'pico'|'caida', 'desviacion': float}]
    """
    anomalias = []

    # Calcular estadísticas globales
    media = df_evolucion['total'].mean()
    std = df_evolucion['total'].std()

    if std == 0:
        return anomalias  # No hay variación

    for _, row in df_evolucion.iterrows():
        volumen = row['total']
        desviacion = (volumen - media) / std

        if abs(desviacion) >= umbral_sigma:
            tipo = 'pico' if desviacion > 0 else 'caida'

            anomalias.append({
                'mes': row['mes_anio'],
                'volumen': int(volumen),
                'tipo': tipo,
                'desviacion': round(desviacion, 2),
                'nivel': 'critico' if abs(desviacion) >= 3 else 'advertencia'
            })

    return anomalias


def detectar_anomalias_sentimientos(df_sentimientos, umbral_cambio=20.0):
    """
    Detecta cambios bruscos en % de sentimientos negativos entre meses

    Args:
        df_sentimientos: DataFrame con mes_anio, sentimiento, total
        umbral_cambio: Cambio mínimo en puntos porcentuales (default 20%)

    Returns:
        Lista de dicts: [{'mes': 'YYYY-MM', 'cambio_pct': float, 'tipo': 'mejora'|'empeoramiento'}]
    """
    anomalias = []

    # Calcular % de negativos por mes
    df_pivot = df_sentimientos.pivot_table(
        index='mes_anio',
        columns='sentimiento',
        values='total',
        fill_value=0
    ).reset_index()

    # Asegurar que existen las columnas
    if 'NEGATIVO' not in df_pivot.columns:
        return anomalias

    df_pivot['total'] = df_pivot.iloc[:, 1:].sum(axis=1)
    df_pivot['pct_negativo'] = (df_pivot['NEGATIVO'] / df_pivot['total'] * 100).round(1)

    # Calcular cambio mes a mes
    df_pivot = df_pivot.sort_values('mes_anio')
    df_pivot['cambio_pct'] = df_pivot['pct_negativo'].diff()

    for _, row in df_pivot.iterrows():
        if pd.isna(row['cambio_pct']):
            continue

        cambio = row['cambio_pct']

        if abs(cambio) >= umbral_cambio:
            tipo = 'empeoramiento' if cambio > 0 else 'mejora'
            nivel = 'critico' if abs(cambio) >= 30 else 'advertencia'

            anomalias.append({
                'mes': row['mes_anio'],
                'pct_negativo_actual': round(row['pct_negativo'], 1),
                'cambio_pct': round(cambio, 1),
                'tipo': tipo,
                'nivel': nivel
            })

    return anomalias


def detectar_anomalias_ofensivos(df_evolucion, umbral_pct=5.0):
    """
    Detecta meses con alto porcentaje de contenido ofensivo

    Args:
        df_evolucion: DataFrame con mes_anio, total, ofensivos
        umbral_pct: Umbral de % ofensivos (default 5%)

    Returns:
        Lista de dicts: [{'mes': 'YYYY-MM', 'pct_ofensivo': float, 'tipo': 'critico'}]
    """
    anomalias = []

    for _, row in df_evolucion.iterrows():
        if row['total'] == 0:
            continue

        pct_ofensivo = (row['ofensivos'] / row['total'] * 100)

        if pct_ofensivo >= umbral_pct:
            nivel = 'critico' if pct_ofensivo >= 10 else 'advertencia'

            anomalias.append({
                'mes': row['mes_anio'],
                'total': int(row['total']),
                'ofensivos': int(row['ofensivos']),
                'pct_ofensivo': round(pct_ofensivo, 1),
                'tipo': 'critico',
                'nivel': nivel
            })

    return anomalias


def detectar_categorias_nuevas_perdidas(df_categorias_mes):
    """
    Detecta categorías que aparecen o desaparecen entre meses

    Args:
        df_categorias_mes: DataFrame con mes_anio, categoria, total

    Returns:
        Lista de dicts: [{'mes': 'YYYY-MM', 'categoria': str, 'tipo': 'nueva'|'perdida'}]
    """
    anomalias = []

    # Agrupar por mes
    meses = sorted(df_categorias_mes['mes_anio'].unique())

    if len(meses) < 2:
        return anomalias  # Necesitamos al menos 2 meses para comparar

    for i in range(1, len(meses)):
        mes_anterior = meses[i-1]
        mes_actual = meses[i]

        cats_anterior = set(df_categorias_mes[df_categorias_mes['mes_anio'] == mes_anterior]['categoria'].unique())
        cats_actual = set(df_categorias_mes[df_categorias_mes['mes_anio'] == mes_actual]['categoria'].unique())

        # Categorías nuevas
        nuevas = cats_actual - cats_anterior
        for cat in nuevas:
            # Filtrar categorías con poco volumen (probablemente ruido)
            volumen = df_categorias_mes[
                (df_categorias_mes['mes_anio'] == mes_actual) &
                (df_categorias_mes['categoria'] == cat)
            ]['total'].sum()

            if volumen >= 50:  # Umbral mínimo
                anomalias.append({
                    'mes': mes_actual,
                    'categoria': cat,
                    'tipo': 'nueva',
                    'volumen': int(volumen),
                    'nivel': 'info'
                })

        # Categorías perdidas (que tenían volumen significativo)
        perdidas = cats_anterior - cats_actual
        for cat in perdidas:
            volumen_anterior = df_categorias_mes[
                (df_categorias_mes['mes_anio'] == mes_anterior) &
                (df_categorias_mes['categoria'] == cat)
            ]['total'].sum()

            if volumen_anterior >= 50:
                anomalias.append({
                    'mes': mes_actual,
                    'categoria': cat,
                    'tipo': 'perdida',
                    'volumen_anterior': int(volumen_anterior),
                    'nivel': 'advertencia'
                })

    return anomalias


def generar_seccion_alertas_html(anomalias_dict):
    """
    Genera sección HTML con alertas visuales

    Args:
        anomalias_dict: Dict con keys 'volumen', 'sentimientos', 'ofensivos', 'categorias'

    Returns:
        String HTML con sección de alertas
    """
    html = """
    <div style="background: #fff3cd; border-left: 5px solid #ffc107; padding: 20px; margin: 30px 0; border-radius: 5px;">
        <h2 style="color: #856404; margin-top: 0;">🚨 ALERTAS Y ANOMALÍAS DETECTADAS</h2>
"""

    total_alertas = sum(len(anomalias_dict.get(k, [])) for k in ['volumen', 'sentimientos', 'ofensivos', 'categorias'])

    if total_alertas == 0:
        html += """
        <p style="color: #155724; font-weight: bold;">
            🟢 No se detectaron anomalías significativas en el período analizado.
        </p>
"""
    else:
        html += f"""
        <p style="color: #856404;">
            Se detectaron <strong>{total_alertas} anomalías</strong> que requieren atención:
        </p>
"""

        # Volumen
        if anomalias_dict.get('volumen'):
            html += """
        <h3 style="color: #721c24;">📊 Anomalías de Volumen</h3>
        <ul>
"""
            for a in anomalias_dict['volumen']:
                icono = '🔴' if a['nivel'] == 'critico' else '🟡'
                html += f"""
            <li>{icono} <strong>{a['mes']}</strong>: {a['tipo'].upper()} de volumen
                ({a['volumen']:,} registros, {a['desviacion']:+.1f}σ)</li>
"""
            html += """
        </ul>
"""

        # Sentimientos
        if anomalias_dict.get('sentimientos'):
            html += """
        <h3 style="color: #721c24;">😟 Cambios Bruscos en Sentimientos</h3>
        <ul>
"""
            for a in anomalias_dict['sentimientos']:
                icono = '🔴' if a['nivel'] == 'critico' else '🟡'
                html += f"""
            <li>{icono} <strong>{a['mes']}</strong>: {a['tipo'].upper()}
                ({a['cambio_pct']:+.1f}% de negativos, actual: {a['pct_negativo_actual']}%)</li>
"""
            html += """
        </ul>
"""

        # Ofensivos
        if anomalias_dict.get('ofensivos'):
            html += """
        <h3 style="color: #721c24;">⚠️ Alto Contenido Ofensivo</h3>
        <ul>
"""
            for a in anomalias_dict['ofensivos']:
                icono = '🔴' if a['nivel'] == 'critico' else '🟡'
                html += f"""
            <li>{icono} <strong>{a['mes']}</strong>: {a['pct_ofensivo']}% ofensivo
                ({a['ofensivos']:,} de {a['total']:,} registros)</li>
"""
            html += """
        </ul>
"""

        # Categorías
        if anomalias_dict.get('categorias'):
            nuevas = [a for a in anomalias_dict['categorias'] if a['tipo'] == 'nueva']
            perdidas = [a for a in anomalias_dict['categorias'] if a['tipo'] == 'perdida']

            if nuevas or perdidas:
                html += """
        <h3 style="color: #0c5460;">📋 Cambios en Categorías</h3>
"""

            if nuevas:
                html += """
        <p><strong>Nuevas categorías:</strong></p>
        <ul>
"""
                for a in nuevas[:5]:  # Mostrar máximo 5
                    html += f"""
            <li>🔵 <strong>{a['categoria']}</strong> apareció en {a['mes']} ({a['volumen']:,} registros)</li>
"""
                if len(nuevas) > 5:
                    html += f"""
            <li>...y {len(nuevas) - 5} más</li>
"""
                html += """
        </ul>
"""

            if perdidas:
                html += """
        <p><strong>Categorías desaparecidas:</strong></p>
        <ul>
"""
                for a in perdidas[:5]:
                    html += f"""
            <li>🟠 <strong>{a['categoria']}</strong> desapareció después de {a['mes']}
                (volumen anterior: {a['volumen_anterior']:,})</li>
"""
                if len(perdidas) > 5:
                    html += f"""
            <li>...y {len(perdidas) - 5} más</li>
"""
                html += """
        </ul>
"""

    html += """
    </div>
"""

    return html
