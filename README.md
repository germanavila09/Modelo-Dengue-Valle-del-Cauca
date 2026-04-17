# Modelo Dengue — Valle del Cauca

Análisis descriptivo espacial de casos de dengue por municipio en el Valle del Cauca, a partir de datos almacenados en PostgreSQL/PostGIS.

## Estructura

```
modelo_dengue/
├── notebooks/
│   ├── analisis_dengue.ipynb   # notebook principal
│   └── archivo_original.ipynb  # versión original de referencia
├── src/
│   ├── config.py               # variables de entorno
│   ├── db.py                   # conexión y carga desde PostgreSQL
│   ├── transform.py            # limpieza, pivot, priorización
│   ├── viz.py                  # gráficas (matplotlib/seaborn)
│   └── mapa.py                 # generación de mapa HTML interactivo
├── .env.example                # plantilla de configuración
└── requirements.txt
```

## Requisitos

- Python 3.10+
- PostgreSQL con extensión PostGIS y base de datos `dengue`

## Configuración

1. Copiar la plantilla de variables de entorno:
   ```bash
   cp .env.example .env
   ```

2. Editar `.env` con tus credenciales y rutas:
   ```
   DB_HOST=localhost
   DB_PORT=5432
   DB_NAME=dengue
   DB_USER=postgres
   DB_PASSWORD=tu_contraseña
   RUTA_SALIDA=ruta/donde/guardar/mapas
   ```

3. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
   ```

## Uso

Abrir y ejecutar `notebooks/analisis_dengue.ipynb` en orden. El notebook:

- Carga los datos desde PostgreSQL
- Genera gráficas descriptivas por año y municipio
- Construye una tabla pivote con priorización
- Exporta un mapa HTML interactivo con filtros de año y municipio

## Datos

La tabla `public.valle_mun` en PostgreSQL contiene:

| Columna | Tipo | Descripción |
|---|---|---|
| MPIO_CCDGO | text | Código DANE del municipio |
| MPIO_CNMBR | text | Nombre del municipio |
| año | integer | Año del registro |
| población | bigint | Población del municipio |
| conteo_dengue | integer | Casos confirmados |
| incidencia_dengue | numeric | Incidencia por 100 000 hab. |
| geom | geometry | Geometría (EPSG:3857) |
