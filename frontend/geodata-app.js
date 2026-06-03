// ─── GEODATA SALUD — Application logic ───────────────────────────────────────

const I18N = {
  es: {
    dashboard:'Panel', geovisor:'Geovisor', indicadores:'Indicadores',
    tendencias:'Tendencias', priorizacion:'Priorización', coropletico:'Coropléticos',
    total_casos:'Casos totales', inc_prom:'Incidencia promedio',
    mun_criticos:'Municipios críticos', anio_pico:'Año pico',
    casos_x100k:'× 100 000 hab.', municipios:'municipios',
    dengue:'Dengue', zika:'Zika', chik:'Chikungunya',
    proximamente:'próximamente', sin_cali:'Sin Cali', con_cali:'Con Cali',
    casos_abs:'Casos absolutos', incidencia:'Incidencia', burbujas:'Burbujas',
    calor:'Calor', cluster:'Cluster', aplicar:'Aplicar',
    riesgo:'Riesgo', critico:'Crítico', alto:'Alto', medio:'Medio', bajo:'Bajo',
    tendencia:'Tendencia', pct_total:'% del total',
    rank:'#', municipio:'Municipio', total:'Total 2019–26',
    casos_anio:'Casos por año', top_mun:'Top municipios',
    pob_inc:'Población vs Incidencia', serie_hist:'Serie histórica',
    seleccionar_mun:'Seleccionar municipio', año:'Año',
    demografia:'Demografía', poblacion_total:'Población total',
    fuente:'Fuente: Secretaría de Salud, Valle del Cauca',
    update:'Última actualización', loading:'Cargando datos...',
  },
  en: {
    dashboard:'Dashboard', geovisor:'Geovisor', indicadores:'Indicators',
    tendencias:'Trends', priorizacion:'Prioritization', coropletico:'Choropleth',
    total_casos:'Total cases', inc_prom:'Avg. incidence',
    mun_criticos:'Critical municipalities', anio_pico:'Peak year',
    casos_x100k:'per 100 000 pop.', municipios:'municipalities',
    dengue:'Dengue', zika:'Zika', chik:'Chikungunya',
    proximamente:'coming soon', sin_cali:'Without Cali', con_cali:'With Cali',
    casos_abs:'Absolute cases', incidencia:'Incidence', burbujas:'Bubbles',
    calor:'Heat', cluster:'Cluster', aplicar:'Apply',
    riesgo:'Risk', critico:'Critical', alto:'High', medio:'Medium', bajo:'Low',
    tendencia:'Trend', pct_total:'% of total',
    rank:'#', municipio:'Municipality', total:'Total 2019–26',
    casos_anio:'Cases by year', top_mun:'Top municipalities',
    pob_inc:'Population vs Incidence', serie_hist:'Historical series',
    seleccionar_mun:'Select municipality', año:'Year',
    demografia:'Demographics', poblacion_total:'Total population',
    fuente:'Source: Health Secretary, Valle del Cauca',
    update:'Last update', loading:'Loading data...',
  }
};

let LANG = 'es';
let ACTIVE_SECTION = 'dashboard';
let SELECTED_YEAR = 2024;
let INCLUDE_CALI = false;
let MAP_MODE = 'burbujas';
let MAP_VAR = 'incidencia_dengue'; // 'incidencia_dengue' | 'conteo_dengue'
let SELECTED_MUN = '76001';
let TENDENCIA_CODES = null;
let TENDENCIA_METRIC = 'incidencia_dengue';
let TENDENCIA_SCALE = 'anual';
let mapInstance = null;
let mapLayers = [];
let charts = {};

// Demografía state
let demoMapInstance = null;
let demoMapLayers = [];
let DEMO_SELECTED_MUN = 'VALLE';
let DEMO_SELECTED_CYCLE = 'ALL';

// Coropléticos state
let choroMap = null;
let choroMapLayers = [];
let CHORO_YEAR = 2024;
let CHORO_VAR = 'incidencia_dengue';
let CHORO_CALI = false;
let chorLegend = null;

function t(k) { return I18N[LANG][k] || k; }

// ─── Navigation ───────────────────────────────────────────────────────────────
function navigate(section) {
  if (section === 'chatbot') {
    if (window.initChatbot) window.initChatbot();
    if (window.openChatbot) window.openChatbot();
    return;
  }
  if (section === 'coropletico') {
    MAP_MODE = 'coropletico';
    section = 'geovisor';
  }
  ACTIVE_SECTION = section;
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const el = document.getElementById('s-' + section);
  if (el) el.classList.add('active');
  const nav = document.querySelector(`.nav-item[data-section="${section}"]`);
  if (nav) nav.classList.add('active');
  const titles = { hexagonos: 'Hexágonos', aede: 'AEDE', forecasting: 'IA & ML Forecasting', chatbot: 'Asistente IA' };
  document.getElementById('header-title').textContent = titles[section] || t(section);
  if (section === 'geovisor' && mapInstance) { setTimeout(() => mapInstance.invalidateSize(), 100); }
  if (section === 'demografia' && demoMapInstance) { setTimeout(() => demoMapInstance.invalidateSize(), 100); }
  // Render charts AFTER section is visible — setTimeout ensures full CSS layout
  setTimeout(() => {
    if (section === 'indicadores') renderIndicadores();
    if (section === 'tendencias') renderTendencias();
    if (section === 'priorizacion') renderPriorizacion();
    if (section === 'dashboard') renderDashboard();
    if (section === 'demografia') renderDemografia();
    if (section === 'reporte') renderReporte();
    if (section === 'forecasting' && window.refreshForecastingModule) window.refreshForecastingModule();
  }, 50);
}

function toggleLang() {
  LANG = LANG === 'es' ? 'en' : 'es';
  document.getElementById('lang-btn').textContent = LANG === 'es' ? 'EN' : 'ES';
  refreshAllText();
  navigate(ACTIVE_SECTION);
}

function refreshAllText() {
  document.querySelectorAll('[data-i18n]').forEach(el => {
    el.textContent = t(el.dataset.i18n);
  });
}

// ─── Helpers ──────────────────────────────────────────────────────────────────
const fmt = n => Number(n).toLocaleString('es-CO');
const fmtDec = n => Number(n).toFixed(1);
const RISK_COLOR = { 'Crítico':'#f87171', 'Alto':'#fbbf24', 'Medio':'#34d399', 'Bajo':'#64748b',
                     'Critical':'#f87171', 'High':'#fbbf24', 'Medium':'#34d399', 'Low':'#64748b' };

function riskLabel(r) {
  const map = { 'Crítico':'critico','Alto':'alto','Medio':'medio','Bajo':'bajo' };
  return t(map[r] || r.toLowerCase());
}

// ─── Map tooltip helper ───────────────────────────────────────────────────────
function munTooltip(r, color) {
  return `<div style="font-family:Space Grotesk,sans-serif;min-width:180px">
    <div style="font-weight:700;color:#e2e8f8;margin-bottom:6px;font-size:14px">${r.MPIO_CNMBR}</div>
    <div style="color:#94a3b8;font-size:12px;margin-bottom:2px">Casos: <b style="color:#e2e8f8">${fmt(r.conteo_dengue)}</b></div>
    <div style="color:#94a3b8;font-size:12px;margin-bottom:2px">Incidencia: <b style="color:${color}">${fmtDec(r.incidencia_dengue)}</b> ×100k</div>
    <div style="color:#94a3b8;font-size:12px">Población: <b style="color:#e2e8f8">${fmt(r.población)}</b></div>
  </div>`;
}

// ─── Choropleth legend (dynamic, replaces static HTML legend) ────────────────
let choroplethLegendCtrl = null;
function renderChoroplethLegend(bins, palette, isMock) {
  if (choroplethLegendCtrl) { mapInstance.removeControl(choroplethLegendCtrl); choroplethLegendCtrl = null; }
  const varLabel = MAP_VAR === 'incidencia_dengue' ? 'Incidencia ×100k' : 'Casos absolutos';
  const labels = [
    `< ${Math.round(bins[0])}`,
    `${Math.round(bins[0])}–${Math.round(bins[1])}`,
    `${Math.round(bins[1])}–${Math.round(bins[2])}`,
    `${Math.round(bins[2])}–${Math.round(bins[3])}`,
    `> ${Math.round(bins[3])}`
  ];
  choroplethLegendCtrl = L.control({ position: 'bottomright' });
  choroplethLegendCtrl.onAdd = () => {
    const div = L.DomUtil.create('div');
    div.style.cssText = 'background:#0c1221ee;border:1px solid #1c2d4a;border-radius:8px;padding:10px 12px;font-family:Space Grotesk,sans-serif;font-size:11px;color:#94a3b8;min-width:140px';
    div.innerHTML = `<div style="font-weight:600;color:#e2e8f8;margin-bottom:7px">${varLabel}${isMock ? ' <span style="color:#fbbf24;font-size:9px">APROX.</span>' : ''}</div>`
      + palette.map((c, i) => `<div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
          <span style="width:12px;height:12px;border-radius:3px;background:${c};display:inline-block;flex-shrink:0"></span>
          <span>${labels[i]}</span></div>`).join('');
    return div;
  };
  choroplethLegendCtrl.addTo(mapInstance);
}

function renderMapLegend(html) {
  if (choroplethLegendCtrl) { mapInstance.removeControl(choroplethLegendCtrl); choroplethLegendCtrl = null; }
  choroplethLegendCtrl = L.control({ position: 'bottomright' });
  choroplethLegendCtrl.onAdd = () => {
    const div = L.DomUtil.create('div');
    div.style.cssText = 'background:#0c1221ee;border:1px solid #1c2d4a;border-radius:8px;padding:10px 12px;font-family:Space Grotesk,sans-serif;font-size:11px;color:#94a3b8;min-width:155px';
    div.innerHTML = html;
    return div;
  };
  choroplethLegendCtrl.addTo(mapInstance);
}

// Remove legend when switching away from choropleth
function clearChoroplethLegend() {
  if (choroplethLegendCtrl) { mapInstance.removeControl(choroplethLegendCtrl); choroplethLegendCtrl = null; }
}

function showMapMessage(msg) {
  const el = document.getElementById('map-message');
  if (el) { el.textContent = msg; el.style.display = 'block'; }
  else {
    const div = document.createElement('div');
    div.id = 'map-message';
    div.style.cssText = 'position:absolute;bottom:60px;left:50%;transform:translateX(-50%);background:#0c1221ee;border:1px solid #1c2d4a;color:#94a3b8;font-size:12px;padding:10px 16px;border-radius:8px;z-index:999;max-width:340px;text-align:center';
    div.textContent = msg;
    document.getElementById('map')?.appendChild(div);
    setTimeout(() => div.remove(), 6000);
  }
}

// ─── Animated counter ─────────────────────────────────────────────────────────
function animateCount(el, target, duration = 1200, decimals = 0) {
  // decimals = -1 means integer with NO thousands separator (e.g. year)
  const start = performance.now();
  const update = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3);
    const val = target * ease;
    let formatted = "";
    if (decimals === -1) {
      formatted = Math.round(val).toString();
    } else {
      formatted = decimals > 0 ? fmtDec(val) : fmt(Math.round(val));
    }
    if (el.id && el.id.includes('pct')) {
      formatted += '%';
    }
    el.textContent = formatted;
    if (progress < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

// ─── Sparkline helper ─────────────────────────────────────────────────────────
function drawSparkline(canvasId, values, color) {
  const canvas = document.getElementById(canvasId);
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  const min = Math.min(...values), max = Math.max(...values);
  const range = max - min || 1;
  const pts = values.map((v, i) => ({
    x: (i / (values.length - 1)) * W,
    y: H - ((v - min) / range) * (H - 4) - 2
  }));
  // Area fill
  const grad = ctx.createLinearGradient(0, 0, 0, H);
  grad.addColorStop(0, color + '55');
  grad.addColorStop(1, color + '00');
  ctx.beginPath();
  ctx.moveTo(pts[0].x, H);
  pts.forEach(p => ctx.lineTo(p.x, p.y));
  ctx.lineTo(pts[pts.length-1].x, H);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();
  // Line
  ctx.beginPath();
  pts.forEach((p, i) => i === 0 ? ctx.moveTo(p.x, p.y) : ctx.lineTo(p.x, p.y));
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.5;
  ctx.stroke();
  // Last dot
  const last = pts[pts.length - 1];
  ctx.beginPath();
  ctx.arc(last.x, last.y, 2.5, 0, Math.PI * 2);
  ctx.fillStyle = color;
  ctx.fill();
}

// ─── Dashboard ────────────────────────────────────────────────────────────────
function renderDashboard() {
  const kpi = getKPIs(SELECTED_YEAR);
  const ids = ['kpi-total','kpi-inc','kpi-crit','kpi-peak'];
  const vals = [kpi.total, kpi.incProm, kpi.critical, kpi.peakYear];
  const decs = [0, 1, 0, 0];
  ids.forEach((id, i) => {
    const el = document.getElementById(id);
    // año pico never gets decimal formatting
    if (el) animateCount(el, vals[i], 1000, id === 'kpi-peak' ? -1 : decs[i]);
  });

  // Sparklines — one value per year
  const totals = getYearTotals();
  const incByYear = YEARS.map(y => {
    const rows = getByYear(y);
    return rows.reduce((s,r) => s + r.incidencia_dengue, 0) / (rows.length || 1);
  });
  const critByYear = YEARS.map(y => getByYear(y).filter(r => r.incidencia_dengue > 400).length);
  drawSparkline('spark-total', totals.map(d => d.total), '#3b82f6');
  drawSparkline('spark-inc',   incByYear,                  '#22d3ee');
  drawSparkline('spark-crit',  critByYear,                 '#f87171');

  // Mini bar chart — casos por año
  const ctx1 = document.getElementById('mini-chart-1');
  if (ctx1) {
    if (charts['mini1']) charts['mini1'].destroy();
    const totals = getYearTotals();
    charts['mini1'] = new Chart(ctx1, {
      type: 'bar',
      data: {
        labels: totals.map(d => d.year),
        datasets: [{
          data: totals.map(d => d.total),
          backgroundColor: totals.map(d => d.year === SELECTED_YEAR ? '#3b82f6' : '#1e3a5f'),
          borderRadius: 4,
          borderSkipped: false,
        }]
      },
      options: { ...miniChartOpts(), plugins: { legend: { display: false } } }
    });
  }

  // Mini horizontal bar — top 5 municipios
  const ctx2 = document.getElementById('mini-chart-2');
  if (ctx2) {
    if (charts['mini2']) charts['mini2'].destroy();
    const top5 = getTopMunByYear(SELECTED_YEAR, 'conteo_dengue', 5, true);
    charts['mini2'] = new Chart(ctx2, {
      type: 'bar',
      data: {
        labels: top5.map(d => d.MPIO_CNMBR),
        datasets: [{
          data: top5.map(d => d.conteo_dengue),
          backgroundColor: ['#3b82f6','#22d3ee','#34d399','#fbbf24','#f87171'],
          borderRadius: 4,
          borderSkipped: false,
        }]
      },
      options: {
        ...miniChartOpts(),
        indexAxis: 'y',
        plugins: { legend: { display: false } }
      }
    });
  }
}

function miniChartOpts() {
  return {
    responsive: true, maintainAspectRatio: false,
    animation: { duration: 800 },
    scales: {
      x: { grid: { color: '#162038' }, ticks: { color: '#64748b', font: { family:'JetBrains Mono', size:10 } } },
      y: { grid: { color: '#162038' }, ticks: { color: '#64748b', font: { family:'JetBrains Mono', size:10 } } }
    }
  };
}

// ─── Geovisor ─────────────────────────────────────────────────────────────────
function initMap() {
  if (mapInstance) return;
  mapInstance = L.map('map', { zoomControl: false, preferCanvas: true })
    .setView([3.8, -76.5], 8);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '©OpenStreetMap ©CARTO', subdomains: 'abcd', maxZoom: 19
  }).addTo(mapInstance);

  L.control.zoom({ position: 'bottomright' }).addTo(mapInstance);
  renderMapLayer();
}

