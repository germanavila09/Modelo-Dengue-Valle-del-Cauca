# Observatorio GeoSalud — Asistente Epidemiológico con ADK

> **Sistema multiagente de vigilancia epidemiológica de dengue en el Valle del Cauca** (42 municipios · 2019–2026) construido sobre Google Agent Development Kit (ADK) y Gemini.

---

## ¿Qué es?

El **Observatorio GeoSalud** es un dashboard epidemiológico interactivo que integra un agente de IA conversacional para responder preguntas en lenguaje natural sobre dengue en el departamento del Valle del Cauca, Colombia. El usuario puede pedir datos, visualizaciones y navegar la interfaz usando el chat — sin necesidad de conocer filtros o menús.

**Casos de uso reales:**
- *"¿Cuáles fueron los 10 municipios con mayor incidencia en 2023?"*
- *"Muéstrame la serie histórica de Palmira y Tuluá comparadas"*
- *"Abre el mapa coroplético de casos para 2024 sin Cali"*
- *"¿Cómo está la población por ciclo de vida en Buga?"*

---

## Arquitectura multiagente (ADK)

```
┌───────────────────────────────────────────────────────────────────────┐
│                         FRONTEND  (HTML + Leaflet.js)                 │
│  Dashboard · Mapa coroplético · Geovisor · Tendencias · Demografía   │
└──────────────────────────────────┬────────────────────────────────────┘
                                   │ HTTP POST /chat
                                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│                    FASTAPI  chatbot/server.py                         │
│                                                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │          CAPA LOCAL (sin Gemini, cero latencia)                 │  │
│  │  • Fuzzy matching de municipios (difflib)                       │  │
│  │  • Extracción de año, top-N y métricas con regex               │  │
│  │  • Respuestas directas a BD y generación de gráficas           │  │
│  │  • Action chaining: datos + navegación en un mismo turno       │  │
│  └────────────────────────────┬────────────────────────────────────┘  │
│                               │ si no resuelve localmente             │
│                               ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │               CAPA ADK  (Google ADK + Gemini)                  │  │
│  │                                                                 │  │
│  │   ┌──────────────────────────────────────────────────────┐     │  │
│  │   │         observatorio_orchestrator  (root_agent)      │     │  │
│  │   │  Enruta solicitudes al subagente especializado.      │     │  │
│  │   └──────────┬──────────────────┬────────────────┬───────┘     │  │
│  │              │                  │                │             │  │
│  │   ┌──────────▼───┐   ┌──────────▼────┐   ┌──────▼─────────┐  │  │
│  │   │ epidemio_    │   │   viz_agent   │   │   ui_agent     │  │  │
│  │   │   agent      │   │               │   │                │  │  │
│  │   │ ─────────    │   │ ─────────     │   │ ─────────      │  │  │
│  │   │ Datos        │   │ Gráficas PNG  │   │ Navegar        │  │  │
│  │   │ numéricos    │   │ ADK Artifacts │   │ módulos,       │  │  │
│  │   │ Demografía   │   │ (seaborn/     │   │ mapas y        │  │  │
│  │   │ Rankings     │   │  matplotlib)  │   │ variables      │  │  │
│  │   │ Series       │   │               │   │                │  │  │
│  │   └──────────┬───┘   └──────────┬────┘   └──────┬─────────┘  │  │
│  │              │                  │                │             │  │
│  │   ┌──────────▼──────────────────▼────────────────▼──────────┐  │  │
│  │   │              TOOLS (FunctionTools ADK)                   │  │  │
│  │   │  listar_municipios · casos_por_municipio_anio           │  │  │
│  │   │  top_municipios · serie_temporal_municipio              │  │  │
│  │   │  resumen_anio · consultar_poblacion_municipio           │  │  │
│  │   │  consultar_poblacion_ciclo_vida · consultar_piramide    │  │  │
│  │   │  graficar_top_n · graficar_serie · mostrar_geovisor     │  │  │
│  │   │  mostrar_mapa_coropletico · abrir_modulo_observatorio   │  │  │
│  │   └──────────────────────────────┬───────────────────────────┘  │  │
│  │                                  │                               │  │
│  │   ┌──────────────────────────────▼───────────────────────────┐  │  │
│  │   │         before_tool_callback / after_tool_callback       │  │  │
│  │   │         InMemorySessionService · InMemoryArtifactService │  │  │
│  │   └──────────────────────────────────────────────────────────┘  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────────────────┘
                                   │ SQL (SQLAlchemy + psycopg2)
                                   ▼
┌───────────────────────────────────────────────────────────────────────┐
│                  PostgreSQL / PostGIS  (terrarIA.valle_mun)           │
│         42 municipios · 2019–2026 · casos · incidencia · geom        │
└───────────────────────────────────────────────────────────────────────┘
```

