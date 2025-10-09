# PLAN DE ANÁLISIS DETALLADO - NPS Analytics

## Base de datos: `test_nps` (PostgreSQL)

---

## 📊 ESTRUCTURA DE LAS TABLAS

### **Tabla: banco_movil_clean**
- **Volumen:** 1,234,628 registros (704 MB)
- **Fuente:** Aplicación Banco Móvil (BM)
- **Período:** Múltiples meses de datos históricos

#### Columnas principales:

**Identificación y Timestamps:**
- `id` - Primary key
- `timestamp` - Timestamp original de envío
- `answer_date` - Fecha de respuesta
- `record_id` - ID del registro original
- `source_file` - Archivo fuente (UNIQUE constraint con record_id)
- `inserted_at` - Fecha de inserción en BD

**Cliente:**
- `cust_ident_num` - Número de identificación (bigint)
- `cust_ident_type` - Tipo de ID (CC, NIT, etc.)
- `channel` - Canal (BM)
- `feedback_type` - Tipo de feedback (NPS, CSAT)

**Métricas NPS:**
- `nps_recomendacion_score` - Score de recomendación (0-10)
- `nps_recomendacion_motivo` - Texto del motivo (text)
- `nps_score` - Score NPS computado (float)
- `nps_category` - Categoría: Detractor/Neutral/Promotor

**Métricas CSAT (exclusivo de BM):**
- `csat_satisfaccion_score` - Score de satisfacción (float)
- `csat_satisfaccion_motivo` - Texto del motivo (text)

**Metadata:**
- `answers` - JSON completo original con todas las respuestas
- `month_year` - Período (ej: "2025-08")
- `file_type` - BM
- `cleaned_date` - Fecha de limpieza

---

### **Tabla: banco_virtual_clean**
- **Volumen:** 5,727 registros (2 MB)
- **Fuente:** Plataforma Web Banco Virtual (BV)
- **Período:** Datos históricos de plataforma digital

#### Columnas principales:

**Identificación y Timestamps:**
- `id` - Primary key
- `date_submitted_original` - String original de fecha
- `date_submitted` - Timestamp parseado
- `source_file` - Archivo fuente (UNIQUE constraint)
- `inserted_at` - Fecha de inserción

**Métricas NPS:**
- `nps_score_bv` - Score NPS original del archivo
- `nps_score` - Score NPS normalizado (integer)
- `nps_category` - Categoría: Detractor/Neutral/Promotor

**Feedback textual:**
- `calificacion_acerca` - Sobre qué fue la calificación
- `motivo_calificacion` - Motivo de la calificación (text principal)
- `tags_recomendacion` - Tags de recomendación
- `tags_calificacion` - Tags de calificación
- `tags_motivo` - Tags del motivo
- `sentiment_motivo` - Análisis de sentimiento del motivo

**Contexto técnico (exclusivo de BV):**
- `device` - Tipo de dispositivo (desktop/mobile)
- `browser` - Navegador y versión
- `operating_system` - Sistema operativo y versión
- `country` - País del usuario
- `source_url` - URL donde se envió la encuesta

**Metadata:**
- `month_year` - Período
- `file_type` - BV
- `cleaned_date` - Fecha de limpieza

---

## 🎯 MÉTRICAS DISPONIBLES Y QUERIES

### **1. MÉTRICAS BÁSICAS (YA INCLUIDAS EN SQL)**

✅ **Promedio total de NPS por fuente (BM y BV)**
- Query incluido en sección #2

✅ **Volumen total y comparado (BM vs BV)**
- Query incluido en sección #3

✅ **Distribución por categoría (Detractor/Neutral/Promotor)**
- Queries incluidos en sección #4
- Incluye porcentajes y volumenes

---

## 📈 PLAN DE ANÁLISIS AVANZADO

### **FASE 1: Análisis Temporal (Tendencias)**

**Métricas a extraer:**

1. **Evolución mensual de NPS**
   - NPS promedio por mes (BM y BV separados)
   - Volumen de respuestas por mes
   - Tendencia: ¿mejorando o empeorando?
   - **Query:** Ya incluido en sección #5

2. **Análisis de estacionalidad**
   - Identificar meses con más respuestas
   - Correlación entre volumen y NPS promedio
   - Días de la semana con mejor/peor NPS (requiere extraer día de `answer_date`)

3. **Análisis día/hora (BM):**
   ```sql
   SELECT
       EXTRACT(HOUR FROM answer_date) as hora_del_dia,
       COUNT(*) as respuestas,
       ROUND(AVG(nps_score), 2) as nps_promedio
   FROM banco_movil_clean
   GROUP BY hora_del_dia
   ORDER BY hora_del_dia;
   ```

---

### **FASE 2: Análisis de Segmentación**

**2.1 Segmentación por tipo de cliente (BM):**

