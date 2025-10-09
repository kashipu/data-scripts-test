-- Script para agregar constraints de unicidad y prevenir duplicados
-- Ejecutar ANTES de usar insertar_muestras.py

-- Paso 1: Eliminar duplicados existentes si los hay
-- (Mantiene solo el primer registro de cada duplicado basado en el ID más bajo)

-- Para Banco Móvil: elimina duplicados basados en record_id + source_file
DELETE FROM banco_movil_clean
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY record_id, source_file
                   ORDER BY id ASC
               ) AS row_num
        FROM banco_movil_clean
    ) t
    WHERE row_num > 1
);

-- Para Banco Virtual: elimina duplicados basados en date_submitted + nps_score_bv + source_file
DELETE FROM banco_virtual_clean
WHERE id IN (
    SELECT id FROM (
        SELECT id,
               ROW_NUMBER() OVER (
                   PARTITION BY date_submitted, nps_score_bv, source_file
                   ORDER BY id ASC
               ) AS row_num
        FROM banco_virtual_clean
    ) t
    WHERE row_num > 1
);

-- Paso 2: Agregar constraints de unicidad
-- Esto garantiza que NUNCA se puedan insertar duplicados a nivel de base de datos

-- Constraint para Banco Móvil
-- Usa record_id (que viene de la columna 'id' del Excel) + source_file
ALTER TABLE banco_movil_clean
ADD CONSTRAINT unique_bm_record
UNIQUE (record_id, source_file);

-- Constraint para Banco Virtual
-- Usa combinación de fecha, score y archivo fuente
ALTER TABLE banco_virtual_clean
ADD CONSTRAINT unique_bv_record
UNIQUE (date_submitted, nps_score_bv, source_file);

-- Paso 3: Crear índices adicionales para optimizar las validaciones
CREATE INDEX IF NOT EXISTS idx_bm_source_file ON banco_movil_clean(source_file);
CREATE INDEX IF NOT EXISTS idx_bv_source_file ON banco_virtual_clean(source_file);

-- Verificación: muestra estadísticas de la base de datos limpia
SELECT
    'banco_movil_clean' as tabla,
    COUNT(*) as total_registros,
    COUNT(DISTINCT source_file) as archivos_unicos
FROM banco_movil_clean

UNION ALL

SELECT
    'banco_virtual_clean' as tabla,
    COUNT(*) as total_registros,
    COUNT(DISTINCT source_file) as archivos_unicos
FROM banco_virtual_clean;
