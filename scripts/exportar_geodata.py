"""
exportar_geodata.py — Geodata Salud Observatory
=================================================
Exporta datos reales desde PostgreSQL/PostGIS a frontend/geodata-data.js
como un archivo JS autocontenido con todas las variables y helpers.

Uso:
    python scripts/exportar_geodata.py
"""

import json
import sys
import warnings
from datetime import date
from pathlib import Path

# ── Path setup ───────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import geopandas as gpd
import pandas as pd
from sqlalchemy import text

warnings.filterwarnings("ignore", message="Geometry is in a geographic CRS")

from src.db import crear_engine

# ── Destino ──────────────────────────────────────────────────────────────────
DEST = ROOT / "frontend" / "geodata-data.js"


# ─── 1. Conexión ─────────────────────────────────────────────────────────────
print("Conectando a PostgreSQL…")
engine = crear_engine()

# ─── 2. UPDATE: redondear decimales en valle_mun ─────────────────────────────
print("Redondeando decimales en valle_mun…")
with engine.begin() as conn:
    conn.execute(text("""
        UPDATE public.valle_mun
        SET
            conteo_dengue     = ROUND(conteo_dengue),
            incidencia_dengue = ROUND(incidencia_dengue::numeric, 1)
        WHERE conteo_dengue IS NOT NULL
           OR incidencia_dengue IS NOT NULL
    """))
print("  UPDATE completado.")

# ─── 3. GeoJSON desde municipios_valle ───────────────────────────────────────
print("Leyendo geometrías de municipios_valle…")
gdf_geo = gpd.read_postgis(
    """
    SELECT
        mpio_ccdgo_full                           AS "MPIO_CCDGO",
        INITCAP(LOWER(mpio_cnmbr))                AS "MPIO_CNMBR",
        geometry
    FROM public.municipios_valle
    WHERE mpio_ccdgo_full IS NOT NULL
      AND geometry IS NOT NULL
    ORDER BY mpio_ccdgo_full
    """,
    engine,
    geom_col="geometry",
)

# Reproyectar a WGS84 (ya está en 4326, pero por si acaso)
if gdf_geo.crs is None or gdf_geo.crs.to_epsg() != 4326:
    print(f"  Reproyectando de EPSG:{gdf_geo.crs.to_epsg()} a EPSG:4326…")
    gdf_geo = gdf_geo.to_crs(4326)

# Simplificar geometría
gdf_geo["geometry"] = gdf_geo["geometry"].simplify(0.0001, preserve_topology=True)
print(f"  {len(gdf_geo)} municipios cargados.")

# ─── 4. Centroides ───────────────────────────────────────────────────────────
centroids = gdf_geo.copy()
centroids["centroid"] = centroids["geometry"].centroid
centroids["lat"] = centroids["centroid"].y.round(6)
centroids["lng"] = centroids["centroid"].x.round(6)
centroid_map = centroids.set_index("MPIO_CCDGO")[["lat", "lng"]].to_dict("index")

# ─── 5. GeoJSON serializado ──────────────────────────────────────────────────
geojson_obj = json.loads(gdf_geo.to_json())
# Inyectar lat/lng en properties de cada feature
for feat in geojson_obj.get("features", []):
    code = feat["properties"].get("MPIO_CCDGO")
    if code and code in centroid_map:
        feat["properties"]["lat"] = centroid_map[code]["lat"]
        feat["properties"]["lng"] = centroid_map[code]["lng"]

# ─── 6. Leer valle_mun ───────────────────────────────────────────────────────
print("Leyendo datos de valle_mun…")
df = pd.read_sql(
    text("""
    SELECT
        "MPIO_CCDGO",
        INITCAP(LOWER("MPIO_CNMBR"))            AS "MPIO_CNMBR",
        año                                      AS ano,
        COALESCE(conteo_dengue, 0)              AS conteo_dengue,
        COALESCE(incidencia_dengue::float, 0.0) AS incidencia_dengue,
        COALESCE(población, 0)                  AS poblacion
    FROM public.valle_mun
    ORDER BY año, "MPIO_CCDGO"
    """),
    engine,
)
print(f"  {len(df)} registros cargados.")

# ─── 7. RISK_MAP: promedio incidencia 2022-2024 ───────────────────────────────
print("Calculando RISK_MAP…")
df_risk = df[df["ano"].between(2022, 2024)].copy()
risk_agg = (
    df_risk.groupby("MPIO_CCDGO")
    .agg(
        inc_prom=("incidencia_dengue", "mean"),
        mpio_cnmbr=("MPIO_CNMBR", "first"),
    )
    .reset_index()
)

