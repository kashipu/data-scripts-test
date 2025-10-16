-- =============================================================================
-- QUERIES PARA REPORTE CONSOLIDADO NPS/CSAT
-- =============================================================================

-- -----------------------------------------------------------------------------
-- QUERY 1: BM-NPS (Banco Móvil - Net Promoter Score)
-- -----------------------------------------------------------------------------
SELECT
    month_year AS mes,
    COUNT(*) AS volumen,
    ROUND(AVG(nps_recomendacion_score)::numeric, 2) AS promedio_nps,
    COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) AS detractores,
    ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_detractores,
    COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) AS neutrales,
    ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_neutrales,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) AS promotores,
    ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_promotores
FROM banco_movil_clean
WHERE nps_recomendacion_score IS NOT NULL
  AND month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;

-- -----------------------------------------------------------------------------
-- QUERY 2: BM-CSAT (Banco Móvil - Customer Satisfaction)
-- -----------------------------------------------------------------------------
SELECT
    month_year AS mes,
    COUNT(*) AS volumen,
    ROUND(AVG(csat_satisfaccion_score)::numeric, 2) AS promedio_csat,
    MIN(csat_satisfaccion_score) AS min_csat,
    MAX(csat_satisfaccion_score) AS max_csat,
    COUNT(CASE WHEN csat_satisfaccion_score <= 2 THEN 1 END) AS insatisfechos,
    ROUND(COUNT(CASE WHEN csat_satisfaccion_score <= 2 THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_insatisfechos,
    COUNT(CASE WHEN csat_satisfaccion_score = 3 THEN 1 END) AS neutrales,
    ROUND(COUNT(CASE WHEN csat_satisfaccion_score = 3 THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_neutrales,
    COUNT(CASE WHEN csat_satisfaccion_score >= 4 THEN 1 END) AS satisfechos,
    ROUND(COUNT(CASE WHEN csat_satisfaccion_score >= 4 THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_satisfechos
FROM banco_movil_clean
WHERE csat_satisfaccion_score IS NOT NULL
  AND month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;

-- -----------------------------------------------------------------------------
-- QUERY 3: BV-NPS (Banco Virtual - Net Promoter Score)
-- -----------------------------------------------------------------------------
SELECT
    month_year AS mes,
    COUNT(*) AS volumen,
    ROUND(AVG(nps_score)::numeric, 2) AS promedio_nps,
    COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) AS detractores,
    ROUND(COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_detractores,
    COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) AS neutrales,
    ROUND(COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_neutrales,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) AS promotores,
    ROUND(COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) * 100.0 / COUNT(*), 1) AS pct_promotores
FROM banco_virtual_clean
WHERE nps_score IS NOT NULL
  AND month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;

-- -----------------------------------------------------------------------------
-- QUERY 4: CONSOLIDADO GENERAL (Totales por Canal y Métrica)
-- -----------------------------------------------------------------------------
SELECT
    canal,
    metrica,
    SUM(volumen) AS total_registros,
    ROUND(AVG(promedio)::numeric, 2) AS promedio_general,
    ROUND(SUM(volumen) * 100.0 / (SELECT SUM(volumen) FROM (
        SELECT COUNT(*) as volumen FROM banco_movil_clean WHERE nps_recomendacion_score IS NOT NULL
        UNION ALL
        SELECT COUNT(*) FROM banco_movil_clean WHERE csat_satisfaccion_score IS NOT NULL
        UNION ALL
        SELECT COUNT(*) FROM banco_virtual_clean WHERE nps_score IS NOT NULL
    ) total), 1) AS porcentaje_del_total
FROM (
    -- BM-NPS
    SELECT
        'BM' as canal,
        'NPS' as metrica,
        COUNT(*) as volumen,
        AVG(nps_recomendacion_score) as promedio
    FROM banco_movil_clean
    WHERE nps_recomendacion_score IS NOT NULL

    UNION ALL

    -- BM-CSAT
    SELECT
        'BM' as canal,
        'CSAT' as metrica,
        COUNT(*) as volumen,
        AVG(csat_satisfaccion_score) as promedio
    FROM banco_movil_clean
    WHERE csat_satisfaccion_score IS NOT NULL

    UNION ALL

    -- BV-NPS
    SELECT
        'BV' as canal,
        'NPS' as metrica,
        COUNT(*) as volumen,
        AVG(nps_score) as promedio
    FROM banco_virtual_clean
    WHERE nps_score IS NOT NULL
) consolidado
GROUP BY canal, metrica
ORDER BY canal, metrica;

-- -----------------------------------------------------------------------------
-- QUERY 5: EVOLUCIÓN MENSUAL (Comparación mes a mes)
-- -----------------------------------------------------------------------------
SELECT
    COALESCE(bm_nps.month_year, bm_csat.month_year, bv_nps.month_year) AS mes,
    COALESCE(bm_nps.volumen, 0) AS bm_nps_vol,
    ROUND(COALESCE(bm_nps.promedio, 0)::numeric, 2) AS bm_nps_prom,
    COALESCE(bm_csat.volumen, 0) AS bm_csat_vol,
    ROUND(COALESCE(bm_csat.promedio, 0)::numeric, 2) AS bm_csat_prom,
    COALESCE(bv_nps.volumen, 0) AS bv_nps_vol,
    ROUND(COALESCE(bv_nps.promedio, 0)::numeric, 2) AS bv_nps_prom,
    COALESCE(bm_nps.volumen, 0) + COALESCE(bm_csat.volumen, 0) + COALESCE(bv_nps.volumen, 0) AS total_mes,
    -- Variación vs mes anterior (se calcula en Python)
    NULL AS variacion_pct
FROM (
    -- BM-NPS por mes
    SELECT month_year, COUNT(*) as volumen, AVG(nps_recomendacion_score) as promedio
    FROM banco_movil_clean
    WHERE nps_recomendacion_score IS NOT NULL AND month_year IS NOT NULL
    GROUP BY month_year
) bm_nps
FULL OUTER JOIN (
    -- BM-CSAT por mes
    SELECT month_year, COUNT(*) as volumen, AVG(csat_satisfaccion_score) as promedio
    FROM banco_movil_clean
    WHERE csat_satisfaccion_score IS NOT NULL AND month_year IS NOT NULL
    GROUP BY month_year
) bm_csat ON bm_nps.month_year = bm_csat.month_year
FULL OUTER JOIN (
    -- BV-NPS por mes
    SELECT month_year, COUNT(*) as volumen, AVG(nps_score) as promedio
    FROM banco_virtual_clean
    WHERE nps_score IS NOT NULL AND month_year IS NOT NULL
    GROUP BY month_year
) bv_nps ON COALESCE(bm_nps.month_year, bm_csat.month_year) = bv_nps.month_year
ORDER BY mes DESC;
