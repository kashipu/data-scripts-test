# Plan de Optimización de Base de Datos - NPS Analytics

**Fecha:** 20 de Octubre, 2025
**Objetivo:** Optimizar estructura de BD para análisis eficiente por canal, mes, categoría y sentimiento

---

## 📊 ANÁLISIS DE ESTRUCTURA ACTUAL

### Tablas Existentes

```
1. banco_movil_clean (1,013,592 registros)
   - Datos de NPS/CSAT de Banco Móvil
   - Incluye: categoría, confianza, metadata (columnas redundantes)

2. banco_virtual_clean (7,605 registros)
   - Datos de NPS de Banco Virtual
   - Incluye: categoría, confianza, metadata (columnas redundantes)

3. motivos_categorizados (604,441 registros)
   - Tabla SEPARADA con categorizaciones
   - Duplica información que ya está en tablas principales

4. sentimientos_analisis (6,184 registros)
   - Tabla SEPARADA con análisis de sentimientos
   - No está relacionada con las tablas principales
```

---

## ❌ PROBLEMAS IDENTIFICADOS

### 1. **Redundancia de Datos**
- Las columnas `categoria_motivo`, `confidence_categoria`, `metadata_categoria` están en:
  - ✗ `banco_movil_clean`
  - ✗ `banco_virtual_clean`
  - ✗ `motivos_categorizados` (tabla separada)
- **Problema:** Datos duplicados = inconsistencias + desperdicio de espacio

### 2. **Tablas Desconectadas**
- `sentimientos_analisis` no tiene FK a tablas principales
- Para reportes necesitas hacer JOINs complejos por hash o IDs
- **Problema:** Consultas lentas y complejas

### 3. **Separación Artificial por Canal**
- `banco_movil_clean` vs `banco_virtual_clean`
- Para reportes consolidados necesitas UNION de ambas tablas
- **Problema:** Queries duplicados y complejos

### 4. **Falta de Particionamiento por Mes**
- No hay particiones de tabla por mes
- Índice en `month_year` pero no es óptimo para queries grandes
- **Problema:** Queries lentos en tablas con +1M registros

### 5. **Esquema No Normalizado**
- Datos mezclados: transaccionales + dimensionales
- Dificulta análisis tipo data warehouse
- **Problema:** Reportes complejos y lentos

---

## ✅ PROPUESTA: NUEVA ESTRUCTURA OPTIMIZADA

### Opción Recomendada: **Tabla Unificada con Desnormalización Estratégica**

Esta estructura es ideal para:
- ✅ Análisis y reportes rápidos
- ✅ Queries simples sin JOINs complejos
- ✅ Fácil filtrado por canal, mes, categoría, sentimiento
- ✅ Escalabilidad con particionamiento

---

## 🗄️ NUEVA ESTRUCTURA DE TABLAS

### Tabla Principal: `respuestas_nps_csat`

