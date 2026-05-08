"""Tools ADK para controlar módulos visuales del Observatorio GeoSalud.

Devuelven acciones estructuradas que el frontend entiende mediante
window.applyGeoSaludChatAction(action).
"""

from __future__ import annotations

from typing import Any

from google.adk.tools import ToolContext

from .ui_actions import coropletico_action, geovisor_action, navigate_action


def _ok(mensaje: str, action: dict[str, Any]) -> dict:
    return {"status": "success", "mensaje": mensaje, "actions": [action]}


def abrir_modulo_observatorio(
    modulo: str,
    tool_context: ToolContext,
    anio: int = 0,
) -> dict:
    """Abre un módulo principal del observatorio.

    Args:
        modulo: Uno de "dashboard", "indicadores", "tendencias",
            "priorizacion", "geovisor" o "coropletico".
        anio: Año opcional para sincronizar los controles globales. Usa 0 si
            el usuario no pidió un año.
    """
    aliases = {
        "panel": "dashboard",
        "dashboard": "dashboard",
        "control": "dashboard",
        "indicador": "indicadores",
        "indicadores": "indicadores",
        "tendencia": "tendencias",
        "tendencias": "tendencias",
        "priorizacion": "priorizacion",
        "priorización": "priorizacion",
        "prioridad": "priorizacion",
        "geovisor": "geovisor",
        "mapa": "coropletico",
        "coropletico": "coropletico",
        "coropleticos": "coropletico",
    }
    section = aliases.get((modulo or "").strip().lower(), "dashboard")
    action_year = anio or None
    if action_year is not None:
        tool_context.state["last_anio"] = int(anio)
    return _ok(f"Listo. Abrí {section}.", navigate_action(section, action_year))


def mostrar_mapa_coropletico(
    tool_context: ToolContext,
    anio: int = 2024,
    variable: str = "incidencia",
    incluir_cali: bool = False,
) -> dict:
    """Muestra el mapa coroplético del Valle del Cauca.

    Args:
        anio: Año de consulta entre 2019 y 2026. Para riesgo o cambio se
            conserva 2024 como referencia visual.
        variable: "casos", "incidencia", "riesgo" o "delta"/"cambio".
        incluir_cali: True para incluir Cali, False para excluirlo.
    """
    action = coropletico_action(variable=variable, anio=anio, incluir_cali=incluir_cali)
    tool_context.state["last_anio"] = int(action["anio"])
    tool_context.state["last_ui_module"] = "coropletico"
    return _ok("Listo. Actualicé el mapa coroplético.", action)


def mostrar_geovisor(
    tool_context: ToolContext,
    anio: int = 2024,
    modo: str = "burbujas",
    variable: str = "incidencia",
    incluir_cali: bool = False,
) -> dict:
    """Abre el geovisor y configura modo, variable y año.

    Args:
        anio: Año de consulta entre 2019 y 2026.
        modo: "burbujas", "coropletico" o "calor".
        variable: "casos" o "incidencia".
        incluir_cali: True para incluir Cali, False para excluirlo.
    """
    action = geovisor_action(mode=modo, variable=variable, anio=anio, incluir_cali=incluir_cali)
    tool_context.state["last_anio"] = int(action["anio"])
    tool_context.state["last_ui_module"] = "geovisor"
    return _ok("Listo. Actualicé el geovisor.", action)
