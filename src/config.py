import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST", "localhost"),
    "port": int(os.getenv("DB_PORT", 5432)),
    "database": os.getenv("DB_NAME", "dengue"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", ""),
}

SCHEMA = os.getenv("DB_SCHEMA", "public")
TABLE = os.getenv("DB_TABLE", "valle_mun")

ANIO = int(os.getenv("ANIO_DEFAULT", 2024))
MUNICIPIO = os.getenv("MUNICIPIO_DEFAULT", "CALI")

RUTA_SALIDA = Path(os.getenv("RUTA_SALIDA", "outputs"))