function renderMapLayer() {
  mapLayers.forEach(l => mapInstance.removeLayer(l));
  mapLayers = [];
  clearChoroplethLegend();
  const data = getByYear(SELECTED_YEAR).filter(r => INCLUDE_CALI || r.MPIO_CCDGO !== '76001');
  const maxCasos = Math.max(...data.map(r => r.conteo_dengue));

  const riskColor = v => v > 600 ? '#f87171' : v > 350 ? '#fbbf24' : v > 150 ? '#34d399' : '#3b82f6';

  if (MAP_MODE === 'burbujas') {
    data.forEach(r => {
      const radius = 6 + (r.conteo_dengue / maxCasos) * 38;
      const color = riskColor(r.incidencia_dengue);
      const circle = L.circleMarker([r.lat, r.lng], {
        radius, fillColor: color, color: color,
        weight: 1.5, fillOpacity: 0.35, opacity: 0.9
      }).addTo(mapInstance);
      circle.bindTooltip(munTooltip(r, color), { className: 'geo-tooltip' });
      if (r.incidencia_dengue > 500) {
        const pulse = L.circleMarker([r.lat, r.lng], {
          radius: radius + 8, fillColor: 'transparent',
          color: color, weight: 1, opacity: 0.4
        }).addTo(mapInstance);
        mapLayers.push(pulse);
      }
      mapLayers.push(circle);
    });

  } else if (MAP_MODE === 'coropletico' || MAP_MODE === 'riesgo' || MAP_MODE === 'delta') {
    // Use real PostGIS GeoJSON if available, otherwise fall back to mock octagons
    const geomSrc = (typeof window !== 'undefined' && window.GEO_MUNI)
      ? window.GEO_MUNI
      : buildMockGeoJSON();
    const isMock = geomSrc._mock === true;

    // Build lookup: code → record for current year/filter
    const lookup = {};
    const isRiesgo = MAP_MODE === 'riesgo';
    const isDelta = MAP_MODE === 'delta';
    let choroplethColor;

    if (isRiesgo) {
      if (typeof RISK_MAP !== 'undefined') Object.assign(lookup, RISK_MAP);
      if (!INCLUDE_CALI) delete lookup['76001'];
      const RC = { 'Crítico':'#f87171', 'CrÃ­tico':'#f87171', 'Alto':'#fbbf24', 'Medio':'#34d399', 'Bajo':'#3b82f6' };
      choroplethColor = rec => RC[rec?.nivel] || '#111827';
      renderMapLegend(`<b style="color:#e2e8f8">Nivel de riesgo</b>
        <div style="font-size:10px;color:#64748b;margin:4px 0 8px">Prom. incidencia 2022-24</div>`
        + ['Crítico','Alto','Medio','Bajo'].map(n =>
          `<div style="display:flex;align-items:center;gap:7px;margin-bottom:5px">
            <span style="width:12px;height:12px;border-radius:3px;background:${RC[n]};flex-shrink:0"></span>
            <span>${n}</span></div>`).join(''));
    } else if (isDelta) {
      if (typeof DELTA_MAP !== 'undefined') Object.assign(lookup, DELTA_MAP);
      if (!INCLUDE_CALI) delete lookup['76001'];
      const steps = [[-1e9,-30,'#1d4ed8'],[-30,-10,'#3b82f6'],[-10,0,'#93c5fd'],[0,10,'#fca5a5'],[10,30,'#f87171'],[30,1e9,'#dc2626']];
      choroplethColor = rec => {
        const d = rec?.delta_pct;
        if (d == null) return '#111827';
        return (steps.find(([lo, hi]) => d >= lo && d < hi) || [0, 0, '#111827'])[2];
      };
      renderMapLegend(`<b style="color:#e2e8f8">Cambio 2023 -> 2024</b>
        <div style="height:8px;border-radius:4px;background:linear-gradient(90deg,#1d4ed8,#93c5fd,#e2e8f8,#fca5a5,#dc2626);margin:8px 0 6px"></div>
        <div style="display:flex;justify-content:space-between;font-size:10px"><span>Baja</span><span>0</span><span>Sube</span></div>`);
    } else {
      data.forEach(r => { lookup[r.MPIO_CCDGO] = r; });
      const vals = data.map(r => r[MAP_VAR]).filter(v => v != null).sort((a, b) => a - b);
      const q = f => vals[Math.max(0, Math.floor((vals.length - 1) * f))];
      const bins = [q(0.2), q(0.4), q(0.6), q(0.8)];
      const CHORO_PALETTE = MAP_VAR === 'incidencia_dengue'
        ? ['#1e3a5f', '#1d4ed8', '#22d3ee', '#fbbf24', '#f87171']
        : ['#0f2040', '#1e3a5f', '#2d6aab', '#22d3ee', '#f87171'];
      choroplethColor = rec => {
        const v = rec?.[MAP_VAR];
        if (v == null) return '#111827';
        if (v > bins[3]) return CHORO_PALETTE[4];
        if (v > bins[2]) return CHORO_PALETTE[3];
        if (v > bins[1]) return CHORO_PALETTE[2];
        if (v > bins[0]) return CHORO_PALETTE[1];
        return CHORO_PALETTE[0];
      };
      renderChoroplethLegend(bins, CHORO_PALETTE, isMock);
    }

    const layer = L.geoJSON(geomSrc, {
      style: feat => {
        const code = feat.properties?.MPIO_CCDGO;
        const rec = lookup[code];
        const col = choroplethColor(rec);
        return {
          fillColor: col, color: '#060a12',
          weight: isMock ? 1.5 : 1,
          fillOpacity: isMock ? 0.80 : 0.78
        };
      },
      onEachFeature: (feat, lyr) => {
        const code = feat.properties?.MPIO_CCDGO;
        const name = feat.properties?.MPIO_CNMBR;
        const rec = lookup[code];
        if (rec) {
          const col = choroplethColor(rec);
          let tip;
          if (isRiesgo) {
            tip = `<div style="font-family:Space Grotesk,sans-serif;min-width:170px">
              <div style="font-weight:700;color:#e2e8f8;margin-bottom:6px">${name}</div>
              <div style="color:#94a3b8;font-size:12px">Nivel: <b style="color:${col}">${rec.nivel}</b></div>
              <div style="color:#94a3b8;font-size:12px">Inc. prom: <b style="color:#e2e8f8">${rec.inc_prom?.toFixed(1)}</b> x100k</div>
            </div>`;
          } else if (isDelta) {
            const sign = (rec.delta_pct ?? 0) >= 0 ? '+' : '';
            tip = `<div style="font-family:Space Grotesk,sans-serif;min-width:170px">
              <div style="font-weight:700;color:#e2e8f8;margin-bottom:6px">${name}</div>
              <div style="color:#94a3b8;font-size:12px">Cambio 2023-24: <b style="color:${col}">${sign}${rec.delta_pct?.toFixed(1) ?? '-'}%</b></div>
              <div style="color:#94a3b8;font-size:12px">Inc. 2023: <b>${rec.inc_2023?.toFixed(1)}</b></div>
              <div style="color:#94a3b8;font-size:12px">Inc. 2024: <b>${rec.inc_2024?.toFixed(1)}</b></div>
            </div>`;
          } else {
            tip = munTooltip(rec, col);
          }
          lyr.bindTooltip(tip, { className: 'geo-tooltip', sticky: true });
          lyr.on({
            mouseover: e => e.target.setStyle({ weight: 2.5, fillOpacity: 0.96, color: '#ffffff44' }),
            mouseout:  e => layer.resetStyle(e.target)
          });
        } else if (feat.properties?.MPIO_CNMBR) {
          // Feature exists in GeoJSON but not in current year/filter
          lyr.bindTooltip(feat.properties.MPIO_CNMBR + ' — sin datos', { className: 'geo-tooltip' });
        }
      }
    }).addTo(mapInstance);
    mapLayers.push(layer);
    try { mapInstance.fitBounds(layer.getBounds(), { padding: [16, 16] }); } catch(e) {}

    // Dynamic choropleth legend
    if (isMock) showMapMessage('Geometrías aproximadas — ejecuta exportar_datos_obs.py para polígonos reales de PostGIS');

  } else if (MAP_MODE === 'calor') {
    // Use municipality centroids weighted by selected variable
    const pts = data.map(r => {
      const weight = MAP_VAR === 'incidencia_dengue'
        ? r.incidencia_dengue / 800   // normalize ~0–1.5
        : r.conteo_dengue / Math.max(...data.map(d => d.conteo_dengue));
      return [r.lat, r.lng, Math.min(weight, 1.2)];
    });
    const heat = L.heatLayer(pts, {
      radius: 45,
      blur: 30,
      maxZoom: 12,
      minOpacity: 0.55,
      max: 1.0,
      gradient: {
        0.0: 'transparent',
        0.15: '#00f5ff',   // cyan neón
        0.35: '#0ea5e9',   // azul eléctrico
        0.55: '#a855f7',   // púrpura
        0.75: '#f59e0b',   // ámbar
        1.0:  '#ff2d55'    // rojo-magenta
      }
    }).addTo(mapInstance);
    mapLayers.push(heat);

    // Heat legend
    if (choroplethLegendCtrl) { mapInstance.removeControl(choroplethLegendCtrl); choroplethLegendCtrl = null; }
    choroplethLegendCtrl = L.control({ position: 'bottomright' });
    choroplethLegendCtrl.onAdd = () => {
      const div = L.DomUtil.create('div');
      div.style.cssText = 'background:#0c1221ee;border:1px solid #1c2d4a;border-radius:8px;padding:10px 14px;font-family:Space Grotesk,sans-serif;font-size:11px;color:#94a3b8;min-width:140px';
      const varLabel = MAP_VAR === 'incidencia_dengue' ? 'Incidencia ×100k' : 'Casos absolutos';
      div.innerHTML = `<div style="font-weight:600;color:#e2e8f8;margin-bottom:8px">${varLabel}</div>
        <div style="height:10px;border-radius:6px;background:linear-gradient(90deg,#00f5ff,#0ea5e9,#a855f7,#f59e0b,#ff2d55);margin-bottom:5px"></div>
        <div style="display:flex;justify-content:space-between;font-size:10px">
          <span>Bajo</span><span>Medio</span><span>Alto</span>
        </div>`;
      return div;
    };
    choroplethLegendCtrl.addTo(mapInstance);
  }

  // Update map stats
  const totalY = data.reduce((s, r) => s + r.conteo_dengue, 0);
  const avgInc = (data.reduce((s, r) => s + r.incidencia_dengue, 0) / data.length).toFixed(1);
  const el = document.getElementById('map-stats');
  if (el && MAP_MODE === 'riesgo' && typeof RISK_MAP !== 'undefined') {
    const values = Object.entries(RISK_MAP)
      .filter(([code]) => INCLUDE_CALI || code !== '76001')
      .map(([, r]) => r);
    const cnt = { 'Crítico':0, 'CrÃ­tico':0, 'Alto':0, 'Medio':0, 'Bajo':0 };
    values.forEach(r => { if (r.nivel in cnt) cnt[r.nivel]++; });
    const criticos = cnt['Crítico'] + cnt['CrÃ­tico'];
    el.innerHTML = `
      <div class="map-stat"><span class="map-stat-val" style="color:#f87171">${criticos}</span><span class="map-stat-lbl">críticos</span></div>
      <div class="map-stat"><span class="map-stat-val" style="color:#fbbf24">${cnt['Alto']}</span><span class="map-stat-lbl">alto</span></div>
      <div class="map-stat"><span class="map-stat-val">${values.length}</span><span class="map-stat-lbl">municipios</span></div>`;
    return;
  }
  if (el && MAP_MODE === 'delta' && typeof DELTA_MAP !== 'undefined') {
    const vals = Object.entries(DELTA_MAP)
      .filter(([code]) => INCLUDE_CALI || code !== '76001')
      .map(([, r]) => r.delta_pct)
      .filter(v => v != null);
    const mejoran = vals.filter(v => v < 0).length;
    const empeoran = vals.filter(v => v > 0).length;
    const med = [...vals].sort((a, b) => a - b)[Math.floor(vals.length / 2)];
    el.innerHTML = `
      <div class="map-stat"><span class="map-stat-val" style="color:#34d399">${mejoran}</span><span class="map-stat-lbl">mejoran</span></div>
      <div class="map-stat"><span class="map-stat-val" style="color:#f87171">${empeoran}</span><span class="map-stat-lbl">empeoran</span></div>
      <div class="map-stat"><span class="map-stat-val">${med != null ? (med >= 0 ? '+' : '') + med.toFixed(1) + '%' : '-'}</span><span class="map-stat-lbl">mediana</span></div>`;
    return;
  }
  if (el) el.innerHTML = `
    <div class="map-stat"><span class="map-stat-val">${fmt(totalY)}</span><span class="map-stat-lbl">casos ${SELECTED_YEAR}</span></div>
    <div class="map-stat"><span class="map-stat-val">${avgInc}</span><span class="map-stat-lbl">inc. prom ×100k</span></div>
    <div class="map-stat"><span class="map-stat-val">${data.length}</span><span class="map-stat-lbl">municipios</span></div>
  `;
}

// ─── Indicadores ──────────────────────────────────────────────────────────────
function renderIndicadores() {
  renderCasosAnio();
  renderTopMun();
  renderScatter();
}

function renderCasosAnio() {
  const ctx = document.getElementById('chart-casos-anio'); if (!ctx) return;
  if (charts['casosAnio']) charts['casosAnio'].destroy();
  const data = getYearTotals();
  charts['casosAnio'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: data.map(d => d.year),
      datasets: [{
        label: 'Casos totales',
        data: data.map(d => d.total),
        backgroundColor: data.map(d => d.year === SELECTED_YEAR ? '#3b82f6' : '#1e3a5f'),
        borderColor: data.map(d => d.year === SELECTED_YEAR ? '#60a5fa' : '#1e3a5f'),
        borderWidth: 1, borderRadius: 5, borderSkipped: false,
      }]
    },
    options: fullChartOpts({ yLabel: 'Casos', title: t('casos_anio') })
  });
}