```sql
CREATE TABLE respuestas_nps_csat (
    -- Identificadores
    id SERIAL PRIMARY KEY,
    record_id VARCHAR(100) NOT NULL,  -- ID original del registro

    -- Dimensiones clave (para filtrado rápido)
    canal VARCHAR(10) NOT NULL,  -- 'BM' o 'BV'
    metrica VARCHAR(10) NOT NULL,  -- 'NPS' o 'CSAT'
    mes_anio VARCHAR(7) NOT NULL,  -- 'YYYY-MM' para particionamiento

    -- Fechas
    fecha_respuesta TIMESTAMP NOT NULL,
    fecha_procesamiento TIMESTAMP DEFAULT NOW(),

    -- Cliente (si aplica)
    cliente_id BIGINT,
    cliente_tipo VARCHAR(10),

    -- Scores
    score NUMERIC(4,2) NOT NULL,  -- Score de NPS (0-10) o CSAT (1-5)
    categoria_score VARCHAR(20),  -- 'Detractor', 'Neutral', 'Promotor'

    -- Texto y categorización
    motivo_texto TEXT,
    categoria VARCHAR(100),
    categoria_confianza NUMERIC(3,2),  -- 0.00 a 1.00
    es_ruido BOOLEAN DEFAULT FALSE,
    razon_ruido VARCHAR(50),

    -- Sentimiento
    sentimiento VARCHAR(20),  -- 'POSITIVO', 'NEUTRAL', 'NEGATIVO'
    sentimiento_confianza NUMERIC(3,2),

    -- Metadata específica por canal
    metadata JSONB,  -- Almacena campos específicos de cada canal

    -- Trazabilidad
    archivo_origen VARCHAR(255),

    -- Constraints
    CONSTRAINT valid_canal CHECK (canal IN ('BM', 'BV')),
    CONSTRAINT valid_metrica CHECK (metrica IN ('NPS', 'CSAT')),
    CONSTRAINT valid_score_nps CHECK (
        (metrica = 'NPS' AND score BETWEEN 0 AND 10) OR
        (metrica = 'CSAT' AND score BETWEEN 1 AND 5)
    ),
    CONSTRAINT valid_sentimiento CHECK (
        sentimiento IN ('POSITIVO', 'NEUTRAL', 'NEGATIVO') OR sentimiento IS NULL
    )
) PARTITION BY RANGE (fecha_respuesta);

-- Índices compuestos para queries comunes
CREATE INDEX idx_canal_mes ON respuestas_nps_csat(canal, mes_anio);
CREATE INDEX idx_categoria ON respuestas_nps_csat(categoria) WHERE categoria IS NOT NULL;
CREATE INDEX idx_sentimiento ON respuestas_nps_csat(sentimiento) WHERE sentimiento IS NOT NULL;
CREATE INDEX idx_score_categoria ON respuestas_nps_csat(canal, metrica, categoria_score);
CREATE INDEX idx_mes_canal_metrica ON respuestas_nps_csat(mes_anio, canal, metrica);
CREATE INDEX idx_metadata_gin ON respuestas_nps_csat USING GIN (metadata);  -- Para búsquedas en JSONB

-- Índice de texto completo para búsquedas en motivo
CREATE INDEX idx_motivo_texto_fts ON respuestas_nps_csat USING GIN (to_tsvector('spanish', motivo_texto));
```

### Particiones por Mes (Ejemplo)

```sql
-- Crear particiones automáticamente por mes
-- Junio 2025
CREATE TABLE respuestas_nps_csat_2025_06 PARTITION OF respuestas_nps_csat
    FOR VALUES FROM ('2025-06-01') TO ('2025-07-01');

-- Julio 2025
CREATE TABLE respuestas_nps_csat_2025_07 PARTITION OF respuestas_nps_csat
    FOR VALUES FROM ('2025-07-01') TO ('2025-08-01');

-- Agosto 2025
CREATE TABLE respuestas_nps_csat_2025_08 PARTITION OF respuestas_nps_csat
    FOR VALUES FROM ('2025-08-01') TO ('2025-09-01');

-- Septiembre 2025
CREATE TABLE respuestas_nps_csat_2025_09 PARTITION OF respuestas_nps_csat
    FOR VALUES FROM ('2025-09-01') TO ('2025-10-01');
```

**Beneficios del Particionamiento:**
- ✅ Queries por mes son extremadamente rápidos (solo escanean la partición relevante)
- ✅ Mantenimiento fácil (puedes eliminar meses antiguos completos)
- ✅ Backups incrementales por mes
- ✅ Crecimiento escalable

---

## 📋 TABLA AUXILIAR: Catálogo de Categorías

```sql
CREATE TABLE catalogo_categorias (
    id SERIAL PRIMARY KEY,
    nombre VARCHAR(100) UNIQUE NOT NULL,
    descripcion TEXT,
    palabras_clave TEXT[],  -- Array de palabras clave
    activa BOOLEAN DEFAULT TRUE,
    creada_en TIMESTAMP DEFAULT NOW()
);

-- Insertar categorías desde YAML
INSERT INTO catalogo_categorias (nombre, descripcion, palabras_clave) VALUES
('Texto Sin Sentido / Ruido', 'Textos sin contenido útil', ARRAY['__ruido__', '__sin_sentido__']),
('Falta de Información / N/A', 'Sin información relevante', ARRAY['n/a', 'na', 'no aplica']),
-- ... etc
```

---

## 📈 VISTAS MATERIALIZADAS PARA REPORTES

### Vista 1: Resumen Mensual por Canal y Métrica

