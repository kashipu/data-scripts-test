# Sistema de Prevención de Duplicados

## 🛡️ Resumen
Este sistema **garantiza cero duplicados** mediante una estrategia de doble capa:
1. **Validación a nivel de aplicación** - Verifica archivos ya procesados antes de insertar
2. **Constraints UNIQUE en base de datos** - PostgreSQL rechaza duplicados automáticamente

---

## 📋 Instrucciones de Uso

### Paso 1: Aplicar Constraints en la Base de Datos (SOLO UNA VEZ)

**IMPORTANTE:** Ejecuta este paso **ANTES** de usar `insertar_muestras.py` por primera vez.

```bash
# Opción A: Desde línea de comandos
psql -U postgres -d test_nps -f add_unique_constraints.sql

# Opción B: Desde pgAdmin o DBeaver
# Abre add_unique_constraints.sql y ejecuta el contenido
```

Este script:
- ✅ Elimina duplicados existentes (si los hay)
- ✅ Agrega constraint `UNIQUE(record_id, source_file)` en `banco_movil_clean`
- ✅ Agrega constraint `UNIQUE(date_submitted, nps_score_bv, source_file)` en `banco_virtual_clean`
- ✅ Crea índices en `source_file` para optimizar búsquedas

### Paso 2: Ejecutar el Pipeline Normalmente

```bash
python sample_extractor.py   # Extrae muestras
python sample_cleaner.py      # Limpia datos
python insertar_muestras.py   # Inserta en BD (ahora con protección anti-duplicados)
```

---

## 🔍 Cómo Funciona

### Validación de Archivos (Primera Barrera)

El script verifica `source_file` antes de procesar:

```python
# Si el archivo ya fue procesado:
if self.file_already_processed(file_name, 'banco_movil_clean'):
    logger.warning(f"⊘ OMITIDO - Archivo ya procesado: {file_name}")
    return True  # Se salta sin error
```

**Ventajas:**
- ⚡ Rápido - evita leer archivos grandes innecesariamente
- 📊 Log claro de qué archivos se omiten
- 🔄 Permite re-ejecutar el script sin consecuencias

### Constraints de Base de Datos (Segunda Barrera)

Si por alguna razón la validación falla, PostgreSQL rechaza duplicados:

```sql
-- Banco Móvil: record_id + source_file deben ser únicos
ALTER TABLE banco_movil_clean
ADD CONSTRAINT unique_bm_record
UNIQUE (record_id, source_file);

-- Banco Virtual: fecha + score + source_file deben ser únicos
ALTER TABLE banco_virtual_clean
ADD CONSTRAINT unique_bv_record
UNIQUE (date_submitted, nps_score_bv, source_file);
```

**Ventajas:**
- 🛡️ Protección absoluta a nivel de base de datos
- 🚨 Error claro si se intenta insertar duplicados
- 💪 Funciona incluso si el script es modificado o bypassed

---

## 📊 Ejemplo de Salida

### Primera Ejecución (Archivos Nuevos)
```
============================================================
VERIFICANDO ARCHIVOS YA PROCESADOS
============================================================
No hay archivos procesados previamente (base de datos vacía)

============================================================
Procesando 2 archivos BANCO MÓVIL
============================================================

[1/2] agosto_bm_2025_limpio.xlsx
→ Procesando Banco Móvil: agosto_bm_2025_limpio.xlsx
✓ Banco Móvil insertado: 50000 registros de 50000

[2/2] septiembre_bm_2025_limpio.xlsx
→ Procesando Banco Móvil: septiembre_bm_2025_limpio.xlsx
✓ Banco Móvil insertado: 45000 registros de 45000

============================================================
RESUMEN DE INSERCIÓN
============================================================
Banco Móvil:
  ✓ Insertados: 95000 registros
  ⊘ Omitidos: 0 archivos (ya procesados)
Banco Virtual:
  ✓ Insertados: 0 registros
  ⊘ Omitidos: 0 archivos (ya procesados)
Total insertado: 95000 registros
✓ PIPELINE COMPLETADO - Sin duplicados garantizados
```

### Segunda Ejecución (Archivos Ya Procesados)
```
============================================================
VERIFICANDO ARCHIVOS YA PROCESADOS
============================================================

Banco Móvil - 2 archivos en BD:
  • agosto_bm_2025_limpio.xlsx: 50000 registros (última: 2025-10-09 14:23:11)
  • septiembre_bm_2025_limpio.xlsx: 45000 registros (última: 2025-10-09 14:23:45)

============================================================
Procesando 2 archivos BANCO MÓVIL
============================================================

[1/2] agosto_bm_2025_limpio.xlsx
⊘ OMITIDO - Archivo ya procesado: agosto_bm_2025_limpio.xlsx

[2/2] septiembre_bm_2025_limpio.xlsx
⊘ OMITIDO - Archivo ya procesado: septiembre_bm_2025_limpio.xlsx

============================================================
RESUMEN DE INSERCIÓN
============================================================
Banco Móvil:
  ✓ Insertados: 0 registros
  ⊘ Omitidos: 2 archivos (ya procesados)
Total insertado: 0 registros
✓ PIPELINE COMPLETADO - Sin duplicados garantizados
```

