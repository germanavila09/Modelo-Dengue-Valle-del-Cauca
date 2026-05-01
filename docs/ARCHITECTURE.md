# ARCHITECTURE — Arquitectura del Proyecto

Descripción técnica de la arquitectura, componentes y flujo de datos en Observatorio GeoSalud.

## 1. Vista General

```
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL + PostGIS (BD)                    │
│              (42 municipios, 2019–2026, 166k casos)             │
└────────────────────────┬────────────────────────────────────────┘
                         │ SQL queries
                         ▼
            ┌────────────────────────────┐
            │      src/db.py             │
            │  (SQLAlchemy + psycopg2)   │
            │  - cargar_datos()          │
            │  - cargar_puntos_calor()   │
            └────────────┬───────────────┘
                         │ GeoDataFrame
                         ▼
    ┌────────────────────────────────────────────┐
    │         src/transform.py                   │
    │  - limpiar_datos()                         │
    │  - construir_pivot()                       │
    │  - calcular_priorizacion()                 │
    └────────┬──────────────────┬────────────────┘
             │                  │
             ▼ Clean DF         ▼ Pivot DF
    ┌─────────────────┐  ┌──────────────────┐
    │   src/viz.py    │  │   src/mapa.py    │
    │ Gráficas        │  │ Mapa HTML        │
    │ (matplotlib)    │  │ (Leaflet)        │
    └────────┬────────┘  └────────┬─────────┘
             │                    │
             ▼ PNG/SVG            ▼ HTML
    ┌──────────────────────────────────────┐
    │        outputs/                      │
    │  ├── graficas/                       │
    │  │   ├── casos_por_anio.png         │
    │  │   ├── top_municipios_*.png       │
    │  │   └── ...                        │
    │  └── mapa_actual.html               │
    └──────────────────────────────────────┘
```

## 2. Componentes Principales

### 2.1 Backend (Python)

#### `src/config.py`
- **Función**: Carga variables de entorno
- **Entrada**: `.env`
- **Salida**: Constantes (`DB_CONFIG`, `SCHEMA`, `TABLE`, `RUTA_SALIDA`)
- **Dependencias**: `python-dotenv`

#### `src/db.py`
- **Función**: Conexión a PostgreSQL/PostGIS
- **Entrada**: `.env` variables
- **Salida**: GeoDataFrame con datos de municipios + puntos calor
- **Funciones clave**:
  - `crear_engine()` → SQLAlchemy engine
  - `cargar_datos()` → GeoDataFrame municipal
  - `cargar_puntos_calor()` → Puntos individuales de casos
- **Dependencias**: `SQLAlchemy`, `psycopg2`, `geopandas`, `pandas`

#### `src/transform.py`
- **Función**: Procesamiento de datos
- **Entrada**: GeoDataFrame crudo
- **Salida**: GeoDataFrame limpio + Pivot table
- **Funciones clave**:
  - `limpiar_datos()` → normaliza tipos, maneja nulos
  - `construir_pivot()` → tabla municipio × año
  - `calcular_priorizacion()` → ranking por carga histórica
- **Dependencias**: `pandas`, `geopandas`

#### `src/viz.py`
- **Función**: Generación de gráficas
- **Entrada**: GeoDataFrame limpio + Pivot
- **Salida**: Figuras matplotlib (PNG/SVG)
- **Funciones clave**:
  - `graficar_casos_por_anio()` → barras
  - `graficar_top_municipios()` → top N
  - `graficar_heatmap()` → heatmap año × municipio
  - `graficar_scatter_poblacion_incidencia()` → scatter
- **Dependencias**: `matplotlib`, `seaborn`, `pandas`

#### `src/mapa.py`
- **Función**: Generación de dashboard HTML
- **Entrada**: GeoDataFrame + Puntos calor
- **Salida**: HTML interactivo con Leaflet
- **Características**:
  - 3 modos de visualización (coroplético, calor, cluster)
  - Filtros dinámicos (año, variable, Cali)
  - Popups informativos
- **Dependencias**: `geopandas`, `geojson`

