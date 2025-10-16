# 🔍 Sistema de Validación de Datos - 1_extractor.py

**Fecha:** 13 de octubre de 2025
**Versión:** 3.0

---

## ✅ Nueva Funcionalidad Implementada

### Sistema de Validación Detallada por Fila y Columna

El extractor ahora valida **TODOS** los datos extraídos y genera reportes detallados de errores por fila y columna, permitiendo identificar exactamente dónde están los problemas antes de la inserción.

---

## 📋 Archivos Generados por Cada Extracción

Para cada archivo procesado, el extractor genera **3 archivos**:

```
datos_raw/
├── Agosto_BM_2025_extracted_50000.xlsx          ← Datos extraídos
├── Agosto_BM_2025_extracted_50000.txt           ← Log de extracción
└── Agosto_BM_2025_extracted_50000.validation    ← ✨ NUEVO: Reporte de validación
```

---

## 🔍 Archivo de Validación (.validation)

### Contenido del Reporte:

```
================================================================================
REPORTE DE VALIDACIÓN - 1_extractor.py
================================================================================

Archivo: Agosto_BM_2025_extracted_50000.xlsx
Tipo: BM
Fecha de validación: 2025-10-13 15:45:30

RESUMEN DE VALIDACIÓN:
  Total de filas: 50,000
  Filas válidas: 49,850
  Filas con errores: 150
  Registros duplicados: 5

VALORES NULOS POR COLUMNA:
  • answers: 45 (0.09%)
  • nps_recomendacion_motivo: 1,234 (2.47%)
  • csat_satisfaccion_score: 890 (1.78%)
  • timestamp: 12 (0.02%)

ERRORES POR COLUMNA:
  • answers: 45 errores
  • timestamp: 12 errores

ERRORES DETALLADOS POR FILA (Primeros 100):
--------------------------------------------------------------------------------

Fila 15 del Excel:
  • Columna 'timestamp': Valor nulo en columna crítica
    Valor: None

Fila 23 del Excel:
  • Columna 'answers': Campo vacío o nulo
    Valor: None

Fila 142 del Excel:
  • Columna 'answers': Encoding UTF-8 corrupto detectado
    Ejemplo: [{'subQuestionId': 'nps_rate_recomendation', 'an...

Fila 289 del Excel:
  • Columna 'timestamp': Valor nulo en columna crítica
    Valor: None

...

TASA DE CALIDAD: 99.70%
ESTADO: ✅ EXCELENTE - Datos listos para inserción
================================================================================
```

---

## 📊 Niveles de Calidad

El sistema asigna un **ESTADO** basado en la tasa de calidad:

| Tasa de Calidad | Estado | Descripción |
|----------------|--------|-------------|
| **≥ 95%** | ✅ **EXCELENTE** | Datos listos para inserción |
| **80-94%** | ⚠️  **ACEPTABLE** | Revisar errores antes de insertar |
| **< 80%** | ❌ **CRÍTICO** | Revisar archivo antes de continuar |

---

## 🔎 Validaciones Realizadas

### Para Banco Móvil (BM):

1. ✅ **Columnas críticas presentes:**
   - `timestamp` - Marca de tiempo del registro
   - `answers` - JSON con respuestas NPS/CSAT
   - `feedbackType` - Tipo de feedback

2. ✅ **Validación por fila:**
   - `timestamp` no debe ser nulo
   - `answers` no debe estar vacío
   - `answers` no debe tener encoding corrupto (Ã)
   - Detecta JSON malformado

3. ✅ **Duplicados:**
   - Verifica duplicados por columna `id`

### Para Banco Virtual (BV):

1. ✅ **Columnas críticas presentes:**
   - `Date Submitted` - Fecha de envío

2. ✅ **Validación por fila:**
   - `Date Submitted` no debe ser nulo

3. ✅ **Duplicados:**
   - Verifica duplicados por `Date Submitted`

---

## 💻 Salida en Consola

Durante la extracción, verás el nuevo paso de validación:

