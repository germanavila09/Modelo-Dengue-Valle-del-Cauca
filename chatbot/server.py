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

import difflib
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


def _clean_db_muni_name(name: str) -> str:
    """Convierte un nombre de municipio potencialmente corrupto (con '?')
    a su forma limpia sin acentos y en minúsculas."""
    mapping = {
        "ALCAL?": "ALCALA",
        "ANDALUC?A": "ANDALUCIA",
        "BOL?VAR": "BOLIVAR",
        "EL ?GUILA": "EL AGUILA",
        "GUACAR?": "GUACARI",
        "JAMUND?": "JAMUNDI",
        "LA UNI?N": "LA UNION",
        "RIOFR?O": "RIOFRIO",
        "TULU?": "TULUA"
    }
    canonical = mapping.get(name, name)
    return _plain_text(canonical)


def _extract_multiple_municipios(text: str) -> list[str]:
    """Extrae todos los municipios mencionados en el texto de forma secuencial y limpia."""
    if not text:
        return []
    normalized_msg = _plain_text(text)
    
    # 1. Mapeos directos de aliases y nombres con espacios
    direct_mappings = {
        "guadalajara de buga": "GUADALAJARA DE BUGA",
        "san santiago de cali": "CALI",
        "santiago de cali": "CALI",
        "calima el darien": "CALIMA",
        "calima darien": "CALIMA",
        "el aguila": "EL AGUILA",
        "el cairo": "EL CAIRO",
        "el cerrito": "EL CERRITO",
        "el dovio": "EL DOVIO",
        "la cumbre": "LA CUMBRE",
        "la union": "LA UNION",
        "la victoria": "LA VICTORIA",
        "san pedro": "SAN PEDRO",
        "buga": "GUADALAJARA DE BUGA",
    }
    
    # Municipios de una sola palabra
    single_word_canonic = {
        "alcala": "ALCALA",
        "andalucia": "ANDALUCIA",
        "ansermanuevo": "ANSERMANUEVO",
        "argelia": "ARGELIA",
        "bolivar": "BOLIVAR",
        "buenaventura": "BUENAVENTURA",
        "bugalagrande": "BUGALAGRANDE",
        "caicedonia": "CAICEDONIA",
        "cali": "CALI",
        "calima": "CALIMA",
        "candelaria": "CANDELARIA",
        "cartago": "CARTAGO",
        "dagua": "DAGUA",
        "florida": "FLORIDA",
        "ginebra": "GINEBRA",
        "guacari": "GUACARI",
        "jamundi": "JAMUNDI",
        "obando": "OBANDO",
        "palmira": "PALMIRA",
        "pradera": "PRADERA",
        "restrepo": "RESTREPO",
        "riofrio": "RIOFRIO",
        "roldanillo": "ROLDANILLO",
        "sevilla": "SEVILLA",
        "toro": "TORO",
        "trujillo": "TRUJILLO",
        "tulua": "TULUA",
        "ulloa": "ULLOA",
        "versalles": "VERSALLES",
        "vijes": "VIJES",
        "yotoco": "YOTOCO",
        "yumbo": "YUMBO",
        "zarzal": "ZARZAL"
    }

    found = []  # Lista de tuplas (start, end, canonical_name)
    
    # Buscar coincidencias exactas de direct mappings
    for term, canonical in direct_mappings.items():
        pattern = rf"\b{re.escape(term)}\b"
        for m in re.finditer(pattern, normalized_msg):
            found.append((m.start(), m.end(), canonical))
            
    # Buscar coincidencias exactas de palabras simples
    for term, canonical in single_word_canonic.items():
        pattern = rf"\b{re.escape(term)}\b"
        for m in re.finditer(pattern, normalized_msg):
            # Evitar doble coincidencia si ya está cubierto por un mapeo directo
            overlap = False
            for start, end, can in found:
                if max(m.start(), start) < min(m.end(), end):
                    overlap = True
                    break
            if not overlap:
                found.append((m.start(), m.end(), canonical))
                
    # Coincidencia difusa para palabras restantes
    clean_msg_for_tokens = re.sub(r"[^\w\s]", " ", normalized_msg)
    tokens = [t for t in clean_msg_for_tokens.split() if len(t) >= 3]
    
    STOP_WORDS = {
        "cual", "cuales", "como", "cuanto", "cuantos", "cuantas", "que", "donde",
        "cuando", "quien", "quienes", "hubo", "tuvo", "tiene", "hay", "han",
        "del", "las", "los", "una", "uno", "son", "fue", "esta", "este",
        "para", "por", "con", "sin", "mas", "muy", "tan", "hay", "ser",
        "puede", "puedo", "dime", "dame", "muestra", "ver", "mostrar",
    }
    
    search_targets = list(single_word_canonic.keys()) + list(direct_mappings.keys())
    
    for token in tokens:
        if token in STOP_WORDS:
            continue
        token_pos = normalized_msg.find(token)
        if token_pos != -1:
            token_end = token_pos + len(token)
            already_matched = False
            for start, end, can in found:
                if max(token_pos, start) < min(token_end, end):
                    already_matched = True
                    break
            if already_matched:
                continue
                
        matches = difflib.get_close_matches(token, search_targets, n=1, cutoff=0.85)
        if matches:
            matched_term = matches[0]
            canonical = direct_mappings.get(matched_term) or single_word_canonic.get(matched_term)
            if canonical and canonical not in [c for _, _, c in found]:
                found.append((token_pos, token_pos + len(token), canonical))
                
    # Ordenar por índice de aparición
    found.sort(key=lambda x: x[0])
    
    # Retornar únicos preservando orden
    seen = set()
    result = []
    for _, _, canonical in found:
        if canonical not in seen:
            seen.add(canonical)
            result.append(canonical)
    return result


