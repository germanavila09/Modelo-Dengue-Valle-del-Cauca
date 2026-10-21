// Informe Word del Objetivo 1: autocorrelación espacial (Moran, LISA) y clústeres (Gi*)
// de casos de dengue por hexágono de 200 m en Palmira, Buga, Tuluá y Jamundí, 2019–2023.
//
// Lee las salidas de scripts/clusters_hexagonos.py y scripts/figuras_objetivo1.py:
//   node scripts/informe_word_objetivo1.js [carpeta_entrada] [archivo_salida.docx]
// Por defecto: outputs/clusters_hexagonos  →  outputs/clusters_hexagonos/informe_objetivo1_clusters.docx
//
// Privacidad: usa solo agregados municipales y mapas sin conteos (no lee interno/).

const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, Header, Footer,
  AlignmentType, HeadingLevel, WidthType, ShadingType, BorderStyle, PageNumber, PageBreak,
  LevelFormat, TableOfContents, VerticalAlign,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const ENTRADA = path.resolve(process.argv[2] || path.join(ROOT, "outputs", "clusters_hexagonos"));
const SALIDA = path.resolve(process.argv[3] || path.join(ENTRADA, "informe_objetivo1_clusters.docx"));
const FIG = path.join(ENTRADA, "figuras");

// ── Datos ────────────────────────────────────────────────────────────────────
function csv(nombre) {
  const txt = fs.readFileSync(path.join(ENTRADA, nombre), "utf8").replace(/\r/g, "").trim();
  const [cab, ...filas] = txt.split("\n");
  const cols = cab.split(",");
  return filas.map((f) => {
    const v = f.split(",");
    const o = {};
    cols.forEach((c, i) => { const x = v[i]; o[c] = x !== "" && !isNaN(Number(x)) && !/^0\d/.test(x) ? Number(x) : x; });
    return o;
  });
}
const MET = csv("metricas_municipio_anio.csv");
const PERS = csv("persistencia_resumen.csv");
const CAL = csv("calidad_geocodificacion.csv");
const AREA = csv("area_estudio.csv");
const CLIMA = csv("clima_anual_municipio.csv");
const RES = csv("resumen_lisa_gi_2019_2023.csv");
const META = JSON.parse(fs.readFileSync(path.join(ENTRADA, "metadata.json"), "utf8"));

const MUN = ["Palmira", "Guadalajara de Buga", "Tuluá", "Jamundí"];
const CORTO = { "Guadalajara de Buga": "Buga" };
const sh = (m) => CORTO[m] || m;
const ANIOS = ["2019", "2020", "2021", "2022", "2023"];
const nf = (v, d = 1) => Number(v).toLocaleString("es-CO", { minimumFractionDigits: d, maximumFractionDigits: d });
const ni = (v) => Number(v).toLocaleString("es-CO");
const met = (m, a, v = "principal") => MET.find((r) => r.municipio === m && String(r.anio) === a && r.variante === v);
const pooled = MUN.map((m) => met(m, "2019-2023"));
const sens = MUN.map((m) => met(m, "2019-2023", "sensibilidad"));
const rng = (arr, k, d) => `${nf(Math.min(...arr.map((r) => r[k])), d)}–${nf(Math.max(...arr.map((r) => r[k])), d)}`;
const casosAnalizados = pooled.reduce((s, r) => s + r.casos, 0);
const persist = (m, clase, v = "principal") => PERS.find((r) => r.municipio === m && r.clase === clase && r.variante === v) || { hexagonos: 0, pct_casos_mpio: 0, casos: 0 };
const sigPorAnio = ANIOS.map((a) => ({ a, n: MUN.filter((m) => met(m, a).moran_p < 0.05).length }));
const climaUtil = CLIMA.filter((r) => r.anio >= 2019 && r.anio <= 2023 && r.meses_validos >= 9).length;
const fuenteDb = META.fuente === "db";

// ── Estilo ───────────────────────────────────────────────────────────────────
const FONT = "Calibri";
const C_TXT = "1F1F1E", C_SEC = "52514E", C_ACC = "B2182B", C_HEAD = "F1F0EB", C_LINE = "D6D5CE";
const W_PAGE = 12240, MARGIN = 1300, W_TXT = W_PAGE - 2 * MARGIN; // DXA

const p = (runs, opt = {}) => new Paragraph({
  spacing: { after: 120, line: 290 }, ...opt,
  children: (Array.isArray(runs) ? runs : [runs]).map((r) => (typeof r === "string" ? new TextRun(r) : r)),
});
const t = (text, o = {}) => new TextRun({ text, ...o });
const b = (text) => new TextRun({ text, bold: true });
const i = (text) => new TextRun({ text, italics: true });
const h1 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(text)] });
const h2 = (text) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(text)] });
const bullet = (runs, nivel = 0) => new Paragraph({
  numbering: { reference: "vinetas", level: nivel }, spacing: { after: 80, line: 280 },
  children: (Array.isArray(runs) ? runs : [runs]).map((r) => (typeof r === "string" ? new TextRun(r) : r)),
});
const formula = (runs) => new Paragraph({
  alignment: AlignmentType.CENTER, spacing: { before: 100, after: 140 },
  children: runs.map((r) => (typeof r === "string" ? new TextRun({ text: r, font: "Cambria Math", size: 23 }) : r)),
});

