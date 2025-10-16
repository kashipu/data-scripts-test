# 🔧 Plan de Mejoras del Validador - Versión 4.0

**Objetivo:** Hacer que el extractor valide correctamente para que `2_limpieza.py` reciba datos óptimos

---

## 📋 Mejoras a Implementar

### 1. ✅ Categorización de Errores por Severidad

#### 🔴 CRÍTICOS (Bloquean procesamiento):
- Columnas críticas completamente faltantes
- > 50% de timestamps nulos
- Archivo completamente corrupto
- JSON imposible de parsear (no solo encoding)

#### ⚠️ ADVERTENCIAS (Revisar pero no bloquean):
- IDs duplicados (si las respuestas son diferentes)
- 10-50% de valores nulos en columnas secundarias
- Duplicados potenciales que necesitan revisión manual

#### ℹ️ INFORMATIVOS (Se corrigen automáticamente):
- **Encoding UTF-8 corrupto** (Ã, Â, etc.) → 2_limpieza.py lo corrige
- JSON con comillas simples → 2_limpieza.py lo corrige
- Timezones en fechas → 2_limpieza.py lo corrige

---

### 2. ✅ Detección Inteligente de Duplicados

#### Duplicados por ID vs Duplicados Reales:

```python
# ANTES (incorrecto):
duplicados = df['id'].duplicated().sum()  # Solo mira el ID

# DESPUÉS (correcto):
# Para BM: Comparar timestamp + answers + custIdentNum
columnas_unicas_bm = ['timestamp', 'answers', 'custIdentNum']
duplicados_reales = df[columnas_unicas_bm].duplicated().sum()

# Para BV: Comparar Date Submitted + respuestas
columnas_unicas_bv = ['Date Submitted', 'nps_score_bv', 'motivo_calificacion']
duplicados_reales = df[columnas_unicas_bv].duplicated().sum()
```

---

### 3. ✅ Tasa de Calidad Ajustada

#### Nueva Fórmula:

```
Tasa de Calidad = (Filas sin errores críticos / Total filas) × 100

Donde:
- NO se cuentan errores informativos (auto-corregibles)
- NO se cuentan IDs duplicados si las respuestas son únicas
- SÍ se cuentan valores nulos en columnas críticas
- SÍ se cuentan registros completamente duplicados
```

#### Clasificación:

| Tasa | Estado | Acción |
|------|--------|--------|
| ≥ 95% | ✅ EXCELENTE | Continuar sin problemas |
| 80-94% | ⚠️ BUENO | Revisar advertencias |
| 50-79% | ⚠️ ACEPTABLE | Revisar errores antes de continuar |
| < 50% | ❌ CRÍTICO | NO continuar, corregir archivo |

---

### 4. ✅ Validaciones Específicas para Preparar `2_limpieza.py`

#### Para Banco Móvil (BM):

```python
✅ Verificar estructura del JSON 'answers':
   - Debe ser parseable (aunque tenga encoding corrupto)
   - Debe tener estructura de array [{'subQuestionId': ...}]
   - Debe tener al menos 1 elemento

✅ Verificar timestamp:
   - No debe ser nulo en > 10% de registros
   - Debe ser formato fecha válido

✅ Verificar custIdentNum:
   - Debe tener al menos 50% de valores únicos
   - Detectar si todos son iguales (error de exportación)
```

#### Para Banco Virtual (BV):

```python
✅ Verificar 'Date Submitted':
   - No debe ser nulo en > 5% de registros
   - Debe ser formato fecha válido

✅ Verificar columnas de NPS:
   - Debe existir al menos una columna con 'recomien' + 'probable'
   - Valores deben estar en rango 0-10

✅ Verificar metadata (device, browser, OS):
   - Opcional pero debe tener valores válidos si existe
```

---

### 5. ✅ Nuevo Formato de Reporte `.validation`

