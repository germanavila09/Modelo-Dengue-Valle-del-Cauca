"""Publica derivados anónimos de dengue_m en la base del observatorio.

La tabla fuente permanece en la base restringida ``dengue``. Este proceso solo
extrae agregados; nunca lee ni copia identificadores, direcciones o fechas
individuales hacia ``terrarIA``.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import DB_CONFIG  # noqa: E402
from src.db import crear_engine  # noqa: E402


SOURCE_DB = os.getenv("DENGUE_SOURCE_DB_NAME", "dengue")
GRID_SIZE = float(os.getenv("DENGUE_GRID_SIZE_DEGREES", "0.01"))
MIN_CELL_CASES = int(os.getenv("DENGUE_MIN_CELL_CASES", "5"))


def _source_engine():
    return create_engine(
        URL.create(
            "postgresql+psycopg2",
            username=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=SOURCE_DB,
        )
    )


def _load_aggregates(source_engine):
    weekly_query = text(
        """
        SELECT mpio_ccdgo, "año"::int AS anio, semana::int AS semana,
               cod_eve, COUNT(*)::int AS casos
        FROM public.dengue_m
        WHERE mpio_ccdgo ~ '^[0-9]{5}$'
          AND "año" ~ '^[0-9]{4}$'
          AND semana ~ '^[0-9]+$'
          AND semana::int BETWEEN 1 AND 53
        GROUP BY mpio_ccdgo, "año"::int, semana::int, cod_eve
        ORDER BY anio, semana, mpio_ccdgo, cod_eve
        """
    )
    cells_query = text(
        """
        WITH cells AS (
            SELECT mpio_ccdgo, "año"::int AS anio,
                   (floor(ST_Y(geom) / :grid_size) * :grid_size + :half_grid) AS lat,
                   (floor(ST_X(geom) / :grid_size) * :grid_size + :half_grid) AS lng,
                   COUNT(*)::int AS casos
            FROM public.dengue_m
            WHERE mpio_ccdgo ~ '^[0-9]{5}$'
              AND "año" ~ '^[0-9]{4}$'
              AND geom IS NOT NULL
              AND ST_X(geom) BETWEEN -78 AND -75
              AND ST_Y(geom) BETWEEN 3 AND 6
            GROUP BY mpio_ccdgo, "año"::int,
                     floor(ST_Y(geom) / :grid_size), floor(ST_X(geom) / :grid_size)
        )
        SELECT mpio_ccdgo, anio, round(lat::numeric, 6) AS lat,
               round(lng::numeric, 6) AS lng, casos
        FROM cells
        WHERE casos >= :min_cases
        ORDER BY anio, mpio_ccdgo, lat, lng
        """
    )
    params = {
        "grid_size": GRID_SIZE,
        "half_grid": GRID_SIZE / 2,
        "min_cases": MIN_CELL_CASES,
    }
    weekly = pd.read_sql(weekly_query, source_engine)
    cells = pd.read_sql(cells_query, source_engine, params=params)
    return weekly, cells


def _validate(weekly, cells):
    if weekly.empty:
        raise ValueError("La fuente no produjo agregados semanales.")
    if cells.empty:
        raise ValueError("La política de anonimización suprimió todas las celdas.")
    sensitive = {"num_ide_", "direccion", "fec_not", "geom", "x", "y"}
    leaked = sensitive.intersection(weekly.columns).union(sensitive.intersection(cells.columns))
    if leaked:
        raise ValueError(f"Se detectaron columnas sensibles en los derivados: {sorted(leaked)}")
    if (cells["casos"] < MIN_CELL_CASES).any():
        raise ValueError("Hay celdas por debajo del umbral mínimo de publicación.")


def _records(frame):
    return [
        {key: value.item() if hasattr(value, "item") else value for key, value in row.items()}
        for row in frame.to_dict(orient="records")
    ]


def _publish(target_engine, weekly, cells):
    ddl = """
    CREATE TABLE IF NOT EXISTS public.dengue_semana_municipio (
        mpio_ccdgo varchar(5) NOT NULL CHECK (mpio_ccdgo ~ '^[0-9]{5}$'),
        anio smallint NOT NULL CHECK (anio BETWEEN 2010 AND 2100),
        semana smallint NOT NULL CHECK (semana BETWEEN 1 AND 53),
        cod_eve varchar(10) NOT NULL,
        casos integer NOT NULL CHECK (casos > 0),
        PRIMARY KEY (mpio_ccdgo, anio, semana, cod_eve)
    );
    CREATE INDEX IF NOT EXISTS idx_dengue_semana_anio
        ON public.dengue_semana_municipio (anio, semana);

    CREATE TABLE IF NOT EXISTS public.dengue_celda_anio (
        mpio_ccdgo varchar(5) NOT NULL CHECK (mpio_ccdgo ~ '^[0-9]{5}$'),
        anio smallint NOT NULL CHECK (anio BETWEEN 2010 AND 2100),
        lat numeric(9,6) NOT NULL CHECK (lat BETWEEN 3 AND 6),
        lng numeric(9,6) NOT NULL CHECK (lng BETWEEN -78 AND -75),
        casos integer NOT NULL CHECK (casos >= 5),
        PRIMARY KEY (mpio_ccdgo, anio, lat, lng)
    );
    CREATE INDEX IF NOT EXISTS idx_dengue_celda_anio
        ON public.dengue_celda_anio (anio, mpio_ccdgo);

    CREATE TABLE IF NOT EXISTS public.dengue_derivados_metadata (
        id smallint PRIMARY KEY CHECK (id = 1),
        actualizado_en timestamptz NOT NULL,
        fuente_base text NOT NULL,
        grid_grados numeric NOT NULL,
        minimo_casos_celda integer NOT NULL CHECK (minimo_casos_celda >= 5),
        casos_semanales integer NOT NULL,
        casos_publicados_celdas integer NOT NULL
    );
    """
    insert_weekly = text(
        """INSERT INTO public.dengue_semana_municipio
        (mpio_ccdgo, anio, semana, cod_eve, casos)
        VALUES (:mpio_ccdgo, :anio, :semana, :cod_eve, :casos)"""
    )
    insert_cells = text(
        """INSERT INTO public.dengue_celda_anio
        (mpio_ccdgo, anio, lat, lng, casos)
        VALUES (:mpio_ccdgo, :anio, :lat, :lng, :casos)"""
    )
    with target_engine.begin() as connection:
        connection.exec_driver_sql(ddl)
        connection.execute(text("DELETE FROM public.dengue_semana_municipio"))
        connection.execute(text("DELETE FROM public.dengue_celda_anio"))
        connection.execute(insert_weekly, _records(weekly))
        connection.execute(insert_cells, _records(cells))
        connection.execute(
            text(
                """INSERT INTO public.dengue_derivados_metadata
                (id, actualizado_en, fuente_base, grid_grados, minimo_casos_celda,
                 casos_semanales, casos_publicados_celdas)
                VALUES (1, now(), :source, :grid, :minimum, :weekly_cases, :cell_cases)
                ON CONFLICT (id) DO UPDATE SET
                    actualizado_en = EXCLUDED.actualizado_en,
                    fuente_base = EXCLUDED.fuente_base,
                    grid_grados = EXCLUDED.grid_grados,
                    minimo_casos_celda = EXCLUDED.minimo_casos_celda,
                    casos_semanales = EXCLUDED.casos_semanales,
                    casos_publicados_celdas = EXCLUDED.casos_publicados_celdas"""
            ),
            {
                "source": SOURCE_DB,
                "grid": GRID_SIZE,
                "minimum": MIN_CELL_CASES,
                "weekly_cases": int(weekly["casos"].sum()),
                "cell_cases": int(cells["casos"].sum()),
            },
        )


def main():
    if not 0.005 <= GRID_SIZE <= 0.05:
        raise ValueError("DENGUE_GRID_SIZE_DEGREES debe estar entre 0.005 y 0.05.")
    if MIN_CELL_CASES < 5:
        raise ValueError("DENGUE_MIN_CELL_CASES no puede ser menor que 5.")

    source_engine = _source_engine()
    target_engine = crear_engine()
    try:
        weekly, cells = _load_aggregates(source_engine)
        _validate(weekly, cells)
        _publish(target_engine, weekly, cells)
    finally:
        source_engine.dispose()
        target_engine.dispose()

    print(
        f"Publicados {len(weekly):,} agregados semanales ({weekly['casos'].sum():,} casos) "
        f"y {len(cells):,} celdas anónimas ({cells['casos'].sum():,} casos)."
    )
    print("No se copiaron identificadores, direcciones, fechas individuales ni geometrías de casos.")


if __name__ == "__main__":
    main()