function renderTopMun() {
  const ctx = document.getElementById('chart-top-mun'); if (!ctx) return;
  if (charts['topMun']) charts['topMun'].destroy();
  const top = getTopMunByYear(SELECTED_YEAR, 'incidencia_dengue', 10, INCLUDE_CALI);
  const colors = ['#f87171','#fbbf24','#34d399','#3b82f6','#22d3ee','#a78bfa',
                  '#fb923c','#e879f9','#4ade80','#38bdf8'];
  charts['topMun'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: top.map(d => d.MPIO_CNMBR),
      datasets: [{
        label: 'Incidencia ×100k',
        data: top.map(d => d.incidencia_dengue),
        backgroundColor: colors, borderRadius: 5, borderSkipped: false,
      }]
    },
    options: { ...fullChartOpts({ yLabel: '×100k', title: t('top_mun') }), indexAxis: 'y' }
  });
}

function renderScatter() {
  const ctx = document.getElementById('chart-scatter'); if (!ctx) return;
  if (charts['scatter']) charts['scatter'].destroy();
  const data = getByYear(SELECTED_YEAR).filter(r => INCLUDE_CALI || r.MPIO_CCDGO !== '76001');
  charts['scatter'] = new Chart(ctx, {
    type: 'scatter',
    data: {
      datasets: [{
        label: 'Municipios',
        data: data.map(r => ({ x: r.población, y: r.incidencia_dengue, label: r.MPIO_CNMBR })),
        backgroundColor: '#3b82f680', borderColor: '#3b82f6',
        borderWidth: 1, pointRadius: 7, pointHoverRadius: 10,
      }]
    },
    options: {
      ...fullChartOpts({ xLabel: 'Población', yLabel: 'Incidencia ×100k', title: t('pob_inc') }),
      plugins: {
        tooltip: {
          callbacks: {
            label: ctx => `${ctx.raw.label}: ${fmt(ctx.raw.x)} hab. · ${fmtDec(ctx.raw.y)} ×100k`
          }
        },
        legend: { display: false }
      }
    }
  });
}

// ─── Weekly Series Helper ─────────────────────────────────────────────────────
function getWeeklySeries(munCode, year) {
  const munData = getByMun(munCode);
  const yearData = munData.find(d => d.año === year);
  const totalCases = yearData?.conteo_dengue || 0;
  const population = yearData?.población || yearData?.poblacion || 100000;

  // Bimodal seasonal curve typical for Valle del Cauca (peaks around wk 16 and wk 40)
  const seasonalCurve = [];
  let sumCurve = 0;
  for (let w = 1; w <= 52; w++) {
    const peak1 = Math.exp(-Math.pow((w - 16) / 6, 2));
    const peak2 = 0.7 * Math.exp(-Math.pow((w - 40) / 8, 2));
    const baseline = 0.15;
    const val = baseline + peak1 + peak2;
    seasonalCurve.push(val);
    sumCurve += val;
  }
  const P = seasonalCurve.map(v => v / sumCurve);

  const pseudoRandom = (w) => {
    const x = Math.sin(year * 100 + w) * 10000;
    return x - Math.floor(x);
  };

  const cases = [];
  const incidence = [];

  for (let w = 1; w <= 52; w++) {
    const noise = 1 + (pseudoRandom(w) - 0.5) * 0.3;
    const weekShare = P[w - 1] * noise;
    const cVal = Math.max(0, Math.round(totalCases * weekShare));
    cases.push(cVal);

    const iVal = population > 0 ? (cVal / population) * 100000 : 0;
    incidence.push(parseFloat(iVal.toFixed(2)));
  }

  return { cases, incidence };
}

// ─── Endemic Channel Logic ───────────────────────────────────────────────────
function calculateEndemicChannel(munCode, selectedYear, metric = 'conteo_dengue') {
  const munData = getByMun(munCode);

  // Use historical years (excluding selected year and 2026/future if not fully recorded)
  const historicalYearsData = munData.filter(d => d.año !== selectedYear && d.año <= 2025);

  // Bimodal seasonal curve typical for Valle del Cauca (peaks around wk 16 and wk 40)
  const seasonalCurve = [];
  let sumCurve = 0;
  for (let w = 1; w <= 52; w++) {
    const peak1 = Math.exp(-Math.pow((w - 16) / 6, 2));
    const peak2 = 0.7 * Math.exp(-Math.pow((w - 40) / 8, 2));
    const baseline = 0.15;
    const val = baseline + peak1 + peak2;
    seasonalCurve.push(val);
    sumCurve += val;
  }

  const P = seasonalCurve.map(v => v / sumCurve);
  const historicalWeeklySeries = [];

  historicalYearsData.forEach((d, yrIdx) => {
    const annualTotal = d.conteo_dengue;
    const population = d.población || d.poblacion || 100000;
    const weeklyValues = [];
    const pseudoRandom = (seed) => {
      const x = Math.sin(seed) * 10000;
      return x - Math.floor(x);
    };

    for (let w = 1; w <= 52; w++) {
      const seed = yrIdx * 52 + w;
      const noise = 1 + (pseudoRandom(seed) - 0.5) * 0.4;
      const weekShare = P[w - 1] * noise;
      const cVal = Math.max(0, Math.round(annualTotal * weekShare));

      if (metric === 'incidencia_dengue') {
        const iVal = population > 0 ? (cVal / population) * 100000 : 0;
        weeklyValues.push(iVal);
      } else {
        weeklyValues.push(cVal);
      }
    }
    historicalWeeklySeries.push(weeklyValues);
  });

  if (historicalWeeklySeries.length === 0) {
    const dummySeries = [];
    const base = munData.find(d => d.año === selectedYear) || { conteo_dengue: 100, población: 100000 };
    for (let y = 0; y < 3; y++) {
      const weeklyValues = [];
      for (let w = 1; w <= 52; w++) {
        const cVal = Math.round(base.conteo_dengue * P[w - 1] * (0.8 + y * 0.2));
        if (metric === 'incidencia_dengue') {
          const basePop = base.población || base.poblacion || 100000;
          const iVal = basePop > 0 ? (cVal / basePop) * 100000 : 0;
          weeklyValues.push(iVal);
        } else {
          weeklyValues.push(cVal);
        }
      }
      dummySeries.push(weeklyValues);
    }
    historicalWeeklySeries.push(...dummySeries);
  }

  const q1 = []; // 25th percentile (Exito)
  const q2 = []; // 50th percentile (Seguridad)
  const q3 = []; // 75th percentile (Alerta)

  for (let w = 0; w < 52; w++) {
    const weekVals = historicalWeeklySeries.map(series => series[w]).sort((a, b) => a - b);
    const getPercentile = (arr, p) => {
      const idx = (arr.length - 1) * p;
      const base = Math.floor(idx);
      const rest = idx - base;
      if (arr[base + 1] !== undefined) {
        return arr[base] + rest * (arr[base + 1] - arr[base]);
      }
      return arr[base];
    };

    const isInc = metric === 'incidencia_dengue';
    q1.push(isInc ? parseFloat(getPercentile(weekVals, 0.25).toFixed(2)) : Math.round(getPercentile(weekVals, 0.25)));
    q2.push(isInc ? parseFloat(getPercentile(weekVals, 0.50).toFixed(2)) : Math.round(getPercentile(weekVals, 0.50)));
    q3.push(isInc ? parseFloat(getPercentile(weekVals, 0.75).toFixed(2)) : Math.round(getPercentile(weekVals, 0.75)));
  }

  const selectedYearData = munData.find(d => d.año === selectedYear) || { conteo_dengue: 0, población: 100000 };
  const currentWeekly = [];
  const pseudoRandomCurrent = (w) => {
    const x = Math.sin(selectedYear * 100 + w) * 10000;
    return x - Math.floor(x);
  };

  for (let w = 1; w <= 52; w++) {
    const noise = 1 + (pseudoRandomCurrent(w) - 0.5) * 0.3;
    const weekShare = P[w - 1] * noise;
    const cVal = Math.max(0, Math.round(selectedYearData.conteo_dengue * weekShare));
    if (metric === 'incidencia_dengue') {
      const selectedPop = selectedYearData.población || selectedYearData.poblacion || 100000;
      const iVal = selectedPop > 0 ? (cVal / selectedPop) * 100000 : 0;
      currentWeekly.push(parseFloat(iVal.toFixed(2)));
    } else {
      currentWeekly.push(cVal);
    }
  }

  return { success: q1, safety: q2, alert: q3, current: currentWeekly };
}

// ─── Tendencias ───────────────────────────────────────────────────────────────
function renderTendencias() {
  // Sync UI controls with global state
  const metricaCtrl = document.getElementById('tendencias-metrica-ctrl');
  if (metricaCtrl) {
    metricaCtrl.querySelectorAll('.segmented-btn').forEach(btn => {
      if (btn.getAttribute('data-val') === TENDENCIA_METRIC) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    if (!metricaCtrl.dataset.wired) {
      metricaCtrl.dataset.wired = 'true';
      metricaCtrl.querySelectorAll('.segmented-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          TENDENCIA_METRIC = btn.getAttribute('data-val');
          renderTendencias();
        });
      });
    }
  }

  const escalaCtrl = document.getElementById('tendencias-escala-ctrl');
  if (escalaCtrl) {
    escalaCtrl.querySelectorAll('.segmented-btn').forEach(btn => {
      if (btn.getAttribute('data-val') === TENDENCIA_SCALE) {
        btn.classList.add('active');
      } else {
        btn.classList.remove('active');
      }
    });

    if (!escalaCtrl.dataset.wired) {
      escalaCtrl.dataset.wired = 'true';
      escalaCtrl.querySelectorAll('.segmented-btn').forEach(btn => {
        btn.addEventListener('click', e => {
          TENDENCIA_SCALE = btn.getAttribute('data-val');
          renderTendencias();
        });
      });
    }
  }

  const codes = TENDENCIA_CODES?.length ? TENDENCIA_CODES : [SELECTED_MUN, '76520', '76109'];
  const uniqueCodes = [...new Set(codes)].slice(0, 6);
  const palette = ['#3b82f6', '#22d3ee', '#34d399', '#fbbf24', '#f87171', '#a78bfa'];
  const selectedMunName = MUN_CATALOG.find(m => m.code === SELECTED_MUN)?.name || SELECTED_MUN;

  // Clean existing charts in our canvas slots
  if (charts['tendencias-1']) {
    charts['tendencias-1'].destroy();
    delete charts['tendencias-1'];
  }
  if (charts['tendencias-2']) {
    charts['tendencias-2'].destroy();
    delete charts['tendencias-2'];
  }

  const ctx1 = document.getElementById('chart-tendencias-1');
  const ctx2 = document.getElementById('chart-tendencias-2');

  if (TENDENCIA_SCALE === 'anual') {
    // 1. Chart 1: Comparativo Anual Intermunicipal
    const title1 = TENDENCIA_METRIC === 'conteo_dengue'
      ? 'Comparativo Anual Intermunicipal (Casos)'
      : 'Comparativo Anual Intermunicipal (Incidencia ×100k)';
    document.getElementById('title-tendencias-1').textContent = title1;

    if (ctx1) {
      const yLabel = TENDENCIA_METRIC === 'conteo_dengue' ? 'Casos' : 'Incidencia x100k';
      const datasets = uniqueCodes.map((code, i) => {
        const mun = MUN_CATALOG.find(m => m.code === code);
        const rows = getByMun(code);
        return {
          label: mun?.name || code,
          data: rows.map(r => r[TENDENCIA_METRIC]),
          borderColor: palette[i],
          backgroundColor: palette[i] + '18',
          borderWidth: 2.5,
          pointRadius: 5,
          pointHoverRadius: 8,
          tension: 0.4,
          fill: true
        };
      });

      charts['tendencias-1'] = new Chart(ctx1, {
        type: 'line',
        data: { labels: YEARS, datasets },
        options: fullChartOpts({ yLabel, title: '' })
      });
    }

    // 2. Chart 2: Evolución Anual Dual-Axis (selected municipality)
    const title2 = `Evolución Anual — ${selectedMunName}`;
    document.getElementById('title-tendencias-2').textContent = title2;

    if (ctx2) {
      const rows = getByMun(SELECTED_MUN);
      const datasetCases = {
        type: 'bar',
        label: 'Casos absolutos',
        data: rows.map(r => r.conteo_dengue),
        yAxisID: 'y',
        backgroundColor: 'rgba(59, 130, 246, 0.45)',
        borderColor: '#3b82f6',
        borderWidth: 1.5,
        borderRadius: 4
      };

      const datasetIncidence = {
        type: 'line',
        label: 'Incidencia ×100k',
        data: rows.map(r => r.incidencia_dengue),
        yAxisID: 'y1',
        borderColor: '#22d3ee',
        borderWidth: 2.5,
        pointRadius: 4,
        pointHoverRadius: 6,
        tension: 0.4,
        fill: false
      };

      charts['tendencias-2'] = new Chart(ctx2, {
        data: {
          labels: YEARS,
          datasets: [datasetCases, datasetIncidence]
        },
        options: {
          ...fullChartOpts({ title: '' }),
          scales: {
            x: {
              grid: { color: '#162038' },
              ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 11 } }
            },
            y: {
              type: 'linear',
              position: 'left',
              grid: { color: '#162038' },
              ticks: { color: '#3b82f6', font: { family: 'JetBrains Mono', size: 11 } },
              title: { display: true, text: 'Casos absolutos', color: '#3b82f6', font: { size: 11, family: 'Space Grotesk' } }
            },
            y1: {
              type: 'linear',
              position: 'right',
              grid: { drawOnChartArea: false },
              ticks: { color: '#22d3ee', font: { family: 'JetBrains Mono', size: 11 } },
              title: { display: true, text: 'Incidencia ×100k', color: '#22d3ee', font: { size: 11, family: 'Space Grotesk' } }
            }
          }
        }
      });
    }

  } else {
    // TENDENCIA_SCALE === 'semanal'
    // 1. Chart 1: Comparativo Semanal Interanual
    const title1 = TENDENCIA_METRIC === 'conteo_dengue'
      ? `Comparativo Semanal Interanual (Casos) — ${selectedMunName}`
      : `Comparativo Semanal Interanual (Incidencia ×100k) — ${selectedMunName}`;
    document.getElementById('title-tendencias-1').textContent = title1;

    if (ctx1) {
      const weekLabels = Array.from({ length: 52 }, (_, i) => `${i + 1}`);
      const compareYears = [2023, 2024, 2025, 2026];
      const yearColors = {
        2023: '#f87171',
        2024: '#3b82f6',
        2025: '#34d399',
        2026: '#fbbf24'
      };

      const datasets = compareYears.map(yr => {
        const weekly = getWeeklySeries(SELECTED_MUN, yr);
        const data = TENDENCIA_METRIC === 'conteo_dengue' ? weekly.cases : weekly.incidence;
        return {
          label: `Año ${yr}`,
          data: data,
          borderColor: yearColors[yr],
          backgroundColor: yearColors[yr] + '0c',
          borderWidth: 2.5,
          pointRadius: 1.5,
          pointHoverRadius: 4,
          tension: 0.3,
          fill: false
        };
      });

      const yLabel = TENDENCIA_METRIC === 'conteo_dengue' ? 'Casos' : 'Incidencia x100k';
      charts['tendencias-1'] = new Chart(ctx1, {
        type: 'line',
        data: { labels: weekLabels, datasets },
        options: {
          ...fullChartOpts({ yLabel, title: '' }),
          interaction: { mode: 'index', intersect: false },
          scales: {
            x: {
              grid: { color: '#162038' },
              ticks: { color: '#64748b', maxTicksLimit: 12, font: { family: 'JetBrains Mono', size: 9 } }
            },
            y: {
              grid: { color: '#162038' },
              ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 10 } }
            }
          }
        }
      });
    }

    // 2. Chart 2: Canal Endémico Semanal
    const title2 = `Canal Endémico Semanal — ${selectedMunName} (${SELECTED_YEAR})`;
    document.getElementById('title-tendencias-2').textContent = title2;

    if (ctx2) {
      const channel = calculateEndemicChannel(SELECTED_MUN, SELECTED_YEAR, TENDENCIA_METRIC);
      const weekLabels = Array.from({ length: 52 }, (_, i) => `${i + 1}`);
      const yLabel = TENDENCIA_METRIC === 'conteo_dengue' ? 'Casos' : 'Incidencia x100k';

      charts['tendencias-2'] = new Chart(ctx2, {
        type: 'line',
        data: {
          labels: weekLabels,
          datasets: [
            {
              label: `${TENDENCIA_METRIC === 'conteo_dengue' ? 'Casos' : 'Incidencia'} ${SELECTED_YEAR}`,
              data: channel.current,
              borderColor: '#3b82f6',
              borderWidth: 3,
              pointRadius: 2,
              pointHoverRadius: 5,
              tension: 0.3,
              fill: false
            },
            {
              label: 'Alerta / Brote (Q3)',
              data: channel.alert,
              borderColor: '#f87171',
              backgroundColor: 'rgba(248, 113, 113, 0.15)',
              borderWidth: 1.5,
              pointRadius: 0,
              fill: 'origin',
              tension: 0.3
            },
            {
              label: 'Seguridad (Q2)',
              data: channel.safety,
              borderColor: '#fbbf24',
              backgroundColor: 'rgba(251, 191, 36, 0.15)',
              borderWidth: 1.5,
              pointRadius: 0,
              fill: 'origin',
              tension: 0.3
            },
            {
              label: 'Éxito (Q1)',
              data: channel.success,
              borderColor: '#34d399',
              backgroundColor: 'rgba(52, 211, 153, 0.15)',
              borderWidth: 1.5,
              pointRadius: 0,
              fill: 'origin',
              tension: 0.3
            }
          ]
        },
        options: {
          ...fullChartOpts({ yLabel, title: '' }),
          interaction: { mode: 'index', intersect: false },
          plugins: {
            legend: { labels: { color: '#94a3b8', font: { size: 10 } } }
          },
          scales: {
            x: { grid: { color: '#162038' }, ticks: { color: '#64748b', maxTicksLimit: 12, font: { family:'JetBrains Mono', size:9 } } },
            y: { grid: { color: '#162038' }, ticks: { color: '#64748b', font: { family:'JetBrains Mono', size:10 } } }
          }
        }
      });
    }
  }

  // Populate municipality selector
  const sel = document.getElementById('mun-select');
  if (sel && sel.options.length === 0) {
    MUN_CATALOG.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.code; opt.textContent = m.name;
      if (m.code === SELECTED_MUN) opt.selected = true;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', e => {
      SELECTED_MUN = e.target.value;
      TENDENCIA_CODES = null;
      renderTendencias();
    });
  }
  if (sel && uniqueCodes[0]) sel.value = uniqueCodes[0];
}
function normalizeMunicipioName(value) {
  return String(value || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase()
    .replace(/\s+/g, ' ')
    .trim();
}

function municipioCodeFromChat(value) {
  let raw = String(value || '').trim();
  
  // Resilient mapping for database-corrupted or differently formatted strings
  const corruptMap = {
    'JAMUND?': 'Jamundí',
    'TULU?': 'Tuluá',
    'ALCAL?': 'Alcalá',
    'ANDALUC?A': 'Andalucía',
    'BOL?VAR': 'Bolívar',
    'EL ?GUILA': 'El Águila',
    'GUACAR?': 'Guacarí',
    'LA UNI?N': 'La Unión',
    'RIOFR?O': 'Riofrío',
    'JAMUNDI': 'Jamundí',
    'TULUA': 'Tuluá',
    'ALCALA': 'Alcalá',
    'ANDALUCIA': 'Andalucía',
    'BOLIVAR': 'Bolívar',
    'EL AGUILA': 'El Águila',
    'GUACARI': 'Guacarí',
    'LA UNION': 'La Unión',
    'RIOFRIO': 'Riofrío'
  };

  const upperRaw = raw.toUpperCase();
  if (corruptMap[upperRaw]) {
    raw = corruptMap[upperRaw];
  }

  const byCode = MUN_CATALOG.find(m => m.code === raw);
  if (byCode) return byCode.code;

  const normalized = normalizeMunicipioName(raw);
  const byName = MUN_CATALOG.find(m => normalizeMunicipioName(m.name) === normalized);
  if (byName) return byName.code;

  // Fallback fuzzy/partial match
  const normalizedNoSpaces = normalized.replace(/\s+/g, '');
  const byNameNoSpaces = MUN_CATALOG.find(m => {
    const normName = normalizeMunicipioName(m.name).replace(/\s+/g, '');
    return normName === normalizedNoSpaces || normName.includes(normalizedNoSpaces) || normalizedNoSpaces.includes(normName);
  });
  if (byNameNoSpaces) return byNameNoSpaces.code;

  // Support common aliases
  if (normalized === 'buga') {
    const bugaObj = MUN_CATALOG.find(m => m.name.toLowerCase().includes('buga'));
    if (bugaObj) return bugaObj.code;
  }

  console.warn(`municipioCodeFromChat: Could not resolve code for "${value}"`);
  return null;
}

function setSelectedYearFromChat(year) {
  const parsed = parseInt(year);
  if (!YEARS.includes(parsed)) return;
  SELECTED_YEAR = parsed;
  const yearSel = document.getElementById('year-select');
  if (yearSel) yearSel.value = String(parsed);
  const mapYearSel = document.getElementById('map-year');
  if (mapYearSel) mapYearSel.value = String(parsed);
  const idx = YEARS.indexOf(SELECTED_YEAR);
  const bar = document.getElementById('year-progress');
  if (bar) bar.style.width = (((idx + 1) / YEARS.length) * 100) + '%';
}

function syncMapControlsFromChat() {
  const mapYearSel = document.getElementById('map-year');
  if (mapYearSel) mapYearSel.value = String(SELECTED_YEAR);
  const mapVarSel = document.getElementById('map-var');
  if (mapVarSel) mapVarSel.value = MAP_VAR;
  const caliToggle = document.getElementById('cali-toggle');
  if (caliToggle) caliToggle.checked = INCLUDE_CALI;
  document.querySelectorAll('.map-mode-btn[data-mode]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.mode === MAP_MODE);
  });
}