def nivel_riesgo(inc):
    if inc >= 600:
        return "Crítico"
    elif inc >= 300:
        return "Alto"
    elif inc >= 100:
        return "Medio"
    else:
        return "Bajo"

risk_agg["nivel"] = risk_agg["inc_prom"].apply(nivel_riesgo)
risk_agg["inc_prom"] = risk_agg["inc_prom"].round(1)

RISK_MAP = {
    row["MPIO_CCDGO"]: {
        "nivel":      row["nivel"],
        "inc_prom":   row["inc_prom"],
        "mpio_cnmbr": row["mpio_cnmbr"],
    }
    for _, row in risk_agg.iterrows()
}

# ─── 8. DELTA_MAP: cambio 2023 → 2024 ────────────────────────────────────────
print("Calculando DELTA_MAP…")
df_2023 = df[df["ano"] == 2023].set_index("MPIO_CCDGO")[["incidencia_dengue"]].rename(columns={"incidencia_dengue": "inc_2023"})
df_2024 = df[df["ano"] == 2024].set_index("MPIO_CCDGO")[["incidencia_dengue"]].rename(columns={"incidencia_dengue": "inc_2024"})
df_delta = df_2023.join(df_2024, how="outer").fillna(0)
df_delta["delta_pct"] = df_delta.apply(
    lambda r: round((r["inc_2024"] - r["inc_2023"]) / r["inc_2023"] * 100, 1)
    if r["inc_2023"] > 0 else 0.0,
    axis=1,
)

DELTA_MAP = {
    code: {
        "delta_pct": float(row["delta_pct"]),
        "inc_2023":  float(row["inc_2023"]),
        "inc_2024":  float(row["inc_2024"]),
    }
    for code, row in df_delta.iterrows()
}

# ─── 9. MUN_CATALOG ──────────────────────────────────────────────────────────
print("Construyendo MUN_CATALOG…")
# Población más reciente disponible por municipio
pop_latest = (
    df.sort_values("ano", ascending=False)
    .drop_duplicates("MPIO_CCDGO")
    .set_index("MPIO_CCDGO")["poblacion"]
    .to_dict()
)
# Nombre más reciente
name_latest = (
    df.sort_values("ano", ascending=False)
    .drop_duplicates("MPIO_CCDGO")
    .set_index("MPIO_CCDGO")["MPIO_CNMBR"]
    .to_dict()
)

MUN_CATALOG = sorted(
    [
        {
            "code": code,
            "name": name_latest.get(code, gdf_geo.loc[gdf_geo["MPIO_CCDGO"] == code, "MPIO_CNMBR"].iloc[0] if len(gdf_geo[gdf_geo["MPIO_CCDGO"] == code]) > 0 else code),
            "lat":  centroid_map[code]["lat"] if code in centroid_map else None,
            "lng":  centroid_map[code]["lng"] if code in centroid_map else None,
            "pop":  int(pop_latest.get(code, 0)),
        }
        for code in centroid_map
    ],
    key=lambda x: x["name"],
)

# ─── 10. GEODATA records ─────────────────────────────────────────────────────
print("Construyendo GEODATA…")
GEODATA = []
for _, row in df.iterrows():
    code = row["MPIO_CCDGO"]
    lat  = centroid_map[code]["lat"] if code in centroid_map else None
    lng  = centroid_map[code]["lng"] if code in centroid_map else None
    GEODATA.append({
        "MPIO_CCDGO":        str(code),
        "MPIO_CNMBR":        str(row["MPIO_CNMBR"]),
        "año":               int(row["ano"]),
        "conteo_dengue":     int(row["conteo_dengue"]),
        "incidencia_dengue": round(float(row["incidencia_dengue"]), 1),
        "población":         int(row["poblacion"]),
        "lat":               lat,
        "lng":               lng,
    })

# ─── 11. YEARS ───────────────────────────────────────────────────────────────
YEARS = sorted(df["ano"].unique().tolist())

# ─── 12. Escribir geodata-data.js ────────────────────────────────────────────
today = date.today().strftime("%Y-%m-%d")
print(f"Escribiendo {DEST}…")

js_parts = []