let nFig = 0, nTab = 0;
function pngSize(file) {
  const buf = fs.readFileSync(file);
  return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20), buf };
}
function figura(archivo, pie, anchoIn = 6.3) {
  const { w, h, buf } = pngSize(path.join(FIG, archivo));
  const ancho = Math.round(anchoIn * 96), alto = Math.round((ancho * h) / w);
  nFig += 1;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: ancho, height: alto },
        altText: { title: `Figura ${nFig}`, description: pie, name: archivo } })] }),
    new Paragraph({ alignment: AlignmentType.LEFT, spacing: { after: 220 },
      children: [new TextRun({ text: `Figura ${nFig}. `, bold: true, size: 19, color: C_SEC }), new TextRun({ text: pie, size: 19, color: C_SEC })] }),
  ];
}
function tabla(titulo, cabecera, filas, anchos, opts = {}) {
  nTab += 1;
  const total = anchos.reduce((a, x) => a + x, 0);
  const borde = { style: BorderStyle.SINGLE, size: 4, color: C_LINE };
  const sinBorde = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
  const juntar = filas.length <= 12; // tablas cortas: no partir entre páginas
  const celda = (txt, j, head, ultima = false) => new TableCell({
    width: { size: anchos[j], type: WidthType.DXA },
    shading: head ? { type: ShadingType.CLEAR, color: "auto", fill: C_HEAD } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    verticalAlign: VerticalAlign.CENTER,
    borders: { top: sinBorde, left: sinBorde, right: sinBorde, bottom: borde },
    children: [new Paragraph({ keepNext: juntar && !ultima, alignment: j >= (opts.numDesde ?? 1) ? AlignmentType.RIGHT : AlignmentType.LEFT,
      children: [new TextRun({ text: String(txt), bold: !!head, size: 18, color: head ? C_SEC : C_TXT })] })],
  });
  return [
    new Paragraph({ spacing: { before: 160, after: 80 }, keepNext: true,
      children: [new TextRun({ text: `Tabla ${nTab}. `, bold: true, size: 19, color: C_SEC }), new TextRun({ text: titulo, size: 19, color: C_SEC })] }),
    new Table({
      width: { size: total, type: WidthType.DXA }, columnWidths: anchos,
      rows: [new TableRow({ tableHeader: true, children: cabecera.map((c, j) => celda(c, j, true)) }),
        ...filas.map((f, k) => new TableRow({ cantSplit: true, children: f.map((c, j) => celda(c, j, false, k === filas.length - 1)) }))],
    }),
    new Paragraph({ spacing: { after: 160 }, children: [] }),
  ];
}
const nota = (texto) => new Paragraph({
  spacing: { before: 120, after: 160 }, shading: { type: ShadingType.CLEAR, color: "auto", fill: "F6F5F1" },
  border: { left: { style: BorderStyle.SINGLE, size: 18, color: C_ACC, space: 8 } },
  indent: { left: 160, right: 160 },
  children: (Array.isArray(texto) ? texto : [texto]).map((r) => (typeof r === "string" ? new TextRun({ text: r, size: 20 }) : r)),
});

// ── Contenido ────────────────────────────────────────────────────────────────
const portada = [
  new Paragraph({ spacing: { before: 2400, after: 120 }, children: [t("OBSERVATORIO GEOSALUD · VALLE DEL CAUCA", { size: 20, color: C_SEC, characterSpacing: 40 })] }),
  new Paragraph({ spacing: { after: 240 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: C_ACC, space: 12 } },
    children: [t("Clústeres espaciales de dengue a escala intraurbana en Palmira, Buga, Tuluá y Jamundí, 2019–2023", { size: 44, bold: true, color: C_TXT })] }),
  p(t("Objetivo 1 · Componente de autocorrelación espacial (I de Moran, LISA) y detección de clústeres (Getis-Ord Gi*) en hexágonos de 200 m", { size: 24, color: C_SEC })),
  new Paragraph({ spacing: { before: 1800, after: 60 }, children: [t("Informe técnico", { bold: true, size: 22 })] }),
  p(t(`Octubre de 2026 · ${fuenteDb ? "Versión calculada desde la base de datos" : "Versión preliminar (conteos agregados; pendiente recalcular desde la base de datos)"}`, { size: 20, color: C_SEC })),
  p(t("Uso analítico. El documento contiene solo agregados municipales y mapas sin conteos; no incluye identificadores, direcciones, fechas ni coordenadas de casos.", { size: 18, color: C_SEC, italics: true })),
  new Paragraph({ children: [new PageBreak()] }),
];

