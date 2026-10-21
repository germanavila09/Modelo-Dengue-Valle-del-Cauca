"""Clústeres espaciales de dengue por hexágonos de 200 m (Objetivo 1, componente espacial).

Municipios: Palmira, Guadalajara de Buga, Tuluá y Jamundí. Periodo 2019–2023.

Método
------
1. Unidad: hexágono de 200 m de la malla ``public.hexagonos``.
2. Área de estudio ("huella urbana"): hexágonos con al menos un caso entre
   2019 y 2026 en cada municipio. Sin denominadores de población por hexágono,
   esta huella aproxima dónde vive la población expuesta; dentro de ella los
   años sin casos cuentan como cero.
3. Vecindad: los 6 hexágonos contiguos (banda de distancia sobre centroides en
   EPSG:9377), pesos estandarizados por fila.
4. Por municipio y año: I de Moran global, LISA (Moran local) y Gi* con 999
   permutaciones condicionales (semilla 42). Significancia a p<0,05 y con
   corrección FDR.
5. Persistencia: años 2019–2023 en que cada hexágono es núcleo alto-alto (HH).
6. Clima: resumen anual por municipio con cobertura de meses y asociación
   exploratoria (Spearman) con las métricas de clúster.

Privacidad
----------
- ``interno/`` guarda conteos por hexágono: solo uso del equipo, no publicar.
- Las capas publicables no contienen conteos ni hexágonos aislados: se
  publican zonas (uniones de hexágonos HH contiguos) con al menos
  ``MIN_CASOS_ZONA`` casos, y la persistencia solo para hexágonos con al menos
  ``MIN_CASOS_ZONA`` casos acumulados. Los atípicos HL/LH no se publican porque
  pueden señalar un caso aislado.

Uso
---
    python scripts/clusters_hexagonos.py --fuente db     # malla y casos desde PostGIS (base dengue)
    python scripts/clusters_hexagonos.py --fuente html   # conteos ya agregados en outputs/mapa_dengue_hexagonos.html
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import warnings
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from shapely.geometry import shape

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MUNICIPIOS = {
    "76520": "Palmira",
    "76111": "Guadalajara de Buga",
    "76834": "Tuluá",
    "76364": "Jamundí",
}
ANIOS = list(range(2019, 2024))
ANIOS_HUELLA = (2019, 2026)
MIN_HEX_COMPONENTE = 10  # áreas urbanas continuas; los hexágonos dispersos (rurales) se reportan aparte
PERMUTACIONES = 999
SEMILLA = 42
ALFA = 0.05
MIN_CASOS_ZONA = int(os.getenv("DENGUE_MIN_CELL_CASES", "5"))
CRS_METRICO = 9377  # MAGNA-SIRGAS / Origen-Nacional
SALIDA = ROOT / "outputs" / "clusters_hexagonos"

# Calidad de geocodificación: muchos casos en exactamente la misma coordenada
# indican una ubicación por defecto, no el domicilio.
UMBRAL_SUMIDERO = 100  # punto por defecto del municipio (centro, hospital): se excluye
UMBRAL_CENTROIDE = 10  # probable centroide de barrio: se conserva y se prueba sin él
VARIANTES = {
    "principal": "sin puntos por defecto (≥%d casos en la misma coordenada)" % UMBRAL_SUMIDERO,
    "sensibilidad": "además sin probables centroides (≥%d casos en la misma coordenada)" % UMBRAL_CENTROIDE,
}


# ── Carga ─────────────────────────────────────────────────────────────────────

SQL_HEX = """
WITH casos AS (
    SELECT "año"::int AS anio, geom, ST_X(geom) AS x, ST_Y(geom) AS y
    FROM public.dengue_m
    WHERE geom IS NOT NULL AND ST_X(geom) <> 0 AND ST_Y(geom) <> 0
      AND "año" ~ '^[0-9]{4}$' AND "año"::int BETWEEN :anio_ini AND :anio_fin
),
repeticion AS (
    SELECT x, y, count(*) AS n FROM casos GROUP BY x, y
)
SELECT h.id_3::text AS hex_id, h."MPIO_CCDGO"::text AS mpio_ccdgo, c.anio,
       count(*)::int AS casos,
       count(*) FILTER (WHERE r.n >= :umbral_sumidero)::int AS casos_sumidero,
       count(*) FILTER (WHERE r.n >= :umbral_centroide AND r.n < :umbral_sumidero)::int AS casos_centroide,
       ST_AsGeoJSON(h.geometry, 6) AS geometry_geojson