```sql
CREATE MATERIALIZED VIEW mv_resumen_mensual AS
SELECT
    mes_anio,
    canal,
    metrica,
    COUNT(*) as total_respuestas,
    AVG(score) as score_promedio,
    -- NPS Calculation
    COUNT(*) FILTER (WHERE categoria_score = 'Promotor') as promotores,
    COUNT(*) FILTER (WHERE categoria_score = 'Neutral') as neutrales,
    COUNT(*) FILTER (WHERE categoria_score = 'Detractor') as detractores,
    ROUND(
        (COUNT(*) FILTER (WHERE categoria_score = 'Promotor')::NUMERIC / NULLIF(COUNT(*), 0) * 100) -
        (COUNT(*) FILTER (WHERE categoria_score = 'Detractor')::NUMERIC / NULLIF(COUNT(*), 0) * 100)
    , 2) as nps_score,
    -- Sentimientos
    COUNT(*) FILTER (WHERE sentimiento = 'POSITIVO') as sentimiento_positivo,
    COUNT(*) FILTER (WHERE sentimiento = 'NEUTRAL') as sentimiento_neutral,
    COUNT(*) FILTER (WHERE sentimiento = 'NEGATIVO') as sentimiento_negativo
FROM respuestas_nps_csat
GROUP BY mes_anio, canal, metrica;

CREATE UNIQUE INDEX ON mv_resumen_mensual(mes_anio, canal, metrica);
```

### Vista 2: Top Categorías por Canal y Mes

```sql
CREATE MATERIALIZED VIEW mv_top_categorias AS
SELECT
    mes_anio,
    canal,
    metrica,
    categoria,
    COUNT(*) as frecuencia,
    AVG(score) as score_promedio,
    AVG(categoria_confianza) as confianza_promedio,
    COUNT(*) FILTER (WHERE sentimiento = 'NEGATIVO') as negativos,
    RANK() OVER (PARTITION BY mes_anio, canal, metrica ORDER BY COUNT(*) DESC) as ranking
FROM respuestas_nps_csat
WHERE categoria IS NOT NULL AND es_ruido = FALSE
GROUP BY mes_anio, canal, metrica, categoria;

CREATE INDEX ON mv_top_categorias(mes_anio, canal, metrica, ranking);
```

### Vista 3: Análisis de Sentimientos por Categoría

```sql
CREATE MATERIALIZED VIEW mv_sentimiento_por_categoria AS
SELECT
    canal,
    metrica,
    categoria,
    sentimiento,
    COUNT(*) as cantidad,
    AVG(score) as score_promedio,
    ROUND(COUNT(*)::NUMERIC / SUM(COUNT(*)) OVER (PARTITION BY canal, metrica, categoria) * 100, 2) as porcentaje
FROM respuestas_nps_csat
WHERE sentimiento IS NOT NULL AND categoria IS NOT NULL
GROUP BY canal, metrica, categoria, sentimiento;

CREATE INDEX ON mv_sentimiento_por_categoria(canal, categoria);
```

**Refrescar vistas:**
```sql
-- Ejecutar diariamente o después de cargar datos
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_resumen_mensual;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_top_categorias;
REFRESH MATERIALIZED VIEW CONCURRENTLY mv_sentimiento_por_categoria;
```

---

## 🔄 PLAN DE MIGRACIÓN

### Fase 1: Crear Nueva Estructura (SIN borrar datos actuales)

```sql
-- 1. Crear tabla nueva con particiones
-- (Ver scripts arriba)

-- 2. Crear vistas materializadas
-- (Ver scripts arriba)

-- 3. Crear tabla de respaldo
CREATE TABLE _backup_banco_movil_clean AS
SELECT * FROM banco_movil_clean;

CREATE TABLE _backup_banco_virtual_clean AS
SELECT * FROM banco_virtual_clean;
```

### Fase 2: Migrar Datos