```
================================================================================
REPORTE DE VALIDACIÓN - 1_extractor.py
================================================================================

Archivo: Agosto_BM_2025_extracted_50000.xlsx
Tipo: BM
Fecha de validación: 2025-10-13 16:30:00

┌─────────────────────────────────────────────────────────────────────────────┐
│ RESUMEN EJECUTIVO                                                            │
└─────────────────────────────────────────────────────────────────────────────┘

Total de filas: 50,000
Tasa de calidad: 98.50% ✅ EXCELENTE
Estado: ✅ LISTO PARA PROCESAMIENTO

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERRORES POR SEVERIDAD                                                        │
└─────────────────────────────────────────────────────────────────────────────┘

🔴 CRÍTICOS (Bloquean procesamiento): 0
   → Ninguno detectado

⚠️ ADVERTENCIAS (Revisar pero no bloquean): 750
   • IDs duplicados: 98 (respuestas únicas - no bloquea)
   • Valores nulos en 'nps_recomendacion_motivo': 652 (13%)

ℹ️ INFORMATIVOS (Se corrigen automáticamente): 50,000
   • Encoding UTF-8 corrupto en 'answers': 50,000 (100%)
     → Se corregirá automáticamente en 2_limpieza.py

┌─────────────────────────────────────────────────────────────────────────────┐
│ ANÁLISIS DE DUPLICADOS                                                       │
└─────────────────────────────────────────────────────────────────────────────┘

Duplicados por ID: 98
Duplicados reales (todas las columnas): 0
Veredicto: ✅ No hay duplicados reales

Explicación:
  El campo 'id' tiene valores repetidos, pero cada registro tiene
  respuestas únicas en 'answers'. Estos NO son duplicados reales.
  La inserción en PostgreSQL funcionará correctamente.

┌─────────────────────────────────────────────────────────────────────────────┐
│ VALORES NULOS POR COLUMNA                                                    │
└─────────────────────────────────────────────────────────────────────────────┘

Columna                          | Nulos     | %      | Severidad
─────────────────────────────────────────────────────────────────────────────
nps_recomendacion_motivo         | 652       | 1.30%  | ℹ️  Normal
timestamp                        | 5         | 0.01%  | ⚠️  Bajo
custIdentNum                     | 0         | 0.00%  | ✅ OK

┌─────────────────────────────────────────────────────────────────────────────┐
│ ERRORES DETALLADOS POR FILA                                                  │
└─────────────────────────────────────────────────────────────────────────────┘

⚠️ Solo se muestran errores CRÍTICOS y ADVERTENCIAS (no informativos)

Fila 15:
  ⚠️  ADVERTENCIA: timestamp es nulo
      Impacto: Bajo - se puede procesar igual

Fila 89:
  ⚠️  ADVERTENCIA: timestamp es nulo
      Impacto: Bajo - se puede procesar igual

[Total: 5 filas con advertencias]

┌─────────────────────────────────────────────────────────────────────────────┐
│ RECOMENDACIONES                                                              │
└─────────────────────────────────────────────────────────────────────────────┘

✅ PUEDES CONTINUAR con el procesamiento

Próximos pasos:
  1. python 2_limpieza.py      # Corregirá encoding automáticamente
  2. python 3_insercion.py     # Insertará sin problemas
  3. python 4_visualizacion.py # Generará dashboard

Notas:
  • El encoding UTF-8 corrupto es normal y se corregirá en limpieza
  • Los IDs duplicados no afectan el procesamiento
  • Los valores nulos son esperados en campos opcionales

================================================================================
```

---

### 6. ✅ Salida en Consola Mejorada

```bash
🔍 Validando calidad de datos...

   📊 Errores por severidad:
      🔴 Críticos: 0
      ⚠️  Advertencias: 750
      ℹ️  Informativos: 50,000 (encoding - se corrige auto)

   📈 Análisis de duplicados:
      IDs repetidos: 98
      Duplicados reales: 0 ✅

   📋 Tasa de calidad: 98.50% ✅ EXCELENTE

   ✅ LISTO PARA PROCESAMIENTO
   📄 Ver detalles: Agosto_BM_2025_extracted_50000.validation
```

---

### 7. ✅ Integración con `2_limpieza.py`

El archivo `.validation` incluirá metadata para que `2_limpieza.py` sepa:

```json
{
  "tiene_encoding_corrupto": true,
  "columnas_con_encoding_corrupto": ["answers", "nps_recomendacion_motivo"],
  "tiene_json_malformado": false,
  "duplicados_reales": 0,
  "listo_para_limpieza": true,
  "advertencias_para_limpieza": [
    "5 filas con timestamp nulo",
    "13% de nps_recomendacion_motivo nulo"
  ]
}
```

---

## 🚀 Implementación

### Opción 1: Reescribir función `validar_datos_detallado()` completa
- Más limpio
- Mejor estructura
- Todas las mejoras integradas

### Opción 2: Actualizar función actual paso a paso
- Menos disruptivo
- Más difícil de mantener
- Cambios incrementales

**Recomendación:** Opción 1 (reescribir completa)

---

## ✅ Resultado Esperado

Después de las mejoras, para tu archivo actual:

**ANTES:**
```
Tasa de calidad: 0.00% ❌ CRÍTICO
```

**DESPUÉS:**
```
Tasa de calidad: 98.70% ✅ EXCELENTE
🔴 Críticos: 0
⚠️  Advertencias: 105 (IDs duplicados, algunos nulos)
ℹ️  Informativos: 100 (encoding - auto-fix)
Estado: ✅ LISTO PARA PROCESAMIENTO
```

---

¿Procedo con la implementación completa?

**Autor:** Claude Code
**Fecha:** 13 de octubre de 2025
**Estado:** 📋 Plan completo - Listo para implementar