#### `src/modelo.py`
- **Función**: Modelado predictivo con NeuralProphet
- **Entrada**: Series semanales de casos
- **Salida**: Pronósticos 52 semanas adelante
- **Funciones clave**:
  - `cargar_serie_semanal()` → agrega a nivel semanal
  - `pronosticar_municipio()` → pronóstico individual
  - `pronosticar_todos()` → todos los 42 municipios (12-15 min con GPU)
- **Dependencias**: `neuralprophet`, `torch`, `pandas`

#### `src/pipeline.py`
- **Función**: Orquestación del análisis completo
- **Entrada**: Parámetros (anio, municipio, ruta_salida)
- **Salida**: Todos los análisis ejecutados
- **Flujo**:
  1. `crear_engine()` → conexión BD
  2. `cargar_datos()` → GeoDataFrame
  3. `limpiar_datos()` → limpieza
  4. `construir_pivot()` → tabla pivote
  5. `calcular_priorizacion()` → ranking
  6. Generar todas las gráficas
  7. Generar mapa HTML
  8. (Opcional) Pronósticos con NeuralProphet

### 2.2 Frontend (JavaScript + HTML)

#### `frontend/Geodata Salud.html`
- Dashboard HTML autocontenido con Leaflet.js
- Estilos CSS modernos (Dark mode friendly)
- Responsive design

#### `frontend/geodata-app.js`
- Lógica de interacción del dashboard
- Gestión de filtros (año, variable, Cali)
- Manejo de eventos de usuario

#### `frontend/geodata-data.js`
- Mock dataset (reemplazar con datos reales exportados)
- Catálogo de municipios
- Datos de incidencia por año

### 2.3 Datos (PostgreSQL)

```sql
-- Tabla principal
public.valle_mun (42 municipios × 8 años = 336+ registros)
  - MPIO_CCDGO: Código DANE del municipio
  - MPIO_CNMBR: Nombre del municipio
  - año: Año (2019-2026)
  - población: Población estimada
  - conteo_dengue: Casos confirmados
  - incidencia_dengue: Casos × 100k habitantes
  - geom: Geometría MultiPolygon (EPSG:3857)

-- Tabla de casos puntuales
public.dengue_m (166k casos individuales)
  - mpio_ccdgo: Código municipio
  - latitud, longitud: Coordenadas
  - año, semana: Temporal
  - geom: Geometría Point
```

## 3. Flujo de Datos

### Análisis Estándar

```
1. CARGA (src/db.py)
   └─> PostgreSQL → GeoDataFrame (336 filas, 42 municipios)

2. LIMPIEZA (src/transform.py)
   └─> Normalizar tipos, manejar nulos → GeoDataFrame limpio

3. TRANSFORMACIÓN (src/transform.py)
   └─> Pivote municipio × año → Tabla 42×8

4. PRIORIZACIÓN (src/transform.py)
   └─> Ranking histórico → CSV exportado

5. VISUALIZACIÓN (src/viz.py)
   ├─> casos_por_anio.png
   ├─> top_municipios_YYYY.png
   ├─> heatmap.png
   ├─> scatter_poblacion.png
   └─> serie_MUNICIPIO.png

6. MAPA (src/mapa.py)
   └─> mapa_actual.html (Leaflet interactivo)

7. OUTPUTS
   └─> outputs/
       ├── graficas/ (7+ PNG)
       ├── mapa_actual.html
       └── priorizacion_municipios.csv
```

### Análisis con Pronósticos

```
(Pasos 1-6 anteriores)

7. SERIES SEMANALES (src/modelo.py)
   └─> Agregar por municipio y semana ISO

8. ENTRENAMIENTO (NeuralProphet)
   ├─> GPU: 12-15 min (42 municipios)
   └─> CPU: 30-45 min

9. PRONÓSTICOS
   └─> 52 semanas adelante × 42 municipios

10. VISUALIZACIÓN PRONÓSTICOS (src/viz.py)
    └─> forecast_top_municipios.png

11. OUTPUTS ADICIONALES
    └─> forecast_municipios.csv
```

## 4. Arquitectura de Directorios

