# Chatbot ADK — Observatorio GeoSalud

Guía paso a paso para levantar el agente conversacional del Observatorio
basado en **Google Agent Development Kit (ADK)**, alineada con la
documentación oficial: <https://google.github.io/adk-docs/get-started/python/>.

El agente ya está implementado en `chatbot/observatorio_agent/`. Esta guía
cubre desde la instalación hasta la primera conversación.

---

## 1. Requisitos previos

| Requisito | Versión / Detalle |
|---|---|
| Python | 3.10 o superior |
| Acceso a la BD PostGIS del proyecto | `.env` raíz ya configurado con `DB_*` |
| API key de Google AI Studio | <https://aistudio.google.com/apikey> (gratuita) |
| Navegador moderno | Para la UI `adk web` |

> Si ya corres el resto del Observatorio (`scripts/run_all.py`, etc.) tienes
> Python y la conexión a PostgreSQL listos. Solo te falta la API key.

---

## 2. Instalar ADK en el entorno del proyecto

Desde la raíz del repositorio, con el venv activado:

```bash
pip install -r requirements.txt
```

Eso instala `google-adk` (ya añadido al `requirements.txt`). Para verificar:

```bash
adk --version
```

Si el comando no aparece, fuerza la instalación directa:

```bash
pip install --upgrade google-adk
```

---

## 3. Configurar la API key **sin exponerla**

El agente usa el patrón estándar de 12-Factor: la key vive en un archivo
`.env` local que **nunca** se sube al repo (ya está cubierto por
`.gitignore`).

### 3.1 Obtener la key

1. Entra a <https://aistudio.google.com/apikey>.
2. *Create API key* → copia el valor (formato `AIzaSy...`).

### 3.2 Crear el `.env` del agente

```bash
# Desde la raíz del repo
cp chatbot/observatorio_agent/.env.example chatbot/observatorio_agent/.env
```

Edita `chatbot/observatorio_agent/.env` y reemplaza el placeholder:

```env
GOOGLE_GENAI_USE_VERTEXAI=FALSE
GOOGLE_API_KEY=AIzaSy...tu_key_aqui
```

### 3.3 Buenas prácticas

- **Nunca** pegues la key en `agent.py`, `tools.py`, ni en notebooks.
- **Nunca** la subas a git ni a issues. El patrón `.env` del `.gitignore`
  ya la protege, pero si por error queda en un commit deberás:
  1. Revocarla en Google AI Studio (botón 🗑️ junto a la key).
  2. Generar una nueva.
  3. Reescribir la historia con `git filter-repo` o equivalente.
- En CI/producción, usa el secret manager de la plataforma
  (GitHub Secrets, Cloud Secret Manager, etc.) y exporta la variable
  `GOOGLE_API_KEY` en el entorno del runner — no leas un `.env`.
- Restringe la key en Google AI Studio a las APIs que usa ADK (Gemini API)
  para limitar el blast radius si se filtra.

---

## 4. Estructura del paquete

ADK descubre agentes por convención: cada carpeta-paquete dentro del
directorio donde se ejecuta `adk web` debe tener `agent.py` con un
`root_agent` y un `__init__.py` que importe `agent`.

```
chatbot/
└── observatorio_agent/
    ├── __init__.py        # re-exporta agent (convención ADK)
    ├── agent.py           # define root_agent (Gemini + tools)
    ├── tools.py           # 5 funciones que consultan PostGIS
    ├── .env.example       # plantilla — sí se versiona
    └── .env               # tu API key — NO se versiona
```

Las **tools** (`tools.py`) son funciones Python normales con type hints y
docstrings. ADK las inspecciona y se las describe al modelo Gemini, que
decide cuándo llamarlas.

| Tool | Para qué sirve |
|---|---|
| `listar_municipios()` | Devuelve los 42 municipios disponibles |
| `casos_por_municipio_anio(municipio, anio)` | Cifras puntuales |
| `top_municipios(anio, n, metrica)` | Ranking por casos o incidencia |
| `serie_temporal_municipio(municipio)` | Histórico 2019-2026 |
| `resumen_anio(anio)` | Foto agregada del Valle del Cauca |

---