def _preprocess_message_multi(message: str) -> tuple[str, list[str]]:
    """Preprocesa el mensaje para corregir errores ortográficos en municipios
    y detectar todos los municipios mencionados.
    
    Devuelve (mensaje_corregido, lista_municipios_canonicos)
    """
    if not message:
        return message, []
        
    detected_munis = _extract_multiple_municipios(message)
    corrected_message = message
    
    # Realizar reemplazos correctivos en el texto original
    words = re.findall(r"\b\w+\b", message)
    for word in words:
        norm_word = _plain_text(word)
        if len(norm_word) < 3:
            continue
        for muni in detected_munis:
            muni_norm = _plain_text(muni)
            if norm_word == muni_norm:
                pattern = rf"\b{re.escape(word)}\b"
                corrected_message = re.sub(pattern, muni.title(), corrected_message, flags=re.IGNORECASE)
            elif len(norm_word) >= 4 and difflib.get_close_matches(norm_word, [muni_norm], n=1, cutoff=0.8):
                pattern = rf"\b{re.escape(word)}\b"
                corrected_message = re.sub(pattern, muni.title(), corrected_message, flags=re.IGNORECASE)
                
    return corrected_message, detected_munis


def _extract_navigation_action(message: str) -> tuple[str, dict | None]:
    """Extrae comandos de navegación del mensaje del usuario y los devuelve limpios.
    
    Permite separar intenciones de navegación de consultas de datos/visualizaciones.
    Devuelve (mensaje_limpio, accion_navegacion_dict | None).
    """
    if not message:
        return message, None

    msg_lower = message.lower()
    
    # Secciones y sus palabras clave
    section_keywords = {
        "dashboard": ["panel de control", "panel", "dashboard", "control"],
        "indicadores": ["indicadores", "indicador"],
        "priorizacion": ["priorizacion", "priorización", "priorizar", "prioridad"],
        "tendencias": ["tendencias", "tendencia"],
        "demografia": ["demografia", "demografía", "poblacion", "población"],
    }
    
    matched_section = None
    matched_keyword = None
    for sec, keywords in section_keywords.items():
        for kw in keywords:
            pattern = rf"\b{re.escape(kw)}\b"
            if re.search(pattern, msg_lower):
                if matched_keyword is None or len(kw) > len(matched_keyword):
                    matched_section = sec
                    matched_keyword = kw
                        
    if not matched_section:
        return message, None
        
    # Expresión regular mejorada para capturar el verbo de navegación y la sección
    kw_escaped = re.escape(matched_keyword)
    pattern = rf"\b(abre|abrir|navega|navegar|ir|ve|ver|mostrar)\b\s*(?:a|al|hacia|en)?\s*(?:el|la|los|las|el\s+módulo\s+de|la\s+sección\s+de|módulo\s+de|sección\s+de)?\s+{kw_escaped}\b"
    
    match = re.search(pattern, msg_lower)
    if not match:
        return message, None
        
    start, end = match.span()
    
    # Revisar si hay un conector antes (ej: "... y abre demografía")
    prefix = message[:start]
    match_leading_connector = re.search(r"\s+(y|e)\s+$", prefix)
    if match_leading_connector:
        start = match_leading_connector.start()
    else:
        # Revisar si hay un conector después (ej: "abre demografía y ...")
        remaining_msg = message[end:]
        clean_remaining = remaining_msg.strip()
        if clean_remaining.startswith("y ") or clean_remaining.startswith("e "):
            match_connector = re.match(r"\s+(y|e)\s+", remaining_msg)
            if match_connector:
                end += match_connector.end()
                
    clean_message = message[:start] + message[end:]
    clean_message = re.sub(r'\s+', ' ', clean_message).strip()
    
    if not clean_message:
        return message, None
        
    anio = _extract_year(message)
    action = navigate_action(matched_section, anio)
    
    return clean_message, action


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
    return (
        "resource_exhausted" in message
        or "429" in message
        or "quota" in message
        or "503" in message
        or "unavailable" in message
        or "high demand" in message
    )


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
    exclusion_keywords = ["sin", "excepto", "excluye", "excluir", "quita", "quitar"]
    first_excl_idx = -1
    for kw in exclusion_keywords:
        idx = text.find(kw)
        if idx != -1:
            if first_excl_idx == -1 or idx < first_excl_idx:
                first_excl_idx = idx

    if first_excl_idx == -1:
        return []

    mentioned = []
    for municipio in municipios:
        plain = _clean_db_muni_name(municipio)
        pattern = rf"\b{re.escape(plain)}\b"
        match = re.search(pattern, text)
        if match and match.start() > first_excl_idx:
            mentioned.append(municipio)
    return mentioned


