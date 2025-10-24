# Estructura de Base de Datos - NPS Analytics

**Última actualización:** 20 de Octubre, 2025
**Versión:** 2.0 - Tabla Unificada Optimizada

---

## Resumen Ejecutivo

La base de datos utiliza una **tabla unificada particionada por mes** que consolida todos los datos de NPS/CSAT de ambos canales (Banco Móvil y Banco Virtual). Esta estructura optimiza:

- ✅ Queries por mes (70-90% más rápidas)
- ✅ Análisis consolidado sin JOINs complejos
- ✅ Categorización y sentimiento integrados
- ✅ Escalabilidad hasta 3 años de histórico

---

## Tabla Principal: `respuestas_nps_csat`

### Descripción
Almacena todas las respuestas de encuestas NPS y CSAT de ambos canales, con datos de categorización y sentimiento integrados.

### Características
- **Particionada por mes** usando `fecha_respuesta`
- **48 particiones** (2023-2026, 4 años)
- **Índices optimizados** para queries por canal, mes, categoría y sentimiento
- **Constraints de validación** para integridad de datos

### Esquema

```sql
CREATE TABLE respuestas_nps_csat (
    -- Identificadores
    id BIGSERIAL,
    record_id VARCHAR(100) NOT NULL,

    -- Dimensiones clave (para filtrado rápido)
    canal VARCHAR(10) NOT NULL,           -- 'BM' o 'BV'
    metrica VARCHAR(10) NOT NULL,         -- 'NPS' o 'CSAT'
    mes_anio VARCHAR(7) NOT NULL,         -- 'YYYY-MM' formato

    -- Fechas
    fecha_respuesta TIMESTAMP NOT NULL,
    fecha_procesamiento TIMESTAMP DEFAULT NOW(),

    -- Información del cliente (opcional)
    cliente_id BIGINT,
    cliente_tipo VARCHAR(50),

    -- Score y categorización de score
    score NUMERIC(4,2) NOT NULL,
    categoria_score VARCHAR(20),          -- 'Detractor', 'Neutral', 'Promotor' (solo NPS)

    -- Texto del motivo
    motivo_texto TEXT,

    -- Categorización automática
    categoria VARCHAR(100),
    categoria_confianza NUMERIC(3,2),     -- 0.00 a 1.00
    es_ruido BOOLEAN DEFAULT FALSE,
    razon_ruido VARCHAR(100),

    -- Análisis de sentimiento
    sentimiento VARCHAR(20),               -- 'POSITIVO', 'NEUTRAL', 'NEGATIVO'
    sentimiento_confianza NUMERIC(3,2),   -- 0.00 a 1.00

    -- Metadata mínima por canal
    feedback_type VARCHAR(50),             -- BM: tipo de feedback
    canal_respuesta VARCHAR(50),           -- BM: canal de respuesta
    dispositivo VARCHAR(50),               -- BV: tipo de dispositivo
    pais VARCHAR(10),                      -- BV: código de país

    -- Trazabilidad
    archivo_origen VARCHAR(255),

    -- Primary key compuesta
    PRIMARY KEY (id, fecha_respuesta)

) PARTITION BY RANGE (fecha_respuesta);
```

Ver scripts completos en: [sql/02_create_new_structure.sql](../sql/02_create_new_structure.sql)

---

## Vistas Materializadas para Reportes

### 1. `mv_resumen_mensual`
Métricas consolidadas por mes, canal y métrica.

### 2. `mv_top_categorias`
Top categorías con rankings.

### 3. `mv_sentimiento_por_categoria`
Distribución de sentimientos.

### 4. `mv_evolucion_temporal`
Tendencias a lo largo del tiempo.

### 5. `mv_analisis_detractores`
Análisis detallado de detractores.

Ver detalles completos en: [sql/03_create_views.sql](../sql/03_create_views.sql)

---

## Migración y Mantenimiento

Ver documentación completa en:
- [PLAN_OPTIMIZACION_BD.md](PLAN_OPTIMIZACION_BD.md) - Plan completo de optimización
- [sql/README.md](../sql/README.md) - Guía de scripts SQL