```bash
📂 Procesando: data-cruda/Agosto/Agosto_BM_2025.xlsx
   ⏳ Leyendo archivo Excel...
   📊 Total de registros en archivo: 50,234
   📋 Columnas disponibles: 15
   ℹ️  Extrayendo TODOS los registros (50,234)
   💾 Guardando datos extraídos...
   ✅ Datos guardados: datos_raw/Agosto_BM_2025_extracted_50234.xlsx
   📈 Registros extraídos: 50,234

   🔍 Validando calidad de datos...
   ⚠️  Errores encontrados: 150 filas con problemas
   📋 Ver detalles en: Agosto_BM_2025_extracted_50234.validation
   ⚠️  Duplicados detectados: 5 registros

   📊 COLUMNAS CLAVE DETECTADAS:
      • timestamp
      • answerDate
      • answers

📄 Log individual generado: Agosto_BM_2025_extracted_50234.txt
📋 Reporte de validación generado: Agosto_BM_2025_extracted_50234.validation
📝 Archivo registrado en tracking: Agosto_BM_2025.xlsx
```

---

## 📄 Log Individual Actualizado (.txt)

El log individual ahora incluye resumen de validación:

```
================================================================================
LOG DE EXTRACCIÓN - 1_extractor.py
================================================================================

Fecha de extracción: 2025-10-13 15:45:30
Archivo original: Agosto_BM_2025.xlsx
Archivo de salida: Agosto_BM_2025_extracted_50234.xlsx
Tipo de archivo: BM

ESTADÍSTICAS:
  - Total registros en archivo original: 50,234
  - Registros extraídos: 50,234
  - Total columnas: 15

COLUMNAS CLAVE DETECTADAS:
  • timestamp
  • answerDate
  • answers
  • nps_score
  • feedbackType

ADVERTENCIAS:
  ⚠️  Encoding UTF-8 malformado detectado en columna 'answers'
  ⚠️  5 registros duplicados detectados

VALIDACIÓN DE CALIDAD:
  - Filas válidas: 49,850
  - Filas con errores: 150
  - Registros duplicados: 5
  - Tasa de calidad: 99.70%
  📋 Ver detalles completos en archivo .validation

ESTADO: ✅ Exitoso
================================================================================
```

---

## 🎯 Casos de Uso

### Caso 1: Extracción con Datos Perfectos

```bash
python 1_extractor.py

# Output:
🔍 Validando calidad de datos...
✅ Validación exitosa: Todos los registros son válidos

# Archivo .validation:
TASA DE CALIDAD: 100.00%
ESTADO: ✅ EXCELENTE - Datos listos para inserción
```

### Caso 2: Extracción con Errores Menores

```bash
python 1_extractor.py

# Output:
🔍 Validando calidad de datos...
⚠️  Errores encontrados: 45 filas con problemas
📋 Ver detalles en: Agosto_BM_2025_extracted_50000.validation

# Archivo .validation muestra:
Fila 15 del Excel:
  • Columna 'answers': Campo vacío o nulo
    Valor: None

Fila 23 del Excel:
  • Columna 'timestamp': Valor nulo en columna crítica
    Valor: None

TASA DE CALIDAD: 99.91%
ESTADO: ✅ EXCELENTE - Datos listos para inserción
```

### Caso 3: Extracción con Problemas Críticos

```bash
python 1_extractor.py

# Output:
🔍 Validando calidad de datos...
⚠️  Errores encontrados: 15,000 filas con problemas
⚠️  Duplicados detectados: 2,500 registros
📋 Ver detalles en: Agosto_BM_2025_extracted_50000.validation

# Archivo .validation muestra:
TASA DE CALIDAD: 70.00%
ESTADO: ❌ CRÍTICO - Revisar archivo antes de continuar
```

**Acción recomendada:** Revisar el archivo Excel original antes de continuar con 2_limpieza.py

---

## 🔧 Integración con 3_insercion.py (Próximamente)

El script de inserción podrá leer el archivo `.validation` para:

1. ✅ Verificar que el archivo fue validado
2. ✅ Comprobar la tasa de calidad antes de insertar
3. ⚠️  Alertar si hay duplicados detectados
4. ❌ Rechazar archivos con tasa de calidad < 80%

**Ejemplo de verificación:**

```python
# En 3_insercion.py (próximamente)
def validar_archivo_antes_insercion(ruta_archivo):
    archivo_validacion = ruta_archivo.replace('_LIMPIO.xlsx', '_extracted_XXXXX.validation')

    if not os.path.exists(archivo_validacion):
        print("⚠️  No se encontró archivo de validación")
        return False

    # Leer tasa de calidad
    with open(archivo_validacion, 'r') as f:
        contenido = f.read()

    # Extraer tasa de calidad
    match = re.search(r'TASA DE CALIDAD: ([\d.]+)%', contenido)
    if match:
        tasa = float(match.group(1))

        if tasa >= 95:
            print(f"✅ Calidad excelente ({tasa:.2f}%) - Listo para inserción")
            return True
        elif tasa >= 80:
            print(f"⚠️  Calidad aceptable ({tasa:.2f}%) - Revisar advertencias")
            return True
        else:
            print(f"❌ Calidad crítica ({tasa:.2f}%) - NO INSERTAR")
            return False

    return False
```

