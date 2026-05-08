"""Callbacks de logging compartidos por todos los agentes ADK del Observatorio.

Cada llamada a una tool se registra como línea JSON en
outputs/adk_tool_calls.log — útil para auditar qué pidió el agente,
con qué argumentos y qué devolvió, sin depender de la UI de adk web.

Uso en cualquier agente:

    from .callbacks import before_tool, after_tool

    mi_agente = Agent(
        ...
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
    )
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

# ------------------------------------------------------------------
# Configuración del logger persistente
# ------------------------------------------------------------------
# El archivo vive en outputs/ (raíz del proyecto), junto a otros artefactos.
_LOG_FILE = Path(__file__).resolve().parents[3] / "outputs" / "adk_tool_calls.log"
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

_logger = logging.getLogger("observatorio_geosalud.tools")
_logger.setLevel(logging.INFO)
if not _logger.handlers:
    _handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")
    _handler.setFormatter(logging.Formatter("%(message)s"))
    _logger.addHandler(_handler)


# ------------------------------------------------------------------
# Helpers internos
# ------------------------------------------------------------------

def _log_event(event: str, **fields: Any) -> None:
    record = {
        "ts": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        "event": event,
        **fields,
    }
    _logger.info(json.dumps(record, ensure_ascii=False, default=str))


# ------------------------------------------------------------------
# Callbacks públicos (before / after tool)
# ------------------------------------------------------------------

def before_tool(tool, args, tool_context) -> None:
    """Registra el inicio de cada tool call con su nombre y argumentos."""
    inv_id = getattr(tool_context, "invocation_id", None)
    agent_name = getattr(tool_context, "agent_name", None)
    _log_event(
        "tool_call",
        agent=agent_name,
        tool=tool.name,
        args=args,
        invocation_id=inv_id,
    )
    return None


def after_tool(tool, args, tool_context, tool_response) -> None:
    """Registra el resultado de cada tool call (status y claves presentes)."""
    is_dict = isinstance(tool_response, dict)
    status = tool_response.get("status") if is_dict else None
    keys = list(tool_response.keys()) if is_dict else None
    inv_id = getattr(tool_context, "invocation_id", None)
    agent_name = getattr(tool_context, "agent_name", None)
    _log_event(
        "tool_response",
        agent=agent_name,
        tool=tool.name,
        status=status,
        response_keys=keys,
        invocation_id=inv_id,
    )
    return None
