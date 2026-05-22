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
import unicodedata
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
    # 1. Decomponer acentos (NFKD) y remover marcas combinadas
    normalized = unicodedata.normalize("NFKD", nombre.lower())
    clean_name = "".join(ch for ch in normalized if not unicodedata.combining(ch)).upper().strip()
    
    # 2. Mapeo de alias comunes
    aliases = {
        "BUGA": "GUADALAJARA DE BUGA",
        "SAN SANTIAGO DE CALI": "CALI",
        "SANTIAGO DE CALI": "CALI",
        "CALIMA EL DARIEN": "CALIMA",
        "CALIMA DARIEN": "CALIMA",
    }
    canonical = aliases.get(clean_name, clean_name)
    
    # 3. Mapeo específico de los 9 municipios con caracteres corruptos (?) en la tabla de dengue de PostgreSQL
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
    return dengue_corrupt_mapping.get(canonical, canonical)


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
            f'SELECT "MPIO_CNMBR" AS municipio, anio, '
            f'       poblacion, conteo_dengue, incidencia_dengue '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'WHERE "MPIO_CNMBR" = :muni AND anio = :anio;'
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
            f'WHERE anio = :anio AND {col} IS NOT NULL '
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
            f'SELECT anio, conteo_dengue AS casos, '
            f'       incidencia_dengue AS incidencia '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'WHERE "MPIO_CNMBR" = :muni '
            f'ORDER BY anio;'
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
            f'       poblacion, '
            f'       conteo_dengue AS casos, '
            f'       incidencia_dengue AS incidencia '
            f'FROM "{SCHEMA}"."{TABLE}" '
            f'WHERE anio = :anio;'
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


# ---------------------------------------------------------------------------
# Tools nuevas: demografia (PostgreSQL terrarIA DB)
# ---------------------------------------------------------------------------

def _normalize_muni_for_demografia(nombre: str) -> str:
    normalized = unicodedata.normalize("NFKD", nombre.lower())
    muni_upper = "".join(ch for ch in normalized if not unicodedata.combining(ch)).upper().strip()
    
    # Mapeo de alias comunes a nombres estándar en demografía (dim_municipio.nombre_normalizado)
    aliases = {
        "BUGA": "GUADALAJARA DE BUGA",
        "SAN SANTIAGO DE CALI": "CALI",
        "SANTIAGO DE CALI": "CALI",
        "CALIMA EL DARIEN": "CALIMA",
        "CALIMA DARIEN": "CALIMA",
    }
    return aliases.get(muni_upper, muni_upper)


def consultar_poblacion_municipio(municipio: str, tool_context: ToolContext) -> dict:
    """Consulta la poblacion total y por genero de un municipio o del departamento entero.

    Args:
        municipio: Nombre del municipio (ej. "Cali", "Alcalá", "Zarzal") o "Valle"/"Valle del Cauca" para el total.
    """
    try:
        muni_norm = _normalize_muni_for_demografia(municipio)
        is_valle = muni_norm in ("VALLE", "VALLE DEL CAUCA")
        
        engine = crear_engine()
        if is_valle:
            query = text("""
                SELECT 
                    'Valle del Cauca (Total)' AS municipio,
                    'VALLE' AS codigo_dane,
                    anio_referencia,
                    SUM(poblacion_total) AS poblacion_total,
                    SUM(poblacion_masculina) AS poblacion_masculina,
                    SUM(poblacion_femenina) AS poblacion_femenina,
                    ROUND((100.0 * SUM(poblacion_femenina)) / SUM(poblacion_total), 1) AS pct_femenino
                FROM demografia.v_poblacion_municipio_total
                WHERE anio_referencia = 2024
                GROUP BY anio_referencia;
            """)
            df = pd.read_sql(query, engine)
        else:
            query = text("""
                SELECT v.municipio, v.codigo_dane, v.anio_referencia, v.poblacion_total, v.poblacion_masculina, v.poblacion_femenina, v.pct_femenino
                FROM demografia.v_poblacion_municipio_total v
                JOIN demografia.dim_municipio m ON v.codigo_dane = m.codigo_dane
                WHERE m.nombre_normalizado = :muni_norm AND v.anio_referencia = 2024;
            """)
            df = pd.read_sql(query, engine, params={"muni_norm": muni_norm})

        if df.empty:
            return _err(f"No se encontro informacion demografica para el municipio: {municipio}")
        
        row = df.iloc[0].to_dict()
        _remember(tool_context, municipio=muni_norm)
        
        pct_fem = float(row["pct_femenino"])
        pct_masc = round(100.0 - pct_fem, 1)
        
        return _ok(
            municipio=row["municipio"],
            codigo_dane=row["codigo_dane"],
            anio_referencia=int(row["anio_referencia"]),
            poblacion_total=int(row["poblacion_total"]),
            poblacion_masculina=int(row["poblacion_masculina"]),
            poblacion_femenina=int(row["poblacion_femenina"]),
            pct_femenino=pct_fem,
            pct_masculino=pct_masc,
        )
    except Exception as exc:
        return _err(f"Error consultando poblacion: {exc}")


