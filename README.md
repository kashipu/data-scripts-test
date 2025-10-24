# Pipeline de Análisis NPS/CSAT

Sistema completo de extracción, transformación, análisis y visualización de datos de NPS (Net Promoter Score) y CSAT (Customer Satisfaction) para Banco Móvil y Banco Virtual.

## Descripción

Este proyecto implementa un pipeline ETL completo que:
- Extrae datos de archivos Excel
- Limpia y valida la información
- Almacena en PostgreSQL
- Categoriza motivos automáticamente usando palabras clave
- Analiza sentimientos con IA (Ollama)
- Genera visualizaciones y reportes ejecutivos

## Estructura del Proyecto

```
datos/
├── 01_validar_conexion.py              # Validación de conexión a BD
├── 02_extractor.py                     # Extracción de datos Excel
├── 03_limpieza.py                      # Limpieza y normalización
├── 04_insercion.py                     # Inserción en PostgreSQL
├── 05_categorizar_motivos.py           # Categorización automática
├── 06_analisis_sentimientos.py        # Análisis de sentimientos (Ollama)
├── 07_visualizar_metricas_nps_csat.py # Tabla HTML de métricas
├── 08_visualizar_consolidado.py       # Visualizaciones consolidadas
├── 09_visualizar_nubes_palabras.py    # Word clouds por categoría
├── 10_generar_reporte_final.py        # Reporte ejecutivo final
│
├── datos/                              # Carpeta de datos
│   ├── raw/                           # Datos originales (Excel)
│   ├── procesados/                    # Datos extraídos
│   └── clean/                         # Datos limpios
│
├── categorias/                         # Utilidades de categorización
│   ├── categorias.yml                 # Definición de categorías
│   ├── 9_optimizar_categorias.py      # Optimización de categorías
│   ├── 10_crear_tabla_categorias.py   # Creación de tabla
│   ├── 11_visualizar_categorias.py    # Estadísticas de categorías
│   └── 12_agregar_columna_longitud.py # Agregar campo de longitud
│
├── documentacion/                      # Documentación completa
│   ├── README.md                      # Este archivo
│   ├── GUIA_EJECUCION_PASO_A_PASO.md # Guía detallada de uso
│   ├── ESTRUCTURA_BASE_DATOS.md       # Schema de PostgreSQL
│   └── GUIA_CATEGORIZACION.md         # Categorías y palabras clave
│
├── outputs/                            # Resultados finales
├── visualizaciones/                    # Gráficos y tablas HTML
└── .venv/                             # Entorno virtual Python
```

## Inicio Rápido

### 1. Requisitos

- Python 3.8+
- PostgreSQL 12+
- Ollama (para análisis de sentimientos)

### 2. Instalación

```bash
# Clonar repositorio
git clone <repository-url>
cd datos

# Crear entorno virtual
python -m venv .venv

# Activar entorno virtual
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instalar dependencias
pip install pandas openpyxl sqlalchemy psycopg2-binary matplotlib wordcloud pyyaml ahocorasick
```

### 3. Configuración de Base de Datos

```sql
-- Crear base de datos
CREATE DATABASE nps_analitycs;

-- Usuario por defecto: postgres
-- Contraseña por defecto: postgres
-- Puerto: 5432
```

### 4. Ejecución del Pipeline

```bash
# Paso 1: Validar conexión
python 01_validar_conexion.py

# Paso 2: Extraer datos
python 02_extractor.py

# Paso 3: Limpiar datos
python 03_limpieza.py

# Paso 4: Insertar en BD
python 04_insercion.py

# Paso 5: Categorizar motivos
python 05_categorizar_motivos.py --mode process

# Paso 6: Analizar sentimientos
python 06_analisis_sentimientos.py

# Paso 7-10: Generar visualizaciones y reportes
python 07_visualizar_metricas_nps_csat.py
python 08_visualizar_consolidado.py
python 09_visualizar_nubes_palabras.py
python 10_generar_reporte_final.py
```

## Características Principales

### Extracción y Limpieza (Pasos 2-3)
- Validación automática de estructura de archivos Excel
- Detección de columnas requeridas
- Normalización de datos
- Generación de reportes de calidad

### Categorización Automática (Paso 5)
- Sistema basado en palabras clave (YAML)
- Algoritmo Aho-Corasick para alta performance (10-20x más rápido)
- Detección de textos sin sentido/ruido
- Scores de confianza para revisión humana
- Modo exploración antes de procesar

### Análisis de Sentimientos (Paso 6)
- Clasificación: POSITIVO, NEUTRAL, NEGATIVO
- Procesamiento incremental (solo nuevos comentarios)
- Deduplicación por hash SHA256
- Procesamiento paralelo
- Integración con Ollama

