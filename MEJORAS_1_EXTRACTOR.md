# 🚀 Mejoras Implementadas en 1_extractor.py

**Fecha:** 13 de octubre de 2025
**Versión:** 2.0

---

## ✅ Todas las Mejoras Solicitadas Implementadas

### 1. ✅ Carpeta `backups/` Creada

Todos los archivos de respaldo ahora están organizados en la carpeta `backups/`:

```
backups/
├── 1_extractor_backup.py
├── 1_extractor_original.py
├── 3_insercion_backup.py
└── 4_visualizacion_backup.py
```

---

### 2. ✅ Parámetro para Procesar Archivos Completos (Sin Número Extenso)

**Antes:**
```python
max_records = 300000  # Número fijo y extenso
```

**Ahora:**
```python
# Por defecto: Procesa archivos COMPLETOS (max_registros = None)
python 1_extractor.py              # Procesa TODOS los registros sin límite
python 1_extractor.py --full       # Explícitamente procesa completos
python 1_extractor.py --limit 5000 # Limita si es necesario
```

**Ventajas:**
- ✅ Modo por defecto: Extrae TODOS los registros
- ✅ Sin números extensos como 90000000
- ✅ Mensaje claro: "Extrayendo TODOS los registros (123,456)"
- ✅ Flexible: Puedes limitar si necesitas probar con menos datos

---

### 3. ✅ Sistema de Tracking para Evitar Reprocesamiento

**Archivo de tracking:** `datos_raw/.processed_files.txt`

**Cómo funciona:**
1. Cada vez que un archivo es procesado exitosamente, se registra su:
   - Ruta completa
   - Hash MD5 (para detectar si cambió)

2. En ejecuciones futuras:
   - ✅ Archivos ya procesados se omiten automáticamente
   - ⚠️  Si un archivo cambió (hash diferente), se reprocesa
   - 🔄 Opción `--force` permite reprocesar todos

**Ejemplo del archivo de tracking:**
```
data-cruda/Agosto/Agosto_BM_2025.xlsx|a3f5e8c9d1b2...
data-cruda/Agosto/Agosto_BV_2025.xlsx|b4f6e9c0d2b3...
data-cruda/Septiembre/Septiembre_BM_2025.xlsx|c5f7e0c1d3b4...
```

**Salida del script:**
```
📝 Archivos previamente procesados: 6

🏦 Banco Móvil - Agosto
   ⏭️  Omitiendo: Agosto_BM_2025.xlsx (ya procesado)

🏦 Banco Móvil - Septiembre
   📂 Procesando: data-cruda/Septiembre/Septiembre_BM_2025.xlsx
   ...
```

---

### 4. ✅ Opción para Procesar Solo un Archivo Específico

**Comando:**
```bash
python 1_extractor.py --file "Agosto_BM_2025.xlsx"
```

**Qué hace:**
- Solo procesa el archivo especificado
- Ignora todos los demás archivos
- Útil para:
  - Corregir problemas con un archivo específico
  - Reprocesar un solo mes
  - Pruebas y debugging

**Ejemplo de uso:**
```bash
# Problema detectado en archivo de Septiembre BM
python 1_extractor.py --file "Septiembre_BM_2025.xlsx" --force

# Output:
📄 Procesando solo: Septiembre_BM_2025.xlsx

🏦 Banco Móvil - Septiembre
   📂 Procesando: data-cruda/Septiembre/Septiembre_BM_2025.xlsx
   ...
```

---

### 5. ✅ Log Individual (.txt) por Cada Archivo Procesado

**Para cada archivo Excel procesado, se genera un archivo .txt con información detallada:**

**Ejemplo:** `datos_raw/Agosto_BM_2025_extracted_50000.txt`