---

## 📊 Limitaciones

1. **Validación de primeras 1,000 filas:**
   - Para archivos grandes, solo valida las primeras 1,000 filas en detalle
   - Evita saturar el log con millones de errores
   - Las estadísticas globales (nulos, duplicados) se calculan sobre TODOS los datos

2. **Primeros 100 errores detallados:**
   - El archivo `.validation` muestra solo los primeros 100 errores con detalle
   - El resumen completo de errores por columna siempre se muestra

---

## 🎓 Interpretación de Errores

### Errores Comunes y Soluciones:

| Error | Causa | Solución |
|-------|-------|----------|
| **"Valor nulo en columna crítica"** | Campo obligatorio vacío | Revisar archivo Excel original |
| **"Campo vacío o nulo"** | Celda sin datos | Verificar si es esperado |
| **"Encoding UTF-8 corrupto"** | Caracteres mal codificados (Ã) | Será corregido por 2_limpieza.py |
| **"Registros duplicados"** | IDs repetidos | Verificar si son realmente duplicados |

---

## ✅ Ventajas del Sistema de Validación

### Para el Usuario:
- ✅ **Visibilidad completa:** Sabe exactamente qué errores hay y dónde
- ✅ **Prevención temprana:** Detecta problemas antes de la inserción
- ✅ **Trazabilidad:** Puede rastrear errores a filas específicas del Excel
- ✅ **Confianza:** Sabe la calidad de sus datos antes de continuar

### Para el Sistema:
- ✅ **Métricas de calidad:** Tasa de calidad documentada
- ✅ **Auditoría:** Registro permanente de validaciones
- ✅ **Decisiones informadas:** 3_insercion.py puede rechazar datos malos
- ✅ **Debugging:** Errores específicos por fila facilitan correcciones

---

## 🚀 Próximos Pasos

1. **Ejecutar extracción:**
   ```bash
   python 1_extractor.py
   ```

2. **Revisar archivos `.validation`:**
   ```bash
   cat datos_raw/*.validation
   ```

3. **Si calidad es buena (≥95%):**
   ```bash
   python 2_limpieza.py      # Continuar con limpieza
   python 3_insercion.py     # Insertar en PostgreSQL
   ```

4. **Si calidad es crítica (<80%):**
   - Revisar errores en `.validation`
   - Corregir archivo Excel original
   - Volver a ejecutar `python 1_extractor.py --force`

---

## 📝 Ejemplo Completo de Workflow

```bash
# 1. Extraer y validar
python 1_extractor.py

# Output:
✅ ARCHIVOS PROCESADOS EXITOSAMENTE (2):

   BM - Agosto:
      Original: Agosto_BM_2025.xlsx
      Extraído: Agosto_BM_2025_extracted_50234.xlsx
      Registros: 50,234

   🔍 Validación: 99.70% calidad ✅

   BV - Agosto:
      Original: Agosto_BV_2025.xlsx
      Extraído: Agosto_BV_2025_extracted_234.xlsx
      Registros: 234

   🔍 Validación: 100.00% calidad ✅

# 2. Revisar validaciones si necesario
cat datos_raw/Agosto_BM_2025_extracted_50234.validation

# 3. Continuar con pipeline
python 2_limpieza.py
python 3_insercion.py
```

---

## 🔍 Debugging de Problemas

### Problema: Muchos errores de encoding

```
ERRORES POR COLUMNA:
  • answers: 15,000 errores (todos encoding UTF-8 corrupto)
```

**Solución:** Este error es esperado y será corregido automáticamente por `2_limpieza.py`

### Problema: Muchos campos nulos

```
VALORES NULOS POR COLUMNA:
  • nps_recomendacion_motivo: 25,000 (50.00%)
```

**Solución:** Esto puede ser normal si muchos usuarios no dejan comentarios. Verificar si el porcentaje es esperado.

### Problema: Muchos duplicados

```
Registros duplicados: 5,000
```

**Solución:** Verificar en el archivo Excel original si hay filas repetidas. Considerar eliminarlas antes de reextracción.

---

**Autor:** Claude Code
**Fecha:** 13 de octubre de 2025
**Versión:** 3.0
**Estado:** ✅ Implementado y funcionando
