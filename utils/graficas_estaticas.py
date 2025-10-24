#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Imágenes estáticas PNG usando Matplotlib y Seaborn
"""

import matplotlib.pyplot as plt
import seaborn as sns
import pandas as pd
import numpy as np
from pathlib import Path

# Configuración global
plt.rcParams['font.family'] = 'sans-serif'
plt.rcParams['font.sans-serif'] = ['Arial', 'DejaVu Sans']
sns.set_palette("husl")


def imagen_nps_csat_interpretado(df_categorias, output_path, top_n=12):
    """
    Gráfica interpretada NPS/CSAT - REDISEÑO COMPLETO

    Panel izquierdo: NPS - Volumen por categoría con score promedio
    Panel derecho: CSAT - Volumen por categoría con score promedio

    Barras horizontales muestran VOLUMEN de datos
    Color de barra según score (Verde=bueno, Amarillo=medio, Rojo=malo)
    Anotación de score promedio al final de cada barra
    """
    # Verificar columna metrica
    if 'metrica' not in df_categorias.columns:
        print("[ERROR] DataFrame debe incluir columna 'metrica'")
        return None

    # Separar y ordenar por volumen (no por score)
    df_nps = df_categorias[df_categorias['metrica'] == 'NPS'].copy()
    df_csat = df_categorias[df_categorias['metrica'] == 'CSAT'].copy()

    if df_nps.empty or df_csat.empty:
        print(f"[WARN] Datos insuficientes - NPS: {len(df_nps)}, CSAT: {len(df_csat)}")
        return None

    # Ordenar por total (volumen) y tomar top N
    df_nps = df_nps.nlargest(top_n, 'total')
    df_csat = df_csat.nlargest(top_n, 'total')

    # Crear figura
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(22, 10))

    # === PANEL 1: NPS ===
    def color_nps(score):
        if score <= 6: return '#e74c3c'  # Detractores (rojo)
        elif score <= 8: return '#f39c12'  # Pasivos (amarillo)
        return '#27ae60'  # Promotores (verde)

    # Preparar datos
    categorias_nps = [cat[:45] + '...' if len(cat) > 45 else cat for cat in df_nps['categoria']]
    volumenes_nps = df_nps['total'].values
    scores_nps = df_nps['score_promedio'].values
    colores_nps = [color_nps(s) for s in scores_nps]

    y_pos = np.arange(len(categorias_nps))

    # Barras horizontales (volumen)
    ax1.barh(y_pos, volumenes_nps, color=colores_nps, edgecolor='white', linewidth=1, alpha=0.85)

    # Etiquetas de categorías en eje Y
    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(categorias_nps, fontsize=10)

    # Anotaciones de score al final de cada barra
    for i, (vol, score) in enumerate(zip(volumenes_nps, scores_nps)):
        ax1.text(vol + max(volumenes_nps)*0.02, i, f'Score: {score:.2f}',
                 va='center', fontsize=9, fontweight='bold')

    ax1.set_xlabel('Volumen de Comentarios', fontsize=12, fontweight='bold')
    ax1.set_title('NPS por Categoría (Top 12)\nColor: Verde=Promotores (9-10) | Amarillo=Pasivos (7-8) | Rojo=Detractores (0-6)',
                  fontsize=13, fontweight='bold', pad=15)
    ax1.grid(axis='x', alpha=0.3, linestyle='--')
    ax1.invert_yaxis()

    # === PANEL 2: CSAT ===
    def color_csat(score):
        if score <= 2: return '#e74c3c'  # Bajo (rojo)
        elif score <= 3: return '#f39c12'  # Medio (amarillo)
        return '#27ae60'  # Alto (verde)

    # Preparar datos
    categorias_csat = [cat[:45] + '...' if len(cat) > 45 else cat for cat in df_csat['categoria']]
    volumenes_csat = df_csat['total'].values
    scores_csat = df_csat['score_promedio'].values
    colores_csat = [color_csat(s) for s in scores_csat]

    y_pos2 = np.arange(len(categorias_csat))

    # Barras horizontales (volumen)
    ax2.barh(y_pos2, volumenes_csat, color=colores_csat, edgecolor='white', linewidth=1, alpha=0.85)

    # Etiquetas de categorías en eje Y
    ax2.set_yticks(y_pos2)
    ax2.set_yticklabels(categorias_csat, fontsize=10)

    # Anotaciones de score al final de cada barra
    for i, (vol, score) in enumerate(zip(volumenes_csat, scores_csat)):
        ax2.text(vol + max(volumenes_csat)*0.02, i, f'Score: {score:.2f}',
                 va='center', fontsize=9, fontweight='bold')

    ax2.set_xlabel('Volumen de Comentarios', fontsize=12, fontweight='bold')
    ax2.set_title('CSAT por Categoría (Top 12)\nColor: Verde=Alto (4-5) | Amarillo=Medio (3) | Rojo=Bajo (1-2)',
                  fontsize=13, fontweight='bold', pad=15)
    ax2.grid(axis='x', alpha=0.3, linestyle='--')
    ax2.invert_yaxis()

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"[OK] Imagen generada: {output_path}")
    return output_path


def imagen_heatmap_temporal(df_categorias_mes, output_path, top_n=10):
    """
    Replica viz_05_heatmap_temporal.png

    Heatmap con:
    - Rows: Top N categorías
    - Columns: Meses
    - Values: Volumen de comentarios
    - Colormap: Amarillo claro → Rojo oscuro
    """
    # Pivotar datos
    df_pivot = df_categorias_mes.pivot_table(
        index='categoria',
        columns='mes_anio',
        values='total',
        fill_value=0
    )

    # Top N categorías por volumen total
    top_cats = df_pivot.sum(axis=1).nlargest(top_n).index
    df_pivot = df_pivot.loc[top_cats]

    # Crear heatmap
    fig, ax = plt.subplots(figsize=(14, 8))

    sns.heatmap(
        df_pivot,
        annot=True,
        fmt='g',
        cmap='YlOrRd',
        linewidths=1,
        linecolor='white',
        cbar_kws={'label': 'Número de Comentarios'},
        ax=ax
    )

    ax.set_title(f'HEATMAP TEMPORAL: Volumen de Comentarios por Categoría y Mes (Top {top_n})\n(Colores más intensos = Más comentarios)',
                 fontsize=14, fontweight='bold', pad=15)
    ax.set_xlabel('Mes', fontsize=12, fontweight='bold')
    ax.set_ylabel('Categoría', fontsize=12, fontweight='bold')

    plt.xticks(rotation=45, ha='right')
    plt.yticks(rotation=0)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"[OK] Imagen generada: {output_path}")
    return output_path


def imagen_matriz_priorizacion(df_categorias, output_path):
    """
    Replica viz_06_matriz_priorizacion.png

    Scatter plot con:
    - X: Score promedio
    - Y: Volumen (escala logarítmica)
    - Tamaño de burbuja: Volumen
    - Color: Score promedio (colormap)
    - Líneas de mediana para crear cuadrantes
    """
    if df_categorias.empty:
        print("[WARN] No hay datos para matriz de priorización")
        return None

    fig, ax = plt.subplots(figsize=(14, 10))

    # Preparar datos
    df = df_categorias.copy()
    df = df[df['total'] > 0]  # Filtrar sin volumen

    # Scatter plot
    scatter = ax.scatter(
        df['score_promedio'],
        df['total'],
        s=df['total']/10,  # Tamaño proporcional al volumen
        c=df['score_promedio'],
        cmap='RdYlGn',
        alpha=0.6,
        edgecolors='black',
        linewidth=0.5
    )

    # Líneas de mediana
    mediana_score = df['score_promedio'].median()
    mediana_vol = df['total'].median()

    ax.axvline(x=mediana_score, color='red', linestyle='--', linewidth=2, label=f'Mediana Score: {mediana_score:.2f}')
    ax.axhline(y=mediana_vol, color='blue', linestyle='--', linewidth=2, label=f'Mediana Volumen: {mediana_vol:,.0f}')

    # Etiquetas para categorías significativas
    # Mostrar etiquetas en cuadrantes extremos
    for _, row in df.iterrows():
        # Cuadrante crítico: Bajo score + Alto volumen
        if row['score_promedio'] < mediana_score and row['total'] > mediana_vol:
            ax.annotate(row['categoria'],
                       (row['score_promedio'], row['total']),
                       fontsize=8,
                       xytext=(5, 5),
                       textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
        # Cuadrante positivo: Alto score + Alto volumen
        elif row['score_promedio'] > mediana_score and row['total'] > mediana_vol * 1.5:
            ax.annotate(row['categoria'],
                       (row['score_promedio'], row['total']),
                       fontsize=8,
                       xytext=(5, 5),
                       textcoords='offset points',
                       bbox=dict(boxstyle='round,pad=0.3', facecolor='lightgreen', alpha=0.7))

    # Configuración
    ax.set_yscale('log')
    ax.set_xlabel('Score Promedio', fontsize=12, fontweight='bold')
    ax.set_ylabel('Número de Comentarios (log scale)', fontsize=12, fontweight='bold')
    ax.set_title('MATRIZ DE PRIORIZACIÓN: Volumen vs Satisfacción\n(Tamaño = volumen | Priorizar: Alto volumen + Bajo score)',
                 fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3)
    ax.legend(loc='upper left')

    # Colorbar
    cbar = plt.colorbar(scatter, ax=ax)
    cbar.set_label('Score Promedio', fontsize=11)

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight', facecolor='white')
    plt.close()

    print(f"[OK] Imagen generada: {output_path}")
    return output_path
