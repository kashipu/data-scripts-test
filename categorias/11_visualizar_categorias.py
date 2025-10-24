#!/usr/bin/env python3
"""
Visualización Avanzada de Métricas por Categoría con Análisis Temporal

Métricas:
- NPS (Net Promoter Score): 0-10, entre más alto más probable que recomienden
- CSAT (Customer Satisfaction): 1-5, entre más alto más satisfechos están
"""
import sys
import os
from sqlalchemy import create_engine, text

def get_engine(db_name='nps_analitycs'):
    """Crea conexión a PostgreSQL"""
    conn_string = f"postgresql://postgres:postgres@localhost:5432/{db_name}?client_encoding=utf8"
    return create_engine(conn_string)
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
import numpy as np

# Configurar estilo mejorado
plt.style.use('seaborn-v0_8-darkgrid')
sns.set_palette("husl")
plt.rcParams['figure.facecolor'] = 'white'
plt.rcParams['axes.facecolor'] = 'white'

def get_fecha_field(tabla):
    """Retorna el campo de fecha según la tabla origen."""
    if tabla == 'banco_movil_clean':
        return 'answer_date'
    elif tabla == 'banco_virtual_clean':
        return 'date_submitted'
    return 'cleaned_date'

def crear_visualizaciones():
    """Genera visualizaciones avanzadas de los datos de categorización."""
    engine = get_engine("nps_analitycs")

    print("=" * 100)
    print("GENERANDO VISUALIZACIONES AVANZADAS DE CATEGORÍAS CON ANÁLISIS TEMPORAL")
    print("=" * 100)
    print("\nMétricas:")
    print("  - NPS: 0-10 (más alto = más recomendación)")
    print("  - CSAT: 1-5 (más alto = más satisfacción)")
    print("=" * 100)

    # Crear directorio de salida
    output_dir = "outputs"
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    archivos_generados = []

    with engine.connect() as conn:
        # =====================================================================
        # 1. VOLUMEN DE COMENTARIOS POR CATEGORÍA
        # =====================================================================
        print("\n[1/10] Generando gráfico: Volumen de Comentarios por Categoría...")

        query_volumen = text("""
            SELECT
                categoria,
                COUNT(*) as total_comentarios,
                COUNT(DISTINCT CASE WHEN metrica = 'NPS' THEN registro_id END) as comentarios_nps,
                COUNT(DISTINCT CASE WHEN metrica = 'CSAT' THEN registro_id END) as comentarios_csat,
                ROUND(AVG(score_metrica), 2) as promedio_score
            FROM motivos_categorizados
            WHERE (es_ruido = FALSE OR es_ruido IS NULL)
            AND score_metrica IS NOT NULL
            GROUP BY categoria
            ORDER BY total_comentarios DESC
        """)
        df_vol = pd.read_sql(query_volumen, conn)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 10))

        # Gráfico de volumen total
        colors_vol = sns.color_palette("viridis", len(df_vol))
        bars = ax1.barh(df_vol['categoria'], df_vol['total_comentarios'], color=colors_vol)

        total_comentarios = df_vol['total_comentarios'].sum()
        for bar, val in zip(bars, df_vol['total_comentarios']):
            pct = (val / total_comentarios) * 100
            ax1.text(val + total_comentarios*0.01, bar.get_y() + bar.get_height()/2,
                    f'{val:,} ({pct:.1f}%)', va='center', fontsize=9, fontweight='bold')

        ax1.set_xlabel('Número de Comentarios', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Categoría', fontsize=12, fontweight='bold')
        ax1.set_title('VOLUMEN TOTAL de Comentarios por Categoría\n(Mayor volumen = más menciones)',
                      fontsize=13, fontweight='bold', pad=15)
        ax1.grid(axis='x', alpha=0.3)

        # Gráfico de desglose NPS vs CSAT
        x = np.arange(len(df_vol))
        width = 0.35
        ax2.barh(x - width/2, df_vol['comentarios_nps'], width, label='NPS', color='#3498db', alpha=0.8)
        ax2.barh(x + width/2, df_vol['comentarios_csat'], width, label='CSAT', color='#e74c3c', alpha=0.8)

        ax2.set_yticks(x)
        ax2.set_yticklabels(df_vol['categoria'], fontsize=10)
        ax2.set_xlabel('Número de Comentarios', fontsize=12, fontweight='bold')
        ax2.set_title('Desglose de Comentarios por Métrica\n(NPS vs CSAT)',
                      fontsize=13, fontweight='bold', pad=15)
        ax2.legend(loc='lower right', fontsize=11)
        ax2.grid(axis='x', alpha=0.3)

        plt.tight_layout()
        file_vol = f"{output_dir}/viz_01_volumen_comentarios_{timestamp}.png"
        plt.savefig(file_vol, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   ✓ Guardado: {file_vol}")
        archivos_generados.append(os.path.basename(file_vol))

        # =====================================================================
        # 2. COMPARACIÓN NPS vs CSAT POR CATEGORÍA CON INTERPRETACIÓN
        # =====================================================================
        print("\n[2/10] Generando gráfico: NPS vs CSAT por Categoría...")

        query_metricas = text("""
            SELECT
                categoria,
                metrica,
                COUNT(*) as total_registros,
                ROUND(AVG(score_metrica), 2) as promedio_score,
                ROUND(STDDEV(score_metrica), 2) as desviacion
            FROM motivos_categorizados
            WHERE (es_ruido = FALSE OR es_ruido IS NULL)
            AND score_metrica IS NOT NULL
            GROUP BY categoria, metrica
            ORDER BY categoria, metrica
        """)
        df_metricas = pd.read_sql(query_metricas, conn)

        # Separar NPS y CSAT para gráficos lado a lado
        df_nps = df_metricas[df_metricas['metrica'] == 'NPS'].sort_values('promedio_score', ascending=True)
        df_csat = df_metricas[df_metricas['metrica'] == 'CSAT'].sort_values('promedio_score', ascending=True)

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))

        # Gráfico NPS
        colors_nps = ['#e74c3c' if x < 6 else '#f39c12' if x < 8 else '#2ecc71'
                      for x in df_nps['promedio_score']]
        bars_nps = ax1.barh(df_nps['categoria'], df_nps['promedio_score'], color=colors_nps, alpha=0.8)

        for bar, val, count in zip(bars_nps, df_nps['promedio_score'], df_nps['total_registros']):
            interpretacion = "Detractores" if val < 6 else "Pasivos" if val < 8 else "Promotores"
            ax1.text(val + 0.2, bar.get_y() + bar.get_height()/2,
                    f'{val:.2f} - {interpretacion}\n(n={count:,})',
                    va='center', fontsize=8, fontweight='bold')

        ax1.axvline(6, color='red', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Detractores')
        ax1.axvline(8, color='green', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Promotores')
        ax1.set_xlabel('Score NPS (0-10)', fontsize=12, fontweight='bold')
        ax1.set_ylabel('Categoría', fontsize=12, fontweight='bold')
        ax1.set_title('NPS por Categoría\n(Más alto = Mayor recomendación)\nVerde: Promotores (8-10) | Amarillo: Pasivos (6-7) | Rojo: Detractores (0-5)',
                      fontsize=13, fontweight='bold', pad=15)
        ax1.set_xlim(0, 11)
        ax1.legend(loc='lower right', fontsize=9)
        ax1.grid(axis='x', alpha=0.3)

        # Gráfico CSAT
        colors_csat = ['#e74c3c' if x < 3 else '#f39c12' if x < 4 else '#2ecc71'
                       for x in df_csat['promedio_score']]
        bars_csat = ax2.barh(df_csat['categoria'], df_csat['promedio_score'], color=colors_csat, alpha=0.8)

        for bar, val, count in zip(bars_csat, df_csat['promedio_score'], df_csat['total_registros']):
            interpretacion = "Bajo" if val < 3 else "Medio" if val < 4 else "Alto"
            ax2.text(val + 0.1, bar.get_y() + bar.get_height()/2,
                    f'{val:.2f} - {interpretacion}\n(n={count:,})',
                    va='center', fontsize=8, fontweight='bold')

        ax2.axvline(3, color='red', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Bajo')
        ax2.axvline(4, color='green', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Alto')
        ax2.set_xlabel('Score CSAT (1-5)', fontsize=12, fontweight='bold')
        ax2.set_ylabel('Categoría', fontsize=12, fontweight='bold')
        ax2.set_title('CSAT por Categoría\n(Más alto = Mayor satisfacción)\nVerde: Alto (4-5) | Amarillo: Medio (3-4) | Rojo: Bajo (1-3)',
                      fontsize=13, fontweight='bold', pad=15)
        ax2.set_xlim(0, 5.5)
        ax2.legend(loc='lower right', fontsize=9)
        ax2.grid(axis='x', alpha=0.3)

        plt.tight_layout()
        file_metricas = f"{output_dir}/viz_02_nps_csat_interpretado_{timestamp}.png"
        plt.savefig(file_metricas, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   ✓ Guardado: {file_metricas}")
        archivos_generados.append(os.path.basename(file_metricas))

        # =====================================================================
        # 3. EVOLUCIÓN MENSUAL DE CATEGORÍAS (TOP 5)
        # =====================================================================
        print("\n[3/10] Generando gráfico: Evolución Mensual de Categorías...")

        # Obtener top 5 categorías por volumen
        top5_cats = df_vol.nlargest(5, 'total_comentarios')['categoria'].tolist()

        query_evol = text("""
            SELECT
                mc.categoria,
                CASE
                    WHEN mc.tabla_origen = 'banco_movil_clean' THEN
                        TO_CHAR(bm.answer_date, 'YYYY-MM')
                    WHEN mc.tabla_origen = 'banco_virtual_clean' THEN
                        TO_CHAR(bv.date_submitted, 'YYYY-MM')
                END as mes,
                COUNT(*) as total_comentarios,
                ROUND(AVG(mc.score_metrica), 2) as promedio_score
            FROM motivos_categorizados mc
            LEFT JOIN banco_movil_clean bm ON mc.tabla_origen = 'banco_movil_clean' AND mc.registro_id = bm.id
            LEFT JOIN banco_virtual_clean bv ON mc.tabla_origen = 'banco_virtual_clean' AND mc.registro_id = bv.id
            WHERE (mc.es_ruido = FALSE OR mc.es_ruido IS NULL)
            AND mc.score_metrica IS NOT NULL
            AND mc.categoria IN :categorias
            GROUP BY mc.categoria, mes
            ORDER BY mes, mc.categoria
        """)
        df_evol = pd.read_sql(query_evol, conn, params={'categorias': tuple(top5_cats)})

        if not df_evol.empty:
            fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 12))

            # Gráfico de volumen
            for cat in top5_cats:
                df_cat = df_evol[df_evol['categoria'] == cat].sort_values('mes')
                ax1.plot(df_cat['mes'], df_cat['total_comentarios'],
                        marker='o', linewidth=2, markersize=6, label=cat)

            ax1.set_xlabel('Mes', fontsize=12, fontweight='bold')
            ax1.set_ylabel('Número de Comentarios', fontsize=12, fontweight='bold')
            ax1.set_title('EVOLUCIÓN MENSUAL: Volumen de Comentarios por Categoría (Top 5)\n(Ver tendencias y picos)',
                         fontsize=13, fontweight='bold', pad=15)
            ax1.legend(loc='best', fontsize=10)
            ax1.grid(alpha=0.3)
            ax1.tick_params(axis='x', rotation=45)

            # Gráfico de score promedio
            for cat in top5_cats:
                df_cat = df_evol[df_evol['categoria'] == cat].sort_values('mes')
                ax2.plot(df_cat['mes'], df_cat['promedio_score'],
                        marker='s', linewidth=2, markersize=6, label=cat)

            ax2.set_xlabel('Mes', fontsize=12, fontweight='bold')
            ax2.set_ylabel('Score Promedio', fontsize=12, fontweight='bold')
            ax2.set_title('EVOLUCIÓN MENSUAL: Score Promedio por Categoría (Top 5)\n(Ver si mejora o empeora la satisfacción)',
                         fontsize=13, fontweight='bold', pad=15)
            ax2.legend(loc='best', fontsize=10)
            ax2.grid(alpha=0.3)
            ax2.tick_params(axis='x', rotation=45)

            plt.tight_layout()
            file_evol = f"{output_dir}/viz_03_evolucion_mensual_{timestamp}.png"
            plt.savefig(file_evol, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"   ✓ Guardado: {file_evol}")
            archivos_generados.append(os.path.basename(file_evol))
        else:
            print("   ⚠ No hay datos temporales suficientes para generar evolución mensual")

        # =====================================================================
        # 4. EVOLUCIÓN MENSUAL DE NPS Y CSAT (GENERAL)
        # =====================================================================
        print("\n[4/10] Generando gráfico: Evolución Mensual de Métricas...")

        query_metricas_tiempo = text("""
            SELECT
                CASE
                    WHEN mc.tabla_origen = 'banco_movil_clean' THEN
                        TO_CHAR(bm.answer_date, 'YYYY-MM')
                    WHEN mc.tabla_origen = 'banco_virtual_clean' THEN
                        TO_CHAR(bv.date_submitted, 'YYYY-MM')
                END as mes,
                mc.metrica,
                COUNT(*) as total_comentarios,
                ROUND(AVG(mc.score_metrica), 2) as promedio_score
            FROM motivos_categorizados mc
            LEFT JOIN banco_movil_clean bm ON mc.tabla_origen = 'banco_movil_clean' AND mc.registro_id = bm.id
            LEFT JOIN banco_virtual_clean bv ON mc.tabla_origen = 'banco_virtual_clean' AND mc.registro_id = bv.id
            WHERE (mc.es_ruido = FALSE OR mc.es_ruido IS NULL)
            AND mc.score_metrica IS NOT NULL
            GROUP BY mes, mc.metrica
            ORDER BY mes, mc.metrica
        """)
        df_met_tiempo = pd.read_sql(query_metricas_tiempo, conn)

        if not df_met_tiempo.empty:
            fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(18, 12))

            # NPS: Score promedio
            df_nps_t = df_met_tiempo[df_met_tiempo['metrica'] == 'NPS'].sort_values('mes')
            ax1.plot(df_nps_t['mes'], df_nps_t['promedio_score'],
                    marker='o', linewidth=3, markersize=8, color='#3498db', label='NPS')
            ax1.axhline(8, color='green', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Promotores (8)')
            ax1.axhline(6, color='red', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Detractores (6)')
            ax1.fill_between(df_nps_t['mes'], 0, df_nps_t['promedio_score'],
                           alpha=0.2, color='#3498db')
            ax1.set_ylabel('Score NPS (0-10)', fontsize=12, fontweight='bold')
            ax1.set_title('Evolución del Score NPS\n(Más alto = Mayor recomendación)',
                         fontsize=13, fontweight='bold', pad=15)
            ax1.legend(loc='best', fontsize=9)
            ax1.grid(alpha=0.3)
            ax1.tick_params(axis='x', rotation=45)

            # NPS: Volumen
            ax2.bar(df_nps_t['mes'], df_nps_t['total_comentarios'],
                   color='#3498db', alpha=0.7)
            ax2.set_ylabel('Número de Comentarios NPS', fontsize=12, fontweight='bold')
            ax2.set_title('Volumen de Comentarios NPS por Mes',
                         fontsize=13, fontweight='bold', pad=15)
            ax2.grid(alpha=0.3)
            ax2.tick_params(axis='x', rotation=45)

            # CSAT: Score promedio
            df_csat_t = df_met_tiempo[df_met_tiempo['metrica'] == 'CSAT'].sort_values('mes')
            ax3.plot(df_csat_t['mes'], df_csat_t['promedio_score'],
                    marker='s', linewidth=3, markersize=8, color='#e74c3c', label='CSAT')
            ax3.axhline(4, color='green', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Alto (4)')
            ax3.axhline(3, color='red', linestyle='--', alpha=0.5, linewidth=2, label='Umbral Bajo (3)')
            ax3.fill_between(df_csat_t['mes'], 0, df_csat_t['promedio_score'],
                           alpha=0.2, color='#e74c3c')
            ax3.set_xlabel('Mes', fontsize=12, fontweight='bold')
            ax3.set_ylabel('Score CSAT (1-5)', fontsize=12, fontweight='bold')
            ax3.set_title('Evolución del Score CSAT\n(Más alto = Mayor satisfacción)',
                         fontsize=13, fontweight='bold', pad=15)
            ax3.legend(loc='best', fontsize=9)
            ax3.grid(alpha=0.3)
            ax3.tick_params(axis='x', rotation=45)

            # CSAT: Volumen
            ax4.bar(df_csat_t['mes'], df_csat_t['total_comentarios'],
                   color='#e74c3c', alpha=0.7)
            ax4.set_xlabel('Mes', fontsize=12, fontweight='bold')
            ax4.set_ylabel('Número de Comentarios CSAT', fontsize=12, fontweight='bold')
            ax4.set_title('Volumen de Comentarios CSAT por Mes',
                         fontsize=13, fontweight='bold', pad=15)
            ax4.grid(alpha=0.3)
            ax4.tick_params(axis='x', rotation=45)

            plt.tight_layout()
            file_met_tiempo = f"{output_dir}/viz_04_evolucion_metricas_{timestamp}.png"
            plt.savefig(file_met_tiempo, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"   ✓ Guardado: {file_met_tiempo}")
            archivos_generados.append(os.path.basename(file_met_tiempo))
        else:
            print("   ⚠ No hay datos temporales suficientes")

        # =====================================================================
        # 5. HEATMAP TEMPORAL: CATEGORÍA x MES (TOP 10)
        # =====================================================================
        print("\n[5/10] Generando heatmap temporal: Categoría x Mes...")

        # Top 10 categorías
        top10_cats = df_vol.nlargest(10, 'total_comentarios')['categoria'].tolist()

        query_heatmap = text("""
            SELECT
                mc.categoria,
                CASE
                    WHEN mc.tabla_origen = 'banco_movil_clean' THEN
                        TO_CHAR(bm.answer_date, 'YYYY-MM')
                    WHEN mc.tabla_origen = 'banco_virtual_clean' THEN
                        TO_CHAR(bv.date_submitted, 'YYYY-MM')
                END as mes,
                COUNT(*) as total_comentarios
            FROM motivos_categorizados mc
            LEFT JOIN banco_movil_clean bm ON mc.tabla_origen = 'banco_movil_clean' AND mc.registro_id = bm.id
            LEFT JOIN banco_virtual_clean bv ON mc.tabla_origen = 'banco_virtual_clean' AND mc.registro_id = bv.id
            WHERE (mc.es_ruido = FALSE OR mc.es_ruido IS NULL)
            AND mc.categoria IN :categorias
            GROUP BY mc.categoria, mes
            ORDER BY mes, mc.categoria
        """)
        df_heatmap = pd.read_sql(query_heatmap, conn, params={'categorias': tuple(top10_cats)})

        if not df_heatmap.empty:
            # Pivotar para heatmap
            df_hm_pivot = df_heatmap.pivot(index='categoria', columns='mes', values='total_comentarios')
            df_hm_pivot = df_hm_pivot.fillna(0)

            fig, ax = plt.subplots(figsize=(16, 10))
            sns.heatmap(df_hm_pivot, annot=True, fmt='.0f', cmap='YlOrRd',
                       cbar_kws={'label': 'Número de Comentarios'},
                       linewidths=0.5, ax=ax)

            ax.set_title('HEATMAP TEMPORAL: Volumen de Comentarios por Categoría y Mes (Top 10)\n(Colores más intensos = Más comentarios)',
                        fontsize=13, fontweight='bold', pad=15)
            ax.set_xlabel('Mes', fontsize=12, fontweight='bold')
            ax.set_ylabel('Categoría', fontsize=12, fontweight='bold')
            plt.xticks(rotation=45)
            plt.yticks(rotation=0)

            plt.tight_layout()
            file_heatmap = f"{output_dir}/viz_05_heatmap_temporal_{timestamp}.png"
            plt.savefig(file_heatmap, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"   ✓ Guardado: {file_heatmap}")
            archivos_generados.append(os.path.basename(file_heatmap))
        else:
            print("   ⚠ No hay datos temporales suficientes para heatmap")

        # =====================================================================
        # 6. MATRIZ DE ANÁLISIS: VOLUMEN vs SCORE
        # =====================================================================
        print("\n[6/10] Generando matriz: Volumen vs Score...")

        fig, ax = plt.subplots(figsize=(14, 10))

        # Scatter plot con tamaño proporcional
        scatter = ax.scatter(df_vol['promedio_score'], df_vol['total_comentarios'],
                            s=df_vol['total_comentarios']/30, alpha=0.6,
                            c=df_vol['promedio_score'], cmap='RdYlGn',
                            edgecolors='black', linewidth=1.5)

        # Añadir etiquetas para cada punto
        for idx, row in df_vol.iterrows():
            ax.annotate(row['categoria'],
                       (row['promedio_score'], row['total_comentarios']),
                       xytext=(5, 5), textcoords='offset points',
                       fontsize=8, alpha=0.8, fontweight='bold')

        # Líneas de referencia
        median_score = df_vol['promedio_score'].median()
        median_vol = df_vol['total_comentarios'].median()
        ax.axvline(median_score, color='red',
                  linestyle='--', alpha=0.5, linewidth=2, label=f'Mediana Score: {median_score:.2f}')
        ax.axhline(median_vol, color='blue',
                  linestyle='--', alpha=0.5, linewidth=2, label=f'Mediana Volumen: {median_vol:,.0f}')

        # Cuadrantes
        ax.text(median_score + 0.5, median_vol * 2, 'Alto Score\nAlto Volumen',
               fontsize=11, fontweight='bold', color='green', alpha=0.6)
        ax.text(median_score - 2, median_vol * 2, 'Bajo Score\nAlto Volumen',
               fontsize=11, fontweight='bold', color='red', alpha=0.6)

        ax.set_xlabel('Score Promedio', fontsize=12, fontweight='bold')
        ax.set_ylabel('Número de Comentarios (log scale)', fontsize=12, fontweight='bold')
        ax.set_yscale('log')
        ax.set_title('MATRIZ DE PRIORIZACIÓN: Volumen vs Satisfacción\n(Tamaño = volumen | Priorizar: Alto volumen + Bajo score)',
                     fontsize=13, fontweight='bold', pad=15)
        ax.legend(loc='upper left', fontsize=10)
        ax.grid(alpha=0.3)

        cbar = plt.colorbar(scatter, ax=ax, label='Score Promedio')
        cbar.set_label('Score Promedio', fontsize=10, fontweight='bold')

        plt.tight_layout()
        file_matriz = f"{output_dir}/viz_06_matriz_priorizacion_{timestamp}.png"
        plt.savefig(file_matriz, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   ✓ Guardado: {file_matriz}")
        archivos_generados.append(os.path.basename(file_matriz))

        # =====================================================================
        # 7. COMPARACIÓN POR CANAL (BM vs BV)
        # =====================================================================
        print("\n[7/10] Generando gráfico: Comparación por Canal...")

        query_canal = text("""
            SELECT
                categoria,
                canal,
                COUNT(*) as total_comentarios,
                ROUND(AVG(score_metrica), 2) as promedio_score
            FROM motivos_categorizados
            WHERE (es_ruido = FALSE OR es_ruido IS NULL)
            AND score_metrica IS NOT NULL
            GROUP BY categoria, canal
            ORDER BY categoria, canal
        """)
        df_canal = pd.read_sql(query_canal, conn)

        # Top 10 categorías
        df_canal_top = df_canal[df_canal['categoria'].isin(top10_cats)]
        df_canal_pivot = df_canal_top.pivot(index='categoria', columns='canal', values='promedio_score')

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 10))

        # Comparación de scores
        if 'BM' in df_canal_pivot.columns and 'BV' in df_canal_pivot.columns:
            df_canal_pivot = df_canal_pivot.fillna(0).sort_values(by='BM', ascending=True)
            x = range(len(df_canal_pivot))
            width = 0.35

            ax1.barh([i - width/2 for i in x], df_canal_pivot['BM'],
                    width, label='Banco Móvil', color='#2ecc71', alpha=0.8)
            ax1.barh([i + width/2 for i in x], df_canal_pivot['BV'],
                    width, label='Banco Virtual', color='#9b59b6', alpha=0.8)

            ax1.set_yticks(x)
            ax1.set_yticklabels(df_canal_pivot.index, fontsize=10)
            ax1.set_xlabel('Score Promedio', fontsize=12, fontweight='bold')
            ax1.set_title('Comparación de Score: BM vs BV\n(Top 10 Categorías)',
                         fontsize=13, fontweight='bold', pad=15)
            ax1.legend(loc='lower right', fontsize=11)
            ax1.grid(axis='x', alpha=0.3)

        # Volumen por canal
        df_canal_vol = df_canal_top.pivot(index='categoria', columns='canal', values='total_comentarios')
        if 'BM' in df_canal_vol.columns and 'BV' in df_canal_vol.columns:
            df_canal_vol = df_canal_vol.fillna(0).sort_values(by='BM', ascending=True)
            x = range(len(df_canal_vol))

            ax2.barh([i - width/2 for i in x], df_canal_vol['BM'],
                    width, label='Banco Móvil', color='#2ecc71', alpha=0.8)
            ax2.barh([i + width/2 for i in x], df_canal_vol['BV'],
                    width, label='Banco Virtual', color='#9b59b6', alpha=0.8)

            ax2.set_yticks(x)
            ax2.set_yticklabels(df_canal_vol.index, fontsize=10)
            ax2.set_xlabel('Número de Comentarios', fontsize=12, fontweight='bold')
            ax2.set_title('Volumen de Comentarios: BM vs BV\n(Top 10 Categorías)',
                         fontsize=13, fontweight='bold', pad=15)
            ax2.legend(loc='lower right', fontsize=11)
            ax2.grid(axis='x', alpha=0.3)

        plt.tight_layout()
        file_canal = f"{output_dir}/viz_07_comparacion_canal_{timestamp}.png"
        plt.savefig(file_canal, dpi=300, bbox_inches='tight')
        plt.close()
        print(f"   ✓ Guardado: {file_canal}")
        archivos_generados.append(os.path.basename(file_canal))

        # =====================================================================
        # 8. TOP CATEGORÍAS A MEJORAR (Bajo score + Alto volumen)
        # =====================================================================
        print("\n[8/10] Generando gráfico: Top Categorías a Mejorar...")

        # Categorías con score bajo y alto volumen
        df_mejorar = df_vol.copy()
        df_mejorar = df_mejorar[df_mejorar['promedio_score'] < median_score]
        df_mejorar = df_mejorar.nlargest(10, 'total_comentarios')

        if not df_mejorar.empty:
            fig, ax = plt.subplots(figsize=(14, 8))

            colors_mejorar = ['#e74c3c' if x < 5 else '#f39c12'
                             for x in df_mejorar['promedio_score']]
            bars = ax.barh(df_mejorar['categoria'], df_mejorar['total_comentarios'],
                          color=colors_mejorar, alpha=0.8)

            for bar, val, score in zip(bars, df_mejorar['total_comentarios'], df_mejorar['promedio_score']):
                ax.text(val + max(df_mejorar['total_comentarios'])*0.01, bar.get_y() + bar.get_height()/2,
                       f'{val:,} coments.\nScore: {score:.2f}',
                       va='center', fontsize=9, fontweight='bold')

            ax.set_xlabel('Número de Comentarios', fontsize=12, fontweight='bold')
            ax.set_ylabel('Categoría', fontsize=12, fontweight='bold')
            ax.set_title('TOP 10 CATEGORÍAS A MEJORAR\n(Alto volumen + Score bajo = Alta prioridad)',
                        fontsize=13, fontweight='bold', pad=15, color='#c0392b')
            ax.grid(axis='x', alpha=0.3)

            plt.tight_layout()
            file_mejorar = f"{output_dir}/viz_08_top_a_mejorar_{timestamp}.png"
            plt.savefig(file_mejorar, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"   ✓ Guardado: {file_mejorar}")
            archivos_generados.append(os.path.basename(file_mejorar))

        # =====================================================================
        # 9. TOP CATEGORÍAS DESTACADAS (Alto score + Alto volumen)
        # =====================================================================
        print("\n[9/10] Generando gráfico: Top Categorías Destacadas...")

        df_destacadas = df_vol.copy()
        df_destacadas = df_destacadas[df_destacadas['promedio_score'] >= median_score]
        df_destacadas = df_destacadas.nlargest(10, 'total_comentarios')

        if not df_destacadas.empty:
            fig, ax = plt.subplots(figsize=(14, 8))

            colors_destacadas = ['#2ecc71' if x >= 7 else '#3498db'
                                for x in df_destacadas['promedio_score']]
            bars = ax.barh(df_destacadas['categoria'], df_destacadas['total_comentarios'],
                          color=colors_destacadas, alpha=0.8)

            for bar, val, score in zip(bars, df_destacadas['total_comentarios'], df_destacadas['promedio_score']):
                ax.text(val + max(df_destacadas['total_comentarios'])*0.01, bar.get_y() + bar.get_height()/2,
                       f'{val:,} coments.\nScore: {score:.2f}',
                       va='center', fontsize=9, fontweight='bold')

            ax.set_xlabel('Número de Comentarios', fontsize=12, fontweight='bold')
            ax.set_ylabel('Categoría', fontsize=12, fontweight='bold')
            ax.set_title('TOP 10 CATEGORÍAS DESTACADAS\n(Alto volumen + Alto score = Fortalezas)',
                        fontsize=13, fontweight='bold', pad=15, color='#27ae60')
            ax.grid(axis='x', alpha=0.3)

            plt.tight_layout()
            file_destacadas = f"{output_dir}/viz_09_top_destacadas_{timestamp}.png"
            plt.savefig(file_destacadas, dpi=300, bbox_inches='tight')
            plt.close()
            print(f"   ✓ Guardado: {file_destacadas}")
            archivos_generados.append(os.path.basename(file_destacadas))

        # =====================================================================
        # 10. REPORTE DETALLADO POR MES (CSV)
        # =====================================================================
        print("\n[10/10] Generando reporte detallado por mes (CSV)...")

        query_reporte_mes = text("""
            SELECT
                CASE
                    WHEN mc.tabla_origen = 'banco_movil_clean' THEN
                        TO_CHAR(bm.answer_date, 'YYYY-MM')
                    WHEN mc.tabla_origen = 'banco_virtual_clean' THEN
                        TO_CHAR(bv.date_submitted, 'YYYY-MM')
                END as mes,
                mc.categoria,
                mc.metrica,
                mc.canal,
                COUNT(*) as total_comentarios,
                ROUND(AVG(mc.score_metrica), 2) as promedio_score,
                ROUND(MIN(mc.score_metrica), 2) as min_score,
                ROUND(MAX(mc.score_metrica), 2) as max_score,
                ROUND(STDDEV(mc.score_metrica), 2) as desviacion_std
            FROM motivos_categorizados mc
            LEFT JOIN banco_movil_clean bm ON mc.tabla_origen = 'banco_movil_clean' AND mc.registro_id = bm.id
            LEFT JOIN banco_virtual_clean bv ON mc.tabla_origen = 'banco_virtual_clean' AND mc.registro_id = bv.id
            WHERE (mc.es_ruido = FALSE OR mc.es_ruido IS NULL)
            AND mc.score_metrica IS NOT NULL
            GROUP BY mes, mc.categoria, mc.metrica, mc.canal
            ORDER BY mes DESC, total_comentarios DESC
        """)
        df_reporte = pd.read_sql(query_reporte_mes, conn)

        if not df_reporte.empty:
            file_reporte = f"{output_dir}/reporte_mensual_detallado_{timestamp}.csv"
            df_reporte.to_csv(file_reporte, index=False, encoding='utf-8-sig')
            print(f"   ✓ Guardado: {file_reporte}")
            archivos_generados.append(os.path.basename(file_reporte))

            # Resumen del reporte
            print(f"\n   📊 RESUMEN DEL REPORTE:")
            print(f"      - Total de registros: {len(df_reporte):,}")
            print(f"      - Meses únicos: {df_reporte['mes'].nunique()}")
            print(f"      - Categorías únicas: {df_reporte['categoria'].nunique()}")
            print(f"      - Rango de fechas: {df_reporte['mes'].min()} a {df_reporte['mes'].max()}")

        # =====================================================================
        # RESUMEN FINAL
        # =====================================================================
        print("\n" + "=" * 100)
        print("✅ VISUALIZACIONES GENERADAS EXITOSAMENTE")
        print("=" * 100)
        print(f"\n📁 Archivos creados en '{output_dir}/':\n")
        for i, archivo in enumerate(archivos_generados, 1):
            print(f"  {i:2d}. {archivo}")
        print("\n" + "=" * 100)
        print("INTERPRETACIÓN DE LOS GRÁFICOS:")
        print("=" * 100)
        print("📈 NPS (0-10):")
        print("   • 0-5: Detractores (Rojo) - No recomendarían")
        print("   • 6-7: Pasivos (Amarillo) - Indiferentes")
        print("   • 8-10: Promotores (Verde) - Sí recomendarían")
        print("\n⭐ CSAT (1-5):")
        print("   • 1-3: Baja satisfacción (Rojo)")
        print("   • 3-4: Satisfacción media (Amarillo)")
        print("   • 4-5: Alta satisfacción (Verde)")
        print("\n🎯 PRIORIZACIÓN:")
        print("   • Alto volumen + Bajo score = MEJORAR URGENTE")
        print("   • Alto volumen + Alto score = MANTENER (Fortaleza)")
        print("   • Bajo volumen + Bajo score = Monitorear")
        print("=" * 100)

if __name__ == "__main__":
    # Configurar encoding para Windows
    if sys.platform == 'win32':
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

    crear_visualizaciones()
