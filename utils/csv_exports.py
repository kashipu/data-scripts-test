#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Exportación de archivos CSV para informes mensuales
"""

import pandas as pd
from pathlib import Path


def export_resumen_mes(df_resumen, output_path):
    """
    Exporta CSV con resumen mensual ejecutivo

    Columnas:
    - Canal, Métrica
    - Total, Con Texto, Sin Texto
    - Categorizados, Con Sentimiento
    - Ofensivos, Ruido
    - Score Promedio, Longitud Promedio
    - Porcentajes calculados
    """
    # Calcular porcentajes
    df_export = df_resumen.copy()

    df_export['pct_con_texto'] = (df_export['con_texto'] / df_export['total'] * 100).round(1)
    df_export['pct_sin_texto'] = (df_export['sin_texto'] / df_export['total'] * 100).round(1)
    df_export['pct_categorizados'] = (df_export['categorizados'] / df_export['total'] * 100).round(1)
    df_export['pct_con_sentimiento'] = (df_export['con_sentimiento'] / df_export['total'] * 100).round(1)
    df_export['pct_ofensivos'] = (df_export['ofensivos'] / df_export['total'] * 100).round(1)
    df_export['pct_ruido'] = (df_export['ruido'] / df_export['total'] * 100).round(1)

    # Reordenar columnas
    columnas_orden = [
        'canal', 'metrica',
        'total', 'con_texto', 'pct_con_texto', 'sin_texto', 'pct_sin_texto',
        'categorizados', 'pct_categorizados',
        'con_sentimiento', 'pct_con_sentimiento',
        'ofensivos', 'pct_ofensivos',
        'ruido', 'pct_ruido',
        'promedio_score', 'longitud_promedio'
    ]

    df_export = df_export[columnas_orden]

    # Exportar
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_export.to_csv(output_path, index=False, encoding='utf-8-sig', sep=',')

    print(f"[OK] CSV resumen exportado: {output_path}")
    return output_path


def export_detalle_mes(df_detalle, output_path):
    """
    Exporta CSV con detalle completo de todos los registros del mes

    Incluye todos los campos relevantes para análisis detallado
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Exportar sin índice
    df_detalle.to_csv(output_path, index=False, encoding='utf-8-sig', sep=',')

    print(f"[OK] CSV detalle exportado: {output_path} ({len(df_detalle):,} registros)")
    return output_path


def export_categorias_mes(df_categorias, output_path):
    """
    Exporta CSV con distribución de categorías y sentimientos

    Incluye:
    - Categoría
    - Total, Positivos, Negativos, Neutrales
    - Ofensivos
    - Score Promedio, Confianza Promedio
    - Porcentajes
    """
    df_export = df_categorias.copy()

    # Calcular porcentajes de sentimientos
    df_export['pct_positivos'] = (df_export['positivos'] / df_export['total'] * 100).round(1)
    df_export['pct_negativos'] = (df_export['negativos'] / df_export['total'] * 100).round(1)
    df_export['pct_neutrales'] = (df_export['neutrales'] / df_export['total'] * 100).round(1)
    df_export['pct_ofensivos'] = (df_export['ofensivos'] / df_export['total'] * 100).round(1)

    # Reordenar
    columnas_orden = [
        'categoria', 'total',
        'positivos', 'pct_positivos',
        'negativos', 'pct_negativos',
        'neutrales', 'pct_neutrales',
        'ofensivos', 'pct_ofensivos',
        'score_promedio', 'confianza_promedio'
    ]

    df_export = df_export[columnas_orden]

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    df_export.to_csv(output_path, index=False, encoding='utf-8-sig', sep=',')

    print(f"[OK] CSV categorías exportado: {output_path}")
    return output_path