```
================================================================================
LOG DE EXTRACCIÓN - 1_extractor.py
================================================================================

Fecha de extracción: 2025-10-13 14:32:15
Archivo original: Agosto_BM_2025.xlsx
Archivo de salida: Agosto_BM_2025_extracted_50000.xlsx
Tipo de archivo: BM

ESTADÍSTICAS:
  - Total registros en archivo original: 50,234
  - Registros extraídos: 50,000
  - Total columnas: 15

COLUMNAS CLAVE DETECTADAS:
  • timestamp
  • answerDate
  • answers
  • nps_score
  • feedbackType

ADVERTENCIAS:
  ⚠️  Archivo limitado a 50,000 registros
  ⚠️  Encoding UTF-8 malformado detectado en columna 'answers'

ESTADO: ✅ Exitoso
================================================================================
```

**Ubicación de logs:**
- **Individual por archivo:** `datos_raw/[nombre_archivo].txt`
- **Log general del script:** `extraccion_datos.log`

**Ventajas:**
- ✅ Historial completo de cada extracción
- ✅ Detección de problemas específicos por archivo
- ✅ Información útil para debugging
- ✅ Trazabilidad completa

---

### 6. ✅ Log General Mejorado

**Archivo:** `extraccion_datos.log`

**Contenido:**
```
2025-10-13 14:32:10 - INFO - Iniciando extracción - Modo: COMPLETO (sin límite)
2025-10-13 14:32:10 - INFO - Archivos en tracking: 4
2025-10-13 14:32:10 - INFO - Escaneando directorio: data-cruda
2025-10-13 14:32:10 - INFO - Encontrado BM: data-cruda/Agosto/Agosto_BM_2025.xlsx
2025-10-13 14:32:10 - INFO - Omitido (ya procesado): data-cruda/Agosto/Agosto_BM_2025.xlsx
2025-10-13 14:32:15 - INFO - Iniciando extracción: data-cruda/Septiembre/Septiembre_BM_2025.xlsx
2025-10-13 14:32:45 - INFO - 📄 Log individual generado: Septiembre_BM_2025_extracted_52000.txt
2025-10-13 14:32:45 - INFO - Extracción exitosa: datos_raw/Septiembre_BM_2025_extracted_52000.xlsx (52,000 registros)
2025-10-13 14:32:45 - INFO - 📝 Archivo registrado en tracking: Septiembre_BM_2025.xlsx
2025-10-13 14:33:00 - INFO - Extracción completada: 1 archivos, 52,000 registros
```

---

## 📋 Opciones de Línea de Comandos

### Todas las Opciones Disponibles:

```bash
# 1. Modo por defecto (procesa archivos nuevos completos)
python 1_extractor.py

# 2. Procesar archivos completos explícitamente
python 1_extractor.py --full

# 3. Limitar registros para pruebas
python 1_extractor.py --limit 5000

# 4. Procesar solo un archivo específico
python 1_extractor.py --file "Agosto_BM_2025.xlsx"

# 5. Forzar reprocesamiento de todos (ignorar tracking)
python 1_extractor.py --force

# 6. Combinar opciones
python 1_extractor.py --file "Septiembre_BM_2025.xlsx" --limit 1000 --force
```

### Ayuda del Script:

```bash
python 1_extractor.py --help

usage: 1_extractor.py [-h] [--full] [--limit LIMIT] [--file FILE] [--force]

Extractor de Datos NPS - Pipeline de Producción

optional arguments:
  -h, --help      show this help message and exit
  --full          Procesar archivos completos sin límite de registros
  --limit LIMIT   Número máximo de registros a extraer por archivo
  --file FILE     Nombre específico de archivo a procesar (ej: Agosto_BM_2025.xlsx)
  --force         Forzar reprocesamiento de archivos ya procesados

Ejemplos de uso:
  python 1_extractor.py                              # Procesa archivos nuevos
  python 1_extractor.py --full                       # Procesa archivos completos
  python 1_extractor.py --limit 5000                 # Limita a 5000 registros
  python 1_extractor.py --file "Agosto_BM_2025.xlsx" # Solo un archivo
  python 1_extractor.py --force                      # Fuerza reprocesamiento
```

---

## 🎯 Flujo de Trabajo Típico