def _clean_title_muni(muni_db: str) -> str:
    mapping = {
        "ALCAL?": "Alcalá",
        "ANDALUC?A": "Andalucía",
        "BOL?VAR": "Bolívar",
        "EL ?GUILA": "El Águila",
        "GUACAR?": "Guacarí",
        "JAMUND?": "Jamundí",
        "LA UNI?N": "La Unión",
        "RIOFR?O": "Riofrío",
        "TULU?": "Tuluá",
    }
    return mapping.get(muni_db, muni_db.title())


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
        "municipios": [_clean_title_muni(m) for m in municipios],
        "metrica": metrica,
        "anio": anio,
    }
    return ChatResponse(
        reply=f"Listo. Actualicé la serie de tiempo para {', '.join([_clean_title_muni(m) for m in municipios])}.",
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


def _local_series_multiple_municipios_response(req: ChatRequest) -> ChatResponse | None:
    text = _plain_text(req.message)
    municipios = _extract_multiple_municipios(req.message)
    if len(municipios) < 2:
        return None

    gdf = cargar_datos()
    dengue_corrupt_mapping = {
        "ALCALA": "ALCAL?",
        "ANDALUCIA": "ANDALUC?A",
        "BOLIVAR": "BOL?VAR",
        "EL AGUILA": "EL ?GUILA",
        "GUACARI": "GUACAR?",
        "JAMUNDI": "JAMUND?",
        "LA UNION": "LA UNI?N",
        "RIOFRIO": "RIOFR?O",
        "TULUA": "TULU?",
    }
    db_municipios = [dengue_corrupt_mapping.get(m, m) for m in municipios]

    ctx = local_context.setdefault(req.session_id, {})
    metrica = "incidencia" if "incidencia" in text else "casos" if "casos" in text else ctx.get("last_metrica", "casos")
    anio = _extract_year(text) or ctx.get("last_anio")
    n = len(db_municipios)
    label = "comparativa"

    return _series_response(req, gdf, db_municipios, metrica, anio, n, label)


def _local_series_top_municipios_response(req: ChatRequest) -> ChatResponse | None:
    text = _plain_text(req.message)
    wants_top_munis = "municip" in text and any(word in text for word in ("mayor", "mas", "top", "ranking", "peores"))
    if not wants_top_munis:
        return None

    wants_series = any(word in text for word in ("serie", "tiempo", "evolucion", "historica", "historico", "tendencia", "comportamiento")) or (_extract_year(text) is None)
    if not wants_series:
        return None

    ctx = local_context.setdefault(req.session_id, {})
    metrica = "incidencia" if "incidencia" in text else "casos" if "casos" in text else ctx.get("last_metrica", "casos")
    n = _extract_top_n(text, default=int(ctx.get("last_n", 5)))
    anio = _extract_year(text) or ctx.get("last_anio")

    gdf = cargar_datos()
    year_col = _year_column(gdf)
    col = "incidencia_dengue" if metrica == "incidencia" else "conteo_dengue"

    base = gdf[gdf[year_col] == int(anio)].copy() if anio else gdf.copy()
    if metrica == "casos" and anio is None:
        ranking = (
            base.groupby("MPIO_CNMBR", as_index=False)[col]
            .sum()
            .sort_values(col, ascending=False)
            .head(n)
        )
    elif metrica == "incidencia" and anio is None:
        ranking = (
            base.dropna(subset=[col])
            .groupby("MPIO_CNMBR", as_index=False)[col]
            .mean()
            .sort_values(col, ascending=False)
            .head(n)
        )
    else:
        ranking = base.sort_values(col, ascending=False).head(n)
    municipios = ranking["MPIO_CNMBR"].tolist()

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
    ctx = local_context.get(req.session_id, {})
    if ctx.get("last_visual") != "series":
        return None

    # Si la consulta solicita un top de municipios, no es un follow-up de la selección actual.
    if "top" in text or ("municip" in text and any(word in text for word in ("mayor", "mas", "ranking", "peores"))):
        return None

    detected_munis = _extract_multiple_municipios(req.message)
    
    # Si detectamos una nueva comparación explícita o implícita de 2+ municipios,
    # y no hay verbos explícitos de adición/remoción, tratarlo como una nueva consulta.
    is_comparison = "compar" in text or " vs " in text or "versus" in text or len(detected_munis) >= 2
    has_explicit_action = any(w in text for w in ("agrega", "añade", "incluye", "adiciona", "con", "sin", "excepto", "excluye", "quita", "elimina", "remueve"))
    if is_comparison and not has_explicit_action:
        return None

    removal_words = ("sin", "excepto", "excluye", "excluir", "quita", "quitar", "elimina", "eliminar", "remueve", "remover", "menos")
    addition_words = ("agrega", "agrega-le", "añade", "incluye", "adiciona", "con", "sumar", "y")

    is_removal = any(w in text for w in removal_words)
    is_addition = any(w in text for w in ("agrega", "añade", "incluye", "adiciona", "con"))
    if not is_addition and (" y " in text or text.startswith("y ")):
        is_addition = True
    is_metric_change = "casos" in text or "incidencia" in text

    if not (is_removal or is_addition or is_metric_change):
        return None

    previous = ctx.get("last_series_municipios") or ctx.get("last_top_municipios") or []
    if not previous:
        return None
    dengue_corrupt_mapping = {
        "ALCALA": "ALCAL?",
        "ANDALUCIA": "ANDALUC?A",
        "BOLIVAR": "BOL?VAR",
        "EL AGUILA": "EL ?GUILA",
        "GUACARI": "GUACAR?",
        "JAMUNDI": "JAMUND?",
        "LA UNION": "LA UNI?N",
        "RIOFRIO": "RIOFR?O",
        "TULUA": "TULU?",
    }
    db_detected = [dengue_corrupt_mapping.get(m, m) for m in detected_munis]

    removals = []
    additions = []

    muni_indices = []
    for m in db_detected:
        clean_db_name = {
            "ALCAL?": "alcala",
            "ANDALUC?A": "andalucia",
            "BOL?VAR": "bolivar",
            "EL ?GUILA": "el aguila",
            "GUACAR?": "guacari",
            "JAMUND?": "jamundi",
            "LA UNI?N": "la union",
            "RIOFR?O": "riofrio",
            "TULU?": "tulua",
        }
        plain_m = clean_db_name.get(m, _plain_text(m))
        pos = text.find(plain_m)
        if pos != -1:
            muni_indices.append((pos, m))

    action_positions = []
    for w in removal_words:
        pos = text.find(w)
        if pos != -1:
            action_positions.append((pos, "remove"))
    for w in addition_words:
        pos = text.find(w)
        if pos != -1:
            action_positions.append((pos, "add"))

    muni_indices.sort(key=lambda x: x[0])
    action_positions.sort(key=lambda x: x[0])

    for pos, m in muni_indices:
        preceding = [act for act in action_positions if act[0] < pos]
        if preceding:
            closest_action = preceding[-1][1]
            if closest_action == "remove":
                removals.append(m)
            else:
                additions.append(m)
        else:
            if is_removal:
                removals.append(m)
            elif is_addition:
                additions.append(m)

    municipios = list(previous)
    changes = []

    if removals:
        municipios = [m for m in municipios if m not in removals]
        changes.append(f"removí {', '.join([_clean_title_muni(m) for m in removals])}")

    if additions:
        added = []
        for m in additions:
            if m not in municipios:
                municipios.append(m)
                added.append(m)
        if added:
            changes.append(f"agregué {', '.join([_clean_title_muni(m) for m in added])}")

    prev_metrica = ctx.get("last_metrica", "casos")
    metrica = prev_metrica
    if "incidencia" in text:
        metrica = "incidencia"
    elif "casos" in text:
        metrica = "casos"

    if metrica != prev_metrica:
        changes.append(f"cambié la métrica a {metrica}")

    if not municipios:
        return ChatResponse(
            reply="Al excluir esos municipios no queda ninguna serie para mostrar.",
            artifacts=[],
            session_id=req.session_id,
        )

    gdf = cargar_datos()
    anio = ctx.get("last_anio")
    n = len(municipios)
    label = "serie_followup"

    reply_prefix = f"Listo, {', '.join(changes)}." if changes else "Listo. Redibujé el gráfico."

    res = _series_response(req, gdf, municipios, metrica, anio, n, label)
    res.reply = f"{reply_prefix} Actualicé la serie de tiempo para {', '.join([_clean_title_muni(m) for m in municipios])}."
    return res


def _local_observatory_action_response(req: ChatRequest) -> ChatResponse | None:
    text = _plain_text(req.message)
    anio = _extract_year(text)
    include_cali = None
    if any(phrase in text for phrase in ("incluye cali", "incluir cali", "con cali")):
        include_cali = True
    elif any(phrase in text for phrase in ("sin cali", "excluye cali", "excluir cali")):
        include_cali = False

    is_pob_query = any(w in text for w in ("poblacion", "habitantes", "personas"))
    if not is_pob_query and any(word in text for word in ("mapa", "coropletico", "coropleticos", "valle del cauca")):
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
        (("demografia", "demografía", "poblacion", "población"), "demografia", "demografía"),
    ]
    for words, section, label in section_aliases:
        if any(word in text for word in words):
            if section == "demografia":
                is_query = (
                    any(q in text for q in ["cual", "como", "cuant", "de ", "en ", "por ", "ciclo", "piramide", "sexo", "genero", "hombre", "mujer", "edad"])
                    or len(text.split()) > 4
                )
                is_explicit_nav = any(nav in text for nav in ["abre", "abrir", "navegar", "ir a", "modulo", "seccion", "ver ", "mostrar "])
                if is_query and not is_explicit_nav:
                    continue
            action = navigate_action(section, anio)
            return ChatResponse(
                reply=f"Listo. Abrí {label}" + (f" para {anio}." if anio else "."),
                artifacts=[],
                session_id=req.session_id,
                actions=[action],
            )

    return None


