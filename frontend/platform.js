const sectors = {
  salud: {
    kicker: "Salud publica",
    title: "Priorizar intervenciones con evidencia territorial.",
    copy: "Cruza casos, poblacion, equipamientos, movilidad y condiciones ambientales para identificar focos de riesgo y orientar acciones preventivas.",
    list: [
      "Deteccion de concentraciones espaciales.",
      "Priorizacion municipal y barrial.",
      "Seguimiento temporal de brotes e indicadores."
    ],
    color: "#1463ff",
    layers: 7,
    image: "assets/sector-salud.svg"
  },
  ambiente: {
    kicker: "Ambiente",
    title: "Monitorear presiones ambientales y cambios en el territorio.",
    copy: "Relaciona coberturas, fuentes hidricas, calidad ambiental, ocupacion del suelo y alertas tempranas para proteger ecosistemas y comunidades.",
    list: [
      "Seguimiento de deforestacion y cambios de cobertura.",
      "Identificacion de zonas criticas por contaminacion.",
      "Cruce entre amenazas ambientales y poblacion expuesta."
    ],
    color: "#2a9d66",
    layers: 9,
    image: "assets/sector-ambiente.svg"
  },
  riesgo: {
    kicker: "Gestion del riesgo",
    title: "Anticipar amenazas y focalizar capacidades de respuesta.",
    copy: "Integra amenaza, vulnerabilidad, exposicion, infraestructura critica y rutas de acceso para planear prevencion, preparacion y respuesta.",
    list: [
      "Mapas de exposicion ante inundacion, remocion o incendios.",
      "Escenarios de afectacion por municipio o zona.",
      "Rutas y nodos criticos para atencion."
    ],
    color: "#d04a3a",
    layers: 8,
    image: "assets/sector-riesgo.svg"
  },
  movilidad: {
    kicker: "Movilidad",
    title: "Entender flujos, accesibilidad y brechas de conexion.",
    copy: "Analiza redes, tiempos de viaje, demanda, siniestralidad y acceso a servicios para disenar intervenciones de movilidad con enfoque territorial.",
    list: [
      "Accesibilidad a equipamientos y servicios.",
      "Puntos criticos de siniestralidad vial.",
      "Priorizacion de corredores y conexiones."
    ],
    color: "#6c63b8",
    layers: 6,
    image: "assets/sector-movilidad.svg"
  },
  agro: {
    kicker: "Agro y ruralidad",
    title: "Planear productividad, asistencia tecnica y resiliencia rural.",
    copy: "Combina predios, cultivos, clima, suelos, infraestructura y mercados para orientar cadenas productivas y programas rurales.",
    list: [
      "Aptitud productiva y conflictos de uso.",
      "Seguimiento climatico y alertas para cultivos.",
      "Cobertura territorial de asistencia tecnica."
    ],
    color: "#c98b22",
    layers: 10,
    image: "assets/sector-agro.svg"
  },
  servicios: {
    kicker: "Servicios publicos",
    title: "Medir cobertura, calidad y expansion de redes.",
    copy: "Ordena redes, usuarios, calidad del servicio, expansion urbana y demanda futura para cerrar brechas de cobertura con criterios espaciales.",
    list: [
      "Cobertura y continuidad por zona.",
      "Priorizacion de expansion de redes.",
      "Analisis de demanda y poblacion no servida."
    ],
    color: "#0f9f9a",
    layers: 8,
    image: "assets/sector-servicios.svg"
  }
};

const buttons = document.querySelectorAll(".sector-btn");
const kicker = document.getElementById("sector-kicker");
const title = document.getElementById("sector-title");
const copy = document.getElementById("sector-copy");
const list = document.getElementById("sector-list");
const layerCount = document.getElementById("layer-count");
const sectorVisual = document.getElementById("sector-visual");
const sectorMap = document.querySelector(".sector-map");

buttons.forEach((button) => {
  button.addEventListener("click", () => {
    const data = sectors[button.dataset.sector];
    buttons.forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    kicker.textContent = data.kicker;
    title.textContent = data.title;
    copy.textContent = data.copy;
    layerCount.textContent = data.layers;
    document.documentElement.style.setProperty("--blue", data.color);
    list.innerHTML = data.list.map((item) => `<li>${item}</li>`).join("");
    if (sectorVisual && sectorMap) {
      sectorMap.classList.add("is-changing");
      window.setTimeout(() => {
        sectorVisual.src = data.image;
        sectorMap.classList.remove("is-changing");
      }, 120);
    }
  });
});

const canvas = document.getElementById("geo-scene");
const ctx = canvas.getContext("2d");
const points = Array.from({ length: 46 }, (_, index) => ({
  x: (index * 83) % 100,
  y: (index * 47) % 100,
  r: 1.5 + (index % 5) * 0.45,
  speed: 0.18 + (index % 7) * 0.025
}));

function resizeCanvas() {
  const ratio = window.devicePixelRatio || 1;
  canvas.width = Math.floor(canvas.offsetWidth * ratio);
  canvas.height = Math.floor(canvas.offsetHeight * ratio);
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
}

function drawScene(time = 0) {
  const width = canvas.offsetWidth;
  const height = canvas.offsetHeight;
  ctx.clearRect(0, 0, width, height);

  const terrain = ctx.createLinearGradient(0, 0, width, height);
  terrain.addColorStop(0, "#1b5f73");
  terrain.addColorStop(0.44, "#254f72");
  terrain.addColorStop(1, "#4f5f55");
  ctx.fillStyle = terrain;
  ctx.fillRect(0, 0, width, height);

  ctx.strokeStyle = "rgba(255,255,255,0.12)";
  ctx.lineWidth = 1;
  for (let i = -height; i < width; i += 48) {
    ctx.beginPath();
    ctx.moveTo(i, 0);
    ctx.lineTo(i + height, height);
    ctx.stroke();
  }
  for (let y = 70; y < height; y += 86) {
    ctx.beginPath();
    for (let x = 0; x <= width; x += 18) {
      const wave = Math.sin((x + time * 0.025) * 0.012 + y * 0.01) * 18;
      if (x === 0) ctx.moveTo(x, y + wave);
      else ctx.lineTo(x, y + wave);
    }
    ctx.stroke();
  }

  points.forEach((point, index) => {
    const drift = Math.sin(time * 0.001 * point.speed + index) * 12;
    point.sx = (point.x / 100) * width + drift;
    point.sy = (point.y / 100) * height + Math.cos(time * 0.001 * point.speed + index) * 10;
  });

  ctx.strokeStyle = "rgba(255,255,255,0.18)";
  points.forEach((a, index) => {
    const b = points[(index + 9) % points.length];
    const dx = a.sx - b.sx;
    const dy = a.sy - b.sy;
    if (Math.hypot(dx, dy) < 230) {
      ctx.beginPath();
      ctx.moveTo(a.sx, a.sy);
      ctx.lineTo(b.sx, b.sy);
      ctx.stroke();
    }
  });

  points.forEach((point, index) => {
    const palette = ["#8fe8d7", "#ffffff", "#f6c96e", "#ff9b8d"];
    ctx.beginPath();
    ctx.arc(point.sx, point.sy, point.r, 0, Math.PI * 2);
    ctx.fillStyle = palette[index % palette.length];
    ctx.fill();
  });

  requestAnimationFrame(drawScene);
}

window.addEventListener("resize", resizeCanvas);
resizeCanvas();
drawScene();
