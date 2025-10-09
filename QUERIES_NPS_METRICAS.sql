-- ================================================================================
-- ANÁLISIS MENSUAL DETALLADO DE MÉTRICAS NPS Y CSAT
-- Base de datos: test_nps
-- Tablas: banco_movil_clean (1.2M registros), banco_virtual_clean (5.7K registros)
-- ================================================================================

-- ============================================================================
-- ANÁLISIS MES A MES - BANCO MÓVIL (BM)
-- Incluye: NPS y CSAT con volúmenes, porcentajes y promedios
-- ============================================================================

SELECT
    month_year,

    -- VOLUMEN TOTAL
    COUNT(*) as volumen_total_mes,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as porcentaje_del_total,

    -- MÉTRICA NPS
    'NPS' as metrica_nps,
    COUNT(nps_recomendacion_score) as volumen_nps,
    ROUND(AVG(nps_recomendacion_score)::numeric, 2) as promedio_nps,
    COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) as nps_detractores,
    COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) as nps_neutrales,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) as nps_promotores,
    ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_recomendacion_score), 0), 2) as nps_porc_detractores,
    ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_recomendacion_score), 0), 2) as nps_porc_neutrales,
    ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_recomendacion_score), 0), 2) as nps_porc_promotores,

    -- MÉTRICA CSAT
    'CSAT' as metrica_csat,
    COUNT(csat_satisfaccion_score) as volumen_csat,
    ROUND(AVG(csat_satisfaccion_score)::numeric, 2) as promedio_csat,
    MIN(csat_satisfaccion_score) as csat_minimo,
    MAX(csat_satisfaccion_score) as csat_maximo

FROM banco_movil_clean
WHERE month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;


-- ============================================================================
-- ANÁLISIS MES A MES - BANCO VIRTUAL (BV)
-- Incluye: NPS con volúmenes, porcentajes y promedios
-- ============================================================================

SELECT
    month_year,

    -- VOLUMEN TOTAL
    COUNT(*) as volumen_total_mes,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as porcentaje_del_total,

    -- MÉTRICA NPS
    'NPS' as metrica_nps,
    COUNT(nps_score_bv) as volumen_nps,
    ROUND(AVG(nps_score_bv)::numeric, 2) as promedio_nps,
    COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) as nps_detractores,
    COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) as nps_neutrales,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) as nps_promotores,
    ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_score_bv), 0), 2) as nps_porc_detractores,
    ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_score_bv), 0), 2) as nps_porc_neutrales,
    ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / NULLIF(COUNT(nps_score_bv), 0), 2) as nps_porc_promotores

FROM banco_virtual_clean
WHERE month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;


-- ============================================================================
-- RESUMEN CONSOLIDADO - PROMEDIOS GENERALES POR MÉTRICA
-- ============================================================================

-- Promedios generales de Banco Móvil (BM)
SELECT
    'Banco Móvil' as fuente,
    'NPS' as metrica,
    COUNT(nps_recomendacion_score) as volumen_total,
    ROUND(AVG(nps_recomendacion_score)::numeric, 2) as promedio_general,
    MIN(nps_recomendacion_score) as minimo,
    MAX(nps_recomendacion_score) as maximo
FROM banco_movil_clean
WHERE nps_recomendacion_score IS NOT NULL

UNION ALL

SELECT
    'Banco Móvil' as fuente,
    'CSAT' as metrica,
    COUNT(csat_satisfaccion_score) as volumen_total,
    ROUND(AVG(csat_satisfaccion_score)::numeric, 2) as promedio_general,
    MIN(csat_satisfaccion_score) as minimo,
    MAX(csat_satisfaccion_score) as maximo
FROM banco_movil_clean
WHERE csat_satisfaccion_score IS NOT NULL

UNION ALL

-- Promedios generales de Banco Virtual (BV)
SELECT
    'Banco Virtual' as fuente,
    'NPS' as metrica,
    COUNT(nps_score_bv) as volumen_total,
    ROUND(AVG(nps_score_bv)::numeric, 2) as promedio_general,
    MIN(nps_score_bv) as minimo,
    MAX(nps_score_bv) as maximo
FROM banco_virtual_clean
WHERE nps_score_bv IS NOT NULL

ORDER BY fuente, metrica;
