import geopandas as gpd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from .config import DB_CONFIG, SCHEMA, TABLE


def crear_engine():
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=DB_CONFIG["database"],
    )
    return create_engine(url, connect_args={"client_encoding": "utf8"})


def cargar_datos(engine=None):
    if engine is None:
        engine = crear_engine()

    query = f"""
    SELECT
        "MPIO_CCDGO",
        "MPIO_CNMBR",
        "año",
        "población",
        conteo_dengue,
        incidencia_dengue,
        geom
    FROM {SCHEMA}.{TABLE}
    ORDER BY "año", "MPIO_CNMBR";
    """

    return gpd.read_postgis(query, engine, geom_col="geom")