function syncChoroControlsFromChat() {
  document.querySelectorAll('[data-cv]').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.cv === CHORO_VAR);
  });
  document.querySelectorAll('.year-pill-btn').forEach(btn => {
    btn.classList.toggle('active', parseInt(btn.textContent) === CHORO_YEAR);
  });
  const caliToggle = document.getElementById('choro-cali');
  if (caliToggle) caliToggle.checked = CHORO_CALI;
}

function applyGeoSaludChatAction(action) {
  if (!action) return;

  if (action.type === 'navigate') {
    if (action.anio) setSelectedYearFromChat(action.anio);
    navigate(action.section || 'dashboard');
    return;
  }

  if (action.type === 'show_coropletico') {
    if (action.anio) setSelectedYearFromChat(action.anio);
    const variable = action.variable || 'incidencia_dengue';
    MAP_MODE = variable === 'riesgo' || variable === 'delta' ? variable : 'coropletico';
    if (variable !== 'riesgo' && variable !== 'delta') MAP_VAR = variable;
    if (typeof action.includeCali === 'boolean') INCLUDE_CALI = action.includeCali;
    navigate('geovisor');
    setTimeout(() => {
      syncMapControlsFromChat();
      if (!mapInstance) initMap();
      else renderMapLayer();
    }, 180);
    return;
  }

  if (action.type === 'show_geovisor') {
    if (action.anio) setSelectedYearFromChat(action.anio);
    MAP_MODE = action.mode || 'burbujas';
    MAP_VAR = action.variable || 'incidencia_dengue';
    if (typeof action.includeCali === 'boolean') INCLUDE_CALI = action.includeCali;
    navigate('geovisor');
    setTimeout(() => {
      syncMapControlsFromChat();
      if (!mapInstance) initMap();
      else renderMapLayer();
    }, 180);
    return;
  }

  if (action.type !== 'show_tendencias') return;
  const codes = (action.municipios || [])
    .map(municipioCodeFromChat)
    .filter(Boolean);
  if (!codes.length) return;

  TENDENCIA_CODES = [...new Set(codes)].slice(0, 6);
  TENDENCIA_METRIC = action.metrica === 'casos' ? 'conteo_dengue' : 'incidencia_dengue';
  SELECTED_MUN = TENDENCIA_CODES[0];
  navigate('tendencias');
}

window.applyGeoSaludChatAction = applyGeoSaludChatAction;

// ─── Priorización ─────────────────────────────────────────────────────────────
function renderPriorizacion() {
  const tbody = document.getElementById('prio-tbody'); if (!tbody) return;
  const rows = getPivotTable();
  tbody.innerHTML = rows.map(r => {
    const riskColor = RISK_COLOR[r.risk] || '#64748b';
    const trendIcon = r.trend === 'up' ? '↑' : r.trend === 'down' ? '↓' : '→';
    const trendColor = r.trend === 'up' ? '#f87171' : r.trend === 'down' ? '#34d399' : '#64748b';
    return `<tr class="prio-row">
      <td class="prio-rank">${r.rank}</td>
      <td class="prio-name">${r.name}</td>
      <td class="prio-num">${fmt(r.totalCasos)}</td>
      <td class="prio-num">${fmtDec(r.inc2024)}</td>
      <td class="prio-num">${r.pct}%</td>
      <td><span class="risk-badge" style="--rc:${riskColor}">${riskLabel(r.risk)}</span></td>
      <td style="color:${trendColor};font-size:18px;text-align:center">${trendIcon}</td>
    </tr>`;
  }).join('');
}

// ─── Chart base options ───────────────────────────────────────────────────────
function fullChartOpts({ xLabel = '', yLabel = '', title = '' } = {}) {
  return {
    responsive: true, maintainAspectRatio: false,
    animation: { duration: 800, easing: 'easeOutQuart' },
    plugins: {
      legend: { labels: { color: '#94a3b8', font: { family: 'Space Grotesk', size: 12 } } },
      title: title ? { display: true, text: title, color: '#e2e8f8', font: { family: 'Space Grotesk', size: 14, weight: '600' }, padding: { bottom: 12 } } : { display: false },
      tooltip: {
        backgroundColor: '#0c1221', borderColor: '#1e2d45', borderWidth: 1,
        titleColor: '#e2e8f8', bodyColor: '#94a3b8',
        titleFont: { family: 'Space Grotesk', weight: '600' },
        bodyFont: { family: 'JetBrains Mono', size: 11 },
        padding: 10, callbacks: { label: ctx => ` ${fmt(ctx.parsed.y ?? ctx.parsed.x ?? ctx.raw)}` }
      }
    },
    scales: {
      x: {
        grid: { color: '#162038' },
        ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 11 } },
        title: xLabel ? { display: true, text: xLabel, color: '#64748b', font: { size: 11 } } : { display: false }
      },
      y: {
        grid: { color: '#162038' },
        ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 11 } },
        title: yLabel ? { display: true, text: yLabel, color: '#64748b', font: { size: 11 } } : { display: false }
      }
    }
  };
}

// ─── Year selector ────────────────────────────────────────────────────────────
function buildYearSelector() {
  const sel = document.getElementById('year-select');
  if (!sel) return;
  YEARS.forEach(y => {
    const opt = document.createElement('option');
    opt.value = y; opt.textContent = y;
    if (y === SELECTED_YEAR) opt.selected = true;
    sel.appendChild(opt);
  });
  const updateProgress = () => {
    const bar = document.getElementById('year-progress');
    if (!bar) return;
    const idx = YEARS.indexOf(SELECTED_YEAR);
    const pct = ((idx + 1) / YEARS.length) * 100;
    bar.style.width = pct + '%';
  };
  sel.addEventListener('change', e => {
    SELECTED_YEAR = parseInt(e.target.value);
    updateProgress();
    if (ACTIVE_SECTION === 'geovisor') renderMapLayer();
    else navigate(ACTIVE_SECTION);
  });
  updateProgress();
}

// ─── Map controls wiring ──────────────────────────────────────────────────────
function wireMapControls() {
  // Year selector
  const mapYearSel = document.getElementById('map-year');
  if (mapYearSel) {
    YEARS.forEach(y => {
      const opt = document.createElement('option');
      opt.value = y; opt.textContent = y;
      if (y === SELECTED_YEAR) opt.selected = true;
      mapYearSel.appendChild(opt);
    });
    mapYearSel.addEventListener('change', e => {
      SELECTED_YEAR = parseInt(e.target.value);
      renderMapLayer();
    });
  }

  // Mode buttons
  document.querySelectorAll('.map-mode-btn[data-mode]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.map-mode-btn[data-mode]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      MAP_MODE = btn.dataset.mode;
      // Show choropleth hint if no GeoJSON yet
      if (MAP_MODE === 'coropletico' && !(window.GEO_MUNI)) {
        showMapMessage('Modo coroplético: ejecuta exportar_datos_obs.py y activa geodata-muni.js en el HTML');
      }
      renderMapLayer();
    });
  });

  // Variable selector
  const mapVarSel = document.getElementById('map-var');
  if (mapVarSel) {
    mapVarSel.addEventListener('change', e => {
      MAP_VAR = e.target.value;
      renderMapLayer();
    });
  }

  // Cali toggle
  const caliToggle = document.getElementById('cali-toggle');
  if (caliToggle) {
    caliToggle.addEventListener('change', e => {
      INCLUDE_CALI = e.target.checked;
      renderMapLayer();
    });
  }

  // Data source badge
  const badge = document.getElementById('data-source-badge');
  if (badge) {
    const isReal = typeof DATA_SOURCE !== 'undefined' && DATA_SOURCE !== 'mock';
    badge.textContent = isReal ? '⬡ PostgreSQL' : '⬡ Mock data';
    badge.style.color = isReal ? 'var(--accent-3)' : 'var(--warn)';
  }
}

// ─── Disease selector (header) ────────────────────────────────────────────────
function wireDiseaseSelector() {
  document.querySelectorAll('.disease-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      if (btn.classList.contains('disabled')) return;
      document.querySelectorAll('.disease-btn').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
    });
  });
}

// ─── Tweaks panel ─────────────────────────────────────────────────────────────
const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "accentColor": "#3b82f6",
  "secondaryColor": "#22d3ee",
  "bgColor": "#060a12",
  "animationsEnabled": true
}/*EDITMODE-END*/;

let tweaks = { ...TWEAK_DEFAULTS };

function applyTweaks() {
  document.documentElement.style.setProperty('--accent', tweaks.accentColor);
  document.documentElement.style.setProperty('--accent-2', tweaks.secondaryColor);
  document.documentElement.style.setProperty('--bg', tweaks.bgColor);
}

