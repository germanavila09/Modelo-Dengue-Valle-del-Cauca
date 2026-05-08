"""Servidor FastAPI — puente entre el frontend GeoSalud y el agente ADK.

Expone dos endpoints:

  POST /chat
      Recibe { session_id, message } y devuelve { reply, artifacts }.

  GET  /artifacts/{filename}?session_id=...
      Sirve el PNG guardado como ADK Artifact en la sesión.

  GET  /health
      Estado del servidor.

Arranque:
    cd observatorio_geosalud/chatbot
    uvicorn server:app --host 0.0.0.0 --port 8080 --reload

El frontend llama a http://localhost:8080 (configurable con la variable
CHATBOT_PORT en .env).
"""

from __future__ import annotations

import io
import os
import re
import sys
import unicodedata
from pathlib import Path

# ── sys.path: permite importar observatorio_agent y src.* ─────────────────────
_CHATBOT_DIR = Path(__file__).resolve().parent          # .../chatbot/
_PROJECT_ROOT = _CHATBOT_DIR.parent                     # .../observatorio_geosalud/

for _p in (_CHATBOT_DIR, _PROJECT_ROOT):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

# ── Imports externos ───────────────────────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv(_PROJECT_ROOT / ".env")
load_dotenv(_CHATBOT_DIR / "observatorio_agent" / ".env", override=False)

from fastapi import FastAPI, Response, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.artifacts import InMemoryArtifactService
from google.genai import types as genai_types

import matplotlib.pyplot as plt

from src.db import cargar_datos
from src.viz import graficar_top_municipios, graficar_top_municipios_incidencia

# ── Agente raíz (importado DESPUÉS de ajustar sys.path) ───────────────────────
from observatorio_agent.agent import root_agent
from observatorio_agent.ui_actions import coropletico_action, geovisor_action, navigate_action

# ── Constantes ─────────────────────────────────────────────────────────────────
APP_NAME  = "observatorio_geosalud"
USER_ID   = "frontend_user"

# ── Servicios ADK ──────────────────────────────────────────────────────────────
session_service  = InMemorySessionService()
artifact_service = InMemoryArtifactService()
fallback_artifacts: dict[tuple[str, str], bytes] = {}
local_context: dict[str, dict] = {}

runner = Runner(
    agent=root_agent,
    app_name=APP_NAME,
    session_service=session_service,
    artifact_service=artifact_service,
)

# ── FastAPI app ────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Observatorio GeoSalud — Chatbot API",
    description="Puente entre el dashboard frontend y el agente ADK de dengue.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # en producción: restringe al dominio del frontend
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


# ── Schemas ────────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    session_id: str
    message: str


class ChatResponse(BaseModel):
    reply: str
    artifacts: list[str]
    session_id: str
    actions: list[dict] = Field(default_factory=list)


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _ensure_session(session_id: str) -> None:
    """Crea la sesión ADK si no existe."""
    existing = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=session_id
    )
    if existing is None:
        await session_service.create_session(
            app_name=APP_NAME, user_id=USER_ID, session_id=session_id
        )


def _chart_cache(state: dict) -> set[str]:
    """Extrae las claves del caché de gráficas del state de sesión."""
    return set((state or {}).get("_chart_cache", {}).keys())


def _plain_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in normalized if not unicodedata.combining(ch))


def _figure_to_png_bytes(fig) -> bytes:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close(fig)
    return buf.getvalue()


def _extract_year(text: str) -> int | None:
    match = re.search(r"\b(2019|2020|2021|2022|2023|2024|2025|2026)\b", text)
    return int(match.group(1)) if match else None


def _extract_top_n(text: str, default: int = 5) -> int:
    match = re.search(r"\btop\s*(\d{1,2})\b|\b(\d{1,2})\s+municipios\b", text)
    if not match:
        return default
    return max(1, min(int(match.group(1) or match.group(2)), 42))


def _year_column(gdf) -> str:
    for col in ("año", "aÃ±o", "anio"):
        if col in gdf.columns:
            return col
    raise KeyError("No se encontró la columna de año en los datos.")


def _is_quota_error(exc: Exception) -> bool:
    message = str(exc).lower()
    return "resource_exhausted" in message or "429" in message or "quota" in message


def _extract_actions_from_part(part) -> list[dict]:
    actions: list[dict] = []
    function_response = getattr(part, "function_response", None)
    response = getattr(function_response, "response", None) if function_response else None
    if response is not None and not isinstance(response, dict) and hasattr(response, "model_dump"):
        response = response.model_dump()
    if isinstance(response, dict) and isinstance(response.get("actions"), list):
        actions.extend(a for a in response["actions"] if isinstance(a, dict))
    return actions


