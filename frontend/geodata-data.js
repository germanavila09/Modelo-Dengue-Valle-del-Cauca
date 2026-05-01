// ─── GEODATA SALUD — Mock dataset ────────────────────────────────────────────
// Structure mirrors public.valle_mun (PostgreSQL/PostGIS)
// Replace GEODATA constant with real export from Python pipeline

var YEARS = [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026];

// Base incidence per 100k — epidemic cycle for Valle del Cauca
var BASE_INC = { 2019:185, 2020:88, 2021:215, 2022:162, 2023:398, 2024:445, 2025:312, 2026:168 };

var MUN_CATALOG = [
  { code:'76001', name:'Cali',          lat:3.4516,  lng:-76.5320, pop:2250000, risk_mult:1.15, r:0.06 },
  { code:'76109', name:'Buenaventura',  lat:3.8801,  lng:-77.0311, pop:425000,  risk_mult:2.45, r:0.14 },
  { code:'76520', name:'Palmira',       lat:3.5394,  lng:-76.3036, pop:322000,  risk_mult:1.30, r:0.06 },
  { code:'76834', name:'Tuluá',         lat:4.0841,  lng:-76.2001, pop:218000,  risk_mult:1.10, r:0.05 },
  { code:'76147', name:'Cartago',       lat:4.7458,  lng:-75.9119, pop:139000,  risk_mult:0.98, r:0.05 },
  { code:'76400', name:'Jamundí',       lat:3.2600,  lng:-76.5400, pop:142000,  risk_mult:1.75, r:0.05 },
  { code:'76111', name:'Buga',          lat:3.9000,  lng:-76.2971, pop:122000,  risk_mult:1.05, r:0.05 },
  { code:'76248', name:'Florida',       lat:3.3300,  lng:-76.2300, pop:66500,   risk_mult:1.55, r:0.04 },
  { code:'76616', name:'Pradera',       lat:3.4200,  lng:-76.2400, pop:57000,   risk_mult:1.48, r:0.04 },
  { code:'76895', name:'Zarzal',        lat:4.3901,  lng:-76.0700, pop:51000,   risk_mult:0.90, r:0.04 },
  { code:'76233', name:'El Cerrito',    lat:3.6967,  lng:-76.2984, pop:61000,   risk_mult:1.22, r:0.04 },
  { code:'76126', name:'Caicedonia',    lat:4.3283,  lng:-75.8284, pop:33000,   risk_mult:0.85, r:0.04 },
  { code:'76054', name:'Ansermanuevo',  lat:4.7987,  lng:-76.0358, pop:22500,   risk_mult:0.78, r:0.04 },
  { code:'76318', name:'Guacarí',       lat:3.7660,  lng:-76.3340, pop:24800,   risk_mult:1.18, r:0.04 },
  { code:'76306', name:'Ginebra',       lat:3.7332,  lng:-76.2785, pop:18500,   risk_mult:1.02, r:0.04 },
];

