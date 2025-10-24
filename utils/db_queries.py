#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Queries SQL reutilizables para informes NPS/CSAT
Todas las consultas usan la tabla unificada: respuestas_nps_csat
"""

import pandas as pd
from sqlalchemy import text

# =============================================================================
# QUERIES MENSUALES (para informe mensual)
# =============================================================================

def query_resumen_mes(engine, mes_anio):
    """
    Resumen ejecutivo del mes por canal y métrica

    Retorna: DataFrame con total, con_texto, categorizados, sentimientos, ofensivos, ruido, score_promedio
    """
    query = f"""
        SELECT
            canal,
            metrica,
            COUNT(*) as total,
            COUNT(motivo_texto) FILTER (WHERE LENGTH(TRIM(motivo_texto)) > 0) as con_texto,
            COUNT(*) FILTER (WHERE LENGTH(TRIM(motivo_texto)) = 0 OR motivo_texto IS NULL) as sin_texto,
            COUNT(categoria) as categorizados,
            COUNT(sentimiento_py) as con_sentimiento,
            COUNT(*) FILTER (WHERE es_ofensivo = TRUE) as ofensivos,
            COUNT(*) FILTER (WHERE es_ruido = TRUE) as ruido,
            ROUND(AVG(score)::numeric, 2) as promedio_score,
            ROUND(AVG(longitud_motivo)::numeric, 1) as longitud_promedio,
            ROUND(AVG(categoria_confianza)::numeric, 3) as confianza_categoria,
            ROUND(AVG(confianza_py)::numeric, 3) as confianza_sentimiento
        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
        GROUP BY canal, metrica
        ORDER BY canal, metrica
    """
    return pd.read_sql(text(query), engine)


def query_detalle_mes(engine, mes_anio):
    """
    Detalle completo de todos los registros del mes (para CSV)

    Retorna: DataFrame con todos los campos relevantes
    """
    query = f"""
        SELECT
            id,
            record_id,
            canal,
            metrica,
            mes_anio,
            fecha_respuesta,
            cliente_id,
            score,
            categoria_score,
            motivo_texto,
            categoria,
            categoria_confianza,
            es_ruido,
            razon_ruido,
            sentimiento_py as sentimiento,
            confianza_py as sentimiento_confianza,
            emocion,
            intensidad_emocional,
            es_ofensivo,
            longitud_motivo,
            pais,
            dispositivo
        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
        ORDER BY fecha_respuesta DESC
    """
    return pd.read_sql(text(query), engine)


def query_categorias_sentimientos_mes(engine, mes_anio):
    """
    Categorías con distribución de sentimientos para el mes (separado por canal/metrica)

    Retorna: DataFrame con canal, metrica, categoria, total, positivos, negativos, neutrales, score_promedio
    """
    query = f"""
        SELECT
            canal,
            metrica,
            categoria,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE sentimiento_py = 'POSITIVO') as positivos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEGATIVO') as negativos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEUTRAL') as neutrales,
            COUNT(*) FILTER (WHERE es_ofensivo = TRUE) as ofensivos,
            ROUND(AVG(score)::numeric, 2) as score_promedio,
            ROUND(AVG(confianza_py)::numeric, 3) as confianza_promedio
        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
          AND categoria IS NOT NULL
        GROUP BY canal, metrica, categoria
        ORDER BY canal, metrica, total DESC
    """
    return pd.read_sql(text(query), engine)


def query_emociones_mes(engine, mes_anio):
    """
    Distribución de emociones con intensidad para el mes

    Retorna: DataFrame con emocion, total, intensidad_promedio, score_promedio
    """
    query = f"""
        SELECT
            emocion,
            COUNT(*) as total,
            ROUND(AVG(intensidad_emocional)::numeric, 3) as intensidad_promedio,
            ROUND(AVG(score)::numeric, 2) as score_promedio,
            COUNT(*) FILTER (WHERE intensidad_emocional > 0.8) as muy_intensas
        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
          AND emocion IS NOT NULL
        GROUP BY emocion
        ORDER BY total DESC
    """
    return pd.read_sql(text(query), engine)


def query_ofensivos_mes(engine, mes_anio):
    """
    Motivos marcados como ofensivos en el mes

    Retorna: DataFrame con id, motivo_texto, categoria, score, sentimiento
    """
    query = f"""
        SELECT
            id,
            canal,
            metrica,
            fecha_respuesta,
            motivo_texto,
            categoria,
            score,
            sentimiento_py as sentimiento,
            intensidad_emocional,
            longitud_motivo
        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
          AND es_ofensivo = TRUE
        ORDER BY intensidad_emocional DESC, longitud_motivo DESC
    """
    return pd.read_sql(text(query), engine)


def query_top_largos_mes(engine, mes_anio, limit=10):
    """
    Top N mensajes más largos del mes

    Retorna: DataFrame con motivo_texto, longitud_motivo, categoria, sentimiento
    """
    query = f"""
        SELECT
            id,
            canal,
            metrica,
            motivo_texto,
            longitud_motivo,
            categoria,
            sentimiento_py as sentimiento,
            score,
            intensidad_emocional
        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
          AND longitud_motivo IS NOT NULL
        ORDER BY longitud_motivo DESC
        LIMIT {limit}
    """
    return pd.read_sql(text(query), engine)


def query_cruces_categoria_sentimiento_canal_mes(engine, mes_anio):
    """
    Cruce completo: Canal x Métrica x Categoría x Sentimiento

    Retorna: DataFrame con todas las combinaciones y sus volúmenes
    """
    query = f"""
        SELECT
            canal,
            metrica,
            categoria,
            sentimiento_py as sentimiento,
            COUNT(*) as total,
            ROUND(AVG(score)::numeric, 2) as score_promedio
        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
          AND categoria IS NOT NULL
          AND sentimiento_py IS NOT NULL
        GROUP BY canal, metrica, categoria, sentimiento_py
        ORDER BY canal, metrica, total DESC
    """
    return pd.read_sql(text(query), engine)


def query_tabla_metricas_mes(engine, mes_anio):
    """
    Tabla consolidada de métricas detalladas para el mes
    Incluye desglose NPS (Detractores/Pasivos/Promotores) y CSAT (Bajo/Medio/Alto)
    Incluye intensidad promedio de sentimientos

    Retorna: DataFrame con canal, metrica, total, categorizados, sentimientos,
             detractores, pasivos, promotores (NPS) o bajo, medio, alto (CSAT),
             intensidad_positiva, intensidad_negativa, intensidad_neutral
    """
    query = f"""
        SELECT
            canal,
            metrica,
            COUNT(*) as total,
            COUNT(motivo_texto) FILTER (WHERE LENGTH(TRIM(motivo_texto)) > 0) as con_texto,
            COUNT(categoria) as categorizados,
            COUNT(sentimiento_py) as con_sentimiento,
            COUNT(*) FILTER (WHERE es_ofensivo = TRUE) as ofensivos,
            ROUND(AVG(score)::numeric, 2) as score_promedio,

            -- Desglose NPS (0-10)
            COUNT(*) FILTER (WHERE metrica = 'NPS' AND score <= 6) as nps_detractores,
            COUNT(*) FILTER (WHERE metrica = 'NPS' AND score BETWEEN 7 AND 8) as nps_pasivos,
            COUNT(*) FILTER (WHERE metrica = 'NPS' AND score >= 9) as nps_promotores,

            -- Desglose CSAT (1-5)
            COUNT(*) FILTER (WHERE metrica = 'CSAT' AND score <= 2) as csat_bajo,
            COUNT(*) FILTER (WHERE metrica = 'CSAT' AND score = 3) as csat_medio,
            COUNT(*) FILTER (WHERE metrica = 'CSAT' AND score >= 4) as csat_alto,

            -- Distribución de sentimientos
            COUNT(*) FILTER (WHERE sentimiento_py = 'POSITIVO') as positivos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEGATIVO') as negativos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEUTRAL') as neutrales,

            -- Intensidad de sentimientos (0.0 - 1.0)
            ROUND(AVG(intensidad_emocional) FILTER (WHERE sentimiento_py = 'POSITIVO')::numeric, 2) as intensidad_positiva,
            ROUND(AVG(intensidad_emocional) FILTER (WHERE sentimiento_py = 'NEGATIVO')::numeric, 2) as intensidad_negativa,
            ROUND(AVG(intensidad_emocional) FILTER (WHERE sentimiento_py = 'NEUTRAL')::numeric, 2) as intensidad_neutral

        FROM respuestas_nps_csat
        WHERE mes_anio = '{mes_anio}'
        GROUP BY canal, metrica
        ORDER BY canal, metrica
    """
    return pd.read_sql(text(query), engine)


# =============================================================================
# QUERIES CONSOLIDADAS (para informe consolidado - todos los meses)
# =============================================================================

def query_evolucion_mensual(engine):
    """
    Evolución temporal por mes, canal y métrica

    Retorna: DataFrame con mes_anio, canal, metrica, total, con_sentimiento, ofensivos, score_promedio
    """
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
            ROUND(AVG(score)::numeric, 2) as score_promedio,
            ROUND(AVG(categoria_confianza)::numeric, 3) as confianza_categoria,
            ROUND(AVG(confianza_py)::numeric, 3) as confianza_sentimiento
        FROM respuestas_nps_csat
        WHERE mes_anio IS NOT NULL
        GROUP BY mes_anio, canal, metrica
        ORDER BY mes_anio ASC, canal, metrica
    """
    return pd.read_sql(text(query), engine)


