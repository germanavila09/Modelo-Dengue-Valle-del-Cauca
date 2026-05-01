"""
exportar_datos_obs.py — Geodata Salud Observatory
====================================================
Exporta datos desde PostgreSQL/PostGIS a archivos JS listos para el
observatorio estático (Geodata Salud.html).

Genera dos archivos en --ruta (por defecto: directorio raíz del proyecto):
  • geodata-records.js  →  window.GEO_RECORDS  (array de registros planos)
  • geodata-muni.js     →  window.GEO_MUNI     (GeoJSON FeatureCollection)

Uso:
  python scripts/exportar_datos_obs.py
  python scripts/exportar_datos_obs.py --ruta /ruta/al/observatorio
  python scripts/exportar_datos_obs.py --anio 2024 --ruta ../observatorio

Requisitos:
  • .env configurado con credenciales PostgreSQL
  • Tabla public.valle_mun con columnas:
      MPIO_CCDGO, MPIO_CNMBR, año, población,
      conteo_dengue, incidencia_dengue, geom (EPSG:3857 o 4326)
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Agregar raíz del proyecto al path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.config import DB_CONFIG, SCHEMA, TABLE
from src.db import crear_engine, cargar_datos


# ─── Helpers ──────────────────────────────────────────────────────────────────

def reproyectar_a_4326(gdf):
    """Reproyecta a WGS84 si es necesario."""
    if gdf.crs is None:
        print("  ⚠ Sin CRS definido — asumiendo EPSG:4326")
        return gdf
    try:
        epsg = gdf.crs.to_epsg()
        if epsg != 4326:
            print(f"  → Reproyectando de EPSG:{epsg} a EPSG:4326 …")
            return gdf.to_crs(4326)
    except Exception as e:
        print(f"  ⚠ No se pudo leer EPSG ({e}) — intentando to_crs(4326) …")
        try:
            return gdf.to_crs(4326)
        except Exception as e2:
            print(f"  ✗ Reproyección falló: {e2} — usando geometría original")
    return gdf


def corregir_geometrias(gdf):
    """Corrige geometrías inválidas con buffer(0)."""
    gdf = gdf.copy()
    gdf["geom"] = gdf.geometry.buffer(0)
    return gdf.set_geometry("geom")


def calcular_centroide(feature):
    """Calcula el centroide de un feature GeoJSON (lista de coordenadas)."""
    geom = feature.get("geometry", {})
    coords = []
    gtype = geom.get("type", "")
    if gtype == "Point":
        return geom["coordinates"][1], geom["coordinates"][0]
    elif gtype == "Polygon":
        coords = geom["coordinates"][0]
    elif gtype == "MultiPolygon":
        # Usar el polígono más grande (más coordenadas)
        all_rings = [ring for poly in geom["coordinates"] for ring in poly[:1]]
        coords = max(all_rings, key=len) if all_rings else []
    if coords:
        lats = [c[1] for c in coords]
        lons = [c[0] for c in coords]
        return sum(lats) / len(lats), sum(lons) / len(lons)
    return None, None


# ─── Exportar registros planos ────────────────────────────────────────────────

def exportar_records(gdf, ruta_salida: Path):
    """
    Genera geodata-records.js con window.GEO_RECORDS — array de objetos
    con la misma estructura que el mock en geodata-data.js.
    """
    print("  Exportando registros …")

    columnas_req = ["MPIO_CCDGO", "MPIO_CNMBR", "año", "población",
                    "conteo_dengue", "incidencia_dengue"]
    for col in columnas_req:
        if col not in gdf.columns:
            # Intentar variantes de capitalización
            col_lower = col.lower()
            match = next((c for c in gdf.columns if c.lower() == col_lower), None)
            if match:
                gdf = gdf.rename(columns={match: col})
            else:
                print(f"  ⚠ Columna '{col}' no encontrada — se usará null")

    records = []
    for _, row in gdf.iterrows():
        rec = {
            "MPIO_CCDGO": str(row.get("MPIO_CCDGO", "")),
            "MPIO_CNMBR": str(row.get("MPIO_CNMBR", "")),
            "año":        int(row.get("año", 0)) if row.get("año") else 0,
            "población":  int(row.get("población", 0)) if row.get("población") else 0,
            "conteo_dengue": int(row.get("conteo_dengue", 0)) if row.get("conteo_dengue") else 0,
            "incidencia_dengue": float(round(float(row.get("incidencia_dengue", 0) or 0), 2)),
        }
        records.append(rec)

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    js = (
        f"// geodata-records.js — generado por exportar_datos_obs.py\n"
        f"// {ts} · {len(records)} registros · {TABLE}\n"
        f"window.GEO_RECORDS = {json.dumps(records, ensure_ascii=False, indent=2)};\n"
    )

    dest = ruta_salida / "geodata-records.js"
    dest.write_text(js, encoding="utf-8")
    print(f"  ✓ {dest}  ({len(records)} registros)")
    return records


# ─── Exportar GeoJSON de municipios ──────────────────────────────────────────

def exportar_geojson(gdf, records, ruta_salida: Path):
    """
    Genera geodata-muni.js con window.GEO_MUNI — GeoJSON FeatureCollection
    con una feature por municipio (geometría del año más reciente disponible).
    """
    print("  Exportando geometrías …")

    gdf_geo = corregir_geometrias(gdf)
    gdf_geo = reproyectar_a_4326(gdf_geo)

    # Un feature por municipio (geometría única — la del año más reciente)
    latest_year = gdf_geo["año"].max() if "año" in gdf_geo.columns else None
    if latest_year:
        gdf_muni = gdf_geo[gdf_geo["año"] == latest_year].drop_duplicates("MPIO_CCDGO")
    else:
        gdf_muni = gdf_geo.drop_duplicates("MPIO_CCDGO")

    # Construir mapa code → centroide desde los propios registros GeoJSON
    import geopandas as gpd
    geojson_str = gdf_muni[["MPIO_CCDGO", "MPIO_CNMBR", "geom"]].to_json()
    geojson_obj = json.loads(geojson_str)

    # Inyectar centroide lat/lng a cada feature
    for feat in geojson_obj.get("features", []):
        lat, lng = calcular_centroide(feat)
        feat["properties"]["lat"] = round(lat, 6) if lat else None
        feat["properties"]["lng"] = round(lng, 6) if lng else None

    ts = datetime.now().strftime("%Y-%m-%d %H:%M")
    js = (
        f"// geodata-muni.js — generado por exportar_datos_obs.py\n"
        f"// {ts} · {len(geojson_obj.get('features', []))} municipios · {TABLE}\n"
        f"window.GEO_MUNI = {json.dumps(geojson_obj, ensure_ascii=False)};\n"
    )

    dest = ruta_salida / "geodata-muni.js"
    dest.write_text(js, encoding="utf-8")
    n = len(geojson_obj.get("features", []))
    print(f"  ✓ {dest}  ({n} municipios)")


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Exporta datos PostgreSQL → JS para Geodata Salud Observatory"
    )
    parser.add_argument(
        "--ruta", type=Path, default=ROOT,
        help="Directorio donde guardar geodata-records.js y geodata-muni.js "
             "(debe ser el mismo directorio que Geodata Salud.html). "
             f"Por defecto: {ROOT}"
    )
    args = parser.parse_args()
    ruta_salida = Path(args.ruta).resolve()
    ruta_salida.mkdir(parents=True, exist_ok=True)

    print(f"\n{'─'*60}")
    print(f"  Geodata Salud — Exportador de datos")
    print(f"  Destino: {ruta_salida}")
    print(f"{'─'*60}")

    print("\n[1/3] Conectando a PostgreSQL …")
    try:
        engine = crear_engine()
    except Exception as e:
        print(f"  ✗ No se pudo crear engine: {e}")
        sys.exit(1)

    print("[2/3] Cargando datos desde PostGIS …")
    try:
        gdf = cargar_datos(engine)
        print(f"  ✓ {len(gdf)} filas · columnas: {list(gdf.columns)}")
    except Exception as e:
        print(f"  ✗ Error al cargar datos: {e}")
        sys.exit(1)

    print("[3/3] Exportando archivos JS …")
    try:
        records = exportar_records(gdf, ruta_salida)
        exportar_geojson(gdf, records, ruta_salida)
    except Exception as e:
        import traceback
        print(f"  ✗ Error al exportar: {e}")
        traceback.print_exc()
        sys.exit(1)

    print(f"\n{'─'*60}")
    print("  ✓ Exportación completa.")
    print()
    print("  Próximos pasos:")
    print("  1. Copia geodata-records.js y geodata-muni.js al directorio")
    print("     donde está Geodata Salud.html (si no lo están ya).")
    print("  2. En Geodata Salud.html, descomenta las líneas:")
    print('     <script src="geodata-records.js"></script>')
    print('     <script src="geodata-muni.js"></script>')
    print("  3. Abre Geodata Salud.html en el navegador.")
    print(f"{'─'*60}\n")


if __name__ == "__main__":
    main()