---

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| LLM & Agentes | Google ADK · Gemini 2.5 Flash |
| API backend | FastAPI + Uvicorn |
| Base de datos | PostgreSQL 13+ · PostGIS · SQLAlchemy |
| Datos espaciales | GeoPandas · Shapely |
| Visualización | Matplotlib · Seaborn |
| Frontend | HTML5 · Leaflet.js · JavaScript |
| ML / Pronósticos | NeuralProphet · PyTorch |
| Testing | Pytest |
| Gestión de entorno | pip / uv · python-dotenv |

---

## Componentes ADK utilizados

| Componente ADK | Uso en el proyecto |
|----------------|-------------------|
| `google.adk.agents.Agent` | Orquestador + 3 subagentes especializados |
| `sub_agents` | Delegación a epidemio_agent, viz_agent, ui_agent |
| `google.adk.tools.ToolContext` | Lectura/escritura de `state` entre turnos |
| `before_tool_callback` | Validación y enriquecimiento antes de cada tool |
| `after_tool_callback` | Logging y post-procesamiento de resultados |
| `InMemorySessionService` | Persistencia de contexto dentro de la sesión |
| `InMemoryArtifactService` | Almacenamiento y servicio de PNG generados |
| `google.adk.runners.Runner` | Ejecución asíncrona del agente |
| `google.genai.types.Content` | Construcción de mensajes usuario/modelo |

---

## Subagentes especializados

### `epidemio_agent`
Responde consultas numéricas y demográficas. Usa 10 tools conectadas a la BD.

**Tools:**
- `listar_municipios` — catálogo de los 42 municipios
- `casos_por_municipio_anio` — casos e incidencia puntuales
- `top_municipios` — ranking por casos o incidencia
- `serie_temporal_municipio` — evolución histórica 2019–2026
- `resumen_anio` — panorama departamental de un año
- `consultar_poblacion_municipio` — población total, hombres y mujeres
- `consultar_poblacion_ciclo_vida` — distribución por etapa de vida
- `consultar_piramide_poblacional` — grupos quinquenales
- `establecer_preferencia` — configura métrica por defecto (casos/incidencia)
- `mostrar_contexto` — recupera el contexto de la sesión actual

### `viz_agent`
Genera imágenes PNG como ADK Artifacts. Implementa caché determinista para evitar regenerar gráficas idénticas.

**Tools:**
- `graficar_top_n` — barras horizontales top-N municipios
- `graficar_top_n_incidencia` — por tasa por 100.000 hab.
- `graficar_serie_municipio` — línea temporal de un municipio
- `graficar_scatter_poblacion_incidencia` — scatter bivariate

### `ui_agent`
Controla el dashboard desde el chat. Emite acciones JSON que el frontend interpreta.

**Tools:**
- `mostrar_mapa_coropletico` — variable, año, incluir/excluir Cali
- `mostrar_geovisor` — modo burbujas / calor / coroplético
- `abrir_modulo_observatorio` — navegar a Panel, Indicadores, Tendencias, Demografía, Priorización

---

## Técnicas de ingeniería de prompts

Cada subagente tiene instrucciones diseñadas para guiar el comportamiento del LLM de forma precisa y controlada:

1. **Tabla de enrutamiento explícita** en el orquestador: mapea la intención del usuario al subagente correcto sin ambigüedad.
2. **Reglas de uso de tools con ejemplos** en cada agente: el LLM sabe exactamente cuándo invocar cada función.
3. **Memoria de sesión documentada**: las instrucciones describen las claves del `state` (`last_municipio`, `last_anio`, `metrica_preferida`) para que el LLM las use en referencias implícitas.
4. **Regla de no alucinación explícita**: "Nunca inventes cifras. Usa siempre una tool para datos numéricos."
5. **Respuesta estructurada por tipo de dato**: instrucciones distintas para población, incidencia, pirámide, etc.