const indice = [
  new Paragraph({ spacing: { after: 200 }, children: [t("Contenido", { bold: true, size: 28 })] }),
  new TableOfContents("Contenido", { hyperlink: true, headingStyleRange: "1-2" }),
  new Paragraph({ children: [new PageBreak()] }),
];

const persistTop = MUN.map((m) => ({ m, ...persist(m, "persistente") })).sort((a, c) => c.pct_casos_mpio - a.pct_casos_mpio);
const resumen = [
  h1("Resumen ejecutivo"),
  p(["Este informe evalúa si los casos de dengue notificados entre 2019 y 2023 en las cabeceras de Palmira, Guadalajara de Buga, Tuluá y Jamundí se agrupan en el espacio a una escala más fina que el barrio, usando una malla de hexágonos de 200 m. Se aplicaron el ", i("I de Moran global"), ", los ", i("indicadores locales de asociación espacial (LISA)"), " y el estadístico ", i("Getis-Ord Gi*"), " para identificar clústeres, y se revisó si los datos climáticos disponibles permiten asociarlos con precipitación, humedad y temperatura."]),
  bullet([b("Hay clústeres significativos en los cuatro municipios. "), t(`En el acumulado 2019–2023 el I de Moran va de ${rng(pooled, "moran_I", 2)} (p = 0,001 en todos) y sube a ${rng(sens, "moran_I", 2)} al retirar ubicaciones imprecisas.`)]),
  bullet([b("El dengue está concentrado. "), t(`Los hexágonos alto-alto ocupan entre ${rng(pooled, "pct_area_HH", 0)} % del área urbana y reúnen entre ${rng(pooled, "pct_casos_en_HH", 0)} % de los casos.`)]),
  bullet([b("Los clústeres aparecen con las epidemias. "), t(`La autocorrelación es significativa en ${sigPorAnio.filter((x) => x.n >= 3).map((x) => x.a).join(", ")} en la mayoría de municipios y se debilita en ${sigPorAnio.filter((x) => x.n <= 2).map((x) => x.a).join(" y ")}, años de baja transmisión.`)]),
  bullet([b("Pocos focos son persistentes. "), t(`Los hexágonos que son alto-alto tres años o más concentran ${nf(persistTop[0].pct_casos_mpio)} % de los casos en ${sh(persistTop[0].m)} y ${nf(persistTop[1].pct_casos_mpio)} % en ${sh(persistTop[1].m)}; en ${sh(persistTop[3].m)} y ${sh(persistTop[2].m)} los focos cambian de lugar de un año a otro.`)]),
  bullet([b("La geocodificación limita la precisión. "), t(`Entre ${rng(CAL, "pct_sumidero", 1)} % de los casos están ubicados en un punto por defecto del municipio y se excluyeron.`)]),
  bullet([b("La asociación con el clima no puede estimarse con la fuente actual. "), t(`Solo ${climaUtil} de 20 combinaciones municipio-año tienen al menos 9 meses de dato climático válido, y la fuente contiene valores físicamente imposibles.`)]),
  new Paragraph({ children: [new PageBreak()] }),
];

const intro = [
  h1("1. Introducción y objetivo"),
  p("El dengue es endémico en el valle geográfico del río Cauca y su transmisión urbana depende de la presencia de Aedes aegypti, de las condiciones de la vivienda y del entorno, y de la variabilidad climática. Identificar dónde se agrupan los casos dentro de la ciudad es el primer paso para orientar la vigilancia entomológica y las acciones de control hacia los sectores de mayor carga."),
  p([b("Objetivo 1. "), t("Explorar la asociación de los clústeres de dengue con las variables climáticas (precipitación, humedad, temperatura), socioeconómicas, entomológicas y las intervenciones de control vectorial a escala de barrio en Palmira, Buga, Tuluá y Jamundí en el Valle del Cauca, Colombia, de 2019 a 2023.")]),
  p("Este informe resuelve el primer componente del objetivo: la detección y caracterización de los clústeres espaciales. Además documenta qué tan preparados están los datos climáticos para la etapa de asociación y qué insumos faltan para las variables socioeconómicas, entomológicas y de intervención."),
];