```
observatorio_geosalud/
│
├── src/
│   ├── __init__.py
│   ├── config.py          ◄─── Configuración
│   ├── db.py              ◄─── Conexión BD
│   ├── transform.py       ◄─── Limpieza & Pivot
│   ├── viz.py             ◄─── Gráficas
│   ├── mapa.py            ◄─── Mapa HTML
│   ├── modelo.py          ◄─── NeuralProphet
│   └── pipeline.py        ◄─── Orquestación
│
├── scripts/
│   ├── run_all.py         ◄─── Main entry point
│   ├── verificar_conexion.py
│   ├── resumen.py
│   ├── exportar_mapa.py
│   └── exportar_datos_obs.py
│
├── frontend/
│   ├── Geodata Salud.html
│   ├── geodata-app.js
│   └── geodata-data.js
│
├── notebooks/
│   ├── analisis_dengue.ipynb
│   └── archivo_original.ipynb
│
├── tests/
│   ├── conftest.py
│   ├── test_db.py
│   ├── test_transform.py
│   └── test_pipeline.py
│
├── docs/
│   ├── SETUP.md
│   ├── ARCHITECTURE.md    ◄─── Este archivo
│   └── API.md
│
├── outputs/               (ignorado por .gitignore)
│   ├── graficas/
│   ├── lightning_logs/
│   └── *.csv
│
├── .env                   (ignorado por .gitignore)
├── .env.example
├── requirements.txt
├── setup.py
├── pyproject.toml
└── README.md
```

## 5. Dependencias Principales

### Core ETL
- `pandas` — manipulación de datos
- `geopandas` — datos geoespaciales
- `SQLAlchemy` — ORM
- `psycopg2` — driver PostgreSQL

### Visualización
- `matplotlib` — gráficas estáticas
- `seaborn` — gráficas estadísticas
- `geojson` — exportación para Leaflet

### Machine Learning
- `neuralprophet` — series temporales
- `torch` — backend para NeuralProphet
- `numpy` — operaciones numéricas

### Desarrollo
- `pytest` — testing
- `black` — code formatting
- `jupyter/jupyterlab` — notebooks

## 6. Consideraciones de Performance

### Base de Datos
- **Índices**: Se han creado en `MPIO_CCDGO`, `año` y geometría
- **Query**: ~500ms para cargar 336 registros
- **Caché**: No hay caché local (cada ejecución consulta BD)

### Análisis (CPU)
- **Carga + Transform**: ~1-2 segundos
- **Gráficas**: ~5-10 segundos
- **Mapa HTML**: ~2-3 segundos
- **Total sin ML**: ~10-15 segundos

### Análisis (ML con GPU)
- **NeuralProphet 1 municipio**: ~30 segundos
- **NeuralProphet 42 municipios**: 12-15 minutos
- **Sin GPU**: 30-45 minutos

### Memoria
- **GeoDataFrame (336 filas)**: ~5 MB
- **Pivot table**: ~1 KB
- **HTML mapa**: 200-500 KB
- **Total**: <50 MB en ejecución normal

## 7. Extensibilidad

### Agregar Nuevo Gráfico

1. Crear función en `src/viz.py`:
```python
def graficar_nuevo(gdf, anio):
    fig, ax = plt.subplots()
    # ... lógica
    return fig
```

2. Importar en `src/pipeline.py`
3. Llamar en `ejecutar()`

### Agregar Nueva Visualización Geoespacial

1. Modificar `src/mapa.py` para agregar nueva capa
2. Actualizar lógica de filtros en `frontend/geodata-app.js`

### Agregar Nueva Fuente de Datos

1. Crear nueva tabla en PostgreSQL
2. Crear función de carga en `src/db.py`
3. Integrar en `src/pipeline.py`

## 8. Limitaciones Conocidas

- ⚠️ **Puntos calor**: HTML puede ser lento con >500k puntos
- ⚠️ **CUDA**: Requiere GPU NVIDIA; CPU es mucho más lento
- ⚠️ **PostGIS**: Se asume geometría en EPSG:3857
- ⚠️ **Datos faltantes**: Algunos municipios pueden tener años incompletos

## 9. Futuros Mejoras

- [ ] Caché de resultados (Redis)
- [ ] API REST (FastAPI)
- [ ] Dashboard interactivo Streamlit/Dash
- [ ] Exportación a múltiples formatos (Excel, PDF)
- [ ] Integración CI/CD (GitHub Actions)
- [ ] Documentación automática (Sphinx)
- [ ] Benchmarking y profiling