---

## Características de implementación

### Sistema de respuesta híbrido
El servidor resuelve **primero en local** (sin llamar a Gemini) las consultas más frecuentes: top municipios, series temporales, casos puntuales, resúmenes anuales, y todas las acciones de UI. Solo las preguntas complejas o de lenguaje libre escalan al agente ADK.

**Beneficios:**
- Latencia ~0ms para consultas estructuradas
- Tolerancia a errores de cuota de Gemini
- Funciona en modo degradado sin API key

### Fuzzy matching de municipios
El preprocesamiento normaliza nombres con tildes, aliases comunes (`Buga` → `GUADALAJARA DE BUGA`), y usa `difflib.get_close_matches` para corregir errores ortográficos antes de consultar la BD.

### Action chaining
Una sola pregunta puede producir múltiples acciones. El servidor separa la intención de navegación de la intención de datos y emite ambas acciones en la misma respuesta.
```json
// "Muéstrame los datos de Cali 2024 y abre tendencias"
{ "reply": "...", "actions": [{"type": "navigate", "section": "tendencias"}, ...] }
```

### Persistencia de contexto conversacional
El `local_context` y `session.state` del ADK se sincronizan bidireccionalmente en cada turno, permitiendo referencias implícitas:
```
Usuario: "¿Cuántos casos tuvo Cali en 2024?"
→ state: { last_municipio: "CALI", last_anio: 2024 }

Usuario: "¿Y en 2023?"
→ Usa state.last_municipio sin necesidad de repetir "Cali"
```

### Caché de artifacts
Los PNG generados se indexan con nombres deterministas (`top10_incidencia_2024.png`). Si el mismo gráfico se solicita de nuevo, se sirve desde caché sin regenerar.

---

## Estructura del repositorio

```
observatorio_geosalud/
├── chatbot/                        # Agente ADK + API
│   ├── server.py                  # FastAPI + capa local + runner ADK
│   └── observatorio_agent/
│       ├── agent.py               # root_agent (orquestador)
│       ├── agents/
│       │   ├── epidemio_agent.py  # Subagente numérico / demográfico
│       │   ├── viz_agent.py       # Subagente de visualización
│       │   └── ui_agent.py        # Subagente de interfaz
│       ├── tools.py               # Tools epidemiológicas (BD)
│       ├── viz_tools.py           # Tools de gráficas (ADK Artifacts)
│       ├── ui_tools.py            # Tools de UI (acciones JSON)
│       ├── ui_actions.py          # Constructores de acciones frontend
│       └── callbacks.py           # before_tool / after_tool callbacks
│
├── src/                           # Pipeline de datos
│   ├── config.py                  # Variables de entorno
│   ├── db.py                      # Conexión PostGIS
│   ├── transform.py               # Limpieza y priorización
│   ├── viz.py                     # Gráficas matplotlib
│   ├── mapa.py                    # Mapa HTML Leaflet
│   ├── modelo.py                  # NeuralProphet forecasting
│   └── pipeline.py                # Orquestación completa
│
├── frontend/                      # Dashboard HTML + JS
│   ├── Geodata Salud.html         # Dashboard principal (Leaflet)
│   ├── geodata-app.js             # Lógica del dashboard
│   └── geodata-data.js            # Datos precalculados para JS
│
├── scripts/                       # Scripts de ejecución
│   ├── run_all.py                 # Pipeline completo
│   └── verificar_conexion.py      # Check de BD
│
├── tests/                         # Tests unitarios
│   ├── test_db.py
│   ├── test_transform.py
│   └── test_pipeline.py
│
├── docs/                          # Documentación técnica
│   ├── ARCHITECTURE.md
│   ├── SETUP.md
│   └── API.md
│
├── notebooks/                     # Análisis exploratorio
│   └── analisis_dengue.ipynb
│
├── .env                           # Credenciales (no en git)
├── .env.example                   # Template
├── requirements.txt
├── pyproject.toml
└── README.md
```