### Visualizaciones (Pasos 7-9)
- Tablas HTML interactivas con métricas mensuales
- Consolidación por canal (BM/BV) y tipo (NPS/CSAT)
- Nubes de palabras por categoría NPS
- Estilos profesionales y responsive

## Flujo de Datos

```
Excel (raw/) → Extracción → Limpieza → PostgreSQL
                                           ↓
                                    Categorización
                                           ↓
                                    Análisis Sentimientos
                                           ↓
                                    Visualizaciones → Reporte Final
```

## Métricas Analizadas

### NPS (Net Promoter Score)
- **Detractores**: Calificaciones 0-6
- **Neutrales**: Calificaciones 7-8
- **Promotores**: Calificaciones 9-10
- **NPS Score**: % Promotores - % Detractores

### CSAT (Customer Satisfaction)
- **Satisfechos**: Calificaciones 4-5
- **Neutrales**: Calificación 3
- **Insatisfechos**: Calificaciones 1-2
- **CSAT Score**: Promedio de satisfacción

## Categorías de Motivos

Las categorías se definen en [categorias/categorias.yml](categorias/categorias.yml):

- Texto Sin Sentido / Ruido
- Falta de Información / N/A
- Información de Producto y Servicio
- Experiencia Positiva General
- Problemas Técnicos y Funcionalidad
- Atención al Cliente
- Seguridad y Confianza
- Problemas de Acceso y Uso
- Y más... (ver archivo YAML completo)

## Documentación Completa

Consulta la documentación detallada en la carpeta [documentacion/](documentacion/):

- **[GUIA_EJECUCION_PASO_A_PASO.md](documentacion/GUIA_EJECUCION_PASO_A_PASO.md)**: Guía completa con comandos y explicaciones
- **[ESTRUCTURA_BASE_DATOS.md](documentacion/ESTRUCTURA_BASE_DATOS.md)**: Schema de PostgreSQL y tablas
- **[GUIA_CATEGORIZACION.md](documentacion/GUIA_CATEGORIZACION.md)**: Detalles sobre categorías y optimización

## Utilidades Adicionales

### Optimización de Categorías
```bash
cd categorias
python 9_optimizar_categorias.py --db-name nps_analitycs --limit 50000
```
Analiza textos categorizados como "Otros" y sugiere nuevas palabras clave.

### Visualización de Categorías
```bash
cd categorias
python 11_visualizar_categorias.py
```
Genera estadísticas y distribuciones de categorías.

## Configuración

### Base de Datos
Edita `DB_CONFIG` en cada script para cambiar la configuración:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'
}
```

### Categorías
Edita [categorias/categorias.yml](categorias/categorias.yml) para:
- Agregar nuevas categorías
- Modificar palabras clave
- Ajustar longitudes mínimas
- Actualizar descripciones

## Logs

Cada script genera su propio archivo de log:

- `extraccion_datos.log`
- `data_cleaning.log`
- `insercion_datos.log`
- `limpieza_categoria.log`
- `visualizacion_nps.log`
- `cloudwords.log`

## Solución de Problemas

### PostgreSQL no conecta
```bash
# Windows: Verificar servicio
net start postgresql-x64-14

# Verificar puerto
netstat -an | findstr 5432
```

### Ollama no disponible
```bash
# Instalar desde https://ollama.ai/
ollama serve

# Verificar modelos disponibles
ollama list
```

### Módulos Python faltantes
```bash
pip install --upgrade pandas openpyxl sqlalchemy psycopg2-binary matplotlib wordcloud pyyaml ahocorasick
```

## Tecnologías Utilizadas

- **Python 3.8+**: Lenguaje principal
- **PostgreSQL**: Base de datos relacional
- **Pandas**: Manipulación de datos
- **SQLAlchemy**: ORM y manejo de BD
- **Matplotlib + WordCloud**: Visualizaciones
- **Ollama**: Análisis de sentimientos con IA
- **Aho-Corasick**: Búsqueda rápida de patrones
- **YAML**: Configuración de categorías

## Contribución

Para contribuir al proyecto:

1. Revisar estructura de código en scripts numerados
2. Seguir convenciones de nombrado existentes
3. Actualizar documentación al hacer cambios
4. Probar pipeline completo antes de commit

## Licencia

[Especificar licencia del proyecto]

## Contacto

[Información de contacto o equipo responsable]

---

**Versión del Pipeline**: 2.0
**Última actualización**: Octubre 2025
**Estado**: Producción