const areaFilas = MUN.map((m) => {
  const a = AREA.find((r) => r.municipio === m), c = CAL.find((r) => r.municipio === m);
  return [sh(m), ni(c.casos), `${nf(c.pct_sumidero)} %`, `${nf(c.pct_centroide)} %`, ni(a.hex_area_urbana), `${ni(a.casos_2019_2023_excluidos)} (${nf(a.pct_casos_excluidos)} %)`];
});
const datos = [
  h1("2. Área de estudio y datos"),
  h2("2.1 Área de estudio"),
  p("Los cuatro municipios se ubican en el valle geográfico del río Cauca, entre 900 y 1.100 m s. n. m., con clima cálido y transmisión endémica de dengue. El análisis se concentra en las áreas urbanas, donde reside la mayor parte de la población y de los casos."),
  ...figura("f01_localizacion.png", "Localización de Palmira, Guadalajara de Buga, Tuluá y Jamundí en el Valle del Cauca.", 3.9),
  h2("2.2 Fuentes"),
  bullet([b("Casos de dengue: "), t("notificación individual a SIVIGILA (eventos 210 dengue y 220 dengue grave), geocodificada, en la base restringida del observatorio. Se usan los casos de 2019 a 2023 agregados por hexágono; ningún dato individual sale de la base.")]),
  bullet([b("Malla hexagonal: "), t("hexágonos regulares de 200 m (tabla public.hexagonos), con asignación de municipio.")]),
  bullet([b("Clima: "), t("serie mensual por municipio de precipitación, temperatura máxima y mínima y humedad relativa máxima y mínima (tabla clima_mensual_municipio).")]),
  bullet([b("Límites municipales: "), t("capa de municipios del Marco Geoestadístico Nacional.")]),
  h2("2.3 Calidad de la geocodificación"),
  p("Antes del análisis se revisó la ubicación de los casos. Una fracción importante comparte exactamente la misma coordenada: cuando un punto concentra cien o más casos corresponde a una ubicación por defecto del municipio (por ejemplo, el centro o una institución), no al domicilio, y se excluyó. Los puntos con entre 10 y 99 casos se interpretan como probables centroides de barrio: se conservan en el análisis principal y se retiran en un análisis de sensibilidad."),
  ...figura("f02_geocodificacion.png", "Composición de los casos 2019–2023 según la calidad de su ubicación."),
  p("Además, el área urbana se definió como los grupos contiguos de al menos 10 hexágonos con algún caso entre 2019 y 2026. Los hexágonos dispersos, principalmente rurales, quedan fuera porque no tienen vecinos para el análisis de vecindad."),
  ...tabla("Casos, calidad de ubicación y área de estudio por municipio, 2019–2023.",
    ["Municipio", "Casos", "Punto por defecto", "Probable centroide", "Hexágonos urbanos", "Casos dispersos excluidos"],
    areaFilas, [1500, 1150, 1500, 1550, 1500, 2440]),
];

const metodos = [
  h1("3. Métodos"),
  h2("3.1 Unidad de análisis y matriz de vecindad"),
  p(`La unidad es el hexágono de 200 m. Para cada municipio se construyó una matriz de pesos espaciales W en la que cada hexágono tiene como vecinos los seis hexágonos contiguos (banda de distancia sobre los centroides en el sistema MAGNA-SIRGAS Origen Nacional, EPSG:9377), estandarizada por filas. La variable es el número de casos por hexágono en cada año y en el acumulado 2019–2023; dentro del área urbana, los hexágonos sin casos cuentan como cero.`),
  h2("3.2 Autocorrelación espacial global: I de Moran"),
  p("El I de Moran mide si los valores similares tienden a ubicarse cerca unos de otros en el conjunto del área de estudio:"),
  formula(["I = (n / S", new TextRun({ text: "0", subScript: true, font: "Cambria Math", size: 23 }), ") · ΣᵢΣⱼ wᵢⱼ zᵢ zⱼ / Σᵢ zᵢ²"]),
  p("donde n es el número de hexágonos, zᵢ es la desviación de los casos del hexágono i respecto a la media, wᵢⱼ son los pesos espaciales y S₀ es la suma de todos los pesos. Valores positivos indican agrupamiento de valores similares; valores cercanos a cero, distribución aleatoria. La significancia se evaluó con 999 permutaciones condicionales (p mínimo 0,001). El diagrama de dispersión de Moran representa cada hexágono por sus casos estandarizados frente al promedio de sus vecinos (rezago espacial); la pendiente de la recta es el I de Moran."),
  h2("3.3 Indicadores locales de asociación espacial (LISA)"),
  p("El I de Moran local descompone el indicador global para cada hexágono:"),
  formula(["Iᵢ = zᵢ · Σⱼ wᵢⱼ zⱼ / (Σₖ zₖ² / n)"]),
  p("Según el signo de zᵢ y de su rezago espacial, cada hexágono significativo se clasifica como alto-alto (HH, foco: muchos casos rodeado de muchos casos), bajo-bajo (LL), alto-bajo (HL) o bajo-alto (LH); los dos últimos son atípicos espaciales. La significancia se evaluó con 999 permutaciones condicionales (semilla 42) y se informa también el número de focos que se mantienen tras la corrección por tasa de falsos descubrimientos (FDR). Los mapas de significancia muestran el nivel p de cada hexágono significativo."),
  h2("3.4 Detección de puntos calientes: Getis-Ord Gi*"),
  p("El estadístico Gi* compara la suma de casos en el vecindario de cada hexágono (incluido él mismo) con la esperada si los casos se distribuyeran al azar:"),
  formula(["Gᵢ* = Σⱼ wᵢⱼ xⱼ / Σⱼ xⱼ"]),
  p("Se expresa como puntuación z: valores positivos y significativos son puntos calientes y negativos, puntos fríos. Se reportan con 90 %, 95 % y 99 % de confianza (999 permutaciones). A diferencia de LISA, Gi* no distingue atípicos y suele delimitar zonas calientes más amplias."),
  h2("3.5 Persistencia de los focos"),
  p("Para cada hexágono se contó el número de años entre 2019 y 2023 en que fue núcleo alto-alto: persistente (tres o más años), intermitente (dos), esporádico (uno) o nunca."),
  h2("3.6 Análisis de sensibilidad"),
  p(`Todo el análisis se repitió retirando además los probables centroides de barrio. Variante principal: ${META.variantes.principal}. Variante de sensibilidad: ${META.variantes.sensibilidad}.`),
  h2("3.7 Clima"),
  p("Para cada municipio y año se resumieron los meses con dato climático válido, descartando valores físicamente imposibles (precipitaciones mensuales mayores de 1.000 mm, humedad máxima menor de 50 %, temperaturas mínimas mayores que las máximas). Solo se plantea la asociación cuando hay al menos 9 meses válidos."),
  h2("3.8 Programas y protección de datos"),
  p("El análisis se implementó en Python con GeoPandas, libpysal y esda (PySAL) sobre PostgreSQL/PostGIS. Los casos se agregan por hexágono dentro de la base restringida; los mapas no muestran conteos y los atípicos alto-bajo y bajo-alto solo se dibujan cuando el hexágono tiene al menos cinco casos, para no señalar casos aislados."),
];