def consultar_poblacion_ciclo_vida(municipio: str, tool_context: ToolContext) -> dict:
    """Consulta la distribucion de poblacion por ciclo de vida y genero para un municipio o departamento.

    Args:
        municipio: Nombre del municipio (ej. "Cali", "Palmira") o "Valle"/"Valle del Cauca" para el total.
    """
    try:
        muni_norm = _normalize_muni_for_demografia(municipio)
        is_valle = muni_norm in ("VALLE", "VALLE DEL CAUCA")
        
        engine = crear_engine()
        if is_valle:
            query = text("""
                SELECT 
                    c.nombre AS ciclo_nombre,
                    pc.sexo,
                    SUM(pc.cantidad) AS cantidad
                FROM demografia.pob_ciclo_vida pc
                JOIN demografia.dim_ciclo_vida c ON pc.id_ciclo = c.id_ciclo
                WHERE pc.anio_referencia = 2024
                GROUP BY c.nombre, c.id_ciclo, pc.sexo
                ORDER BY c.id_ciclo, pc.sexo;
            """)
            df = pd.read_sql(query, engine)
        else:
            query = text("""
                SELECT 
                    c.nombre AS ciclo_nombre,
                    pc.sexo,
                    SUM(pc.cantidad) AS cantidad,
                    m.nombre AS municipio_nombre
                FROM demografia.pob_ciclo_vida pc
                JOIN demografia.dim_municipio m ON pc.id_municipio = m.id_municipio
                JOIN demografia.dim_ciclo_vida c ON pc.id_ciclo = c.id_ciclo
                WHERE m.nombre_normalizado = :muni_norm AND pc.anio_referencia = 2024
                GROUP BY c.nombre, c.id_ciclo, pc.sexo, m.nombre
                ORDER BY c.id_ciclo, pc.sexo;
            """)
            df = pd.read_sql(query, engine, params={"muni_norm": muni_norm})

        if df.empty:
            return _err(f"No se encontro informacion demografica por ciclo de vida para el municipio: {municipio}")
        
        # Obtener el nombre del municipio de la consulta
        df_muni_name = "Valle del Cauca (Total)" if is_valle else df.iloc[0]["municipio_nombre"]
        
        # Agrupar por ciclo de vida
        ciclos = {}
        for _, r in df.iterrows():
            c_name = r["ciclo_nombre"]
            sex = r["sexo"]
            qty = int(r["cantidad"])
            if c_name not in ciclos:
                ciclos[c_name] = {"total": 0, "masculino": 0, "femenino": 0}
            ciclos[c_name]["total"] += qty
            if sex == "M":
                ciclos[c_name]["masculino"] += qty
            else:
                ciclos[c_name]["femenino"] += qty

        ciclos_list = []
        for c_name, vals in ciclos.items():
            tot = vals["total"]
            m_qty = vals["masculino"]
            f_qty = vals["femenino"]
            pct_m = round((m_qty / tot * 100), 1) if tot > 0 else 0.0
            pct_f = round((f_qty / tot * 100), 1) if tot > 0 else 0.0
            ciclos_list.append({
                "ciclo": c_name,
                "total": tot,
                "hombres": m_qty,
                "mujeres": f_qty,
                "pct_hombres": pct_m,
                "pct_mujeres": pct_f
            })

        _remember(tool_context, municipio=muni_norm)
        return _ok(
            municipio=df_muni_name,
            ciclos=ciclos_list
        )
    except Exception as exc:
        return _err(f"Error consultando ciclos de vida: {exc}")


def consultar_piramide_poblacional(municipio: str, tool_context: ToolContext) -> dict:
    """Consulta la distribución de población en grupos quinquenales (pirámide poblacional) por género.

    Args:
        municipio: Nombre del municipio (ej. "Cali", "Buga") o "Valle"/"Valle del Cauca" para el total.
    """
    try:
        muni_norm = _normalize_muni_for_demografia(municipio)
        is_valle = muni_norm in ("VALLE", "VALLE DEL CAUCA")
        
        engine = crear_engine()
        if is_valle:
            query = text("""
                SELECT 
                    v.grupo_quinquenal,
                    v.sexo,
                    SUM(v.cantidad) AS cantidad,
                    v.orden
                FROM demografia.v_piramide_poblacional_municipio v
                WHERE v.anio_referencia = 2024
                GROUP BY v.grupo_quinquenal, v.sexo, v.orden
                ORDER BY v.orden, v.sexo;
            """)
            df = pd.read_sql(query, engine)
        else:
            query = text("""
                SELECT 
                    v.grupo_quinquenal,
                    v.sexo,
                    v.cantidad,
                    v.orden,
                    m.nombre AS municipio_nombre
                FROM demografia.v_piramide_poblacional_municipio v
                JOIN demografia.dim_municipio m ON v.codigo_dane = m.codigo_dane
                WHERE m.nombre_normalizado = :muni_norm AND v.anio_referencia = 2024
                ORDER BY v.orden, v.sexo;
            """)
            df = pd.read_sql(query, engine, params={"muni_norm": muni_norm})

        if df.empty:
            return _err(f"No se encontro piramide poblacional para el municipio: {municipio}")
        
        df_muni_name = "Valle del Cauca (Total)" if is_valle else df.iloc[0]["municipio_nombre"]
        
        piramide = {}
        for _, r in df.iterrows():
            g = r["grupo_quinquenal"]
            sex = r["sexo"]
            qty = int(r["cantidad"])
            if g not in piramide:
                piramide[g] = {"total": 0, "hombres": 0, "mujeres": 0, "orden": int(r["orden"])}
            piramide[g]["total"] += qty
            if sex == "M":
                piramide[g]["hombres"] += qty
            else:
                piramide[g]["mujeres"] += qty

        sorted_piramide = sorted(
            [{"grupo": g, **vals} for g, vals in piramide.items()],
            key=lambda x: x["orden"]
        )
        
        for item in sorted_piramide:
            del item["orden"]
            tot = item["total"]
            item["pct_hombres"] = round((item["hombres"] / tot * 100), 1) if tot > 0 else 0.0
            item["pct_mujeres"] = round((item["mujeres"] / tot * 100), 1) if tot > 0 else 0.0

        _remember(tool_context, municipio=muni_norm)
        return _ok(
            municipio=df_muni_name,
            piramide=sorted_piramide
        )
    except Exception as exc:
        return _err(f"Error consultando piramide: {exc}")