```sql
-- Migrar Banco Móvil (NPS)
INSERT INTO respuestas_nps_csat (
    record_id, canal, metrica, mes_anio, fecha_respuesta, fecha_procesamiento,
    cliente_id, cliente_tipo, score, categoria_score,
    motivo_texto, categoria, categoria_confianza, es_ruido,
    sentimiento, sentimiento_confianza, archivo_origen, metadata
)
SELECT
    'BM_' || bm.id::TEXT,
    'BM',
    'NPS',
    bm.month_year,
    bm.answer_date,
    NOW(),
    bm.cust_ident_num,
    bm.cust_ident_type,
    bm.nps_recomendacion_score,
    bm.nps_category,
    bm.nps_recomendacion_motivo,
    bm.categoria_motivo,
    bm.confidence_categoria,
    FALSE,  -- determinar si es ruido
    sa.sentimiento,
    sa.confianza,
    bm.source_file,
    jsonb_build_object(
        'feedback_type', bm.feedback_type,
        'channel', bm.channel,
        'timestamp', bm.timestamp
    )
FROM banco_movil_clean bm
LEFT JOIN sentimientos_analisis sa ON (
    sa.tabla_origen = 'banco_movil_clean'
    AND sa.registro_origen_id = bm.id
    AND sa.columna_origen = 'nps_recomendacion_motivo'
)
WHERE bm.nps_recomendacion_score IS NOT NULL;

-- Migrar Banco Móvil (CSAT)
INSERT INTO respuestas_nps_csat (
    record_id, canal, metrica, mes_anio, fecha_respuesta, fecha_procesamiento,
    cliente_id, cliente_tipo, score, categoria_score,
    motivo_texto, categoria, categoria_confianza, es_ruido,
    sentimiento, sentimiento_confianza, archivo_origen, metadata
)
SELECT
    'BM_CSAT_' || bm.id::TEXT,
    'BM',
    'CSAT',
    bm.month_year,
    bm.answer_date,
    NOW(),
    bm.cust_ident_num,
    bm.cust_ident_type,
    bm.csat_satisfaccion_score,
    NULL,  -- CSAT no tiene categorías de Promotor/Detractor
    bm.csat_satisfaccion_motivo,
    bm.categoria_motivo,  -- Si categorizaste CSAT también
    bm.confidence_categoria,
    FALSE,
    sa.sentimiento,
    sa.confianza,
    bm.source_file,
    jsonb_build_object(
        'feedback_type', bm.feedback_type,
        'channel', bm.channel,
        'timestamp', bm.timestamp
    )
FROM banco_movil_clean bm
LEFT JOIN sentimientos_analisis sa ON (
    sa.tabla_origen = 'banco_movil_clean'
    AND sa.registro_origen_id = bm.id
    AND sa.columna_origen = 'csat_satisfaccion_motivo'
)
WHERE bm.csat_satisfaccion_score IS NOT NULL;

-- Migrar Banco Virtual (NPS)
INSERT INTO respuestas_nps_csat (
    record_id, canal, metrica, mes_anio, fecha_respuesta, fecha_procesamiento,
    cliente_id, cliente_tipo, score, categoria_score,
    motivo_texto, categoria, categoria_confianza, es_ruido,
    sentimiento, sentimiento_confianza, archivo_origen, metadata
)
SELECT
    'BV_' || bv.id::TEXT,
    'BV',
    'NPS',
    bv.month_year,
    bv.date_submitted,
    NOW(),
    NULL,  -- BV no tiene cliente_id
    NULL,
    bv.nps_score_bv,
    bv.nps_category,
    bv.motivo_calificacion,
    bv.categoria_motivo,
    bv.confidence_categoria,
    FALSE,
    sa.sentimiento,
    sa.confianza,
    bv.source_file,
    jsonb_build_object(
        'country', bv.country,
        'device', bv.device,
        'browser', bv.browser,
        'os', bv.operating_system,
        'source_url', bv.source_url
    )
FROM banco_virtual_clean bv
LEFT JOIN sentimientos_analisis sa ON (
    sa.tabla_origen = 'banco_virtual_clean'
    AND sa.registro_origen_id = bv.id
    AND sa.columna_origen = 'motivo_calificacion'
)
WHERE bv.nps_score_bv IS NOT NULL;
```

### Fase 3: Validar Migración