## 5. Probar el agente

ADK ofrece tres formas de interactuar con `root_agent`. Elige la que
prefieras — todas leen el mismo paquete.

### 5.1 `adk web` — UI local con tracing (recomendado para iterar)

```bash
cd chatbot
adk web
```

Abre <http://localhost:8000> en el navegador. Vas a ver:

1. Un selector de agente (elige `observatorio_agent`).
2. Chat en vivo.
3. Panel **Trace** que muestra cada llamada a tool con sus argumentos
   y la respuesta JSON — ideal para depurar.

Prueba con prompts como:

- *"¿Cuántos casos tuvo Cali en 2024?"*
- *"Dame el top 5 de municipios por incidencia en 2023."*
- *"Muéstrame la evolución histórica de Palmira."*
- *"Resume el año 2024 a nivel departamental."*

### 5.2 `adk run` — chat por terminal

```bash
cd chatbot
adk run observatorio_agent
```

Útil cuando estás en una sesión SSH sin navegador.

### 5.3 `adk api_server` — endpoint REST

```bash
cd chatbot
adk api_server
```

Levanta una API en `http://localhost:8000` con endpoints estilo
`/run`, `/run_sse` (streaming) y `/list-apps`. Esta es la base si en el
futuro quieres conectar el chatbot al frontend Leaflet del Observatorio.

---

## 6. Cómo funciona internamente

1. El usuario escribe una pregunta.
2. ADK construye el prompt con: instrucciones del agente + esquemas de
   las tools (extraídos de docstring + type hints) + historial.
3. Gemini decide si responder directo o invocar una tool.
4. Si invoca, ADK ejecuta la función Python — que abre el engine
   PostGIS vía `src.db.crear_engine()` y consulta `valle_mun`.
5. El resultado JSON vuelve al modelo, que lo redacta en español.

```
Usuario  ──prompt──▶  Gemini ──tool_call──▶  tools.py ──SQL──▶  PostGIS
                       ▲                                             │
                       └────────── JSON con resultados ◀─────────────┘
                       │
                       └── responde al usuario en español
```

---

## 7. Troubleshooting

| Síntoma | Causa probable | Solución |
|---|---|---|
| `adk: command not found` | google-adk no instalado en el venv activo | `pip install --upgrade google-adk` |
| `PermissionDenied: API key not valid` | `.env` mal escrito o key revocada | Revisa `chatbot/observatorio_agent/.env`, regenera la key |
| `ModuleNotFoundError: src` | Estás corriendo desde otra carpeta | Ejecuta `adk web` desde `chatbot/`, no desde la raíz |
| `psycopg2.OperationalError` | Variables `DB_*` mal en el `.env` raíz | Verifica con `python scripts/verificar_conexion.py` |
| El agente "inventa" números | Las tools no se están llamando | Mira el panel Trace de `adk web`; revisa que las docstrings sean claras |

---

## 8. Hoja de ruta — mejoras incrementales

Cada paso mapea a una sección de la guía oficial de ADK y agrega una
capacidad nueva al chatbot del Observatorio. Marcamos `[x]` los que ya
están implementados.

### Fase A — Calidad conversacional

- [x] **Paso 1 — Session & State** (sección 9 de este doc).
  Memoria turno-a-turno: `last_municipio`, `last_anio`,
  `metrica_preferida`. Doc oficial:
  <https://google.github.io/adk-docs/sessions/>
- [ ] **Paso 2 — Memoria de preferencias cross-sesión.**
  `MemoryService` para que las preferencias persistan entre sesiones.

### Fase B — Más capacidades

- [x] **Paso 3 — Tool de visualización** (sección 10 de este doc).
  Cuatro tools `grafica_*` que generan PNG y los entregan como
  ADK Artifacts. Doc oficial:
  <https://google.github.io/adk-docs/artifacts/>
- [ ] **Paso 4 — Tool de mapas Leaflet** (HTML como artifact).
- [ ] **Paso 5 — Tool de forecast NeuralProphet** como
  `LongRunningFunctionTool`.

### Fase C — Orquestación multi-agente

