"""Validación de solo lectura de dengue_m y auditoría de exposición en terrarIA.

Qué hace
--------
1. Perfila la tabla restringida ``dengue.public.dengue_m`` (calidad, calendario
   epidemiológico, geometrías, duplicados) sin extraer valores individuales.
2. Concilia la fuente con ``terrarIA.public.valle_mun`` y con las tablas
   anónimas ``dengue_semana_municipio`` y ``dengue_celda_anio``.
3. Audita que ``terrarIA`` no contenga columnas, tablas, vistas ni tablas
   foráneas con microdatos de casos.
4. Revisa privilegios: quién puede leer ``dengue_m`` y con qué rol se conecta
   la aplicación.

Garantías
---------
- Ambas conexiones se abren con ``default_transaction_read_only = on``.
- El informe solo contiene conteos, proporciones, nombres de columnas y rangos
  agregados. Nunca escribe identificadores, direcciones, fechas o coordenadas
  de un caso.

Uso
---
    python scripts/validar_dengue_m.py [--salida outputs/validacion_dengue_m]
"""

from __future__ import annotations

import argparse
import datetime as dt
import decimal
import json
import os
import re
import sys
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import DB_CONFIG, SCHEMA, TABLE  # noqa: E402

SOURCE_DB = os.getenv("DENGUE_SOURCE_DB_NAME", "dengue")
TARGET_DB = DB_CONFIG["database"]
GRID_SIZE = float(os.getenv("DENGUE_GRID_SIZE_DEGREES", "0.01"))
MIN_CELL_CASES = int(os.getenv("DENGUE_MIN_CELL_CASES", "5"))

# Nombres de columna que delatan microdatos (se reporta el nombre, nunca el valor).
SENSITIVE_PATTERNS = {
    "identificador": r"(^|_)(num_ide|tip_ide|ide|documento|cedula|id_paciente|historia)(_|$)",
    # Solo nombres de persona; "nombre" a secas es legítimo (municipios, atractivos).
    "nombre": r"(^|_)(pri_nom|seg_nom|pri_ape|seg_ape|apellidos?|nombre_(paciente|persona|caso))(_|$)",
    "direccion": r"(direcc|^dir_|dir_res|barrio|bar_ver|vereda|domicilio)",
    "contacto": r"(telefono|celular|correo|email)",
    "fecha_individual": r"(^|_)(fec_[a-z_]*|fecha_[a-z_]*|ini_sin|fec_nac|nacimiento)(_|$)",
    "coordenada": r"(^|_)(lat|lon|lng|latitud|longitud|x|y|coord[a-z]*)(_|$)",
}
SENSITIVE_RE = {k: re.compile(v, re.I) for k, v in SENSITIVE_PATTERNS.items()}
# Columnas que son legítimas en productos agregados aunque coincidan con un patrón.
ALLOWED_AGGREGATE_COLUMNS = {
    ("public", "dengue_celda_anio", "lat"),  # centro de celda, no del caso
    ("public", "dengue_celda_anio", "lng"),
}


# ── utilidades ────────────────────────────────────────────────────────────────

def _engine(database: str):
    url = URL.create(
        "postgresql+psycopg2",
        username=DB_CONFIG["user"],
        password=DB_CONFIG["password"],
        host=DB_CONFIG["host"],
        port=DB_CONFIG["port"],
        database=database,
    )
    return create_engine(
        url,
        connect_args={
            "client_encoding": "utf8",
            "options": "-c default_transaction_read_only=on -c statement_timeout=600000",
        },
    )


