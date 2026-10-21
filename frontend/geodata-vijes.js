// ─── GEODATA SALUD — Módulo «Piloto Vijes» ────────────────────────────────────
// Muestra el municipio de Vijes y sus edificaciones detectadas por satélite
// (Google Open Buildings v3) a partir de VIJES_DATA (vijes-data.js, generado por
// scripts/exportar_vijes.py). Módulo autocontenido: no modifica geodata-app.js;
// se engancha a navigate() para iniciarse la primera vez que se abre la sección.
// Ojo: son EDIFICACIONES (huellas de techos), no predios catastrales.

(function () {
  'use strict';

  const SECCION = 'vijes';
  let mapa = null, capaEdif = null, capaLimite = null, capaCabecera = null, base = {}, baseActiva = 'oscuro';
  const estado = { modo: 'vivienda', confMin: 0.65, soloCandidatas: false, ocultarFuera: false };

  const COLOR = {
    vivienda: '#f59e0b', otra: '#64748b', limite: '#22d3ee',
    conf: ['#1e3a8a', '#2563eb', '#3b82f6', '#60a5fa', '#bfdbfe'],
    area: { '< 20 m²': '#94a3b8', '20–100 m²': '#34d399', '100–400 m²': '#f59e0b', '> 400 m²': '#ef4444' },
  };

  const fmt = n => Number(n).toLocaleString('es-CO');

  function colorConf(c) {
    const cortes = [0.70, 0.75, 0.80, 0.90];
    let i = 0; while (i < cortes.length && c >= cortes[i]) i++;
    return COLOR.conf[i];
  }
  function claseArea(a) {
    if (a < 20) return '< 20 m²';
    if (a <= 100) return '20–100 m²';
    if (a <= 400) return '100–400 m²';
    return '> 400 m²';
  }
  function colorDe(e) {
    if (estado.modo === 'confianza') return colorConf(e.c);
    if (estado.modo === 'area') return COLOR.area[claseArea(e.a)];
    return e.v ? COLOR.vivienda : COLOR.otra;
  }
  function visible(e) {
    if (e.c < estado.confMin) return false;
    if (estado.soloCandidatas && !e.v) return false;
    if (estado.ocultarFuera && !e.d) return false;
    return true;
  }

  // ── Estilos propios del módulo (mismo lenguaje visual que #geovisor-wrap) ──
  function inyectarCSS() {
    if (document.getElementById('vijes-css')) return;
    const css = `
      #vijes-wrap { display:flex; height: calc(100vh - var(--header-h, 60px)); }
      #vijes-sidebar { width:250px; min-width:250px; background:var(--bg-card); border-right:1px solid var(--border);
        padding:16px; display:flex; flex-direction:column; gap:14px; overflow-y:auto; z-index:5; }
      #vijes-map { flex:1; position:relative; background:#0a0f1a; }
      .vj-kpis { display:grid; grid-template-columns:1fr 1fr; gap:8px; }
      .vj-kpi { background:var(--bg-card2); border:1px solid var(--border2); border-radius:8px; padding:8px 10px; }
      .vj-kpi b { display:block; font-family:var(--mono); font-size:18px; color:var(--text); }
      .vj-kpi span { font-size:10px; color:var(--text-3); line-height:1.25; display:block; }
      .vj-kpi.acento b { color:${COLOR.vivienda}; }
      .vj-aviso { font-size:11px; line-height:1.4; color:var(--text-2); background:color-mix(in srgb, ${COLOR.vivienda} 10%, transparent);
        border:1px solid color-mix(in srgb, ${COLOR.vivienda} 35%, transparent); border-radius:8px; padding:8px 10px; }
      .vj-row { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--text-2); cursor:pointer; }
      .vj-row input { accent-color: var(--accent); }
      .vj-range { width:100%; accent-color: var(--accent); }
      .vj-leyenda { display:flex; flex-direction:column; gap:5px; font-size:11px; color:var(--text-2); }
      .vj-leyenda i { display:inline-block; width:12px; height:12px; border-radius:3px; margin-right:7px; vertical-align:-2px; }
      .vj-fuente { font-size:10px; color:var(--text-3); line-height:1.4; }
      .vj-popup { font-family:var(--font); font-size:12px; line-height:1.5; }
      .vj-popup b { color:#0f172a; }
    `;
    const s = document.createElement('style'); s.id = 'vijes-css'; s.textContent = css; document.head.appendChild(s);
  }

  function construirSidebar() {
    const R = VIJES_DATA.resumen, P = VIJES_DATA.meta.parametros;
    const sb = document.getElementById('vijes-sidebar');
    sb.innerHTML = `
      <div>
        <div class="map-ctrl-label">Piloto de tesis · Vijes (76869)</div>
        <div class="vj-kpis">
          <div class="vj-kpi"><b>${fmt(R.total)}</b><span>edificaciones detectadas</span></div>
          <div class="vj-kpi acento"><b>${fmt(R.candidatas_vivienda)}</b><span>candidatas a vivienda</span></div>
          <div class="vj-kpi"><b>${fmt(R.cabecera_1_5km)}</b><span>a ≤ 1,5 km de la cabecera</span></div>
          <div class="vj-kpi"><b>${fmt(R.area_mediana_m2)} m²</b><span>área mediana de huella</span></div>
        </div>
      </div>
      <div>
        <div class="map-ctrl-label">Colorear por</div>
        <div class="map-ctrl-group" id="vj-modos">
          <button class="map-mode-btn active" data-modo="vivienda">⌂ Candidata a vivienda</button>
          <button class="map-mode-btn" data-modo="confianza">◉ Confianza del modelo</button>
          <button class="map-mode-btn" data-modo="area">◫ Tamaño de la huella</button>
        </div>
      </div>
      <div>
        <div class="map-ctrl-label">Confianza mínima: <span id="vj-conf-val">0,65</span></div>
        <input type="range" class="vj-range" id="vj-conf" min="0.65" max="0.95" step="0.05" value="0.65">
        <label class="vj-row" style="margin-top:8px"><input type="checkbox" id="vj-solo-cand"> Solo candidatas a vivienda</label>
        <label class="vj-row" style="margin-top:4px"><input type="checkbox" id="vj-fuera"> Ocultar las que caen fuera del límite</label>
      </div>
      <div>
        <div class="map-ctrl-label">Mapa base</div>
        <div class="map-ctrl-group" id="vj-bases">
          <button class="map-mode-btn active" data-base="oscuro">◐ Oscuro</button>
          <button class="map-mode-btn" data-base="satelite">◍ Sat. 2020</button>
          <button class="map-mode-btn" data-base="satelite2026">◍ Sat. 2026</button>
        </div>
        <div class="vj-fuente" id="vj-base-nota" style="margin-top:6px"></div>
      </div>
      <div>
        <div class="map-ctrl-label">En el mapa</div>
        <div class="map-stat"><span class="map-stat-val" id="vj-visibles">—</span><span class="map-stat-lbl">edificaciones visibles</span></div>
        <div class="vj-leyenda" id="vj-leyenda" style="margin-top:8px"></div>
      </div>
      <div class="vj-aviso"><b>Edificaciones, no predios.</b> Son huellas de techos detectadas por satélite.
        El predio es una unidad catastral y no se ve en la imagen; se comparará con el catastro y el CNPV en la validación.
        Candidata a vivienda = confianza ≥ ${String(P.confianza_min).replace('.', ',')} y área entre ${P.area_min_m2} y ${P.area_max_m2} m².</div>
      <div class="vj-fuente" style="margin-top:auto">
        <div class="map-ctrl-label">Fuente</div>
        ${VIJES_DATA.meta.fuente_edificaciones}.<br>Límite: ${VIJES_DATA.meta.fuente_limite}.<br>Exportado ${VIJES_DATA.meta.exportado}.
      </div>`;

    sb.querySelectorAll('#vj-modos .map-mode-btn').forEach(b => b.addEventListener('click', () => {
      sb.querySelectorAll('#vj-modos .map-mode-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); estado.modo = b.dataset.modo; dibujar();
    }));
    sb.querySelectorAll('#vj-bases .map-mode-btn').forEach(b => b.addEventListener('click', () => {
      sb.querySelectorAll('#vj-bases .map-mode-btn').forEach(x => x.classList.remove('active'));
      b.classList.add('active'); cambiarBase(b.dataset.base);
    }));
    const conf = sb.querySelector('#vj-conf');
    conf.addEventListener('input', () => {
      estado.confMin = parseFloat(conf.value);
      sb.querySelector('#vj-conf-val').textContent = estado.confMin.toFixed(2).replace('.', ',');
      dibujar();
    });
    sb.querySelector('#vj-solo-cand').addEventListener('change', e => { estado.soloCandidatas = e.target.checked; dibujar(); });
    sb.querySelector('#vj-fuera').addEventListener('change', e => { estado.ocultarFuera = e.target.checked; dibujar(); });
  }

  const NOTA_BASE = {
    satelite: 'Imagen del 17-jul-2020 (Esri Wayback, 0,5 m), sin nubes. Es anterior a Open Buildings (2023): pueden aparecer huellas sin techo visible.',
    satelite2026: 'Imagen del 31-mar-2026 (Esri World Imagery, 0,34 m). Más nítida y reciente, pero con nubes sobre la cabecera.',
  };

  function cambiarBase(clave) {
    if (!mapa || clave === baseActiva) return;
    mapa.removeLayer(base[baseActiva]); base[clave].addTo(mapa); base[clave].bringToBack(); baseActiva = clave;
    if (capaLimite) capaLimite.setStyle({ color: clave === 'oscuro' ? COLOR.limite : '#facc15' });
    const nota = document.getElementById('vj-base-nota');
    if (nota) nota.textContent = NOTA_BASE[clave] || '';
  }

  function leyenda() {
    let filas;
    if (estado.modo === 'confianza') {
      const et = ['0,65–0,70', '0,70–0,75', '0,75–0,80', '0,80–0,90', '≥ 0,90'];
      filas = COLOR.conf.map((c, i) => `<div><i style="background:${c}"></i>${et[i]}</div>`);
    } else if (estado.modo === 'area') {
      filas = Object.entries(COLOR.area).map(([k, c]) => `<div><i style="background:${c}"></i>${k}</div>`);
    } else {
      filas = [`<div><i style="background:${COLOR.vivienda}"></i>Candidata a vivienda</div>`,
               `<div><i style="background:${COLOR.otra}"></i>Otra edificación</div>`];
    }
    filas.push(`<div><i style="background:transparent;border:2px solid ${COLOR.limite}"></i>Límite municipal (GAUL 2025)</div>`);
    filas.push(`<div><i style="background:transparent;border:1px dashed #e2e8f8;border-radius:50%"></i>Radio de 1,5 km de la cabecera</div>`);
    document.getElementById('vj-leyenda').innerHTML = filas.join('');
  }

  function popup(e) {
    return `<div class="vj-popup"><b>Edificación detectada</b><br>
      Confianza: ${e.c.toFixed(2).replace('.', ',')}<br>
      Área de la huella: ${fmt(Math.round(e.a))} m²<br>
      Candidata a vivienda: ${e.v ? 'sí' : 'no'}<br>
      ${e.d ? 'Dentro' : 'Fuera'} del límite municipal<br>
      Plus Code: ${e.p}</div>`;
  }

  function dibujar() {
    if (!mapa) return;
    if (capaEdif) mapa.removeLayer(capaEdif);
    const capas = [];
    let n = 0;
    for (const e of VIJES_DATA.edificaciones) {
      if (!visible(e)) continue;
      const col = colorDe(e);
      const poly = L.polygon(e.g.map(([x, y]) => [y, x]), {
        color: col, weight: 1.2, fillColor: col, fillOpacity: 0.75, opacity: 0.95,
      });
      poly.bindPopup(() => popup(e));
      capas.push(poly); n++;
    }
    capaEdif = L.layerGroup(capas).addTo(mapa);
    document.getElementById('vj-visibles').textContent = fmt(n);
    leyenda();
  }

  function iniciar() {
    if (mapa) { setTimeout(() => mapa.invalidateSize(), 100); return; }
    if (typeof VIJES_DATA === 'undefined') {
      document.getElementById('vijes-map').innerHTML =
        '<div style="padding:24px;color:#94a3b8">No se encontró vijes-data.js. Corre <code>python scripts/exportar_vijes.py</code>.</div>';
      return;
    }
    inyectarCSS();
    construirSidebar();
    mapa = L.map('vijes-map', { zoomControl: false, preferCanvas: true });
    // Esri Dark Gray: no pide API key. CARTO dark_all responde "API KEY REQUIRED"
    // cuando el geovisor se sirve por http://localhost (sí funciona con file://).
    base.oscuro = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}', {
      maxNativeZoom: 16, maxZoom: 20, attribution: 'Mapa base &copy; Esri, HERE, Garmin, &copy; OpenStreetMap' });
    // Satélite: la imagen vigente de Esri World Imagery (captura 31-mar-2026, 0,34 m) tiene
    // ~20 % de nubes sobre la cabecera. Por defecto se usa la versión de Esri Wayback
    // 32246 (captura 17-jul-2020, Vivid 0,5 m), la más reciente sin nubes (0,2 %).
    base.satelite = L.tileLayer('https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/32246/{z}/{y}/{x}', {
      maxNativeZoom: 19, maxZoom: 20, attribution: 'Imágenes &copy; Esri World Imagery Wayback (jul 2020), Maxar' });
    base.satelite2026 = L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', {
      maxNativeZoom: 19, maxZoom: 20, attribution: 'Imágenes &copy; Esri, Maxar, Earthstar Geographics' });
    base.oscuro.addTo(mapa);
    L.control.zoom({ position: 'bottomright' }).addTo(mapa);
    L.control.scale({ position: 'bottomleft', imperial: false }).addTo(mapa);

    // La vista se fija ANTES de agregar capas vectoriales: con preferCanvas, Leaflet
    // falla (_clipPoints) si se agregan polígonos a un mapa que aún no tiene vista.
    capaLimite = L.geoJSON(VIJES_DATA.limite, {
      style: { color: COLOR.limite, weight: 2.5, fill: false }, interactive: false });
    mapa.fitBounds(capaLimite.getBounds(), { padding: [20, 20] });
    capaLimite.addTo(mapa);
    const [lon, lat] = VIJES_DATA.meta.parametros.cabecera_lonlat;
    capaCabecera = L.circle([lat, lon], { radius: VIJES_DATA.meta.parametros.radio_cabecera_m,
      color: '#e2e8f8', weight: 1, dashArray: '4 4', fill: false, interactive: false }).addTo(mapa);
    dibujar();
    setTimeout(() => mapa.invalidateSize(), 150);
  }

  // ── Enganche con la navegación del observatorio ──────────────────────────
  const navegarOriginal = window.navigate;
  if (typeof navegarOriginal === 'function') {
    window.navigate = function (seccion) {
      navegarOriginal(seccion);
      if (seccion === SECCION) {
        const h = document.getElementById('header-title');
        if (h) h.textContent = 'Piloto Vijes · Edificaciones';
        setTimeout(iniciar, 60);
      }
    };
  }
  window.abrirPilotoVijes = () => window.navigate(SECCION);
})();
