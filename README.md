# Modelo Dengue — Valle del Cauca

Repositorio de análisis descriptivo espacial de casos de dengue por municipio en el departamento del Valle del Cauca (Colombia), 2019–2026.

Los datos provienen de una base PostgreSQL/PostGIS con registros históricos de 42 municipios. El análisis genera gráficas descriptivas, tablas de priorización y un mapa HTML interactivo con filtros por año y municipio.

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
│   └── mapa.py                 # generación del mapa HTML interactivo (Leaflet)
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
git clone <url-del-repositorio>
cd modelo_dengue
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

RUTA_SALIDA=ruta/donde/guardar/mapas
```

### 3. Instalar dependencias

```bash
pip install -r requirements.txt
```

---

## Uso

Abrir `notebooks/analisis_dengue.ipynb` y ejecutar las celdas en orden.

El notebook realiza los siguientes pasos:

| Paso | Descripción |
|---|---|
| 1. Cargar datos | Conecta a PostgreSQL y carga el GeoDataFrame |
| 2. Descriptivo | Resumen estadístico y valores nulos |
| 3. Visualizaciones | Barras por año, top municipios, heatmap, serie temporal |
| 4. Pivote y priorización | Tabla pivote por municipio/año con ranking total |
| 5. Mapa interactivo | Genera `mapa_actual.html` con filtros de año y Cali |

---

## Módulos (`src/`)

### `config.py`
Lee todas las variables desde `.env` y las expone como constantes (`DB_CONFIG`, `SCHEMA`, `TABLE`, `ANIO`, `MUNICIPIO`, `RUTA_SALIDA`).

### `db.py`
- `crear_engine()` — crea la conexión SQLAlchemy a PostgreSQL
- `cargar_datos(engine)` — carga la tabla como GeoDataFrame vía PostGIS

### `transform.py`
- `limpiar_datos(gdf)` — normaliza tipos y codificación
- `construir_pivot(gdf)` — tabla pivote municipio × año
- `columnas_anio(pivot)` — lista de columnas `dengue_YYYY`
- `calcular_priorizacion(pivot)` — ordena municipios por carga total histórica

### `viz.py`
- `graficar_casos_por_anio(gdf)` — barras de casos totales por año
- `graficar_top_municipios(gdf, anio, n)` — ranking de municipios para un año
- `graficar_heatmap(pivot, n)` — heatmap municipio × año
- `graficar_serie_municipio(pivot, municipio)` — serie temporal de un municipio

### `mapa.py`
- `generar_mapa_html(gdf, anios, ruta_salida, anio_default)` — genera un archivo HTML autocontenido con mapa Leaflet, leyenda dinámica y filtros de año y Cali/Sin Cali

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
| `mapa_actual.html` | Mapa interactivo con filtros por año y municipio |

Los outputs están excluidos del repositorio vía `.gitignore`.