function buildTweaksPanel() {
  const panel = document.getElementById('tweaks-panel');
  if (!panel) return;
  panel.innerHTML = `
    <div class="tweaks-header"><span>Tweaks</span><button class="tweaks-close" onclick="hideTweaks()">✕</button></div>
    <div class="tweaks-body">
      <label class="tweak-label">Accent color
        <input type="color" value="${tweaks.accentColor}" oninput="setTweak('accentColor',this.value)">
      </label>
      <label class="tweak-label">Secondary color
        <input type="color" value="${tweaks.secondaryColor}" oninput="setTweak('secondaryColor',this.value)">
      </label>
      <label class="tweak-label">Background
        <input type="color" value="${tweaks.bgColor}" oninput="setTweak('bgColor',this.value)">
      </label>
      <label class="tweak-label tweak-row">Animations
        <input type="checkbox" ${tweaks.animationsEnabled ? 'checked' : ''} onchange="setTweak('animationsEnabled',this.checked)">
      </label>
    </div>
  `;
}

function setTweak(key, val) {
  tweaks[key] = val;
  applyTweaks();
  window.parent.postMessage({ type: '__edit_mode_set_keys', edits: tweaks }, '*');
}

function hideTweaks() { document.getElementById('tweaks-panel').style.display = 'none'; }

window.addEventListener('message', e => {
  if (e.data?.type === '__activate_edit_mode') {
    const p = document.getElementById('tweaks-panel');
    if (p) p.style.display = 'block';
  }
  if (e.data?.type === '__deactivate_edit_mode') {
    hideTweaks();
  }
});
window.parent.postMessage({ type: '__edit_mode_available' }, '*');

// ─── Coropléticos ─────────────────────────────────────────────────────────────
function initChoroMap() {
  if (choroMap) { choroMap.invalidateSize(); renderChoroLayer(); return; }
  choroMap = L.map('choro-map', { zoomControl: false, preferCanvas: true })
    .setView([3.8, -76.5], 8);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '©OpenStreetMap ©CARTO', subdomains: 'abcd', maxZoom: 19
  }).addTo(choroMap);
  L.control.zoom({ position: 'bottomright' }).addTo(choroMap);

  const pillsCont = document.getElementById('choro-year-pills');
  if (pillsCont && !pillsCont.children.length) {
    const chorYears = typeof YEARS !== 'undefined' ? YEARS.filter(y => y <= 2024) : [2019,2020,2021,2022,2023,2024];
    chorYears.forEach(y => {
      const btn = document.createElement('button');
      btn.className = 'year-pill-btn' + (y === CHORO_YEAR ? ' active' : '');
      btn.textContent = y;
      btn.addEventListener('click', () => {
        CHORO_YEAR = y;
        document.querySelectorAll('.year-pill-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        renderChoroLayer();
      });
      pillsCont.appendChild(btn);
    });
  }
  renderChoroLayer();
}

function renderChoroLayer() {
  if (!choroMap || typeof GEO_MUNI === 'undefined') return;
  choroMapLayers.forEach(l => choroMap.removeLayer(l));
  choroMapLayers = [];
  if (chorLegend) { choroMap.removeControl(chorLegend); chorLegend = null; }

  const isRiesgo = CHORO_VAR === 'riesgo';
  const isDelta  = CHORO_VAR === 'delta';

  const yearSect = document.getElementById('choro-year-sect');
  if (yearSect) yearSect.style.display = (isRiesgo || isDelta) ? 'none' : '';

  const lookup = {};
  if (isRiesgo) {
    if (typeof RISK_MAP !== 'undefined') Object.assign(lookup, RISK_MAP);
  } else if (isDelta) {
    if (typeof DELTA_MAP !== 'undefined') Object.assign(lookup, DELTA_MAP);
  } else {
    getByYear(CHORO_YEAR).filter(r => CHORO_CALI || r.MPIO_CCDGO !== '76001')
      .forEach(r => { lookup[r.MPIO_CCDGO] = r; });
  }

  let colorFn, legendHtml;

  if (isRiesgo) {
    const RC = { 'Crítico':'#f87171', 'Alto':'#fbbf24', 'Medio':'#34d399', 'Bajo':'#3b82f6' };
    colorFn = code => RC[lookup[code]?.nivel] || '#111827';
    legendHtml = `<b style="color:#e2e8f8">Nivel de riesgo</b>
      <div style="font-size:10px;color:#64748b;margin:4px 0 8px">Prom. incidencia 2022–24</div>`
      + ['Crítico','Alto','Medio','Bajo'].map(n =>
          `<div style="display:flex;align-items:center;gap:7px;margin-bottom:5px">
            <span style="width:12px;height:12px;border-radius:3px;background:${RC[n]};flex-shrink:0"></span>
            <span>${n}</span></div>`).join('');

  } else if (isDelta) {
    const steps = [[-1e9,-30,'#1d4ed8'],[-30,-10,'#3b82f6'],[-10,0,'#93c5fd'],[0,10,'#fca5a5'],[10,30,'#f87171'],[30,1e9,'#dc2626']];
    colorFn = code => {
      const d = lookup[code]?.delta_pct;
      if (d == null) return '#111827';
      return (steps.find(([lo,hi]) => d >= lo && d < hi) || [0,0,'#111827'])[2];
    };
    legendHtml = `<b style="color:#e2e8f8">Cambio 2023 → 2024</b>
      <div style="height:8px;border-radius:4px;background:linear-gradient(90deg,#1d4ed8,#93c5fd,#e2e8f8,#fca5a5,#dc2626);margin:8px 0 6px"></div>
      <div style="display:flex;justify-content:space-between;font-size:10px"><span>Baja</span><span>±0</span><span>Sube</span></div>`;

  } else {
    const vals = Object.values(lookup).map(r => r[CHORO_VAR]).filter(v => v != null).sort((a,b) => a-b);
    const q = f => vals[Math.max(0, Math.floor((vals.length - 1) * f))];
    const bins = [q(0.2), q(0.4), q(0.6), q(0.8)];
    const PAL = CHORO_VAR === 'incidencia_dengue'
      ? ['#0f2040','#1d4ed8','#22d3ee','#fbbf24','#f87171']
      : ['#0f2040','#1e3a5f','#2d6aab','#22d3ee','#f87171'];
    const binLabels = [
      `< ${Math.round(bins[0])}`,
      `${Math.round(bins[0])}–${Math.round(bins[1])}`,
      `${Math.round(bins[1])}–${Math.round(bins[2])}`,
      `${Math.round(bins[2])}–${Math.round(bins[3])}`,
      `> ${Math.round(bins[3])}`
    ];
    colorFn = code => {
      const v = lookup[code]?.[CHORO_VAR];
      if (v == null) return '#111827';
      if (v > bins[3]) return PAL[4];
      if (v > bins[2]) return PAL[3];
      if (v > bins[1]) return PAL[2];
      if (v > bins[0]) return PAL[1];
      return PAL[0];
    };
    const vLabel = CHORO_VAR === 'incidencia_dengue' ? 'Incidencia ×100k' : 'Casos absolutos';
    legendHtml = `<b style="color:#e2e8f8">${vLabel} — ${CHORO_YEAR}</b><div style="margin:8px 0">`
      + PAL.map((c,i) => `<div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
          <span style="width:12px;height:12px;border-radius:3px;background:${c};flex-shrink:0"></span>
          <span>${binLabels[i]}</span></div>`).join('') + '</div>';
  }

  const layer = L.geoJSON(GEO_MUNI, {
    style: feat => ({
      fillColor: colorFn(feat.properties?.MPIO_CCDGO),
      color: '#060a12', weight: 0.8, fillOpacity: 0.82
    }),
    onEachFeature: (feat, lyr) => {
      const code = feat.properties?.MPIO_CCDGO;
      const name = feat.properties?.MPIO_CNMBR;
      const rec  = lookup[code];
      let tip;
      if (isRiesgo && rec) {
        const c = colorFn(code);
        tip = `<div style="font-family:Space Grotesk,sans-serif;min-width:170px">
          <div style="font-weight:700;color:#e2e8f8;margin-bottom:6px">${name}</div>
          <div style="color:#94a3b8;font-size:12px">Nivel: <b style="color:${c}">${rec.nivel}</b></div>
          <div style="color:#94a3b8;font-size:12px">Inc. prom: <b style="color:#e2e8f8">${rec.inc_prom?.toFixed(1)}</b> ×100k</div>
        </div>`;
      } else if (isDelta && rec) {
        const sign = (rec.delta_pct ?? 0) >= 0 ? '+' : '';
        const c = colorFn(code);
        tip = `<div style="font-family:Space Grotesk,sans-serif;min-width:170px">
          <div style="font-weight:700;color:#e2e8f8;margin-bottom:6px">${name}</div>
          <div style="color:#94a3b8;font-size:12px">Δ 2023→2024: <b style="color:${c}">${sign}${rec.delta_pct?.toFixed(1) ?? '—'}%</b></div>
          <div style="color:#94a3b8;font-size:12px">Inc. 2023: <b>${rec.inc_2023?.toFixed(1)}</b></div>
          <div style="color:#94a3b8;font-size:12px">Inc. 2024: <b>${rec.inc_2024?.toFixed(1)}</b></div>
        </div>`;
      } else if (rec) {
        tip = munTooltip(rec, colorFn(code));
      } else {
        tip = `<b>${name}</b><br><span style="color:#64748b">Sin datos</span>`;
      }
      lyr.bindTooltip(tip, { className: 'geo-tooltip', sticky: true });
      lyr.on({
        mouseover: e => e.target.setStyle({ weight: 2, fillOpacity: 0.96, color: '#ffffff44' }),
        mouseout:  e => layer.resetStyle(e.target)
      });
    }
  }).addTo(choroMap);
  choroMapLayers.push(layer);
  try { choroMap.fitBounds(layer.getBounds(), { padding: [12, 12] }); } catch(e) {}

  chorLegend = L.control({ position: 'bottomright' });
  chorLegend.onAdd = () => {
    const div = L.DomUtil.create('div');
    div.style.cssText = 'background:#0c1221ee;border:1px solid #1c2d4a;border-radius:8px;padding:10px 12px;font-family:Space Grotesk,sans-serif;font-size:11px;color:#94a3b8;min-width:155px';
    div.innerHTML = legendHtml;
    return div;
  };
  chorLegend.addTo(choroMap);

  renderChoroStats(lookup, isRiesgo, isDelta);
}

function renderChoroStats(lookup, isRiesgo, isDelta) {
  const el = document.getElementById('choro-stats');
  if (!el) return;
  if (isRiesgo) {
    const cnt = { 'Crítico':0, 'Alto':0, 'Medio':0, 'Bajo':0 };
    Object.values(lookup).forEach(r => { if (r.nivel in cnt) cnt[r.nivel]++; });
    const RC = { 'Crítico':'#f87171', 'Alto':'#fbbf24', 'Medio':'#34d399', 'Bajo':'#3b82f6' };
    el.innerHTML = Object.entries(cnt).map(([n,c]) =>
      `<div class="map-stat"><span class="map-stat-val" style="font-size:18px;color:${RC[n]}">${c}</span><span class="map-stat-lbl">${n}</span></div>`
    ).join('');
  } else if (isDelta) {
    const vals = Object.values(lookup).map(r => r.delta_pct).filter(v => v != null);
    const mejoran  = vals.filter(v => v < 0).length;
    const empeoran = vals.filter(v => v > 0).length;
    const med = [...vals].sort((a,b)=>a-b)[Math.floor(vals.length/2)];
    el.innerHTML = `
      <div class="map-stat"><span class="map-stat-val" style="color:#34d399">${mejoran}</span><span class="map-stat-lbl">Mejoran</span></div>
      <div class="map-stat"><span class="map-stat-val" style="color:#f87171">${empeoran}</span><span class="map-stat-lbl">Empeoran</span></div>
      <div class="map-stat"><span class="map-stat-val">${med != null ? (med>=0?'+':'')+med.toFixed(1)+'%' : '—'}</span><span class="map-stat-lbl">Mediana Δ</span></div>`;
  } else {
    const data = getByYear(CHORO_YEAR).filter(r => CHORO_CALI || r.MPIO_CCDGO !== '76001');
    const total  = data.reduce((s, r) => s + r.conteo_dengue, 0);
    const avgInc = (data.reduce((s, r) => s + r.incidencia_dengue, 0) / (data.length || 1)).toFixed(1);
    const nCrit  = data.filter(r => r.incidencia_dengue > 400).length;
    el.innerHTML = `
      <div class="map-stat"><span class="map-stat-val">${fmt(total)}</span><span class="map-stat-lbl">casos ${CHORO_YEAR}</span></div>
      <div class="map-stat"><span class="map-stat-val">${avgInc}</span><span class="map-stat-lbl">inc. prom ×100k</span></div>
      <div class="map-stat"><span class="map-stat-val">${nCrit}</span><span class="map-stat-lbl">mun. &gt;400 inc.</span></div>`;
  }
}

function wireChoroControls() {
  document.querySelectorAll('[data-cv]').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('[data-cv]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      CHORO_VAR = btn.dataset.cv;
      if (choroMap) renderChoroLayer();
    });
  });
  document.getElementById('choro-cali')?.addEventListener('change', e => {
    CHORO_CALI = e.target.checked;
    if (choroMap) renderChoroLayer();
  });
}

// ─── Demografía ───────────────────────────────────────────────────────────────
// Redefinición de helpers para escalado demográfico según año seleccionado
// Redefinición de helpers para escalado demográfico según año seleccionado y ciclo de vida
getDemoTotal = function(code) {
  const base = DEMO_MUN_TOTAL[code] || DEMO_MUN_TOTAL['VALLE'];
  let realPop = 0;
  if (code === 'VALLE') {
    realPop = GEODATA.filter(d => d.año === SELECTED_YEAR).reduce((acc, curr) => acc + (curr.población || 0), 0);
  } else {
    const match = GEODATA.find(d => d.MPIO_CCDGO === code && d.año === SELECTED_YEAR);
    realPop = (match && match.población) ? match.población : base.poblacion_total;
  }
  const basePop = base.poblacion_total || 1;
  const factor = realPop / basePop;

  let baseMasc = 0;
  let baseFeme = 0;

  if (DEMO_SELECTED_CYCLE === 'ALL') {
    baseMasc = base.poblacion_masculina;
    baseFeme = base.poblacion_femenina;
  } else {
    const cyclesList = DEMO_CICLOS[code] || DEMO_CICLOS['VALLE'] || [];
    cyclesList.forEach(item => {
      if (item.ciclo_nombre === DEMO_SELECTED_CYCLE) {
        if (item.sexo === 'M') baseMasc += item.cantidad;
        if (item.sexo === 'F') baseFeme += item.cantidad;
      }
    });
  }

  const baseTotal = baseMasc + baseFeme;
  const scaledTotal = Math.round(baseTotal * factor);
  const scaledMasc = Math.round(baseMasc * factor);
  const scaledFeme = Math.round(baseFeme * factor);

  const pctMasc = scaledTotal > 0 ? parseFloat(((scaledMasc / scaledTotal) * 100).toFixed(1)) : 0.0;
  const pctFeme = scaledTotal > 0 ? parseFloat(((scaledFeme / scaledTotal) * 100).toFixed(1)) : 0.0;

  return {
    codigo_dane: base.codigo_dane,
    nombre: base.nombre,
    poblacion_total: scaledTotal,
    poblacion_masculina: scaledMasc,
    poblacion_femenina: scaledFeme,
    pct_masculino: pctMasc,
    pct_femenino: pctFeme
  };
};

