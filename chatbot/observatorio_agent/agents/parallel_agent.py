"""Agente paralelo: epidemio_agent + viz_agent simultáneos.

Patrón ADK: ParallelAgent
Documentación: https://adk.dev/agents/workflow-agents/parallel-agents/

Úsalo cuando el usuario pida datos numéricos Y una gráfica en el mismo turno.
Ejecuta ambos agentes de forma concurrente, reduciendo la latencia total
respecto a ejecutarlos en secuencia.

Flujo de resultados:
  · epidemio_agent  → texto con datos (casos, incidencia, ranking…)
  · viz_agent       → artifact PNG almacenado en la sesión ADK

El servidor (server.py) recoge ambas salidas en el mismo ciclo de eventos:
  - final_text  acumula el texto de ambos agentes
  - new_artifacts detecta los PNG nuevos por diff del _chart_cache en session.state
"""

from __future__ import annotations

from google.adk.agents.parallel_agent import ParallelAgent

from .epidemio_agent import build_epidemio_agent
from .viz_agent import build_viz_agent


class TransferableParallelAgent(ParallelAgent):
    """Compatibilidad con ADK 2.x al exponer el modo esperado por transfers."""

    @property
    def mode(self) -> str:
        return "default"


# Instancias propias y distintas de las de root_agent: ADK no permite que
# el mismo objeto Agent tenga dos padres (aquí, root_agent y este
# ParallelAgent), así que cada rama del árbol necesita la suya.
epidemio_viz_parallel = TransferableParallelAgent(
    name="epidemio_viz_parallel",
    description=(
        "Ejecuta epidemio_agent y viz_agent en paralelo. "
        "Usame cuando el usuario pida datos numéricos Y una gráfica en el mismo mensaje. "
        "Ejemplos: 'dame el top 5 de 2024 y la gráfica', "
        "'serie histórica de Tuluá en tabla y gráfico', "
        "'visualiza y muéstrame los números de Cali en 2023'."
    ),
    sub_agents=[
        build_epidemio_agent(name="epidemio_agent_par"),
        build_viz_agent(name="viz_agent_par"),
    ],
)
