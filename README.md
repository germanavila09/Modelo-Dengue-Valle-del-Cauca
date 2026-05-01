# Observatorio GeoSalud — Análisis Dengue Valle del Cauca

Repositorio de análisis descriptivo espacial de casos de dengue por municipio en el departamento del Valle del Cauca (Colombia), 2019–2026.

Los datos provienen de una base PostgreSQL/PostGIS con registros históricos de 42 municipios. El análisis genera gráficas descriptivas, tablas de priorización, modelos predictivos (NeuralProphet) y un dashboard HTML interactivo con filtros por año, variable y municipio.

**Stack**: Python (pandas, geopandas, SQLAlchemy) | PostgreSQL/PostGIS | NeuralProphet (ML) | Leaflet.js (Frontend) | PyTorch (GPU)

---

## 📁 Estructura del Repositorio

```
observatorio_geosalud/
├── src/                        # Módulos core del pipeline
│   ├── config.py              # Configuración (.env)
│   ├── db.py                  # Conexión PostGIS
│   ├── transform.py           # Limpieza, pivot, priorización
│   ├── viz.py                 # Gráficas (matplotlib/seaborn)
│   ├── mapa.py                # Generación del mapa HTML (Leaflet)
│   ├── modelo.py              # NeuralProphet forecasts
│   ├── pipeline.py            # Orquestación completa
│   └── __init__.py
│
├── scripts/                    # Scripts ejecutables
│   ├── run_all.py            # Pipeline completo
│   ├── exportar_mapa.py       # Solo mapa interactivo
│   ├── resumen.py             # Estadísticas en consola
│   ├── verificar_conexion.py  # Check BD
│   └── exportar_datos_obs.py  # Export para observatorio
│
├── frontend/                   # Dashboard HTML (Leaflet)
│   ├── Geodata Salud.html     # Dashboard principal
│   ├── geodata-app.js         # Lógica JS
│   └── geodata-data.js        # Mock data
│
├── notebooks/                  # Análisis exploratorio
│   ├── analisis_dengue.ipynb  # Notebook principal
│   └── archivo_original.ipynb # Versión original
│
├── tests/                      # Tests unitarios
│   ├── __init__.py
│   ├── test_db.py
│   ├── test_transform.py
│   └── test_pipeline.py
│
├── docs/                       # Documentación
│   ├── SETUP.md               # Instrucciones de instalación
│   ├── ARCHITECTURE.md        # Arquitectura del proyecto
│   └── API.md                 # Referencia de módulos
│
├── outputs/                    # Archivos generados (no se sube a git)
│   ├── graficas/              # Gráficas PNG/SVG
│   ├── lightning_logs/        # Logs de entrenamiento PyTorch
│   └── *.csv                  # CSVs exportados
│
├── .env                        # Credenciales locales (no se sube)
├── .env.example               # Template de configuración
├── .gitignore
├── requirements.txt
├── setup.py
└── README.md
```

---

## ⚡ Quick Start

### 1. Clonar y configurar

```bash
git clone https://github.com/germanavila09/Observatorio-GeoSalud.git
cd observatorio_geosalud

# Copiar template de configuración
cp .env.example .env
```

### 2. Editar `.env` con credenciales de BD

```env
# Database
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dengue
DB_USER=postgres
DB_PASSWORD=tu_contraseña
DB_SCHEMA=public
DB_TABLE=valle_mun

# Defaults
ANIO_DEFAULT=2024
MUNICIPIO_DEFAULT=CALI
RUTA_SALIDA=outputs
```

### 3. Instalar dependencias

```bash
# Crear entorno virtual (recomendado)
python -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate

# Instalar requisitos
pip install -r requirements.txt

# (Opcional) PyTorch con CUDA para GPU
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

### 4. Verificar conexión a BD

```bash
python scripts/verificar_conexion.py
```

### 5. Ejecutar análisis

```bash
# Análisis completo
python scripts/run_all.py

# Con año específico
python scripts/run_all.py --anio 2023

# Con municipio específico
python scripts/run_all.py --anio 2023 --municipio PALMIRA
```

---



---

## 📊 Uso

### Scripts principales

| Script | Descripción |
|--------|-------------|
| `run_all.py` | Pipeline completo: carga → transform → gráficas → mapa → pronósticos |
| `verificar_conexion.py` | Verifica conexión BD y estructura de tabla |
| `resumen.py` | Resumen estadístico en consola |
| `exportar_mapa.py` | Genera solo el mapa HTML interactivo |
| `exportar_datos_obs.py` | Exporta datos para el observatorio |

#### Ejemplos:

```bash
# Análisis completo para año por defecto (ANIO_DEFAULT)
python scripts/run_all.py