def _json_safe(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if hasattr(value, "item"):
        return value.item()
    return value


def _rows(conn, sql: str, **params) -> list[dict]:
    result = conn.execute(text(sql), params)
    return [{k: _json_safe(v) for k, v in row._mapping.items()} for row in result]


def _one(conn, sql: str, **params) -> dict:
    rows = _rows(conn, sql, **params)
    return rows[0] if rows else {}


def _q(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _classify(column: str) -> list[str]:
    return [k for k, rx in SENSITIVE_RE.items() if rx.search(column)]


class Report:
    def __init__(self):
        self.data: dict = {
            "generado_en": dt.datetime.now(dt.timezone.utc).isoformat(),
            "solo_lectura": True,
            "fuente": f"{SOURCE_DB}.public.dengue_m",
            "destino": TARGET_DB,
            "politica": {"grid_grados": GRID_SIZE, "minimo_casos_celda": MIN_CELL_CASES},
            "checks": {},
            "veredictos": [],
        }

    def put(self, key, value):
        self.data["checks"][key] = value

    def verdict(self, code: str, status: str, message: str):
        assert status in {"OK", "AVISO", "FALLA"}
        self.data["veredictos"].append({"check": code, "estado": status, "detalle": message})


# ── 1. Fuente restringida ─────────────────────────────────────────────────────

def _source_columns(conn) -> list[dict]:
    return _rows(
        conn,
        """
        SELECT column_name, data_type, udt_name
        FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = 'dengue_m'
        ORDER BY ordinal_position
        """,
    )


def _date_expr(col: str, data_type: str) -> str:
    """Expresión SQL que convierte la columna de fecha a date sin exponer valores."""
    c = _q(col)
    if data_type in ("date", "timestamp without time zone", "timestamp with time zone"):
        return f"{c}::date"
    t = f"btrim({c}::text)"
    return (
        f"CASE "
        f"WHEN {t} ~ '^\\d{{4}}-\\d{{2}}-\\d{{2}}' THEN to_date(left({t}, 10), 'YYYY-MM-DD') "
        f"WHEN {t} ~ '^\\d{{2}}/\\d{{2}}/\\d{{4}}' THEN to_date(left({t}, 10), 'DD/MM/YYYY') "
        f"WHEN {t} ~ '^\\d{{4}}/\\d{{2}}/\\d{{2}}' THEN to_date(left({t}, 10), 'YYYY/MM/DD') "
        f"ELSE NULL END"
    )


def validar_fuente(src, report: Report, valle_codes: list[str], valle_wkb: list[str]):
    cols = _source_columns(src)
    if not cols:
        report.verdict("fuente.existe", "FALLA", f"No existe public.dengue_m en la base {SOURCE_DB}.")
        return None
    names = {c["column_name"]: c for c in cols}
    report.put(
        "fuente_columnas",
        [
            {"columna": c["column_name"], "tipo": c["data_type"], "clase_sensible": _classify(c["column_name"])}
            for c in cols
        ],
    )
    required = {"mpio_ccdgo", "año", "semana", "cod_eve", "geom"}
    missing = sorted(required - names.keys())
    if missing:
        report.verdict("fuente.columnas", "FALLA", f"Faltan columnas requeridas: {missing}")
        return None

    size = _one(
        src,
        """SELECT count(*)::bigint AS registros,
                  pg_size_pretty(pg_total_relation_size('public.dengue_m')) AS tamano
           FROM public.dengue_m""",
    )
    report.put("fuente_tamano", size)

    # Completitud de columnas clave (sin leer valores).
    key_cols = [c for c in ("mpio_ccdgo", "año", "semana", "cod_eve", "fec_not", "num_ide_", "direccion", "geom") if c in names]
    nulls = []
    for c in key_cols:
        expr = _q(c)
        empty = f"OR btrim({expr}::text) = ''" if c != "geom" else ""
        r = _one(src, f"SELECT count(*) FILTER (WHERE {expr} IS NULL {empty})::bigint AS vacios FROM public.dengue_m")
        nulls.append({"columna": c, "vacios": r["vacios"], "pct": round(100 * r["vacios"] / max(size["registros"], 1), 2)})
    report.put("fuente_completitud", nulls)

    # Distribuciones básicas.
    report.put(
        "fuente_por_anio_evento",
        _rows(
            src,
            """SELECT "año" AS anio, cod_eve, count(*)::int AS registros
               FROM public.dengue_m GROUP BY 1, 2 ORDER BY 1, 2""",
        ),
    )

    # Códigos municipales.
    codes = _one(
        src,
        """
        SELECT
          count(*) FILTER (WHERE mpio_ccdgo ~ '^[0-9]{5}$')::int AS codigo_5_digitos,
          count(*) FILTER (WHERE mpio_ccdgo ~ '^[0-9]{5}$' AND mpio_ccdgo = ANY(CAST(:codes AS text[])))::int AS codigo_en_valle_mun,
          count(*) FILTER (WHERE mpio_ccdgo ~ '^[0-9]{5}$' AND NOT mpio_ccdgo = ANY(CAST(:codes AS text[])))::int AS codigo_fuera_valle_mun,
          count(*) FILTER (WHERE mpio_ccdgo IS NULL OR mpio_ccdgo !~ '^[0-9]{5}$')::int AS codigo_invalido_o_vacio,
          count(DISTINCT mpio_ccdgo) FILTER (WHERE mpio_ccdgo = ANY(CAST(:codes AS text[])))::int AS municipios_distintos
        FROM public.dengue_m
        """,
        codes=valle_codes,
    )
    report.put("fuente_codigos_municipales", codes)
    if codes["codigo_fuera_valle_mun"]:
        report.verdict("fuente.codigos", "AVISO", f"{codes['codigo_fuera_valle_mun']} registros con código de 5 dígitos que no está en valle_mun.")
    if codes["municipios_distintos"] != len(valle_codes):
        report.verdict("fuente.cobertura", "AVISO", f"La fuente cubre {codes['municipios_distintos']} de {len(valle_codes)} municipios.")

    # Geometrías: tipo, SRID, nulos, (0,0), fuera del Valle y coherencia con el municipio declarado.
    report.put(
        "fuente_geometria_tipo",
        _rows(
            src,
            """SELECT GeometryType(geom) AS tipo, ST_SRID(geom) AS srid, count(*)::int AS registros
               FROM public.dengue_m GROUP BY 1, 2 ORDER BY 3 DESC""",
        ),
    )
    geo = _one(
        src,
        """
        WITH m AS (
            SELECT c AS mpio, ST_SetSRID(ST_GeomFromWKB(decode(w, 'hex')), 4326) AS g
            FROM unnest(CAST(:codes AS text[]), CAST(:wkbs AS text[])) AS t(c, w)
        ),
        valle AS (SELECT ST_Union(g) AS g FROM m),
        p AS (
            SELECT d.mpio_ccdgo,
                   CASE WHEN d.geom IS NULL OR ST_IsEmpty(d.geom) THEN NULL
                        WHEN ST_SRID(d.geom) = 0 THEN ST_SetSRID(d.geom, 4326)
                        ELSE ST_Transform(d.geom, 4326) END AS g
            FROM public.dengue_m d
        )
        SELECT
          count(*) FILTER (WHERE p.g IS NULL)::int AS sin_geometria,
          count(*) FILTER (WHERE p.g IS NOT NULL AND abs(ST_X(p.g)) < 0.001 AND abs(ST_Y(p.g)) < 0.001)::int AS en_cero_cero,
          count(*) FILTER (WHERE p.g IS NOT NULL AND ST_Contains(m.g, p.g))::int AS dentro_municipio_declarado,
          count(*) FILTER (WHERE p.g IS NOT NULL AND m.g IS NOT NULL AND NOT ST_Contains(m.g, p.g)
                           AND ST_Contains(v.g, p.g))::int AS en_otro_municipio_del_valle,
          count(*) FILTER (WHERE p.g IS NOT NULL AND NOT ST_Contains(v.g, p.g)
                           AND NOT (abs(ST_X(p.g)) < 0.001 AND abs(ST_Y(p.g)) < 0.001))::int AS fuera_del_valle,
          count(*) FILTER (WHERE p.g IS NOT NULL AND m.g IS NULL AND ST_Contains(v.g, p.g))::int AS sin_codigo_pero_dentro_valle
        FROM p
        LEFT JOIN m ON m.mpio = p.mpio_ccdgo
        CROSS JOIN valle v
        """,
        codes=valle_codes,
        wkbs=valle_wkb,
    )
    report.put("fuente_geometria_coherencia", geo)
    if geo["en_otro_municipio_del_valle"]:
        report.verdict(
            "fuente.geometria",
            "AVISO",
            f"{geo['en_otro_municipio_del_valle']} puntos caen en un municipio distinto al declarado "
            "(las celdas se agrupan por el código declarado).",
        )

    # Calendario epidemiológico: (año, semana) frente a la semana derivada de fec_not.
    if "fec_not" in names:
        dtype = names["fec_not"]["data_type"]
        d = _date_expr("fec_not", dtype)
        if dtype not in ("date", "timestamp without time zone", "timestamp with time zone"):
            report.put(
                "fec_not_formatos",
                _one(
                    src,
                    """SELECT
                         count(*) FILTER (WHERE btrim(fec_not::text) ~ '^\\d{4}-\\d{2}-\\d{2}')::int AS iso,
                         count(*) FILTER (WHERE btrim(fec_not::text) ~ '^\\d{2}/\\d{2}/\\d{4}')::int AS dd_mm_aaaa,
                         count(*) FILTER (WHERE btrim(fec_not::text) ~ '^\\d{4}/\\d{2}/\\d{2}')::int AS aaaa_mm_dd,
                         count(*) FILTER (WHERE fec_not IS NULL OR btrim(fec_not::text) = '')::int AS vacia
                       FROM public.dengue_m""",
                ),
            )
        cal_cte = f"""
            WITH b AS (
                SELECT "año" AS anio_txt, semana AS semana_txt, {d} AS d
                FROM public.dengue_m
            ),
            w AS (
                SELECT anio_txt, semana_txt, d,
                       d - extract(dow FROM d)::int AS ws
                FROM b
            ),
            e AS (
                SELECT anio_txt, semana_txt, d, ws,
                       extract(year FROM ws + 3)::int AS epi_anio
                FROM w
            ),
            f AS (
                SELECT *,
                       ((ws - (make_date(epi_anio, 1, 4) - extract(dow FROM make_date(epi_anio, 1, 4))::int)) / 7 + 1)::int AS epi_semana,
                       CASE WHEN anio_txt ~ '^[0-9]{{4}}$' THEN anio_txt::int END AS anio,
                       CASE WHEN semana_txt ~ '^[0-9]+$' THEN semana_txt::int END AS semana
                FROM e
            )
        """
        cal = _one(
            src,
            cal_cte
            + """
            SELECT
              count(*)::int AS total,
              count(*) FILTER (WHERE d IS NULL)::int AS fec_not_no_interpretable,
              min(d) AS fec_not_minima,
              max(d) AS fec_not_maxima_fecha_corte,
              count(*) FILTER (WHERE d IS NOT NULL AND anio = epi_anio AND semana = epi_semana)::int AS coincide_anio_y_semana,
              count(*) FILTER (WHERE d IS NOT NULL AND semana = epi_semana AND anio <> epi_anio)::int AS misma_semana_otro_anio,
              count(*) FILTER (WHERE d IS NOT NULL AND anio = extract(year FROM d)::int AND anio <> epi_anio)::int AS anio_calendario_en_vez_de_epi,
              count(*) FILTER (WHERE d IS NOT NULL AND semana IS NOT NULL AND semana <> epi_semana)::int AS semana_distinta,
              count(*) FILTER (WHERE d IS NOT NULL AND d > CURRENT_DATE)::int AS fecha_futura
            FROM f
            """,
        )
        report.put("calendario_epidemiologico", cal)
        report.put(
            "semana_53",
            _rows(
                src,
                cal_cte
                + """
                SELECT anio, epi_anio, epi_semana, count(*)::int AS registros
                FROM f
                WHERE semana = 53
                GROUP BY 1, 2, 3 ORDER BY 1, 2, 3
                """,
            ),
        )
        report.put(
            "desfase_anio_por_frontera",
            _rows(
                src,
                cal_cte
                + """
                SELECT anio AS anio_declarado, semana AS semana_declarada, epi_anio, epi_semana, count(*)::int AS registros
                FROM f
                WHERE d IS NOT NULL AND anio IS NOT NULL AND anio <> epi_anio
                GROUP BY 1, 2, 3, 4 ORDER BY 1, 2, 3, 4
                """,
            ),
        )
        mismatch = cal["total"] - cal["coincide_anio_y_semana"] - cal["fec_not_no_interpretable"]
        if mismatch:
            report.verdict(
                "fuente.calendario",
                "AVISO",
                f"{mismatch} registros tienen (año, semana) distinto de la semana epidemiológica de fec_not; "
                f"{cal['misma_semana_otro_anio']} solo difieren en el año (frontera de año).",
            )
        else:
            report.verdict("fuente.calendario", "OK", "(año, semana) coincide con la semana epidemiológica de fec_not.")
    else:
        report.verdict("fuente.calendario", "AVISO", "No hay columna fec_not para validar el calendario.")

    # Duplicados (se agrupa dentro de la base; solo salen conteos).
    if "num_ide_" in names:
        key = ["num_ide_"] + [c for c in ("tip_ide_", "cod_eve", "fec_not") if c in names]
        key_sql = ", ".join(_q(c) for c in key)
        dup = _one(
            src,
            f"""
            SELECT count(*)::int AS grupos_duplicados, coalesce(sum(n - 1), 0)::int AS registros_sobrantes
            FROM (SELECT count(*) AS n FROM public.dengue_m
                  WHERE num_ide_ IS NOT NULL AND btrim(num_ide_::text) <> ''
                  GROUP BY {key_sql} HAVING count(*) > 1) s
            """,
        )
        dup["llave"] = key
        same_year = _one(
            src,
            """
            SELECT count(*)::int AS personas_evento_anio_repetido, coalesce(sum(n - 1), 0)::int AS notificaciones_extra
            FROM (SELECT count(*) AS n FROM public.dengue_m
                  WHERE num_ide_ IS NOT NULL AND btrim(num_ide_::text) <> ''
                  GROUP BY num_ide_, cod_eve, "año" HAVING count(*) > 1) s
            """,
        )
        report.put("duplicados", {"exactos": dup, "misma_persona_evento_anio": same_year})
        if dup["registros_sobrantes"]:
            report.verdict("fuente.duplicados", "AVISO", f"{dup['registros_sobrantes']} registros duplicados por {key}.")
        else:
            report.verdict("fuente.duplicados", "OK", f"Sin duplicados exactos por {key}.")

    return names


# ── 2. Conciliación con terrarIA ──────────────────────────────────────────────

WEEKLY_SQL = """
    SELECT mpio_ccdgo, "año"::int AS anio, semana::int AS semana, cod_eve, COUNT(*)::int AS casos
    FROM public.dengue_m
    WHERE mpio_ccdgo ~ '^[0-9]{5}$' AND "año" ~ '^[0-9]{4}$'
      AND semana ~ '^[0-9]+$' AND semana::int BETWEEN 1 AND 53
    GROUP BY 1, 2, 3, 4
"""


def conciliar(src, tgt, report: Report, tgt_tables: set[str]):
    source_weekly = pd.read_sql(text(WEEKLY_SQL), src)
    src_annual = source_weekly.groupby(["mpio_ccdgo", "anio"], as_index=False)["casos"].sum()

    valle = pd.read_sql(
        text(f'SELECT "MPIO_CCDGO"::text AS mpio_ccdgo, anio::int AS anio, conteo_dengue::int AS valle_mun '
             f'FROM {_q(SCHEMA)}.{_q(TABLE)}'),
        tgt,
    )
    annual = valle.merge(src_annual, on=["mpio_ccdgo", "anio"], how="outer").fillna(0)
    annual["diferencia"] = annual["casos"] - annual["valle_mun"]
    diffs = annual[annual["diferencia"] != 0]
    report.put(
        "conciliacion_valle_mun",
        {
            "casos_fuente_codigo_valido": int(source_weekly["casos"].sum()),
            "casos_valle_mun": int(valle["valle_mun"].sum()),
            "pares_municipio_anio": int(len(annual)),
            "pares_con_diferencia": int(len(diffs)),
            "detalle_diferencias": diffs.head(50).to_dict(orient="records"),
        },
    )
    if len(diffs):
        report.verdict("conciliacion.valle_mun", "AVISO", f"{len(diffs)} pares municipio-año no coinciden con valle_mun.")
    else:
        report.verdict("conciliacion.valle_mun", "OK", "Los conteos anuales coinciden exactamente con valle_mun.")

    if "dengue_semana_municipio" in tgt_tables:
        published = pd.read_sql(
            text("SELECT mpio_ccdgo, anio::int AS anio, semana::int AS semana, cod_eve, casos::int AS casos "
                 "FROM public.dengue_semana_municipio"),
            tgt,
        )
        cmp = source_weekly.merge(published, on=["mpio_ccdgo", "anio", "semana", "cod_eve"], how="outer",
                                  suffixes=("_fuente", "_publicado"), indicator=True)
        distintos = cmp[(cmp["_merge"] != "both") | (cmp["casos_fuente"] != cmp["casos_publicado"])]
        small = published["casos"]
        report.put(
            "semana_municipio",
            {
                "filas": int(len(published)),
                "casos": int(published["casos"].sum()),
                "filas_distintas_de_la_fuente": int(len(distintos)),
                "distribucion_conteos": {
                    "1": int((small == 1).sum()),
                    "2": int((small == 2).sum()),
                    "3_4": int(small.between(3, 4).sum()),
                    "5_mas": int((small >= 5).sum()),
                },
            },
        )
        if len(distintos):
            report.verdict("publicado.semana", "AVISO", f"{len(distintos)} filas semanales no coinciden con la fuente actual (¿migración desactualizada?).")
        else:
            report.verdict("publicado.semana", "OK", "dengue_semana_municipio reproduce exactamente la fuente.")
    else:
        report.verdict("publicado.semana", "FALLA", "No existe public.dengue_semana_municipio en terrarIA.")

    if "dengue_celda_anio" in tgt_tables:
        cells = _one(
            tgt,
            """
            SELECT count(*)::int AS celdas,
                   coalesce(sum(casos), 0)::int AS casos,
                   min(casos)::int AS minimo_casos,
                   count(*) FILTER (WHERE casos < :minimum)::int AS bajo_umbral,
                   count(*) FILTER (WHERE abs(((lat - :half) / :grid) - round((lat - :half) / :grid)) > 1e-6
                                     OR abs(((lng - :half) / :grid) - round((lng - :half) / :grid)) > 1e-6)::int AS fuera_de_malla,
                   count(DISTINCT (lat, lng))::int AS ubicaciones_distintas
            FROM public.dengue_celda_anio
            """,
            minimum=MIN_CELL_CASES,
            grid=GRID_SIZE,
            half=GRID_SIZE / 2,
        )
        total_valid = int(source_weekly["casos"].sum())
        cells["pct_casos_publicados_en_celdas"] = round(100 * cells["casos"] / max(total_valid, 1), 2)
        report.put("celda_anio", cells)
        if cells["bajo_umbral"] or cells["fuera_de_malla"]:
            report.verdict("publicado.celdas", "FALLA",
                           f"{cells['bajo_umbral']} celdas bajo el umbral y {cells['fuera_de_malla']} fuera de la malla.")
        else:
            report.verdict("publicado.celdas", "OK",
                           f"Todas las celdas tienen ≥{MIN_CELL_CASES} casos y coordenadas de centro de malla.")
    else:
        report.verdict("publicado.celdas", "FALLA", "No existe public.dengue_celda_anio en terrarIA.")

    if "dengue_derivados_metadata" in tgt_tables:
        report.put("metadata", _one(tgt, "SELECT * FROM public.dengue_derivados_metadata WHERE id = 1"))


# ── 3. Exposición en terrarIA ─────────────────────────────────────────────────

def auditar_destino(tgt, report: Report) -> set[str]:
    cols = _rows(
        tgt,
        """
        SELECT c.table_schema, c.table_name, c.column_name, c.data_type, t.table_type
        FROM information_schema.columns c
        JOIN information_schema.tables t USING (table_schema, table_name)
        WHERE c.table_schema NOT IN ('pg_catalog', 'information_schema', 'tiger', 'topology')
          AND c.table_name NOT IN ('spatial_ref_sys', 'geometry_columns', 'geography_columns')
        """,
    )
    flagged = []
    for c in cols:
        classes = _classify(c["column_name"])
        if classes and (c["table_schema"], c["table_name"], c["column_name"]) not in ALLOWED_AGGREGATE_COLUMNS:
            flagged.append({**{k: c[k] for k in ("table_schema", "table_name", "column_name", "table_type")}, "clase": classes})
    report.put("destino_columnas_sospechosas", flagged)

    # Tablas con geometrías de tipo punto (posibles casos individuales).
    points = _rows(
        tgt,
        """SELECT f_table_schema AS esquema, f_table_name AS tabla, f_geometry_column AS columna, type AS tipo, srid
           FROM public.geometry_columns
           WHERE upper(type) IN ('POINT', 'MULTIPOINT', 'GEOMETRY')""",
    )
    for p in points:
        p["filas"] = _one(tgt, f"SELECT count(*)::bigint AS n FROM {_q(p['esquema'])}.{_q(p['tabla'])}")["n"]
    report.put("destino_tablas_con_puntos", points)

    tables = _rows(
        tgt,
        """SELECT table_schema, table_name, table_type FROM information_schema.tables
           WHERE table_schema NOT IN ('pg_catalog', 'information_schema')""",
    )
    dengue_like = [t for t in tables if re.search(r"dengue_m$|sivigila|microdato|caso_ind", t["table_name"], re.I)]
    report.put("destino_tablas_tipo_microdato", dengue_like)

    views = _rows(
        tgt,
        """SELECT schemaname, viewname FROM pg_views
           WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
             AND (definition ~* 'dengue_m[^a-z_]' OR definition ~* 'num_ide|direccion|fec_not|dblink')""",
    )
    report.put("destino_vistas_que_leen_microdatos", views)

    foreign = _rows(
        tgt,
        """SELECT n.nspname AS esquema, c.relname AS tabla, s.srvname AS servidor
           FROM pg_foreign_table ft
           JOIN pg_class c ON c.oid = ft.ftrelid
           JOIN pg_namespace n ON n.oid = c.relnamespace
           JOIN pg_foreign_server s ON s.oid = ft.ftserver""",
    )
    extensions = [r["extname"] for r in _rows(tgt, "SELECT extname FROM pg_extension WHERE extname IN ('dblink', 'postgres_fdw')")]
    report.put("destino_acceso_remoto", {"tablas_foraneas": foreign, "extensiones": extensions})

    strong = [f for f in flagged if set(f["clase"]) & {"identificador", "nombre", "direccion", "contacto"}]
    weak = [f for f in flagged if f not in strong]
    if weak:
        report.verdict(
            "destino.columnas_revisar",
            "AVISO",
            "Columnas con nombre de fecha o coordenada; confirmar que son agregadas: "
            + ", ".join(f"{f['table_schema']}.{f['table_name']}.{f['column_name']}" for f in weak[:15]),
        )
    problems = []
    if strong:
        problems.append(f"{len(strong)} columnas de identificación, nombre, dirección o contacto")
    if dengue_like:
        problems.append(f"{len(dengue_like)} tablas tipo microdato")
    if views:
        problems.append(f"{len(views)} vistas que leen microdatos")
    if foreign or extensions:
        problems.append("acceso remoto (FDW/dblink) habilitado")
    if problems:
        report.verdict("destino.exposicion", "FALLA", "terrarIA contiene: " + "; ".join(problems) + ".")
    else:
        report.verdict("destino.exposicion", "OK", "terrarIA no contiene columnas, tablas, vistas ni enlaces con microdatos de casos.")
    if any(p["tabla"] not in ("atractivos_turisticos",) for p in points):
        report.verdict("destino.puntos", "AVISO",
                       "Hay tablas con geometría de punto; confirmar que ninguna representa casos: "
                       + ", ".join(f"{p['esquema']}.{p['tabla']}" for p in points))
    return {t["table_name"] for t in tables if t["table_schema"] == "public"}


# ── 4. Privilegios ────────────────────────────────────────────────────────────

def auditar_privilegios(src, tgt, report: Report):
    me = _one(src, "SELECT current_user AS rol, rolsuper AS superusuario FROM pg_roles WHERE rolname = current_user")
    report.put("rol_aplicacion", me)
    grants = _rows(
        src,
        """SELECT grantee, string_agg(privilege_type, ',' ORDER BY privilege_type) AS privilegios
           FROM information_schema.role_table_grants
           WHERE table_schema = 'public' AND table_name = 'dengue_m'
           GROUP BY grantee ORDER BY grantee""",
    )
    report.put("permisos_dengue_m", grants)
    connect_public = _one(
        src,
        """SELECT has_database_privilege('public', current_database(), 'CONNECT') AS public_puede_conectar""",
    )
    report.put("base_fuente_connect_public", connect_public)
    readers = _rows(
        src,
        """SELECT r.rolname, r.rolsuper, r.rolcanlogin
           FROM pg_roles r
           WHERE r.rolcanlogin AND (r.rolsuper OR has_table_privilege(r.oid, 'public.dengue_m', 'SELECT'))
           ORDER BY 1""",
    )
    report.put("roles_que_leen_dengue_m", readers)
    if me.get("superusuario"):
        report.verdict("privilegios.rol_app", "AVISO",
                       f"La aplicación se conecta como superusuario ({me['rol']}): puede leer dengue_m desde el chatbot o el frontend. "
                       "Usar un rol de solo lectura sin CONNECT sobre la base dengue.")
    if any(g["grantee"] == "PUBLIC" for g in grants):
        report.verdict("privilegios.public", "FALLA", "PUBLIC tiene privilegios sobre dengue_m.")


# ── main ──────────────────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--salida", default=str(ROOT / "outputs" / "validacion_dengue_m"))
    args = parser.parse_args(argv)
    out = Path(args.salida)
    out.mkdir(parents=True, exist_ok=True)

    report = Report()
    src_engine, tgt_engine = _engine(SOURCE_DB), _engine(TARGET_DB)
    try:
        with src_engine.connect() as src, tgt_engine.connect() as tgt:
            valle = _rows(
                tgt,
                f"""SELECT DISTINCT ON ("MPIO_CCDGO") "MPIO_CCDGO"::text AS mpio,
                           encode(ST_AsBinary(ST_Transform(ST_MakeValid(geom), 4326)), 'hex') AS wkb
                    FROM {_q(SCHEMA)}.{_q(TABLE)} ORDER BY "MPIO_CCDGO", anio DESC""",
            )
            codes = [v["mpio"] for v in valle]
            wkbs = [v["wkb"] for v in valle]
            tgt_tables = auditar_destino(tgt, report)
            validar_fuente(src, report, codes, wkbs)
            conciliar(src, tgt, report, tgt_tables)
            auditar_privilegios(src, tgt, report)
    finally:
        src_engine.dispose()
        tgt_engine.dispose()

    path = out / "validacion_dengue_m.json"
    path.write_text(json.dumps(report.data, ensure_ascii=False, indent=2, default=_json_safe), encoding="utf-8")
    print(f"Informe agregado: {path}")
    for v in report.data["veredictos"]:
        print(f"[{v['estado']:5}] {v['check']}: {v['detalle']}")
    return 1 if any(v["estado"] == "FALLA" for v in report.data["veredictos"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