### Primera Ejecución (Archivos Nuevos):

```bash
python 1_extractor.py

# Output:
🚀 EXTRACTOR DE DATOS NPS - PIPELINE DE PRODUCCIÓN
⚙️  MODO: COMPLETO (sin límite)

📝 Archivos previamente procesados: 0

🔍 Escaneando directorio: data-cruda

📁 Escaneando mes: Agosto
   ✅ Banco Móvil (BM): Agosto_BM_2025.xlsx
   ✅ Banco Virtual (BV): Agosto_BV_2025.xlsx

================================================================================
📅 PROCESANDO MES: Agosto
================================================================================

🏦 Banco Móvil - Agosto

📂 Procesando: data-cruda/Agosto/Agosto_BM_2025.xlsx
   ⏳ Leyendo archivo Excel...
   📊 Total de registros en archivo: 50,234
   📋 Columnas disponibles: 15
   ℹ️  Extrayendo TODOS los registros (50,234)
   💾 Guardando datos extraídos...
   ✅ Datos guardados: datos_raw/Agosto_BM_2025_extracted_50234.xlsx
   📈 Registros extraídos: 50,234

   📊 COLUMNAS CLAVE DETECTADAS:
      • timestamp
      • answerDate
      • answers

📄 Log individual generado: Agosto_BM_2025_extracted_50234.txt
📝 Archivo registrado en tracking: Agosto_BM_2025.xlsx

💻 Banco Virtual - Agosto
...

================================================================================
📊 RESUMEN DE EXTRACCIÓN
================================================================================

✅ ARCHIVOS PROCESADOS EXITOSAMENTE (2):

   BM - Agosto:
      Original: Agosto_BM_2025.xlsx
      Extraído: Agosto_BM_2025_extracted_50234.xlsx
      Registros: 50,234

   BV - Agosto:
      Original: Agosto_BV_2025.xlsx
      Extraído: Agosto_BV_2025_extracted_234.xlsx
      Registros: 234

📈 TOTAL: 2 archivos procesados, 50,468 registros extraídos

🎯 PRÓXIMOS PASOS:
   1. Revisar logs individuales (.txt) en 'datos_raw/'
   2. python 2_limpieza.py      # Limpiar y transformar datos
   3. python 3_insercion.py     # Insertar en PostgreSQL
   4. python 4_visualizacion.py # Generar dashboard

📝 Archivo de tracking actualizado: datos_raw/.processed_files.txt
   Total de archivos registrados: 2
```

### Segunda Ejecución (Archivos Ya Procesados):

```bash
python 1_extractor.py

# Output:
🚀 EXTRACTOR DE DATOS NPS - PIPELINE DE PRODUCCIÓN
⚙️  MODO: COMPLETO (sin límite)

📝 Archivos previamente procesados: 2

🔍 Escaneando directorio: data-cruda

📁 Escaneando mes: Agosto
   ✅ Banco Móvil (BM): Agosto_BM_2025.xlsx
   ✅ Banco Virtual (BV): Agosto_BV_2025.xlsx

================================================================================
📅 PROCESANDO MES: Agosto
================================================================================

🏦 Banco Móvil - Agosto
   ⏭️  Omitiendo: Agosto_BM_2025.xlsx (ya procesado)

💻 Banco Virtual - Agosto
   ⏭️  Omitiendo: Agosto_BV_2025.xlsx (ya procesado)

================================================================================
📊 RESUMEN DE EXTRACCIÓN
================================================================================

⏭️  ARCHIVOS OMITIDOS (ya procesados): 2
   • BM - Agosto: Agosto_BM_2025.xlsx
   • BV - Agosto: Agosto_BV_2025.xlsx
```

### Reprocesar un Archivo Modificado:

```bash
# El archivo Agosto_BM_2025.xlsx fue modificado/actualizado
python 1_extractor.py

# Output:
⚠️  Archivo modificado detectado: Agosto_BM_2025.xlsx

🏦 Banco Móvil - Agosto
📂 Procesando: data-cruda/Agosto/Agosto_BM_2025.xlsx
   ...
```