- [ ] **Paso 6 — sub_agents especializados.** `consulta_agent`,
  `viz_agent`, `forecast_agent`. Doc oficial:
  <https://google.github.io/adk-docs/agents/multi-agents/>
- [ ] **Paso 7 — `SequentialAgent` para informes mensuales.**

### Fase D — Robustez y producción

- [ ] **Paso 8 — Evaluación con `adk eval`.**
- [ ] **Paso 9 — Streaming + integración al frontend Leaflet.**
- [ ] **Paso 10 — Despliegue (Cloud Run / Vertex AI Agent Engine).**

---

## 9. Paso 1 — Session & State *(implementado)*

ADK distingue tres conceptos que conviene tener claros:

| Concepto | Vida útil | Para qué |
|---|---|---|
| **Session** | Una conversación (multiples turnos). Identificada por `session_id`. | Agrupa todos los `events` de un usuario hablando con el agente. |
| **State** | Atado a una `Session`. Es un dict que sobrevive entre turnos. | Variables de la conversación: último municipio, preferencias, contadores… |
| **Memory** | Cross-sesión. Persistencia a largo plazo. | "Recordar al usuario" entre sesiones (queda para el Paso 2). |

### 9.1 Qué se guarda en state

`tools.py` define tres claves canónicas:

| Clave | Tipo | Quién la escribe |
|---|---|---|
| `last_municipio` | `str` | Toda tool que recibe un municipio (al final, si tuvo éxito). |
| `last_anio` | `int` | Toda tool que recibe un año. |
| `metrica_preferida` | `"casos"` \| `"incidencia"` | Solo `establecer_preferencia`. |

Las tools acceden vía `tool_context.state`, que ADK inyecta cuando
declaras el parámetro `tool_context: ToolContext` en tu firma.

### 9.2 Tools nuevas

| Tool | Para qué |
|---|---|
| `mostrar_contexto()` | Devuelve el state actual. Útil para *"¿qué estábamos viendo?"* o para depurar. |
| `establecer_preferencia(metrica_default)` | Fija `state.metrica_preferida`. |

`top_municipios` ahora respeta `state.metrica_preferida` cuando el usuario
no especifica métrica explícitamente.

### 9.3 Cómo el agente lo aprovecha

Las **reglas 7-9** del prompt del agente (en `agent.py`) le indican:

- Reutilizar `state.last_*` cuando la pregunta sea ambigua *(ej. "y Palmira?")*.
- Llamar a `establecer_preferencia` cuando el usuario exprese una
  preferencia explícita.
- Llamar a `mostrar_contexto` cuando el usuario pregunte por la conversación.

### 9.4 Cómo probarlo

Reinicia `adk web`:

```powershell
cd E:\observatorio_geosalud\chatbot
adk web
```

Conversación de prueba (todo en la misma sesión):

```
Tú:    ¿Cuántos casos tuvo Cali en 2024?
Bot:   En 2024, Cali tuvo 38.590 casos…  [tool: casos_por_municipio_anio]

Tú:    ¿Y Palmira?
Bot:   En 2024, Palmira tuvo …           [tool: casos_por_municipio_anio
                                          municipio="PALMIRA", anio=2024 ← de state]

Tú:    Prefiero ver siempre incidencia, no casos absolutos.
Bot:   Listo, ahora reportaré por defecto en incidencia.
                                          [tool: establecer_preferencia]

Tú:    Dame el top 5 de 2023.
Bot:   [usa metrica="incidencia" automáticamente desde state]

Tú:    ¿Qué estábamos viendo?
Bot:   Hablamos de Palmira en 2024, métrica preferida: incidencia.
                                          [tool: mostrar_contexto]
```

En la pestaña **State** de `adk web` puedes ver el dict en tiempo real.
En el panel **Events** verás `function_call` con los args resueltos
desde state.

### 9.5 Persistencia entre reinicios del servidor

Por defecto, `adk web` usa `InMemorySessionService`: el state se pierde
si reinicias el proceso. Para que sobreviva entre reinicios, pasa una
URL de base de datos al lanzar:

```powershell
adk web --session_db_url=sqlite:///./adk_sessions.db
```

Esto crea `adk_sessions.db` en `chatbot/` y guarda sesiones+state en SQLite.
Para pasar a producción, usa `postgresql://...` con la misma BD del
Observatorio.

