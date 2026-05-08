/* ─────────────────────────────────────────────────────────────────────────────
   IA & ML Forecasting — módulo dummy (sin modelos corridos)
   Renderiza catálogo de modelos, gráfica de pronóstico simulada,
   métricas placeholder, importancia de variables y arquitectura.
   ───────────────────────────────────────────────────────────────────────────── */
(function () {
  const MODELS = [
    { id: 'rf',   name: 'Random Forest',           cat: 'ML',  glyph: 'RF',
      color: '#3b82f6',
      desc: 'Ensamble de árboles para predecir brotes y mapear riesgo de dengue con alta precisión.',
      metrics: { RMSE: 18.2, MAE: 12.4, MAPE: '14.6%', R2: 0.81 },
      features: [['Lag 4 sem', 92], ['Temp media', 78], ['Precipitación', 71], ['NDVI', 55], ['Densidad pob.', 47]],
      arch: ['Tabular', '500 árboles', 'Bagging', 'Predicción'] },
    { id: 'svm',  name: 'Support Vector Machines', cat: 'ML',  glyph: 'SVM',
      color: '#22d3ee',
      desc: 'Clasificación y predicción de patrones de brotes sobre conjuntos de datos complejos.',
      metrics: { 'Acc.': '0.83', 'F1': '0.79', 'AUC': '0.86', 'Prec.': '0.81' },
      features: [['Casos t-1', 88], ['Humedad', 72], ['Temp mín.', 64], ['Lag 8 sem', 51], ['Población', 40]],
      arch: ['Tabular', 'Kernel RBF', 'Margen máx.', 'Clase / score'] },
    { id: 'knn',  name: 'K-Nearest Neighbors',     cat: 'ML',  glyph: 'KNN',
      color: '#34d399',
      desc: 'Minería de datos espaciales — vecindad k de municipios con incidencia similar.',
      metrics: { RMSE: 22.7, MAE: 15.9, MAPE: '18.3%', R2: 0.71 },
      features: [['Vecinos espac.', 95], ['Lag 4 sem', 70], ['Altitud', 58], ['Temp', 52], ['Precip.', 44]],
      arch: ['Tabular', 'k = 7', 'Distancia ponderada', 'Predicción'] },
    { id: 'ann',  name: 'Redes Neuronales (ANN)',  cat: 'DL',  glyph: 'ANN',
      color: '#fbbf24',
      desc: 'Modelado de interacciones entre incidencia del dengue y variables de cambio climático.',
      metrics: { RMSE: 16.5, MAE: 11.2, MAPE: '13.1%', R2: 0.84 },
      features: [['Temp media', 85], ['Lag 4 sem', 80], ['Humedad', 76], ['Precipitación', 68], ['Pob. urb.', 49]],
      arch: ['Tabular', 'Dense 64', 'Dense 32', 'Output'] },
    { id: 'cnn',  name: 'Convolucional (CNN)',     cat: 'DL',  glyph: 'CNN',
      color: '#a78bfa',
      desc: 'Reconocimiento de patrones espaciales avanzados y procesamiento de imágenes / rasters.',
      metrics: { RMSE: 14.8, MAE: 10.1, MAPE: '12.4%', R2: 0.87 },
      features: [['Imagen NDVI', 92], ['LST satelital', 80], ['Uso de suelo', 70], ['Densidad pob.', 58], ['Capa hidro.', 41]],
      arch: ['Raster H×W', 'Conv 3×3', 'Pool', 'FC + Output'] },
    { id: 'lstm', name: 'LSTM',                     cat: 'DL',  glyph: 'LSTM',
      color: '#f87171',
      desc: 'Series temporales — predice tendencias estacionales y picos epidémicos.',
      metrics: { RMSE: 13.4, MAE: 9.6, MAPE: '11.2%', R2: 0.89 },
      features: [['Casos t-1..t-12', 96], ['Temp', 79], ['Humedad', 71], ['Precip. lag', 65], ['Estacionalidad', 60]],
      arch: ['Secuencia', 'LSTM 64', 'LSTM 32', 'Dense + Output'] },
    { id: 'fnn',  name: 'Feedforward (FNN)',        cat: 'DL',  glyph: 'FNN',
      color: '#60a5fa',
      desc: 'Arquitectura base utilizada en predicción de brotes con variables tabulares.',
      metrics: { RMSE: 17.9, MAE: 12.1, MAPE: '14.0%', R2: 0.82 },
      features: [['Lag 4 sem', 84], ['Temp', 76], ['Humedad', 68], ['Precipitación', 60], ['Pob.', 45]],
      arch: ['Tabular', 'Dense 128', 'Dense 64', 'Output'] }
  ];

  let activeModelId = 'rf';
  let chart = null;

  function el(html) {
    const t = document.createElement('template');
    t.innerHTML = html.trim();
    return t.content.firstElementChild;
  }

  function renderCatalog() {
    const grid = document.getElementById('fc-models-grid');
    if (!grid) return;
    grid.innerHTML = '';
    MODELS.forEach(m => {
      const bars = Array.from({ length: 8 }, () => {
        const h = 4 + Math.round(Math.random() * 14);
        return `<span style="height:${h}px"></span>`;
      }).join('');
      const card = el(`
        <div class="fc-model-card ${m.id === activeModelId ? 'active' : ''}"
             data-id="${m.id}" style="--mc:${m.color}">
          <div class="fc-model-head">
            <div class="fc-model-name">
              <div class="fc-model-glyph">${m.glyph}</div>
              ${m.name}
            </div>
            <span class="fc-model-cat">${m.cat}</span>
          </div>
          <div class="fc-model-desc">${m.desc}</div>
          <div class="fc-model-foot">
            <span>${m.cat === 'ML' ? 'Tabular · CV temporal' : 'Tensor · GPU-ready'}</span>
            <div class="fc-mini-bars">${bars}</div>
          </div>
        </div>
      `);
      card.addEventListener('click', () => {
        activeModelId = m.id;
        renderCatalog();
        renderDetail();
      });
      grid.appendChild(card);
    });
  }

  function simulateSeries(model, horizon) {
    // Synthetic: 52 weeks history + horizon weeks forecast with CI
    const hist = [];
    for (let i = 0; i < 52; i++) {
      const seasonal = 60 + 35 * Math.sin((i / 52) * Math.PI * 2 - 1.2);
      const noise = (Math.random() - 0.5) * 18;
      hist.push(Math.max(5, Math.round(seasonal + noise + i * 0.4)));
    }
    const fc = [], lo = [], hi = [];
    const last = hist[hist.length - 1];
    for (let i = 1; i <= horizon; i++) {
      const seasonal = 60 + 35 * Math.sin(((52 + i) / 52) * Math.PI * 2 - 1.2);
      const drift = last * 0.4 + seasonal * 0.6 + i * 0.3;
      const sigma = 6 + i * 1.4;
      fc.push(Math.round(drift));
      lo.push(Math.round(drift - sigma));
      hi.push(Math.round(drift + sigma));
    }
    return { hist, fc, lo, hi };
  }

  function renderDetail() {
    const m = MODELS.find(x => x.id === activeModelId);
    document.getElementById('fc-detail-name').textContent = m.name;
    const horizonSel = document.getElementById('fc-horizonte');
    const h = parseInt((horizonSel && horizonSel.value) || '12', 10) || 12;
    document.getElementById('fc-meta-h').textContent = h + ' sem';

    // Chart
    const { hist, fc, lo, hi } = simulateSeries(m, h);
    const labels = [];
    for (let i = -52 + 1; i <= 0; i++) labels.push('w' + i);
    for (let i = 1; i <= h; i++) labels.push('+w' + i);
    const histPad = hist.concat(Array(h).fill(null));
    const fcPad   = Array(52).fill(null).concat(fc);
    const loPad   = Array(52).fill(null).concat(lo);
    const hiPad   = Array(52).fill(null).concat(hi);

    const ctx = document.getElementById('fc-forecast-canvas');
    if (chart) chart.destroy();
    chart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [
          { label: 'IC superior', data: hiPad, borderColor: 'transparent',
            backgroundColor: m.color + '22', fill: '+1', pointRadius: 0, tension: 0.3 },
          { label: 'IC inferior', data: loPad, borderColor: 'transparent',
            backgroundColor: m.color + '22', fill: false, pointRadius: 0, tension: 0.3 },
          { label: 'Histórico', data: histPad, borderColor: '#94a3b8',
            backgroundColor: '#94a3b822', borderWidth: 1.5, pointRadius: 0, tension: 0.25 },
          { label: 'Pronóstico', data: fcPad, borderColor: m.color,
            backgroundColor: m.color + '33', borderWidth: 2, pointRadius: 0,
            tension: 0.3, borderDash: [4, 3] }
        ]
      },
      options: {
        responsive: true, maintainAspectRatio: false,
        interaction: { intersect: false, mode: 'index' },
        plugins: {
          legend: { labels: { color: '#94a3b8', font: { size: 11 }, filter: i => !i.text.startsWith('IC') } },
          tooltip: { backgroundColor: '#0c1221ee', borderColor: '#1c2d4a', borderWidth: 1 }
        },
        scales: {
          x: { ticks: { color: '#3d5575', maxTicksLimit: 10, font: { size: 10 } },
               grid: { color: '#16203855' } },
          y: { ticks: { color: '#3d5575', font: { size: 10 } },
               grid: { color: '#16203855' } }
        }
      }
    });

    // Metrics
    const mEl = document.getElementById('fc-metrics');
    mEl.innerHTML = '';
    Object.entries(m.metrics).forEach(([k, v]) => {
      mEl.appendChild(el(`
        <div class="fc-metric">
          <div class="fc-metric-lbl">${k}</div>
          <div class="fc-metric-val">${v}</div>
          <div class="fc-metric-sub">simulado</div>
        </div>
      `));
    });

    // Features
    const fEl = document.getElementById('fc-feat-list');
    fEl.innerHTML = '';
    m.features.forEach(([name, val]) => {
      fEl.appendChild(el(`
        <div class="fc-feat-row">
          <span style="flex:0 0 110px;">${name}</span>
          <div class="fc-feat-bar"><div class="fc-feat-fill" style="width:${val}%;"></div></div>
          <span class="fc-feat-val">${val}</span>
        </div>
      `));
    });

    // Architecture
    const aEl = document.getElementById('fc-arch-row');
    aEl.innerHTML = '';
    m.arch.forEach((step, i) => {
      aEl.appendChild(el(`<div class="fc-arch-block">${step}</div>`));
      if (i < m.arch.length - 1) aEl.appendChild(el(`<span class="fc-arch-arrow">→</span>`));
    });
  }

  function init() {
    if (!document.getElementById('fc-models-grid')) return;
    renderCatalog();
    renderDetail();
    ['fc-horizonte', 'fc-municipio', 'fc-target', 'fc-ci'].forEach(id => {
      const e = document.getElementById(id);
      if (e) e.addEventListener('change', renderDetail);
    });
  }

  window.refreshForecastingModule = function () {
    if (!document.getElementById('fc-models-grid')) return;
    renderDetail();
    if (chart) chart.resize();
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
