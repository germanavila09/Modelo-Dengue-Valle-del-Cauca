"""Tools del agente ADK del Observatorio GeoSalud.

Cada funcion expuesta como tool sigue las reglas de ADK:

* Tipos de parametros JSON-serializables (str, int, float, bool, list, dict).
* Docstring claro: el LLM lee este texto para decidir cuando invocarla.
* Devuelve siempre ``dict`` con clave ``status`` ("success" | "error") y
  el resto de la informacion, asi el agente puede razonar sobre fallos.
* Recibe ``tool_context: ToolContext`` (lo inyecta ADK) para leer/escribir
  ``state``: el diccionario de la sesion que sobrevive entre turnos.

Las tools consultan la base PostGIS reutilizando ``src.db`` y ``src.config``
del proyecto. Para que funcione sin instalar el paquete, agregamos la raiz
del repo a ``sys.path`` la primera vez que se importa este modulo.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# Permite ``import src.db`` cuando se ejecuta ``adk web`` desde chatbot/
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# Imports tardios (despues de manipular sys.path)
import pandas as pd  # noqa: E402
from sqlalchemy import text  # noqa: E402

from google.adk.tools import ToolContext  # noqa: E402

from src.config import SCHEMA, TABLE  # noqa: E402
from src.db import crear_engine  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

# Claves canonicas de state. Centralizadas aqui para no tipear strings sueltas.
STATE_LAST_MUNI = "last_municipio"
STATE_LAST_ANIO = "last_anio"
STATE_METRICA = "metrica_preferida"


def _ok(**payload: Any) -> dict:
    return {"status": "success", **payload}


def _err(message: str) -> dict:
    return {"status": "error", "error_message": message}


def _norm_municipio(nombre: str) -> str:
    return nombre.strip().upper()


def _remember(tool_context: ToolContext, municipio: str | None = None, anio: int | None = None) -> None:
    """Guarda el ultimo municipio/anio consultado en state."""
    if municipio is not None:
        tool_context.state[STATE_LAST_MUNI] = municipio
    if anio is not None:
        tool_context.state[STATE_LAST_ANIO] = int(anio)


# ---------------------------------------------------------------------------
# Tools expuestas al agente
# ---------------------------------------------------------------------------

def listar_municipios(tool_context: ToolContext) -> dict:
    """Devuelve la lista de municipios disponibles en el Observatorio GeoSalud.

    Usar cuando el usuario pregunte que municipios cubre el sistema o
    cuando necesites validar un nombre antes de otra consulta.
    """
    try:
        engine = crear_engine()
        query = text(
            f'SELECT DISTINCT "MPIO_CNMBR" AS municipio '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'ORDER BY "MPIO_CNMBR";'
        )
        df = pd.read_sql(query, engine)
        municipios = df["municipio"].tolist()
        return _ok(municipios=municipios, total=len(municipios))
    except Exception as exc:
        return _err(f"No se pudo consultar la lista de municipios: {exc}")


def casos_por_municipio_anio(municipio: str, anio: int, tool_context: ToolContext) -> dict:
    """Casos de dengue de un municipio en un anio especifico.

    Args:
        municipio: Nombre del municipio (ej. "CALI", "PALMIRA"). Se normaliza
            a mayusculas internamente.
        anio: Anio de consulta (entero, ej. 2024).
    """
    try:
        muni = _norm_municipio(municipio)
        engine = crear_engine()
        query = text(
            f'SELECT "MPIO_CNMBR" AS municipio, "año" AS anio, '
            f'       "población" AS poblacion, conteo_dengue, incidencia_dengue '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'WHERE "MPIO_CNMBR" = :muni AND "año" = :anio;'
        )
        df = pd.read_sql(query, engine, params={"muni": muni, "anio": int(anio)})
        if df.empty:
            return _err(
                f"No hay datos para municipio={muni!r} y anio={anio}. "
                "Revisa el nombre con la tool listar_municipios."
            )
        row = df.iloc[0].to_dict()
        _remember(tool_context, municipio=muni, anio=int(anio))
        return _ok(
            municipio=row["municipio"],
            anio=int(row["anio"]),
            poblacion=int(row["poblacion"]) if pd.notna(row["poblacion"]) else None,
            casos=int(row["conteo_dengue"]) if pd.notna(row["conteo_dengue"]) else 0,
            incidencia_x100k=(
                float(row["incidencia_dengue"]) if pd.notna(row["incidencia_dengue"]) else None
            ),
        )
    except Exception as exc:
        return _err(f"Error consultando casos: {exc}")


def top_municipios(anio: int, tool_context: ToolContext, n: int = 5, metrica: str = "") -> dict:
    """Top-N municipios con mas casos o mayor incidencia en un anio.

    Args:
        anio: Anio a consultar.
        n: Cantidad de municipios a devolver (1-42). Default 5.
        metrica: "casos" para conteo absoluto, "incidencia" para tasa por
            100.000 habitantes. Si llega vacio se usa la preferencia
            guardada en state (state.metrica_preferida) o "casos" por defecto.
    """
    try:
        if not metrica:
            metrica = tool_context.state.get(STATE_METRICA, "casos")
        if metrica not in {"casos", "incidencia"}:
            return _err("metrica debe ser 'casos' o 'incidencia'.")
        n = max(1, min(int(n), 42))

        col = "conteo_dengue" if metrica == "casos" else "incidencia_dengue"
        engine = crear_engine()
        query = text(
            f'SELECT "MPIO_CNMBR" AS municipio, '
            f'       conteo_dengue AS casos, '
            f'       incidencia_dengue AS incidencia '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'WHERE "año" = :anio AND {col} IS NOT NULL '
            f'ORDER BY {col} DESC '
            f'LIMIT :n;'
        )
        df = pd.read_sql(query, engine, params={"anio": int(anio), "n": n})
        if df.empty:
            return _err(f"No hay datos para el anio {anio}.")
        ranking = [
            {
                "municipio": r["municipio"],
                "casos": int(r["casos"]) if pd.notna(r["casos"]) else 0,
                "incidencia_x100k": (
                    float(r["incidencia"]) if pd.notna(r["incidencia"]) else None
                ),
            }
            for _, r in df.iterrows()
        ]
        _remember(tool_context, anio=int(anio))
        return _ok(anio=int(anio), metrica=metrica, ranking=ranking)
    except Exception as exc:
        return _err(f"Error generando ranking: {exc}")


def serie_temporal_municipio(municipio: str, tool_context: ToolContext) -> dict:
    """Serie historica de casos de un municipio (todos los anios disponibles).

    Args:
        municipio: Nombre del municipio (ej. "CALI").
    """
    try:
        muni = _norm_municipio(municipio)
        engine = crear_engine()
        query = text(
            f'SELECT "año" AS anio, conteo_dengue AS casos, '
            f'       incidencia_dengue AS incidencia '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'WHERE "MPIO_CNMBR" = :muni '
            f'ORDER BY "año";'
        )
        df = pd.read_sql(query, engine, params={"muni": muni})
        if df.empty:
            return _err(
                f"No hay serie historica para {muni!r}. "
                "Usa listar_municipios para verificar el nombre."
            )
        serie = [
            {
                "anio": int(r["anio"]),
                "casos": int(r["casos"]) if pd.notna(r["casos"]) else 0,
                "incidencia_x100k": (
                    float(r["incidencia"]) if pd.notna(r["incidencia"]) else None
                ),
            }
            for _, r in df.iterrows()
        ]
        _remember(tool_context, municipio=muni)
        return _ok(municipio=muni, n_puntos=len(serie), serie=serie)
    except Exception as exc:
        return _err(f"Error consultando serie temporal: {exc}")


def resumen_anio(anio: int, tool_context: ToolContext) -> dict:
    """Resumen agregado del Valle del Cauca para un anio dado.

    Calcula totales, promedios y municipios extremos.

    Args:
        anio: Anio a consultar.
    """
    try:
        engine = crear_engine()
        query = text(
            f'SELECT "MPIO_CNMBR" AS municipio, '
            f'       "población" AS poblacion, '
            f'       conteo_dengue AS casos, '
            f'       incidencia_dengue AS incidencia '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'WHERE "año" = :anio;'
        )
        df = pd.read_sql(query, engine, params={"anio": int(anio)})
        if df.empty:
            return _err(f"No hay datos para el anio {anio}.")

        total_casos = int(df["casos"].fillna(0).sum())
        poblacion = int(df["poblacion"].fillna(0).sum())
        incidencia_dpto = (total_casos / poblacion * 100_000) if poblacion > 0 else None

        df_casos = df.dropna(subset=["casos"])
        df_inc = df.dropna(subset=["incidencia"])
        idx_max = df_casos["casos"].idxmax() if not df_casos.empty else None
        idx_inc = df_inc["incidencia"].idxmax() if not df_inc.empty else None

        muni_mas_casos = None
        if idx_max is not None:
            muni_mas_casos = {
                "nombre": df.loc[idx_max, "municipio"],
                "casos": int(df.loc[idx_max, "casos"]),
            }
        muni_mayor_inc = None
        if idx_inc is not None:
            muni_mayor_inc = {
                "nombre": df.loc[idx_inc, "municipio"],
                "incidencia_x100k": float(df.loc[idx_inc, "incidencia"]),
            }

        _remember(tool_context, anio=int(anio))
        return _ok(
            anio=int(anio),
            total_casos=total_casos,
            poblacion_estimada=poblacion,
            incidencia_departamental_x100k=(
                round(incidencia_dpto, 2) if incidencia_dpto is not None else None
            ),
            n_municipios=int(df.shape[0]),
            municipio_mas_casos=muni_mas_casos,
            municipio_mayor_incidencia=muni_mayor_inc,
        )
    except Exception as exc:
        return _err(f"Error generando resumen anual: {exc}")


# ---------------------------------------------------------------------------
# Tools nuevas: estado de la conversacion (Paso 1: Session & State)
# ---------------------------------------------------------------------------

def mostrar_contexto(tool_context: ToolContext) -> dict:
    """Muestra el contexto actual de la conversacion (state).

    Util cuando el usuario pregunta "que estabamos viendo?", "recuerdas
    el ultimo municipio?", o cuando el agente necesita autoexplicarse
    su propio estado para depurar.
    """
    state = tool_context.state
    return _ok(
        last_municipio=state.get(STATE_LAST_MUNI),
        last_anio=state.get(STATE_LAST_ANIO),
        metrica_preferida=state.get(STATE_METRICA, "casos"),
    )


def establecer_preferencia(metrica_default: str, tool_context: ToolContext) -> dict:
    """Guarda la metrica preferida del usuario para los siguientes turnos.

    Args:
        metrica_default: "casos" o "incidencia". Una vez fijada, las tools
            como top_municipios la usan automaticamente cuando el usuario
            no especifique otra.
    """
    if metrica_default not in {"casos", "incidencia"}:
        return _err("metrica_default debe ser 'casos' o 'incidencia'.")
    tool_context.state[STATE_METRICA] = metrica_default
    return _ok(
        metrica_preferida=metrica_default,
        mensaje=f"Listo, ahora reportare por defecto en {metrica_default}.",
    )