---

## 📊 Archivos Generados

### Estructura de `datos_raw/` Después de Extracción:

```
datos_raw/
├── .processed_files.txt                      ← Tracking de archivos procesados
│
├── Agosto_BM_2025_extracted_50234.xlsx      ← Datos extraídos
├── Agosto_BM_2025_extracted_50234.txt       ← Log individual
│
├── Agosto_BV_2025_extracted_234.xlsx
├── Agosto_BV_2025_extracted_234.txt
│
├── Septiembre_BM_2025_extracted_52100.xlsx
├── Septiembre_BM_2025_extracted_52100.txt
│
└── Septiembre_BV_2025_extracted_198.xlsx
    Septiembre_BV_2025_extracted_198.txt
```

---

## 🔍 Comparación: Antes vs Ahora

| Aspecto | Antes | Ahora |
|---------|-------|-------|
| **Límite de registros** | Número fijo (300,000) | `--full` (sin límite) o `--limit N` |
| **Reprocesamiento** | Siempre reprocesa todo | Sistema de tracking evita reprocesar |
| **Archivo específico** | No disponible | `--file "nombre.xlsx"` |
| **Logs individuales** | Solo log general | `.txt` por cada archivo + log general |
| **Detección de cambios** | No detecta | Hash MD5 detecta archivos modificados |
| **Forzar reproceso** | No disponible | `--force` flag |
| **Backups** | Dispersos | Carpeta `backups/` organizada |

---

## ✅ Checklist de Implementación

- [x] ✅ Parámetro `--full` para procesar archivos completos
- [x] ✅ Parámetro `--limit N` para limitar registros
- [x] ✅ Sistema de tracking con `.processed_files.txt`
- [x] ✅ Hash MD5 para detectar archivos modificados
- [x] ✅ Opción `--file` para procesar archivo específico
- [x] ✅ Opción `--force` para reprocesar todos
- [x] ✅ Log individual `.txt` por cada archivo procesado
- [x] ✅ Log general mejorado `extraccion_datos.log`
- [x] ✅ Carpeta `backups/` para archivos de respaldo
- [x] ✅ Formato de salida optimizado para `2_limpieza.py`

---

## 🎓 Documentación Adicional

### Variables de Configuración:

```python
# En 1_extractor.py (líneas 76-85)
DIRECTORIO_ENTRADA = "data-cruda"           # Archivos Excel originales
DIRECTORIO_SALIDA = "datos_raw"             # Datos extraídos
ARCHIVO_TRACKING = ".processed_files.txt"   # Tracking
LOG_GENERAL = "extraccion_datos.log"        # Log general
```

### Funciones Principales:

1. `obtener_hash_archivo()` - Genera hash MD5 del archivo
2. `cargar_archivos_procesados()` - Lee archivo de tracking
3. `registrar_archivo_procesado()` - Actualiza tracking
4. `archivo_ya_procesado()` - Verifica si debe omitir
5. `generar_log_individual()` - Crea archivo .txt con info
6. `extraer_datos()` - Extrae datos del Excel
7. `buscar_archivos_datos()` - Escanea directorios

---

## 🚀 Ventajas de las Mejoras

### Para el Usuario:
- ✅ **No reprocesa archivos innecesariamente** (ahorra tiempo)
- ✅ **Logs detallados por archivo** (fácil debugging)
- ✅ **Procesamiento selectivo** (repara problemas específicos)
- ✅ **Detección automática de cambios** (seguridad)

### Para el Sistema:
- ✅ **Eficiencia mejorada** (solo procesa lo nuevo)
- ✅ **Trazabilidad completa** (logs individuales + tracking)
- ✅ **Flexibilidad** (múltiples opciones de ejecución)
- ✅ **Robustez** (detección de archivos modificados)

---

**Autor:** Claude Code
**Fecha:** 13 de octubre de 2025
**Versión:** 2.0
**Estado:** ✅ Completado
