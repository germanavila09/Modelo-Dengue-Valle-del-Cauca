# Modelo Dengue — Valle del Cauca

Repositorio de análisis descriptivo espacial de casos de dengue por municipio en el departamento del Valle del Cauca (Colombia), 2019–2026.

Los datos provienen de una base PostgreSQL/PostGIS con registros históricos de 42 municipios. El análisis genera gráficas descriptivas, tablas de priorización y un mapa HTML interactivo con filtros por año, variable y municipio.

---

## Estructura del repositorio

```
modelo_dengue/
├── notebooks/
│   ├── analisis_dengue.ipynb   # notebook principal — orquesta el análisis
│   └── archivo_original.ipynb  # versión original de referencia
├── src/
│   ├── config.py               # carga variables desde .env
│   ├── db.py                   # conexión SQLAlchemy y carga desde PostGIS
│   ├── transform.py            # limpieza, tabla pivote, priorización
│   ├── viz.py                  # gráficas con matplotlib y seaborn
│   ├── mapa.py                 # generación del mapa HTML interactivo (Leaflet)
│   └── pipeline.py             # orquesta el análisis completo
├── scripts/
│   ├── verificar_conexion.py   # verifica BD y estructura de tabla
│   ├── resumen.py              # estadísticas en consola
│   ├── exportar_mapa.py        # genera el mapa HTML
│   └── run_all.py              # ejecuta el pipeline completo
├── .env                        # credenciales locales (no se sube a git)
├── .env.example                # plantilla de configuración
├── .gitignore
└── requirements.txt
```

---

## Requisitos

- Python 3.10+
- PostgreSQL 13+ con extensión PostGIS
- Base de datos `dengue` con tabla `public.valle_mun`

---

## Configuración

### 1. Clonar el repositorio

```bash
git clone https://github.com/germanavila09/Modelo-Dengue-Valle-del-Cauca.git
cd Modelo-Dengue-Valle-del-Cauca
```

### 2. Crear el archivo `.env`

```bash
cp .env.example .env
```

Editar `.env` con tus valores:

```env
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dengue
DB_USER=postgres
DB_PASSWORD=tu_contraseña
DB_SCHEMA=public
DB_TABLE=valle_mun

ANIO_DEFAULT=2024
MUNICIPIO_DEFAULT=CALI

RUTA_SALIDA=ruta/donde/guardar/outputs
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Uso

### Verificar conexión a la BD

```bash
python scripts/verificar_conexion.py
```

### Ver resumen estadístico en consola

```bash
python scripts/resumen.py
```

### Ejecutar análisis completo (re-ejecutar cuando la BD se actualice)

```bash
python scripts/run_all.py
python scripts/run_all.py --anio 2023
python scripts/run_all.py --anio 2023 --municipio PALMIRA
```

### Generar solo el mapa interactivo

```bash
python scripts/exportar_mapa.py --anio 2024
```

### Abrir el notebook

```bash
jupyter lab notebooks/analisis_dengue.ipynb
```

---

## Notebook (`analisis_dengue.ipynb`)

| Sección | Descripción |
|---|---|
| 1. Cargar datos | Conecta a PostgreSQL y carga el GeoDataFrame |
| 2. Descriptivo general | Resumen estadístico y valores nulos |
| 3. Casos por año | Barras de casos totales por año |
| 4. Incidencia por año | Incidencia promedio por año (x 100k hab.) |
| 5. Top municipios por casos | Ranking absoluto para el año de referencia |
| 6. Top municipios por incidencia | Ranking por tasa para el año de referencia |
| 7. Pivote y priorización | Tabla pivote municipio × año con ranking histórico |
| 8. Población vs Incidencia | Scatter — relación tamaño poblacional vs tasa |
| 9. Serie histórica | Tendencia de un municipio a lo largo del tiempo |
| 10. Mapa interactivo | Genera `mapa_actual.html` con filtros |

---

## Módulos (`src/`)

### `config.py`
Lee todas las variables desde `.env` y las expone como constantes (`DB_CONFIG`, `SCHEMA`, `TABLE`, `ANIO`, `MUNICIPIO`, `RUTA_SALIDA`).

### `db.py`
- `crear_engine()` — crea la conexión SQLAlchemy a PostgreSQL
- `cargar_datos(engine)` — carga `MPIO_CCDGO`, `MPIO_CNMBR`, `año`, `población`, `conteo_dengue`, `incidencia_dengue`, `geom`

### `transform.py`
- `limpiar_datos(gdf)` — normaliza tipos y codificación
- `construir_pivot(gdf)` — tabla pivote municipio × año
- `columnas_anio(pivot)` — lista de columnas `dengue_YYYY`
- `calcular_priorizacion(pivot)` — ordena municipios por carga total histórica

### `viz.py`
- `graficar_casos_por_anio(gdf)` — barras de casos totales por año
- `graficar_incidencia_por_anio(gdf)` — barras de incidencia promedio por año
- `graficar_top_municipios(gdf, anio, n)` — top N por casos absolutos
- `graficar_top_municipios_incidencia(gdf, anio, n)` — top N por incidencia
- `graficar_heatmap(pivot, n)` — heatmap municipio × año
- `graficar_scatter_poblacion_incidencia(gdf, anio)` — scatter población vs incidencia
- `graficar_serie_municipio(pivot, municipio)` — serie temporal de un municipio

### `mapa.py`
- `generar_mapa_html(gdf, anios, ruta_salida, anio_default)` — genera HTML autocontenido con mapa Leaflet (capa base CartoDB Light), leyenda dinámica, toggle casos/incidencia, filtro Con/Sin Cali, y popup con nivel de riesgo

### `pipeline.py`
- `ejecutar(anio, municipio, ruta_salida)` — orquesta carga → pivot → gráficas → mapa → resumen

---

## Datos

Tabla `public.valle_mun` en PostgreSQL:

| Columna | Tipo | Descripción |
|---|---|---|
| MPIO_CCDGO | text | Código DANE del municipio |
| MPIO_CNMBR | text | Nombre del municipio |
| año | integer | Año del registro |
| población | bigint | Población estimada |
| conteo_dengue | integer | Casos confirmados de dengue |
| incidencia_dengue | numeric | Incidencia por 100 000 hab. |
| geom | geometry | Geometría municipal (EPSG:3857) |

Cobertura: 42 municipios del Valle del Cauca, 2019–2026.

---

## Outputs

Los archivos generados se guardan en `RUTA_SALIDA` (definida en `.env`):

| Archivo | Descripción |
|---|---|
| `mapa_actual.html` | Mapa interactivo con filtros de año, variable y Cali |
| `priorizacion_municipios.csv` | Tabla pivote con ranking histórico |
| `graficas/casos_por_anio.png` | Casos totales por año |
| `graficas/incidencia_por_anio.png` | Incidencia promedio por año |
| `graficas/top_municipios_YYYY.png` | Top 15 por casos — año de referencia |
| `graficas/top_incidencia_YYYY.png` | Top 15 por incidencia — año de referencia |
| `graficas/heatmap.png` | Heatmap municipio × año |
| `graficas/scatter_poblacion_YYYY.png` | Scatter población vs incidencia |
| `graficas/serie_MUNICIPIO.png` | Serie histórica del municipio de referencia |

Los outputs están excluidos del repositorio vía `.gitignore`.
