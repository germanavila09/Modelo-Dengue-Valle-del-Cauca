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

// ─── Tendencias ───────────────────────────────────────────────────────────────
function renderTendencias() {
  const ctx = document.getElementById('chart-tendencia'); if (!ctx) return;
  if (charts['tendencia']) charts['tendencia'].destroy();
  const codes = TENDENCIA_CODES?.length ? TENDENCIA_CODES : [SELECTED_MUN, '76520', '76109'];
  const uniqueCodes = [...new Set(codes)].slice(0, 6);
  const palette = ['#3b82f6','#22d3ee','#34d399','#fbbf24','#f87171','#a78bfa'];
  const metric = TENDENCIA_METRIC || 'incidencia_dengue';
  const yLabel = metric === 'conteo_dengue' ? 'Casos' : 'Incidencia x100k';
  const title = metric === 'conteo_dengue' ? 'Serie historica - Casos' : t('serie_hist');
  const titleEl = document.querySelector('#s-tendencias .chart-card-title');
  if (titleEl) titleEl.textContent = title;
  const datasets = uniqueCodes.map((code, i) => {
    const mun = MUN_CATALOG.find(m => m.code === code);
    const rows = getByMun(code);
    return {
      label: mun?.name || code,
      data: rows.map(r => r[metric]),
      borderColor: palette[i], backgroundColor: palette[i] + '18',
      borderWidth: 2.5, pointRadius: 5, pointHoverRadius: 8,
      tension: 0.4, fill: true,
    };
  });
  charts['tendencia'] = new Chart(ctx, {
    type: 'line',
    data: { labels: YEARS, datasets },
    options: fullChartOpts({ yLabel, title })
  });
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