def query_sentimientos_por_mes(engine):
    """
    Distribución de sentimientos mes a mes

    Retorna: DataFrame con mes_anio, sentimiento, total, score_promedio
    """
    query = """
        SELECT
            mes_anio,
            canal,
            metrica,
            sentimiento_py as sentimiento,
            COUNT(*) as total,
            ROUND(AVG(score)::numeric, 2) as score_promedio
        FROM respuestas_nps_csat
        WHERE mes_anio IS NOT NULL
          AND sentimiento_py IS NOT NULL
        GROUP BY mes_anio, canal, metrica, sentimiento_py
        ORDER BY mes_anio ASC, canal, metrica, sentimiento_py
    """
    return pd.read_sql(text(query), engine)


def query_categorias_por_mes(engine):
    """
    Volumen de categorías mes a mes (para heatmap temporal) - separado por canal/metrica

    Retorna: DataFrame con mes_anio, canal, metrica, categoria, total, score_promedio
    """
    query = """
        SELECT
            mes_anio,
            canal,
            metrica,
            categoria,
            COUNT(*) as total,
            ROUND(AVG(score)::numeric, 2) as score_promedio,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEGATIVO') as negativos
        FROM respuestas_nps_csat
        WHERE mes_anio IS NOT NULL
          AND categoria IS NOT NULL
        GROUP BY mes_anio, canal, metrica, categoria
        ORDER BY mes_anio ASC, canal, metrica, total DESC
    """
    return pd.read_sql(text(query), engine)


