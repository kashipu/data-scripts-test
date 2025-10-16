# Tabla NPS/CSAT - Guía Rápida

## 🚀 Inicio Rápido

```bash
# Generar tabla HTML
python visualize_nps.py
```

**Resultado:** Se creará `visualizaciones/tabla_nps.html` - Una tabla HTML simple y detallada con todos los datos de la query SQL

## 📊 Contenido de la Tabla

La tabla muestra **mes por mes** + **fila consolidada** con todas las métricas:

### Columnas incluidas:

#### Volumen General
- **Vol. Total**: Cantidad total de registros del mes
- **% del Total**: Porcentaje que representa del total histórico

#### Métricas NPS (8 columnas)
- **Vol. NPS**: Volumen de respuestas NPS
- **Promedio NPS**: Score promedio NPS del mes
- **Detractores**: Cantidad de detractores (0-6)
- **Neutrales**: Cantidad de neutrales (7-8)
- **Promotores**: Cantidad de promotores (9-10)
- **% Detractores**: Porcentaje de detractores
- **% Neutrales**: Porcentaje de neutrales
- **% Promotores**: Porcentaje de promotores

#### Métricas CSAT (4 columnas)
- **Vol. CSAT**: Volumen de respuestas CSAT
- **Promedio CSAT**: Score promedio CSAT del mes
- **CSAT Mín**: Valor mínimo CSAT
- **CSAT Máx**: Valor máximo CSAT

### Fila Consolidada

Al final de la tabla aparece una **fila azul** con el total consolidado de todos los meses:
- Promedios ponderados de NPS y CSAT
- Suma total de volúmenes
- Porcentajes globales de categorías

## 🎯 Casos de Uso

### Ver tabla completa (todos los meses)
```bash
python visualize_nps.py
```

### Filtrar por mes específico
```bash
python visualize_nps.py --month 2025-08
```

### Guardar en ubicación personalizada
```bash
python visualize_nps.py --output reportes/tabla_septiembre.html
```

## 🎨 Características Visuales

- **Colores por categoría:**
  - 🔴 Rojo: Detractores
  - 🟠 Naranja: Neutrales
  - 🟢 Verde: Promotores y porcentajes positivos

- **Fila consolidada:** Azul con texto blanco

- **Hover interactivo:** Al pasar el mouse sobre las filas se destacan

- **Headers sticky:** Los encabezados se quedan fijos al hacer scroll

- **Responsive:** Se adapta al tamaño de la pantalla

## 📈 Datos Actuales

Basado en tu base de datos `nps_analitycs`:
- **Tabla fuente**: `banco_movil_clean`
- **Registros totales**: 1,234,628
- **Período actual**: Mayo 2025 - Septiembre 2025 (5 meses)
- **Métricas**: NPS, CSAT, categorías, volúmenes

## 🔧 Configuración

Si tu base de datos tiene credenciales diferentes, edita `visualize_nps.py`:

```python
DB_CONFIG = {
    'host': 'localhost',
    'port': '5432',
    'database': 'nps_analitycs',
    'user': 'postgres',
    'password': 'postgres'  # ⚠️ CAMBIAR ESTE VALOR
}
```

## 📂 Archivos Generados

```
visualizaciones/
└── tabla_nps.html           # Tabla HTML detallada (~10 KB)

visualizacion_nps.log         # Log de operaciones
```

## 💡 Ventajas de esta Tabla

✅ **Simple y directa**: Solo una tabla, sin gráficos complejos
✅ **Fácil de compartir**: Archivo HTML autocontenido
✅ **Exportable**: Copia y pega a Excel/Word si lo necesitas
✅ **Consolidado incluido**: Ves totales históricos en una sola fila
✅ **Basada en tu query SQL**: Exactamente los mismos datos que proporcionaste
✅ **Lectura rápida**: Todos los datos a la vista

## 📊 Query SQL Utilizada

Ejecuta exactamente esta query (la misma que proporcionaste):

```sql
SELECT
    month_year,
    COUNT(*) as volumen_total_mes,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) as porcentaje_del_total,
    COUNT(nps_recomendacion_score) as volumen_nps,
    ROUND(AVG(nps_recomendacion_score)::numeric, 2) as promedio_nps,
    COUNT(CASE WHEN nps_category = 'Detractor' THEN 1 END) as nps_detractores,
    COUNT(CASE WHEN nps_category = 'Neutral' THEN 1 END) as nps_neutrales,
    COUNT(CASE WHEN nps_category = 'Promotor' THEN 1 END) as nps_promotores,
    -- ... (query completa en el script)
FROM banco_movil_clean
WHERE month_year IS NOT NULL
GROUP BY month_year
ORDER BY month_year DESC;
```

## 🔄 Workflow de Uso

```bash
# 1. Generar tabla
python visualize_nps.py

# 2. Abrir en navegador
# El archivo está en: visualizaciones/tabla_nps.html

# 3. (Opcional) Copiar datos a Excel
# Selecciona la tabla en el navegador → Ctrl+C → Pega en Excel
```

## ❓ Troubleshooting

**Error: "Connection refused"**
- Verifica que PostgreSQL esté corriendo
- Revisa las credenciales en `DB_CONFIG` dentro de `visualize_nps.py`

**Error: "No module named 'pandas'"**
```bash
pip install pandas sqlalchemy psycopg2
```

**La tabla se ve mal en el navegador**
- Usa Chrome, Firefox o Edge (no Internet Explorer)
- El archivo HTML es autocontenido, no necesita Internet

**Quiero actualizar los datos**
```bash
# Primero asegúrate de tener datos actualizados en la BD
python data_extractor.py      # Extrae nuevos datos
python data_cleaner.py         # Limpia datos
python insertar_muestras.py    # Inserta en BD

# Luego regenera la tabla
python visualize_nps.py
```

---

**¿Necesitas ayuda?** Revisa [CLAUDE.md](CLAUDE.md) para documentación completa del proyecto.
