import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text

from .config import ATTRACTIONS_TABLE, DB_CONFIG, SCHEMA, TABLE


def crear_engine():
    cfg = DB_CONFIG
    url = (
        f"postgresql+psycopg2://{cfg['user']}:{cfg['password']}"
        f"@{cfg['host']}:{cfg['port']}/{cfg['dbname']}"
    )
    return create_engine(url)


def cargar_datos(engine):
    query = text(f'SELECT * FROM "{SCHEMA}"."{TABLE}"')
    return gpd.read_postgis(query, engine, geom_col="geom")


def cargar_atractivos(engine):
    query = text(f'SELECT * FROM "{SCHEMA}"."{ATTRACTIONS_TABLE}"')
    try:
        return gpd.read_postgis(query, engine, geom_col="geom")
    except Exception:
        return pd.read_sql(query, engine)