# Año específico
python scripts/run_all.py --anio 2023

# Con municipio específico para serie temporal
python scripts/run_all.py --anio 2023 --municipio PALMIRA

# Solo pronósticos
python scripts/run_all.py --forecast --todos

# Ver estadísticas rápidas
python scripts/resumen.py

# Exportar solo mapa
python scripts/exportar_mapa.py --anio 2024
```

### Notebook (`analisis_dengue.ipynb`)

Notebook Jupyter con análisis exploratorio sección-por-sección:

| Sección | Output |
|---------|--------|
| Cargar datos | GeoDataFrame desde PostgreSQL |
| Descriptivo general | Resumen estadístico, nulos |
| Casos por año | Gráfica barras |
| Incidencia por año | Gráfica incidencia × 100k hab |
| Top municipios | Ranking por casos absolutos |
| Top por incidencia | Ranking por tasa |
| Pivote & priorización | Tabla municipio × año |
| Población vs Incidencia | Scatter plot |
| Serie histórica | Tendencia municipal |
| Mapa interactivo | HTML autocontenido (Leaflet) |

```bash
jupyter lab notebooks/analisis_dengue.ipynb
```

### Dashboard HTML

Abrir el dashboard interactivo en navegador:

```bash
# Windows
start "frontend/Geodata Salud.html"

# macOS
open "frontend/Geodata Salud.html"

# Linux
xdg-open "frontend/Geodata Salud.html"
```

**Características del dashboard:**
- 📍 Mapa coroplético (municipios coloreados por variable)
- 🔥 Mapa de calor (166k casos puntuales)
- 🔗 Cluster (agrupación de casos)
- 🎚️ Filtros: Año, Variable (Casos/Incidencia), Con/Sin Cali
- 📊 Panel de indicadores (total casos, incidencia promedio, municipios críticos)

---

## 🛠️ Desarrollo

### Instalar en modo editable + dev dependencies

```bash
# Instalar como paquete editable
pip install -e .

# Instalar con extras para desarrollo (cuando esté disponible)
# pip install -e ".[dev]"
```

### Ejecutar tests

```bash
# Todos los tests
pytest

# Con coverage
pytest --cov=src

# Modo verbose
pytest -v

# Solo un archivo
pytest tests/test_db.py
```

### Estructura de módulos

#### `src/config.py`
Lee variables desde `.env`. Expone: `DB_CONFIG`, `SCHEMA`, `TABLE`, `ANIO`, `MUNICIPIO`, `RUTA_SALIDA`.

#### `src/db.py`
- `crear_engine()` — SQLAlchemy engine
- `cargar_datos(engine)` — GeoDataFrame desde `valley_mun`
- `cargar_puntos_calor(engine)` — Lat/lng de casos puntuales

#### `src/transform.py`
- `limpiar_datos(gdf)` — Normalización y encoding
- `construir_pivot(gdf)` — Tabla municipio × año
- `calcular_priorizacion(pivot)` — Ranking histórico

#### `src/viz.py`
- `graficar_casos_por_anio(gdf)` — Barras
- `graficar_incidencia_por_anio(gdf)` — Incidencia × 100k
- `graficar_top_municipios(gdf, anio)` — Top N por casos
- `graficar_top_municipios_incidencia(gdf, anio)` — Top N por tasa
- `graficar_heatmap(pivot)` — Heatmap año × municipio
- `graficar_scatter_poblacion_incidencia(gdf, anio)` — Scatter
- `graficar_serie_municipio(pivot, municipio)` — Serie temporal

#### `src/mapa.py`
- `generar_mapa_html(gdf, anios, ruta_salida)` — HTML Leaflet con:
  - **Modo coroplético** — municipios coloreados
  - **Modo mapa de calor** — 166k puntos
  - **Modo cluster** — agrupación
  - Filtros dinámicos (año, variable, Cali)
  - Popup con riesgo, población, % del total

#### `src/modelo.py`
Modelos predictivos con NeuralProphet:
- `cargar_serie_semanal(engine, mpio_ccdgo)` — Agrega a nivel semanal
- `pronosticar_municipio(engine, mpio_ccdgo, periodos, accelerator)` — Pronóstico individual
- `pronosticar_todos(engine, periodos, accelerator)` — Todos los 42 municipios

#### `src/pipeline.py`
- `ejecutar(anio, municipio, ruta_salida)` — Orquesta análisis completo
- `ejecutar_forecast(anio, municipio, todos, periodos, accelerator)` — Solo pronósticos

### Agregar un nuevo gráfico

1. Crear función en `src/viz.py`:
```python
def graficar_nuevo(gdf, anio):
    fig, ax = plt.subplots(figsize=(10, 6))
    # ... tu lógica
    return fig