const tablaMoran = MUN.map((m, k) => {
  const r = pooled[k], s = sens[k];
  return [sh(m), ni(r.casos), nf(r.moran_I, 3), nf(r.moran_z, 2), nf(r.moran_p, 3), nf(s.moran_I, 3), nf(s.moran_p, 3)];
});
const tablaLisa = MUN.map((m) => {
  const r = RES.find((x) => x.municipio === m);
  const pm = pooled[MUN.indexOf(m)];
  return [sh(m), ni(r.hexagonos), r.lisa_HH, pm.hex_HH_fdr, r.lisa_LL, r.lisa_HL, r.lisa_LH, r.lisa_atipicos_suprimidos];
});
const tablaGi = MUN.map((m) => {
  const r = RES.find((x) => x.municipio === m);
  return [sh(m), r.gi_c99, r.gi_c95, r.gi_c90, r.gi_f90, r.gi_f95, r.gi_f99];
});
const tablaConc = MUN.map((m, k) => {
  const r = pooled[k];
  return [sh(m), `${nf(r.pct_area_HH)} %`, `${nf(r.pct_casos_en_HH)} %`, nf(r.pct_casos_en_HH / r.pct_area_HH, 1),
    `${persist(m, "persistente").hexagonos} (${nf(persist(m, "persistente").pct_casos_mpio)} %)`,
    `${persist(m, "intermitente").hexagonos} (${nf(persist(m, "intermitente").pct_casos_mpio)} %)`,
    `${persist(m, "esporadico").hexagonos} (${nf(persist(m, "esporadico").pct_casos_mpio)} %)`];
});

const descLisa = {
  "Palmira": "En Palmira los focos alto-alto no forman un único núcleo: aparecen varios sectores separados, en el norte, el noroccidente, el oriente y, con mayor significancia, en el extremo sur de la cabecera. Los hexágonos bajo-bajo se distribuyen en la periferia occidental y nororiental.",
  "Guadalajara de Buga": "En Buga el clúster alto-alto es compacto y se ubica en el sector norte y nororiental de la cabecera, con alta significancia; los hexágonos bajo-bajo se concentran en el occidente y el sur.",
  "Tuluá": "En Tuluá se observa el clúster más extenso y coherente: un núcleo alto-alto en el noroccidente de la cabecera que se repite en varios años, mientras el oriente y el sur aparecen como zonas bajo-bajo.",
  "Jamundí": "En Jamundí el foco alto-alto se localiza en el sector centro-sur de la cabecera; el occidente y el suroccidente aparecen como bajo-bajo. El número de casos es menor y una parte importante de los atípicos se suprimió por tener menos de cinco casos.",
};
const archivoLisa = { "Palmira": "f05_lisa_palmira.png", "Guadalajara de Buga": "f06_lisa_buga.png", "Tuluá": "f07_lisa_tulua.png", "Jamundí": "f08_lisa_jamundi.png" };