def export_excel_mensual(df_detalle, df_tabla_metricas, df_categorias, df_resumen, output_path):
    """
    Exporta datos mensuales a Excel con múltiples hojas

    Args:
        df_detalle: DataFrame con detalle completo de registros
        df_tabla_metricas: DataFrame con tabla de métricas consolidadas
        df_categorias: DataFrame con categorías y sentimientos
        df_resumen: DataFrame con resumen por canal/metrica
        output_path: Path del archivo Excel de salida

    Hojas:
        1. Metricas - Tabla consolidada con desgloses NPS/CSAT
        2. Detalle - Registros completos (fecha, metrica, score, motivo, categoria, sentimiento, intensidad, canal)
        3. Categorias - Volúmenes y sentimientos por canal/metrica/categoria
        4. Sentimientos - Distribución de sentimientos por canal/metrica
    """
    try:
        import openpyxl
        from openpyxl.utils.dataframe import dataframe_to_rows
        from openpyxl.styles import Font, PatternFill, Alignment
    except ImportError:
        print("[ERROR] openpyxl no está instalado. Instalar con: pip install openpyxl")
        return None

    # Crear workbook
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:

        # HOJA 1: Métricas consolidadas
        df_metricas_export = df_tabla_metricas.copy()

        # Calcular porcentajes
        df_metricas_export['pct_con_texto'] = (df_metricas_export['con_texto'] / df_metricas_export['total'] * 100).round(1)
        df_metricas_export['pct_categorizados'] = (df_metricas_export['categorizados'] / df_metricas_export['total'] * 100).round(1)
        df_metricas_export['pct_con_sentimiento'] = (df_metricas_export['con_sentimiento'] / df_metricas_export['total'] * 100).round(1)

        # Para NPS: calcular porcentajes de detractores/pasivos/promotores
        mask_nps = df_metricas_export['metrica'] == 'NPS'
        df_metricas_export.loc[mask_nps, 'pct_detractores'] = (
            df_metricas_export.loc[mask_nps, 'nps_detractores'] / df_metricas_export.loc[mask_nps, 'total'] * 100
        ).round(1)
        df_metricas_export.loc[mask_nps, 'pct_pasivos'] = (
            df_metricas_export.loc[mask_nps, 'nps_pasivos'] / df_metricas_export.loc[mask_nps, 'total'] * 100
        ).round(1)
        df_metricas_export.loc[mask_nps, 'pct_promotores'] = (
            df_metricas_export.loc[mask_nps, 'nps_promotores'] / df_metricas_export.loc[mask_nps, 'total'] * 100
        ).round(1)

        # Para CSAT: calcular porcentajes de bajo/medio/alto
        mask_csat = df_metricas_export['metrica'] == 'CSAT'
        df_metricas_export.loc[mask_csat, 'pct_bajo'] = (
            df_metricas_export.loc[mask_csat, 'csat_bajo'] / df_metricas_export.loc[mask_csat, 'total'] * 100
        ).round(1)
        df_metricas_export.loc[mask_csat, 'pct_medio'] = (
            df_metricas_export.loc[mask_csat, 'csat_medio'] / df_metricas_export.loc[mask_csat, 'total'] * 100
        ).round(1)
        df_metricas_export.loc[mask_csat, 'pct_alto'] = (
            df_metricas_export.loc[mask_csat, 'csat_alto'] / df_metricas_export.loc[mask_csat, 'total'] * 100
        ).round(1)

        df_metricas_export.to_excel(writer, sheet_name='Metricas', index=False)

        # HOJA 2: Detalle completo (columnas específicas del usuario)
        columnas_detalle = ['fecha_respuesta', 'canal', 'metrica', 'score', 'motivo_texto',
                           'categoria', 'sentimiento', 'confianza_py', 'intensidad_emocional',
                           'es_ofensivo', 'longitud_motivo']

        df_detalle_export = df_detalle[[col for col in columnas_detalle if col in df_detalle.columns]].copy()
        df_detalle_export.to_excel(writer, sheet_name='Detalle', index=False)

        # HOJA 3: Categorías con sentimientos
        df_cat_export = df_categorias.copy()

        # Calcular porcentajes de sentimientos
        df_cat_export['pct_positivos'] = (df_cat_export['positivos'] / df_cat_export['total'] * 100).round(1)
        df_cat_export['pct_negativos'] = (df_cat_export['negativos'] / df_cat_export['total'] * 100).round(1)
        df_cat_export['pct_neutrales'] = (df_cat_export['neutrales'] / df_cat_export['total'] * 100).round(1)

        df_cat_export.to_excel(writer, sheet_name='Categorias', index=False)

        # HOJA 4: Distribución de sentimientos (resumen por canal/metrica/sentimiento)
        # Crear pivot de sentimientos
        if 'positivos' in df_categorias.columns:
            df_sent_pivot = df_categorias.groupby(['canal', 'metrica']).agg({
                'total': 'sum',
                'positivos': 'sum',
                'negativos': 'sum',
                'neutrales': 'sum'
            }).reset_index()

            df_sent_pivot['pct_positivos'] = (df_sent_pivot['positivos'] / df_sent_pivot['total'] * 100).round(1)
            df_sent_pivot['pct_negativos'] = (df_sent_pivot['negativos'] / df_sent_pivot['total'] * 100).round(1)
            df_sent_pivot['pct_neutrales'] = (df_sent_pivot['neutrales'] / df_sent_pivot['total'] * 100).round(1)

            df_sent_pivot.to_excel(writer, sheet_name='Sentimientos', index=False)

        # Auto-ajustar anchos de columna
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

    print(f"[OK] Excel generado: {output_path}")
    return output_path
