const slides = [
  {
    kicker: "Innovacion territorial",
    title: "Laboratorio de Inteligencia Territorial",
    text: "Ciencia de datos geoespaciales para la gestion inteligente del territorio.",
    action: "Conoce el laboratorio",
    href: "#laboratorio",
    panelTitle: "Territorio conectado",
    panelCopy: "Mapas, modelos, sensores y observatorios."
  },
  {
    kicker: "Smart cities",
    title: "Territorios y ciudades inteligentes",
    text: "Analitica espacial, datos abiertos e innovacion para responder a los retos urbanos y regionales.",
    action: "Ver lineas estrategicas",
    href: "#lineas",
    panelTitle: "Ciudad inteligente",
    panelCopy: "Flujos, servicios, accesibilidad y gestion urbana."
  },
  {
    kicker: "GeoAI",
    title: "Inteligencia artificial geoespacial",
    text: "Modelos predictivos, percepcion remota y analisis territorial avanzado para la toma de decisiones.",
    action: "Explorar tecnologias",
    href: "#tecnologias",
    panelTitle: "Modelos predictivos",
    panelCopy: "IA aplicada a patrones, escenarios y alertas."
  },
  {
    kicker: "Observatorios inteligentes",
    title: "Plataformas de informacion territorial",
    text: "Observatorios para salud, turismo, movilidad, ambiente y desarrollo urbano.",
    action: "Ver proyectos",
    href: "#proyectos",
    panelTitle: "Observatorios vivos",
    panelCopy: "Indicadores, dashboards, geovisores y reportes."
  },
  {
    kicker: "Universidad y territorio",
    title: "Universidad, territorio e innovacion",
    text: "Un espacio academico para articular investigacion, formacion, extension y cooperacion institucional.",
    action: "Contactanos",
    href: "#contacto",
    panelTitle: "Cooperacion territorial",
    panelCopy: "Academia, instituciones, empresas y comunidades."
  }
];

const strategicLines = [
  ["IT", "Inteligencia Territorial y Analitica Espacial", "Lectura integrada de patrones, relaciones, brechas y dinamicas territoriales para apoyar decisiones."],
  ["CI", "Ciudades y Territorios Inteligentes", "Datos urbanos, servicios, movilidad, infraestructura y gestion inteligente de retos metropolitanos."],
  ["SP", "Salud y Vigilancia Epidemiologica Inteligente", "Observatorios de salud publica espacial, priorizacion de riesgo y seguimiento de eventos."],
  ["PR", "Percepcion Remota y Observacion de la Tierra", "Imagenes satelitales, drones y sensores para monitorear coberturas, ambiente y cambios del territorio."],
  ["DA", "Observatorios Inteligentes y Datos Abiertos", "Plataformas publicas con indicadores, geovisores, interoperabilidad, datos abiertos y reportes."],
  ["MP", "Modelado Predictivo Territorial", "Escenarios, alertas tempranas, pronosticos y modelos de apoyo para gestion publica y academica."]
];

const components = [
  ["Sala de analisis territorial y geovisores", "Espacio para lectura de mapas, tableros, indicadores y visualizacion territorial colaborativa."],
  ["Nodo de inteligencia artificial geoespacial", "Capacidad para modelos predictivos, aprendizaje automatico, simulaciones y analitica avanzada."],
  ["Unidad de percepcion remota y drones", "Captura, procesamiento e interpretacion de imagenes satelitales, sensores y vuelos territoriales."],
  ["Observatorio territorial universitario", "Sistema de seguimiento academico y publico a fenomenos urbanos, regionales, ambientales y sociales."],
  ["Plataforma de datos espaciales e interoperabilidad", "Repositorio de datos, servicios geograficos, APIs, estandares y flujos de actualizacion."]
];

const projects = [
  ["Observatorio Inteligente de Salud Publica", "salud", "Salud", "assets/sector-salud.svg", "Vigilancia epidemiologica, indicadores, mapas de riesgo, AEDE y modelos predictivos."],
  ["Observatorio de Turismo Inteligente", "ciudad", "Ciudad", "assets/sector-servicios.svg", "Flujos de visitantes, atractivos, accesibilidad, seguridad y oportunidades economicas."],
  ["Analitica de Movilidad Urbana", "ciudad", "Movilidad", "assets/sector-movilidad.svg", "Tiempos de viaje, siniestralidad, acceso a servicios y priorizacion de corredores."],
  ["Modelos Predictivos de Riesgo Territorial", "riesgo", "Riesgo", "assets/sector-riesgo.svg", "Amenaza, vulnerabilidad, exposicion, infraestructura critica y escenarios de respuesta."],
  ["Monitoreo Ambiental y Cambio Climatico", "ambiente", "Ambiente", "assets/sector-ambiente.svg", "Coberturas, calidad ambiental, sensores, percepcion remota y alertas regionales."],
  ["Gemelo Digital Territorial para Cali", "ciudad", "GeoAI", "assets/sector-agro.svg", "Modelo digital para integrar datos, simulacion, escenarios y gestion inteligente."]
];

const technologies = [
  "Python", "PostgreSQL/PostGIS", "QGIS", "ArcGIS Pro", "GeoServer", "Docker", "GitLab",
  "Google Earth Engine", "BigQuery", "Vertex AI", "Leaflet", "Folium", "APIs geoespaciales",
  "FHIR", "Drones", "Sensores", "Inteligencia Artificial"
];

const impacts = [
  [6, "", "lineas estrategicas"],
  [5, "", "componentes tecnologicos"],
  [6, "", "proyectos potenciales"],
  [10, "+", "aliados estrategicos"],
  [1, "", "plataforma de inteligencia territorial"],
  [3, "", "ejes misionales: investigacion, formacion y extension"]
];