const tablaAnual = [];
MUN.forEach((m) => ANIOS.forEach((a) => {
  const r = met(m, a);
  tablaAnual.push([sh(m), a, ni(r.casos), nf(r.moran_I, 3), nf(r.moran_p, 3), r.hex_HH, `${nf(r.pct_casos_en_HH)} %`]);
}));

const resultados = [
  h1("4. Resultados"),
  h2("4.1 Autocorrelación espacial global"),
  p(`Se analizaron ${ni(casosAnalizados)} casos ubicados en ${ni(pooled.reduce((s, r) => s + r.hex_huella, 0))} hexágonos urbanos. En el acumulado 2019–2023 el I de Moran es positivo y significativo en los cuatro municipios (Tabla ${nTab + 1}): los hexágonos con muchos casos tienden a estar rodeados de hexágonos con muchos casos. Al retirar los probables centroides de barrio el indicador aumenta, lo que indica que la imprecisión de la geocodificación atenúa el patrón pero no lo produce.`),
  ...tabla("I de Moran global, casos acumulados 2019–2023 (999 permutaciones).",
    ["Municipio", "Casos", "I principal", "z", "p", "I sensibilidad", "p"],
    tablaMoran, [2200, 1200, 1400, 1100, 1100, 1500, 1140]),
  p("La Figura 3 muestra la evolución anual. La autocorrelación es más fuerte en los años epidémicos (2019, 2020 y 2023) y cae cerca de cero en 2021 y 2022, cuando hubo pocos casos. Jamundí mantiene una autocorrelación moderada y significativa incluso en años de baja transmisión."),
  ...figura("f03_moran_anual.png", "I de Moran por año y municipio. Punto relleno: p < 0,05; punto hueco: no significativo."),
  ...figura("f04_moran_dispersion.png", "Diagramas de dispersión de Moran, casos acumulados 2019–2023. Cada punto es un hexágono, coloreado según su categoría LISA; la pendiente de la recta es el I de Moran."),
  h2("4.2 Clústeres locales (LISA)"),
  p(`La Tabla ${nTab + 1} resume el número de hexágonos en cada categoría LISA para el acumulado 2019–2023, y las Figuras ${nFig + 1} a ${nFig + 4} muestran los mapas de clústeres y de significancia por municipio.`),
  ...tabla("Hexágonos por categoría LISA, casos acumulados 2019–2023 (p < 0,05).",
    ["Municipio", "Hexágonos", "Alto-alto", "Alto-alto FDR", "Bajo-bajo", "Alto-bajo", "Bajo-alto", "Atípicos suprimidos"],
    tablaLisa, [1500, 1150, 1050, 1250, 1050, 1050, 1050, 1540]),
  ...MUN.flatMap((m) => [p(descLisa[m]), ...figura(archivoLisa[m], `${sh(m)}: mapa de clústeres LISA y mapa de significancia, casos acumulados 2019–2023.`)]),
  h2("4.3 Dinámica anual de los clústeres"),
  p("Los mapas anuales (Figura " + (nFig + 1) + ") muestran que los focos alto-alto se expanden en los años epidémicos y casi desaparecen en 2021 y 2022. En esos años de baja transmisión predominan los hexágonos bajo-bajo, que reflejan sobre todo la abundancia de ceros y no deben interpretarse como zonas protegidas."),
  ...figura("f09_lisa_anual.png", "Clústeres LISA por año y municipio (p < 0,05)."),
  h2("4.4 Puntos calientes (Getis-Ord Gi*)"),
  p("Los puntos calientes de Gi* coinciden con los núcleos alto-alto de LISA y delimitan zonas algo más amplias, lo que facilita definir sectores operativos para el control vectorial (Figura " + (nFig + 1) + ", Tabla " + (nTab + 1) + ")."),
  ...figura("f10_gi_hotspots.png", "Puntos calientes y fríos (Getis-Ord Gi*), casos acumulados 2019–2023."),
  ...tabla("Hexágonos por nivel de confianza de Gi*, casos acumulados 2019–2023.",
    ["Municipio", "Caliente 99 %", "Caliente 95 %", "Caliente 90 %", "Frío 90 %", "Frío 95 %", "Frío 99 %"],
    tablaGi, [1700, 1260, 1260, 1260, 1260, 1450, 1450]),
  h2("4.5 Concentración y persistencia"),
  p(`Los hexágonos alto-alto reúnen una proporción de casos entre ${nf(Math.min(...pooled.map((r) => r.pct_casos_en_HH / r.pct_area_HH)), 1)} y ${nf(Math.max(...pooled.map((r) => r.pct_casos_en_HH / r.pct_area_HH)), 1)} veces mayor que el área que ocupan. Sin embargo, la mayoría de los focos lo son un solo año: los focos persistentes son pocos y se concentran en ${sh(persistTop[0].m)} y ${sh(persistTop[1].m)}.`),
  ...figura("f12_concentracion.png", "Porcentaje del área urbana en hexágonos alto-alto y porcentaje de los casos que concentran, 2019–2023."),
  ...tabla("Concentración de casos y persistencia de los focos, 2019–2023 (número de hexágonos y % de los casos del municipio).",
    ["Municipio", "% área alto-alto", "% casos alto-alto", "Razón", "Persistentes", "Intermitentes", "Esporádicos"],
    tablaConc, [1500, 1300, 1300, 900, 1500, 1570, 1570]),
  ...figura("f13_persistencia_barras.png", "Distribución de los casos 2019–2023 según la persistencia del foco de su hexágono."),
  ...figura("f11_persistencia_mapa.png", "Persistencia de los focos alto-alto entre 2019 y 2023."),
  h2("4.6 Disponibilidad de datos climáticos"),
  p(`Para asociar los clústeres con el clima se requieren series completas por municipio. Solo ${climaUtil} de 20 combinaciones municipio-año tienen al menos 9 meses válidos (Figura ${nFig + 1}); Jamundí no tiene ningún año utilizable y Tuluá solo 2020. La fuente contiene además precipitaciones mensuales de decenas de miles de milímetros, humedades máximas menores de 50 % y, en Tuluá, temperaturas máximas medias cercanas a 16 °C, propias de una estación de montaña y no de la cabecera.`),
  ...figura("f14_clima_cobertura.png", "Meses con dato climático válido por municipio y año.", 4.6),
  nota([b("Conclusión sobre el clima. "), t("Con la fuente actual cualquier correlación entre clima y clústeres es inestable (n ≤ 5) y no se interpreta. La asociación requiere series de reanálisis completas (CHIRPS para lluvia, ERA5-Land para temperatura y humedad) y conteos mensuales por hexágono con rezagos de 0 a 3 meses.")]),
];