def _load_gdf_cached() -> object:
    """Carga el GeoDataFrame; reutiliza la instancia si ya se cargó."""
    if not hasattr(_load_gdf_cached, "_cache"):
        _load_gdf_cached._cache = cargar_datos()
    return _load_gdf_cached._cache


def _all_municipios() -> list[str]:
    """Lista normalizada de municipios del observatorio."""
    if not hasattr(_all_municipios, "_cache"):
        gdf = cargar_datos()
        _all_municipios._cache = [
            m.strip().upper() for m in gdf["MPIO_CNMBR"].dropna().unique().tolist()
        ]
    return _all_municipios._cache


def _extract_municipio(text: str) -> str | None:
    """Detecta el primer municipio mencionado en el texto."""
    for municipio in _all_municipios():
        plain = _plain_text(municipio)
        if re.search(rf"\b{re.escape(plain)}\b", text):
            return municipio
    return None


def _local_casos_municipio_response(req: ChatRequest) -> ChatResponse | None:
    """Consulta directa de casos para un municipio y año específicos."""
    text = _plain_text(req.message)
    anio = _extract_year(text)
    if anio is None:
        return None
    municipio = _extract_municipio(text)
    if municipio is None:
        return None

    gdf = cargar_datos()
    year_col = _year_column(gdf)
    row = gdf[(gdf["MPIO_CNMBR"] == municipio) & (gdf[year_col] == anio)]
    if row.empty:
        return ChatResponse(
            reply=f"No encontré datos para {municipio.title()} en {anio}. El observatorio cubre 2019-2026.",
            artifacts=[],
            session_id=req.session_id,
        )

    r = row.iloc[0]
    casos = int(r["conteo_dengue"]) if r["conteo_dengue"] is not None else 0
    inc = r["incidencia_dengue"]
    pob = r["poblacion"]
    lineas = [f"En **{municipio.title()}** durante **{anio}**:"]
    lineas.append(f"- Casos confirmados de dengue: **{casos:,}**")
    if inc is not None:
        lineas.append(f"- Incidencia: **{float(inc):.1f}** por 100.000 hab.")
    if pob is not None:
        lineas.append(f"- Población estimada: **{int(pob):,}**")
    local_context[req.session_id] = {
        **local_context.get(req.session_id, {}),
        "last_anio": anio,
        "last_municipio": municipio,
    }
    return ChatResponse(
        reply="\n".join(lineas),
        artifacts=[],
        session_id=req.session_id,
    )


