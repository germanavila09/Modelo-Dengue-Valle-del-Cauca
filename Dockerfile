# =============================================================================
# Dockerfile — Observatorio GeoSalud (Laboratorio TerrarIA)
# Stack: FastAPI + Google ADK (Gemini) + GeoPandas + NeuralProphet + PostGIS client
# =============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=America/Bogota

# -----------------------------------------------------------------------------
# Dependencias del sistema:
#   - libgdal/geos/proj: geopandas, folium
#   - libspatialindex:   rtree (índices espaciales de geopandas)
#   - libpq + postgresql-client: psycopg2 + pg_restore para la base de datos
#   - build-essential:   compilación de paquetes que no tienen wheel
#   - tzdata, curl:      utilidades
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgdal-dev \
        libgeos-dev \
        libproj-dev \
        libspatialindex-dev \
        libpq-dev \
        postgresql-client \
        tzdata \
        curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# -----------------------------------------------------------------------------
# Instalar dependencias Python
# -----------------------------------------------------------------------------
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

# -----------------------------------------------------------------------------
# Copiar el código de la aplicación
# -----------------------------------------------------------------------------
COPY . .

EXPOSE 8080

# Healthcheck simple: el endpoint /health del server.py
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -fsS http://localhost:8080/health || exit 1

# Comando por defecto: arranca FastAPI con recarga automática
CMD ["uvicorn", "chatbot.server:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]
