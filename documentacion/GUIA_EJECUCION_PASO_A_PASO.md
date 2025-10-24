# Guía de Ejecución Paso a Paso - Pipeline ETL NPS/CSAT

Esta guía documenta el proceso completo para ejecutar el pipeline de análisis de datos NPS/CSAT desde la extracción hasta la generación de reportes finales.

## Requisitos Previos

### 1. Entorno Virtual
```bash
# Crear entorno virtual (primera vez)
python -m venv .venv

# Activar entorno virtual
# En Windows:
.venv\Scripts\activate
# En Linux/Mac:
source .venv/bin/activate

# Instalar dependencias
pip install pandas openpyxl sqlalchemy psycopg2-binary matplotlib wordcloud pyyaml ahocorasick
```

### 2. Base de Datos PostgreSQL
- Base de datos: `nps_analitycs`
- Usuario: `postgres`
- Contraseña: `postgres`
- Puerto: `5432`
- Host: `localhost`

### 3. Estructura de Datos
- Archivos Excel fuente en: `datos/raw/`
- Archivos procesados: `datos/procesados/`
- Archivos limpios: `datos/clean/`

---

## Pipeline ETL - Orden de Ejecución

### PASO 1: Validar Conexión a Base de Datos
```bash
python 01_validar_conexion.py
```

**Propósito**: Verificar que la conexión a PostgreSQL está funcionando correctamente.

**Resultado esperado**: Mensaje de conexión exitosa.

---

### PASO 2: Extracción de Datos
```bash
python 02_extractor.py
```

**Propósito**:
- Leer archivos Excel de `datos/raw/`
- Extraer datos de NPS y CSAT de Banco Móvil y Banco Virtual
- Validar estructura y calidad de datos
- Generar archivos `.txt` con resúmenes de validación

**Entrada**: Archivos Excel en `datos/raw/`

**Salida**:
- Archivos `.xlsx` extraídos en `datos/procesados/`
- Archivos `.txt` y `.validation` con reportes
- Log: `extraccion_datos.log`

**Archivos procesados**:
- Banco Móvil: NPS y CSAT
- Banco Virtual: NPS

---

### PASO 3: Limpieza de Datos
```bash
python 03_limpieza.py
```

**Propósito**:
- Limpiar y normalizar datos extraídos
- Aplicar transformaciones y validaciones
- Preparar datos para inserción en BD

**Entrada**: Archivos de `datos/procesados/`

**Salida**:
- Archivos `*_LIMPIO.xlsx` en `datos/clean/`
- Archivos `.summary` con estadísticas
- Log: `data_cleaning.log`

---

### PASO 4: Inserción en Base de Datos
```bash
python 04_insercion.py
```

**Propósito**:
- Crear tablas en PostgreSQL si no existen
- Insertar datos limpios en las tablas correspondientes
- Aplicar constraints y validaciones de integridad

**Entrada**: Archivos de `datos/clean/`

**Salida**:
- Tablas pobladas en PostgreSQL:
  - `banco_movil_clean` (NPS y CSAT)
  - `banco_virtual_clean` (NPS)
- Log: `insercion_datos.log`

**Estructura de tablas**: Ver [ESTRUCTURA_BASE_DATOS.md](ESTRUCTURA_BASE_DATOS.md)

---

### PASO 5: Categorización de Motivos
```bash
python 05_categorizar_motivos.py --mode process --batch-size 5000
```

**Propósito**:
- Categorizar automáticamente comentarios de NPS/CSAT
- Asignar categorías basadas en palabras clave (archivo `categorias/categorias.yml`)
- Calcular scores de confianza
- Detectar y filtrar textos sin sentido/ruido

**Parámetros opcionales**:
```bash
# Explorar antes de procesar (recomendado primero)
python 05_categorizar_motivos.py --mode explore --limit 10000

# Procesar solo motivos sin categorizar
python 05_categorizar_motivos.py --mode process --only-uncategorized

# Cambiar tamaño de lote
python 05_categorizar_motivos.py --mode process --batch-size 10000
```