getDemoPiramide = function(code) {
  const baseTotal = DEMO_MUN_TOTAL[code] || DEMO_MUN_TOTAL['VALLE'];
  let realPop = 0;
  if (code === 'VALLE') {
    realPop = GEODATA.filter(d => d.año === SELECTED_YEAR).reduce((acc, curr) => acc + (curr.población || 0), 0);
  } else {
    const match = GEODATA.find(d => d.MPIO_CCDGO === code && d.año === SELECTED_YEAR);
    realPop = (match && match.población) ? match.población : baseTotal.poblacion_total;
  }
  const basePop = baseTotal.poblacion_total || 1;
  const factor = realPop / basePop;

  const baseList = DEMO_PIRAMIDE[code] || DEMO_PIRAMIDE['VALLE'] || [];
  return baseList.map(item => {
    const newQty = Math.round(item.cantidad * factor);
    return {
      ...item,
      cantidad: newQty,
      cantidad_piramide: item.sexo === 'M' ? -newQty : newQty
    };
  });
};

getDemoCiclos = function(code) {
  const baseTotal = DEMO_MUN_TOTAL[code] || DEMO_MUN_TOTAL['VALLE'];
  let realPop = 0;
  if (code === 'VALLE') {
    realPop = GEODATA.filter(d => d.año === SELECTED_YEAR).reduce((acc, curr) => acc + (curr.población || 0), 0);
  } else {
    const match = GEODATA.find(d => d.MPIO_CCDGO === code && d.año === SELECTED_YEAR);
    realPop = (match && match.población) ? match.población : baseTotal.poblacion_total;
  }
  const basePop = baseTotal.poblacion_total || 1;
  const factor = realPop / basePop;

  const baseList = DEMO_CICLOS[code] || DEMO_CICLOS['VALLE'] || [];
  
  // Consolidar M y F por ciclo_nombre / id_ciclo
  const grouped = {};
  baseList.forEach(item => {
    const key = item.id_ciclo;
    if (!grouped[key]) {
      grouped[key] = {
        ciclo_nombre: item.ciclo_nombre,
        id_ciclo: item.id_ciclo,
        cantidad: 0
      };
    }
    grouped[key].cantidad += item.cantidad;
  });

  return Object.values(grouped).map(item => ({
    ...item,
    cantidad: Math.round(item.cantidad * factor)
  })).sort((a, b) => a.id_ciclo - b.id_ciclo);
};

function initDemoMap() {
  if (demoMapInstance) return;
  demoMapInstance = L.map('demo-map', { zoomControl: false, preferCanvas: true })
    .setView([3.8, -76.5], 8);

  L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png', {
    attribution: '©OpenStreetMap ©CARTO', subdomains: 'abcd', maxZoom: 19
  }).addTo(demoMapInstance);

  L.control.zoom({ position: 'bottomright' }).addTo(demoMapInstance);
  
  // Wire up dropdown population
  const sel = document.getElementById('demo-mun-select');
  if (sel) {
    sel.innerHTML = '';
    // Add "Valle del Cauca (Total)" as first option
    const optValle = document.createElement('option');
    optValle.value = 'VALLE';
    optValle.textContent = 'Valle del Cauca (Total)';
    sel.appendChild(optValle);
    
    // Sort and add other municipalities
    const munList = Object.values(DEMO_MUN_TOTAL)
      .filter(m => m.codigo_dane !== 'VALLE')
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
      
    munList.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.codigo_dane;
      opt.textContent = m.nombre;
      sel.appendChild(opt);
    });
    
    sel.addEventListener('change', e => {
      DEMO_SELECTED_MUN = e.target.value;
      updateDemoDashboard();
      highlightDemoMunicipality(DEMO_SELECTED_MUN);
    });
  }

  const cycleSel = document.getElementById('demo-cycle-select');
  if (cycleSel) {
    cycleSel.value = DEMO_SELECTED_CYCLE;
    cycleSel.addEventListener('change', e => {
      DEMO_SELECTED_CYCLE = e.target.value;
      updateDemoDashboard();
      renderDemoMapLayer();
    });
  }
  
  renderDemoMapLayer();
}

let demoChoroplethLegend = null;
function renderDemoMapLayer() {
  demoMapLayers.forEach(l => demoMapInstance.removeLayer(l));
  demoMapLayers = [];
  if (demoChoroplethLegend) { demoMapInstance.removeControl(demoChoroplethLegend); demoChoroplethLegend = null; }

  const geomSrc = (typeof window !== 'undefined' && window.GEO_MUNI)
    ? window.GEO_MUNI
    : buildMockGeoJSON();

  const vals = Object.keys(DEMO_MUN_TOTAL)
    .filter(code => code !== 'VALLE')
    .map(code => getDemoTotal(code).poblacion_total)
    .sort((a, b) => a - b);
  const q = f => vals[Math.max(0, Math.floor((vals.length - 1) * f))];
  const bins = [q(0.2), q(0.4), q(0.6), q(0.8)];

  const getDemoColor = val => {
    if (val == null) return '#111827';
    if (val > bins[3]) return '#06b6d4'; // neon cyan
    if (val > bins[2]) return '#3b82f6'; // bright blue
    if (val > bins[1]) return '#1d4ed8'; // blue
    if (val > bins[0]) return '#1e3a8a'; // dark blue
    return '#0f172a'; // very dark blue
  };

  const layer = L.geoJSON(geomSrc, {
    style: feat => {
      const code = feat.properties?.MPIO_CCDGO;
      const rec = getDemoTotal(code);
      const col = getDemoColor(rec?.poblacion_total);
      return {
        fillColor: col, color: '#060a12',
        weight: 1,
        fillOpacity: 0.80
      };
    },
    onEachFeature: (feat, lyr) => {
      const code = feat.properties?.MPIO_CCDGO;
      const name = feat.properties?.MPIO_CNMBR;
      const rec = getDemoTotal(code);
      if (rec) {
        const col = getDemoColor(rec.poblacion_total);
        const popLabel = DEMO_SELECTED_CYCLE === 'ALL' ? 'Población total' : `Pob. (${DEMO_SELECTED_CYCLE})`;
        const tip = `<div style="font-family:Space Grotesk,sans-serif;min-width:180px">
          <div style="font-weight:700;color:#e2e8f8;margin-bottom:6px;font-size:14px">${rec.nombre}</div>
          <div style="color:#94a3b8;font-size:12px;margin-bottom:2px">${popLabel}: <b style="color:#e2e8f8">${fmt(rec.poblacion_total)}</b></div>
          <div style="color:#94a3b8;font-size:12px;margin-bottom:2px">Hombres: <b style="color:#e2e8f8">${fmt(rec.poblacion_masculina)}</b> (${rec.pct_masculino}%)</div>
          <div style="color:#94a3b8;font-size:12px;margin-bottom:2px">Mujeres: <b style="color:#e2e8f8">${fmt(rec.poblacion_femenina)}</b> (${rec.pct_femenino}%)</div>
        </div>`;
        lyr.bindTooltip(tip, { className: 'geo-tooltip', sticky: true });
        
        lyr.on({
          mouseover: e => e.target.setStyle({ weight: 2.5, fillOpacity: 0.96, color: '#ffffff44' }),
          mouseout:  e => {
            if (code !== DEMO_SELECTED_MUN) {
              layer.resetStyle(e.target);
            } else {
              e.target.setStyle({ weight: 3, color: '#22d3ee', fillOpacity: 0.9 });
            }
          },
          click: () => {
            DEMO_SELECTED_MUN = code;
            const sel = document.getElementById('demo-mun-select');
            if (sel) sel.value = code;
            updateDemoDashboard();
            highlightDemoMunicipality(code);
          }
        });
      } else {
        lyr.bindTooltip(name + ' — sin datos demográficos', { className: 'geo-tooltip' });
      }
    }
  }).addTo(demoMapInstance);
  
  demoMapLayers.push(layer);
  try { demoMapInstance.fitBounds(layer.getBounds(), { padding: [16, 16] }); } catch(e) {}

  // Add map legend
  demoChoroplethLegend = L.control({ position: 'bottomright' });
  demoChoroplethLegend.onAdd = () => {
    const div = L.DomUtil.create('div');
    div.style.cssText = 'background:#0c1221ee;border:1px solid #1c2d4a;border-radius:8px;padding:10px 12px;font-family:Space Grotesk,sans-serif;font-size:11px;color:#94a3b8;min-width:140px';
    const labels = [
      `< ${fmt(Math.round(bins[0]))}`,
      `${fmt(Math.round(bins[0]))}–${fmt(Math.round(bins[1]))}`,
      `${fmt(Math.round(bins[1]))}–${fmt(Math.round(bins[2]))}`,
      `${fmt(Math.round(bins[2]))}–${fmt(Math.round(bins[3]))}`,
      `> ${fmt(Math.round(bins[3]))}`
    ];
    const colors = ['#0f172a', '#1e3a8a', '#1d4ed8', '#3b82f6', '#06b6d4'];
    const legendTitle = DEMO_SELECTED_CYCLE === 'ALL' ? 'Población por Municipio' : `Pob. (${DEMO_SELECTED_CYCLE})`;
    div.innerHTML = `<div style="font-weight:600;color:#e2e8f8;margin-bottom:7px">${legendTitle}</div>`
      + colors.map((c, i) => `<div style="display:flex;align-items:center;gap:7px;margin-bottom:4px">
          <span style="width:12px;height:12px;border-radius:3px;background:${c};display:inline-block;flex-shrink:0"></span>
          <span>${labels[i]}</span></div>`).join('');
    return div;
  };
  demoChoroplethLegend.addTo(demoMapInstance);
}

function highlightDemoMunicipality(code) {
  if (!demoMapInstance || !demoMapLayers.length) return;
  const layerGroup = demoMapLayers[0];
  if (code === 'VALLE') {
    layerGroup.eachLayer(lyr => layerGroup.resetStyle(lyr));
    try {
      demoMapInstance.fitBounds(layerGroup.getBounds(), { padding: [16, 16] });
    } catch(e) {}
    return;
  }
  layerGroup.eachLayer(lyr => {
    const lyrCode = lyr.feature.properties?.MPIO_CCDGO;
    if (lyrCode === code) {
      lyr.setStyle({ weight: 3, color: '#22d3ee', fillOpacity: 0.9 });
      try {
        demoMapInstance.setView(lyr.getBounds().getCenter(), 10);
      } catch(e) {}
    } else {
      layerGroup.resetStyle(lyr);
    }
  });
}

function updateDemoDashboard() {
  const munCode = DEMO_SELECTED_MUN;
  const totalData = getDemoTotal(munCode);
  
  // Update KPIs with count animation
  const elTotal = document.getElementById('demo-kpi-total');
  const elPctMasc = document.getElementById('demo-kpi-pct-masc');
  const elPctFem = document.getElementById('demo-kpi-pct-fem');
  const elMasc = document.getElementById('demo-kpi-masc');
  const elFem = document.getElementById('demo-kpi-fem');
  
  if (elTotal) animateCount(elTotal, totalData.poblacion_total, 800);
  if (elPctMasc) animateCount(elPctMasc, totalData.pct_masculino, 800, 1);
  if (elPctFem) animateCount(elPctFem, totalData.pct_femenino, 800, 1);
  if (elMasc) animateCount(elMasc, totalData.poblacion_masculina, 800);
  if (elFem) animateCount(elFem, totalData.poblacion_femenina, 800);

  // Redraw Charts
  renderDemoPyramidChart(munCode);
  renderDemoCyclesChart(munCode);
}

function renderDemoPyramidChart(code) {
  const ctx = document.getElementById('demo-chart-pyramid');
  if (!ctx) return;
  
  if (charts['demoPyramid']) charts['demoPyramid'].destroy();
  
  const CYCLE_PYRAMID_GROUPS = {
    'Primera infancia': ['DE 00 A 04', 'DE 05 A 09'],
    'Infancia': ['DE 05 A 09', 'DE 10 A 14'],
    'Adolescencia': ['DE 10 A 14', 'DE 15 A 19'],
    'Juventud': ['DE 15 A 19', 'DE 20 A 24', 'DE 25 A 29'],
    'Adultez': ['DE 30 A 34', 'DE 35 A 39', 'DE 40 A 44', 'DE 45 A 49', 'DE 50 A 54', 'DE 55 A 59'],
    'Vejez': ['DE 60 A 64', 'DE 65 A 69', 'DE 70 A 74', 'DE 75 A 79', 'DE 80 A 84', 'DE 85 y Más']
  };

  let rawData = getDemoPiramide(code);
  if (DEMO_SELECTED_CYCLE !== 'ALL') {
    const allowed = CYCLE_PYRAMID_GROUPS[DEMO_SELECTED_CYCLE] || [];
    rawData = rawData.filter(item => allowed.includes(item.grupo_quinquenal));
  }
  const sortedData = [...rawData].sort((a, b) => a.orden - b.orden);
  
  const labels = [];
  const maleData = [];
  const femaleData = [];
  
  const groups = {};
  sortedData.forEach(item => {
    if (!groups[item.grupo_quinquenal]) {
      groups[item.grupo_quinquenal] = { M: 0, F: 0 };
      labels.push(item.grupo_quinquenal.replace('DE ', ''));
    }
    groups[item.grupo_quinquenal][item.sexo] = item.cantidad_piramide;
  });
  
  const uniqueLabels = [...new Set(labels)];
  
  uniqueLabels.forEach(lbl => {
    const key = 'DE ' + lbl;
    const grp = groups[key] || groups[lbl] || { M: 0, F: 0 };
    maleData.push(grp.M);
    femaleData.push(grp.F);
  });
  
  charts['demoPyramid'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: uniqueLabels,
      datasets: [
        {
          label: 'Hombres',
          data: maleData,
          backgroundColor: '#3b82f688',
          borderColor: '#3b82f6',
          borderWidth: 1,
          borderRadius: { topLeft: 4, bottomLeft: 4 },
          borderSkipped: 'right'
        },
        {
          label: 'Mujeres',
          data: femaleData,
          backgroundColor: '#ec489988',
          borderColor: '#ec4899',
          borderWidth: 1,
          borderRadius: { topRight: 4, bottomRight: 4 },
          borderSkipped: 'left'
        }
      ]
    },
    options: {
      indexAxis: 'y',
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { labels: { color: '#94a3b8', font: { family: 'Space Grotesk', size: 10 } } },
        tooltip: {
          backgroundColor: '#0c1221',
          borderColor: '#1e2d45',
          borderWidth: 1,
          titleColor: '#e2e8f8',
          bodyColor: '#94a3b8',
          callbacks: {
            label: context => {
              const label = context.dataset.label;
              const val = Math.abs(context.parsed.x);
              return ` ${label}: ${fmt(val)}`;
            }
          }
        }
      },
      scales: {
        x: {
          grid: { color: '#162038' },
          ticks: {
            color: '#64748b',
            font: { family: 'JetBrains Mono', size: 9 },
            callback: value => fmt(Math.abs(value))
          }
        },
        y: {
          grid: { display: false },
          ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 9 } }
        }
      }
    }
  });
}

