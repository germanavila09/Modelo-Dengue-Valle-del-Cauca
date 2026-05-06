"""Genera un mapa Leaflet dinamico de casos de dengue por hexagono y ano."""

from __future__ import annotations

import csv
import html
import json
import os
import subprocess
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "outputs" / "mapa_dengue_hexagonos.html"
PSQL = Path(r"C:\Program Files\PostgreSQL\17\bin\psql.exe")


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


def build_datasets(rows: list[dict[str, str]]) -> tuple[dict[str, dict], dict[str, dict]]:
    datasets: dict[str, dict] = {}
    summaries: dict[str, dict] = {}

    for row in rows:
        anio = row["anio"]
        casos = int(row["casos"])
        feature = {
            "type": "Feature",
            "geometry": json.loads(row["geometry_geojson"]),
            "properties": {
                "hex_id": row["hex_id"],
                "mpio_ccdgo": row["mpio_ccdgo"],
                "municipio": row["municipio"],
                "anio": int(anio),
                "casos": casos,
                "casos_total_hex": int(row["casos_total_hex"]),
                "anios_con_casos": int(row["anios_con_casos"]),
            },
        }
        datasets.setdefault(anio, {"type": "FeatureCollection", "features": []})["features"].append(feature)

        summary = summaries.setdefault(
            anio,
            {"casos": 0, "hexagonos": 0, "municipios": set(), "max_hex": 0},
        )
        summary["casos"] += casos
        summary["hexagonos"] += 1
        summary["municipios"].add(row["mpio_ccdgo"])
        summary["max_hex"] = max(summary["max_hex"], casos)

    clean_summaries = {}
    for anio, summary in summaries.items():
        clean_summaries[anio] = {
            "casos": summary["casos"],
            "hexagonos": summary["hexagonos"],
            "municipios": len(summary["municipios"]),
            "max_hex": summary["max_hex"],
        }
    return datasets, clean_summaries


SQL_MAP = """
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
),
persistencia as (
  select hex_id,
         sum(casos)::int as casos_total_hex,
         count(distinct anio)::int as anios_con_casos
  from conteos
  group by hex_id
)
select c.anio,
       c.hex_id,
       c.mpio_ccdgo,
       c.municipio,
       c.casos,
       p.casos_total_hex,
       p.anios_con_casos,
       ST_AsGeoJSON(h.geometry, 6) as geometry_geojson
from conteos c
join persistencia p on p.hex_id = c.hex_id
join public.hexagonos h on h.id_3 = c.hex_id
order by c.anio, c.casos desc
"""


STYLE = """
html, body, #map {
  height: 100%;
  width: 100%;
  margin: 0;
  font-family: "Space Grotesk", "Segoe UI", Arial, sans-serif;
  background: #060a12;
  color: #e2e8f8;
  overflow: hidden;
}
#map { background: #060a12; }
.leaflet-container { background: #060a12 !important; }
.leaflet-control-zoom a {
  background: #0c1221 !important;
  border-color: #162038 !important;
  color: #e2e8f8 !important;
}
#panel {
  position: absolute;
  z-index: 9999;
  top: 0;
  left: 0;
  bottom: 0;
  width: 220px;
  background: #0c1221;
  border-right: 1px solid #162038;
  padding: 18px 16px;
  color: #e2e8f8;
  box-shadow: 10px 0 28px rgba(0, 0, 0, .25);
}
#panel::before {
  content: "";
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  height: 2px;
  background: linear-gradient(90deg, #3b82f6, #22d3ee, #34d399);
}
#panel h2 {
  margin: 0 0 18px;
  font-size: 18px;
  letter-spacing: -0.02em;
}
#panel label {
  display: block;
  font-size: 9px;
  font-weight: 700;
  color: #3d5575;
  margin: 16px 0 6px;
  text-transform: uppercase;
  letter-spacing: 1px;
}
select, button {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid #1c2d4a;
  border-radius: 6px;
  padding: 8px 10px;
  background: #111827;
  color: #e2e8f8;
  font-size: 13px;
  font-family: inherit;
}
select:focus, button:focus { outline: 1px solid #3b82f6; }
button {
  margin-top: 14px;
  background: rgba(59, 130, 246, .14);
  color: #3b82f6;
  border-color: #3b82f6;
  font-weight: 700;
  cursor: pointer;
}
button:hover { background: rgba(59, 130, 246, .22); color: #e2e8f8; }
#summary {
  margin-top: 18px;
  padding-top: 14px;
  border-top: 1px solid #162038;
  font-size: 11px;
  line-height: 1.55;
  color: #94a3b8;
}
#summary strong {
  color: #3d5575;
  font-size: 9px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1px;
}
#summary .summary-value {
  display: block;
  margin: 3px 0 9px;
  color: #e2e8f8;
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.03em;
}
.legend {
  background: #0c1221;
  border: 1px solid #1c2d4a;
  border-radius: 8px;
  box-shadow: 0 8px 22px rgba(0, 0, 0, .35);
  padding: 12px;
  color: #e2e8f8;
  font-size: 12px;
  line-height: 1.5;
}
.legend strong { display: block; margin-bottom: 8px; }
.legend i {
  display: inline-block;
  width: 14px;
  height: 14px;
  border-radius: 3px;
  margin-right: 6px;
  vertical-align: -2px;
}
.map-title {
  position: absolute;
  z-index: 999;
  top: 18px;
  left: 240px;
  padding: 10px 14px;
  border: 1px solid #162038;
  border-radius: 8px;
  background: rgba(12, 18, 33, .86);
  backdrop-filter: blur(8px);
  color: #e2e8f8;
  box-shadow: 0 8px 24px rgba(0, 0, 0, .25);
}
.map-title h1 { margin: 0; font-size: 17px; letter-spacing: -0.02em; }
.map-title p { margin: 3px 0 0; color: #94a3b8; font-size: 11px; }
.leaflet-popup-content-wrapper,
.leaflet-popup-tip {
  background: #0c1221;
  color: #e2e8f8;
  border: 1px solid #1c2d4a;
}
.leaflet-popup-content { font-family: "Space Grotesk", "Segoe UI", Arial, sans-serif; }
.leaflet-tooltip {
  background: #0c1221;
  border: 1px solid #1c2d4a;
  color: #e2e8f8;
}
"""