---

## Instalación y arranque

### Prerrequisitos
- Python 3.10+
- PostgreSQL 13+ con PostGIS y datos en `public.valle_mun`
- API Key de Google AI Studio ([aistudio.google.com/apikey](https://aistudio.google.com/apikey))

### 1. Clonar y configurar

```bash
git clone <repo-url>
cd observatorio_geosalud
cp .env.example .env
```

### 2. Variables de entorno (`.env`)

```env
# Base de datos
DB_HOST=localhost
DB_PORT=5432
DB_NAME=terrarIA
DB_USER=postgres
DB_PASSWORD=tu_contraseña
DB_SCHEMA=public
DB_TABLE=valle_mun

# Gemini
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=tu_api_key_aqui
GEMINI_MODEL=gemini-2.5-flash

# Servidor
CHATBOT_PORT=8080
```

### 3. Instalar dependencias

```bash
# Con pip
pip install -r requirements.txt

# Con uv (recomendado)
uv sync
```

### 4. Verificar conexión a BD

```bash
python scripts/verificar_conexion.py
```

### 5. Levantar el servidor

```bash
cd chatbot
uvicorn server:app --host 0.0.0.0 --port 8080 --reload
```

El servidor queda disponible en:
- API: `http://localhost:8080`
- Docs interactivos: `http://localhost:8080/docs`
- Health check: `http://localhost:8080/health`

### 6. Abrir el dashboard

Abre `frontend/Geodata Salud.html` en el navegador. El chat en la esquina inferior derecha conecta al servidor automáticamente.

---

## API Reference

### `POST /chat`

```json
// Request
{ "session_id": "abc123", "message": "Top 5 municipios con más casos en 2024" }

// Response
{
  "reply": "Los 5 municipios con más casos en 2024 fueron:\n1. Cali: 4.823 casos\n...",
  "artifacts": ["top5_casos_2024.png"],
  "session_id": "abc123",
  "actions": [{ "type": "show_top", "anio": 2024, "metrica": "casos" }]
}
```

### `GET /artifacts/{filename}?session_id=...`

Sirve las imágenes PNG generadas por el agente como ADK Artifacts.

### `GET /health`

```json
{ "status": "ok", "agent": "observatorio_orchestrator", "app": "observatorio_geosalud" }
```

---

## Esquema de BD requerido

```sql
CREATE TABLE public.valle_mun (
    MPIO_CCDGO        text,
    MPIO_CNMBR        text,
    "año"             integer,
    "población"       bigint,
    conteo_dengue     integer,
    incidencia_dengue numeric,
    geom              geometry(MultiPolygon, 3857)
);

-- Índices
CREATE INDEX idx_valle_mun_nombre ON public.valle_mun(MPIO_CNMBR);
CREATE INDEX idx_valle_mun_anio   ON public.valle_mun("año");
CREATE INDEX idx_valle_mun_geom   ON public.valle_mun USING GIST(geom);
```

Cobertura: **42 municipios** · **2019–2026** · **+166.000 casos registrados**

---

## Tests

```bash
# Todos los tests
pytest

# Con coverage
pytest --cov=src --cov-report=term-missing

# Solo tests de transformación
pytest tests/test_transform.py -v
```

---

## Troubleshooting

**`No es posible conectar con el servidor remoto`**
→ El servidor no está corriendo. Ejecuta: `uvicorn server:app --port 8080 --reload` desde `chatbot/`.

**`GOOGLE_API_KEY not set`**
→ El agente corre en modo local (solo BD). Para activar Gemini, agrega la key en `.env`.

**`No module named 'psycopg2'`**
```bash
pip install psycopg2-binary
```

**`No se encontró la columna de año`**
→ La columna en tu BD puede llamarse `año`, `aÃ±o` o `anio`. El servidor detecta automáticamente las tres variantes.

---

## Créditos

Desarrollado por **Germán Ávila** como proyecto del **Curso ADK - Fundamentos de IA (T26475)**.

Datos de dengue: SIVIGILA / Secretaría de Salud del Valle del Cauca.  
Cartografía: DANE — Marco Geoestadístico Nacional.