```sql
-- Contar registros
SELECT 'banco_movil NPS' as fuente, COUNT(*) FROM banco_movil_clean WHERE nps_recomendacion_score IS NOT NULL
UNION ALL
SELECT 'banco_movil CSAT', COUNT(*) FROM banco_movil_clean WHERE csat_satisfaccion_score IS NOT NULL
UNION ALL
SELECT 'banco_virtual NPS', COUNT(*) FROM banco_virtual_clean WHERE nps_score_bv IS NOT NULL
UNION ALL
SELECT 'Nueva tabla', COUNT(*) FROM respuestas_nps_csat;

-- Verificar distribución por canal
SELECT canal, metrica, COUNT(*)
FROM respuestas_nps_csat
GROUP BY canal, metrica;

-- Verificar distribución por mes
SELECT mes_anio, canal, COUNT(*)
FROM respuestas_nps_csat
GROUP BY mes_anio, canal
ORDER BY mes_anio, canal;
```

### Fase 4: Actualizar Scripts ETL

**Modificar `04_insercion.py`** para insertar directamente en `respuestas_nps_csat`:

```python
# Nuevo código de inserción
def insert_to_unified_table(df, canal, metrica, engine):
    """
    Inserta datos en respuestas_nps_csat
    """
    # Preparar datos según canal y métrica
    if canal == 'BM' and metrica == 'NPS':
        data = pd.DataFrame({
            'record_id': 'BM_' + df['record_id'].astype(str),
            'canal': 'BM',
            'metrica': 'NPS',
            'mes_anio': df['month_year'],
            'fecha_respuesta': df['answer_date'],
            'cliente_id': df['cust_ident_num'],
            'cliente_tipo': df['cust_ident_type'],
            'score': df['nps_recomendacion_score'],
            'categoria_score': df['nps_category'],
            'motivo_texto': df['nps_recomendacion_motivo'],
            'archivo_origen': df['source_file'],
            'metadata': df.apply(lambda row: {
                'feedback_type': row.get('feedback_type'),
                'channel': row.get('channel')
            }, axis=1)
        })
    # ... etc para otros canales/métricas

    data.to_sql('respuestas_nps_csat', engine, if_exists='append', index=False)
```

---

## 🎯 QUERIES DE EJEMPLO PARA REPORTES

### 1. NPS Score Mensual por Canal

```sql
SELECT * FROM mv_resumen_mensual
WHERE mes_anio >= '2025-06'
ORDER BY mes_anio, canal, metrica;
```

### 2. Top 10 Categorías Negativas del Mes

```sql
SELECT
    categoria,
    COUNT(*) as cantidad,
    ROUND(AVG(score), 2) as score_promedio,
    COUNT(*) FILTER (WHERE sentimiento = 'NEGATIVO') as negativos
FROM respuestas_nps_csat
WHERE mes_anio = '2025-09'
    AND canal = 'BM'
    AND metrica = 'NPS'
    AND categoria_score = 'Detractor'
    AND es_ruido = FALSE
GROUP BY categoria
ORDER BY cantidad DESC
LIMIT 10;
```

### 3. Evolución de Sentimiento por Categoría

```sql
SELECT
    mes_anio,
    categoria,
    sentimiento,
    COUNT(*) as cantidad
FROM respuestas_nps_csat
WHERE categoria = 'Problemas Técnicos y Funcionalidad'
    AND sentimiento IS NOT NULL
GROUP BY mes_anio, categoria, sentimiento
ORDER BY mes_anio;
```

### 4. Comparativa de Canales

```sql
SELECT
    mes_anio,
    canal,
    COUNT(*) as total,
    AVG(score) as score_promedio,
    COUNT(*) FILTER (WHERE sentimiento = 'POSITIVO')::NUMERIC / NULLIF(COUNT(*), 0) * 100 as pct_positivo
FROM respuestas_nps_csat
WHERE mes_anio >= '2025-06'
GROUP BY mes_anio, canal
ORDER BY mes_anio, canal;
```

---

## 📊 BENEFICIOS ESPERADOS

### Performance
- ✅ **70-90% más rápido** en queries mensuales (gracias a particionamiento)
- ✅ **50% menos JOINs** en reportes (datos desnormalizados)
- ✅ **Índices especializados** para cada tipo de consulta

### Mantenibilidad
- ✅ **1 tabla principal** vs 4 tablas dispersas
- ✅ **Esquema más simple** y fácil de entender
- ✅ **Vistas materializadas** pre-calculan reportes comunes

### Escalabilidad
- ✅ **Particionamiento por mes** permite manejar millones de registros
- ✅ **JSONB para metadata** flexible según canal
- ✅ **Fácil agregar nuevos canales** sin cambiar esquema