```

2. Importar en `src/pipeline.py`:
```python
from .viz import graficar_nuevo
```

3. Llamar en `ejecutar()`:
```python
_guardar(graficar_nuevo(gdf, anio), ruta_graficas / "nuevo.png")
```

---

## 📈 Requisitos del Sistema

- **Python**: 3.10+
- **PostgreSQL**: 13+ con extensión PostGIS
- **RAM**: 4+ GB (8+ GB recomendado para ML)
- **GPU** (opcional): NVIDIA con CUDA 12.4+ para acelerar pronósticos

### Tabla PostgreSQL requerida

```sql
CREATE TABLE public.valle_mun (
    MPIO_CCDGO      text,
    MPIO_CNMBR      text,
    año             integer,
    población       bigint,
    conteo_dengue   integer,
    incidencia_dengue numeric,
    geom            geometry(MultiPolygon, 3857)
);

-- Índices recomendados
CREATE INDEX idx_valle_mun_mpio ON public.valle_mun(MPIO_CCDGO);
CREATE INDEX idx_valle_mun_anio ON public.valle_mun(año);
CREATE INDEX idx_valle_mun_geom ON public.valle_mun USING GIST(geom);
```

Cobertura: **42 municipios**, **2019–2026**.

---

## 📦 Outputs Generados

Archivos guardados en `outputs/` (excluido de git):

```
outputs/
├── graficas/
│   ├── casos_por_anio.png
│   ├── incidencia_por_anio.png
│   ├── top_municipios_2024.png
│   ├── top_incidencia_2024.png
│   ├── heatmap.png
│   ├── scatter_poblacion_2024.png
│   └── serie_MUNICIPIO.png
├── lightning_logs/          # Logs PyTorch
│   ├── version_0/
│   ├── version_1/
│   └── ...
├── priorizacion_municipios.csv
├── mapa_actual.html
└── forecast_municipios.csv  # (si --forecast)
```

---

## 🔗 Arquitectura y Flujo

```
PostgreSQL (BD)
    ↓
db.py: cargar_datos() → GeoDataFrame
    ↓
transform.py: limpiar_datos() → normalize
    ↓
├─→ viz.py: generar gráficas → PNG
├─→ mapa.py: generar HTML → Leaflet
└─→ modelo.py: NeuralProphet → Pronósticos
    ↓
outputs/ ← todos los archivos generados
    ↓
pipeline.py: orquesta todo
    ↓
scripts/run_all.py ← punto de entrada principal
```

---

## 📝 Variables de Entorno

```env
# Conexión BD (requerido)
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dengue
DB_USER=postgres
DB_PASSWORD=

# Esquema y tabla (requerido)
DB_SCHEMA=public
DB_TABLE=valle_mun

# Defaults (recomendado)
ANIO_DEFAULT=2024
MUNICIPIO_DEFAULT=CALI
RUTA_SALIDA=outputs
```

---

## 📚 Documentación Adicional

- [SETUP.md](docs/SETUP.md) — Instalación detallada
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) — Arquitectura del proyecto
- [API.md](docs/API.md) — Referencia de funciones (auto-generada)

---

## 🐛 Troubleshooting

### Error: "No module named 'psycopg2'"
```bash
pip install psycopg2-binary
```

### Error: "Connection refused" a PostgreSQL
- Verificar que PostgreSQL está corriendo
- Comprobar host/port/usuario en `.env`
- Ejecutar: `python scripts/verificar_conexion.py`

### Error: "CUDA out of memory" (ML)
```bash
# Usar CPU en lugar de GPU
python scripts/run_all.py --forecast --accelerator cpu
```

### Las gráficas no se generan
- Verificar que `outputs/graficas/` existe
- Comprobar permisos de escritura
- Ver logs en consola

---

## 📄 Licencia

[Especificar licencia]

---

## 👤 Autores

- Germán Avila (germanavila09)
- [Otros contribuyentes]

---

## 📧 Contacto

[Email o canal de contacto]