**Entrada**: Datos de tablas `banco_movil_clean` y `banco_virtual_clean`

**Salida**:
- Tabla `motivos_categorizados` poblada
- Log: `limpieza_categoria.log`

**Categorías**: Ver [GUIA_CATEGORIZACION.md](GUIA_CATEGORIZACION.md)

---

### PASO 6: Análisis de Sentimientos
```bash
python 06_analisis_sentimientos.py
```

**Propósito**:
- Analizar sentimientos (POSITIVO, NEUTRAL, NEGATIVO) de comentarios
- Utilizar modelo Ollama para análisis de lenguaje natural
- Procesamiento incremental (solo analiza comentarios nuevos)
- Deduplicación por hash SHA256

**Características**:
- Procesamiento paralelo para mayor velocidad
- Reutiliza análisis de comentarios duplicados
- Protección anti-duplicados en BD

**Requisito previo**: Tener Ollama instalado y corriendo
```bash
# Verificar que Ollama está corriendo
ollama list
```

**Entrada**: Comentarios de tablas `banco_movil_clean` y `banco_virtual_clean`

**Salida**:
- Tabla `sentimientos_analisis` poblada
- Columnas: `comentario_hash`, `sentimiento` (POS/NEU/NEG), `confianza`

---

### PASO 7: Visualización de Métricas NPS/CSAT
```bash
python 07_visualizar_metricas_nps_csat.py
```

**Propósito**:
- Generar tabla HTML con métricas mensuales de NPS y CSAT
- Calcular promedios, distribuciones y volúmenes
- Incluir fila consolidada con totales históricos

**Entrada**: Datos de PostgreSQL

**Salida**:
- `visualizaciones/tabla_nps.html` - Tabla interactiva con estilos
- Log: `visualizacion_nps.log`

**Métricas incluidas**:
- NPS: Promedio, Detractores, Neutrales, Promotores (cantidad y %)
- CSAT: Promedio, valores mín/máx, volumen
- Volumen total de registros por mes

---

### PASO 8: Visualización Consolidada
```bash
python 08_visualizar_consolidado.py
```

**Propósito**:
- Generar 5 tablas HTML consolidadas
- Diferenciar BM-NPS, BM-CSAT y BV-NPS
- Análisis comparativo por canal y tipo de métrica

**Salida**:
- Múltiples tablas HTML en `visualizaciones/`
- Vistas consolidadas por canal

---

### PASO 9: Visualización de Nubes de Palabras
```bash
python 09_visualizar_nubes_palabras.py
```

**Propósito**:
- Generar nubes de palabras para motivos NPS/CSAT
- Crear 8 nubes totales:
  - BM: 3 NPS (Detractores, Neutrales, Promotores) + 2 CSAT
  - BV: 3 NPS (Detractores, Neutrales, Promotores)

**Salida**:
- Imágenes PNG en `visualizaciones/`
- Log: `cloudwords.log`

**Características**:
- Filtrado de stopwords
- Normalización de texto
- Análisis de frecuencias

---

### PASO 10: Generación de Reporte Final
```bash
python 10_generar_reporte_final.py
```

**Propósito**:
- Consolidar todas las métricas y análisis
- Generar reporte ejecutivo final
- Resumen de insights y hallazgos clave

**Salida**:
- Reporte final en `outputs/`

---

## Utilidades de Categorización (Carpeta `categorias/`)

### Optimización de Categorías
```bash
cd categorias
python 9_optimizar_categorias.py --db-name nps_analitycs --limit 50000
```

**Propósito**:
- Analizar textos categorizados como "Otros"
- Identificar textos rechazados incorrectamente
- Generar sugerencias de nuevas palabras clave y categorías

---

### Crear Tabla de Categorías
```bash
cd categorias
python 10_crear_tabla_categorias.py --db-name nps_analitycs
```

**Propósito**:
- Crear/recrear tabla `motivos_categorizados`
- Establecer relaciones con tablas originales

