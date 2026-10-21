import geopandas as gpd
import pandas as pd
import re
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from .config import DB_CONFIG, SCHEMA, TABLE


_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class FuenteDatosNoDisponibleError(RuntimeError):
    """Una fuente opcional no existe en la base configurada."""


def _es_tabla_inexistente(exc):
    """Reconoce el SQLSTATE de PostgreSQL para una tabla inexistente."""
    current = exc
    visited = set()
    while current is not None and id(current) not in visited:
        visited.add(id(current))
        original = getattr(current, "orig", None)
        sqlstate = (
            getattr(current, "pgcode", None)
            or getattr(current, "sqlstate", None)
            or getattr(original, "pgcode", None)
            or getattr(original, "sqlstate", None)
        )
        if sqlstate == "42P01":
            return True
        current = getattr(current, "__cause__", None) or getattr(current, "__context__", None)
    return False


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
        anio,
        poblacion,
        conteo_dengue,
        incidencia_dengue,
        geom
    FROM {tabla}
    ORDER BY anio, "MPIO_CNMBR";
    """

    return gpd.read_postgis(query, engine, geom_col="geom")


def cargar_puntos_calor(engine=None):
    if engine is None:
        engine = crear_engine()

    query = """
    SELECT
        anio::text AS anio,
        mpio_ccdgo,
        lat,
        lng,
        casos AS peso
    FROM public.dengue_celda_anio
    ORDER BY anio, mpio_ccdgo, lat, lng;
    """

    try:
        return pd.read_sql(query, engine)
    except (SQLAlchemyError, pd.errors.DatabaseError) as exc:
        if _es_tabla_inexistente(exc):
            raise FuenteDatosNoDisponibleError(
                "La tabla anonimizada public.dengue_celda_anio no existe; "
                "ejecuta scripts/migrar_dengue_anonimizado.py."
            ) from exc
        raise