# Header
js_parts.append(f"""\
// ─── GEODATA SALUD — Datos reales · PostgreSQL/PostGIS ───────────────────────
// Generado por scripts/exportar_geodata.py — {today}

var DATA_SOURCE = 'postgresql';
""")

# YEARS
js_parts.append(f"var YEARS = {json.dumps(YEARS, ensure_ascii=False)};\n")

# GEO_MUNI
js_parts.append(f"\nvar GEO_MUNI = {json.dumps(geojson_obj, ensure_ascii=False)};\n")

# MUN_CATALOG
js_parts.append(f"\nvar MUN_CATALOG = {json.dumps(MUN_CATALOG, ensure_ascii=False, indent=2)};\n")

# GEODATA
js_parts.append(f"\nvar GEODATA = {json.dumps(GEODATA, ensure_ascii=False, indent=2)};\n")

# RISK_MAP
js_parts.append(f"\nvar RISK_MAP = {json.dumps(RISK_MAP, ensure_ascii=False, indent=2)};\n")

# DELTA_MAP
js_parts.append(f"\nvar DELTA_MAP = {json.dumps(DELTA_MAP, ensure_ascii=False, indent=2)};\n")

# Query helpers + getPivotTable + getKPIs
js_parts.append("""
// ─── Query helpers ────────────────────────────────────────────────────────────

function getByYear(year) {
  return GEODATA.filter(r => r.año === year);
}

function getByMun(code) {
  return GEODATA.filter(r => r.MPIO_CCDGO === code).sort((a, b) => a.año - b.año);
}

function getTotalByYear(year, includeCali = true) {
  return getByYear(year)
    .filter(r => includeCali || r.MPIO_CCDGO !== '76001')
    .reduce((s, r) => s + r.conteo_dengue, 0);
}

function getYearTotals() {
  return YEARS.map(y => ({ year: y, total: getTotalByYear(y) }));
}

function getTopMunByYear(year, field = 'conteo_dengue', n = 10, includeCali = true) {
  return getByYear(year)
    .filter(r => includeCali || r.MPIO_CCDGO !== '76001')
    .sort((a, b) => b[field] - a[field])
    .slice(0, n);
}

function getPivotTable() {
  // Uses all unique codes from GEODATA (not just MUN_CATALOG)
  const codes = [...new Set(GEODATA.map(r => r.MPIO_CCDGO))];
  const grandTotal = GEODATA.reduce((s, r) => s + r.conteo_dengue, 0);
  return codes.map(code => {
    const rows = getByMun(code);
    const name = rows[0]?.MPIO_CNMBR || code;
    const totalCasos = rows.reduce((s, r) => s + r.conteo_dengue, 0);
    const inc2024 = rows.find(r => r.año === 2024)?.incidencia_dengue || 0;
    const r2023 = rows.find(r => r.año === 2023)?.conteo_dengue || 0;
    const r2024 = rows.find(r => r.año === 2024)?.conteo_dengue || 0;
    const trend = r2024 > r2023 * 1.1 ? 'up' : r2024 < r2023 * 0.9 ? 'down' : 'stable';
    const risk = inc2024 > 600 ? 'Crítico' : inc2024 > 350 ? 'Alto' : inc2024 > 150 ? 'Medio' : 'Bajo';
    return { code, name, totalCasos, inc2024, pct: parseFloat((totalCasos/grandTotal*100).toFixed(1)), trend, risk };
  }).sort((a, b) => b.totalCasos - a.totalCasos).map((r, i) => ({ ...r, rank: i+1 }));
}

function getKPIs(year = 2024) {
  const rows = getByYear(year);
  const total = rows.reduce((s,r)=>s+r.conteo_dengue,0);
  const incProm = rows.reduce((s,r)=>s+r.incidencia_dengue,0)/(rows.length||1);
  const critical = rows.filter(r=>r.incidencia_dengue>400).length;
  const peakYear = YEARS.reduce((best,y)=>getTotalByYear(y)>getTotalByYear(best)?y:best,YEARS[0]);
  return {total, incProm:parseFloat(incProm.toFixed(1)), critical, peakYear};
}
""")

output = "\n".join(js_parts)
DEST.write_text(output, encoding="utf-8")

size_kb = DEST.stat().st_size / 1024
print(f"\nArchivo generado: {DEST}")
print(f"Tamaño: {size_kb:.1f} KB")
print(f"Años: {YEARS}")
print(f"Municipios: {len(MUN_CATALOG)}")
print(f"Registros GEODATA: {len(GEODATA)}")
print("Listo.")