### 9.6 Notas de diseño

- **Las tools no leen state como "default" automáticamente.** Es el LLM
  quien resuelve los argumentos a partir del historial + las reglas 7-9.
  State sirve como *fuente de verdad* y para que tools como
  `top_municipios` consulten preferencias sin que el modelo tenga que
  pasarlas en cada llamada.
- **El log persistente** (`outputs/adk_tool_calls.log`) sigue funcionando
  e incluye ahora `invocation_id`, lo que permite reconstruir
  conversaciones completas con `pandas.read_json(..., lines=True)`.

---

## 10. Paso 3 — Visualización con Artifacts *(implementado)*

ADK tiene un mecanismo nativo para que las tools devuelvan archivos
binarios (imágenes, PDFs, audio…) que la UI muestra inline al usuario:
los **Artifacts**.

### 11.1 Cómo funciona el flujo

```
Usuario  ──"grafica casos 2024"──▶  Gemini decide: grafica_top_municipios
                                                  │
                                                  ▼
       src/db.cargar_datos() ─────────▶ DataFrame con datos PostGIS
                                                  │
                                                  ▼
       src/viz.graficar_top_municipios(...) ──▶ matplotlib Figure
                                                  │
                                                  ▼
       fig.savefig(BytesIO, format="png") ───▶ PNG bytes
                                                  │
                                                  ▼
       tool_context.save_artifact(filename, Part) ─▶ Artifact registrado
                                                  │
                                                  ▼
       UI de adk web ──> pestaña "Artifacts" muestra el PNG inline
```

La conversión a Artifact se hace con la API estándar de ADK:

```python
from google.genai import types as genai_types

png_bytes = ...  # bytes generados por matplotlib
part = genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png")
version = await tool_context.save_artifact(filename="top10_2024.png", artifact=part)
```

> Las tools de visualización son **async** porque `save_artifact` es
> coroutine. ADK las soporta de forma nativa.

### 11.2 Tools disponibles

Las cuatro viven en `chatbot/observatorio_agent/viz_tools.py`:

| Tool | Cuándo se invoca |
|---|---|
| `grafica_casos_por_anio()` | "evolución general", "tendencia anual del Valle". |
| `grafica_top_municipios(anio, n=10, metrica="")` | "top en gráfica", "ranking visual de 2024". Respeta `state.metrica_preferida`. |
| `grafica_serie_municipio(municipio)` | "evolución de Cali", "histórico de Palmira en gráfica". |
| `grafica_poblacion_vs_incidencia(anio)` | Scatter pob vs incidencia, exploración de correlación. |

### 11.3 Cómo verlas en `adk web`

1. Abre la UI: `adk web` desde `chatbot/`.
2. Pregunta algo visual: *"Muéstrame en gráfica el top 10 de 2024"*.
3. En el lateral izquierdo cambia a la pestaña **Artifacts**.
4. Verás el PNG renderizado inline, con su nombre y versión.
5. Click derecho → *"Save image as…"* para descargarlo.

### 11.4 Conversación de prueba

```
Tú:    Muéstrame en gráfica la evolución general de dengue en el Valle.
Bot:   [grafica_casos_por_anio()]
       Generé la gráfica con la tendencia 2019-2026. La puedes ver en
       el panel Artifacts. Si quieres, también puedo darte el detalle
       numérico por año.

Tú:    Ahora compara visualmente los 8 municipios más afectados de 2024.
Bot:   [grafica_top_municipios(anio=2024, n=8)]
       Listo, ahí tienes el top 8 por casos en 2024. Cali domina con
       diferencia, seguido por Palmira y Buenaventura.

Tú:    Y la evolución de Buenaventura?
Bot:   [grafica_serie_municipio(municipio="BUENAVENTURA")]   ← state activado
       Buenaventura muestra un pico en 2020 y otro mayor en 2024.
```

### 11.5 Notas de diseño

- **Filename con timestamp**: cada tool agrega sufijo `YYYYMMDD_HHMMSS`
  para que invocaciones repetidas no se sobreescriban; `adk web` te
  deja ver versiones anteriores.