def _plot_series_municipios(gdf, municipios: list[str], metrica: str, title: str):
    y_col = "incidencia_dengue" if metrica == "incidencia" else "conteo_dengue"
    y_label = "Incidencia x 100.000 hab." if metrica == "incidencia" else "Casos"
    year_col = _year_column(gdf)
    df = (
        gdf[gdf["MPIO_CNMBR"].isin(municipios)]
        .sort_values(["MPIO_CNMBR", year_col])[
            ["MPIO_CNMBR", year_col, y_col]
        ]
        .copy()
    )

    fig, ax = plt.subplots(figsize=(12, 6))
    for municipio, serie in df.groupby("MPIO_CNMBR"):
        ax.plot(serie[year_col], serie[y_col], marker="o", linewidth=2, label=municipio)

    ax.set_title(title)
    ax.set_xlabel("Año")
    ax.set_ylabel(y_label)
    ax.legend(title="Municipio", fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()
    return fig


def _mentioned_municipios(text: str, municipios: list[str]) -> list[str]:
    mentioned = []
    for municipio in municipios:
        plain = _plain_text(municipio)
        if re.search(rf"\b(?:sin|excepto|excluye|excluir|quita|quitar)\s+{re.escape(plain)}\b", text):
            mentioned.append(municipio)
    return mentioned


def _series_response(
    req: ChatRequest,
    gdf,
    municipios: list[str],
    metrica: str,
    anio: int | None,
    n: int,
    label: str,
) -> ChatResponse:
    periodo = f"top {n} de {anio}" if anio else f"top {n} histórico"
    slug = "_".join(_plain_text(m).replace(" ", "-") for m in municipios)[:80]
    filename = f"serie_{periodo.replace(' ', '_')}_{metrica}_{slug}.png"
    title = f"Serie de tiempo de dengue - {label} por {metrica}"
    fig = _plot_series_municipios(gdf, municipios, metrica, title)
    fallback_artifacts[(req.session_id, filename)] = _figure_to_png_bytes(fig)
    local_context[req.session_id] = {
        **local_context.get(req.session_id, {}),
        "last_top_municipios": municipios,
        "last_series_municipios": municipios,
        "last_visual": "series",
        "last_anio": anio,
        "last_n": n,
        "last_metrica": metrica,
    }
    action = {
        "type": "show_tendencias",
        "municipios": municipios,
        "metrica": metrica,
        "anio": anio,
    }
    return ChatResponse(
        reply=f"Listo. Actualicé la serie de tiempo para {', '.join(municipios)}.",
        artifacts=[filename],
        session_id=req.session_id,
        actions=[action],
    )


def _local_top_municipios_response(req: ChatRequest) -> ChatResponse | None:
    text = _plain_text(req.message)
    if "municip" not in text or not any(word in text for word in ("top", "mayor", "mas")):
        return None
    if "casos" not in text and "incidencia" not in text:
        return None

    anio = _extract_year(text)
    if anio is None:
        return None

    n = _extract_top_n(text)
    metrica = "incidencia" if "incidencia" in text else "casos"
    filename = f"top{n}_{metrica}_{anio}.png"

    gdf = cargar_datos()
    year_col = _year_column(gdf)
    df = gdf[gdf[year_col] == anio].copy()
    if df.empty:
        return ChatResponse(
            reply=f"No encontré datos para {anio}. El observatorio cubre 2019-2026.",
            artifacts=[],
            session_id=req.session_id,
        )

    col = "incidencia_dengue" if metrica == "incidencia" else "conteo_dengue"
    ranking = df.sort_values(col, ascending=False).head(n)
    fig = (
        graficar_top_municipios_incidencia(gdf, anio=anio, n=n)
        if metrica == "incidencia"
        else graficar_top_municipios(gdf, anio=anio, n=n)
    )
    fallback_artifacts[(req.session_id, filename)] = _figure_to_png_bytes(fig)
    local_context[req.session_id] = {
        "last_top_municipios": ranking["MPIO_CNMBR"].tolist(),
        "last_visual": "top",
        "last_anio": anio,
        "last_n": n,
        "last_metrica": metrica,
    }

    lineas = []
    for i, row in enumerate(ranking.itertuples(), start=1):
        casos = int(getattr(row, "conteo_dengue") or 0)
        incidencia = getattr(row, "incidencia_dengue")
        if metrica == "incidencia":
            lineas.append(f"{i}. {row.MPIO_CNMBR}: {incidencia:.1f} por 100.000 hab. ({casos} casos)")
        else:
            lineas.append(f"{i}. {row.MPIO_CNMBR}: {casos} casos")

    modo = "incidencia" if metrica == "incidencia" else "casos"
    reply = (
        f"Estos fueron los {n} municipios con mayor número de {modo} de dengue en {anio}:\n\n"
        + "\n".join(lineas)
        + "\n\nGeneré la gráfica directamente desde los datos del observatorio."
    )
    return ChatResponse(reply=reply, artifacts=[filename], session_id=req.session_id)


def _local_series_top_municipios_response(req: ChatRequest) -> ChatResponse | None:
    text = _plain_text(req.message)
    wants_series = any(word in text for word in ("serie", "tiempo", "evolucion", "historica", "historico"))
    wants_top_munis = "municip" in text and any(word in text for word in ("mayor", "mas", "top"))
    if not wants_series or not wants_top_munis:
        return None
    if "casos" not in text and "incidencia" not in text:
        return None

    ctx = local_context.get(req.session_id, {})
    metrica = "incidencia" if "incidencia" in text else ctx.get("last_metrica", "casos")
    n = _extract_top_n(text, default=int(ctx.get("last_n", 5)))
    anio = _extract_year(text) or ctx.get("last_anio")

    gdf = cargar_datos()
    year_col = _year_column(gdf)
    col = "incidencia_dengue" if metrica == "incidencia" else "conteo_dengue"

    municipios = ctx.get("last_top_municipios")
    if not municipios or len(municipios) < n:
        base = gdf[gdf[year_col] == int(anio)].copy() if anio else gdf.copy()
        if metrica == "casos" and anio is None:
            ranking = (
                base.groupby("MPIO_CNMBR", as_index=False)[col]
                .sum()
                .sort_values(col, ascending=False)
                .head(n)
            )
        else:
            ranking = base.sort_values(col, ascending=False).head(n)
        municipios = ranking["MPIO_CNMBR"].tolist()
    else:
        municipios = municipios[:n]

    if not municipios:
        return ChatResponse(
            reply="No encontré municipios suficientes para construir la serie.",
            artifacts=[],
            session_id=req.session_id,
        )

    periodo = f"top {n} de {anio}" if anio else f"top {n} histórico"
    return _series_response(req, gdf, municipios, metrica, anio, n, periodo)


def _local_followup_response(req: ChatRequest) -> ChatResponse | None:
    text = _plain_text(req.message)
    if not any(word in text for word in ("sin", "excepto", "excluye", "excluir", "quita", "quitar")):
        return None

    ctx = local_context.get(req.session_id, {})
    if ctx.get("last_visual") != "series":
        return None

    gdf = cargar_datos()
    all_municipios = gdf["MPIO_CNMBR"].dropna().unique().tolist()
    excluded = _mentioned_municipios(text, all_municipios)
    if not excluded:
        return None

    previous = ctx.get("last_series_municipios") or ctx.get("last_top_municipios") or []
    municipios = [m for m in previous if m not in excluded]
    if not municipios:
        return ChatResponse(
            reply="Al excluir esos municipios no queda ninguna serie para mostrar.",
            artifacts=[],
            session_id=req.session_id,
        )

    metrica = ctx.get("last_metrica", "casos")
    anio = ctx.get("last_anio")
    n = len(municipios)
    label = f"sin {', '.join(excluded)}"
    return _series_response(req, gdf, municipios, metrica, anio, n, label)


def _local_observatory_action_response(req: ChatRequest) -> ChatResponse | None:
    text = _plain_text(req.message)
    anio = _extract_year(text)
    include_cali = None
    if any(phrase in text for phrase in ("incluye cali", "incluir cali", "con cali")):
        include_cali = True
    elif any(phrase in text for phrase in ("sin cali", "excluye cali", "excluir cali")):
        include_cali = False

    if any(word in text for word in ("mapa", "coropletico", "coropleticos", "valle del cauca")):
        if any(word in text for word in ("riesgo", "nivel")):
            variable = "riesgo"
            label = "nivel de riesgo"
        elif any(word in text for word in ("cambio", "delta", "2023-24", "2023 24")):
            variable = "delta"
            label = "cambio 2023-24"
        elif any(word in text for word in ("caso", "casos", "absoluto", "absolutos")):
            variable = "conteo_dengue"
            label = "casos absolutos"
        else:
            variable = "incidencia_dengue"
            label = "incidencia x100k"

        action = coropletico_action(variable=variable, anio=anio or 2024, incluir_cali=include_cali)
        return ChatResponse(
            reply=f"Listo. Actualicé el mapa coroplético para {label}"
            + (f" en {anio or 2024}." if variable not in ("riesgo", "delta") else "."),
            artifacts=[],
            session_id=req.session_id,
            actions=[action],
        )

    if any(word in text for word in ("geovisor", "burbujas", "calor")):
        mode = "calor" if "calor" in text else "coropletico" if "coropletico" in text else "burbujas"
        variable = "conteo_dengue" if "caso" in text else "incidencia_dengue"
        action = geovisor_action(mode=mode, variable=variable, anio=anio or 2024, incluir_cali=include_cali)
        return ChatResponse(
            reply=f"Listo. Abrí el geovisor en modo {mode} para {anio or 2024}.",
            artifacts=[],
            session_id=req.session_id,
            actions=[action],
        )

    section_aliases = [
        (("panel", "dashboard", "control"), "dashboard", "panel de control"),
        (("indicador", "indicadores"), "indicadores", "indicadores"),
        (("priorizacion", "priorizacion", "priorizar", "prioridad"), "priorizacion", "priorización"),
        (("tendencia", "tendencias"), "tendencias", "tendencias"),
    ]
    for words, section, label in section_aliases:
        if any(word in text for word in words):
            action = navigate_action(section, anio)
            return ChatResponse(
                reply=f"Listo. Abrí {label}" + (f" para {anio}." if anio else "."),
                artifacts=[],
                session_id=req.session_id,
                actions=[action],
            )

    return None


def _local_response(req: ChatRequest) -> ChatResponse | None:
    return (
        _local_followup_response(req)
        or _local_series_top_municipios_response(req)
        or _local_top_municipios_response(req)
        or _local_observatory_action_response(req)
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agent": root_agent.name, "app": APP_NAME}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Ejecuta un turno del agente y devuelve la respuesta + artifacts nuevos."""
    local_response = _local_response(req)
    if local_response is not None:
        return local_response

    await _ensure_session(req.session_id)

    # Snapshot del caché ANTES de este turno
    session_before = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=req.session_id
    )
    cache_before = _chart_cache(getattr(session_before, "state", {}) or {})

    # Construir mensaje del usuario
    user_msg = genai_types.Content(
        role="user",
        parts=[genai_types.Part.from_text(text=req.message)],
    )

    # Ejecutar agente
    final_text = ""
    ui_actions: list[dict] = []
    try:
        async for event in runner.run_async(
            user_id=USER_ID,
            session_id=req.session_id,
            new_message=user_msg,
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    ui_actions.extend(_extract_actions_from_part(part))
            if event.is_final_response():
                if event.content and event.content.parts:
                    for part in event.content.parts:
                        if hasattr(part, "text") and part.text:
                            final_text += part.text
    except Exception as exc:
        if _is_quota_error(exc):
            local_response = _local_response(req)
            if local_response is not None:
                return local_response
            return ChatResponse(
                reply=(
                    "Puedo seguir resolviendo consultas locales del observatorio. "
                    "Prueba con rankings, series de tiempo, mapas, geovisor, casos o incidencia por año."
                ),
                artifacts=[],
                session_id=req.session_id,
            )
        raise HTTPException(status_code=500, detail=f"Error en el agente: {exc}")

    if not final_text:
        final_text = "El agente no generó respuesta de texto. Intenta reformular la pregunta."

    # Detectar artifacts NUEVOS en este turno
    session_after = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=req.session_id
    )
    cache_after = _chart_cache(getattr(session_after, "state", {}) or {})
    new_artifacts = sorted(cache_after - cache_before)

    return ChatResponse(
        reply=final_text,
        artifacts=new_artifacts,
        session_id=req.session_id,
        actions=ui_actions,
    )


@app.get("/artifacts/{filename}")
async def get_artifact(filename: str, session_id: str):
    """Sirve un artifact PNG por su nombre de archivo y sesión."""
    fallback = fallback_artifacts.get((session_id, filename))
    if fallback is not None:
        return Response(
            content=fallback,
            media_type="image/png",
            headers={"Cache-Control": "private, max-age=3600"},
        )

    artifact = await artifact_service.load_artifact(
        app_name=APP_NAME,
        user_id=USER_ID,
        session_id=session_id,
        filename=filename,
    )
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Artifact '{filename}' no encontrado.")

    # El artifact es un genai_types.Part con inline_data
    image_bytes: bytes = artifact.inline_data.data
    return Response(
        content=image_bytes,
        media_type="image/png",
        headers={"Cache-Control": "private, max-age=3600"},
    )


# ── Arranque directo ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("CHATBOT_PORT", "8080"))
    print(f"\n🚀  GeoSalud Chatbot API  →  http://localhost:{port}")
    print(f"   Agente : {root_agent.name}")
    print(f"   Docs   : http://localhost:{port}/docs\n")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