def _local_resumen_anio_response(req: ChatRequest) -> ChatResponse | None:
    """Resumen agregado del Valle del Cauca para un año."""
    text = _plain_text(req.message)
    anio = _extract_year(text)
    if anio is None:
        return None

    keywords = ("dengue", "valle", "departamento", "total", "resumen", "como estuvo", "que paso", "situacion")
    if not any(k in text for k in keywords):
        return None
    # No activar si ya hay un municipio específico detectado
    if _extract_municipio(text) is not None:
        return None

    gdf = cargar_datos()
    year_col = _year_column(gdf)
    df = gdf[gdf[year_col] == anio].copy()
    if df.empty:
        return ChatResponse(
            reply=f"No encontré datos para {anio}. El observatorio cubre 2019-2026.",
            artifacts=[],
            session_id=req.session_id,
        )

    total_casos = int(df["conteo_dengue"].fillna(0).sum())
    pob_total = int(df["poblacion"].fillna(0).sum())
    inc_dpto = round(total_casos / pob_total * 100_000, 1) if pob_total > 0 else None
    df_c = df.dropna(subset=["conteo_dengue"])
    df_i = df.dropna(subset=["incidencia_dengue"])
    top_casos = df_c.sort_values("conteo_dengue", ascending=False).head(3)["MPIO_CNMBR"].tolist()
    top_inc = df_i.sort_values("incidencia_dengue", ascending=False).head(3)["MPIO_CNMBR"].tolist()

    lineas = [f"**Resumen del dengue en el Valle del Cauca — {anio}:**"]
    lineas.append(f"- Casos totales: **{total_casos:,}**")
    if inc_dpto:
        lineas.append(f"- Incidencia departamental: **{inc_dpto}** por 100.000 hab.")
    lineas.append(f"- Municipios con más casos: {', '.join(top_casos)}")
    lineas.append(f"- Municipios con mayor incidencia: {', '.join(top_inc)}")
    lineas.append(f"- Municipios con datos: {len(df_c)}")
    local_context[req.session_id] = {**local_context.get(req.session_id, {}), "last_anio": anio}
    return ChatResponse(reply="\n".join(lineas), artifacts=[], session_id=req.session_id)