```sql
-- Por tipo de identificación
SELECT
    cust_ident_type,
    COUNT(*) as volumen,
    ROUND(AVG(nps_score), 2) as nps_promedio,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) as promotores
FROM banco_movil_clean
WHERE cust_ident_type IS NOT NULL
GROUP BY cust_ident_type
ORDER BY volumen DESC;
```

**2.2 Segmentación por dispositivo (BV):**
- Ya incluido en sección #7
- Desktop vs Mobile
- NPS promedio por dispositivo
- Identificar si hay diferencia significativa

**2.3 Segmentación por país (BV):**
- Ya incluido en sección #7
- Top 10 países
- NPS por país

**2.4 Segmentación por navegador (BV):**
- Ya incluido en sección #7
- Detectar problemas técnicos correlacionados con NPS bajo

---

### **FASE 3: Análisis de CSAT (exclusivo BM)**

**3.1 Correlación NPS vs CSAT:**

```sql
SELECT
    CASE
        WHEN nps_score BETWEEN 0 AND 6 THEN 'Detractor'
        WHEN nps_score BETWEEN 7 AND 8 THEN 'Neutral'
        WHEN nps_score BETWEEN 9 AND 10 THEN 'Promotor'
    END as nps_categoria,
    COUNT(*) as total,
    ROUND(AVG(csat_satisfaccion_score), 2) as csat_promedio,
    ROUND(AVG(nps_recomendacion_score), 2) as nps_promedio
FROM banco_movil_clean
WHERE csat_satisfaccion_score IS NOT NULL
    AND nps_recomendacion_score IS NOT NULL
GROUP BY nps_categoria;
```

**3.2 Clientes con discrepancia (alto NPS pero bajo CSAT o viceversa):**

```sql
SELECT
    nps_recomendacion_score,
    csat_satisfaccion_score,
    LEFT(nps_recomendacion_motivo, 100) as motivo_nps,
    LEFT(csat_satisfaccion_motivo, 100) as motivo_csat
FROM banco_movil_clean
WHERE nps_recomendacion_score IS NOT NULL
    AND csat_satisfaccion_score IS NOT NULL
    AND (
        (nps_recomendacion_score >= 9 AND csat_satisfaccion_score <= 3)
        OR (nps_recomendacion_score <= 6 AND csat_satisfaccion_score >= 4)
    )
LIMIT 50;
```

---

### **FASE 4: Análisis de Texto (NLP)**

**4.1 Palabras más frecuentes en Detractores vs Promotores:**

Requiere procesamiento externo (Python con NLTK/spaCy), pero puedes extraer:

```sql
-- Exportar motivos de Detractores
SELECT nps_recomendacion_motivo
FROM banco_movil_clean
WHERE nps_category = 'Detractor'
    AND nps_recomendacion_motivo IS NOT NULL
    AND LENGTH(nps_recomendacion_motivo) > 20;

-- Exportar motivos de Promotores
SELECT nps_recomendacion_motivo
FROM banco_movil_clean
WHERE nps_category = 'Promotor'
    AND nps_recomendacion_motivo IS NOT NULL
    AND LENGTH(nps_recomendacion_motivo) > 20;
```

**4.2 Longitud de respuestas:**

```sql
SELECT
    nps_category,
    COUNT(*) as respuestas_con_texto,
    ROUND(AVG(LENGTH(nps_recomendacion_motivo)), 0) as longitud_promedio,
    MIN(LENGTH(nps_recomendacion_motivo)) as longitud_minima,
    MAX(LENGTH(nps_recomendacion_motivo)) as longitud_maxima
FROM banco_movil_clean
WHERE nps_recomendacion_motivo IS NOT NULL
    AND LENGTH(nps_recomendacion_motivo) > 10
GROUP BY nps_category;
```

**4.3 Tags en BV:**

```sql
-- Análisis de tags más frecuentes
SELECT
    tags_recomendacion,
    COUNT(*) as frecuencia,
    ROUND(AVG(nps_score), 2) as nps_promedio
FROM banco_virtual_clean
WHERE tags_recomendacion IS NOT NULL
GROUP BY tags_recomendacion
ORDER BY frecuencia DESC
LIMIT 20;
```

---

### **FASE 5: Análisis de Calidad de Datos**

**Ya incluido en sección #9:**
- Completitud de campos
- Porcentaje de respuestas con texto
- Registros duplicados (no debería haber por UNIQUE constraints)

**Adicional - Detectar anomalías:**

```sql
-- Clientes que respondieron múltiples veces
SELECT
    cust_ident_num,
    COUNT(*) as num_respuestas,
    ARRAY_AGG(DISTINCT nps_category) as categorias_distintas,
    ARRAY_AGG(DISTINCT month_year) as meses_distintos
FROM banco_movil_clean
WHERE cust_ident_num IS NOT NULL
GROUP BY cust_ident_num
HAVING COUNT(*) > 5
ORDER BY num_respuestas DESC
LIMIT 20;
```

---