const discusion = [
  h1("5. Discusión"),
  p("Los resultados confirman que, dentro de las cabeceras de los cuatro municipios, el dengue no se distribuye al azar: se agrupa en sectores de pocas cuadras que concentran entre un sexto y casi un tercio de los casos. La autocorrelación es más intensa en los años epidémicos, lo que es consistente con brotes que se propagan por contigüidad desde focos iniciales, y se diluye en los años de baja transmisión, cuando los casos son esporádicos."),
  p("Que la mayoría de los focos cambie de lugar entre años sugiere que la transmisión responde a condiciones locales cambiantes (criaderos, movilidad, inmunidad de la población a serotipos circulantes) más que a sectores permanentemente de alto riesgo. Los focos persistentes de Tuluá y Buga son la excepción y constituyen los candidatos más claros para vigilancia entomológica continua y para evaluar el efecto de las intervenciones."),
  p("La imprecisión de la geocodificación atenúa el patrón: al excluir los probables centroides de barrio, el I de Moran aumenta en todos los municipios. Mejorar la calidad de la dirección en la notificación tendría un efecto directo sobre la capacidad de detectar focos."),
];

const limitaciones = [
  h1("6. Limitaciones"),
  bullet([b("Sin población por hexágono. "), t("Los clústeres son de casos y no de tasas; parte del patrón puede reflejar la densidad de población. Se requiere estimar la población por hexágono con las manzanas del censo DANE 2018 para calcular tasas suavizadas (Bayes empírico).")]),
  bullet([b("Geocodificación. "), t("Entre 8 % y 23 % de los casos de cada municipio se ubicaron en un punto por defecto y se excluyeron; si su distribución real no es aleatoria, los clústeres pueden estar subestimados en algunos sectores.")]),
  bullet([b("Área de estudio aproximada. "), t("Sin un perímetro urbano oficial, el área se definió por la presencia de casos en 2019–2026, lo que puede omitir sectores urbanos sin casos.")]),
  bullet([b("Pruebas múltiples. "), t("Con corrección FDR se mantienen pocos hexágonos alto-alto; los mapas a p < 0,05 deben leerse como exploratorios.")]),
  bullet([b("Escala anual. "), t("Los clústeres se calcularon por año; la dinámica intraanual y los rezagos climáticos requieren conteos mensuales o semanales.")]),
  ...(fuenteDb ? [] : [bullet([b("Versión preliminar. "), t("Los conteos provienen de una agregación previa por hexágono; los resultados deben recalcularse directamente desde la base de datos.")])]),
];

