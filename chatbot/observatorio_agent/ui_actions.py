"""Contratos de acciones para controlar la interfaz del Observatorio GeoSalud.

Estas funciones no dependen de ADK. Las usa el servidor local para responder
sin cuota y las envuelven las tools ADK de ui_tools.py para mantener un mismo
contrato hacia el frontend.
"""

from __future__ import annotations

VALID_YEARS = {2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026}

SECTION_LABELS = {
    "dashboard": "panel de control",
    "indicadores": "indicadores",
    "tendencias": "tendencias",
    "priorizacion": "priorizacion",
    "geovisor": "geovisor",
    "coropletico": "coropleticos",
}

VARIABLES = {
    "casos": "conteo_dengue",
    "casos_absolutos": "conteo_dengue",
    "conteo_dengue": "conteo_dengue",
    "incidencia": "incidencia_dengue",
    "incidencia_dengue": "incidencia_dengue",
    "riesgo": "riesgo",
    "delta": "delta",
    "cambio": "delta",
}

GEOVISOR_MODES = {"burbujas", "coropletico", "calor"}


def normalize_year(anio: int | None, default: int = 2024) -> int:
    year = int(anio or default)
    return year if year in VALID_YEARS else default


def normalize_variable(variable: str | None, default: str = "incidencia_dengue") -> str:
    key = (variable or default).strip().lower()
    return VARIABLES.get(key, default)


def navigate_action(section: str, anio: int | None = None) -> dict:
    section = section if section in SECTION_LABELS else "dashboard"
    action = {"type": "navigate", "section": section}
    if anio is not None:
        action["anio"] = normalize_year(anio)
    return action


def coropletico_action(
    variable: str = "incidencia_dengue",
    anio: int | None = 2024,
    incluir_cali: bool | None = None,
) -> dict:
    normalized = normalize_variable(variable)
    action = {
        "type": "show_geovisor",
        "mode": normalized if normalized in {"riesgo", "delta"} else "coropletico",
        "variable": normalized if normalized not in {"riesgo", "delta"} else "incidencia_dengue",
        "anio": normalize_year(anio),
    }
    if incluir_cali is not None:
        action["includeCali"] = bool(incluir_cali)
    return action


def geovisor_action(
    mode: str = "burbujas",
    variable: str = "incidencia_dengue",
    anio: int | None = 2024,
    incluir_cali: bool | None = None,
) -> dict:
    mode = (mode or "burbujas").strip().lower()
    if mode not in GEOVISOR_MODES:
        mode = "burbujas"
    action = {
        "type": "show_geovisor",
        "mode": mode,
        "variable": normalize_variable(variable),
        "anio": normalize_year(anio),
    }
    if incluir_cali is not None:
        action["includeCali"] = bool(incluir_cali)
    return action
