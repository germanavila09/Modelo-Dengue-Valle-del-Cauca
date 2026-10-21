"""Informe HTML interactivo del Objetivo 1 (componente de clústeres espaciales).

Lee las salidas de ``scripts/clusters_hexagonos.py`` y escribe un único HTML
autocontenido (solo Leaflet y teselas base se cargan de la red):

    outputs/clusters_hexagonos/informe_objetivo1.html

Privacidad: el informe solo usa archivos publicables y agregados municipales.
No lee ``interno/`` (conteos por hexágono) ni muestra atípicos HL/LH.

Uso:
    python scripts/informe_objetivo1.py
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
ENTRADA = ROOT / "outputs" / "clusters_hexagonos"
SALIDA = ENTRADA / "informe_objetivo1.html"

ORDEN_MUNICIPIOS = ["Palmira", "Guadalajara de Buga", "Tuluá", "Jamundí"]
CORTO = {"Guadalajara de Buga": "Buga"}


def _leer_csv(nombre: str) -> pd.DataFrame:
    ruta = ENTRADA / nombre
    if not ruta.exists():
        sys.exit(f"Falta {ruta}. Ejecuta primero scripts/clusters_hexagonos.py.")
    return pd.read_csv(ruta)


def _registros(df: pd.DataFrame) -> list[dict]:
    return json.loads(df.to_json(orient="records", force_ascii=False))


def construir_datos() -> dict:
    metricas = _leer_csv("metricas_municipio_anio.csv")
    columnas = ["variante", "municipio", "anio", "casos", "hex_huella", "hex_con_casos", "moran_I", "moran_p",
                "hex_HH", "hex_HH_fdr", "hex_LL", "pct_casos_en_HH", "pct_area_HH",
                "hex_gi_caliente", "hex_gi_caliente_fdr"]
    metricas = metricas[columnas].copy()
    metricas["anio"] = metricas["anio"].astype(str)

    persistencia = _leer_csv("persistencia_resumen.csv")
    calidad = _leer_csv("calidad_geocodificacion.csv")
    area = _leer_csv("area_estudio.csv")
    clima_mpio = _leer_csv("clima_anual_municipio.csv")
    clima_reg = _leer_csv("clima_anual_regional.csv")
    asociacion = _leer_csv("asociacion_clima_clusters.csv")
    meta = json.loads((ENTRADA / "metadata.json").read_text(encoding="utf-8"))
    zonas = json.loads((ENTRADA / "zonas_HH_publicable.geojson").read_text(encoding="utf-8"))
    pers_geo = json.loads((ENTRADA / "persistencia_publicable.geojson").read_text(encoding="utf-8"))
    ruta_lisa = ENTRADA / "lisa_publicable.geojson"
    if not ruta_lisa.exists():
        sys.exit(f"Falta {ruta_lisa}. Ejecuta de nuevo scripts/clusters_hexagonos.py.")
    lisa_geo = json.loads(ruta_lisa.read_text(encoding="utf-8"))

    # Garantía de privacidad: las capas publicables no pueden traer conteos.
    for capa, nombre in ((zonas, "zonas"), (pers_geo, "persistencia"), (lisa_geo, "lisa")):
        for f in capa["features"]:
            prohibidas = {k for k in f["properties"] if "caso" in k.lower()}
            if prohibidas:
                sys.exit(f"La capa {nombre} contiene campos de conteo {prohibidas}; no se genera el informe.")

    clima_mpio = clima_mpio[clima_mpio["anio"].between(2019, 2023)]
    clima_reg = clima_reg[clima_reg["anio"].between(2019, 2023)]
    nombres = calidad.set_index("mpio_ccdgo")["municipio"].to_dict()
    clima_mpio = clima_mpio.assign(municipio=clima_mpio["mpio_ccdgo"].map(nombres))

    return {
        "generado": dt.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "meta": meta,
        "municipios": ORDEN_MUNICIPIOS,
        "corto": CORTO,
        "metricas": _registros(metricas),
        "persistencia": _registros(persistencia),
        "calidad": _registros(calidad),
        "area": _registros(area),
        "clima_mpio": _registros(clima_mpio.round(1)),
        "clima_reg": _registros(clima_reg.round(1)),
        "asociacion": _registros(asociacion),
        "zonas": zonas,
        "pers_geo": pers_geo,
        "lisa_geo": lisa_geo,
    }


PLANTILLA = r"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Clústeres de dengue · Objetivo 1</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css">
<style>
:root{
  color-scheme: light;
  --page:#f9f9f7; --surface:#fcfcfb; --surface-2:#f3f2ee;
  --ink:#0b0b0b; --ink-2:#52514e; --muted:#6f6d68;
  --grid:#e1e0d9; --axis:#c3c2b7; --ring:rgba(11,11,11,.10);
  --s1:#2a78d6; --s2:#eb6834; --s3:#1baf7a; --s4:#eda100;
  --l-hh:#b2182b; --l-ll:#2166ac; --l-hl:#ef8a62; --l-lh:#67a9cf;
  --hh:#b2182b; --p1:#ee9068; --p2:#d6604d; --p3:#b2182b; --never:#d9d8d2;
  --area:#a8a69e; --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --geo-ok:#2a78d6; --geo-cent:#f0a36e; --geo-def:#c4501f;
  --seq0:#eef4fc; --seq1:#cde2fb; --seq2:#86b6ef; --seq3:#3987e5; --seq4:#1c5cab;
}
@media (prefers-color-scheme: dark){
  :root:where(:not([data-theme="light"])){
    color-scheme: dark;
    --page:#0d0d0d; --surface:#1a1a19; --surface-2:#232321;
    --ink:#f0efec; --ink-2:#c3c2b7; --muted:#9a988f;
    --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
    --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
    --l-hh:#e8606b; --l-ll:#4a8fe0; --l-hl:#f2a07e; --l-lh:#8ec3e6;
  --hh:#e8606b; --p1:#9a3324; --p2:#cf5443; --p3:#f28b7a; --never:#383835;
    --area:#6f6d68; --geo-ok:#3987e5; --geo-cent:#b4683c; --geo-def:#ef8a5c;
    --seq0:#1d2633; --seq1:#184f95; --seq2:#256abf; --seq3:#5598e7; --seq4:#b7d3f6;
  }
}
:root[data-theme="dark"]{
  color-scheme: dark;
  --l-hh:#e8606b; --l-ll:#4a8fe0; --l-hl:#f2a07e; --l-lh:#8ec3e6;
  --page:#0d0d0d; --surface:#1a1a19; --surface-2:#232321;
  --ink:#f0efec; --ink-2:#c3c2b7; --muted:#9a988f;
  --grid:#2c2c2a; --axis:#383835; --ring:rgba(255,255,255,.10);
  --s1:#3987e5; --s2:#d95926; --s3:#199e70; --s4:#c98500;
  --hh:#e8606b; --p1:#9a3324; --p2:#cf5443; --p3:#f28b7a; --never:#383835;
  --area:#6f6d68; --geo-ok:#3987e5; --geo-cent:#b4683c; --geo-def:#ef8a5c;
  --seq0:#1d2633; --seq1:#184f95; --seq2:#256abf; --seq3:#5598e7; --seq4:#b7d3f6;
}
*{box-sizing:border-box}
html,body{margin:0;background:var(--page);color:var(--ink);
  font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
a{color:var(--s1)}
.wrap{max-width:1120px;margin:0 auto;padding:28px 16px 64px}
header.top{display:flex;justify-content:space-between;gap:16px;align-items:flex-start;flex-wrap:wrap}
.eyebrow{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted);margin:0 0 6px}
h1{font-size:28px;line-height:1.2;margin:0 0 8px;max-width:760px}
h2{font-size:20px;margin:0 0 4px}
h3{font-size:15px;margin:0 0 8px}
.lead{color:var(--ink-2);max-width:780px;margin:0}
.btn{font:inherit;font-size:13px;border:1px solid var(--ring);background:var(--surface);color:var(--ink);
  border-radius:8px;padding:6px 10px;cursor:pointer}
.btn[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
nav.toc{display:flex;gap:6px;flex-wrap:wrap;margin:20px 0 8px}
nav.toc a{font-size:13px;text-decoration:none;color:var(--ink-2);border:1px solid var(--ring);
  border-radius:999px;padding:4px 10px;background:var(--surface)}
section{background:var(--surface);border:1px solid var(--ring);border-radius:14px;padding:22px;margin-top:18px}
.sub{color:var(--ink-2);margin:0 0 16px;max-width:820px}
.grid{display:grid;gap:14px}
.g4{grid-template-columns:repeat(4,minmax(0,1fr))}
.g2{grid-template-columns:repeat(2,minmax(0,1fr))}
@media (max-width:860px){.g4{grid-template-columns:repeat(2,minmax(0,1fr))}.g2{grid-template-columns:1fr}}
@media (max-width:520px){.g4{grid-template-columns:1fr}}
.tile{background:var(--surface-2);border-radius:10px;padding:14px}
.tile .v{font-size:30px;font-weight:650;line-height:1.1}
.tile .l{color:var(--ink-2);font-size:13px;margin-top:4px}
.answer{border-left:3px solid var(--hh);padding:2px 0 2px 14px;margin:18px 0 0}
.answer p{margin:0 0 8px}
.controls{display:flex;gap:10px;flex-wrap:wrap;align-items:center;margin:0 0 14px}
.controls label{font-size:13px;color:var(--ink-2)}
select{font:inherit;font-size:14px;padding:6px 8px;border-radius:8px;border:1px solid var(--ring);
  background:var(--surface);color:var(--ink)}
.seg{display:inline-flex;border:1px solid var(--ring);border-radius:8px;overflow:hidden}
.seg button{font:inherit;font-size:13px;border:0;background:var(--surface);color:var(--ink-2);padding:6px 10px;cursor:pointer}
.seg button[aria-pressed="true"]{background:var(--ink);color:var(--surface)}
#map{height:520px;border-radius:10px;border:1px solid var(--ring)}
.legend{display:flex;gap:14px;flex-wrap:wrap;font-size:13px;color:var(--ink-2);margin-top:10px}
.key{display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:6px;vertical-align:-1px}
.key.line{height:2px;width:16px;border-radius:2px;vertical-align:3px}
.chart{position:relative;width:100%}
.chart svg{display:block;width:100%;height:auto;overflow:visible}
.chart text{fill:var(--muted);font-size:12px}
.chart .lbl{fill:var(--ink-2);font-size:12px}
.chart .gridl{stroke:var(--grid);stroke-width:1}
.chart .axisl{stroke:var(--axis);stroke-width:1}
.tip{position:absolute;pointer-events:none;background:var(--surface);border:1px solid var(--ring);border-radius:8px;
  padding:8px 10px;font-size:12.5px;box-shadow:0 4px 18px rgba(0,0,0,.12);opacity:0;transition:opacity .08s;min-width:150px;z-index:5}
.tip .t{color:var(--ink-2);margin-bottom:4px}
.tip .r{display:flex;align-items:center;gap:6px;color:var(--ink-2)}
.tip .r b{color:var(--ink);font-weight:650;min-width:44px}
table{width:100%;border-collapse:collapse;font-size:13px}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--grid)}
th{color:var(--ink-2);font-weight:600}
td.n,th.n{text-align:right;font-variant-numeric:tabular-nums}
details{margin-top:12px}
.tw{overflow-x:auto}
summary{cursor:pointer;color:var(--ink-2);font-size:13px}
.status{display:inline-flex;align-items:center;gap:6px;font-weight:600;font-size:13px}
.dot{width:10px;height:10px;border-radius:50%;display:inline-block}
.note{font-size:13px;color:var(--ink-2);background:var(--surface-2);border-radius:10px;padding:12px 14px}
ul.clean{margin:0;padding-left:18px}
ul.clean li{margin:4px 0}
footer{color:var(--muted);font-size:12.5px;margin-top:22px}
.leaflet-container{background:var(--surface-2)}
.leaflet-tooltip{font:12.5px system-ui,-apple-system,"Segoe UI",sans-serif}
</style>
</head>
<body>
<div class="wrap">
<header class="top">
  <div>
    <p class="eyebrow">Observatorio GeoSalud · Objetivo 1 · componente espacial</p>
    <h1>¿Dónde se agrupa el dengue dentro de Palmira, Buga, Tuluá y Jamundí?</h1>
    <p class="lead">Clústeres espaciales de casos de dengue en hexágonos de 200&nbsp;m, 2019–2023, con autocorrelación espacial global (I de Moran) y local (LISA, Gi*). Incluye la revisión de la calidad de geocodificación y de los datos climáticos disponibles para la asociación.</p>
  </div>
  <button class="btn" id="tema" type="button" aria-pressed="false">Tema oscuro</button>
</header>

<nav class="toc" aria-label="Secciones">
  <a href="#respuesta">Respuesta</a><a href="#datos">Calidad de datos</a><a href="#mapa">Mapa</a>
  <a href="#global">Autocorrelación global</a><a href="#concentracion">Concentración</a>
  <a href="#persistencia">Persistencia</a><a href="#clima">Clima</a><a href="#alcance">Alcance del objetivo</a>
  <a href="#metodo">Método</a>
</nav>

<section id="respuesta">
  <h2>Respuesta corta</h2>
  <div class="grid g4" id="tiles" style="margin-top:14px"></div>
  <div class="answer" id="hallazgos"></div>
</section>

<section id="datos">
  <h2>Calidad de los datos de ubicación</h2>
  <p class="sub">Muchos casos comparten exactamente la misma coordenada. Con cientos de casos en un punto se trata de una ubicación por defecto del municipio y se excluye; entre 10 y 99 casos probablemente es el centroide de un barrio: se conserva en el análisis principal y se retira en el de sensibilidad.</p>
  <div class="grid g2">
    <div>
      <h3>Composición de los casos geocodificados, 2019–2023</h3>
      <div class="chart" id="ch-geo"></div>
      <div class="legend" id="lg-geo"></div>
      <details><summary>Ver tabla</summary><div class="tw"><table id="tb-geo"></table></div></details>
    </div>
    <div>
      <h3>Área de estudio</h3>
      <div class="tw"><table id="tb-area"></table></div>
      <p class="sub" style="margin-top:10px;font-size:13px">El área urbana son los grupos contiguos de 10 o más hexágonos con algún caso entre 2019 y 2026. Los hexágonos dispersos (sobre todo rurales) quedan fuera del análisis de vecindad.</p>
    </div>
  </div>
</section>

<section id="mapa">
  <h2>Mapa de clústeres</h2>
  <p class="sub">Mapa de clústeres LISA (alto-alto: hexágonos con muchos casos rodeados de hexágonos con muchos casos; bajo-bajo: pocos casos rodeados de pocos casos), zonas alto-alto por año y persistencia de los focos entre 2019 y 2023. No se muestran conteos; los atípicos (alto-bajo, bajo-alto) solo aparecen si el hexágono tiene al menos <span class="minc"></span> casos, y las zonas y la persistencia exigen al menos <span class="minc"></span> casos.</p>
  <div class="controls">
    <label for="m-mpio">Municipio</label>
    <select id="m-mpio"></select>
    <label for="m-capa">Capa</label>
    <select id="m-capa"></select>
  </div>
  <div id="map" role="region" aria-label="Mapa de clústeres de dengue"></div>
  <div class="legend" id="lg-map"></div>
</section>

<section id="global">
  <h2>Autocorrelación espacial global</h2>
  <p class="sub">I de Moran de los casos por hexágono en cada año. Valores mayores que cero indican que los hexágonos con muchos casos tienden a estar juntos. Punto relleno: significativo (p&nbsp;&lt;&nbsp;0,05, 999 permutaciones); punto hueco: no significativo.</p>
  <div class="controls">
    <span class="seg" role="group" aria-label="Variante del análisis" id="seg-var"></span>
  </div>
  <div class="chart" id="ch-moran"></div>
  <div class="legend" id="lg-moran"></div>
  <details><summary>Ver tabla por municipio y año</summary><div class="tw"><table id="tb-moran"></table></div></details>
</section>

<section id="concentracion">
  <h2>Concentración de casos en los focos</h2>
  <p class="sub">Acumulado 2019–2023: porcentaje del área urbana que ocupan los hexágonos alto-alto frente al porcentaje de casos que concentran. Cuanto mayor la distancia entre ambas barras, más concentrado está el dengue.</p>
  <div class="chart" id="ch-conc"></div>
  <div class="legend" id="lg-conc"></div>
</section>

<section id="persistencia">
  <h2>Persistencia de los focos</h2>
  <p class="sub">Porcentaje de los casos 2019–2023 de cada municipio según cuántos años su hexágono fue núcleo alto-alto. Los focos persistentes son candidatos naturales para priorizar control vectorial y vigilancia entomológica.</p>
  <div class="chart" id="ch-pers"></div>
  <div class="legend" id="lg-pers"></div>
  <details><summary>Ver tabla</summary><div class="tw"><table id="tb-pers"></table></div></details>
</section>

<section id="clima">
  <h2>Clima: ¿se puede estimar la asociación?</h2>
  <p class="sub" id="clima-txt"></p>
  <div class="grid g2">
    <div>
      <h3>Meses con dato climático válido por municipio</h3>
      <div class="chart" id="ch-clima"></div>
      <div class="legend" id="lg-clima"></div>
    </div>
    <div>
      <h3>Problemas encontrados en la fuente</h3>
      <ul class="clean" id="clima-prob"></ul>
      <details><summary>Correlaciones exploratorias (Spearman)</summary><div class="tw"><table id="tb-asoc"></table></div></details>
    </div>
  </div>
</section>

<section id="alcance">
  <h2>¿Qué parte del Objetivo 1 queda respondida?</h2>
  <div class="tw"><table id="tb-alcance"></table></div>
</section>

<section id="metodo">
  <h2>Método y limitaciones</h2>
  <div class="grid g2">
    <div>
      <h3>Método</h3>
      <ul class="clean" id="metodo-lista"></ul>
    </div>
    <div>
      <h3>Limitaciones</h3>
      <ul class="clean">
        <li><b>Sin población por hexágono:</b> los focos son de casos, no de tasas; parte del patrón puede reflejar densidad de población. El paso siguiente es estimarla con las manzanas del censo DANE 2018.</li>
        <li><b>Geocodificación:</b> los puntos por defecto se excluyen y los probables centroides de barrio se evalúan con la variante de sensibilidad; ambas variantes llegan a la misma conclusión.</li>
        <li><b>Escala anual:</b> el clima actúa con rezagos de semanas; la asociación requiere conteos mensuales o semanales por hexágono.</li>
        <li><b>Pruebas múltiples:</b> con corrección FDR sobreviven pocos hexágonos; los focos deben leerse como exploratorios.</li>
      </ul>
      <div class="note" style="margin-top:12px"><b>Privacidad.</b> Este informe usa solo agregados municipales y capas sin conteos. No contiene identificadores, direcciones, fechas ni coordenadas de casos.</div>
    </div>
  </div>
</section>

<footer id="pie"></footer>
</div>

<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script>
const D = __DATA__;
const css = n => getComputedStyle(document.documentElement).getPropertyValue(n).trim();
const short = m => D.corto[m] || m;
const fmt = (v, d=1) => v == null || Number.isNaN(v) ? '—' : Number(v).toLocaleString('es-CO', {minimumFractionDigits:d, maximumFractionDigits:d});
const fint = v => Number(v).toLocaleString('es-CO');
const SERIE = {'Palmira':'--s1','Guadalajara de Buga':'--s2','Tuluá':'--s3','Jamundí':'--s4'};
const ANIOS = ['2019','2020','2021','2022','2023'];
let variante = 'principal';
const NS = 'http://www.w3.org/2000/svg';
const el = (tag, attrs={}, parent) => { const e = document.createElementNS(NS, tag); for (const k in attrs) e.setAttribute(k, attrs[k]); if (parent) parent.appendChild(e); return e; };
document.querySelectorAll('.minc').forEach(s => s.textContent = D.meta.min_casos_publicacion);

function inkFor(hex){
  const h = hex.replace('#', ''); if (h.length < 6) return '#fff';
  const [r, g, b] = [0, 2, 4].map(i => { const c = parseInt(h.slice(i, i + 2), 16) / 255; return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; });
  const L = 0.2126 * r + 0.7152 * g + 0.0722 * b; return L > 0.36 ? '#141414' : '#ffffff';
}
// ── Tooltip ────────────────────────────────────────────────────────────────
function tooltip(container){
  const t = document.createElement('div'); t.className = 'tip'; container.appendChild(t);
  return {
    show(x, y, title, rows){
      t.replaceChildren();
      const h = document.createElement('div'); h.className = 't'; h.textContent = title; t.appendChild(h);
      rows.forEach(r => {
        const row = document.createElement('div'); row.className = 'r';
        if (r.color){ const k = document.createElement('span'); k.className = 'key ' + (r.line ? 'line' : ''); k.style.background = r.color; row.appendChild(k); }
        const b = document.createElement('b'); b.textContent = r.value; row.appendChild(b);
        const s = document.createElement('span'); s.textContent = r.label; row.appendChild(s);
        t.appendChild(row);
      });
      const w = container.clientWidth, tw = t.offsetWidth || 160;
      t.style.left = Math.min(Math.max(x + 14, 0), w - tw - 4) + 'px'; t.style.top = Math.max(y - 10, 0) + 'px'; t.style.opacity = 1;
    },
    hide(){ t.style.opacity = 0; }
  };
}
function legend(id, items){
  const c = document.getElementById(id); c.replaceChildren();
  items.forEach(it => { const s = document.createElement('span'); const k = document.createElement('span');
    k.className = 'key' + (it.line ? ' line' : ''); k.style.background = it.color; if (it.hollow){k.style.background='transparent';k.style.border='2px solid '+it.color;k.style.borderRadius='50%';}
    if (it.dot){k.style.borderRadius='50%';}
    s.appendChild(k); s.appendChild(document.createTextNode(it.label)); c.appendChild(s); });
}

function tabla(id, cab, filas, numDesde=1){
  const t = document.getElementById(id); t.replaceChildren(); const hr = t.insertRow();
  cab.forEach((h, i) => { const th = document.createElement('th'); th.textContent = h; if (i >= numDesde) th.className = 'n'; hr.appendChild(th); });
  filas.forEach(f => { const tr = t.insertRow(); f.forEach((v, i) => { const td = tr.insertCell(); td.textContent = v; if (i >= numDesde) td.className = 'n'; }); });
}

// ── Respuesta corta ────────────────────────────────────────────────────────
function respuesta(){
  const pooled = D.metricas.filter(r => r.variante === 'principal' && r.anio === '2019-2023');
  const sens = D.metricas.filter(r => r.variante === 'sensibilidad' && r.anio === '2019-2023');
  const casos = pooled.reduce((a, r) => a + r.casos, 0);
  const imin = Math.min(...pooled.map(r => r.moran_I)), imax = Math.max(...pooled.map(r => r.moran_I));
  const smin = Math.min(...sens.map(r => r.moran_I)), smax = Math.max(...sens.map(r => r.moran_I));
  const amin = Math.min(...pooled.map(r => r.pct_area_HH)), amax = Math.max(...pooled.map(r => r.pct_area_HH));
  const cmin = Math.min(...pooled.map(r => r.pct_casos_en_HH)), cmax = Math.max(...pooled.map(r => r.pct_casos_en_HH));
  const sig = pooled.filter(r => r.moran_p < 0.05).length;
  const tiles = [
    [fmt(imin,2) + '–' + fmt(imax,2), `I de Moran 2019–2023 (${sig} de ${pooled.length} municipios con p<0,05)`],
    [fmt(amin,0) + '–' + fmt(amax,0) + ' %', 'del área urbana está en focos alto-alto'],
    [fmt(cmin,0) + '–' + fmt(cmax,0) + ' %', 'de los casos se concentra en esos focos'],
    [fint(casos), 'casos analizados en las cuatro cabeceras'],
  ];
  const c = document.getElementById('tiles');
  tiles.forEach(([v, l]) => { const d = document.createElement('div'); d.className = 'tile';
    const a = document.createElement('div'); a.className = 'v'; a.textContent = v;
    const b = document.createElement('div'); b.className = 'l'; b.textContent = l; d.append(a, b); c.appendChild(d); });

  // años epidémicos con autocorrelación significativa
  const porAnio = ANIOS.map(a => ({a, n: D.metricas.filter(r => r.variante === 'principal' && r.anio === a && r.moran_p < 0.05).length,
    casos: D.metricas.filter(r => r.variante === 'principal' && r.anio === a).reduce((s, r) => s + r.casos, 0)}));
  const fuertes = porAnio.filter(x => x.n >= 3).map(x => x.a);
  const debiles = porAnio.filter(x => x.n <= 1).map(x => x.a);
  const pers = D.persistencia.filter(r => r.variante === 'principal' && r.clase === 'persistente').sort((a, b) => b.pct_casos_mpio - a.pct_casos_mpio);
  const top = pers.slice(0, 2).map(r => `${short(r.municipio)} (${r.hexagonos} hexágonos, ${fmt(r.pct_casos_mpio)} % de sus casos)`).join(' y ');
  const peorGeo = [...D.calidad].sort((a, b) => b.pct_sumidero - a.pct_sumidero)[0];
  const parrafos = [
    `<b>Sí hay clústeres espaciales de dengue a escala de 200 m en los cuatro municipios.</b> En el acumulado 2019–2023 el I de Moran va de ${fmt(imin,2)} a ${fmt(imax,2)} y sube a ${fmt(smin,2)}–${fmt(smax,2)} al retirar los probables centroides de barrio, de modo que el resultado no depende de la geocodificación imprecisa.`,
    `<b>Los clústeres aparecen con las epidemias.</b> La autocorrelación es significativa en la mayoría de municipios en ${fuertes.join(', ') || '—'} y casi desaparece en ${debiles.join(', ') || '—'}, años con pocos casos.`,
    `<b>Los focos se desplazan más de lo que persisten.</b> La mayoría de hexágonos alto-alto lo son un solo año; los focos que se repiten tres años o más se concentran en ${top || '—'}.`,
    `<b>La asociación con el clima no puede estimarse con los datos actuales</b> (cobertura incompleta y valores inválidos en la fuente climática) y la ubicación de ${fmt(peorGeo.pct_sumidero)} % de los casos de ${short(peorGeo.municipio)} es un punto por defecto. Ver las secciones de calidad y clima.`,
  ];
  const h = document.getElementById('hallazgos');
  parrafos.forEach(p => { const e = document.createElement('p'); e.innerHTML = p; h.appendChild(e); });
}

// ── Barras apiladas 100 % (horizontal) ─────────────────────────────────────
function stacked(id, rows, segs, fmtv){
  const c = document.getElementById(id); c.replaceChildren();
  const W = Math.max(300, c.clientWidth || 560), rowH = 30, gap = 10, left = 84, right = 4, top = 4;
  const H = top + rows.length * (rowH + gap);
  const svg = el('svg', {viewBox:`0 0 ${W} ${H}`, role:'img'}, c);
  const tip = tooltip(c);
  rows.forEach((r, i) => {
    const y = top + i * (rowH + gap);
    const t = el('text', {x:left - 10, y:y + rowH/2 + 4, 'text-anchor':'end', class:'lbl'}, svg); t.textContent = r.label;
    const total = segs.reduce((a, s) => a + (r[s.key] || 0), 0) || 1;
    let x = left; const span = W - left - right;
    segs.forEach((s, j) => {
      const w = span * (r[s.key] || 0) / total; if (w <= 0) return;
      const g = el('g', {tabindex:0}, svg);
      const rect = el('rect', {x: x + (j ? 1 : 0), y, width: Math.max(w - (j ? 2 : 1), 0.5), height: rowH, rx: 4, fill: css(s.color)}, g);
      const pct = 100 * (r[s.key] || 0) / total;
      if (w > 46){ const tx = el('text', {x: x + w/2, y: y + rowH/2 + 4, 'text-anchor':'middle', style:`fill:${inkFor(css(s.color))};font-size:12px;font-weight:600`}, g); tx.textContent = fmt(pct,0) + ' %'; }
      const show = ev => { const b = c.getBoundingClientRect(); tip.show((ev.clientX || b.left + (x + w/2) * b.width / W) - b.left, (ev.clientY || b.top + y * b.height / H) - b.top, r.label,
        [{value: fmt(pct) + ' %', label: s.label, color: css(s.color)}, ...(fmtv ? [{value: fmtv(r[s.key]), label: 'casos'}] : [])]); rect.setAttribute('opacity', .85); };
      const hide = () => { tip.hide(); rect.setAttribute('opacity', 1); };
      g.addEventListener('pointermove', show); g.addEventListener('pointerleave', hide); g.addEventListener('focus', show); g.addEventListener('blur', hide);
      x += w;
    });
  });
  legend('lg-' + id.slice(3), segs.map(s => ({label: s.label, color: css(s.color)})));
}

function calidad(){
  const rows = D.municipios.map(m => { const r = D.calidad.find(x => x.municipio === m);
    return {label: short(m), ok: r.casos - r.casos_sumidero - r.casos_centroide, cent: r.casos_centroide, def: r.casos_sumidero}; });
  stacked('ch-geo', rows, [
    {key:'ok', label:'Ubicación individual', color:'--geo-ok'},
    {key:'cent', label:'Probable centroide de barrio', color:'--geo-cent', ink:'#2b1608'},
    {key:'def', label:'Punto por defecto (excluido)', color:'--geo-def'}], fint);
  tabla('tb-geo', ['Municipio', 'Casos', 'Ubicación individual', 'Probable centroide', 'Punto por defecto'],
    D.municipios.map(m => { const r = D.calidad.find(x => x.municipio === m); const ok = r.casos - r.casos_sumidero - r.casos_centroide;
      return [short(m), fint(r.casos), `${fint(ok)} (${fmt(100 * ok / r.casos)} %)`, `${fint(r.casos_centroide)} (${fmt(r.pct_centroide)} %)`, `${fint(r.casos_sumidero)} (${fmt(r.pct_sumidero)} %)`]; }));
  const t = document.getElementById('tb-area'); t.replaceChildren();
  const head = t.insertRow(); ['Municipio','Hexágonos urbanos','Dispersos excluidos','Casos excluidos'].forEach((h, i) => { const th = document.createElement('th'); th.textContent = h; if (i) th.className = 'n'; head.appendChild(th); });
  D.municipios.forEach(m => { const r = D.area.find(x => x.municipio === m); const tr = t.insertRow();
    [short(m), fint(r.hex_area_urbana), fint(r.hex_dispersos_excluidos), `${fint(r.casos_2019_2023_excluidos)} (${fmt(r.pct_casos_excluidos)} %)`].forEach((v, i) => { const td = tr.insertCell(); td.textContent = v; if (i) td.className = 'n'; }); });
}

// ── Línea: I de Moran ──────────────────────────────────────────────────────
function moran(){
  const c = document.getElementById('ch-moran'); c.replaceChildren();
  const W = Math.max(320, c.clientWidth || 760), H = 300, L = 46, R = 84, T = 12, B = 30;
  const rows = D.metricas.filter(r => r.variante === variante && r.anio !== '2019-2023');
  const ys = rows.map(r => r.moran_I); const ymax = Math.max(0.1, Math.ceil(Math.max(...ys) * 10) / 10), ymin = Math.min(0, Math.floor(Math.min(...ys) * 10) / 10);
  const X = i => L + i * (W - L - R) / (ANIOS.length - 1), Y = v => T + (ymax - v) * (H - T - B) / (ymax - ymin);
  const svg = el('svg', {viewBox:`0 0 ${W} ${H}`, role:'img', 'aria-label':'I de Moran por año y municipio'}, c);
  for (let v = ymin; v <= ymax + 1e-9; v += 0.1){ el('line', {x1:L, x2:W-R, y1:Y(v), y2:Y(v), class: Math.abs(v) < 1e-9 ? 'axisl' : 'gridl'}, svg);
    const t = el('text', {x:L - 8, y:Y(v) + 4, 'text-anchor':'end'}, svg); t.textContent = fmt(v, 1); }
  ANIOS.forEach((a, i) => { const t = el('text', {x:X(i), y:H - 8, 'text-anchor':'middle'}, svg); t.textContent = a; });
  const labels = [];
  D.municipios.forEach(m => {
    const col = css(SERIE[m]);
    const pts = ANIOS.map((a, i) => { const r = rows.find(x => x.municipio === m && x.anio === a); return r ? {i, a, v: r.moran_I, p: r.moran_p, r} : null; }).filter(Boolean);
    el('path', {d: pts.map((p, k) => (k ? 'L' : 'M') + X(p.i) + ',' + Y(p.v)).join(''), fill:'none', stroke:col, 'stroke-width':2, 'stroke-linejoin':'round'}, svg);
    pts.forEach(p => el('circle', {cx:X(p.i), cy:Y(p.v), r:4.5, fill: p.p < 0.05 ? col : css('--surface'), stroke: p.p < 0.05 ? css('--surface') : col, 'stroke-width':2}, svg));
    const last = pts[pts.length - 1]; labels.push({y: Y(last.v), text: short(m), col});
  });
  labels.sort((a, b) => a.y - b.y); for (let k = 1; k < labels.length; k++) if (labels[k].y - labels[k-1].y < 15) labels[k].y = labels[k-1].y + 15;
  labels.forEach(l => { const t = el('text', {x: W - R + 10, y: l.y + 4, class:'lbl'}, svg); t.textContent = l.text; });
  // crosshair
  const tip = tooltip(c); const cross = el('line', {y1:T, y2:H - B, stroke:css('--axis'), 'stroke-width':1, opacity:0}, svg);
  const hit = el('rect', {x:L - 20, y:T, width:W - L - R + 40, height:H - T - B, fill:'transparent'}, svg);
  hit.addEventListener('pointermove', ev => { const b = svg.getBoundingClientRect(); const xs = (ev.clientX - b.left) * W / b.width;
    const i = Math.max(0, Math.min(ANIOS.length - 1, Math.round((xs - L) / ((W - L - R) / (ANIOS.length - 1))))); cross.setAttribute('x1', X(i)); cross.setAttribute('x2', X(i)); cross.setAttribute('opacity', 1);
    const items = D.municipios.map(m => { const r = rows.find(x => x.municipio === m && x.anio === ANIOS[i]); return r ? {value: fmt(r.moran_I, 3), label: `${short(m)} · p=${fmt(r.moran_p, 3)}${r.moran_p < 0.05 ? '' : ' (ns)'}`, color: css(SERIE[m]), line:true} : null; }).filter(Boolean);
    tip.show(X(i) * b.width / W + 6, ev.clientY - c.getBoundingClientRect().top, ANIOS[i], items); });
  hit.addEventListener('pointerleave', () => { tip.hide(); cross.setAttribute('opacity', 0); });
  legend('lg-moran', [...D.municipios.map(m => ({label: short(m), color: css(SERIE[m]), line:true})),
    {label:'p < 0,05', color: css('--ink-2'), dot:true}, {label:'no significativo', color: css('--ink-2'), hollow:true}]);
  // tabla
  const t = document.getElementById('tb-moran'); t.replaceChildren();
  const hr = t.insertRow(); ['Municipio','Año','Casos','I de Moran','p','Hex. alto-alto','Alto-alto (FDR)','% casos en alto-alto','% área en alto-alto'].forEach((h, i) => { const th = document.createElement('th'); th.textContent = h; if (i > 1) th.className = 'n'; hr.appendChild(th); });
  D.metricas.filter(r => r.variante === variante).forEach(r => { const tr = t.insertRow();
    [short(r.municipio), r.anio, fint(r.casos), fmt(r.moran_I, 3), fmt(r.moran_p, 3), r.hex_HH, r.hex_HH_fdr, fmt(r.pct_casos_en_HH), fmt(r.pct_area_HH)].forEach((v, i) => { const td = tr.insertCell(); td.textContent = v; if (i > 1) td.className = 'n'; }); });
}

// ── Barras agrupadas: concentración ────────────────────────────────────────
function concentracion(){
  const c = document.getElementById('ch-conc'); c.replaceChildren();
  const rows = D.municipios.map(m => D.metricas.find(r => r.variante === variante && r.anio === '2019-2023' && r.municipio === m));
  const W = Math.max(320, c.clientWidth || 760), H = 260, L = 44, R = 6, T = 20, B = 30;
  const ymax = Math.ceil(Math.max(...rows.map(r => r.pct_casos_en_HH)) / 10) * 10 || 10;
  const Y = v => T + (ymax - v) * (H - T - B) / ymax;
  const svg = el('svg', {viewBox:`0 0 ${W} ${H}`, role:'img', 'aria-label':'Porcentaje de área y de casos en focos alto-alto'}, c);
  for (let v = 0; v <= ymax; v += 10){ el('line', {x1:L, x2:W - R, y1:Y(v), y2:Y(v), class: v ? 'gridl' : 'axisl'}, svg); const t = el('text', {x:L - 8, y:Y(v) + 4, 'text-anchor':'end'}, svg); t.textContent = v + ' %'; }
  const band = (W - L - R) / rows.length, bw = Math.min(44, band * 0.3);
  const tip = tooltip(c);
  const series = [{key:'pct_area_HH', label:'% del área urbana', color:'--area'}, {key:'pct_casos_en_HH', label:'% de los casos', color:'--hh'}];
  rows.forEach((r, i) => {
    const cx = L + band * i + band / 2;
    const t = el('text', {x:cx, y:H - 8, 'text-anchor':'middle', class:'lbl'}, svg); t.textContent = short(r.municipio);
    series.forEach((s, j) => {
      const x = cx + (j ? 1 : -bw - 1), v = r[s.key], y = Y(v);
      const g = el('g', {tabindex:0}, svg);
      el('path', {d:`M${x},${Y(0)} V${y + 4} q0,-4 4,-4 h${bw - 8} q4,0 4,4 V${Y(0)} Z`, fill: css(s.color)}, g);
      const lb = el('text', {x: x + bw/2, y: y - 6, 'text-anchor':'middle', class:'lbl'}, g); lb.textContent = fmt(v, 0) + ' %';
      el('rect', {x: x - 4, y: T, width: bw + 8, height: Y(0) - T, fill:'transparent'}, g);
      const show = ev => { const b = c.getBoundingClientRect(); tip.show((ev.clientX || b.left) - b.left, (ev.clientY || b.top + 40) - b.top, short(r.municipio) + ' · 2019–2023',
        series.map(ss => ({value: fmt(r[ss.key]) + ' %', label: ss.label, color: css(ss.color)}))); };
      g.addEventListener('pointermove', show); g.addEventListener('focus', show); g.addEventListener('pointerleave', () => tip.hide()); g.addEventListener('blur', () => tip.hide());
    });
  });
  legend('lg-conc', series.map(s => ({label: s.label, color: css(s.color)})));
}

function persistencia(){
  const rows = D.municipios.map(m => { const o = {label: short(m)};
    D.persistencia.filter(r => r.variante === variante && r.municipio === m).forEach(r => o[r.clase] = r.casos); return o; });
  stacked('ch-pers', rows, [
    {key:'persistente', label:'Persistente (≥3 años alto-alto)', color:'--p3'},
    {key:'intermitente', label:'Intermitente (2 años)', color:'--p2'},
    {key:'esporadico', label:'Esporádico (1 año)', color:'--p1', ink:'#2b0b05'},
    {key:'nunca', label:'Nunca alto-alto', color:'--never', ink: css('--ink')}], fint);
  const clases = ['persistente', 'intermitente', 'esporadico', 'nunca'];
  tabla('tb-pers', ['Municipio', 'Persistente', 'Intermitente', 'Esporádico', 'Nunca'],
    D.municipios.map(m => [short(m), ...clases.map(k => { const r = D.persistencia.find(x => x.variante === variante && x.municipio === m && x.clase === k);
      return r ? `${r.hexagonos} hex · ${fmt(r.pct_casos_mpio)} %` : '—'; })]));
}

// ── Clima ──────────────────────────────────────────────────────────────────
function clima(){
  const c = document.getElementById('ch-clima'); c.replaceChildren();
  const W = Math.max(280, c.clientWidth || 520), L = 70, T = 22, gap = 3, cell = Math.min(64, (W - L) / 5 - gap);
  const H = T + D.municipios.length * (36 + gap) + 4;
  const svg = el('svg', {viewBox:`0 0 ${W} ${H}`, role:'img', 'aria-label':'Meses con clima válido'}, c);
  const tip = tooltip(c);
  const step = v => v >= 12 ? '--seq4' : v >= 9 ? '--seq3' : v >= 5 ? '--seq2' : v >= 1 ? '--seq1' : '--seq0';
  ANIOS.forEach((a, j) => { const t = el('text', {x: L + j * (cell + gap) + cell/2, y: 14, 'text-anchor':'middle'}, svg); t.textContent = a; });
  D.municipios.forEach((m, i) => {
    const y = T + i * (36 + gap);
    const t = el('text', {x: L - 8, y: y + 22, 'text-anchor':'end', class:'lbl'}, svg); t.textContent = short(m);
    ANIOS.forEach((a, j) => {
      const r = D.clima_mpio.find(x => x.municipio === m && String(x.anio) === a);
      const v = r ? r.meses_validos : 0, inv = r ? r.meses_invalidos : 0;
      const x = L + j * (cell + gap);
      const g = el('g', {tabindex:0}, svg);
      el('rect', {x, y, width: cell, height: 36, rx: 4, fill: css(step(v))}, g);
      const tx = el('text', {x: x + cell/2, y: y + 22, 'text-anchor':'middle', style:`font-weight:600;fill:${inkFor(css(step(v)))}`}, g); tx.textContent = v;
      const show = ev => { const b = c.getBoundingClientRect(); tip.show(ev.clientX ? ev.clientX - b.left : 40, ev.clientY ? ev.clientY - b.top : 40, `${short(m)} · ${a}`,
        [{value: v + ' / 12', label: 'meses válidos'}, {value: String(inv), label: 'meses inválidos descartados'}]); };
      g.addEventListener('pointermove', show); g.addEventListener('focus', show); g.addEventListener('pointerleave', () => tip.hide()); g.addEventListener('blur', () => tip.hide());
    });
  });
  legend('lg-clima', [{label:'0', color:css('--seq0')}, {label:'1–4', color:css('--seq1')}, {label:'5–8', color:css('--seq2')}, {label:'9–11', color:css('--seq3')}, {label:'12 meses', color:css('--seq4')}]);
}
function climaTexto(){
  const utiles = D.clima_mpio.filter(r => r.meses_validos >= 9).length;
  const sinDatos = D.municipios.filter(m => !D.clima_mpio.some(r => r.municipio === m && r.meses_validos >= 9)).map(short);
  document.getElementById('clima-txt').textContent =
    `Para relacionar el clima con los clústeres se necesitan series completas por municipio. Solo ${utiles} de 20 combinaciones municipio-año tienen al menos 9 meses válidos` +
    (sinDatos.length ? ` y ${sinDatos.join(', ')} no tiene${sinDatos.length > 1 ? 'n' : ''} ningún año utilizable` : '') +
    '. Con tan pocos puntos cualquier correlación es inestable, así que la asociación clima–clústeres queda sin responder con esta fuente.';
  const tuluaT = D.clima_mpio.filter(r => r.municipio === 'Tuluá' && r.tmax_c != null && r.tmax_c < 22);
  const prob = [
    'Precipitaciones mensuales de decenas de miles de milímetros y humedades máximas por debajo de 50 % en la fuente original (descartadas).',
    ...(tuluaT.length ? [`Tuluá registra temperaturas máximas medias cercanas a ${fmt(Math.min(...tuluaT.map(r => r.tmax_c)), 0)} °C, propias de una estación de montaña y no de la cabecera.`] : []),
    'La cobertura de estaciones cae con los años y se interrumpe justo en 2022–2023, cuando ocurre una de las epidemias.',
    'Recomendación: usar lluvia CHIRPS y temperatura y humedad ERA5-Land mensuales por municipio, cruzadas con conteos mensuales por hexágono y rezagos de 0 a 3 meses.',
  ];
  const ul = document.getElementById('clima-prob'); prob.forEach(p => { const li = document.createElement('li'); li.textContent = p; ul.appendChild(li); });
  const t = document.getElementById('tb-asoc'); const hr = t.insertRow();
  ['Métrica','Variable','n','rho','p'].forEach((h, i) => { const th = document.createElement('th'); th.textContent = h; if (i > 1) th.className = 'n'; hr.appendChild(th); });
  D.asociacion.forEach(r => { const tr = t.insertRow(); [r.metrica, r.variable, r.n_municipio_anio, r.rho == null ? '—' : fmt(r.rho, 2), r.p == null ? '—' : fmt(r.p, 3)].forEach((v, i) => { const td = tr.insertCell(); td.textContent = v; if (i > 1) td.className = 'n'; }); });
}

// ── Alcance ────────────────────────────────────────────────────────────────
function alcance(){
  const filas = [
    ['Clústeres de dengue a escala fina', 'good', 'Respondido', 'Hexágonos de 200 m en las cabeceras, 2019–2023 (este informe).'],
    ['Escala de barrio', 'warn', 'Parcial', 'Se usa hexágono como unidad. Falta la capa de barrios de los cuatro municipios para agregar o comparar.'],
    ['Precipitación, humedad, temperatura', 'crit', 'Sin datos suficientes', 'Cobertura incompleta e inconsistente. Requiere CHIRPS/ERA5-Land y conteos mensuales.'],
    ['Variables socioeconómicas', 'crit', 'Pendiente', 'Estrato, IPM y NBI por manzana (censo DANE 2018) agregados a hexágono.'],
    ['Variables entomológicas', 'crit', 'Pendiente', 'Índices de vivienda, recipiente, Breteau y ovitrampas por barrio y fecha (secretarías de salud).'],
    ['Intervenciones de control vectorial', 'crit', 'Pendiente', 'Fumigación y control larvario por barrio y fecha; modelarlas con rezago porque siguen a los brotes.'],
  ];
  const ico = {good:'✓', warn:'!', crit:'✕'}; const color = {good:'--good', warn:'--warn', crit:'--crit'};
  const t = document.getElementById('tb-alcance'); const hr = t.insertRow();
  ['Componente del objetivo', 'Estado', 'Qué falta o qué se hizo'].forEach(h => { const th = document.createElement('th'); th.textContent = h; hr.appendChild(th); });
  filas.forEach(([comp, st, label, det]) => { const tr = t.insertRow(); tr.insertCell().textContent = comp;
    const td = tr.insertCell(); const s = document.createElement('span'); s.className = 'status';
    const d = document.createElement('span'); d.className = 'dot'; d.style.background = css(color[st]);
    const i = document.createElement('span'); i.textContent = ico[st]; i.setAttribute('aria-hidden', 'true');
    s.append(d, i, document.createTextNode(label)); td.appendChild(s); tr.insertCell().textContent = det; });
}

function metodo(){
  const m = D.meta;
  const items = [
    `Unidad: hexágono de 200 m (malla <code>public.hexagonos</code>), cabeceras de ${D.municipios.map(short).join(', ')}.`,
    `Área urbana: hexágonos con algún caso entre 2019 y 2026 en grupos contiguos de al menos ${m.componente_minimo_hexagonos} hexágonos; dentro de ella, los años sin casos cuentan como cero.`,
    'Vecindad: los seis hexágonos contiguos; pesos estandarizados por fila.',
    `Estadísticos: I de Moran global, LISA y Gi* con ${m.permutaciones} permutaciones condicionales (semilla ${m.semilla}); significancia a p<${String(m.alfa).replace('.', ',')} y con corrección FDR.`,
    'Persistencia: número de años 2019–2023 en que cada hexágono es núcleo alto-alto.',
    `Variantes: <b>principal</b> — ${m.variantes.principal}; <b>sensibilidad</b> — ${m.variantes.sensibilidad}.`,
    `Fuente de conteos: ${m.fuente === 'db' ? 'PostGIS (base restringida, agregación en la base)' : 'conteos por hexágono ya agregados (modo html); repetir con --fuente db para la versión final'}.`,
  ];
  const ul = document.getElementById('metodo-lista'); items.forEach(h => { const li = document.createElement('li'); li.innerHTML = h; ul.appendChild(li); });
  document.getElementById('pie').textContent = `Generado ${D.generado} con scripts/clusters_hexagonos.py y scripts/informe_objetivo1.py · Observatorio GeoSalud · Uso analítico.`;
}

// ── Mapa ───────────────────────────────────────────────────────────────────
let map, capa, base;
function mapa(){
  const sm = document.getElementById('m-mpio'), sc = document.getElementById('m-capa');
  [['', 'Todos'], ...D.municipios.map(m => [m, short(m)])].forEach(([v, t]) => { const o = document.createElement('option'); o.value = v; o.textContent = t; sm.appendChild(o); });
  const grupos = [
    ['Clústeres LISA', [['lisa:2019-2023', 'Clústeres LISA 2019–2023'], ...ANIOS.map(a => ['lisa:' + a, 'Clústeres LISA ' + a])]],
    ['Focos alto-alto', [['persistencia', 'Persistencia 2019–2023'], ...ANIOS.map(a => [a, 'Zonas alto-alto ' + a])]],
  ];
  grupos.forEach(([g, ops]) => { const og = document.createElement('optgroup'); og.label = g;
    ops.forEach(([v, t]) => { const o = document.createElement('option'); o.value = v; o.textContent = t; og.appendChild(o); }); sc.appendChild(og); });
  sc.value = 'lisa:2019-2023';
  sm.value = 'Tuluá';
  if (typeof L === 'undefined'){ document.getElementById('map').textContent = 'No se pudo cargar Leaflet (requiere conexión a internet).'; return; }
  map = L.map('map', {scrollWheelZoom:false}).setView([3.9, -76.3], 9);
  pintarBase();
  sm.addEventListener('change', pintarMapa); sc.addEventListener('change', pintarMapa);
  pintarMapa();
}
// Mapas base sin clave de API: lienzo gris de Esri (claro/oscuro) con etiquetas encima;
// si sus teselas fallan se cambia automáticamente a OpenStreetMap.
const ESRI = 'https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/';
const ATRIB_ESRI = 'Mapa base © Esri, HERE, Garmin, © colaboradores de OpenStreetMap';
let etiquetas, usarOSM = false;
function pintarBase(){
  if (!map) return;
  if (base) map.removeLayer(base);
  if (etiquetas) map.removeLayer(etiquetas);
  etiquetas = null;
  const dark = document.documentElement.getAttribute('data-theme') === 'dark' || (!document.documentElement.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
  if (usarOSM){
    base = L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {attribution:'© colaboradores de OpenStreetMap', maxZoom:18}).addTo(map);
    return;
  }
  const tono = dark ? 'Dark' : 'Light';
  let errores = 0;
  base = L.tileLayer(`${ESRI}World_${tono}_Gray_Base/MapServer/tile/{z}/{y}/{x}`, {attribution: ATRIB_ESRI, maxZoom:16, maxNativeZoom:16})
    .on('tileerror', () => { if (++errores === 4){ usarOSM = true; pintarBase(); } })
    .addTo(map);
  if (!map.getPane('etiquetas')){ map.createPane('etiquetas'); map.getPane('etiquetas').style.zIndex = 650; map.getPane('etiquetas').style.pointerEvents = 'none'; }
  etiquetas = L.tileLayer(`${ESRI}World_${tono}_Gray_Reference/MapServer/tile/{z}/{y}/{x}`, {pane:'etiquetas', maxZoom:16, maxNativeZoom:16}).addTo(map);
}
function pintarMapa(){
  if (!map) return;
  const mp = document.getElementById('m-mpio').value, v = document.getElementById('m-capa').value;
  const filtro = f => !mp || f.properties.municipio === mp;
  if (capa) map.removeLayer(capa);
  if (v.startsWith('lisa:')){
    const anio = v.slice(5);
    const col = {HH:css('--l-hh'), LL:css('--l-ll'), HL:css('--l-hl'), LH:css('--l-lh')};
    const nom = {HH:'Alto-alto', LL:'Bajo-bajo', HL:'Alto-bajo (atípico)', LH:'Bajo-alto (atípico)'};
    const fc = {type:'FeatureCollection', features: D.lisa_geo.features.filter(f => String(f.properties.anio) === anio)};
    capa = L.geoJSON(fc, {filter: filtro, style: f => ({color: css('--surface'), weight: .6, fillColor: col[f.properties.lisa], fillOpacity: .85}),
      onEachFeature: (f, l) => l.bindTooltip(`${short(f.properties.municipio)} · ${nom[f.properties.lisa]} (${anio === '2019-2023' ? '2019–2023' : anio})`)}).addTo(map);
    const n = k => fc.features.filter(f => filtro(f) && f.properties.lisa === k).length;
    legend('lg-map', ['HH', 'LL', 'HL', 'LH'].map(k => ({label: `${nom[k]} · ${n(k)} hex.`, color: col[k]})));
  } else if (v === 'persistencia'){
    const col = {persistente:css('--p3'), intermitente:css('--p2'), esporadico:css('--p1')};
    capa = L.geoJSON(D.pers_geo, {filter: filtro, style: f => ({color: css('--surface'), weight: .8, fillColor: col[f.properties.clase], fillOpacity: .85}),
      onEachFeature: (f, l) => l.bindTooltip(`${short(f.properties.municipio)} · alto-alto en ${f.properties.anios_HH} de 5 años`)}).addTo(map);
    legend('lg-map', [{label:'Persistente (≥3 años)', color:col.persistente}, {label:'Intermitente (2 años)', color:col.intermitente}, {label:'Esporádico (1 año)', color:col.esporadico}]);
  } else {
    const fc = {type:'FeatureCollection', features: D.zonas.features.filter(f => String(f.properties.anio) === v)};
    capa = L.geoJSON(fc, {filter: filtro, style: () => ({color: css('--hh'), weight: 1.2, fillColor: css('--hh'), fillOpacity: .55}),
      onEachFeature: (f, l) => l.bindTooltip(`${short(f.properties.municipio)} · zona alto-alto de ${f.properties.hexagonos} hexágonos (${v})`)}).addTo(map);
    legend('lg-map', [{label:'Zona alto-alto (LISA, p<0,05)', color: css('--hh')}]);
  }
  encuadrar(capa, !mp);
}
// Encuadra en el núcleo urbano: descarta hexágonos rurales a más de 4 km de la mediana
// para que unos pocos puntos alejados no reduzcan la cabecera a un punto.
function encuadrar(capa, todos){
  const capas = capa.getLayers(); if (!capas.length) return;
  if (todos){ map.fitBounds(capa.getBounds(), {padding:[24, 24], maxZoom: 15}); return; }
  const cs = capas.map(l => l.getBounds().getCenter());
  const med = a => { const s = [...a].sort((x, y) => x - y); return s[Math.floor(s.length / 2)]; };
  const c = L.latLng(med(cs.map(p => p.lat)), med(cs.map(p => p.lng)));
  const cerca = capas.filter((l, k) => cs[k].distanceTo(c) <= 4000);
  const b = L.featureGroup(cerca.length ? cerca : capas).getBounds();
  if (b.isValid()) map.fitBounds(b, {padding:[24, 24], maxZoom: 15});
}

// ── Variante y tema ────────────────────────────────────────────────────────
function segVariante(){
  const s = document.getElementById('seg-var');
  [['principal', 'Principal'], ['sensibilidad', 'Sensibilidad (sin centroides)']].forEach(([v, t]) => {
    const b = document.createElement('button'); b.type = 'button'; b.textContent = t; b.setAttribute('aria-pressed', v === variante);
    b.addEventListener('click', () => { variante = v; s.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); redibujar(); });
    s.appendChild(b); });
}
function redibujar(){ moran(); concentracion(); persistencia(); }
function redibujarTodo(){ calidad(); redibujar(); clima(); pintarBase(); pintarMapa();
  document.getElementById('tb-alcance').replaceChildren(); alcance(); }
let rz; window.addEventListener('resize', () => { clearTimeout(rz); rz = setTimeout(() => { calidad(); redibujar(); clima(); }, 150); });
const btnTema = document.getElementById('tema');
function estadoTema(){ const dark = document.documentElement.getAttribute('data-theme') === 'dark' || (!document.documentElement.getAttribute('data-theme') && matchMedia('(prefers-color-scheme: dark)').matches);
  btnTema.textContent = dark ? 'Tema claro' : 'Tema oscuro'; btnTema.setAttribute('aria-pressed', dark); return dark; }
btnTema.addEventListener('click', () => { const dark = estadoTema(); document.documentElement.setAttribute('data-theme', dark ? 'light' : 'dark');
  try { localStorage.setItem('geosalud-tema', dark ? 'light' : 'dark'); } catch (e) {} estadoTema(); redibujarTodo(); });
try { const t = localStorage.getItem('geosalud-tema'); if (t) document.documentElement.setAttribute('data-theme', t); } catch (e) {}
estadoTema();

respuesta(); calidad(); segVariante(); redibujar(); clima(); climaTexto(); alcance(); metodo(); mapa();
</script>
</body>
</html>
"""


def main():
    datos = construir_datos()
    html = PLANTILLA.replace("__DATA__", json.dumps(datos, ensure_ascii=False).replace("</", "<\\/"))
    SALIDA.write_text(html, encoding="utf-8")
    print(f"Informe: {SALIDA} ({SALIDA.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