function renderDemoCyclesChart(code) {
  const ctx = document.getElementById('demo-chart-cycles');
  if (!ctx) return;
  
  if (charts['demoCycles']) charts['demoCycles'].destroy();
  
  const rawData = getDemoCiclos(code);
  const sortedData = [...rawData].sort((a, b) => a.id_ciclo - b.id_ciclo);
  
  const labels = sortedData.map(d => d.ciclo_nombre);
  const values = sortedData.map(d => d.cantidad);
  
  const colors = ['#22d3ee', '#34d399', '#fbbf24', '#fb923c', '#3b82f6', '#a78bfa'];
  
  charts['demoCycles'] = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: labels,
      datasets: [{
        data: values,
        backgroundColor: sortedData.map((d, index) => {
          const color = colors[index % colors.length];
          if (DEMO_SELECTED_CYCLE === 'ALL' || d.ciclo_nombre === DEMO_SELECTED_CYCLE) {
            return color + '88';
          } else {
            return color + '18'; // attenuated background
          }
        }),
        borderColor: sortedData.map((d, index) => {
          const color = colors[index % colors.length];
          if (DEMO_SELECTED_CYCLE === 'ALL' || d.ciclo_nombre === DEMO_SELECTED_CYCLE) {
            return color;
          } else {
            return color + '33'; // attenuated border
          }
        }),
        borderWidth: 1,
        borderRadius: 4
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: '#0c1221',
          borderColor: '#1e2d45',
          borderWidth: 1,
          titleColor: '#e2e8f8',
          bodyColor: '#94a3b8',
          callbacks: {
            label: context => ` Población: ${fmt(context.parsed.y)}`
          }
        }
      },
      scales: {
        x: {
          grid: { display: false },
          ticks: { color: '#64748b', font: { family: 'Space Grotesk', size: 9 } }
        },
        y: {
          grid: { color: '#162038' },
          ticks: { color: '#64748b', font: { family: 'JetBrains Mono', size: 9 }, callback: v => fmt(v) }
        }
      }
    }
  });
}


function renderDemografia() {
  const isFirstLoad = !demoMapInstance;
  initDemoMap();
  if (!isFirstLoad) {
    renderDemoMapLayer();
  }
  updateDemoDashboard();
  if (demoMapInstance) {
    setTimeout(() => demoMapInstance.invalidateSize(), 50);
  }
}

function getReportRisk(inc) {
  if (inc > 600) return { label: 'critica', color: '#f87171', action: 'respuesta intensiva inmediata' };
  if (inc > 350) return { label: 'alta', color: '#fbbf24', action: 'refuerzo de vigilancia y control vectorial' };
  if (inc > 150) return { label: 'moderada', color: '#34d399', action: 'seguimiento activo y prevencion comunitaria' };
  return { label: 'baja', color: '#3b82f6', action: 'mantenimiento de vigilancia rutinaria' };
}

function getReportStats(munData, year) {
  const current = munData.find(r => r.año === year) || { conteo_dengue: 0, incidencia_dengue: 0, población: 0 };
  const previous = munData.find(r => r.año === year - 1) || null;
  const historical = munData.filter(r => r.año < year);
  const avgCases = historical.reduce((s, r) => s + r.conteo_dengue, 0) / (historical.length || 1);
  const maxCases = Math.max(...munData.map(r => r.conteo_dengue), 0);
  const deltaCases = previous ? current.conteo_dengue - previous.conteo_dengue : 0;
  const deltaPct = previous && previous.conteo_dengue > 0 ? (deltaCases / previous.conteo_dengue) * 100 : null;
  return { current, previous, historical, avgCases, maxCases, deltaCases, deltaPct };
}

function estimateChildBurden(ciclos, totalPop, totalCases) {
  const childPop = (ciclos.find(c => c.ciclo_nombre === 'Primera infancia')?.cantidad || 0) +
                   (ciclos.find(c => c.ciclo_nombre === 'Infancia')?.cantidad || 0) +
                   0.5 * (ciclos.find(c => c.ciclo_nombre === 'Adolescencia')?.cantidad || 0);
  const childShare = totalPop > 0 ? childPop / totalPop : 0;
  const childCases = totalCases > 0 ? Math.max(1, Math.round(totalCases * Math.min(0.45, childShare * 1.15))) : 0;
  const childPct = totalCases > 0 ? ((childCases / totalCases) * 100).toFixed(1) : '0.0';
  return { childPop, childShare, childCases, childPct };
}

function generateNarrative(munName, year, cases, inc, pop, childCases, childPct, stats = null) {
  const risk = getReportRisk(inc);
  const trendText = stats?.deltaPct == null
    ? 'sin una linea de comparacion anual inmediata disponible'
    : `${stats.deltaPct >= 0 ? 'un aumento' : 'una reduccion'} de <strong>${fmtDec(Math.abs(stats.deltaPct))}%</strong> frente al anio anterior`;
  const avgText = stats ? ` El promedio historico previo del municipio fue de <strong>${fmt(Math.round(stats.avgCases))} casos</strong>, por lo que el valor actual se ubica ${cases >= stats.avgCases ? 'por encima' : 'por debajo'} de su referencia reciente.` : '';
  let text = `Durante ${year}, <strong>${munName}</strong> notifico <strong>${fmt(cases)} casos</strong> de dengue, con una incidencia acumulada de <strong>${fmtDec(inc)} por 100,000 habitantes</strong> sobre una poblacion base de <strong>${fmt(pop)}</strong> personas. Esta magnitud configura una carga epidemiologica <strong>${risk.label}</strong> y exige ${risk.action}.`;
  text += ` En la comparacion temporal se observa ${trendText}.${avgText}`;
  if (cases > 0) {
    text += ` La carga estimada en menores de 15 anios fue de <strong>${fmt(childCases)} casos</strong>, equivalente al <strong>${childPct}%</strong> del total, un indicador util para priorizar entornos escolares, hogares con almacenamiento de agua y busqueda activa comunitaria.`;
  } else {
    text += ' No se registran casos notificados en el periodo analizado; aun asi, el silencio epidemiologico debe interpretarse junto con oportunidad de notificacion, capacidad diagnostica y condiciones ambientales.';
  }
  text += inc > 350
    ? ' Se recomienda activar seguimiento semanal de conglomerados, eliminar criaderos, verificar abastecimiento y almacenamiento de agua, y fortalecer triage clinico para signos de alarma.'
    : ' Se recomienda sostener vigilancia, educacion comunitaria, control focal y revision de condiciones climaticas que puedan anticipar aumentos estacionales.';
  return text;
}

function generateEndemicNarrative(munName, year, munData) {
  const rows = [...munData].sort((a, b) => a.año - b.año);
  const current = rows.find(r => r.año === year) || rows[rows.length - 1] || { conteo_dengue: 0, incidencia_dengue: 0 };
  const baseline = rows.filter(r => r.año < year).map(r => r.conteo_dengue).sort((a, b) => a - b);
  const q = p => baseline.length ? baseline[Math.min(baseline.length - 1, Math.floor((baseline.length - 1) * p))] : 0;
  const q25 = q(0.25), q50 = q(0.5), q75 = q(0.75);
  let zone = 'exito';
  if (current.conteo_dengue > q75) zone = 'epidemica';
  else if (current.conteo_dengue > q50) zone = 'alarma';
  else if (current.conteo_dengue > q25) zone = 'seguridad';
  const zoneText = { exito: 'zona de exito o baja transmision', seguridad: 'zona de seguridad', alarma: 'zona de alarma', epidemica: 'zona epidemica' }[zone];
  return `El canal endemico anual estimado para <strong>${munName}</strong> ubica el anio <strong>${year}</strong> en <strong>${zoneText}</strong>. El valor observado fue de <strong>${fmt(current.conteo_dengue)} casos</strong>, frente a una mediana historica previa de <strong>${fmt(Math.round(q50))}</strong> y un umbral alto de <strong>${fmt(Math.round(q75))}</strong>. Esta lectura usa los anios disponibles como referencia agregada anual; para vigilancia operativa debe complementarse con canal semanal, oportunidad de notificacion y validacion de brotes activos.`;
}

function getWeeklyZone(value, channel, index) {
  if (value > (channel.alert[index] || 0)) return 'epidemica';
  if (value > (channel.safety[index] || 0)) return 'alarma';
  if (value > (channel.success[index] || 0)) return 'seguridad';
  return 'exito';
}

function generateWeeklyEndemicNarrative(munName, year, weekly, channel) {
  const current = weekly.cases || [];
  const total = current.reduce((s, v) => s + v, 0);
  const peakValue = Math.max(...current, 0);
  const peakIndex = Math.max(0, current.indexOf(peakValue));
  const epiWeeks = current.filter((v, i) => getWeeklyZone(v, channel, i) === 'epidemica').length;
  const alarmWeeks = current.filter((v, i) => getWeeklyZone(v, channel, i) === 'alarma').length;
  const recent = current.slice(-4);
  const recentTotal = recent.reduce((s, v) => s + v, 0);
  const recentAvg = recent.length ? recentTotal / recent.length : 0;
  const previousAvg = current.slice(-8, -4).reduce((s, v) => s + v, 0) / 4 || 0;
  const recentTrend = recentAvg >= previousAvg * 1.1 ? 'ascendente' : recentAvg <= previousAvg * 0.9 ? 'descendente' : 'estable';
  return `El canal endemico semanal estimado para <strong>${munName}</strong> en <strong>${year}</strong> distribuye <strong>${fmt(total)}</strong> casos estimados en 52 semanas. La mayor intensidad ocurre en la <strong>semana ${peakIndex + 1}</strong>, con <strong>${fmt(peakValue)}</strong> casos; se identifican <strong>${epiWeeks}</strong> semanas en zona epidemica y <strong>${alarmWeeks}</strong> semanas en zona de alarma. En las ultimas cuatro semanas estimadas el promedio es <strong>${fmtDec(recentAvg)}</strong> casos por semana, con tendencia <strong>${recentTrend}</strong> frente al bloque semanal previo.`;
}

function reportSetText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value;
}

