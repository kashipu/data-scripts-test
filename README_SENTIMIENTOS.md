# Análisis de Sentimientos - Guía Rápida

## 🚀 Instalación

```bash
pip install pysentimiento transformers torch pyyaml
```

## 📝 Archivos

- `palabras_clave_sentimientos.yml` - Palabras clave (editable)
- `06b_sentimientos_pysentimiento.py` - Análisis rápido con IA
- `07_refinar_sentimientos.py` - Validación de calidad

## ⚡ Uso Rápido

### 1. Analizar sentimientos (300-500 reg/seg)

```bash
# Prueba con 1,000
python 06b_sentimientos_pysentimiento.py --limit 1000

# Todos los pendientes
python 06b_sentimientos_pysentimiento.py --limit 0
```

### 2. Validar calidad

```bash
python 07_refinar_sentimientos.py --mode validate
```

### 3. Ver inconsistencias

```bash
python 07_refinar_sentimientos.py --mode analyze
```

### 4. Exportar casos dudosos

```bash
python 07_refinar_sentimientos.py --mode export --output revisar.xlsx
```

## 📊 Campos en BD

El script crea automáticamente:

- `sentimiento_py` - POSITIVO/NEGATIVO/NEUTRAL
- `confianza_py` - 0.0 a 1.0
- `emocion` - joy, anger, sadness, fear, surprise, disgust
- `intensidad_emocional` - 0.0 a 1.0 (qué tan fuerte es la emoción)
- `es_ofensivo` - TRUE/FALSE
- `metodo_analisis` - 'pysentimiento'

## 🎯 Intensidad Emocional

**¿Para qué sirve?**

Diferencia entre:
- "Está bien" (intensidad: 0.3) vs "Excelente!" (intensidad: 0.9)
- "No me gustó" (intensidad: 0.4) vs "Pésimo servicio!" (intensidad: 0.95)

**Consulta:**
```sql
SELECT motivo_texto, emocion, intensidad_emocional
FROM respuestas_nps_csat
WHERE intensidad_emocional > 0.8  -- Emociones muy fuertes
ORDER BY intensidad_emocional DESC;
```

## ✏️ Editar Palabras Clave

Abre `palabras_clave_sentimientos.yml` y agrega/quita palabras:

```yaml
ofensivas:
  - mierda
  - tu_palabra_aqui  # Agregar nueva
```

El script las cargará automáticamente.

## 📈 Consultas Útiles

### Ver sentimientos
```sql
SELECT
    sentimiento_py,
    COUNT(*) as total,
    AVG(confianza_py) as confianza_prom
FROM respuestas_nps_csat
WHERE sentimiento_py IS NOT NULL
GROUP BY sentimiento_py;
```

### Emociones más frecuentes
```sql
SELECT
    emocion,
    COUNT(*) as total,
    AVG(intensidad_emocional) as intensidad_prom
FROM respuestas_nps_csat
WHERE emocion IS NOT NULL
GROUP BY emocion
ORDER BY total DESC;
```

### Comentarios de alta intensidad emocional
```sql
SELECT
    motivo_texto,
    sentimiento_py,
    emocion,
    intensidad_emocional,
    score
FROM respuestas_nps_csat
WHERE intensidad_emocional > 0.85
ORDER BY intensidad_emocional DESC
LIMIT 50;
```

### Inconsistencias (sentimiento vs score)
```sql
-- NPS Detractores que no son NEGATIVO
SELECT COUNT(*)
FROM respuestas_nps_csat
WHERE metrica = 'NPS'
  AND score <= 6
  AND sentimiento_py != 'NEGATIVO';

-- NPS Promotores que no son POSITIVO
SELECT COUNT(*)
FROM respuestas_nps_csat
WHERE metrica = 'NPS'
  AND score >= 9
  AND sentimiento_py != 'POSITIVO';
```

## 🔧 Corregir Datos

```sql
-- Corregir un registro
UPDATE respuestas_nps_csat
SET sentimiento_py = 'NEGATIVO',
    metodo_analisis = 'manual'
WHERE id = 12345;

-- Corregir por lote
UPDATE respuestas_nps_csat
SET sentimiento_py = 'NEGATIVO'
WHERE metrica = 'NPS'
  AND score = 0
  AND sentimiento_py != 'NEGATIVO';
```

## ⏱️ Velocidad

| Registros | Tiempo Estimado |
|-----------|-----------------|
| 1,000 | 3 segundos |
| 10,000 | 30 segundos |
| 100,000 | 5 minutos |
| 387,000 | 15-20 minutos |

## 💡 Tips

1. **Empieza con 1,000** para probar
2. **Revisa el YML** antes de procesar todo
3. **Valida calidad** después de analizar
4. **Exporta casos dudosos** y revisa manualmente
5. **Actualiza el YML** con nuevas palabras que encuentres