def _local_serie_municipio_response(req: ChatRequest, nav_action: dict | None = None) -> ChatResponse | None:
    """Serie histórica de un municipio sin especificar año."""
    text = _plain_text(req.message)
    wants_serie = any(w in text for w in ("serie", "historico", "historica", "evolucion", "tiempo", "anos", "anios"))
    if not wants_serie:
        if nav_action and nav_action.get("section") == "tendencias":
            wants_serie = True
        else:
            anio = _extract_year(text)
            municipio = _extract_municipio(text)
            if anio is None and municipio is not None:
                if any(w in text for w in ("caso", "incidencia", "dengue")):
                    wants_serie = True

    if not wants_serie:
        return None
    municipio = _extract_municipio(text)
    if municipio is None:
        ctx = local_context.get(req.session_id, {})
        municipio = ctx.get("last_municipio")
    if municipio is None:
        return None

    gdf = cargar_datos()
    year_col = _year_column(gdf)
    df = gdf[gdf["MPIO_CNMBR"] == municipio].sort_values(year_col)[
        [year_col, "conteo_dengue", "incidencia_dengue"]
    ].dropna(subset=["conteo_dengue"])
    if df.empty:
        return None

    metrica = "incidencia" if "incidencia" in text else "casos"
    filename = f"serie_historica_{metrica}_{_plain_text(municipio).replace(' ', '_')}.png"
    title = f"Serie de tiempo de dengue - {_clean_title_muni(municipio)} por {metrica}"
    fig = _plot_series_municipios(gdf, [municipio], metrica, title)
    fallback_artifacts[(req.session_id, filename)] = _figure_to_png_bytes(fig)

    lineas = [f"**Serie histórica de dengue — {_clean_title_muni(municipio)}:**\n"]
    for _, r in df.iterrows():
        casos = int(r["conteo_dengue"])
        inc = r["incidencia_dengue"]
        sufijo = f" (inc. {float(inc):.1f})" if inc is not None else ""
        lineas.append(f"- {int(r[year_col])}: {casos:,} casos{sufijo}")

    local_context[req.session_id] = {
        **local_context.get(req.session_id, {}),
        "last_municipio": municipio,
        "last_series_municipios": [municipio],
        "last_visual": "series",
        "last_anio": None,
        "last_metrica": metrica,
    }

    action = {
        "type": "show_tendencias",
        "municipios": [_clean_title_muni(municipio)],
        "metrica": metrica,
        "anio": None,
    }

    reply = (
        f"Listo. Mostrando la serie de tiempo para **{_clean_title_muni(municipio)}** en el módulo de Tendencias.\n\n"
        + "\n".join(lineas)
    )

    return ChatResponse(
        reply=reply,
        artifacts=[filename],
        session_id=req.session_id,
        actions=[action],
    )


