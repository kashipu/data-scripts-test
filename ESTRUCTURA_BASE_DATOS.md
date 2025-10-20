# Estructura de Base de Datos - NPS Analytics
**Base de datos:** `nps_analitycs`
**Generado:** 2025-10-20 12:23:51

---

## Resumen de Tablas

| Tabla | Registros | Columnas |
|-------|-----------|----------|
| `banco_movil_clean` | 1,013,592 | 25 |
| `banco_virtual_clean` | 7,605 | 26 |
| `motivos_categorizados` | 604,441 | 14 |
| `sentimientos_analisis` | 6,184 | 21 |

---

## Tabla: `banco_movil_clean`

**Total de registros:** 1,013,592

### Columnas

| Columna | Tipo | Nulo | Default |
|---------|------|------|----------|
| `id` | integer | NO | nextval('banco_movil_clean_... |
| `timestamp` | timestamp without time zone | SI | - |
| `answer_date` | timestamp without time zone | SI | - |
| `answers` | text | SI | - |
| `channel` | character varying(50) | SI | - |
| `cust_ident_num` | bigint | SI | - |
| `cust_ident_type` | character varying(10) | SI | - |
| `feedback_type` | character varying(50) | SI | - |
| `record_id` | integer | SI | - |
| `nps_original` | character varying(50) | SI | - |
| `nps_recomendacion_score` | double precision | SI | - |
| `nps_recomendacion_motivo` | text | SI | - |
| `csat_satisfaccion_score` | double precision | SI | - |
| `csat_satisfaccion_motivo` | text | SI | - |
| `nps_score` | double precision | SI | - |
| `nps_category` | character varying(20) | SI | - |
| `cleaned_date` | timestamp without time zone | SI | - |
| `file_type` | character varying(10) | SI | - |
| `month_year` | character varying(20) | SI | - |
| `source_file` | character varying(255) | SI | - |
| `inserted_at` | timestamp without time zone | SI | now() |
| `categoria_motivo` | character varying(100) | SI | - |
| `confidence_categoria` | numeric | SI | - |
| `metadata_categoria` | text | SI | - |
| `categorizado_en` | timestamp without time zone | SI | - |

### Constraints

| Tipo | Nombre | Columna |
|------|--------|----------|
| PRIMARY KEY | `banco_movil_clean_pkey` | `id` |

### Índices

```sql
CREATE UNIQUE INDEX banco_movil_clean_pkey ON public.banco_movil_clean USING btree (id)
CREATE INDEX idx_banco_movil_clean_categoria ON public.banco_movil_clean USING btree (categoria_motivo)
CREATE INDEX idx_bm_category ON public.banco_movil_clean USING btree (nps_category)
CREATE INDEX idx_bm_month ON public.banco_movil_clean USING btree (month_year)
CREATE INDEX idx_bm_nps_score ON public.banco_movil_clean USING btree (nps_score)
CREATE INDEX idx_bm_source_file ON public.banco_movil_clean USING btree (source_file)
```

---

## Tabla: `banco_virtual_clean`

**Total de registros:** 7,605

### Columnas

| Columna | Tipo | Nulo | Default |
|---------|------|------|----------|
| `id` | integer | NO | nextval('banco_virtual_clea... |
| `date_submitted_original` | character varying(50) | SI | - |
| `date_submitted` | timestamp without time zone | SI | - |
| `country` | character varying(100) | SI | - |
| `source_url` | text | SI | - |
| `device` | character varying(100) | SI | - |
| `browser` | character varying(200) | SI | - |
| `operating_system` | character varying(200) | SI | - |
| `nps_score_bv` | integer | SI | - |
| `calificacion_acerca` | text | SI | - |
| `motivo_calificacion` | text | SI | - |
| `tags_recomendacion` | text | SI | - |
| `tags_calificacion` | text | SI | - |
| `tags_motivo` | text | SI | - |
| `sentiment_motivo` | text | SI | - |
| `month_year` | character varying(20) | SI | - |
| `nps_score` | integer | SI | - |
| `nps_category` | character varying(20) | SI | - |
| `cleaned_date` | timestamp without time zone | SI | - |
| `file_type` | character varying(10) | SI | - |
| `source_file` | character varying(255) | SI | - |
| `inserted_at` | timestamp without time zone | SI | now() |
| `categoria_motivo` | character varying(100) | SI | - |
| `confidence_categoria` | numeric | SI | - |
| `metadata_categoria` | text | SI | - |
| `categorizado_en` | timestamp without time zone | SI | - |

### Constraints

| Tipo | Nombre | Columna |
|------|--------|----------|
| PRIMARY KEY | `banco_virtual_clean_pkey` | `id` |

### Índices

```sql
CREATE UNIQUE INDEX banco_virtual_clean_pkey ON public.banco_virtual_clean USING btree (id)
CREATE INDEX idx_banco_virtual_clean_categoria ON public.banco_virtual_clean USING btree (categoria_motivo)
CREATE INDEX idx_bv_country ON public.banco_virtual_clean USING btree (country)
CREATE INDEX idx_bv_device ON public.banco_virtual_clean USING btree (device)
CREATE INDEX idx_bv_nps_score ON public.banco_virtual_clean USING btree (nps_score)
CREATE INDEX idx_bv_source_file ON public.banco_virtual_clean USING btree (source_file)
```

---

## Tabla: `motivos_categorizados`

**Total de registros:** 604,441

### Columnas

| Columna | Tipo | Nulo | Default |
|---------|------|------|----------|
| `id` | integer | NO | nextval('motivos_categoriza... |
| `tabla_origen` | character varying(50) | NO | - |
| `registro_id` | integer | NO | - |
| `campo_motivo` | character varying(50) | NO | - |
| `texto_motivo` | text | SI | - |
| `canal` | character varying(10) | SI | - |
| `metrica` | character varying(10) | SI | - |
| `score_metrica` | integer | SI | - |
| `categoria` | character varying(100) | SI | - |
| `confidence` | numeric | SI | - |
| `metadata_categoria` | text | SI | - |
| `es_ruido` | boolean | SI | false |
| `razon_ruido` | character varying(50) | SI | - |
| `categorizado_en` | timestamp without time zone | SI | now() |

### Constraints

| Tipo | Nombre | Columna |
|------|--------|----------|
| PRIMARY KEY | `motivos_categorizados_pkey` | `id` |
| UNIQUE | `unique_registro_campo` | `tabla_origen` |
| UNIQUE | `unique_registro_campo` | `registro_id` |
| UNIQUE | `unique_registro_campo` | `campo_motivo` |

### Índices

```sql
CREATE INDEX idx_motivos_cat_canal_metrica ON public.motivos_categorizados USING btree (canal, metrica)
CREATE INDEX idx_motivos_cat_categoria ON public.motivos_categorizados USING btree (categoria)
CREATE INDEX idx_motivos_cat_es_ruido ON public.motivos_categorizados USING btree (es_ruido)
CREATE INDEX idx_motivos_cat_registro_id ON public.motivos_categorizados USING btree (registro_id)
CREATE INDEX idx_motivos_cat_tabla_origen ON public.motivos_categorizados USING btree (tabla_origen)
CREATE UNIQUE INDEX motivos_categorizados_pkey ON public.motivos_categorizados USING btree (id)
CREATE UNIQUE INDEX unique_registro_campo ON public.motivos_categorizados USING btree (tabla_origen, registro_id, campo_motivo)
```

---

## Tabla: `sentimientos_analisis`

**Total de registros:** 6,184

### Columnas

| Columna | Tipo | Nulo | Default |
|---------|------|------|----------|
| `id` | integer | NO | nextval('sentimientos_anali... |
| `canal` | character varying(10) | NO | - |
| `tipo_comentario` | character varying(20) | NO | - |
| `tabla_origen` | character varying(50) | NO | - |
| `registro_origen_id` | integer | NO | - |
| `columna_origen` | character varying(100) | NO | - |
| `score_metrica` | numeric | SI | - |
| `categoria_metrica` | character varying(20) | SI | - |
| `comentario_texto` | text | NO | - |
| `comentario_hash` | character varying(64) | NO | - |
| `longitud_caracteres` | integer | NO | - |
| `longitud_palabras` | integer | SI | - |
| `sentimiento` | character varying(20) | NO | - |
| `confianza` | numeric | SI | - |
| `prob_positivo` | numeric | SI | - |
| `prob_neutral` | numeric | SI | - |
| `prob_negativo` | numeric | SI | - |
| `modelo_version` | character varying(100) | SI | 'pysentimiento/robertuito-s... |
| `dispositivo` | character varying(10) | SI | - |
| `analizado_en` | timestamp without time zone | SI | now() |
| `tiempo_procesamiento_ms` | integer | SI | - |

### Constraints

| Tipo | Nombre | Columna |
|------|--------|----------|
| PRIMARY KEY | `sentimientos_analisis_pkey` | `id` |
| UNIQUE | `sentimientos_analisis_tabla_origen_registro_origen_id_colum_key` | `tabla_origen` |
| UNIQUE | `sentimientos_analisis_tabla_origen_registro_origen_id_colum_key` | `registro_origen_id` |
| UNIQUE | `sentimientos_analisis_tabla_origen_registro_origen_id_colum_key` | `columna_origen` |

### Índices

```sql
CREATE INDEX idx_sentimientos_canal_tipo ON public.sentimientos_analisis USING btree (canal, tipo_comentario)
CREATE INDEX idx_sentimientos_fecha ON public.sentimientos_analisis USING btree (analizado_en)
CREATE INDEX idx_sentimientos_hash ON public.sentimientos_analisis USING btree (comentario_hash)
CREATE INDEX idx_sentimientos_lookup ON public.sentimientos_analisis USING btree (tabla_origen, registro_origen_id, columna_origen)
CREATE INDEX idx_sentimientos_origen ON public.sentimientos_analisis USING btree (tabla_origen, registro_origen_id)
CREATE INDEX idx_sentimientos_score_sent ON public.sentimientos_analisis USING btree (score_metrica, sentimiento) WHERE (score_metrica IS NOT NULL)
CREATE INDEX idx_sentimientos_sentimiento ON public.sentimientos_analisis USING btree (sentimiento)
CREATE UNIQUE INDEX sentimientos_analisis_pkey ON public.sentimientos_analisis USING btree (id)
CREATE UNIQUE INDEX sentimientos_analisis_tabla_origen_registro_origen_id_colum_key ON public.sentimientos_analisis USING btree (tabla_origen, registro_origen_id, columna_origen)
```
