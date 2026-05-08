"""Agente especialista en acciones de interfaz del Observatorio GeoSalud."""

from __future__ import annotations

import os

from google.adk.agents import Agent

from ..callbacks import after_tool, before_tool
from ..ui_tools import abrir_modulo_observatorio, mostrar_geovisor, mostrar_mapa_coropletico

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

INSTRUCCIONES = """\
Eres el agente de interfaz del Observatorio GeoSalud.
Tu trabajo es traducir instrucciones del usuario en acciones concretas de la
aplicación: abrir módulos, cambiar año, seleccionar variables y mostrar mapas.

## Reglas

1. Usa tools cuando el usuario pida navegar o manipular la interfaz.
2. Para "mapa del Valle", "mapa de casos", "coroplético" o "nivel de riesgo",
   usa mostrar_mapa_coropletico.
3. Para "geovisor", "burbujas", "calor" o "mapa interactivo", usa mostrar_geovisor.
4. Para "abre indicadores", "abre priorización", "volver al panel", usa
   abrir_modulo_observatorio.
5. Responde con una frase breve confirmando la acción. No inventes datos.
"""

ui_agent = Agent(
    name="ui_agent",
    model=GEMINI_MODEL,
    description=(
        "Especialista en controlar la interfaz del observatorio: abrir módulos, "
        "mostrar coropléticos, configurar geovisor, año, variable, incluir/excluir Cali."
    ),
    instruction=INSTRUCCIONES,
    tools=[
        abrir_modulo_observatorio,
        mostrar_mapa_coropletico,
        mostrar_geovisor,
    ],
    before_tool_callback=before_tool,
    after_tool_callback=after_tool,
)