def _local_poblacion_municipio_response(req: ChatRequest) -> ChatResponse | None:
    """Población de un municipio o del Valle del Cauca."""
    text = _plain_text(req.message)
    if not any(w in text for w in ("poblacion", "habitantes", "cuantas personas", "cuantos habitantes")):
        return None

    gdf = cargar_datos()
    year_col = _year_column(gdf)
    anio = _extract_year(text)
    municipio = _extract_municipio(text)
    is_valle = any(w in text for w in ("valle", "departamento")) and municipio is None

    if municipio is None and not is_valle:
        return None

    if anio is None:
        anio = int(gdf[year_col].max())

    if municipio:
        df = gdf[(gdf["MPIO_CNMBR"] == municipio) & (gdf[year_col] == anio)]
        if df.empty:
            return None
        pob = df.iloc[0]["poblacion"]
        if pob is None:
            return None
        return ChatResponse(
            reply=f"La población estimada de **{municipio.title()}** en {anio} es de **{int(pob):,} habitantes**.",
            artifacts=[],
            session_id=req.session_id,
        )
    else:
        df = gdf[gdf[year_col] == anio]
        total = int(df["poblacion"].fillna(0).sum())
        return ChatResponse(
            reply=f"La población total estimada del **Valle del Cauca** en {anio} es de **{total:,} habitantes**.",
            artifacts=[],
            session_id=req.session_id,
        )


def _local_info_response(req: ChatRequest) -> ChatResponse | None:
    """Saludo e información básica del observatorio."""
    text = _plain_text(req.message)
    saludo_keys = ("hola", "buenos", "buenas", "que puedes", "como funciona", "que eres", "quien eres",
                   "ayuda", "help", "que hace", "que haces", "capacidades", "para que sirves")
    if not any(k in text for k in saludo_keys):
        return None
    reply = (
        "Soy el asistente del **Observatorio GeoSalud del Valle del Cauca**.\n\n"
        "Puedo ayudarte con:\n"
        "- Casos de dengue por municipio y año\n"
        "- Población de municipios\n"
        "- Top municipios por casos o incidencia\n"
        "- Series históricas de dengue\n"
        "- Resúmenes anuales del departamento\n"
        "- Mapas, geovisor y navegación del observatorio\n\n"
        "El observatorio cubre **42 municipios del Valle del Cauca** entre **2019 y 2026**."
    )
    return ChatResponse(reply=reply, artifacts=[], session_id=req.session_id)


