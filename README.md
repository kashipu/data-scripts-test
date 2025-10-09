# Pipeline de Procesamiento de Datos NPS

Sistema automatizado para extraer, limpiar e insertar datos de encuestas NPS (Net Promoter Score) desde archivos Excel a PostgreSQL.

## 📋 Tabla de Contenidos

- [Requisitos](#requisitos)
- [Configuración Inicial](#configuración-inicial)
- [Estructura del Proyecto](#estructura-del-proyecto)
- [Orden de Ejecución](#orden-de-ejecución)
- [Scripts Principales](#scripts-principales)
- [Scripts Auxiliares](#scripts-auxiliares)
- [Solución de Problemas](#solución-de-problemas)

---

## 🔧 Requisitos

### Software necesario:
- **Python 3.8+**
- **PostgreSQL 12+**

### Librerías Python:
```bash
pip install pandas sqlalchemy psycopg2-binary openpyxl
```

---

## ⚙️ Configuración Inicial

### 1. Crear base de datos en PostgreSQL

```sql
CREATE DATABASE nps_analytics;
```

**⚠️ Importante:** La base de datos se llama `nps_analytics` (nombre de producción, no usar "test" o "sample")

### 2. Actualizar credenciales en los scripts

Edita la variable `DB_CONFIG` en los siguientes archivos:

- `test_connection.py`
- `insertar_muestras.py`
- `setup_constraints.py`
- `inspect_database.py`
- `cleanup_database.py`

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analytics',  # ⬅️ Cambiar aquí
    'user': 'postgres',
    'password': 'TU_CONTRASEÑA'   # ⬅️ Cambiar aquí
}
```

### 3. Crear estructura de carpetas

El sistema espera la siguiente estructura (se crea automáticamente al ejecutar scripts):

```
datos/
├── data-cruda/          # Archivos Excel originales (input)
├── datos_raw/           # Datos extraídos en CSV (generado)
├── datos_clean/         # Datos limpios listos para inserción (generado)
├── test_connection.py
├── data_extractor.py
├── data_cleaner.py
├── insertar_muestras.py
├── setup_constraints.py
├── inspect_database.py
└── cleanup_database.py
```

---

## 📂 Estructura del Proyecto

### Carpetas de datos:

| Carpeta | Propósito | Contenido |
|---------|-----------|-----------|
| `data-cruda/` | **Input** - Archivos originales | Archivos Excel mensuales (`agosto_bm_2025.xlsx`, `agosto_bv_2025.xlsx`) |
| `datos_raw/` | **Intermediario** - Datos extraídos | CSV con datos sin procesar (`agosto_bm_2025_raw.csv`) |
| `datos_clean/` | **Intermediario** - Datos limpios | CSV listos para inserción (`agosto_bm_2025_clean.csv`) |

### Tablas de PostgreSQL:

| Tabla | Registros | Tamaño | Descripción |
|-------|-----------|--------|-------------|
| `banco_movil_clean` | 1.2M+ | 704 MB | Datos de encuestas Banco Móvil (BM) |
| `banco_virtual_clean` | 5.7K+ | 2 MB | Datos de encuestas Banco Virtual (BV) |

---

## 🚀 Orden de Ejecución

### Pipeline Completo (Primera Vez)

Sigue este orden exacto para procesar datos nuevos:

#### **Paso 1: Validar Conexión a Base de Datos**

```bash
python test_connection.py
```

**¿Qué hace?**
- Verifica conectividad a PostgreSQL
- Prueba inserción de datos de prueba
- Valida encoding UTF-8 para caracteres especiales

**Resultado esperado:**
```
✅ Conexión exitosa a PostgreSQL
PostgreSQL version: 16.x
✅ Datos de prueba insertados correctamente
```

---

#### **Paso 2: Extraer Datos de Excel**

```bash
python data_extractor.py
```

**¿Qué hace?**
- Lee archivos Excel desde `data-cruda/`
- Extrae hasta 300,000 registros por archivo
- Genera archivos CSV en `datos_raw/`

**Input:** `data-cruda/agosto_bm_2025.xlsx`, `data-cruda/agosto_bv_2025.xlsx`

**Output:** `datos_raw/agosto_bm_2025_raw.csv`, `datos_raw/agosto_bv_2025_raw.csv`

**Resultado esperado:**
```
✅ Extraídos 50,000 registros de agosto_bm_2025.xlsx → datos_raw/agosto_bm_2025_raw.csv
✅ Extraídos 200 registros de agosto_bv_2025.xlsx → datos_raw/agosto_bv_2025_raw.csv
```

---

#### **Paso 3: Limpiar y Transformar Datos**

```bash
python data_cleaner.py
```

**¿Qué hace?**
- Lee archivos CSV desde `datos_raw/`
- Corrige encoding UTF-8 malformado (Ã³→ó, Ã¡→á)
- Expande JSON de respuestas (solo BM)
- Calcula categoría NPS (Detractor/Neutral/Promotor)
- Genera archivos CSV limpios en `datos_clean/`

**Input:** `datos_raw/agosto_bm_2025_raw.csv`

**Output:** `datos_clean/agosto_bm_2025_clean.csv`

**Resultado esperado:**
```
✅ Limpiados 50,000 registros de agosto_bm_2025_raw.csv → datos_clean/agosto_bm_2025_clean.csv
✅ Limpiados 200 registros de agosto_bv_2025_raw.csv → datos_clean/agosto_bv_2025_clean.csv
```

---

#### **Paso 4: Configurar Restricciones UNIQUE (Solo primera vez)**

```bash
python setup_constraints.py
```

**¿Qué hace?**
- Crea restricciones UNIQUE en tablas de producción
- Previene duplicados a nivel de base de datos
- **Ejecutar solo una vez** al configurar la base de datos

**Restricciones creadas:**
- `banco_movil_clean`: UNIQUE(record_id, source_file)
- `banco_virtual_clean`: UNIQUE(date_submitted, nps_score_bv, source_file)

**Resultado esperado:**
```
✅ Constraint creado: banco_movil_clean UNIQUE(record_id, source_file)
✅ Constraint creado: banco_virtual_clean UNIQUE(date_submitted, nps_score_bv, source_file)
```

---

#### **Paso 5: Insertar Datos en PostgreSQL**

```bash
python insertar_muestras.py
```

**¿Qué hace?**
- Lee archivos CSV desde `datos_clean/`
- Verifica si el archivo ya fue insertado (prevención de duplicados)
- Inserta datos en `banco_movil_clean` o `banco_virtual_clean`
- Crea índices para consultas rápidas

**Input:** `datos_clean/agosto_bm_2025_clean.csv`

**Output:** Registros en tablas PostgreSQL

**Prevención de duplicados:**
- ✅ **Aplicación:** Verifica `source_file` antes de insertar
- ✅ **Base de datos:** UNIQUE constraints rechazan duplicados

**Resultado esperado:**
```
✅ Insertados 50,000 registros en banco_movil_clean desde agosto_bm_2025_clean.csv
✅ Insertados 200 registros en banco_virtual_clean desde agosto_bv_2025_clean.csv
⚠️  Archivo agosto_bm_2025_clean.csv ya fue insertado previamente (omitido)
```

---

### Pipeline Incremental (Meses Posteriores)

Para procesar nuevos meses de datos:

```bash
# 1. Colocar nuevos archivos Excel en data-cruda/
#    Ejemplo: septiembre_bm_2025.xlsx, septiembre_bv_2025.xlsx

# 2. Ejecutar pipeline (sin setup_constraints.py)
python data_extractor.py
python data_cleaner.py
python insertar_muestras.py
```

**⚠️ Nota:** `setup_constraints.py` solo se ejecuta una vez. Los siguientes meses solo requieren los pasos 2, 3 y 5.

---

## 📚 Scripts Principales

### 1. test_connection.py
**Propósito:** Validar configuración de base de datos

**Usa este script cuando:**
- Configuras el sistema por primera vez
- Cambias credenciales de base de datos
- Detectas problemas de conexión

**Ejecución:**
```bash
python test_connection.py
```

---

### 2. data_extractor.py
**Propósito:** Extraer datos desde archivos Excel a CSV

**Configuración:**
- Línea 12: `max_records = 300000` (cambiar para extraer menos registros en pruebas)

**Detecta archivos por patrón:**
- `*_bm_*.xlsx` → Banco Móvil
- `*_bv_*.xlsx` → Banco Virtual

**Ejecución:**
```bash
python data_extractor.py
```

---

### 3. data_cleaner.py
**Propósito:** Limpiar y transformar datos

**Operaciones clave:**
- ✅ Corrección de encoding UTF-8
- ✅ Expansión de JSON `answers` (BM)
- ✅ Cálculo de NPS score
- ✅ Categorización (Detractor/Neutral/Promotor)
- ✅ Normalización de fechas

**Ejecución:**
```bash
python data_cleaner.py
```

---

### 4. insertar_muestras.py
**Propósito:** Insertar datos limpios en PostgreSQL

**Características:**
- ✅ Prevención de duplicados (aplicación + base de datos)
- ✅ Inserción en lotes (1000 registros por batch)
- ✅ Creación automática de índices
- ✅ Logging detallado

**Ejecución:**
```bash
python insertar_muestras.py
```

---

## 🛠️ Scripts Auxiliares

### setup_constraints.py
**Propósito:** Configurar restricciones UNIQUE (una sola vez)

**Cuándo ejecutar:**
- ✅ Primera vez que configuras la base de datos
- ❌ NO ejecutar en cada inserción de datos

**Ejecución:**
```bash
python setup_constraints.py
```

---

### inspect_database.py
**Propósito:** Generar documentación de estructura de base de datos

**Output:** Archivo `database_structure.txt` con:
- Lista de tablas
- Columnas y tipos de datos
- Constraints e índices
- Registros de ejemplo
- Tamaño de tablas

**Ejecución:**
```bash
python inspect_database.py
```

---

### cleanup_database.py
**Propósito:** Eliminar tablas obsoletas de prueba

**Modos:**
```bash
# Modo dry-run (solo muestra qué se eliminaría)
python cleanup_database.py

# Modo ejecución (elimina tablas confirmadas)
python cleanup_database.py --execute
```

**⚠️ Tablas protegidas (NUNCA se eliminan):**
- `banco_movil_clean`
- `banco_virtual_clean`

---

## 🐛 Solución de Problemas

### Error: "No se puede conectar a PostgreSQL"

**Solución:**
1. Verifica que PostgreSQL esté corriendo:
   ```bash
   # Windows
   sc query postgresql-x64-16

   # Linux/Mac
   sudo systemctl status postgresql
   ```
2. Revisa credenciales en `DB_CONFIG`
3. Ejecuta `python test_connection.py`

---

### Error: "IntegrityError: duplicate key value violates unique constraint"

**Causa:** Intentando insertar un archivo que ya existe en la base de datos

**Solución:**
- ✅ Este es el comportamiento esperado (prevención de duplicados)
- El archivo será omitido automáticamente
- No requiere acción

---

### Error: "UnicodeDecodeError" al leer CSV

**Causa:** Archivo con encoding incorrecto

**Solución:**
1. Verifica que los archivos CSV se guardaron con UTF-8
2. Ejecuta `data_cleaner.py` nuevamente
3. Si persiste, abre el CSV en un editor y guarda con UTF-8

---

### Warning: "JSON inválido encontrado"

**Causa:** Campo `answers` con formato JSON corrupto (común en datos BM)

**Solución:**
- ✅ El script maneja esto automáticamente
- Convierte JSON inválido a `[]` (array vacío)
- No detiene el proceso

---

### Pregunta: "¿Cómo proceso solo un archivo de prueba?"

**Solución:**
1. Edita `data_extractor.py` línea 12:
   ```python
   max_records = 100  # Cambiar de 300000 a 100
   ```
2. Ejecuta pipeline normalmente
3. Restaura `max_records = 300000` para producción

---

### Pregunta: "¿Cómo verifico que los datos se insertaron correctamente?"

**Solución:**
```bash
# Generar reporte de base de datos
python inspect_database.py

# Revisar archivo generado
cat database_structure.txt
```

O consulta directamente en PostgreSQL:
```sql
-- Contar registros
SELECT COUNT(*) FROM banco_movil_clean;
SELECT COUNT(*) FROM banco_virtual_clean;

-- Ver últimos 10 registros
SELECT * FROM banco_movil_clean ORDER BY inserted_at DESC LIMIT 10;
```

---

## 📊 Archivos de Log

El sistema genera logs detallados:

| Archivo | Contenido |
|---------|-----------|
| `data_cleaning.log` | Operaciones de limpieza y transformación |
| `insercion_datos.log` | Inserciones en base de datos, duplicados detectados |

**Revisar logs:**
```bash
# Últimas 50 líneas de log de limpieza
tail -n 50 data_cleaning.log

# Últimas 50 líneas de log de inserción
tail -n 50 insercion_datos.log
```

---

## 📈 Flujo Visual del Pipeline

```
┌─────────────────────┐
│   data-cruda/       │
│  agosto_bm_2025.xlsx│ ──┐
└─────────────────────┘   │
                          │ python data_extractor.py
┌─────────────────────┐   │
│   data-cruda/       │   │
│  agosto_bv_2025.xlsx│ ──┤
└─────────────────────┘   │
                          ▼
                    ┌─────────────────────┐
                    │   datos_raw/        │
                    │ agosto_bm_2025_raw  │
                    │ agosto_bv_2025_raw  │
                    └─────────────────────┘
                          │
                          │ python data_cleaner.py
                          ▼
                    ┌─────────────────────┐
                    │   datos_clean/      │
                    │ agosto_bm_2025_clean│
                    │ agosto_bv_2025_clean│
                    └─────────────────────┘
                          │
                          │ python insertar_muestras.py
                          ▼
                    ┌─────────────────────┐
                    │   PostgreSQL        │
                    │ nps_analytics       │
                    │                     │
                    │ banco_movil_clean   │ (1.2M records)
                    │ banco_virtual_clean │ (5.7K records)
                    └─────────────────────┘
```

---

## ✅ Checklist de Primera Ejecución

- [ ] PostgreSQL instalado y corriendo
- [ ] Base de datos `nps_analytics` creada
- [ ] Librerías Python instaladas (`pandas`, `sqlalchemy`, `psycopg2-binary`, `openpyxl`)
- [ ] Credenciales actualizadas en todos los scripts (`DB_CONFIG`)
- [ ] Archivos Excel colocados en `data-cruda/`
- [ ] Ejecutado: `python test_connection.py` ✅
- [ ] Ejecutado: `python data_extractor.py` ✅
- [ ] Ejecutado: `python data_cleaner.py` ✅
- [ ] Ejecutado: `python setup_constraints.py` ✅ (solo primera vez)
- [ ] Ejecutado: `python insertar_muestras.py` ✅
- [ ] Verificado: `python inspect_database.py` ✅

---

## 📞 Soporte

Para más detalles técnicos, consulta:
- [CLAUDE.md](CLAUDE.md) - Documentación completa del proyecto
- [PREVENCION_DUPLICADOS.md](PREVENCION_DUPLICADOS.md) - Sistema de prevención de duplicados
- `database_structure.txt` - Esquema de base de datos (generado por `inspect_database.py`)

---

**Última actualización:** 2025-10-09
