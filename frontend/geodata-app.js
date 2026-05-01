// ─── GEODATA SALUD — Application logic ───────────────────────────────────────

const I18N = {
  es: {
    dashboard:'Panel', geovisor:'Geovisor', indicadores:'Indicadores',
    tendencias:'Tendencias', priorizacion:'Priorización',
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
    fuente:'Fuente: Secretaría de Salud, Valle del Cauca',
    update:'Última actualización', loading:'Cargando datos...',
  },
  en: {
    dashboard:'Dashboard', geovisor:'Geovisor', indicadores:'Indicators',
    tendencias:'Trends', priorizacion:'Prioritization',
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
let mapInstance = null;
let mapLayers = [];
let charts = {};

function t(k) { return I18N[LANG][k] || k; }

// ─── Navigation ───────────────────────────────────────────────────────────────
function navigate(section) {
  ACTIVE_SECTION = section;
  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  const el = document.getElementById('s-' + section);
  if (el) el.classList.add('active');
  const nav = document.querySelector(`.nav-item[data-section="${section}"]`);
  if (nav) nav.classList.add('active');
  document.getElementById('header-title').textContent = t(section);
  if (section === 'geovisor' && mapInstance) { setTimeout(() => mapInstance.invalidateSize(), 100); }
  // Render charts AFTER section is visible — setTimeout ensures full CSS layout
  setTimeout(() => {
    if (section === 'indicadores') renderIndicadores();
    if (section === 'tendencias') renderTendencias();
    if (section === 'priorizacion') renderPriorizacion();
    if (section === 'dashboard') renderDashboard();
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
    if (decimals === -1) {
      el.textContent = Math.round(val).toString();
    } else {
      el.textContent = decimals > 0 ? fmtDec(val) : fmt(Math.round(val));
    }
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

  } else if (MAP_MODE === 'coropletico') {
    // Use real PostGIS GeoJSON if available, otherwise fall back to mock octagons
    const geomSrc = (typeof window !== 'undefined' && window.GEO_MUNI)
      ? window.GEO_MUNI
      : buildMockGeoJSON();
    const isMock = geomSrc._mock === true;

    // Build lookup: code → record for current year/filter
    const lookup = {};
    data.forEach(r => { lookup[r.MPIO_CCDGO] = r; });

    // Quantile colour scale (5 bins)
    const vals = data.map(r => r[MAP_VAR]).filter(v => v != null).sort((a, b) => a - b);
    const q = f => vals[Math.max(0, Math.floor((vals.length - 1) * f))];
    const bins = [q(0.2), q(0.4), q(0.6), q(0.8)];
    const CHORO_PALETTE = ['#1e3a5f', '#1d4ed8', '#22d3ee', '#fbbf24', '#f87171'];
    const choroplethColor = v => {
      if (v == null) return '#111827';
      if (v > bins[3]) return CHORO_PALETTE[4];
      if (v > bins[2]) return CHORO_PALETTE[3];
      if (v > bins[1]) return CHORO_PALETTE[2];
      if (v > bins[0]) return CHORO_PALETTE[1];
      return CHORO_PALETTE[0];
    };

    const layer = L.geoJSON(geomSrc, {
      style: feat => {
        const code = feat.properties?.MPIO_CCDGO;
        const rec = lookup[code];
        const val = rec ? rec[MAP_VAR] : null;
        const col = choroplethColor(val);
        return {
          fillColor: col, color: '#060a12',
          weight: isMock ? 1.5 : 1,
          fillOpacity: isMock ? 0.80 : 0.78
        };
      },
      onEachFeature: (feat, lyr) => {
        const code = feat.properties?.MPIO_CCDGO;
        const rec = lookup[code];
        if (rec) {
          const col = choroplethColor(rec[MAP_VAR]);
          lyr.bindTooltip(munTooltip(rec, col), { className: 'geo-tooltip', sticky: true });
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
    renderChoroplethLegend(bins, CHORO_PALETTE, isMock);
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
  const codes = [SELECTED_MUN, '76520', '76109'];
  const uniqueCodes = [...new Set(codes)].slice(0, 4);
  const palette = ['#3b82f6','#22d3ee','#34d399','#fbbf24'];
  const datasets = uniqueCodes.map((code, i) => {
    const mun = MUN_CATALOG.find(m => m.code === code);
    const rows = getByMun(code);
    return {
      label: mun?.name || code,
      data: rows.map(r => r.incidencia_dengue),
      borderColor: palette[i], backgroundColor: palette[i] + '18',
      borderWidth: 2.5, pointRadius: 5, pointHoverRadius: 8,
      tension: 0.4, fill: true,
    };
  });
  charts['tendencia'] = new Chart(ctx, {
    type: 'line',
    data: { labels: YEARS, datasets },
    options: fullChartOpts({ yLabel: 'Incidencia ×100k', title: t('serie_hist') })
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
    sel.addEventListener('change', e => { SELECTED_MUN = e.target.value; renderTendencias(); });
  }
}

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
  document.querySelectorAll('.map-mode-btn').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.map-mode-btn').forEach(b => b.classList.remove('active'));
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

// ─── Init ─────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  buildYearSelector();
  wireMapControls();
  wireDiseaseSelector();
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