def _local_response(req: ChatRequest, nav_action: dict | None = None) -> ChatResponse | None:
    return (
        _local_followup_response(req)
        or _local_series_multiple_municipios_response(req)
        or _local_series_top_municipios_response(req)
        or _local_top_municipios_response(req)
        or _local_observatory_action_response(req)
        or _local_casos_municipio_response(req)
        or _local_poblacion_municipio_response(req)
        or _local_resumen_anio_response(req)
        or _local_serie_municipio_response(req, nav_action)
        or _local_info_response(req)
    )


# ── Endpoints ──────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "agent": root_agent.name, "app": APP_NAME}


@app.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """Ejecuta un turno del agente y devuelve la respuesta + artifacts nuevos."""
    # 0. Extraer comando de navegación para consultas mixtas (action chaining)
    cleaned_msg, nav_action = _extract_navigation_action(req.message)
    req.message = cleaned_msg

    # 1. Preprocesar mensaje del usuario (coincidencia difusa de municipios)
    corrected_msg, detected_munis = _preprocess_message_multi(req.message)
    req.message = corrected_msg

    # Asegurar sesión de ADK para poder sincronizar
    await _ensure_session(req.session_id)
    stored_session = await session_service.get_session(
        app_name=APP_NAME, user_id=USER_ID, session_id=req.session_id
    )
    if stored_session.state is None:
        stored_session.state = {}

    # Sincronizar bidireccionalmente local_context y session.state antes de responder
    ctx = local_context.setdefault(req.session_id, {})
    keys_to_sync = (
        "last_series_municipios",
        "last_metrica",
        "last_visual",
        "last_municipio",
        "last_anio",
        "last_n",
        "last_top_municipios",
    )
    for key in keys_to_sync:
        if key in ctx and key not in stored_session.state:
            stored_session.state[key] = ctx[key]
        elif key in stored_session.state and key not in ctx:
            ctx[key] = stored_session.state[key]

    # 2. Si se detectaron municipios, inyectarlos en local_context y session.state
    if detected_munis:
        dengue_corrupt_mapping = {
            "ALCALA": "ALCAL?",
            "ANDALUCIA": "ANDALUC?A",
            "BOLIVAR": "BOL?VAR",
            "EL AGUILA": "EL ?GUILA",
            "GUACARI": "GUACAR?",
            "JAMUNDI": "JAMUND?",
            "LA UNION": "LA UNI?N",
            "RIOFRIO": "RIOFR?O",
            "TULUA": "TULU?",
        }
        db_munis = [dengue_corrupt_mapping.get(m, m) for m in detected_munis]
        
        ctx["last_municipio"] = db_munis[-1]
        stored_session.state["last_municipio"] = db_munis[-1]
        
        if len(db_munis) >= 2:
            ctx["last_series_municipios"] = db_munis
            stored_session.state["last_series_municipios"] = db_munis

    # 3. Intentar responder localmente
    local_response = _local_response(req, nav_action)
    if local_response is not None:
        if nav_action:
            local_response.actions.insert(0, nav_action)
        # Sincronizar de vuelta a session.state los cambios del local responder
        for key in keys_to_sync:
            if key in ctx:
                stored_session.state[key] = ctx[key]
        return local_response

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
            local_response = _local_response(req, nav_action)
            if local_response is not None:
                if nav_action:
                    local_response.actions.insert(0, nav_action)
                return local_response
            return ChatResponse(
                reply=(
                    "No tengo información suficiente para responder esa consulta en este momento. "
                    "Puedes preguntarme sobre casos de dengue, población, rankings, "
                    "series históricas o resúmenes anuales del Valle del Cauca."
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

    # Sincronizar el estado de vuelta a local_context
    if session_after and session_after.state:
        for key in keys_to_sync:
            if key in session_after.state:
                ctx[key] = session_after.state[key]

    # Anteponer la acción de navegación si existe
    if nav_action:
        ui_actions.insert(0, nav_action)

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
    print(f"\n[*] GeoSalud Chatbot API  ->  http://localhost:{port}")
    print(f"   Agente : {root_agent.name}")
    print(f"   Docs   : http://localhost:{port}/docs\n", flush=True)
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
