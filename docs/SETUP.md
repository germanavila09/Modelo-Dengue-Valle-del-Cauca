# SETUP — Guía de Instalación Detallada

Instrucciones paso-a-paso para instalar y configurar Observatorio GeoSalud en tu máquina local.

## Requisitos Previos

- **Python** 3.10+ ([descargar](https://www.python.org/downloads/))
- **PostgreSQL** 13+ con extensión **PostGIS** ([descargar](https://www.postgresql.org/download/))
- **Git** ([descargar](https://git-scm.com/download/))
- **RAM** mínimo 4 GB (8 GB recomendado para ML)
- **GPU NVIDIA** (opcional, para acelerar pronósticos con NeuralProphet)

## 1. Clonar el Repositorio

```bash
git clone https://github.com/germanavila09/Observatorio-GeoSalud.git
cd observatorio_geosalud
```

## 2. Crear Entorno Virtual

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
```

### Windows (PowerShell)

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

### Windows (cmd)

```cmd
python -m venv venv
venv\Scripts\activate.bat
```

## 3. Instalar Dependencias

### Instalación Básica

```bash
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Con Herramientas de Desarrollo

```bash
pip install -e ".[dev]"
```

Esto instala:
- Paquete en modo editable
- pytest, pytest-cov
- black, flake8, mypy
- jupyter, jupyterlab

### Con Soporte GPU (NVIDIA CUDA)

```bash
# Después de instalar requirements.txt
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

> ℹ️ **Nota**: Requiere NVIDIA CUDA 12.4+. Ver [pytorch.org](https://pytorch.org/) para otras versiones.

## 4. Configurar PostgreSQL

### Crear Base de Datos

```sql
-- Conectar como superusuario (postgres)
CREATE DATABASE dengue OWNER postgres;

-- Conectar a la base dengue
\c dengue

-- Instalar extensión PostGIS
CREATE EXTENSION IF NOT EXISTS postgis;

-- Verificar instalación
SELECT postgis_version();
```

### Crear Tabla Principal

```sql
CREATE TABLE public.valle_mun (
    MPIO_CCDGO      text NOT NULL,
    MPIO_CNMBR      text NOT NULL,
    año             integer NOT NULL,
    población       bigint,
    conteo_dengue   integer DEFAULT 0,
    incidencia_dengue numeric,
    geom            geometry(MultiPolygon, 3857)
);

-- Crear índices para mejorar performance
CREATE INDEX idx_valle_mun_mpio ON public.valle_mun(MPIO_CCDGO);
CREATE INDEX idx_valle_mun_anio ON public.valle_mun(año);
CREATE INDEX idx_valle_mun_geom ON public.valle_mun USING GIST(geom);

-- Conceder permisos
GRANT SELECT ON public.valle_mun TO postgres;
```

### Crear Tabla de Casos Puntuales (Opcional)

```sql
CREATE TABLE public.dengue_m (
    id              SERIAL PRIMARY KEY,
    mpio_ccdgo      text,
    latitud         numeric,
    longitud        numeric,
    año             integer,
    semana          integer,
    fecha_notif     date,
    geom            geometry(Point, 3857)
);

CREATE INDEX idx_dengue_m_mpio ON public.dengue_m(mpio_ccdgo);
CREATE INDEX idx_dengue_m_geom ON public.dengue_m USING GIST(geom);
```

## 5. Configurar Archivo `.env`

Copiar template:

```bash
cp .env.example .env
```

Editar `.env` con tus valores:

```env
# ─── Base de Datos ───────────────────────────────────────
DB_HOST=localhost
DB_PORT=5432
DB_NAME=dengue
DB_USER=postgres
DB_PASSWORD=tu_contraseña_postgres

# Tabla y esquema
DB_SCHEMA=public
DB_TABLE=valle_mun

# ─── Configuración por Defecto ───────────────────────────
ANIO_DEFAULT=2024
MUNICIPIO_DEFAULT=CALI

# ─── Salida de Resultados ────────────────────────────────
RUTA_SALIDA=outputs
```

> ⚠️ **Seguridad**: Nunca comitear `.env` a Git. Ya está en `.gitignore`.

## 6. Verificar Instalación

### Verificar Conexión a BD

```bash
python scripts/verificar_conexion.py
```

Salida esperada:
```
✓ Conexión exitosa a PostgreSQL
✓ Base de datos: dengue
✓ Tabla: public.valle_mun (XXX registros)
✓ Extensión PostGIS: v3.x.x
```

### Verificar Módulos Python

```bash
python -c "import geopandas, sqlalchemy, neuralprophet; print('✓ Módulos OK')"
```

### Ejecutar Tests (si instaló [dev])

```bash
pytest -v
```

## 7. Cargar Datos en PostgreSQL

### Desde CSV

```bash
psql -U postgres -d dengue -c "\COPY public.valle_mun(MPIO_CCDGO, MPIO_CNMBR, año, población, conteo_dengue, incidencia_dengue) FROM STDIN WITH (FORMAT csv, HEADER)"
```

### Desde PostGIS (Shapefile)

```bash
# Convertir shapefile a SQL
shp2pgsql -I -M municipios.shp public.valle_mun | psql -U postgres -d dengue

# O desde QGIS: Layer → Export → PostGIS
```

## 8. Ejecutar Primera Análisis

```bash
# Análisis completo (recomendado)
python scripts/run_all.py --anio 2024

# Salida esperada:
# [1/5] Cargando datos desde PostgreSQL...
# [2/5] Construyendo tabla pivote...
# [3/5] Generando gráficas...
# [4/5] Generando mapa interactivo...
# [5/5] Guardando resumen...
```

## Troubleshooting

### Error: "Connection refused" a PostgreSQL

**Solución:**
```bash
# Verificar que PostgreSQL está corriendo
sudo service postgresql status  # Linux
brew services list | grep postgres  # macOS
services.msc  # Windows → buscar "PostgreSQL"

# Comprobar valores en .env
psql -U postgres -h localhost -d dengue -c "SELECT 1;"
```

### Error: "No module named 'psycopg2'"

```bash
pip install psycopg2-binary
# o
pip install --no-binary psycopg2-binary psycopg2-binary
```

### Error: "CUDA out of memory" (ML)

```bash
# Usar CPU en lugar de GPU
python scripts/run_all.py --accelerator cpu
```

### Error: "ModuleNotFoundError" al importar src

**Solución**: Asegurar que estás en el directorio raíz:
```bash
cd observatorio_geosalud
python scripts/run_all.py
```

O instalar el paquete:
```bash
pip install -e .
```

## Estructura Final Después de Setup

```
observatorio_geosalud/
├── venv/                    # Entorno virtual (ignorado por .gitignore)
├── .env                     # Configuración local (ignorado por .gitignore)
├── src/                     # Módulos Python
├── scripts/                 # Scripts ejecutables
├── frontend/                # Dashboard HTML
├── notebooks/               # Jupyter notebooks
├── tests/                   # Tests unitarios
├── docs/                    # Documentación
├── outputs/                 # Salidas generadas (ignorado por .gitignore)
└── requirements.txt
```

## Siguientes Pasos

1. **Explorar datos**: [Ver notebooks/analisis_dengue.ipynb](../notebooks/analisis_dengue.ipynb)
2. **Entender arquitectura**: [Ver docs/ARCHITECTURE.md](ARCHITECTURE.md)
3. **Referencia de API**: [Ver docs/API.md](API.md)
4. **Contribuir**: Ver CONTRIBUTING.md (próximamente)

## Soporte

- 📧 Email: germanavila09@gmail.com
- 🐛 Issues: [GitHub Issues](https://github.com/germanavila09/Observatorio-GeoSalud/issues)
- 💬 Discussiones: [GitHub Discussions](https://github.com/germanavila09/Observatorio-GeoSalud/discussions)