const allies = [
  "Alcaldia de Cali", "Secretaria de Salud", "DATIC", "IDEAM", "INS", "Universidades",
  "Empresas de tecnologia", "Centros de investigacion", "Cooperacion internacional"
];

function byId(id) {
  return document.getElementById(id);
}

function renderContent() {
  const strategic = byId("strategic-lines");
  const componentGrid = byId("lab-components");
  const projectGrid = byId("project-grid");
  const techCloud = byId("tech-cloud");
  const impactGrid = byId("impact-grid");
  const alliesGrid = byId("allies-grid");

  if (strategic) {
    strategic.innerHTML = strategicLines.map(([icon, title, text]) => `
      <article class="line-card reveal visible">
        <span class="card-icon" aria-hidden="true">${icon}</span>
        <h3>${title}</h3>
        <p>${text}</p>
      </article>
    `).join("");
  }

  if (componentGrid) {
    componentGrid.innerHTML = components.map(([title, text], index) => `
      <article class="component-card reveal visible">
        <small>${String(index + 1).padStart(2, "0")}</small>
        <h3>${title}</h3>
        <p>${text}</p>
      </article>
    `).join("");
  }

  if (projectGrid) {
    projectGrid.innerHTML = projects.map(([title, category, label, image, text]) => `
      <article class="project-card reveal visible" data-category="${category}">
        <div class="project-media">
          <img src="${image}" alt="${title}">
          <span class="project-category">${label}</span>
        </div>
        <div class="project-body">
          <h3>${title}</h3>
          <p>${text}</p>
          <a href="#contacto">Ver mas</a>
        </div>
      </article>
    `).join("");
  }

  if (techCloud) {
    techCloud.innerHTML = technologies.map((tech) => `<span class="tech-chip reveal visible">${tech}</span>`).join("");
  }

  if (impactGrid) {
    impactGrid.innerHTML = impacts.map(([value, suffix, label]) => `
      <article class="impact-card reveal visible">
        <strong><span class="counter" data-target="${value}">${value}</span>${suffix}</strong>
        <span>${label}</span>
      </article>
    `).join("");
  }

  if (alliesGrid) {
    alliesGrid.innerHTML = allies.map((ally) => `
      <article class="ally-card reveal visible">
        <span class="ally-badge">${ally.slice(0, 2).toUpperCase()}</span>
        <div>
          <strong>${ally}</strong>
          <span>Aliado potencial</span>
        </div>
      </article>
    `).join("");
  }
}

function setSlide(index) {
  const slide = slides[index % slides.length];
  const fields = {
    "hero-kicker": slide.kicker,
    "hero-title": slide.title,
    "hero-text": slide.text,
    "hero-panel-title": slide.panelTitle,
    "hero-panel-copy": slide.panelCopy
  };
  Object.entries(fields).forEach(([id, value]) => {
    const element = byId(id);
    if (element) element.textContent = value;
  });
  const action = byId("hero-action");
  if (action) {
    action.textContent = slide.action;
    action.href = slide.href;
  }
  document.querySelectorAll(".slide-dot").forEach((dot) => {
    dot.classList.toggle("active", Number(dot.dataset.slide) === index % slides.length);
  });
}

function setupCarousel() {
  let current = 0;
  const progress = byId("hero-progress");
  document.querySelectorAll(".slide-dot").forEach((dot) => {
    dot.addEventListener("click", () => {
      current = Number(dot.dataset.slide);
      setSlide(current);
      if (progress) progress.style.width = "0%";
    });
  });
  window.setInterval(() => {
    current = (current + 1) % slides.length;
    setSlide(current);
    if (progress) progress.style.width = "100%";
    window.setTimeout(() => {
      if (progress) progress.style.width = "0%";
    }, 450);
  }, 6500);
}

function setupMenu() {
  const nav = document.querySelector(".main-nav");
  const toggle = document.querySelector(".menu-toggle");
  if (!nav || !toggle) return;
  toggle.addEventListener("click", () => {
    const open = nav.classList.toggle("open");
    toggle.setAttribute("aria-expanded", String(open));
  });
  nav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      nav.classList.remove("open");
      toggle.setAttribute("aria-expanded", "false");
    });
  });
}

function setupFilters() {
  const buttons = document.querySelectorAll(".filter-btn");
  buttons.forEach((button) => {
    button.addEventListener("click", () => {
      buttons.forEach((item) => item.classList.remove("active"));
      button.classList.add("active");
      const filter = button.dataset.filter;
      document.querySelectorAll(".project-card").forEach((card) => {
        const visible = filter === "todos" || card.dataset.category === filter;
        card.hidden = !visible;
      });
    });
  });
}

function setupContactForm() {
  const form = document.querySelector(".contact-form");
  if (!form) return;
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const button = form.querySelector("button");
    button.textContent = "Mensaje preparado";
    window.setTimeout(() => {
      button.textContent = "Enviar mensaje";
    }, 2200);
  });
}

function init() {
  try {
    renderContent();
    setupCarousel();
    setupMenu();
    setupFilters();
    setupContactForm();
    document.querySelectorAll(".reveal").forEach((item) => item.classList.add("visible"));
  } catch (error) {
    document.body.insertAdjacentHTML("afterbegin", `
      <div style="padding:16px;background:#fff3cd;color:#5b4300;font-family:system-ui">
        La pagina cargo con una advertencia de JavaScript. El contenido principal permanece disponible.
      </div>
    `);
  }
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