FROM casos c
JOIN repeticion r ON r.x = c.x AND r.y = c.y
JOIN public.hexagonos h ON h.geometry && c.geom AND ST_Covers(h.geometry, c.geom)
WHERE h."MPIO_CCDGO" = ANY(CAST(:codigos AS text[]))
GROUP BY h.id_3, h."MPIO_CCDGO", c.anio, h.geometry
"""


def cargar_desde_db() -> pd.DataFrame:
    """Agrega casos por hexágono dentro de la base restringida; solo salen conteos."""
    from sqlalchemy import create_engine, text
    from sqlalchemy.engine import URL

    from src.config import DB_CONFIG

    engine = create_engine(
        URL.create(
            "postgresql+psycopg2",
            username=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=os.getenv("DENGUE_SOURCE_DB_NAME", "dengue"),
        ),
        connect_args={"client_encoding": "utf8", "options": "-c default_transaction_read_only=on"},
    )
    try:
        with engine.connect() as conn:
            df = pd.read_sql(
                text(SQL_HEX),
                conn,
                params={"anio_ini": ANIOS_HUELLA[0], "anio_fin": ANIOS_HUELLA[1], "codigos": list(MUNICIPIOS),
                        "umbral_sumidero": UMBRAL_SUMIDERO, "umbral_centroide": UMBRAL_CENTROIDE},
            )
    finally:
        engine.dispose()
    return df


def cargar_desde_html(ruta: Path) -> pd.DataFrame:
    """Lee los conteos por hexágono ya agregados por scripts/generar_mapa_hexagonos_html.py."""
    texto = ruta.read_text(encoding="utf-8")
    inicio = texto.find("=", texto.find("const datasets")) + 1
    while texto[inicio].isspace():
        inicio += 1
    datasets, _ = json.JSONDecoder().raw_decode(texto, inicio)
    filas = []
    for anio, coleccion in datasets.items():
        for f in coleccion["features"]:
            p = f["properties"]
            if p["mpio_ccdgo"] in MUNICIPIOS:
                filas.append(
                    {
                        "hex_id": p["hex_id"],
                        "mpio_ccdgo": p["mpio_ccdgo"],
                        "anio": int(anio),
                        "casos": int(p["casos"]),
                        "geometry_geojson": json.dumps(f["geometry"]),
                    }
                )
    return pd.DataFrame(filas)


def clasificar_geocodificacion_legado(conteos: pd.DataFrame, ruta_puntos: Path) -> pd.DataFrame:
    """Añade casos_sumidero y casos_centroide usando el mapa de puntos heredado.

    Solo para el modo html: el mapa antiguo outputs/mapa_actual.html contiene los
    puntos individuales. Se leen en memoria, se cuentan repeticiones por
    coordenada y únicamente se conservan conteos por hexágono. En modo db el
    mismo cálculo ocurre dentro de PostgreSQL.
    """
    from shapely import STRtree
    from shapely.geometry import Point

    texto = ruta_puntos.read_text(encoding="utf-8", errors="replace")
    i = texto.find("const heatData =")
    datos = json.loads(texto[i + len("const heatData ="): texto.find("\n", i)].strip().rstrip(";"))
    puntos = [
        (int(clave[:4]), tuple(p[:2]))
        for clave, lista in datos.items()
        if clave.endswith("_con_cali") and ANIOS_HUELLA[0] <= int(clave[:4]) <= ANIOS_HUELLA[1]
        for p in lista
    ]
    repeticion = pd.Series([c for _, c in puntos]).value_counts()
    hexes = conteos.drop_duplicates("hex_id")
    geoms = [shape(json.loads(g)) for g in hexes["geometry_geojson"]]
    arbol = STRtree(geoms)
    ids = hexes["hex_id"].to_numpy()
    filas = []
    for anio, coord in puntos:
        n = repeticion[coord]
        if n < UMBRAL_CENTROIDE:
            continue
        idx = arbol.query(Point(coord[1], coord[0]), predicate="within")
        if len(idx):
            filas.append({"hex_id": ids[idx[0]], "anio": anio,
                          "casos_sumidero": int(n >= UMBRAL_SUMIDERO), "casos_centroide": int(n < UMBRAL_SUMIDERO)})
    extra = pd.DataFrame(filas, columns=["hex_id", "anio", "casos_sumidero", "casos_centroide"])
    extra = extra.groupby(["hex_id", "anio"], as_index=False).sum()
    out = conteos.merge(extra, on=["hex_id", "anio"], how="left").fillna({"casos_sumidero": 0, "casos_centroide": 0})
    out[["casos_sumidero", "casos_centroide"]] = out[["casos_sumidero", "casos_centroide"]].astype(int)
    # Por si la fuente de puntos y la de hexágonos difieren levemente.
    out["casos_sumidero"] = out[["casos_sumidero", "casos"]].min(axis=1)
    out["casos_centroide"] = np.minimum(out["casos_centroide"], out["casos"] - out["casos_sumidero"])
    return out


def construir_panel(conteos: pd.DataFrame) -> tuple[gpd.GeoDataFrame, pd.DataFrame]:
    """Devuelve la malla de la huella urbana y el panel hexágono × año con ceros."""
    conteos = conteos[conteos["anio"].between(*ANIOS_HUELLA)]
    malla = (
        conteos.drop_duplicates("hex_id")[["hex_id", "mpio_ccdgo", "geometry_geojson"]]
        .assign(geometry=lambda d: d["geometry_geojson"].map(lambda g: shape(json.loads(g))))
        .drop(columns="geometry_geojson")
    )
    malla = gpd.GeoDataFrame(malla, geometry="geometry", crs=4326)
    malla["municipio"] = malla["mpio_ccdgo"].map(MUNICIPIOS)
    for col in ("casos_sumidero", "casos_centroide"):
        if col not in conteos:
            conteos = conteos.assign(**{col: 0})
    indice = pd.MultiIndex.from_product([malla["hex_id"], ANIOS], names=["hex_id", "anio"])
    panel = (
        conteos.groupby(["hex_id", "anio"])[["casos", "casos_sumidero", "casos_centroide"]].sum()
        .reindex(indice, fill_value=0)
        .reset_index()
        .merge(malla[["hex_id", "mpio_ccdgo"]], on="hex_id")
    )
    panel["principal"] = panel["casos"] - panel["casos_sumidero"]
    panel["sensibilidad"] = panel["principal"] - panel["casos_centroide"]
    return malla, panel


# ── Estadística espacial ──────────────────────────────────────────────────────

def pesos_hexagonales(malla_mpio: gpd.GeoDataFrame):
    from libpysal.weights import DistanceBand
    import libpysal

    libpysal.weights.util.warn = lambda *a, **k: None

    centros = malla_mpio.to_crs(CRS_METRICO).geometry.centroid
    xy = np.column_stack([centros.x, centros.y])
    from scipy.spatial import cKDTree

    d, _ = cKDTree(xy).query(xy, k=2)
    paso = float(np.median(d[:, 1]))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        w = DistanceBand(xy, threshold=paso * 1.15, binary=True, silence_warnings=True, ids=list(malla_mpio["hex_id"]))
    w.transform = "r"
    return w, paso


def area_urbana(malla_mpio: gpd.GeoDataFrame) -> tuple[gpd.GeoDataFrame, pd.Series]:
    """Conserva los componentes contiguos con ≥MIN_HEX_COMPONENTE hexágonos."""
    w, _ = pesos_hexagonales(malla_mpio)
    etiquetas = pd.Series(w.component_labels, index=w.id_order)
    tamanos = etiquetas.map(etiquetas.value_counts())
    conservar = tamanos[tamanos >= MIN_HEX_COMPONENTE].index
    return malla_mpio[malla_mpio["hex_id"].isin(conservar)].reset_index(drop=True), etiquetas


def analizar(y: np.ndarray, w) -> dict:
    from esda.getisord import G_Local
    from esda.moran import Moran, Moran_Local
    from esda import fdr

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        mg = Moran(y, w, permutations=PERMUTACIONES)
        ml = Moran_Local(y, w, permutations=PERMUTACIONES, seed=SEMILLA)
        gi = G_Local(y, w, star=True, permutations=PERMUTACIONES, seed=SEMILLA, transform="R")
    umbral_lisa = fdr(ml.p_sim, ALFA)
    umbral_gi = fdr(gi.p_sim, ALFA)
    etiquetas = np.array(["ns", "HH", "LH", "LL", "HL"], dtype=object)
    cuadrante = etiquetas[ml.q]
    lisa = np.where(ml.p_sim < ALFA, cuadrante, "ns").astype(object)
    lisa_fdr = np.where(ml.p_sim <= umbral_lisa, cuadrante, "ns").astype(object)
    caliente_frio = np.where(gi.Zs > 0, "caliente", "frio").astype(object)
    gi_cat = np.where(gi.p_sim < ALFA, caliente_frio, "ns").astype(object)
    gi_cat_fdr = np.where(gi.p_sim <= umbral_gi, caliente_frio, "ns").astype(object)
    islas = np.array([len(w.neighbors[i]) == 0 for i in w.id_order])
    for arr in (lisa, lisa_fdr, gi_cat, gi_cat_fdr):
        arr[islas] = "aislado"
    return {
        "moran_I": float(mg.I),
        "moran_p": float(mg.p_sim),
        "moran_z": float(mg.z_sim),
        "lisa_Ii": ml.Is,
        "lisa_p": ml.p_sim,
        "lisa": lisa,
        "lisa_fdr": lisa_fdr,
        "gi_z": gi.Zs,
        "gi_p": gi.p_sim,
        "gi": gi_cat,
        "gi_fdr": gi_cat_fdr,
        "islas": islas,
    }


def zonas_hh(malla_mpio: gpd.GeoDataFrame, w, mascara: np.ndarray, casos: np.ndarray) -> list[dict]:
    """Une hexágonos HH contiguos en zonas (componentes conexos)."""
    ids = list(w.id_order)
    pos = {h: i for i, h in enumerate(ids)}
    pendientes = {i for i in range(len(ids)) if mascara[i]}
    zonas = []
    while pendientes:
        semilla = pendientes.pop()
        comp, cola = [semilla], [semilla]
        while cola:
            actual = cola.pop()
            for vecino in w.neighbors[ids[actual]]:
                j = pos[vecino]
                if j in pendientes:
                    pendientes.remove(j)
                    comp.append(j)
                    cola.append(j)
        zonas.append({"indices": comp, "hexagonos": len(comp), "casos": int(casos[comp].sum())})
    return zonas


# ── Clima ─────────────────────────────────────────────────────────────────────

def cargar_clima(fuente: str) -> pd.DataFrame:
    if fuente == "db":
        from src.db import crear_engine

        engine = crear_engine()
        try:
            clima = pd.read_sql('SELECT * FROM public.clima_mensual_municipio', engine)
        finally:
            engine.dispose()
    else:
        texto = (ROOT / "frontend" / "geodata-data.js").read_text(encoding="utf-8")
        inicio = texto.find("=", texto.find("CLIMADATA")) + 1
        while texto[inicio].isspace():
            inicio += 1
        clima = pd.DataFrame(json.JSONDecoder().raw_decode(texto, inicio)[0])
    clima = clima.rename(columns={"año": "anio", "MPIO_CCDGO": "mpio_ccdgo"})
    clima["mpio_ccdgo"] = clima["mpio_ccdgo"].astype(str)
    # Rangos plausibles para el valle geográfico del río Cauca (~900–1.100 m s.n.m.).
    # La fuente trae precipitaciones mensuales de decenas de miles de mm y humedades
    # máximas por debajo de 50 %, que se descartan.
    valido = (
        clima["total_precipitation"].between(0, 1000)
        & (clima["mean_max_humidity"] >= 50)
        & (clima["mean_min_temperature"] < clima["mean_max_temperature"])
        & clima["mean_max_temperature"].between(10, 45)
        & clima["mean_min_temperature"].between(5, 35)
        & clima["mean_min_humidity"].between(0, 100)
        & clima["mean_max_humidity"].between(0, 100)
        & (clima["mean_min_humidity"] <= clima["mean_max_humidity"])
    )
    clima["valido"] = valido
    return clima


def resumen_clima(clima: pd.DataFrame) -> pd.DataFrame:
    v = clima[clima["valido"]]
    columnas = {
        "total_precipitation": "precip_mensual_mm",
        "mean_max_temperature": "tmax_c",
        "mean_min_temperature": "tmin_c",
        "mean_max_humidity": "hr_max_pct",
        "mean_min_humidity": "hr_min_pct",
    }
    def agregar(df, claves):
        r = df.groupby(claves).agg(meses_validos=("mes", "nunique"), **{n: (c, "mean") for c, n in columnas.items()})
        return r.reset_index()

    municipal = agregar(v[v["mpio_ccdgo"].isin(MUNICIPIOS)], ["mpio_ccdgo", "anio"])
    municipal["fuente_clima"] = "municipal"
    # Serie regional: promedio mensual de los municipios del valle con dato válido.
    regional_mes = v.groupby(["anio", "mes"])[list(columnas)].mean().reset_index()
    regional = agregar(regional_mes.assign(), ["anio"])
    invalidos = clima.loc[~clima["valido"] & clima["mpio_ccdgo"].isin(MUNICIPIOS)].groupby(["mpio_ccdgo", "anio"]).size()
    municipal["meses_invalidos"] = [int(invalidos.get((m, a), 0)) for m, a in zip(municipal["mpio_ccdgo"], municipal["anio"])]
    return municipal, regional


def asociacion(metricas: pd.DataFrame, clima_mpio: pd.DataFrame, min_meses: int = 9) -> pd.DataFrame:
    """Spearman exploratorio entre métricas de clúster y clima municipal del mismo año.

    Solo usa municipio-años con ≥min_meses meses válidos. No se usa la serie
    regional para correlacionar: repetirla en los cuatro municipios infla n
    (pseudorreplicación; en realidad son 5 años).
    """
    from scipy.stats import spearmanr

    variables = ["precip_mensual_mm", "tmax_c", "tmin_c", "hr_max_pct", "hr_min_pct"]
    df = metricas.merge(clima_mpio[clima_mpio["meses_validos"] >= min_meses], on=["mpio_ccdgo", "anio"])
    resultados = []
    for metrica in ("casos", "moran_I", "pct_casos_en_HH", "hex_HH"):
        for var in variables:
            sub = df[[metrica, var]].dropna()
            fila = {"metrica": metrica, "variable": var, "n_municipio_anio": len(sub), "rho": None, "p": None}
            if len(sub) >= 5 and sub[metrica].nunique() > 1 and sub[var].nunique() > 1:
                rho, pv = spearmanr(sub[metrica], sub[var])
                fila.update(rho=round(float(rho), 3), p=round(float(pv), 4))
            resultados.append(fila)
    return pd.DataFrame(resultados)


# ── Salidas ───────────────────────────────────────────────────────────────────

COLORES = {"HH": "#b2182b", "persistente": "#67001f", "intermitente": "#d6604d", "esporadico": "#f4a582"}


def mapa_html(zonas: gpd.GeoDataFrame, persistencia: gpd.GeoDataFrame, ruta: Path):
    capas = {
        str(a): json.loads(zonas[zonas["anio"] == a][["municipio", "anio", "hexagonos", "geometry"]].to_json())
        for a in ANIOS
    }
    pers = json.loads(persistencia[["municipio", "anios_HH", "clase", "geometry"]].to_json())
    centro = zonas.union_all().centroid if len(zonas) else persistencia.union_all().centroid
    html = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clústeres de dengue por hexágonos</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
 html,body,#map{{height:100%;margin:0;font-family:system-ui,Segoe UI,Arial,sans-serif}}
 .panel{{position:absolute;top:12px;right:12px;z-index:1000;background:#fff;padding:12px 14px;border-radius:8px;
   box-shadow:0 2px 10px rgba(0,0,0,.2);max-width:300px;font-size:13px;line-height:1.45}}
 .panel h3{{margin:0 0 6px;font-size:15px}} .panel select{{width:100%;margin:4px 0 8px;padding:4px}}
 .sw{{display:inline-block;width:12px;height:12px;margin-right:6px;vertical-align:-1px}}
 .nota{{color:#555;font-size:11.5px;margin-top:8px}}
</style></head><body><div id="map"></div>
<div class="panel"><h3>Clústeres de dengue · hexágonos 200 m</h3>
<label>Municipio</label><select id="mpio"><option value="">Todos</option>
{''.join(f'<option>{n}</option>' for n in MUNICIPIOS.values())}</select>
<label>Capa</label><select id="capa"><option value="persistencia">Persistencia 2019–2023</option>
{''.join(f'<option value="{a}">Zonas alto-alto {a}</option>' for a in ANIOS)}</select>
<div id="leyenda"></div>
<div class="nota">Palmira, Buga, Tuluá y Jamundí. LISA con 999 permutaciones, p&lt;0,05. Sin conteos: zonas con ≥{MIN_CASOS_ZONA} casos y hexágonos con ≥{MIN_CASOS_ZONA} casos acumulados. Uso analítico.</div></div>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const zonas={json.dumps(capas, ensure_ascii=False)};
const pers={json.dumps(pers, ensure_ascii=False)};
const C={json.dumps(COLORES)};
const map=L.map('map').setView([{centro.y:.4f},{centro.x:.4f}],10);
// Mapa base sin clave de API (lienzo gris de Esri); si falla se usa OpenStreetMap.
let errBase=0;
const baseEsri=L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{{z}}/{{y}}/{{x}}',
  {{attribution:'Mapa base © Esri, HERE, Garmin, © colaboradores de OpenStreetMap',maxZoom:16,maxNativeZoom:16}})
  .on('tileerror',()=>{{if(++errBase===4){{map.removeLayer(baseEsri);L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',{{attribution:'© colaboradores de OpenStreetMap',maxZoom:18}}).addTo(map);}}}})
  .addTo(map);
let capa=null;
function pintar(){{
  const v=document.getElementById('capa').value, mp=document.getElementById('mpio').value;
  const filtro=f=>!mp||f.properties.municipio===mp;
  if(capa) map.removeLayer(capa);
  const ley=document.getElementById('leyenda');
  if(v==='persistencia'){{
    capa=L.geoJSON(pers,{{filter:filtro,style:f=>({{color:C[f.properties.clase],weight:.6,fillColor:C[f.properties.clase],fillOpacity:.75}}),
      onEachFeature:(f,l)=>l.bindTooltip(f.properties.municipio+' · alto-alto en '+f.properties.anios_HH+' de 5 años')}}).addTo(map);
    ley.innerHTML=['persistente','intermitente','esporadico'].map(k=>`<div><span class="sw" style="background:${{C[k]}}"></span>${{{{persistente:'Persistente (≥3 años)',intermitente:'Intermitente (2 años)',esporadico:'Esporádico (1 año)'}}[k]}}</div>`).join('');
  }} else {{
    capa=L.geoJSON(zonas[v],{{filter:filtro,style:()=>({{color:C.HH,weight:1,fillColor:C.HH,fillOpacity:.6}}),
      onEachFeature:(f,l)=>l.bindTooltip(f.properties.municipio+' · zona de '+f.properties.hexagonos+' hexágonos')}}).addTo(map);
    ley.innerHTML=`<div><span class="sw" style="background:${{C.HH}}"></span>Zona alto-alto (LISA)</div>`;
  }}
  try{{map.fitBounds(capa.getBounds(),{{padding:[20,20],maxZoom:14}})}}catch(e){{}}
}}
document.getElementById('capa').addEventListener('change',pintar);
document.getElementById('mpio').addEventListener('change',pintar);
pintar();
</script></body></html>"""
    ruta.write_text(html, encoding="utf-8")


