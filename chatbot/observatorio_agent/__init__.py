"""Paquete del agente ADK del Observatorio GeoSalud.

ADK descubre el agente importando ``observatorio_agent.agent.root_agent``,
por eso aquí re-exportamos el módulo ``agent`` para que ``adk web``
y ``adk run`` lo encuentren automáticamente desde la carpeta ``chatbot/``.
"""

from . import agent  # noqa: F401  (lo importa ADK por convención)
