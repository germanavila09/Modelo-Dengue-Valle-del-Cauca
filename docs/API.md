# API — Referencia de Funciones

Documentación de todas las funciones públicas en los módulos de `src/`.

## Tabla de Contenidos

- [src.config](#srcconfig)
- [src.db](#srcdb)
- [src.transform](#srctransform)
- [src.viz](#srcviz)
- [src.mapa](#srcmapa)
- [src.modelo](#srcmodelo)
- [src.pipeline](#srcpipeline)

---

## src.config

**Módulo**: `src/config.py`

Lee configuración desde `.env` y expone constantes para toda la aplicación.

### Constantes Globales

```python
DB_CONFIG: dict
    Configuración de base de datos
    
    Estructura:
    {
        "host": str,         # Host PostgreSQL
        "port": int,         # Puerto (default: 5432)
        "database": str,     # Nombre BD (default: dengue)
        "user": str,         # Usuario PostgreSQL
        "password": str,     # Contraseña
    }
```

```python
SCHEMA: str
    Esquema PostgreSQL (default: "public")
```

```python
TABLE: str
    Tabla principal (default: "valle_mun")
```

```python
ANIO: int
    Año por defecto para análisis (default: 2024)
```

```python
MUNICIPIO: str
    Municipio por defecto para serie temporal (default: "CALI")
```

```python
RUTA_SALIDA: Path
    Directorio para guardar salidas (default: "outputs")
```

---

## src.db

**Módulo**: `src/db.py`

Funciones para conectar a PostgreSQL/PostGIS y cargar datos.

### `crear_engine() -> Engine`

Crea una conexión SQLAlchemy a PostgreSQL.

**Retorna:**
- `sqlalchemy.engine.Engine` — Objeto de conexión reutilizable

**Ejemplo:**
```python
from src.db import crear_engine
engine = crear_engine()
```

**Excepciones:**
- `sqlalchemy.exc.ArgumentError` — Si configuración BD es inválida
- `sqlalchemy.exc.OperationalError` — Si no puede conectar a BD

---

### `cargar_datos(engine=None) -> geopandas.GeoDataFrame`

Carga datos municipales desde tabla `valle_mun`.

**Parámetros:**
- `engine` (Engine, optional) — SQLAlchemy engine. Si no se proporciona, crea uno.

**Retorna:**
- `geopandas.GeoDataFrame` — Datos de 42 municipios (2019-2026)

**Columnas:**
```
MPIO_CCDGO (str)         — Código DANE del municipio
MPIO_CNMBR (str)         — Nombre del municipio
año (int)                — Año del registro
población (int)          — Población estimada
conteo_dengue (int)      — Casos confirmados
incidencia_dengue (float)— Casos × 100k hab.
geometry (MultiPolygon)  — Geometría municipal
```

**Ejemplo:**
```python
from src.db import crear_engine, cargar_datos

engine = crear_engine()
gdf = cargar_datos(engine)
print(f"Municipios: {gdf['MPIO_CNMBR'].nunique()}")  # 42
print(f"Años: {gdf['año'].min()}-{gdf['año'].max()}")  # 2019-2026
```

**Excepciones:**
- `sqlalchemy.exc.ProgrammingError` — Si tabla no existe
- `ValueError` — Si no hay datos en tabla

---

### `cargar_puntos_calor(engine=None) -> geopandas.GeoDataFrame`

Carga casos puntuales individuales desde tabla `dengue_m`.

**Parámetros:**
- `engine` (Engine, optional) — SQLAlchemy engine

**Retorna:**
- `geopandas.GeoDataFrame` — ~166k casos puntuales

**Columnas:**
```
mpio_ccdgo (str)     — Código municipio
latitud (float)      — Coordenada Y
longitud (float)     — Coordenada X
año (int)            — Año del caso
semana (int)         — Semana epidemiológica
geometry (Point)     — Geometría puntual
```

**Ejemplo:**
```python
puntos = cargar_puntos_calor(engine)
print(f"Total casos: {len(puntos)}")  # ~166k
```

---

## src.transform

**Módulo**: `src/transform.py`

Funciones para limpiar, transformar y agregar datos.

### `limpiar_datos(gdf) -> geopandas.GeoDataFrame`

Normaliza tipos, maneja valores faltantes y valida geometría.

**Parámetros:**
- `gdf` (GeoDataFrame) — Datos crudos

**Retorna:**
- `geopandas.GeoDataFrame` — Datos limpios

**Transformaciones:**
- Convierte `año` a int
- Convierte `población`, `conteo_dengue` a int
- Convierte `incidencia_dengue` a float
- Elimina o imputa NaN
- Valida geometría

**Ejemplo:**
```python
from src.transform import limpiar_datos

gdf_limpio = limpiar_datos(gdf)
assert gdf_limpio.isnull().sum().sum() == 0  # Sin nulos
```

---

### `construir_pivot(gdf) -> pandas.DataFrame`

Crea tabla pivote municipio (filas) × año (columnas).

**Parámetros:**
- `gdf` (GeoDataFrame) — Datos limpios

**Retorna:**
- `pandas.DataFrame` — Pivot table (42 filas × 10 columnas)

**Columnas:**
```
MPIO_CCDGO           — Código municipio
MPIO_CNMBR           — Nombre municipio
dengue_2019          — Casos 2019
dengue_2020          — Casos 2020
...
dengue_2026          — Casos 2026
```

**Ejemplo:**
```python
from src.transform import construir_pivot

pivot = construir_pivot(gdf_limpio)
print(pivot.shape)  # (42, 10)
print(pivot.loc[0, "dengue_2024"])  # Casos Cali 2024
```

---

### `columnas_anio(pivot) -> list[str]`

Retorna lista de columnas de años (dengue_YYYY).

**Parámetros:**
- `pivot` (DataFrame) — Pivot table

**Retorna:**
- `list[str]` — Columnas de años en orden

**Ejemplo:**
```python
years = columnas_anio(pivot)  # ['dengue_2019', 'dengue_2020', ...]
```

---

### `calcular_priorizacion(pivot) -> pandas.DataFrame`

Calcula ranking de municipios por carga histórica.

**Parámetros:**
- `pivot` (DataFrame) — Pivot table

**Retorna:**
- `pandas.DataFrame` — Pivot con columnas adicionales:
  - `total` — Suma de casos 2019-2026
  - `ranking` — Posición (1 = mayor carga)
  - `pct_total` — Porcentaje del total nacional

**Ejemplo:**
```python
priorizacion = calcular_priorizacion(pivot)
print(priorizacion.nlargest(5, "total"))  # Top 5 por carga
```

---

## src.viz

**Módulo**: `src/viz.py`

Funciones para generar gráficas con matplotlib/seaborn.

### `graficar_casos_por_anio(gdf) -> matplotlib.figure.Figure`

Gráfica de barras: casos totales por año (2019-2026).

**Parámetros:**
- `gdf` (GeoDataFrame) — Datos

**Retorna:**
- `matplotlib.figure.Figure` — Figura lista para guardar/mostrar

**Ejemplo:**
```python
fig = graficar_casos_por_anio(gdf)
fig.savefig("outputs/casos_por_anio.png", dpi=300, bbox_inches="tight")
```

---

### `graficar_incidencia_por_anio(gdf) -> matplotlib.figure.Figure`

Gráfica de barras: incidencia promedio por año.

**Parámetros:**
- `gdf` (GeoDataFrame) — Datos

**Retorna:**
- `matplotlib.figure.Figure`

---

### `graficar_top_municipios(gdf, anio, n=15) -> matplotlib.figure.Figure`

Top N municipios por casos absolutos en año específico.

**Parámetros:**
- `gdf` (GeoDataFrame) — Datos
- `anio` (int) — Año de análisis
- `n` (int, optional) — Número de municipios a mostrar (default: 15)

**Retorna:**
- `matplotlib.figure.Figure`

---

### `graficar_top_municipios_incidencia(gdf, anio, n=15) -> matplotlib.figure.Figure`

Top N municipios por incidencia (casos × 100k hab).

**Parámetros:**
- `gdf` (GeoDataFrame)
- `anio` (int)
- `n` (int, optional)

**Retorna:**
- `matplotlib.figure.Figure`

---

### `graficar_heatmap(pivot, n=42) -> matplotlib.figure.Figure`

Heatmap: municipios (filas) × años (columnas), coloreado por casos.

**Parámetros:**
- `pivot` (DataFrame) — Pivot table
- `n` (int, optional) — Número de municipios a mostrar (default: todos)

**Retorna:**
- `matplotlib.figure.Figure`

---

### `graficar_scatter_poblacion_incidencia(gdf, anio) -> matplotlib.figure.Figure`

Scatter plot: población (X) vs incidencia (Y).

**Parámetros:**
- `gdf` (GeoDataFrame)
- `anio` (int)

**Retorna:**
- `matplotlib.figure.Figure`

**Insight**: Identifica si municipios grandes tienen mayor/menor incidencia.

---

### `graficar_serie_municipio(pivot, municipio) -> matplotlib.figure.Figure`

Serie temporal: casos de un municipio (2019-2026).

**Parámetros:**
- `pivot` (DataFrame) — Pivot table
- `municipio` (str) — Nombre del municipio

**Retorna:**
- `matplotlib.figure.Figure` — Serie con línea + puntos

---

### `graficar_forecast_municipio(forecast_df, mpio_ccdgo, nombre_municipio=None, ruta_salida=None) -> matplotlib.figure.Figure`

Series temporal con pronóstico (histórico + 52 semanas adelante).

**Parámetros:**
- `forecast_df` (DataFrame) — Salida de `pronosticar_municipio()`
- `mpio_ccdgo` (str) — Código municipio
- `nombre_municipio` (str, optional) — Para título
- `ruta_salida` (str, optional) — Path para guardar

**Retorna:**
- `matplotlib.figure.Figure`

---

## src.mapa

**Módulo**: `src/mapa.py`

Funciones para generar dashboard HTML interactivo con Leaflet.js.

### `generar_mapa_html(gdf, anios, ruta_salida, anio_default=None, puntos_df=None) -> None`

Genera archivo HTML autocontenido con mapa interactivo.

**Parámetros:**
- `gdf` (GeoDataFrame) — Datos municipales
- `anios` (list[int]) — Lista de años disponibles
- `ruta_salida` (str) — Directorio de salida
- `anio_default` (int, optional) — Año inicial (default: máximo)
- `puntos_df` (GeoDataFrame, optional) — Puntos calor (casos puntuales)

**Salida:**
- Crea `{ruta_salida}/mapa_actual.html` (200-500 KB)

**Características del mapa:**
- 3 modos exclusivos: Coroplético | Calor | Cluster
- Filtros: Año, Variable (Casos/Incidencia), Con/Sin Cali
- Panel de indicadores
- Popups informativos

**Ejemplo:**
```python
from src.mapa import generar_mapa_html

generar_mapa_html(
    gdf=gdf,
    anios=[2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026],
    ruta_salida="outputs",
    anio_default=2024,
    puntos_df=puntos_calor
)
# Genera: outputs/mapa_actual.html
```

---

## src.modelo

**Módulo**: `src/modelo.py`

Funciones para modelado predictivo con NeuralProphet.

### `cargar_serie_semanal(engine, mpio_ccdgo=None) -> pandas.DataFrame`

Carga y agrega casos a nivel semanal (ISO) por municipio.

**Parámetros:**
- `engine` (Engine) — SQLAlchemy engine
- `mpio_ccdgo` (str, optional) — Filtrar por municipio (default: todos)

**Retorna:**
- `pandas.DataFrame` — Columnas: mpio_ccdgo, ds (fecha lunes), y (casos)

**Ejemplo:**
```python
from src.modelo import cargar_serie_semanal

serie_cali = cargar_serie_semanal(engine, mpio_ccdgo="76001")
print(serie_cali.shape)  # ~420 semanas
```

---

### `pronosticar_municipio(engine, mpio_ccdgo, periodos=52, accelerator="gpu") -> pandas.DataFrame`

Entrena modelo NeuralProphet y retorna pronóstico para 1 municipio.

**Parámetros:**
- `engine` (Engine) — SQLAlchemy engine
- `mpio_ccdgo` (str) — Código DANE del municipio
- `periodos` (int, optional) — Semanas a pronosticar (default: 52)
- `accelerator` (str, optional) — "gpu" o "cpu" (default: "gpu")

**Retorna:**
- `pandas.DataFrame` — Columnas: ds, y (histórico), yhat (pronóstico), ŷ_lower, ŷ_upper

**Tiempo de ejecución:**
- GPU: ~30 segundos
- CPU: ~2-3 minutos

**Ejemplo:**
```python
forecast = pronosticar_municipio(engine, "76001", periodos=52)
print(forecast.tail(10))  # Últimas 10 semanas pronósticadas
```

---

### `pronosticar_todos(engine, periodos=52, accelerator="gpu", ruta_salida=None) -> pandas.DataFrame`

Entrena modelos para TODOS los 42 municipios (paralelo).

**Parámetros:**
- `engine` (Engine)
- `periodos` (int, optional)
- `accelerator` (str, optional)
- `ruta_salida` (str, optional) — Para guardar archivos intermedios

**Retorna:**
- `pandas.DataFrame` — Pronósticos agregados (42 municipios × 52 semanas)

**Tiempo de ejecución:**
- GPU: 12-15 minutos
- CPU: 30-45 minutos

**Ejemplo:**
```python
forecast_todos = pronosticar_todos(engine, periodos=52, accelerator="gpu")
forecast_todos.to_csv("outputs/forecast_municipios.csv", index=False)
```

---

## src.pipeline

**Módulo**: `src/pipeline.py`

Funciones de orquestación que ejecutan el análisis completo.

### `ejecutar(anio=None, municipio=None, ruta_salida=None) -> None`

Ejecuta el pipeline completo: carga → limpieza → gráficas → mapa.

**Parámetros:**
- `anio` (int, optional) — Año para análisis (default: ANIO_DEFAULT)
- `municipio` (str, optional) — Municipio para serie temporal (default: MUNICIPIO_DEFAULT)
- `ruta_salida` (str, optional) — Directorio de salida (default: RUTA_SALIDA)

**Flujo:**
1. Carga datos desde PostgreSQL
2. Limpia datos
3. Construye pivot table
4. Calcula priorización
5. Genera 7+ gráficas
6. Genera mapa HTML
7. Exporta CSV

**Salidas:**
```
outputs/
├── graficas/
│   ├── casos_por_anio.png
│   ├── incidencia_por_anio.png
│   ├── top_municipios_2024.png
│   ├── top_incidencia_2024.png
│   ├── heatmap.png
│   ├── scatter_poblacion_2024.png
│   └── serie_CALI.png
├── mapa_actual.html
└── priorizacion_municipios.csv
```

**Tiempo total:** ~10-15 segundos

**Ejemplo:**
```python
from src.pipeline import ejecutar

ejecutar(anio=2024, municipio="PALMIRA", ruta_salida="outputs")
```

---

### `ejecutar_forecast(anio=None, municipio=None, ruta_salida=None, todos=False, periodos=52, accelerator="gpu") -> pandas.DataFrame`

Ejecuta pronósticos con NeuralProphet.

**Parámetros:**
- `anio` (int, optional)
- `municipio` (str, optional)
- `ruta_salida` (str, optional)
- `todos` (bool, optional) — True: todos los 42 municipios | False: solo municipio de referencia
- `periodos` (int, optional) — Semanas a pronosticar
- `accelerator` (str, optional) — "gpu" o "cpu"

**Salidas:**
- Si `todos=False`: genera `forecast_{mpio_ccdgo}.png`
- Si `todos=True`: genera `forecast_top_municipios.png` (grid de top 6)

**Ejemplo:**
```python
from src.pipeline import ejecutar_forecast

# Solo Cali
forecast = ejecutar_forecast(municipio="CALI", todos=False)

# Todos los municipios (lento)
forecast_todos = ejecutar_forecast(todos=True, accelerator="gpu")
```

---

## Tipos de Datos Comunes

### GeoDataFrame Estándar

```python
gdf = GeoDataFrame({
    "MPIO_CCDGO": ["76001", ...],       # str
    "MPIO_CNMBR": ["Cali", ...],        # str
    "año": [2023, ...],                 # int64
    "población": [2250000, ...],        # int64
    "conteo_dengue": [1250, ...],       # int64
    "incidencia_dengue": [55.5, ...],   # float64
    "geometry": [MultiPolygon, ...]     # geometry
})
```

### Pivot Table Estándar

```python
pivot = DataFrame({
    "MPIO_CCDGO": ["76001", ...],
    "MPIO_CNMBR": ["Cali", ...],
    "dengue_2019": [1200, ...],
    "dengue_2020": [950, ...],
    ...
    "dengue_2026": [1250, ...],
})
```

---

## Manejo de Errores

Excepciones comunes y cómo manejarlas:

```python
from sqlalchemy.exc import OperationalError, ProgrammingError

try:
    from src.db import crear_engine
    engine = crear_engine()
except OperationalError:
    print("ERROR: No se puede conectar a PostgreSQL. Verificar .env")
except ProgrammingError:
    print("ERROR: Tabla no existe en la BD. Ver SETUP.md")
```

---

## Ejemplos Completos

### Ejemplo 1: Análisis Simple

```python
from src.db import crear_engine, cargar_datos
from src.transform import limpiar_datos, construir_pivot, calcular_priorizacion
from src.viz import graficar_casos_por_anio

# Carga
engine = crear_engine()
gdf = cargar_datos(engine)

# Limpieza
gdf = limpiar_datos(gdf)

# Análisis
pivot = construir_pivot(gdf)
priorizacion = calcular_priorizacion(pivot)

# Visualización
fig = graficar_casos_por_anio(gdf)
fig.savefig("output.png")
```

### Ejemplo 2: Pipeline Completo

```python
from src.pipeline import ejecutar

ejecutar(anio=2024, municipio="PALMIRA")
```

### Ejemplo 3: Pronósticos

```python
from src.pipeline import ejecutar_forecast

forecast = ejecutar_forecast(todos=True, accelerator="gpu")
```

---

**Última actualización**: Abril 2026

Para más ayuda, ver [SETUP.md](SETUP.md) o [ARCHITECTURE.md](ARCHITECTURE.md).