def query_distribucion_scores_global(engine):
    """
    Distribución de scores por categoría (para boxplot) - separado por metrica

    Retorna: DataFrame con canal, metrica, categoria, score (uno por registro)
    """
    query = """
        SELECT
            canal,
            metrica,
            categoria,
            score
        FROM respuestas_nps_csat
        WHERE categoria IS NOT NULL
          AND score IS NOT NULL
    """
    return pd.read_sql(text(query), engine)


def query_treemap_jerarquia(engine):
    """
    Datos jerárquicos para treemap: Canal → Métrica → Categoría

    Retorna: DataFrame con canal, metrica, categoria, total, score_promedio
    """
    query = """
        SELECT
            canal,
            metrica,
            categoria,
            COUNT(*) as total,
            ROUND(AVG(score)::numeric, 2) as score_promedio
        FROM respuestas_nps_csat
        WHERE categoria IS NOT NULL
        GROUP BY canal, metrica, categoria
        ORDER BY canal, metrica, total DESC
    """
    return pd.read_sql(text(query), engine)


def query_categorias_global(engine):
    """
    Top categorías globales (todos los meses)

    Retorna: DataFrame con categoria, total, sentimientos, score_promedio
    """
    query = """
        SELECT
            categoria,
            COUNT(*) as total,
            COUNT(*) FILTER (WHERE sentimiento_py = 'POSITIVO') as positivos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEGATIVO') as negativos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEUTRAL') as neutrales,
            ROUND(AVG(score)::numeric, 2) as score_promedio
        FROM respuestas_nps_csat
        WHERE categoria IS NOT NULL
        GROUP BY categoria
        ORDER BY total DESC
        LIMIT 20
    """
    return pd.read_sql(text(query), engine)


def query_meses_disponibles(engine):
    """
    Lista de meses disponibles en la base de datos

    Retorna: Lista de strings con formato YYYY-MM
    """
    query = """
        SELECT DISTINCT mes_anio
        FROM respuestas_nps_csat
        WHERE mes_anio IS NOT NULL
        ORDER BY mes_anio ASC
    """
    df = pd.read_sql(text(query), engine)
    return df['mes_anio'].tolist()


def query_categorias_detalladas_consolidado(engine):
    """
    Análisis detallado de categorías con evolutivo mensual, sentimientos y ofensivos
    Para detección de datos atípicos y temas complejos

    Retorna: DataFrame con categoria, mes_anio, total, positivos, negativos, neutrales,
             ofensivos, score_promedio, intensidad_positiva, intensidad_negativa
    """
    query = """
        SELECT
            categoria,
            mes_anio,
            canal,
            metrica,
            COUNT(*) as total,

            -- Distribución de sentimientos
            COUNT(*) FILTER (WHERE sentimiento_py = 'POSITIVO') as positivos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEGATIVO') as negativos,
            COUNT(*) FILTER (WHERE sentimiento_py = 'NEUTRAL') as neutrales,

            -- Ofensivos
            COUNT(*) FILTER (WHERE es_ofensivo = TRUE) as ofensivos,

            -- Scores e intensidad
            ROUND(AVG(score)::numeric, 2) as score_promedio,
            ROUND(AVG(intensidad_emocional) FILTER (WHERE sentimiento_py = 'POSITIVO')::numeric, 2) as intensidad_positiva,
            ROUND(AVG(intensidad_emocional) FILTER (WHERE sentimiento_py = 'NEGATIVO')::numeric, 2) as intensidad_negativa,
            ROUND(AVG(intensidad_emocional) FILTER (WHERE sentimiento_py = 'NEUTRAL')::numeric, 2) as intensidad_neutral

        FROM respuestas_nps_csat
        WHERE categoria IS NOT NULL
          AND mes_anio IS NOT NULL
        GROUP BY categoria, mes_anio, canal, metrica
        ORDER BY categoria, mes_anio, canal, metrica
    """
    return pd.read_sql(text(query), engine)
