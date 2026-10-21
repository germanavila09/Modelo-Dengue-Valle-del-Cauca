"""Exporta las edificaciones del piloto de Vijes al geovisor de GeoSalud.

Lee las huellas de Open Buildings v3 y el límite municipal (GAUL 2025) que exporta el
repo Modelo_satelital desde Google Earth Engine, y genera `frontend/vijes-data.js` con
una variable global `VIJES_DATA`. Así el módulo "Piloto Vijes" de `Geodata Salud.html`
abre también con doble clic (file://), igual que el resto de datos del observatorio.

Solo usa la librería estándar de Python.

Uso (desde observatorios/geosalud):
    python scripts/exportar_vijes.py
    python scripts/exportar_vijes.py --huellas RUTA.geojson --limite RUTA.geojson

Importante: son EDIFICACIONES detectadas por satélite (huellas de techos), no predios
catastrales. El predio es una unidad jurídica y no se ve en la imagen.
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
HUELLAS_DEF = Path(r"G:\Mi unidad\piloto_vijes\vijes_open_buildings_v3.geojson")
LIMITE_DEF = Path(r"G:\Mi unidad\piloto_vijes (1)\limite_vijes.geojson")
SALIDA_DEF = RAIZ / "frontend" / "vijes-data.js"

CABECERA = (-76.44, 3.70)  # lon, lat aproximados del casco urbano de Vijes
RADIO_CABECERA_M = 1500


def _anillo_exterior(geom: dict) -> list:
    if geom["type"] == "Polygon":
        return geom["coordinates"][0]
    if geom["type"] == "MultiPolygon":
        return max((p[0] for p in geom["coordinates"]), key=len)
    raise ValueError(f"Geometría no soportada: {geom['type']}")


def _centroide(anillo: list) -> tuple[float, float]:
    pts = anillo[:-1] if anillo[0] == anillo[-1] else anillo
    return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)


def _dentro(x: float, y: float, anillos: list) -> bool:
    """Punto en polígono (ray casting) sobre el anillo exterior y sus huecos."""
    adentro = False
    for anillo in anillos:
        j = len(anillo) - 1
        for i in range(len(anillo)):
            xi, yi = anillo[i]
            xj, yj = anillo[j]
            if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
                adentro = not adentro
            j = i
    return adentro


def _distancia_m(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    r = 6371008.8
    f1, f2 = math.radians(lat1), math.radians(lat2)
    df, dl = f2 - f1, math.radians(lon2 - lon1)
    h = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def exportar(huellas: Path, limite: Path, salida: Path, conf_min: float, area_min: float, area_max: float) -> dict:
    lim = json.loads(limite.read_text(encoding="utf-8"))["features"][0]
    lim_geom = lim["geometry"]
    anillos_lim = lim_geom["coordinates"] if lim_geom["type"] == "Polygon" else lim_geom["coordinates"][0]

    feats = json.loads(huellas.read_text(encoding="utf-8"))["features"]
    edif = []
    resumen = {"total": 0, "dentro_limite": 0, "conf_070": 0, "conf_075": 0, "conf_080": 0,
               "candidatas_vivienda": 0, "cabecera_1_5km": 0, "area_total_m2": 0.0}
    areas = []
    for f in feats:
        p = f["properties"]
        anillo = _anillo_exterior(f["geometry"])
        cx, cy = _centroide(anillo)
        conf = float(p["confidence"])
        area = float(p["area_in_meters"])
        cand = conf >= conf_min and area_min <= area <= area_max
        dentro = _dentro(cx, cy, anillos_lim)
        cab = _distancia_m(cx, cy, *CABECERA) <= RADIO_CABECERA_M
        edif.append({
            "g": [[round(x, 6), round(y, 6)] for x, y in anillo],
            "c": round(conf, 3), "a": round(area, 1), "p": p.get("full_plus_code", ""),
            "v": int(cand), "d": int(dentro), "u": int(cab),
        })
        resumen["total"] += 1
        resumen["dentro_limite"] += dentro
        resumen["conf_070"] += conf >= 0.70
        resumen["conf_075"] += conf >= 0.75
        resumen["conf_080"] += conf >= 0.80
        resumen["candidatas_vivienda"] += cand
        resumen["cabecera_1_5km"] += cab
        resumen["area_total_m2"] += area
        areas.append(area)

    areas.sort()
    resumen["area_mediana_m2"] = round(areas[len(areas) // 2], 1) if areas else None
    resumen["area_total_m2"] = round(resumen["area_total_m2"], 0)

    datos = {
        "meta": {
            "municipio": "Vijes", "divipola": "76869", "departamento": "Valle del Cauca",
            "fuente_edificaciones": "Google Open Buildings v3 (GOOGLE/Research/open-buildings/v3/polygons), inferencia mayo 2023, CC-BY-4.0",
            "fuente_limite": "FAO GAUL 2025 nivel 2 (FAO/GAUL/2025/level2)",
            "aviso": "Edificaciones detectadas por satélite (huellas de techos), no predios catastrales.",
            "parametros": {"confianza_min": conf_min, "area_min_m2": area_min, "area_max_m2": area_max,
                           "cabecera_lonlat": CABECERA, "radio_cabecera_m": RADIO_CABECERA_M},
            "exportado": date.today().isoformat(),
        },
        "resumen": resumen,
        "limite": lim_geom,
        "edificaciones": edif,
    }
    salida.parent.mkdir(parents=True, exist_ok=True)
    cuerpo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
    salida.write_text(
        "// ─── GEODATA SALUD — Piloto Vijes · edificaciones Open Buildings v3 ─────────\n"
        f"// Generado por scripts/exportar_vijes.py — {date.today().isoformat()}\n"
        "// Edificaciones detectadas por satélite, no predios catastrales.\n"
        f"var VIJES_DATA = {cuerpo};\n",
        encoding="utf-8",
    )
    return resumen


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--huellas", type=Path, default=HUELLAS_DEF)
    ap.add_argument("--limite", type=Path, default=LIMITE_DEF)
    ap.add_argument("--salida", type=Path, default=SALIDA_DEF)
    ap.add_argument("--confianza-min", type=float, default=0.70)
    ap.add_argument("--area-min", type=float, default=20)
    ap.add_argument("--area-max", type=float, default=400)
    a = ap.parse_args(argv)
    resumen = exportar(a.huellas, a.limite, a.salida, a.confianza_min, a.area_min, a.area_max)
    print(f"Escrito {a.salida} ({a.salida.stat().st_size / 1e6:.2f} MB)")
    for k, v in resumen.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