const conclusiones = [
  h1("7. Conclusiones y próximos pasos"),
  p("El componente espacial del Objetivo 1 queda respondido: existen clústeres de dengue significativos a escala intraurbana en Palmira, Buga, Tuluá y Jamundí entre 2019 y 2023, ligados a los años epidémicos y con pocos focos persistentes. La asociación con las demás variables del objetivo requiere completar los insumos:"),
  ...tabla("Estado de los componentes del Objetivo 1.",
    ["Componente", "Estado", "Siguiente paso"],
    [
      ["Clústeres a escala fina", "Respondido", "Recalcular desde la base de datos y fijar la versión final."],
      ["Escala de barrio", "Parcial", "Obtener la capa de barrios de los cuatro municipios y agregar los resultados."],
      ["Clima", "Sin datos suficientes", "Descargar CHIRPS y ERA5-Land mensuales; conteos mensuales por hexágono."],
      ["Socioeconómicas", "Pendiente", "Estrato, IPM y NBI por manzana (censo DANE 2018) agregados a hexágono."],
      ["Entomológicas", "Pendiente", "Índices de vivienda, recipiente, Breteau y ovitrampas por barrio y fecha."],
      ["Control vectorial", "Pendiente", "Registros de fumigación y control larvario; modelarlos con rezago."],
    ], [2300, 1900, 5440], { numDesde: 99 }),
  p("Con esos insumos, el paso siguiente es un modelo bayesiano espacio-temporal (Poisson o binomial negativo con efecto espacial BYM2, población como desplazamiento y covariables con rezago), que permitirá estimar la asociación de los clústeres con cada grupo de variables."),
];

const anexos = [
  new Paragraph({ children: [new PageBreak()] }),
  h1("Anexo A. Autocorrelación por municipio y año"),
  ...tabla("I de Moran y clústeres alto-alto por municipio y año, variante principal.",
    ["Municipio", "Año", "Casos", "I de Moran", "p", "Hex. alto-alto", "% casos alto-alto"],
    tablaAnual, [1700, 900, 1100, 1400, 1100, 1500, 1940], { numDesde: 2 }),
  h1("Anexo B. Reproducibilidad"),
  p("Los resultados se generan con los siguientes scripts del repositorio del observatorio:"),
  bullet([t("scripts/clusters_hexagonos.py", { font: "Consolas", size: 19 }), t(" — Moran, LISA, Gi*, persistencia y clima.")]),
  bullet([t("scripts/figuras_objetivo1.py", { font: "Consolas", size: 19 }), t(" — mapas y gráficos de este informe.")]),
  bullet([t("scripts/informe_word_objetivo1.js", { font: "Consolas", size: 19 }), t(" — este documento.")]),
  p(`Parámetros: ${META.permutaciones} permutaciones, semilla ${META.semilla}, α = ${String(META.alfa).replace(".", ",")}, componente urbano mínimo de ${META.componente_minimo_hexagonos} hexágonos, mínimo de ${META.min_casos_publicacion} casos para mostrar zonas o atípicos.`),
];

// ── Documento ────────────────────────────────────────────────────────────────
const doc = new Document({
  creator: "Observatorio GeoSalud",
  title: "Clústeres espaciales de dengue — Objetivo 1",
  description: "Autocorrelación espacial (Moran, LISA) y Gi* por hexágono de 200 m, 2019–2023",
  features: { updateFields: true },
  styles: {
    default: { document: { run: { font: FONT, size: 22, color: C_TXT } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 32, bold: true, color: C_TXT, font: FONT }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0, keepNext: true } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 25, bold: true, color: C_ACC, font: FONT }, paragraph: { spacing: { before: 260, after: 120 }, outlineLevel: 1, keepNext: true } },
    ],
  },
  numbering: { config: [{ reference: "vinetas", levels: [
    { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 540, hanging: 270 } } } },
    { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 1080, hanging: 270 } } } },
  ] }] },
  sections: [
    { properties: { page: { size: { width: W_PAGE, height: 15840 }, margin: { top: 1300, bottom: 1300, left: MARGIN, right: MARGIN } }, titlePage: true },
      headers: {
        default: new Header({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [t("Observatorio GeoSalud · Clústeres de dengue, Objetivo 1", { size: 16, color: C_SEC })] })] }),
        first: new Header({ children: [] }),
      },
      footers: {
        default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ children: [PageNumber.CURRENT], size: 18, color: C_SEC })] })] }),
        first: new Footer({ children: [] }),
      },
      children: [...portada, ...indice, ...resumen, ...intro, ...datos, ...metodos, ...resultados, ...discusion, ...limitaciones, ...conclusiones, ...anexos],
    },
  ],
});

Packer.toBuffer(doc).then((buf) => {
  fs.writeFileSync(SALIDA, buf);
  console.log(`Informe Word: ${SALIDA} (${Math.round(buf.length / 1024)} KB, ${nFig} figuras, ${nTab} tablas)`);
});