---

## 🚨 Manejo de Errores

### Caso 1: Archivo Modificado con Mismo Nombre

Si modificas un archivo ya procesado y lo vuelves a limpiar, el script lo omitirá por seguridad:

```
⊘ OMITIDO - Archivo ya procesado: agosto_bm_2025_limpio.xlsx
```

**Solución:** Renombra el archivo (ej: `agosto_bm_2025_v2_limpio.xlsx`) antes de limpiarlo.

### Caso 2: Constraint Violation (Raro)

Si los datos duplicados logran pasar la validación (escenario teórico):

```
✗ DUPLICADOS DETECTADOS - agosto_bm_2025_limpio.xlsx
  La base de datos rechazó registros duplicados: duplicate key value violates unique constraint "unique_bm_record"
  Verifica que el archivo no haya sido modificado y procesado nuevamente
```

**Solución:** Este error indica una inconsistencia. Verifica:
1. ¿El archivo fue modificado manualmente?
2. ¿Hay múltiples versiones del mismo archivo?
3. ¿Se ejecutaron scripts paralelos?

---

## 🔧 Comandos Útiles

### Verificar Archivos Procesados
```sql
-- Ver todos los archivos en BD con su cantidad de registros
SELECT source_file, COUNT(*) as registros, MAX(inserted_at) as ultima_insercion
FROM banco_movil_clean
GROUP BY source_file
ORDER BY ultima_insercion DESC;

SELECT source_file, COUNT(*) as registros, MAX(inserted_at) as ultima_insercion
FROM banco_virtual_clean
GROUP BY source_file
ORDER BY ultima_insercion DESC;
```

### Buscar Duplicados (No Debería Haber)
```sql
-- Banco Móvil: busca duplicados por record_id + source_file
SELECT record_id, source_file, COUNT(*) as cantidad
FROM banco_movil_clean
GROUP BY record_id, source_file
HAVING COUNT(*) > 1;

-- Banco Virtual: busca duplicados por fecha + score + source_file
SELECT date_submitted, nps_score_bv, source_file, COUNT(*) as cantidad
FROM banco_virtual_clean
GROUP BY date_submitted, nps_score_bv, source_file
HAVING COUNT(*) > 1;
```

### Eliminar Archivo Específico (Si Necesitas Reprocesar)
```sql
-- Elimina todos los registros de un archivo específico
DELETE FROM banco_movil_clean WHERE source_file = 'agosto_bm_2025_limpio.xlsx';
DELETE FROM banco_virtual_clean WHERE source_file = 'agosto_bv_2025_limpio.xlsx';

-- Ahora puedes volver a ejecutar insertar_muestras.py
```

---

## ✅ Garantías del Sistema

Este sistema **GARANTIZA**:

1. ✅ **Mismos datos no se insertan dos veces** - Validación por `source_file`
2. ✅ **Base de datos siempre consistente** - Constraints UNIQUE a nivel de PostgreSQL
3. ✅ **Históricos preservados** - `if_exists='append'` nunca borra datos
4. ✅ **Logs claros y trazables** - Cada archivo tiene timestamp de inserción
5. ✅ **Re-ejecuciones seguras** - Puedes correr el script cuantas veces quieras

---

## 📝 Notas Técnicas

### Criterios de Unicidad

**Banco Móvil:**
- `record_id` (columna `id` del Excel) + `source_file`
- Rationale: Cada registro tiene un ID único dentro del archivo fuente

**Banco Virtual:**
- `date_submitted` + `nps_score_bv` + `source_file`
- Rationale: Combinación de timestamp + score + fuente identifica registros únicos

### Performance

- Índices en `source_file` aceleran validaciones
- Query de verificación: O(1) gracias al índice
- Inserción en batches de 1000 registros (parámetro `chunksize`)

### Limitaciones

- Si cambias el nombre de un archivo ya procesado, se insertará como nuevo
- Si cambias el contenido pero mantienes el nombre, será omitido
- Para reprocesar, debes eliminar manualmente los registros previos (ver comandos útiles)

---

## 🆘 Troubleshooting

### "No module named 'psycopg2'"
```bash
pip install psycopg2-binary
```

### "Cannot add constraint - duplicate keys exist"
Los datos ya tienen duplicados. El script `add_unique_constraints.sql` los elimina automáticamente.

### "Table does not exist"
Ejecuta primero `insertar_muestras.py` una vez sin constraints para crear las tablas, luego aplica `add_unique_constraints.sql`.

---

**Autor:** Sistema NPS Pipeline
**Última actualización:** 2025-10-09