- **`matplotlib.use("Agg")`** al inicio del módulo → backend sin display.
  Importante porque `adk web` corre headless.
- **`plt.close(fig)`** después de cada `savefig` para liberar memoria —
  con muchas gráficas en una sesión larga se acumula rápido.
- **State integrado**: `grafica_serie_municipio` también escribe
  `state.last_municipio`, así que si después preguntas *"y los casos
  exactos?"*, el agente reutiliza el municipio.

---

## 11. Manejo de rate limits (`429 RESOURCE_EXHAUSTED`)

Si ves un error como:

```
429 RESOURCE_EXHAUSTED. Quota exceeded for metric:
generativelanguage.googleapis.com/generate_content_free_tier_requests,
limit: 20, model: gemini-2.5-flash
```

estás topando la cuota **diaria** del Free Tier. El campo `retryDelay`
(ej. *"retry in 46s"*) es engañoso para cuotas diarias: en la práctica
no recuperas presupuesto hasta el reset a medianoche **hora Pacífico**.

### 10.1 Cuotas Free Tier por modelo

Datos según la documentación oficial
(<https://ai.google.dev/gemini-api/docs/rate-limits>) — pueden cambiar:

| Modelo | RPD (Free) | RPM (Free) | Recomendado para |
|---|---:|---:|---|
| `gemini-2.5-flash-lite` | **1.000** | 15 | **Desarrollo** ← default del proyecto |
| `gemini-2.5-flash` | 20 | 5 | Sólo con billing activado |
| `gemini-2.5-pro` | 50 | 5 | Razonamiento complejo (multi-agente) |

Una pregunta del usuario puede generar 2-4 requests al modelo
(decisión inicial → posiblemente otra ronda con resultado de tool →
respuesta final). 20 RPD se acaban con ~6-8 preguntas.

### 10.2 Cambiar de modelo (sin tocar código)

El proyecto ya tiene el modelo parametrizado por env. Edita
`chatbot/observatorio_agent/.env`:

```env
GEMINI_MODEL=gemini-2.5-flash-lite
```

Reinicia `adk web` y listo.

### 10.3 Estrategias de mitigación, en orden

1. **Cambiar a `flash-lite`** *(ya aplicado como default)*. 50× más
   capacidad gratuita, calidad muy similar para tareas estructuradas
   como las de este chatbot.
2. **Habilitar billing → Tier 1.** En
   <https://aistudio.google.com/apikey> botón *"Set up billing"*.
   Solo por activarlo (sin cargo si no superas el free) suben las
   cuotas a niveles de producción (ej. 10.000+ RPD en flash).
3. **Reducir requests por turno.** Cada tool extra que invoque el
   agente es 1 request adicional. Mantén las instrucciones del agente
   concisas y evita que pida 3 tools cuando 1 alcanza.
4. **Batching/caching para evaluación.** Cuando corras `adk eval` con
   muchas preguntas, fija un `--max-concurrency=1` y considera
   cachear respuestas en disco.
5. **Modelo alternativo vía LiteLLM.** Si te cierran completamente,
   ADK soporta Claude/OpenAI vía LiteLLM. Cambias el `model=...` a
   `LiteLlm("anthropic/claude-haiku-...")` y usas tu API key de otro
   proveedor. (Documentado en la guía oficial,
   <https://google.github.io/adk-docs/agents/models/#using-cloud--proprietary-models-via-litellm>.)

### 10.4 Monitoreo

- Tu uso actual: <https://ai.dev/rate-limit>
- Cuando habilites billing: GCP Console → APIs & Services → Generative
  Language API → Quotas.

---

## Referencias

- Quickstart oficial: <https://google.github.io/adk-docs/get-started/python/>
- Tools personalizadas: <https://google.github.io/adk-docs/tools/function-tools/>
- Sessions, State, Memory: <https://google.github.io/adk-docs/sessions/>
- Multi-agent systems: <https://google.github.io/adk-docs/agents/multi-agents/>
- Rate limits: <https://google.github.io/adk-docs/agents/models/google-gemini/#error-code-429-resource_exhausted>
- Repo público: <https://github.com/google/adk-python>
