import geopandas as gpd
import pandas as pd
import re
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

from .config import DB_CONFIG, SCHEMA, TABLE


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _quote_identifier(identifier):
    if not _IDENTIFIER_RE.match(identifier):
        raise ValueError(f"Identificador SQL inválido: {identifier!r}")
    return f'"{identifier}"'


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

    tabla = f"{_quote_identifier(SCHEMA)}.{_quote_identifier(TABLE)}"
    query = f"""
    SELECT
        "MPIO_CCDGO",
        "MPIO_CNMBR",
        "año",
        "población",
        conteo_dengue,
        incidencia_dengue,
        geom
    FROM {tabla}
    ORDER BY "año", "MPIO_CNMBR";
    """

    return gpd.read_postgis(query, engine, geom_col="geom")


def cargar_puntos_calor(engine=None):
    if engine is None:
        engine = crear_engine()

    query = """
    SELECT
        "año"::text AS anio,
        mpio_ccdgo,
        ROUND(ST_Y(geom)::numeric, 5) AS lat,
        ROUND(ST_X(geom)::numeric, 5) AS lng
    FROM public.dengue_m
    WHERE geom IS NOT NULL;
    """

    return pd.read_sql(query, engine)