def build_html(datasets: dict[str, dict], summaries: dict[str, dict]) -> str:
    anios = sorted(datasets.keys(), key=int)
    default_year = "2024" if "2024" in datasets else anios[-1]
    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Mapa dengue por hexagonos</title>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
  <style>{STYLE}</style>
</head>
<body>
  <div id="map"></div>
  <div class="map-title">
    <h1>Casos por hexagonos</h1>
    <p>Microconcentraciones de dengue por municipio y ano</p>
  </div>
  <aside id="panel">
    <h2>Hexagonos</h2>
    <label for="municipioSelect">Municipio</label>
    <select id="municipioSelect"></select>
    <label for="yearSelect">Ano</label>
    <select id="yearSelect"></select>
    <button id="zoomOut">Ver seleccion completa</button>
    <div id="summary"></div>
  </aside>
  <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
  <script>
    const datasets = {json.dumps(datasets, ensure_ascii=False)};
    const summaries = {json.dumps(summaries, ensure_ascii=False)};
    const years = {json.dumps(anios, ensure_ascii=False)};
    const defaultYear = "{html.escape(default_year)}";
    const map = L.map("map", {{ preferCanvas: true, zoomControl: false }}).setView([3.75, -76.45], 8);

    L.control.zoom({{ position: "bottomright" }}).addTo(map);

    L.tileLayer("https://{{s}}.basemaps.cartocdn.com/dark_all/{{z}}/{{x}}/{{y}}{{r}}.png", {{
      attribution: "&copy; OpenStreetMap &copy; CARTO",
      subdomains: "abcd",
      maxZoom: 19
    }}).addTo(map);

    let layer = null;
    let legend = null;
    let fullBounds = null;

    function fmt(value) {{
      return Number(value || 0).toLocaleString("es-CO");
    }}

    function quantiles(values) {{
      const vals = values.filter(v => Number.isFinite(v)).sort((a, b) => a - b);
      if (!vals.length) return [1, 2, 3, 4, 5];
      const q = p => vals[Math.floor((vals.length - 1) * p)];
      return [q(.2), q(.4), q(.6), q(.8), q(.95)];
    }}

    function color(value, bins) {{
      const v = Number(value || 0);
      if (v > bins[4]) return "#800026";
      if (v > bins[3]) return "#ef4444";
      if (v > bins[2]) return "#fbbf24";
      if (v > bins[1]) return "#22d3ee";
      if (v > bins[0]) return "#2563eb";
      return "#15365f";
    }}

    function updateLegend(bins) {{
      if (legend) map.removeControl(legend);
      legend = L.control({{ position: "bottomright" }});
      legend.onAdd = function() {{
        const div = L.DomUtil.create("div", "legend");
        const colors = ["#15365f", "#2563eb", "#22d3ee", "#fbbf24", "#ef4444", "#800026"];
        let from = 1;
        div.innerHTML = "<strong>Casos por hexagono</strong><br>";
        for (let i = 0; i < bins.length; i++) {{
          const to = Math.max(from, Math.round(bins[i]));
          div.innerHTML += `<div><i style="background:${{colors[i]}}"></i>${{fmt(from)}} - ${{fmt(to)}}</div>`;
          from = to + 1;
        }}
        div.innerHTML += `<div><i style="background:${{colors[5]}}"></i>${{fmt(from)}}+</div>`;
        return div;
      }};
      legend.addTo(map);
    }}

    function municipiosAllYears() {{
      const byCode = new Map();
      years.forEach(year => {{
        (datasets[year].features || []).forEach(f => {{
          const p = f.properties;
          byCode.set(p.mpio_ccdgo, p.municipio);
        }});
      }});
      return Array.from(byCode.entries()).sort((a, b) => a[1].localeCompare(b[1], "es"));
    }}

    function populateMunicipios(selectedValue = "__all__") {{
      const selectMun = document.getElementById("municipioSelect");
      selectMun.innerHTML = "";

      const allOption = document.createElement("option");
      allOption.value = "__all__";
      allOption.textContent = "Todos los municipios";
      selectMun.appendChild(allOption);

      municipiosAllYears().forEach(([codigo, nombre]) => {{
        const option = document.createElement("option");
        option.value = codigo;
        option.textContent = nombre;
        selectMun.appendChild(option);
      }});

      const exists = Array.from(selectMun.options).some(option => option.value === selectedValue);
      selectMun.value = exists ? selectedValue : "__all__";
    }}

    function filteredData(year, municipio) {{
      const original = datasets[year];
      if (municipio === "__all__") return original;
      return {{
        type: "FeatureCollection",
        features: original.features.filter(f => f.properties.mpio_ccdgo === municipio)
      }};
    }}

    function summarizeData(data, year, municipio) {{
      if (municipio === "__all__") return summaries[year];
      const features = data.features || [];
      const municipios = new Set(features.map(f => f.properties.mpio_ccdgo));
      return {{
        casos: features.reduce((acc, f) => acc + Number(f.properties.casos || 0), 0),
        hexagonos: features.length,
        municipios: municipios.size,
        max_hex: features.reduce((max, f) => Math.max(max, Number(f.properties.casos || 0)), 0)
      }};
    }}

    function renderSelection() {{
      const year = document.getElementById("yearSelect").value;
      const municipio = document.getElementById("municipioSelect").value || "__all__";
      const data = filteredData(year, municipio);
      const summary = summarizeData(data, year, municipio);
      if (layer) map.removeLayer(layer);
      const values = data.features.map(f => Number(f.properties.casos || 0));
      const bins = quantiles(values);

      layer = L.geoJSON(data, {{
        style: feature => ({{
          color: "#07101d",
          weight: 0.35,
          fillColor: color(feature.properties.casos, bins),
          fillOpacity: 0.82
        }}),
        onEachFeature: (feature, item) => {{
          const p = feature.properties;
          item.bindTooltip(`${{p.municipio}}<br>Hex: ${{p.hex_id}}<br>Casos: ${{fmt(p.casos)}}`);
          item.bindPopup(`
            <div style="min-width:220px;font-family:Space Grotesk,Segoe UI,Arial,sans-serif">
              <strong>${{p.municipio}}</strong><br>
              Codigo DANE: ${{p.mpio_ccdgo}}<br>
              Hexagono: ${{p.hex_id}}<br>
              Ano: ${{p.anio}}<br>
              Casos ano: <strong>${{fmt(p.casos)}}</strong><br>
              Casos acumulados: ${{fmt(p.casos_total_hex)}}<br>
              Anos con casos: ${{fmt(p.anios_con_casos)}}
            </div>
          `);
          item.on({{
            mouseover: e => e.target.setStyle({{ weight: 1.8, color: "#e2e8f8", fillOpacity: 0.96 }}),
            mouseout: e => layer.resetStyle(e.target)
          }});
        }}
      }}).addTo(map);

      fullBounds = layer.getBounds();
      if (data.features.length) {{
        map.fitBounds(fullBounds, {{ padding: [22, 22] }});
      }}
      updateLegend(bins);
      const municipioLabel = municipio === "__all__"
        ? "Todos"
        : (data.features[0]?.properties?.municipio || municipio);
      document.getElementById("summary").innerHTML =
        `<strong>Municipio</strong><span class="summary-value">${{municipioLabel}}</span>` +
        `<strong>Ano</strong><span class="summary-value">${{year}}</span>` +
        `<strong>Casos</strong><span class="summary-value">${{fmt(summary.casos)}}</span>` +
        `<strong>Hexagonos activos</strong><span class="summary-value">${{fmt(summary.hexagonos)}}</span>` +
        `<strong>Maximo en un hexagono</strong><span class="summary-value">${{fmt(summary.max_hex)}}</span>`;
    }}

    const select = document.getElementById("yearSelect");
    const selectMun = document.getElementById("municipioSelect");
    years.forEach(year => {{
      const option = document.createElement("option");
      option.value = year;
      option.textContent = year;
      if (year === defaultYear) option.selected = true;
      select.appendChild(option);
    }});

    populateMunicipios();
    select.addEventListener("change", () => {{
      renderSelection();
    }});
    selectMun.addEventListener("change", renderSelection);
    document.getElementById("zoomOut").addEventListener("click", () => {{
      if (fullBounds) map.fitBounds(fullBounds, {{ padding: [22, 22] }});
    }});

    renderSelection();
  </script>
</body>
</html>"""


def main() -> None:
    rows = query(SQL_MAP)
    datasets, summaries = build_datasets(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_html(datasets, summaries), encoding="utf-8")
    print(f"Mapa guardado: {OUTPUT}")
    print(f"Anios: {', '.join(sorted(datasets.keys(), key=int))}")
    print(f"Features totales: {sum(len(d['features']) for d in datasets.values())}")


if __name__ == "__main__":
    main()
