"""Construye el notebook de analisis de dengue por hexagonos."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NB = ROOT / "notebooks" / "analisis_dengue_hexagonos.ipynb"


def md(source):
    return {"cell_type": "markdown", "metadata": {}, "source": source.splitlines(True)}


def code(source):
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(True),
    }


cells = [
    md(
        """# Analisis de dengue por hexagonos

Informe para cruzar los casos puntuales de `public.dengue_m` con la grilla `public.hexagonos`.
El objetivo es identificar concentraciones espaciales, comparar anos y producir un mapa Leaflet dinamico para exploracion territorial."""
    ),
    md(
        """## 1. Setup

Se cargan librerias de analisis, conexion a PostGIS, visualizacion y generacion de mapas Leaflet. Leaflet se usa en el HTML interactivo; `folium` queda disponible para mapas rapidos dentro del notebook."""
    ),
    code(
        """from pathlib import Path
import json
import warnings

import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
import folium

from IPython.display import IFrame, display
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

warnings.filterwarnings("ignore")

ROOT = Path.cwd().parent if Path.cwd().name == "notebooks" else Path.cwd()
OUTPUTS = ROOT / "outputs"
OUTPUTS.mkdir(exist_ok=True)

load_dotenv(ROOT / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "dengue")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

engine = create_engine(
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

ANIO_DEFAULT = 2024
print(f"Conexion lista: {DB_NAME} en {DB_HOST}:{DB_PORT}")"""
    ),
    md("## 2. Insumos\n\nRevision inicial de `public.hexagonos` y `public.dengue_m`."),
    code(
        """sql_hex_info = text('''
select count(*) as total_hexagonos,
       count(distinct "MPIO_CCDGO") as municipios,
       count(*) filter (where geometry is null) as sin_geometria,
       count(*) filter (where geometry is not null and not ST_IsValid(geometry)) as invalidas,
       count(*) filter (where GeometryType(geometry) = 'POLYGON') as polygon,
       count(*) filter (where GeometryType(geometry) = 'MULTIPOLYGON') as multipolygon,
       round(avg(ST_Area(geometry::geography))::numeric, 2) as area_prom_m2
from public.hexagonos;
''')

sql_casos_info = text('''
select count(*) as total_casos,
       count(geom) as con_geom,
       count(*) filter (where geom is null) as sin_geom,
       count(*) filter (where geom is not null and not ST_IsValid(geom)) as invalidas,
       count(*) filter (where geom is not null and (ST_X(geom) = 0 or ST_Y(geom) = 0)) as coord_cero
from public.dengue_m;
''')

with engine.begin() as conn:
    hex_info = pd.read_sql(sql_hex_info, conn)
    casos_info = pd.read_sql(sql_casos_info, conn)

display(hex_info)
display(casos_info)"""
    ),
    code(
        """sql_anios = text('''
select U&"a\\00F1o"::int as anio,
       count(*) as casos,
       count(*) filter (where geom is not null and ST_X(geom) <> 0 and ST_Y(geom) <> 0) as casos_coord_validas
from public.dengue_m
where U&"a\\00F1o" ~ '^[0-9]{4}$'
group by U&"a\\00F1o"::int
order by anio;
''')

with engine.begin() as conn:
    casos_anio = pd.read_sql(sql_anios, conn)

display(casos_anio)

fig, ax = plt.subplots(figsize=(9, 4))
sns.barplot(data=casos_anio, x="anio", y="casos_coord_validas", color="#d95f02", ax=ax)
ax.set_title("Casos de dengue con coordenadas validas por ano")
ax.set_xlabel("Ano")
ax.set_ylabel("Casos")
ax.bar_label(ax.containers[0], fmt="%.0f", fontsize=8)
plt.tight_layout()"""
    ),
    md(
        """## 3. Geoproceso: casos por hexagono y ano

El cruce usa `ST_Covers(hexagono, punto)` para incluir puntos sobre el borde del poligono. Se excluyen coordenadas cero."""
    ),
    code(
        """sql_hex_anio = text('''
with casos_limpios as (
    select U&"a\\00F1o"::int as anio, geom
    from public.dengue_m
    where geom is not null
      and ST_X(geom) <> 0
      and ST_Y(geom) <> 0
      and U&"a\\00F1o" ~ '^[0-9]{4}$'
),
conteos as (
    select h.id_3 as hex_id,
           h."MPIO_CCDGO" as mpio_ccdgo,
           h."MPIO_CNMBR" as municipio,
           c.anio,
           count(*)::int as casos
    from casos_limpios c
    join public.hexagonos h
      on h.geometry && c.geom
     and ST_Covers(h.geometry, c.geom)
    group by h.id_3, h."MPIO_CCDGO", h."MPIO_CNMBR", c.anio
)
select *
from conteos
order by anio, casos desc;
''')

with engine.begin() as conn:
    dengue_hex_anio = pd.read_sql(sql_hex_anio, conn)

print(f"Registros hexagono-ano: {len(dengue_hex_anio):,}")
display(dengue_hex_anio.head(10))"""
    ),
    code(
        """resumen_anio = (
    dengue_hex_anio
    .groupby("anio", as_index=False)
    .agg(
        casos=("casos", "sum"),
        hexagonos_con_casos=("hex_id", "nunique"),
        municipios=("mpio_ccdgo", "nunique"),
        max_casos_hex=("casos", "max"),
    )
)

display(resumen_anio)

fig, axes = plt.subplots(1, 2, figsize=(13, 4))
sns.lineplot(data=resumen_anio, x="anio", y="casos", marker="o", ax=axes[0], color="#d95f02")
axes[0].set_title("Casos por ano en la malla")
axes[0].set_xlabel("Ano")
axes[0].set_ylabel("Casos")

sns.lineplot(data=resumen_anio, x="anio", y="hexagonos_con_casos", marker="o", ax=axes[1], color="#1b9e77")
axes[1].set_title("Hexagonos con casos por ano")
axes[1].set_xlabel("Ano")
axes[1].set_ylabel("Hexagonos")

plt.tight_layout()"""
    ),
    md("## 4. Ranking municipal y hexagonos criticos"),
    code(
        """ranking_municipal = (
    dengue_hex_anio
    .assign(es_2024=lambda df: df["anio"].eq(2024))
    .groupby(["mpio_ccdgo", "municipio"], as_index=False)
    .agg(
        casos_total=("casos", "sum"),
        hexagonos_con_casos=("hex_id", "nunique"),
        casos_2024=("casos", lambda s: s[dengue_hex_anio.loc[s.index, "anio"].eq(2024)].sum()),
    )
    .sort_values("casos_total", ascending=False)
)

display(ranking_municipal.head(20))"""
    ),
    code(
        """ranking_hex = (
    dengue_hex_anio
    .groupby(["hex_id", "mpio_ccdgo", "municipio"], as_index=False)
    .agg(
        casos_total=("casos", "sum"),
        anios_con_casos=("anio", "nunique"),
        casos_2024=("casos", lambda s: s[dengue_hex_anio.loc[s.index, "anio"].eq(2024)].sum()),
    )
    .sort_values("casos_total", ascending=False)
)

display(ranking_hex.head(20))"""
    ),
    md(
        """## 5. Preparar geometria para mapas

Para que Leaflet responda bien, solo se cargan los hexagonos activos en al menos un ano. La malla completa tiene mas de 600 mil poligonos."""
    ),
    code(
        """hex_ids = dengue_hex_anio["hex_id"].dropna().unique().tolist()
print(f"Hexagonos activos en algun ano: {len(hex_ids):,}")

sql_hex_geom = text('''
select id_3 as hex_id,
       "MPIO_CCDGO" as mpio_ccdgo,
       "MPIO_CNMBR" as municipio,
       geometry
from public.hexagonos
where id_3 = any(:hex_ids)
''')

with engine.begin() as conn:
    hex_geom = gpd.read_postgis(sql_hex_geom, conn, geom_col="geometry", params={"hex_ids": hex_ids})

if hex_geom.crs is None:
    hex_geom = hex_geom.set_crs(4326)
elif hex_geom.crs.to_epsg() != 4326:
    hex_geom = hex_geom.to_crs(4326)

print(f"Geometrias cargadas para mapa: {len(hex_geom):,}")
display(hex_geom.head())"""
    ),
    code(
        """hex_map = hex_geom.merge(
    dengue_hex_anio,
    on=["hex_id", "mpio_ccdgo", "municipio"],
    how="inner",
)

hex_map["casos"] = hex_map["casos"].fillna(0).astype(int)
hex_map["anio"] = hex_map["anio"].astype(int)

print(f"Registros geograficos hexagono-ano: {len(hex_map):,}")
display(hex_map.head())"""
    ),
    md("## 6. Mapa rapido en Folium\n\nVista inicial del ano seleccionado dentro del notebook."),
    code(
        """def color_casos(valor, cortes):
    if valor is None or pd.isna(valor):
        return "#f2f2f2"
    if valor > cortes[3]:
        return "#bd0026"
    if valor > cortes[2]:
        return "#f03b20"
    if valor > cortes[1]:
        return "#fd8d3c"
    if valor > cortes[0]:
        return "#fecc5c"
    return "#ffffb2"


def mapa_folium_anio(gdf, anio=ANIO_DEFAULT):
    data = gdf[gdf["anio"] == anio].copy()
    centro = data.geometry.union_all().centroid
    cortes = data["casos"].quantile([0.2, 0.4, 0.6, 0.8]).to_list()

    m = folium.Map(
        location=[centro.y, centro.x],
        zoom_start=9,
        tiles="cartodbpositron",
        control_scale=True,
    )

    folium.GeoJson(
        data,
        name=f"Casos {anio}",
        style_function=lambda feature: {
            "fillColor": color_casos(feature["properties"].get("casos"), cortes),
            "color": "#334155",
            "weight": 0.4,
            "fillOpacity": 0.75,
        },
        tooltip=folium.GeoJsonTooltip(
            fields=["hex_id", "municipio", "anio", "casos"],
            aliases=["Hexagono", "Municipio", "Ano", "Casos"],
            localize=True,
        ),
    ).add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    return m


mapa_folium_anio(hex_map, ANIO_DEFAULT)"""
    ),
    md(
        """## 7. Mapa Leaflet dinamico por ano

Esta celda exporta un HTML con selector de ano, resumen, popups y leyenda dinamica."""
    ),
    code(
        """def gdf_year_to_geojson(gdf, anio):
    cols = ["hex_id", "mpio_ccdgo", "municipio", "anio", "casos", "geometry"]
    data = gdf.loc[gdf["anio"] == anio, cols].copy()
    return json.loads(data.to_json())


def build_leaflet_hex_map(gdf, output_path, anio_default=ANIO_DEFAULT):
    anios = sorted(gdf["anio"].dropna().astype(int).unique().tolist())
    datasets = {str(anio): gdf_year_to_geojson(gdf, anio) for anio in anios}
    total_por_anio = {str(anio): int(gdf.loc[gdf["anio"] == anio, "casos"].sum()) for anio in anios}
    bounds = gdf.total_bounds
    center_lat = float((bounds[1] + bounds[3]) / 2)
    center_lng = float((bounds[0] + bounds[2]) / 2)

    html = f'''<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <title>Dengue por hexagonos</title>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>
    html, body, #map {{ height: 100%; width: 100%; margin: 0; font-family: Arial, sans-serif; }}
    #panel {{ position: absolute; z-index: 9999; top: 18px; left: 18px; width: 270px; background: white; border-radius: 8px; box-shadow: 0 8px 24px rgba(15,23,42,.22); padding: 14px; color: #0f172a; }}
    #panel h3 {{ margin: 0 0 10px; font-size: 16px; }}
    #panel label {{ display: block; font-size: 12px; font-weight: bold; margin-bottom: 4px; color: #475569; }}
    #anioSelect {{ width: 100%; padding: 8px; border: 1px solid #cbd5e1; border-radius: 6px; }}
    #resumen {{ margin-top: 10px; font-size: 12px; line-height: 1.45; background: #f8fafc; padding: 8px; border-radius: 6px; }}
    .legend {{ background: white; padding: 10px; border-radius: 8px; line-height: 1.4; box-shadow: 0 4px 16px rgba(15,23,42,.18); font-size: 12px; }}
    .legend i {{ width: 14px; height: 14px; float: left; margin-right: 6px; opacity: .8; }}
  </style>
</head>
<body>
  <div id="map"></div>
  <div id="panel">
    <h3>Dengue por hexagonos</h3>
    <label for="anioSelect">Ano</label>
    <select id="anioSelect"></select>
    <div id="resumen"></div>
  </div>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const datasets = {json.dumps(datasets, ensure_ascii=False)};
    const totals = {json.dumps(total_por_anio, ensure_ascii=False)};
    const anios = {json.dumps([str(a) for a in anios], ensure_ascii=False)};
    const anioDefault = "{anio_default}";
    const map = L.map("map", {{ preferCanvas: true }}).setView([{center_lat}, {center_lng}], 8);
    L.tileLayer("https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{ attribution: "&copy; OpenStreetMap &copy; CARTO", subdomains: "abcd", maxZoom: 19 }}).addTo(map);

    let layer = null;
    let legend = null;
    function fmt(x) {{ return Number(x || 0).toLocaleString("es-CO"); }}
    function quantiles(values) {{
      const vals = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b);
      if (!vals.length) return [1, 2, 3, 4, 5];
      const q = p => vals[Math.floor((vals.length - 1) * p)];
      return [q(.2), q(.4), q(.6), q(.8), q(.95)];
    }}
    function color(v, bins) {{
      if (v > bins[4]) return "#800026";
      if (v > bins[3]) return "#bd0026";
      if (v > bins[2]) return "#f03b20";
      if (v > bins[1]) return "#fd8d3c";
      if (v > bins[0]) return "#fecc5c";
      return "#ffffb2";
    }}
    function updateLegend(bins) {{
      if (legend) map.removeControl(legend);
      legend = L.control({{ position: "bottomright" }});
      legend.onAdd = function() {{
        const div = L.DomUtil.create("div", "legend");
        const colors = ["#ffffb2", "#fecc5c", "#fd8d3c", "#f03b20", "#bd0026", "#800026"];
        let from = 0;
        div.innerHTML = "<b>Casos por hexagono</b><br>";
        for (let i = 0; i < bins.length; i++) {{
          const to = Math.round(bins[i]);
          div.innerHTML += `<i style="background:${{colors[i]}}"></i>${{fmt(from)}} - ${{fmt(to)}}<br>`;
          from = to + 1;
        }}
        div.innerHTML += `<i style="background:${{colors[5]}}"></i>${{fmt(from)}}+`;
        return div;
      }};
      legend.addTo(map);
    }}
    function renderYear(anio) {{
      const data = datasets[anio];
      if (layer) map.removeLayer(layer);
      const values = data.features.map(f => Number(f.properties.casos || 0));
      const bins = quantiles(values);
      layer = L.geoJSON(data, {{
        style: feature => ({{ fillColor: color(Number(feature.properties.casos || 0), bins), color: "#334155", weight: 0.35, fillOpacity: 0.78 }}),
        onEachFeature: (feature, lyr) => {{
          const p = feature.properties;
          lyr.bindTooltip(`${{p.municipio}}<br>Hex: ${{p.hex_id}}<br>Casos: ${{fmt(p.casos)}}`);
          lyr.bindPopup(`<b>${{p.municipio}}</b><br>Hexagono: ${{p.hex_id}}<br>Ano: ${{p.anio}}<br>Casos: <b>${{fmt(p.casos)}}</b>`);
          lyr.on({{ mouseover: e => e.target.setStyle({{ weight: 1.5, color: "#0f172a" }}), mouseout: e => layer.resetStyle(e.target) }});
        }}
      }}).addTo(map);
      try {{ map.fitBounds(layer.getBounds()); }} catch (err) {{}}
      updateLegend(bins);
      document.getElementById("resumen").innerHTML = `<b>Ano:</b> ${{anio}}<br><b>Casos:</b> ${{fmt(totals[anio])}}<br><b>Hexagonos activos:</b> ${{fmt(data.features.length)}}`;
    }}
    const select = document.getElementById("anioSelect");
    anios.forEach(a => {{
      const option = document.createElement("option");
      option.value = a;
      option.textContent = a;
      if (a === anioDefault) option.selected = true;
      select.appendChild(option);
    }});
    select.addEventListener("change", () => renderYear(select.value));
    renderYear(select.value || anios[0]);
  </script>
</body>
</html>'''
    output_path = Path(output_path)
    output_path.write_text(html, encoding="utf-8")
    return output_path


ruta_mapa_hex = build_leaflet_hex_map(hex_map, OUTPUTS / "mapa_dengue_hexagonos.html", anio_default=ANIO_DEFAULT)
print(f"Mapa guardado en: {ruta_mapa_hex}")"""
    ),
    code('display(IFrame(src=str(ruta_mapa_hex), width="100%", height=650))'),
    md("## 8. Exportar resultados"),
    code(
        """csv_path = OUTPUTS / "dengue_hexagonos_anio.csv"
geojson_2024_path = OUTPUTS / "dengue_hexagonos_2024.geojson"

dengue_hex_anio.to_csv(csv_path, index=False, encoding="utf-8")
hex_map[hex_map["anio"] == ANIO_DEFAULT].to_file(geojson_2024_path, driver="GeoJSON")

print(f"CSV guardado: {csv_path}")
print(f"GeoJSON guardado: {geojson_2024_path}")"""
    ),
    md("## 9. Lecturas iniciales\n\nEspacio para documentar ano critico, municipios prioritarios, hexagonos persistentes y recomendaciones."),
]


notebook = {
    "cells": cells,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "nbformat": 4,
    "nbformat_minor": 5,
}

NB.write_text(json.dumps(notebook, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Notebook guardado: {NB}")
print(f"Celdas: {len(cells)}")