def figura(malla: gpd.GeoDataFrame, resultados: pd.DataFrame, ruta: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch

    colores = {"HH": "#b2182b", "LL": "#2166ac", "HL": "#f4a582", "LH": "#92c5de", "ns": "#e8e8e8", "aislado": "#e8e8e8"}
    mpios = list(MUNICIPIOS)
    fig, axes = plt.subplots(len(mpios), len(ANIOS), figsize=(3.1 * len(ANIOS), 3.3 * len(mpios)))
    base = malla.to_crs(CRS_METRICO)
    for i, m in enumerate(mpios):
        g = base[base["mpio_ccdgo"] == m]
        g = g[g["hex_id"].isin(resultados["hex_id"])].reset_index(drop=True)
        # Encuadre en la cabecera (componente contiguo más grande) para que se lean los hexágonos.
        w_m, _ = pesos_hexagonales(g)
        etiquetas = pd.Series(w_m.component_labels, index=w_m.id_order)
        cabecera = g[g["hex_id"].isin(etiquetas[etiquetas == etiquetas.value_counts().idxmax()].index)]
        x0, y0, x1, y1 = cabecera.total_bounds
        margen = 0.04 * max(x1 - x0, y1 - y0)
        for j, a in enumerate(ANIOS):
            ax = axes[i, j]
            r = resultados[(resultados["mpio_ccdgo"] == m) & (resultados["anio"] == a)][["hex_id", "lisa"]]
            gg = g.merge(r, on="hex_id", how="inner")
            gg.plot(ax=ax, color=gg["lisa"].map(colores), linewidth=0)
            ax.set_xlim(x0 - margen, x1 + margen)
            ax.set_ylim(y0 - margen, y1 + margen)
            ax.set_aspect("equal")
            ax.set_axis_off()
            if i == 0:
                ax.set_title(str(a), fontsize=12)
            if j == 0:
                ax.text(-0.05, 0.5, MUNICIPIOS[m], transform=ax.transAxes, rotation=90, va="center", ha="right", fontsize=12)
    fig.legend(handles=[Patch(color=colores[k], label=k) for k in ("HH", "LL", "HL", "LH", "ns")],
               loc="lower center", ncol=5, frameon=False)
    fig.suptitle("LISA de casos de dengue por hexágono de 200 m, cabeceras municipales\n"
                 "(p<0,05; 999 permutaciones; sin puntos por defecto de geocodificación)", fontsize=13)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    fig.savefig(ruta, dpi=130)
    plt.close(fig)


# ── Orquestación ──────────────────────────────────────────────────────────────

def ejecutar(fuente: str, salida: Path = SALIDA, puntos_legado: Path | None = None) -> dict:
    salida.mkdir(parents=True, exist_ok=True)
    (salida / "interno").mkdir(exist_ok=True)

    if fuente == "db":
        conteos = cargar_desde_db()
    else:
        conteos = cargar_desde_html(ROOT / "outputs" / "mapa_dengue_hexagonos.html")
        if puntos_legado and puntos_legado.exists():
            conteos = clasificar_geocodificacion_legado(conteos, puntos_legado)
        else:
            print("AVISO: sin fuente de puntos no se detectan ubicaciones por defecto; las variantes coinciden.")
    malla, panel = construir_panel(conteos)

    calidad = (
        panel.groupby("mpio_ccdgo")[["casos", "casos_sumidero", "casos_centroide"]].sum().reset_index()
        .assign(municipio=lambda d: d["mpio_ccdgo"].map(MUNICIPIOS))
    )
    calidad["pct_sumidero"] = (100 * calidad["casos_sumidero"] / calidad["casos"]).round(1)
    calidad["pct_centroide"] = (100 * calidad["casos_centroide"] / calidad["casos"]).round(1)

    filas_hex, metricas, zonas_pub, exclusiones = [], [], [], []
    for m, nombre in MUNICIPIOS.items():
        completa = malla[malla["mpio_ccdgo"] == m].reset_index(drop=True)
        malla_m, _ = area_urbana(completa)
        fuera = panel[(panel["mpio_ccdgo"] == m) & ~panel["hex_id"].isin(malla_m["hex_id"])]
        exclusiones.append({"municipio": nombre, "hex_huella": len(completa), "hex_area_urbana": len(malla_m),
                            "hex_dispersos_excluidos": len(completa) - len(malla_m),
                            "casos_2019_2023_excluidos": int(fuera["casos"].sum()),
                            "pct_casos_excluidos": round(100 * fuera["casos"].sum() / max(panel.loc[panel["mpio_ccdgo"] == m, "casos"].sum(), 1), 1)})
        w, paso = pesos_hexagonales(malla_m)
        orden = pd.Index(w.id_order)
        sub = panel[panel["mpio_ccdgo"] == m]
        for variante in VARIANTES:
            for a in ANIOS + ["2019-2023"]:
                if a == "2019-2023":
                    y = sub.groupby("hex_id")[variante].sum().reindex(orden).to_numpy(float)
                else:
                    y = sub[sub["anio"] == a].set_index("hex_id")[variante].reindex(orden).to_numpy(float)
                if y.sum() == 0:
                    continue
                r = analizar(y, w)
                hh = r["lisa"] == "HH"
                metricas.append({
                    "variante": variante, "mpio_ccdgo": m, "municipio": nombre, "anio": a,
                    "casos": int(y.sum()), "hex_huella": len(y), "hex_con_casos": int((y > 0).sum()),
                    "hex_aislados": int(r["islas"].sum()), "paso_m": round(paso),
                    "moran_I": round(r["moran_I"], 4), "moran_p": r["moran_p"], "moran_z": round(r["moran_z"], 2),
                    "hex_HH": int(hh.sum()), "hex_HH_fdr": int((r["lisa_fdr"] == "HH").sum()),
                    "hex_LL": int((r["lisa"] == "LL").sum()), "hex_HL": int((r["lisa"] == "HL").sum()),
                    "hex_LH": int((r["lisa"] == "LH").sum()),
                    "hex_gi_caliente": int((r["gi"] == "caliente").sum()),
                    "hex_gi_caliente_fdr": int((r["gi_fdr"] == "caliente").sum()),
                    "pct_casos_en_HH": round(100 * y[hh].sum() / y.sum(), 1),
                    "pct_area_HH": round(100 * hh.sum() / len(y), 1),
                    "pct_casos_hex_max": round(100 * y.max() / y.sum(), 1),
                })
                filas_hex.append(pd.DataFrame({
                    "variante": variante, "hex_id": orden, "mpio_ccdgo": m, "anio": a, "casos": y.astype(int),
                    "lisa": r["lisa"], "lisa_fdr": r["lisa_fdr"], "lisa_Ii": r["lisa_Ii"].round(4), "lisa_p": r["lisa_p"],
                    "gi": r["gi"], "gi_fdr": r["gi_fdr"], "gi_z": r["gi_z"].round(3), "gi_p": r["gi_p"],
                }))
                if variante == "principal" and a != "2019-2023":
                    for z in zonas_hh(malla_m, w, hh, y):
                        if z["casos"] >= MIN_CASOS_ZONA:
                            geom = malla_m.loc[z["indices"]].union_all()
                            zonas_pub.append({"municipio": nombre, "mpio_ccdgo": m, "anio": a,
                                              "hexagonos": z["hexagonos"], "geometry": geom})

    resultados = pd.concat(filas_hex, ignore_index=True)
    metricas = pd.DataFrame(metricas)

    anual = resultados[(resultados["anio"] != "2019-2023")].copy()
    anual["anio"] = anual["anio"].astype(int)
    pers = anual.assign(es_hh=anual["lisa"] == "HH").groupby(["variante", "hex_id"]).agg(
        anios_HH=("es_hh", "sum"), casos_2019_2023=("casos", "sum")).reset_index()
    pers["clase"] = pd.cut(pers["anios_HH"], [-1, 0, 1, 2, 5], labels=["nunca", "esporadico", "intermitente", "persistente"]).astype(str)
    resumen_pers = (
        pers.merge(malla[["hex_id", "mpio_ccdgo", "municipio"]], on="hex_id")
        .groupby(["variante", "municipio", "clase"]).agg(hexagonos=("hex_id", "size"), casos=("casos_2019_2023", "sum")).reset_index()
    )
    resumen_pers["pct_casos_mpio"] = (100 * resumen_pers["casos"] / resumen_pers.groupby(["variante", "municipio"])["casos"].transform("sum")).round(1)
    pers_principal = pers[pers["variante"] == "principal"].drop(columns="variante")
    resultados_principal = resultados[resultados["variante"] == "principal"]

    # Clima
    clima = cargar_clima(fuente)
    clima_mpio, clima_reg = resumen_clima(clima)
    metricas_anuales = metricas[(metricas["anio"] != "2019-2023") & (metricas["variante"] == "principal")].copy()
    metricas_anuales["anio"] = metricas_anuales["anio"].astype(int)
    asoc = asociacion(metricas_anuales, clima_mpio)

    # Escritura: interno (conteos) y publicable (sin conteos)
    pd.DataFrame(exclusiones).to_csv(salida / "area_estudio.csv", index=False)
    calidad.to_csv(salida / "calidad_geocodificacion.csv", index=False)
    resultados.to_csv(salida / "interno" / "lisa_gi_hexagono_anio.csv", index=False)
    pers.to_csv(salida / "interno" / "persistencia_hexagono.csv", index=False)
    metricas.to_csv(salida / "metricas_municipio_anio.csv", index=False)
    resumen_pers.to_csv(salida / "persistencia_resumen.csv", index=False)
    clima_mpio.to_csv(salida / "clima_anual_municipio.csv", index=False)
    clima_reg.to_csv(salida / "clima_anual_regional.csv", index=False)
    asoc.to_csv(salida / "asociacion_clima_clusters.csv", index=False)

    zonas_gdf = gpd.GeoDataFrame(zonas_pub, geometry="geometry", crs=4326) if zonas_pub else gpd.GeoDataFrame(
        columns=["municipio", "mpio_ccdgo", "anio", "hexagonos", "geometry"], geometry="geometry", crs=4326)
    pers_pub = malla.merge(pers_principal, on="hex_id")
    pers_pub = pers_pub[(pers_pub["anios_HH"] > 0) & (pers_pub["casos_2019_2023"] >= MIN_CASOS_ZONA)][
        ["hex_id", "mpio_ccdgo", "municipio", "anios_HH", "clase", "geometry"]]
    # Se escribe como texto para poder sobrescribir sin borrar el archivo previo.
    (salida / "zonas_HH_publicable.geojson").write_text(zonas_gdf.to_json(), encoding="utf-8")
    (salida / "persistencia_publicable.geojson").write_text(pers_pub.drop(columns="hex_id").to_json(), encoding="utf-8")
    # Clústeres LISA publicables: solo categoría (sin conteos ni p). Los atípicos HL/LH
    # se omiten si el hexágono tiene menos de MIN_CASOS_ZONA casos en el periodo.
    lisa_pub = resultados_principal[resultados_principal["lisa"].isin(["HH", "LL", "HL", "LH"])].copy()
    lisa_pub = lisa_pub[~(lisa_pub["lisa"].isin(["HL", "LH"]) & (lisa_pub["casos"] < MIN_CASOS_ZONA))]
    lisa_pub = malla[["hex_id", "geometry"]].merge(lisa_pub[["hex_id", "mpio_ccdgo", "anio", "lisa"]], on="hex_id")
    lisa_pub["municipio"] = lisa_pub["mpio_ccdgo"].map(MUNICIPIOS)
    lisa_pub["anio"] = lisa_pub["anio"].astype(str)
    (salida / "lisa_publicable.geojson").write_text(
        lisa_pub[["municipio", "mpio_ccdgo", "anio", "lisa", "geometry"]].to_json(), encoding="utf-8")
    mapa_html(zonas_gdf, pers_pub, salida / "mapa_clusters_hexagonos.html")
    figura(malla, resultados_principal[resultados_principal["anio"] != "2019-2023"].assign(anio=lambda d: d["anio"].astype(int)),
           salida / "lisa_municipio_anio.png")

    meta = {
        "fuente": fuente,
        "municipios": MUNICIPIOS,
        "anios": ANIOS,
        "huella": f"hexágonos con ≥1 caso entre {ANIOS_HUELLA[0]} y {ANIOS_HUELLA[1]}",
        "permutaciones": PERMUTACIONES,
        "semilla": SEMILLA,
        "alfa": ALFA,
        "min_casos_publicacion": MIN_CASOS_ZONA,
        "variantes": VARIANTES,
        "componente_minimo_hexagonos": MIN_HEX_COMPONENTE,
        "hexagonos_huella": int(len(malla)),
        "zonas_publicadas": int(len(zonas_gdf)),
        "hexagonos_persistencia_publicados": int(len(pers_pub)),
        "hexagonos_lisa_publicados": int(len(lisa_pub)),
    }
    (salida / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"metricas": metricas, "persistencia": resumen_pers, "area": pd.DataFrame(exclusiones), "calidad": calidad, "asociacion": asoc,
            "clima_mpio": clima_mpio, "clima_reg": clima_reg, "meta": meta}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fuente", choices=["db", "html"], default="db")
    parser.add_argument("--salida", default=str(SALIDA))
    parser.add_argument("--puntos-legado", default=None,
                        help="Solo modo html: mapa antiguo con puntos para detectar ubicaciones por defecto.")
    args = parser.parse_args(argv)
    r = ejecutar(args.fuente, Path(args.salida), Path(args.puntos_legado) if args.puntos_legado else None)
    pd.set_option("display.width", 200, "display.max_columns", 30)
    print(r["calidad"].to_string(index=False), "\n")
    print(r["metricas"][["variante", "municipio", "anio", "casos", "hex_huella", "hex_con_casos", "moran_I", "moran_p",
                         "hex_HH", "hex_HH_fdr", "pct_casos_en_HH", "pct_area_HH"]].to_string(index=False))
    print("\nÁrea de estudio\n", r["area"].to_string(index=False))
    print("\nPersistencia\n", r["persistencia"].to_string(index=False))
    print(f"\nSalidas en {args.salida}")


if __name__ == "__main__":
    main()