### Análisis
- ✅ **Categoría + Sentimiento** en la misma fila
- ✅ **Filtrado rápido** por canal, mes, categoría
- ✅ **Reportes consolidados** sin UNION complejos

---

## 🚨 QUÉ DEBERÍAS REPLANTEAR

### 1. **Pipeline de Inserción (CRÍTICO)**
**Archivo:** `04_insercion.py`

❌ **Actual:** Inserta en `banco_movil_clean` y `banco_virtual_clean` separadas
✅ **Nuevo:** Insertar directamente en `respuestas_nps_csat` con:
- Canal identificado automáticamente
- Mes extraído de fecha
- Estructura unificada

### 2. **Categorización (MODIFICAR)**
**Archivo:** `05_categorizar_motivos.py`

❌ **Actual:** Inserta en tabla separada `motivos_categorizados`
✅ **Nuevo:** Actualizar campos de categoría directamente en `respuestas_nps_csat`:
```python
UPDATE respuestas_nps_csat
SET categoria = %s,
    categoria_confianza = %s,
    es_ruido = %s
WHERE id = %s
```

### 3. **Análisis de Sentimientos (MODIFICAR)**
**Archivo:** `06_analisis_sentimientos.py`

❌ **Actual:** Inserta en tabla separada `sentimientos_analisis`
✅ **Nuevo:** Actualizar campos de sentimiento en `respuestas_nps_csat`:
```python
UPDATE respuestas_nps_csat
SET sentimiento = %s,
    sentimiento_confianza = %s
WHERE id = %s
```

### 4. **Visualizaciones (SIMPLIFICAR)**
**Archivos:** `07_visualizar_*.py`

❌ **Actual:** Queries con UNION de múltiples tablas
✅ **Nuevo:** Queries directas a `respuestas_nps_csat` o vistas materializadas

### 5. **Estructura de Carpetas de Datos (MANTENER)**
✅ **Correcto:** Ya tienes `datos/raw/` organizado por mes
✅ **Mantener:** Esta estructura alimenta bien el particionamiento por mes

---

## 📝 PRÓXIMOS PASOS RECOMENDADOS

### Paso 1: Validar Estructura (1-2 días)
1. Revisar este plan con tu equipo
2. Ajustar campos según necesidades específicas
3. Decidir qué metadata adicional necesitas en JSONB

### Paso 2: Crear Scripts de Migración (2-3 días)
1. Script SQL para crear nueva estructura
2. Script SQL para migrar datos existentes
3. Script para validar migración

### Paso 3: Actualizar Pipeline ETL (3-5 días)
1. Modificar `04_insercion.py` para nueva tabla
2. Modificar `05_categorizar_motivos.py` para UPDATE directo
3. Modificar `06_analisis_sentimientos.py` para UPDATE directo
4. Probar con dataset pequeño

### Paso 4: Migrar Datos en Producción (1 día)
1. Crear backup completo
2. Ejecutar migración
3. Validar resultados
4. Crear vistas materializadas

### Paso 5: Actualizar Reportes (2-3 días)
1. Reescribir queries de visualización
2. Aprovechar vistas materializadas
3. Optimizar performance

---

## ❓ PREGUNTAS PARA DECIDIR

Antes de implementar, necesito que respondas:

1. **¿Necesitas mantener los datos históricos en las tablas viejas?**
   - Si: Mantener ambas estructuras temporalmente
   - No: Migrar todo y eliminar tablas viejas

2. **¿Qué tan frecuente actualizarás las vistas materializadas?**
   - Diario, semanal, mensual?
   - Esto afecta la estrategia de refresco

3. **¿Necesitas reportes en tiempo real o pueden tener 24h de retraso?**
   - Tiempo real: No usar vistas materializadas
   - 24h OK: Vistas materializadas son perfectas

4. **¿Cuántos meses de datos históricos planeas mantener en línea?**
   - Esto afecta estrategia de particionamiento y archivado

5. **¿Qué metadata específica necesitas por canal?**
   - BM: ¿qué campos adicionales?
   - BV: ¿qué campos adicionales?

---

**¿Procedemos con este plan?** Puedo empezar creando los scripts SQL de migración o ajustar la propuesta según tus necesidades.