// ─── Mock GeoJSON — hexagonal approximations from centroids ──────────────────
// Used as fallback when window.GEO_MUNI (PostGIS export) is not loaded.
// Sides=8 gives a smooth octagon; r is radius in degrees.
function buildMockGeoJSON() {
  const SIDES = 8;
  const features = MUN_CATALOG.map(mun => {
    const coords = [];
    for (let i = 0; i <= SIDES; i++) {
      const angle = (2 * Math.PI * i / SIDES) - Math.PI / 2;
      // Slightly elongate N-S to compensate for cos(lat) distortion
      const dlng = mun.r * Math.cos(angle);
      const dlat = mun.r * 1.1 * Math.sin(angle);
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

// Deterministic pseudo-random (no Math.random — reproducible)
function srand(seed) {
  let s = seed;
  return function() {
    s = (s * 1664525 + 1013904223) & 0xffffffff;
    return (s >>> 0) / 0xffffffff;
  };
}

// Build full dataset
function buildDataset() {
  const records = [];
  MUN_CATALOG.forEach((mun, mi) => {
    YEARS.forEach((year, yi) => {
      const rand = srand(mi * 100 + yi);
      const noise = 0.85 + rand() * 0.30;
      const incidencia = BASE_INC[year] * mun.risk_mult * noise;
      const pop = Math.round(mun.pop * (1 + (year - 2019) * 0.008));
      const casos = Math.round(pop * incidencia / 100000);
      records.push({
        MPIO_CCDGO: mun.code,
        MPIO_CNMBR: mun.name,
        lat: mun.lat,
        lng: mun.lng,
        año: year,
        población: pop,
        conteo_dengue: casos,
        incidencia_dengue: parseFloat(incidencia.toFixed(1)),
      });
    });
  });
  return records;
}

// ─── Use real data if exported from Python, otherwise use mock ───────────────
// Run: python scripts/exportar_datos_obs.py
// Then uncomment in Geodata Salud.html:
//   <script src="geodata-records.js"></script>
//   <script src="geodata-muni.js"></script>
var GEODATA = (typeof window !== 'undefined' && window.GEO_RECORDS && window.GEO_RECORDS.length)
  ? window.GEO_RECORDS
  : buildDataset();

var DATA_SOURCE = (typeof window !== 'undefined' && window.GEO_RECORDS && window.GEO_RECORDS.length)
  ? 'PostgreSQL/PostGIS' : 'mock';

// ─── Query helpers ────────────────────────────────────────────────────────────

function getByYear(year) {
  return GEODATA.filter(r => r.año === year);
}

function getByMun(code) {
  return GEODATA.filter(r => r.MPIO_CCDGO === code).sort((a,b) => a.año - b.año);
}

function getTotalByYear(year, includeCali = true) {
  return getByYear(year)
    .filter(r => includeCali || r.MPIO_CCDGO !== '76001')
    .reduce((s, r) => s + r.conteo_dengue, 0);
}

function getYearTotals() {
  return YEARS.map(y => ({ year: y, total: getTotalByYear(y) }));
}

function getTopMunByYear(year, field = 'conteo_dengue', n = 10, includeCali = true) {
  return getByYear(year)
    .filter(r => includeCali || r.MPIO_CCDGO !== '76001')
    .sort((a, b) => b[field] - a[field])
    .slice(0, n);
}

function getPivotTable() {
  return MUN_CATALOG.map(mun => {
    const rows = getByMun(mun.code);
    const totalCasos = rows.reduce((s, r) => s + r.conteo_dengue, 0);
    const inc2024 = rows.find(r => r.año === 2024)?.incidencia_dengue || 0;
    const grandTotal = GEODATA.reduce((s, r) => s + r.conteo_dengue, 0);
    const trend = (() => {
      const r2023 = rows.find(r => r.año === 2023)?.conteo_dengue || 0;
      const r2024 = rows.find(r => r.año === 2024)?.conteo_dengue || 0;
      return r2024 > r2023 * 1.1 ? 'up' : r2024 < r2023 * 0.9 ? 'down' : 'stable';
    })();
    const risk = inc2024 > 600 ? 'Crítico' : inc2024 > 350 ? 'Alto' : inc2024 > 150 ? 'Medio' : 'Bajo';
    return {
      code: mun.code, name: mun.name,
      totalCasos, inc2024,
      pct: parseFloat((totalCasos / grandTotal * 100).toFixed(1)),
      trend, risk,
    };
  }).sort((a, b) => b.totalCasos - a.totalCasos).map((r, i) => ({ ...r, rank: i + 1 }));
}

function getKPIs(year = 2024) {
  const rows = getByYear(year);
  const total = rows.reduce((s, r) => s + r.conteo_dengue, 0);
  const incProm = rows.reduce((s, r) => s + r.incidencia_dengue, 0) / rows.length;
  const critical = rows.filter(r => r.incidencia_dengue > 400).length;
  const peakYear = YEARS.reduce((best, y) => getTotalByYear(y) > getTotalByYear(best) ? y : best, 2019);
  return { total, incProm: parseFloat(incProm.toFixed(1)), critical, peakYear };
}