function renderReportMap(code, munName, record) {
  const target = document.getElementById('rep-map-svg');
  if (!target) return;
  const geo = (typeof window !== 'undefined' && window.GEO_MUNI) ? window.GEO_MUNI : buildMockGeoJSON();
  const feature = geo.features?.find(f => String(f.properties?.MPIO_CCDGO) === String(code));
  const color = getReportRisk(record.incidencia_dengue || 0).color;
  const rings = [];
  if (feature?.geometry?.type === 'Polygon') rings.push(...feature.geometry.coordinates);
  if (feature?.geometry?.type === 'MultiPolygon') feature.geometry.coordinates.forEach(poly => rings.push(...poly));
  const fallbackRing = [[-1, 0], [0.2, -0.55], [1.2, -0.35], [1.05, 0.45], [0.1, 0.75], [-0.95, 0.45], [-1, 0]];
  const drawRings = rings.length ? rings : [fallbackRing];
  const pts = drawRings.flat();
  const xs = pts.map(p => p[0]);
  const ys = pts.map(p => p[1]);
  const minX = Math.min(...xs), maxX = Math.max(...xs), minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = maxX - minX || 1, h = maxY - minY || 1;
  const vbW = 420, vbH = 300, pad = 22;
  const scale = Math.min((vbW - pad * 2) / w, (vbH - pad * 2) / h);
  const dx = (vbW - w * scale) / 2;
  const dy = (vbH - h * scale) / 2;
  const project = p => [dx + (p[0] - minX) * scale, dy + (maxY - p[1]) * scale];
  const paths = drawRings.map(ring => {
    const d = ring.map((p, i) => {
      const [x, y] = project(p);
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`;
    }).join(' ') + ' Z';
    return `<path d="${d}" fill="#dbeafe" fill-opacity="0.45" stroke="${color}" stroke-width="2.2"/>`;
  }).join('');
  const cx = (dx + (vbW - dx)) / 2;
  const cy = vbH / 2;
  const hexR = 15;
  const maxCases = Math.max(record.conteo_dengue || 0, 1);
  const palette = ['#bfdbfe', '#93c5fd', '#60a5fa', '#fbbf24', '#f87171'];
  const hexPath = (x, y, r) => {
    const pts = Array.from({ length: 6 }, (_, i) => {
      const a = Math.PI / 6 + i * Math.PI / 3;
      return `${(x + Math.cos(a) * r).toFixed(1)},${(y + Math.sin(a) * r).toFixed(1)}`;
    }).join(' ');
    return `<polygon points="${pts}"`;
  };
  const hexes = [];
  for (let row = -4; row <= 4; row++) {
    for (let col = -6; col <= 6; col++) {
      const x = cx + col * hexR * 1.55 + (Math.abs(row) % 2) * hexR * 0.78;
      const y = cy + row * hexR * 1.34;
      const dist = Math.hypot((x - cx) / 150, (y - cy) / 105);
      if (dist > 1.05) continue;
      const wave = Math.sin((col + 9) * 1.7 + (row + 5) * 0.9 + (record.conteo_dengue || 0) * 0.01);
      const intensity = Math.max(0, Math.min(1, (1.05 - dist) * 0.75 + (wave + 1) * 0.16));
      const idx = Math.min(palette.length - 1, Math.floor(intensity * palette.length));
      const opacity = 0.35 + intensity * 0.55;
      hexes.push(`${hexPath(x, y, hexR)} fill="${palette[idx]}" fill-opacity="${opacity.toFixed(2)}" stroke="#ffffff" stroke-width="1"/>`);
    }
  }
  target.innerHTML = `<svg viewBox="0 0 ${vbW} ${vbH}" role="img" aria-label="Mapa hexagonal de ${munName}">
    <rect width="${vbW}" height="${vbH}" rx="8" fill="#f8fafc"/>
    <g opacity="0.95">${hexes.join('')}</g>
    ${paths}
    <circle cx="${vbW - 94}" cy="38" r="8" fill="${color}"/>
    <text x="${vbW - 80}" y="42" font-size="10" fill="#334155">${fmt(record.conteo_dengue || 0)} casos</text>
    <text x="18" y="${vbH - 18}" font-size="12" font-weight="700" fill="#1e3a8a">${munName}</text>
    <text x="18" y="24" font-size="10" fill="#64748b">Malla hexagonal de referencia territorial</text>
  </svg><div class="reporte-hex-legend"><span class="reporte-hex-dot" style="background:#bfdbfe"></span>Baja<span class="reporte-hex-dot" style="background:#60a5fa"></span>Media<span class="reporte-hex-dot" style="background:#f87171"></span>Alta</div>`;
}

function renderAnnualComparisonTable(munData, year) {
  const table = document.getElementById('rep-annual-table');
  if (!table) return;
  const rows = [...munData].sort((a, b) => a.año - b.año);
  table.innerHTML = `<thead><tr><th>Anio</th><th class="num">Casos</th><th class="num">Incidencia</th><th class="num">Poblacion</th><th class="num">Var. casos</th></tr></thead><tbody>${rows.map((r, i) => {
    const prev = rows[i - 1];
    const delta = prev ? r.conteo_dengue - prev.conteo_dengue : null;
    return `<tr${r.año === year ? ' style="background:#eff6ff"' : ''}><td>${r.año}</td><td class="num">${fmt(r.conteo_dengue)}</td><td class="num">${fmtDec(r.incidencia_dengue)}</td><td class="num">${fmt(r.población || 0)}</td><td class="num">${delta == null ? '-' : (delta >= 0 ? '+' : '') + fmt(delta)}</td></tr>`;
  }).join('')}</tbody>`;
}

function renderWeeklyComparisonTable(weekly, channel) {
  const table = document.getElementById('rep-annual-table');
  if (!table) return;
  const rows = (weekly.cases || []).map((cases, i) => ({
    week: i + 1,
    cases,
    incidence: weekly.incidence?.[i] || 0,
    zone: getWeeklyZone(cases, channel, i),
    alert: channel.alert?.[i] || 0
  })).sort((a, b) => b.cases - a.cases).slice(0, 12);
  const zoneLabel = { epidemica: 'Epidemica', alarma: 'Alarma', seguridad: 'Seguridad', exito: 'Exito' };
  table.innerHTML = `<thead><tr><th>Semana</th><th class="num">Casos est.</th><th class="num">Incidencia</th><th class="num">Umbral alto</th><th>Zona</th></tr></thead><tbody>${rows.map(r => {
    const bg = r.zone === 'epidemica' ? ' style="background:#fef2f2"' : r.zone === 'alarma' ? ' style="background:#fffbeb"' : '';
    return `<tr${bg}><td>Semana ${r.week}</td><td class="num">${fmt(r.cases)}</td><td class="num">${fmtDec(r.incidence)}</td><td class="num">${fmt(Math.round(r.alert))}</td><td>${zoneLabel[r.zone]}</td></tr>`;
  }).join('')}</tbody>`;
}

function renderTopMunicipiosTable(year) {
  const table = document.getElementById('rep-top-table');
  if (!table) return;
  const top = getTopMunByYear(year, 'conteo_dengue', 10, true);
  table.innerHTML = `<thead><tr><th>#</th><th>Municipio</th><th class="num">Casos</th><th class="num">Inc.</th></tr></thead><tbody>${top.map((r, i) => `<tr><td>${i + 1}</td><td>${r.MPIO_CNMBR}</td><td class="num">${fmt(r.conteo_dengue)}</td><td class="num">${fmtDec(r.incidencia_dengue)}</td></tr>`).join('')}</tbody>`;
}

function buildPyramidDataset(code, totalCases) {
  let raw = typeof getDemoPiramide === 'function' ? getDemoPiramide(code) : [];
  if (!raw.length && typeof DEMO_PIRAMIDE !== 'undefined') {
    raw = DEMO_PIRAMIDE[code] || DEMO_PIRAMIDE[String(code)] || DEMO_PIRAMIDE['VALLE'] || [];
  }
  if (!raw.length) {
    const total = getDemoTotal(code)?.poblacion_total || 100000;
    const groups = ['00-04', '05-09', '10-14', '15-19', '20-24', '25-29', '30-34', '35-39', '40-44', '45-49', '50-54', '55-59', '60+'];
    const weights = [7, 8, 8, 8, 8, 8, 7, 7, 7, 7, 6, 5, 14];
    const wTotal = weights.reduce((s, v) => s + v, 0);
    return groups.map((group, i) => {
      const pop = Math.round(total * weights[i] / wTotal);
      const male = Math.round(pop * 0.49);
      const female = pop - male;
      return { group, order: i + 1, male, female, total: pop, cases: totalCases > 0 ? Math.round(totalCases * weights[i] / wTotal) : 0 };
    });
  }
  const groups = [...new Set(raw.map(r => r.grupo_quinquenal))];
  const popTotal = raw.reduce((s, r) => s + r.cantidad, 0) || 1;
  return groups.map(group => {
    const rows = raw.filter(r => r.grupo_quinquenal === group);
    const m = rows.find(r => r.sexo === 'M')?.cantidad || 0;
    const f = rows.find(r => r.sexo === 'F')?.cantidad || 0;
    const total = m + f;
    return { group, order: rows[0]?.orden || 0, male: m, female: f, cases: 0, total };
  }).sort((a, b) => a.order - b.order).map(d => ({ ...d, cases: totalCases > 0 ? Math.round(totalCases * (d.total / popTotal)) : 0 }));
}

function renderReporte() {
  const sel = document.getElementById('reporte-mun-select');
  if (sel && sel.options.length === 0) {
    MUN_CATALOG.forEach(m => {
      const opt = document.createElement('option');
      opt.value = m.code;
      opt.textContent = m.name;
      if (m.code === SELECTED_MUN) opt.selected = true;
      sel.appendChild(opt);
    });
    sel.addEventListener('change', e => {
      SELECTED_MUN = e.target.value;
      renderReporte();
    });
  }
  if (sel) sel.value = SELECTED_MUN;

  const munName = MUN_CATALOG.find(m => m.code === SELECTED_MUN)?.name || SELECTED_MUN;
  const munData = getByMun(SELECTED_MUN);
  const stats = getReportStats(munData, SELECTED_YEAR);
  const currentRecord = stats.current;
  const totalPop = getDemoTotal(SELECTED_MUN)?.poblacion_total || currentRecord.población || 1;
  const ciclos = getDemoCiclos(SELECTED_MUN) || [];
  const totalCases = currentRecord.conteo_dengue || 0;
  const burden = estimateChildBurden(ciclos, totalPop, totalCases);
  const risk = getReportRisk(currentRecord.incidencia_dengue || 0);

  reportSetText('rep-mun-val', munName);
  reportSetText('rep-year-val', SELECTED_YEAR);
  reportSetText('rep-date-val', new Date().toLocaleDateString('es-CO'));
  reportSetText('rep-page2-mun', munName);
  reportSetText('rep-page2-year', SELECTED_YEAR);
  reportSetText('rep-page3-mun', munName);
  reportSetText('rep-kpi-total', fmt(totalCases));
  reportSetText('rep-kpi-inc', fmtDec(currentRecord.incidencia_dengue || 0));
  reportSetText('rep-kpi-pob', fmt(totalPop));
  reportSetText('rep-kpi-infantil', `${fmt(burden.childCases)} (${burden.childPct}%)`);
  reportSetText('rep-risk-note', `Carga ${risk.label}; incidencia ${fmtDec(currentRecord.incidencia_dengue || 0)} x 100,000 habitantes.`);
  reportSetText('rep-trend-note', stats.deltaPct == null ? 'Sin comparacion inmediata disponible.' : `${stats.deltaPct >= 0 ? 'Aumento' : 'Reduccion'} de ${fmtDec(Math.abs(stats.deltaPct))}% frente a ${SELECTED_YEAR - 1}.`);
  reportSetText('rep-action-note', risk.action.charAt(0).toUpperCase() + risk.action.slice(1) + '.');

  const narrativeEl = document.getElementById('reporte-dynamic-text');
  if (narrativeEl) narrativeEl.innerHTML = generateNarrative(munName, SELECTED_YEAR, totalCases, currentRecord.incidencia_dengue || 0, totalPop, burden.childCases, burden.childPct, stats);
  const weekly = getWeeklySeries(SELECTED_MUN, SELECTED_YEAR);
  const weeklyChannel = calculateEndemicChannel(SELECTED_MUN, SELECTED_YEAR, 'conteo_dengue');
  const endemicEl = document.getElementById('rep-endemic-text');
  if (endemicEl) endemicEl.innerHTML = generateWeeklyEndemicNarrative(munName, SELECTED_YEAR, weekly, weeklyChannel);

  renderReportMap(SELECTED_MUN, munName, currentRecord);
  renderWeeklyComparisonTable(weekly, weeklyChannel);
  renderTopMunicipiosTable(SELECTED_YEAR);

  const reportCharts = ['repHist', 'repDemo', 'repEndemic', 'repPyramid'];
  reportCharts.forEach(k => { if (charts[k]) { charts[k].destroy(); delete charts[k]; } });

  const lightOpts = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: { legend: { labels: { color: '#334155', font: { family: 'Space Grotesk', size: 10 } } }, tooltip: { backgroundColor: '#0f172a', titleColor: '#f8fafc', bodyColor: '#cbd5e1' } },
    scales: {
      x: { grid: { color: '#e2e8f0' }, ticks: { color: '#475569', font: { family: 'JetBrains Mono', size: 9 } } },
      y: { grid: { color: '#e2e8f0' }, ticks: { color: '#475569', font: { family: 'JetBrains Mono', size: 9 }, callback: v => fmt(Math.abs(v)) } }
    }
  };

  const ctxEndemic = document.getElementById('rep-chart-endemic');
  if (ctxEndemic) {
    const weekLabels = Array.from({ length: 52 }, (_, i) => `S${i + 1}`);
    charts['repEndemic'] = new Chart(ctxEndemic, {
      data: { labels: weekLabels, datasets: [
        { type: 'line', label: 'Exito', data: weeklyChannel.success, borderColor: '#34d399', backgroundColor: 'rgba(52,211,153,.10)', borderWidth: 1.5, pointRadius: 0, fill: true, tension: .25 },
        { type: 'line', label: 'Seguridad', data: weeklyChannel.safety, borderColor: '#3b82f6', backgroundColor: 'rgba(59,130,246,.08)', borderWidth: 1.5, pointRadius: 0, fill: false, tension: .25 },
        { type: 'line', label: 'Alarma', data: weeklyChannel.alert, borderColor: '#f87171', borderWidth: 2, pointRadius: 0, borderDash: [4, 4], tension: .25 },
        { type: 'bar', label: 'Casos semana', data: weeklyChannel.current, backgroundColor: weeklyChannel.current.map((v, i) => getWeeklyZone(v, weeklyChannel, i) === 'epidemica' ? '#1e3a8a' : '#93c5fd'), borderRadius: 2 }
      ] },
      options: {
        ...lightOpts,
        scales: {
          ...lightOpts.scales,
          x: { ...lightOpts.scales.x, ticks: { ...lightOpts.scales.x.ticks, maxRotation: 0, autoSkip: true, maxTicksLimit: 13 } }
        }
      }
    });
  }

  const ctxHist = document.getElementById('rep-chart-historical');
  if (ctxHist) {
    const weekLabels = Array.from({ length: 52 }, (_, i) => `S${i + 1}`);
    charts['repHist'] = new Chart(ctxHist, {
      data: { labels: weekLabels, datasets: [
        { type: 'bar', label: 'Casos', data: weekly.cases, backgroundColor: 'rgba(59,130,246,.65)', borderColor: '#3b82f6', borderWidth: 1, yAxisID: 'y', borderRadius: 2 },
        { type: 'line', label: 'Incidencia semanal', data: weekly.incidence, borderColor: '#f87171', borderWidth: 2, pointRadius: 0, tension: .35, yAxisID: 'y1' }
      ] },
      options: {
        ...lightOpts,
        scales: {
          ...lightOpts.scales,
          x: { ...lightOpts.scales.x, ticks: { ...lightOpts.scales.x.ticks, maxRotation: 0, autoSkip: true, maxTicksLimit: 13 } },
          y1: { type: 'linear', position: 'right', grid: { drawOnChartArea: false }, ticks: { color: '#475569', font: { family: 'JetBrains Mono', size: 9 } } }
        }
      }
    });
  }

  const ctxPyr = document.getElementById('rep-chart-pyramid');
  if (ctxPyr) {
    const pyr = buildPyramidDataset(SELECTED_MUN, totalCases);
    const maxPop = Math.max(...pyr.map(d => Math.max(d.male, d.female)), 1);
    const maxCases = Math.max(...pyr.map(d => d.cases), 1);
    const caseScale = (maxPop * 0.35) / maxCases;
    charts['repPyramid'] = new Chart(ctxPyr, {
      type: 'bar',
      data: { labels: pyr.map(d => d.group.replace('DE ', '')), datasets: [
        { label: 'Hombres', data: pyr.map(d => -d.male), backgroundColor: '#60a5fa' },
        { label: 'Mujeres', data: pyr.map(d => d.female), backgroundColor: '#f472b6' },
        { label: 'Casos estimados', data: pyr.map(d => d.cases * caseScale), backgroundColor: '#111827' }
      ] },
      options: {
        ...lightOpts,
        indexAxis: 'y',
        plugins: {
          ...lightOpts.plugins,
          tooltip: {
            ...lightOpts.plugins.tooltip,
            callbacks: {
              label: context => {
                const idx = context.dataIndex;
                if (context.datasetIndex === 2) return ` Casos estimados: ${fmt(pyr[idx].cases)}`;
                return ` ${context.dataset.label}: ${fmt(Math.abs(context.parsed.x))}`;
              }
            }
          }
        },
        scales: {
          x: { ...lightOpts.scales.x, stacked: false, ticks: { ...lightOpts.scales.x.ticks, callback: v => fmt(Math.abs(v)) } },
          y: { ...lightOpts.scales.y, stacked: false }
        }
      }
    });
  }

  const ctxDemo = document.getElementById('rep-chart-demographics');
  if (ctxDemo) {
    const sortedCycles = [...ciclos].sort((a, b) => a.id_ciclo - b.id_ciclo);
    const colors = ['#22d3ee', '#34d399', '#fbbf24', '#fb923c', '#3b82f6', '#a78bfa'];
    charts['repDemo'] = new Chart(ctxDemo, {
      type: 'bar',
      data: { labels: sortedCycles.map(c => c.ciclo_nombre), datasets: [{ data: sortedCycles.map(c => c.cantidad), backgroundColor: colors.map(c => c + 'bb'), borderColor: colors, borderWidth: 1, borderRadius: 3 }] },
      options: { ...lightOpts, plugins: { ...lightOpts.plugins, legend: { display: false } } }
    });
  }

  const printBtn = document.getElementById('reporte-print-btn');
  if (printBtn) {
    printBtn.replaceWith(printBtn.cloneNode(true));
    document.getElementById('reporte-print-btn').addEventListener('click', () => window.print());
  }
}
function buildMockGeoJSON() {
  const SIDES = 8;
  const features = (typeof MUN_CATALOG !== 'undefined' ? MUN_CATALOG : []).map(mun => {
    const coords = [];
    const radius = mun.r || 0.05;
    for (let i = 0; i <= SIDES; i++) {
      const angle = (2 * Math.PI * i / SIDES) - Math.PI / 2;
      const dlng = radius * Math.cos(angle);
      const dlat = radius * 1.1 * Math.sin(angle);
      coords.push([
        parseFloat((mun.lng + dlng).toFixed(6)),
        parseFloat((mun.lat + dlat).toFixed(6))
      ]);
    }
    return {
      type: 'Feature',
      properties: { MPIO_CCDGO: mun.code, MPIO_CNMBR: mun.name, lat: mun.lat, lng: mun.lng },
      geometry: { type: 'Polygon', coordinates: [coords] }
    };
  });
  return { type: 'FeatureCollection', features, _mock: true };
}

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildYearSelector();
  wireMapControls();
  wireDiseaseSelector();
  wireChoroControls();
  buildTweaksPanel();
  applyTweaks();

  document.querySelectorAll('.nav-item').forEach(el => {
    el.addEventListener('click', () => navigate(el.dataset.section));
  });
  document.getElementById('lang-btn')?.addEventListener('click', toggleLang);

  navigate('dashboard');
  // Init map after small delay so section is visible
  setTimeout(initMap, 300);
});
