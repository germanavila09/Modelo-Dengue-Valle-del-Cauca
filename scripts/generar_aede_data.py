"""Genera frontend/aede_data.js desde PostGIS para el modulo AEDE."""

from __future__ import annotations

import csv
import json
import os
import subprocess
from collections import defaultdict
from io import StringIO
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "frontend" / "aede_data.js"
PSQL = Path(r"C:\Program Files\PostgreSQL\17\bin\psql.exe")
PERMUTATIONS = 999
SEED = 42


def load_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def query(sql: str) -> list[dict[str, str]]:
    db = load_env()
    env = os.environ.copy()
    env["PGPASSWORD"] = db.get("DB_PASSWORD", "")
    env["PGCLIENTENCODING"] = "UTF8"

    result = subprocess.run(
        [
            str(PSQL),
            "-h",
            db.get("DB_HOST", "localhost"),
            "-p",
            db.get("DB_PORT", "5432"),
            "-U",
            db.get("DB_USER", "postgres"),
            "-d",
            db.get("DB_NAME", "dengue"),
            "-P",
            "pager=off",
            "-A",
            "-F",
            ",",
            "-c",
            f"COPY ({sql}) TO STDOUT WITH CSV HEADER",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    return list(csv.DictReader(StringIO(result.stdout)))


SQL_VALLE_MUN = """
select v."MPIO_CCDGO" as codigo,
       initcap(v."MPIO_CNMBR") as nombre,
       U&"a\\00F1o"::int as anio,
       U&"poblaci\\00F3n"::bigint as poblacion,
       v.conteo_dengue::int as casos,
       round(v.incidencia_dengue::numeric, 1) as incidencia,
       round(ST_Y(ST_PointOnSurface(m.geometry))::numeric, 5) as lat,
       round(ST_X(ST_PointOnSurface(m.geometry))::numeric, 5) as lng
from public.valle_mun v
join public.municipios_valle m
  on m.mpio_ccdgo_full = v."MPIO_CCDGO"
where U&"a\\00F1o" is not null
order by anio, codigo
"""

SQL_GEOJSON = """
select mpio_ccdgo_full as codigo,
       mpio_cnmbr as nombre,
       ST_AsGeoJSON(geometry, 6) as geometry
from public.municipios_valle
order by mpio_ccdgo_full
"""

SQL_NEIGHBORS = """
select a.mpio_ccdgo_full as codigo_a,
       b.mpio_ccdgo_full as codigo_b
from public.municipios_valle a
join public.municipios_valle b
  on a.mpio_ccdgo_full < b.mpio_ccdgo_full
 and ST_DWithin(a.geometry, b.geometry, 0.00001)
order by codigo_a, codigo_b
"""


def build_geojson(rows: list[dict[str, str]]) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [
            {
                "id": str(i),
                "type": "Feature",
                "properties": {
                    "mpio_ccdgo_full": row["codigo"],
                    "mpio_cnmbr": row["nombre"],
                },
                "geometry": json.loads(row["geometry"]),
            }
            for i, row in enumerate(rows)
        ],
    }


def build_weights(codes: list[str], pairs: list[dict[str, str]]) -> np.ndarray:
    idx = {code: i for i, code in enumerate(codes)}
    w = np.zeros((len(codes), len(codes)), dtype=float)
    for pair in pairs:
        a = pair["codigo_a"]
        b = pair["codigo_b"]
        if a in idx and b in idx:
            ia = idx[a]
            ib = idx[b]
            w[ia, ib] = 1.0
            w[ib, ia] = 1.0

    row_sums = w.sum(axis=1)
    for i, total in enumerate(row_sums):
        if total > 0:
            w[i, :] = w[i, :] / total
    return w


def moran_i(z: np.ndarray, w: np.ndarray) -> float:
    denom = float(np.dot(z, z))
    if denom == 0:
        return 0.0
    return float(np.dot(z, w @ z) / denom)


def as_float(value: str | None, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    return float(value)


def as_int(value: str | None, default: int = 0) -> int:
    if value is None or value == "":
        return default
    return int(float(value))


def local_moran(z: np.ndarray, w: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    lag_z = w @ z
    m2 = float(np.mean(z**2)) or 1.0
    return z * lag_z / m2, lag_z


def analyze_year(rows: list[dict[str, str]], codes: list[str], w: np.ndarray, rng: np.random.Generator) -> dict:
    by_code = {row["codigo"]: row for row in rows}
    y = np.array([as_float(by_code[code]["incidencia"]) for code in codes], dtype=float)
    mean = float(y.mean())
    std = float(y.std()) or 1.0
    z = (y - mean) / std

    i_obs = moran_i(z, w)
    sim = np.array([moran_i(rng.permutation(z), w) for _ in range(PERMUTATIONS)], dtype=float)
    p_global = (np.sum(np.abs(sim) >= abs(i_obs)) + 1) / (PERMUTATIONS + 1)
    z_global = (i_obs - float(sim.mean())) / (float(sim.std()) or 1.0)
    lisa_i, lag_z = local_moran(z, w)

    sim_local = np.zeros((PERMUTATIONS, len(codes)), dtype=float)
    for p in range(PERMUTATIONS):
        sim_i, _ = local_moran(rng.permutation(z), w)
        sim_local[p, :] = sim_i
    p_local = (np.sum(np.abs(sim_local) >= np.abs(lisa_i), axis=0) + 1) / (PERMUTATIONS + 1)

    municipios = []
    for pos, code in enumerate(codes):
        row = by_code[code]
        if p_local[pos] < 0.05:
            if z[pos] >= 0 and lag_z[pos] >= 0:
                cluster = "HH"
            elif z[pos] < 0 and lag_z[pos] < 0:
                cluster = "LL"
            elif z[pos] >= 0 and lag_z[pos] < 0:
                cluster = "HL"
            else:
                cluster = "LH"
        else:
            cluster = "NS"

        municipios.append(
            {
                "codigo": code,
                "nombre": row["nombre"],
                "incidencia": round(as_float(row["incidencia"]), 1),
                "casos": as_int(row["casos"]),
                "poblacion": as_int(row["poblacion"]),
                "lisa": cluster,
                "lisa_I": round(float(lisa_i[pos]), 4),
                "lisa_p": round(float(p_local[pos]), 3),
                "lag": round(float(mean + lag_z[pos] * std), 1),
                "pct_acueducto": None,
                "lat": float(row["lat"]),
                "lng": float(row["lng"]),
            }
        )

    return {
        "moran": {
            "I": round(float(i_obs), 4),
            "p": round(float(p_global), 3),
            "sig": bool(p_global < 0.05),
            "z": round(float(z_global), 4),
        },
        "municipios": municipios,
        "sim": [round(float(v), 4) for v in sim.tolist()],
    }


def main() -> None:
    data_rows = query(SQL_VALLE_MUN)
    geo_rows = query(SQL_GEOJSON)
    neighbor_rows = query(SQL_NEIGHBORS)

    codes = [row["codigo"] for row in geo_rows]
    years = sorted({int(row["anio"]) for row in data_rows})
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in data_rows:
        grouped[int(row["anio"])].append(row)

    w = build_weights(codes, neighbor_rows)
    rng = np.random.default_rng(SEED)

    resultados = {}
    moran_serie = []
    for year in years:
        result = analyze_year(grouped[year], codes, w, rng)
        resultados[str(year)] = result
        moran_serie.append(
            {
                "año": year,
                "I": result["moran"]["I"],
                "p": result["moran"]["p"],
                "sig": result["moran"]["sig"],
                "z": result["moran"]["z"],
                "EI": round(-1 / (len(codes) - 1), 5),
            }
        )

    payload = {
        "anios": years,
        "moran_serie": moran_serie,
        "resultados": resultados,
        "geojson": build_geojson(geo_rows),
    }

    OUTPUT.write_text(
        "// aede_data.js - generado por scripts/generar_aede_data.py desde public.valle_mun + public.municipios_valle\n"
        f"var AEDE = {json.dumps(payload, ensure_ascii=False)};\n",
        encoding="utf-8",
    )

    print(f"AEDE guardado: {OUTPUT}")
    print(f"Anios: {', '.join(map(str, years))}")
    print(f"Municipios: {len(codes)}")
    print(f"Vecindades Queen: {len(neighbor_rows)} pares")


if __name__ == "__main__":
    main()