---

### Visualizar Estadísticas de Categorías
```bash
cd categorias
python 11_visualizar_categorias.py
```

**Propósito**:
- Generar visualizaciones de distribución de categorías
- Análisis estadístico de categorizaciones
- Métricas de cobertura y confianza

---

### Agregar Columna de Longitud
```bash
cd categorias
python 12_agregar_columna_longitud.py
```

**Propósito**:
- Agregar columna de longitud de texto a las tablas
- Útil para análisis de calidad de comentarios

---

## Flujo Completo - Script Único

Para ejecutar todo el pipeline de una sola vez:

```bash
# Activar entorno virtual
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Ejecutar pipeline completo
python 01_validar_conexion.py && \
python 02_extractor.py && \
python 03_limpieza.py && \
python 04_insercion.py && \
python 05_categorizar_motivos.py --mode process && \
python 06_analisis_sentimientos.py && \
python 07_visualizar_metricas_nps_csat.py && \
python 08_visualizar_consolidado.py && \
python 09_visualizar_nubes_palabras.py && \
python 10_generar_reporte_final.py
```

**Nota**: En Windows, usar `&&` entre comandos. Los comandos se detendrán si hay algún error.

---

## Solución de Problemas

### Error de Conexión a PostgreSQL
```bash
# Verificar que PostgreSQL está corriendo
# Windows:
net start postgresql-x64-14  # Ajustar versión según instalación

# Verificar puerto
netstat -an | findstr 5432
```

### Error de Módulos Python
```bash
# Reinstalar dependencias
pip install --upgrade -r requirements.txt

# O instalar manualmente
pip install pandas openpyxl sqlalchemy psycopg2-binary matplotlib wordcloud pyyaml ahocorasick
```

### Ollama no disponible (Paso 6)
```bash
# Descargar e instalar Ollama
# https://ollama.ai/

# Iniciar Ollama
ollama serve

# Descargar modelo (si es necesario)
ollama pull llama2
```

### Archivos no encontrados
```bash
# Verificar estructura de carpetas
ls -R datos/

# Verificar que archivos Excel están en datos/raw/
ls datos/raw/
```

---

## Logs y Monitoreo

Cada script genera su propio archivo de log:

- `extraccion_datos.log` - Extracción
- `data_cleaning.log` - Limpieza
- `insercion_datos.log` - Inserción
- `limpieza_categoria.log` - Categorización
- `visualizacion_nps.log` - Visualizaciones
- `cloudwords.log` - Nubes de palabras

**Ver logs en tiempo real**:
```bash
# Windows
Get-Content limpieza_categoria.log -Wait

# Linux/Mac
tail -f limpieza_categoria.log
```

---

## Archivos de Configuración

### categorias/categorias.yml
Define las categorías y palabras clave para la categorización automática.

**Estructura**:
```yaml
version: v9-20251020-refinamiento-final-profundo
categorias:
  - nombre: Categoría 1
    palabras_clave:
      - palabra1
      - palabra2
    min_len: 5
    descripcion: "Descripción de la categoría"
```

### Variables de Base de Datos
Ubicadas en cada script. Para cambiar configuración, editar:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}
```

---

## Mejores Prácticas

1. **Siempre ejecutar en orden**: Los pasos tienen dependencias entre sí
2. **Validar conexión primero**: Evita problemas posteriores
3. **Revisar logs**: Cada paso genera logs para debugging
4. **Explorar antes de procesar**: Usar modo `--mode explore` en categorización
5. **Backups**: Respaldar la base de datos antes de reprocesar
6. **Entorno virtual**: Siempre activar el entorno virtual antes de ejecutar

---

## Contacto y Soporte

Para dudas o problemas:
- Revisar logs de error
- Consultar documentación en `documentacion/`
- Verificar estructura de base de datos en `ESTRUCTURA_BASE_DATOS.md`
- Consultar guía de categorización en `GUIA_CATEGORIZACION.md`