### **FASE 6: Análisis Comparativo (BM vs BV)**

**6.1 Comparación de distribuciones:**

```sql
WITH bm_dist AS (
    SELECT
        'BM' as fuente,
        nps_category,
        COUNT(*) as volumen
    FROM banco_movil_clean
    WHERE nps_category IS NOT NULL
    GROUP BY nps_category
),
bv_dist AS (
    SELECT
        'BV' as fuente,
        nps_category,
        COUNT(*) as volumen
    FROM banco_virtual_clean
    WHERE nps_category IS NOT NULL
    GROUP BY nps_category
)
SELECT
    fuente,
    nps_category,
    volumen,
    ROUND(volumen * 100.0 / SUM(volumen) OVER (PARTITION BY fuente), 2) as porcentaje
FROM (SELECT * FROM bm_dist UNION ALL SELECT * FROM bv_dist) combined
ORDER BY fuente, nps_category;
```

**6.2 Promedios comparados:**
- Ya incluido en query #2

---

## 🎨 PRESENTACIÓN DE DATOS

### **DASHBOARD RECOMENDADO (Herramientas: Power BI, Tableau, Metabase, Grafana)**

**Panel 1: Overview General**
- KPI: NPS promedio BM y BV
- KPI: Volumen total de respuestas
- Gráfico de torta: % BM vs BV
- Gráfico de barras: Detractor/Neutral/Promotor (combinado)

**Panel 2: Análisis Temporal**
- Gráfico de línea: Evolución mensual de NPS (2 líneas: BM y BV)
- Gráfico de barras: Volumen de respuestas por mes
- Heatmap: NPS por día de semana y hora (solo BM)

**Panel 3: Banco Móvil (BM)**
- NPS promedio y distribución
- CSAT promedio
- Correlación NPS vs CSAT (scatter plot)
- Top 10 motivos de Detractores (word cloud)
- Top 10 motivos de Promotores (word cloud)

**Panel 4: Banco Virtual (BV)**
- NPS promedio y distribución
- Gráfico de barras: NPS por dispositivo
- Mapa: NPS por país
- Tabla: Top browsers y su NPS promedio

**Panel 5: Análisis de Texto**
- Word clouds por categoría
- Longitud promedio de respuestas
- Análisis de sentimiento (si disponible)

---

## 📁 EXPORTACIONES RECOMENDADAS

**Para análisis en Python/R:**

```sql
-- Exportar todo BM para análisis
COPY (
    SELECT * FROM banco_movil_clean
) TO '/tmp/banco_movil_full.csv' WITH CSV HEADER;

-- Exportar todo BV para análisis
COPY (
    SELECT * FROM banco_virtual_clean
) TO '/tmp/banco_virtual_full.csv' WITH CSV HEADER;

-- Exportar solo textos para NLP
COPY (
    SELECT
        nps_category,
        nps_recomendacion_motivo,
        csat_satisfaccion_motivo
    FROM banco_movil_clean
    WHERE nps_recomendacion_motivo IS NOT NULL
) TO '/tmp/textos_bm.csv' WITH CSV HEADER;
```

---

## 🔄 SIGUIENTES PASOS

1. **Ejecutar queries de sección #2, #3, #4 en `QUERIES_NPS_METRICAS.sql`** para métricas básicas
2. **Crear conexión en herramienta de BI** (Power BI, Tableau, Metabase)
3. **Implementar dashboard con 5 paneles** descritos arriba
4. **Análisis de texto con Python** (NLTK, spaCy, WordCloud):
   - Tokenización
   - Lemmatization
   - Eliminación de stopwords
   - Extracción de N-gramas más frecuentes
   - Word clouds por categoría
5. **Machine Learning (opcional):**
   - Clasificación automática de sentimiento
   - Predicción de NPS basado en texto
   - Clustering de clientes por comportamiento

---

## ⚠️ LIMITACIONES CONOCIDAS

- **Encoding issues:** Hay problemas con psycopg2 y UTF-8 en Windows (usa cliente SQL directo)
- **Volumen BV muy bajo:** 5.7K vs 1.2M de BM (comparaciones deben considerar esto)
- **Datos faltantes:** No todos los campos están completos (ver query #9)
- **Sin datos demográficos:** No hay edad, género, ubicación en BM

---

## 📝 CONCLUSIONES PRELIMINARES

Basado en la estructura:

1. **BM es la fuente principal** (99.5% del volumen total)
2. **BM tiene métricas más ricas** (CSAT además de NPS)
3. **BV tiene contexto técnico único** (device, browser, OS, país)
4. **Ambas tablas tienen protección contra duplicados** (UNIQUE constraints)
5. **Datos limpios y estructurados** listos para análisis

**Prioridad de análisis:**
1. Foco en BM por volumen
2. Usar BV para insights de UX digital
3. Correlacionar CSAT con NPS en BM
4. Análisis de texto es crítico (mayoría de insights vendrán de motivos)
