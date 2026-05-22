"""Tools de visualizacion del agente ADK del Observatorio GeoSalud.

Genera graficas con Seaborn/Matplotlib y las guarda como ADK Artifacts (PNG).

## Caché de gráficas (sesión)

Cada tool usa un nombre de archivo **determinista** basado en sus parámetros
(ej. ``top10_casos_2024.png``). Antes de regenerar, ``_get_or_create_artifact``
revisa ``state["_chart_cache"]``:

- **Hit** → devuelve la referencia del artifact ya guardado. No toca la DB.
- **Miss** → llama a la función de figura, guarda el artifact y registra la clave.

La clave ``reutilizada: True/False`` en el dict de respuesta le indica al agente
si usó o no la caché, para que pueda comunicárselo al usuario.

Patrón oficial de ADK para artifacts:
https://google.github.io/adk-docs/artifacts/
"""

from __future__ import annotations

import io
import sys
import unicodedata
from pathlib import Path
from typing import Any, Callable

# sys.path para importar src.* (mismo patrón que tools.py)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import seaborn as sns  # noqa: E402

sns.set_theme(style="whitegrid", palette="tab10")

from google.adk.tools import ToolContext  # noqa: E402
from google.genai import types as genai_types  # noqa: E402

from src.db import cargar_datos  # noqa: E402
from src.viz import (  # noqa: E402
    graficar_casos_por_anio,
    graficar_scatter_poblacion_incidencia,
    graficar_top_municipios,
    graficar_top_municipios_incidencia,
)


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------

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


def _norm_municipios(municipios: list[str] | str) -> list[str]:
    """Normaliza y elimina duplicados conservando el orden recibido."""
    if isinstance(municipios, str):
        municipios = municipios.replace(" y ", ",").split(",")
    vistos: set[str] = set()
    normalizados: list[str] = []
    for nombre in municipios:
        muni = _norm_municipio(str(nombre))
        if muni and muni not in vistos:
            vistos.add(muni)
            normalizados.append(muni)
    return normalizados


def _figure_to_png_bytes(fig) -> bytes:
    """Serializa una Figure o FacetGrid de seaborn a PNG en memoria."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=120, bbox_inches="tight")
    plt.close("all")
    return buf.getvalue()


def _munis_slug(municipios: list[str]) -> str:
    """Slug de una lista de municipios: ordena, une con guion, acorta a 60 chars."""
    slug = "-".join(sorted(municipios))
    return slug[:60]


# ---------------------------------------------------------------------------
# Caché de gráficas
# ---------------------------------------------------------------------------

# Clave en session state donde se guarda el registro de artifacts ya generados.
# Formato: { "nombre_archivo.png": version_int }
_CACHE_STATE_KEY = "_chart_cache"


async def _get_or_create_artifact(
    tool_context: ToolContext,
    filename: str,
    fig_factory: Callable,
) -> dict:
    """Devuelve el artifact existente o genera uno nuevo si no existe.

    Antes de renderizar cualquier figura, busca ``filename`` en
    ``state["_chart_cache"]``. Si existe, retorna la referencia sin tocar
    la base de datos ni matplotlib.

    Args:
        tool_context: Contexto del agente (acceso a state y artifacts).
        filename: Nombre determinista del PNG (codifica tipo + parámetros).
        fig_factory: Callable sin argumentos → figura matplotlib/seaborn.
                     Solo se invoca en cache MISS.

    Returns:
        Dict con ``artifact_filename``, ``artifact_version``, ``size_bytes``
        y ``reutilizada`` (bool).
    """
    cache: dict = tool_context.state.setdefault(_CACHE_STATE_KEY, {})

    if filename in cache:
        # ── Cache HIT: no se toca la DB ni matplotlib ─────────────────────
        return {
            "artifact_filename": filename,
            "artifact_version": cache[filename],
            "size_bytes": None,
            "reutilizada": True,
        }

    # ── Cache MISS: generar, guardar y registrar ───────────────────────────
    fig = fig_factory()
    png_bytes = _figure_to_png_bytes(fig)
    part = genai_types.Part.from_bytes(data=png_bytes, mime_type="image/png")
    version = await tool_context.save_artifact(filename=filename, artifact=part)

    cache[filename] = version
    tool_context.state[_CACHE_STATE_KEY] = cache

    return {
        "artifact_filename": filename,
        "artifact_version": version,
        "size_bytes": len(png_bytes),
        "reutilizada": False,
    }


# ---------------------------------------------------------------------------
# Tools de visualización
# ---------------------------------------------------------------------------

async def grafica_casos_por_anio(tool_context: ToolContext) -> dict:
    """Genera la grafica de barras de casos totales de dengue por anio (2019-2026).

    Util cuando el usuario pide la "evolucion general", "tendencia anual"
    o "como ha variado el dengue en el Valle".
    """
    try:
        # Sin parámetros → nombre siempre igual → máximo reutilizable
        filename = "casos_por_anio.png"

        def _make():
            return graficar_casos_por_anio(cargar_datos())

        meta = await _get_or_create_artifact(tool_context, filename, _make)
        return _ok(
            grafica="casos_por_anio",
            descripcion="Casos totales de dengue por anio en el Valle del Cauca",
            **meta,
        )
    except Exception as exc:
        return _err(f"Error generando grafica de casos por anio: {exc}")


async def grafica_top_municipios(
    anio: int,
    tool_context: ToolContext,
    n: int = 10,
    metrica: str = "",
) -> dict:
    """Grafica de barras horizontales con el top N municipios de un anio.

    Args:
        anio: Anio a graficar (ej. 2024).
        n: Cantidad de municipios (1-42). Default 10.
        metrica: "casos" o "incidencia". Si llega vacia se usa
            ``state.metrica_preferida`` (default "casos").

    Util para "muestrame los mas afectados", "comparativa visual",
    "ranking grafico", "ver el top en grafica".
    """
    try:
        if not metrica:
            metrica = tool_context.state.get("metrica_preferida", "casos")
        if metrica not in {"casos", "incidencia"}:
            return _err("metrica debe ser 'casos' o 'incidencia'.")
        n = max(1, min(int(n), 42))
        anio = int(anio)

        # Parámetros en el nombre: top10_casos_2024.png
        filename = f"top{n}_{metrica}_{anio}.png"

        def _make():
            gdf = cargar_datos()
            if metrica == "casos":
                return graficar_top_municipios(gdf, anio=anio, n=n)
            return graficar_top_municipios_incidencia(gdf, anio=anio, n=n)

        meta = await _get_or_create_artifact(tool_context, filename, _make)
        return _ok(
            grafica="top_municipios",
            anio=anio,
            n=n,
            metrica=metrica,
            descripcion=(
                f"Top {n} municipios por {metrica} en {anio}"
                f"{' (incidencia x100k hab.)' if metrica == 'incidencia' else ''}"
            ),
            **meta,
        )
    except Exception as exc:
        return _err(f"Error generando grafica top municipios: {exc}")


async def grafica_top_municipios_todos_anios(
    tool_context: ToolContext,
    n: int = 5,
    metrica: str = "",
) -> dict:
    """Grafica la evolucion historica del top N de municipios del periodo.

    Args:
        n: Cantidad de municipios a incluir (1-12). Default 5.
        metrica: "casos" o "incidencia". Si llega vacia se usa
            ``state.metrica_preferida`` (default "casos").

    Para "top 5 en todos los anios", "ranking historico", o visualizaciones
    donde no se pide un anio puntual sino el top N a traves del tiempo.
    """
    try:
        if not metrica:
            metrica = tool_context.state.get("metrica_preferida", "casos")
        if metrica not in {"casos", "incidencia"}:
            return _err("metrica debe ser 'casos' o 'incidencia'.")
        n = max(1, min(int(n), 12))

        filename = f"top{n}_{metrica}_historico.png"

        # Calcular top_munis fuera de _make para guardarlo en el state de sesión
        gdf = cargar_datos()
        col_y = "conteo_dengue" if metrica == "casos" else "incidencia_dengue"
        etiqueta_y = "Casos confirmados" if metrica == "casos" else "Incidencia x100k hab."
        resumen_col = "total_casos" if metrica == "casos" else "incidencia_promedio_x100k"

        if metrica == "casos":
            ranking_df = (
                gdf.groupby("MPIO_CNMBR", as_index=False)[col_y]
                .sum()
                .rename(columns={col_y: resumen_col})
                .sort_values(resumen_col, ascending=False)
                .head(n)
            )
        else:
            ranking_df = (
                gdf.dropna(subset=[col_y])
                .groupby("MPIO_CNMBR", as_index=False)[col_y]
                .mean()
                .rename(columns={col_y: resumen_col})
                .sort_values(resumen_col, ascending=False)
                .head(n)
            )

        top_munis = ranking_df["MPIO_CNMBR"].tolist()

        def _make():
            df = (
                gdf[gdf["MPIO_CNMBR"].isin(top_munis)]
                .sort_values(["MPIO_CNMBR", "anio"])[["MPIO_CNMBR", "anio", col_y]]
                .copy()
            )
            g = sns.relplot(
                data=df,
                x="anio",
                y=col_y,
                hue="MPIO_CNMBR",
                kind="line",
                marker="o",
                height=5,
                aspect=2.0,
            )
            g.set_axis_labels("Año", etiqueta_y)
            g.figure.suptitle(
                f"Top {n} municipios por {metrica} — evolución histórica", y=1.02
            )
            g.legend.set_title("Municipio")
            return g

        meta = await _get_or_create_artifact(tool_context, filename, _make)
        tool_context.state["last_series_municipios"] = top_munis
        tool_context.state["last_metrica"] = metrica
        tool_context.state["last_visual"] = "series"
        if top_munis:
            tool_context.state["last_municipio"] = top_munis[-1]

        return _ok(
            grafica="top_municipios_todos_anios",
            n=n,
            metrica=metrica,
            descripcion=f"Evolucion historica del top {n} municipios por {metrica}",
            **meta,
        )
    except Exception as exc:
        return _err(f"Error generando top historico de municipios: {exc}")


async def grafica_serie_municipio(
    municipio: str,
    tool_context: ToolContext,
) -> dict:
    """Grafica de linea con la serie historica de casos de un municipio.

    Args:
        municipio: Nombre del municipio (ej. "CALI"). Se normaliza a
            mayusculas.

    Util para "evolucion historica de X", "como ha evolucionado X",
    "muestrame el grafico de X en el tiempo".
    """
    try:
        muni = _norm_municipio(municipio)
        filename = f"serie_{muni.lower()}.png"

        def _make():
            gdf = cargar_datos()
            df = (
                gdf[gdf["MPIO_CNMBR"] == muni]
                .sort_values("anio")[["anio", "conteo_dengue", "incidencia_dengue"]]
                .copy()
            )
            if df.empty:
                raise ValueError(
                    f"No hay datos para {muni!r}. "
                    "Usa listar_municipios para verificar el nombre."
                )
            g = sns.relplot(
                data=df,
                x="anio",
                y="conteo_dengue",
                kind="line",
                marker="o",
                height=5,
                aspect=2.2,
            )
            g.set_axis_labels("Año", "Casos confirmados")
            g.figure.suptitle(f"Serie histórica de dengue — {muni}", y=1.02)
            return g

        meta = await _get_or_create_artifact(tool_context, filename, _make)
        tool_context.state["last_municipio"] = muni
        tool_context.state["last_series_municipios"] = [muni]
        tool_context.state["last_metrica"] = "casos"
        tool_context.state["last_visual"] = "series"

        return _ok(
            grafica="serie_municipio",
            municipio=muni,
            descripcion=f"Serie historica de casos confirmados de dengue en {muni}",
            **meta,
        )
    except Exception as exc:
        return _err(f"Error generando serie del municipio: {exc}")


async def grafica_series_municipios(
    municipios: list[str],
    tool_context: ToolContext,
    metrica: str = "",
) -> dict:
    """Grafica comparativa de la serie historica para varios municipios.

    Args:
        municipios: Lista de municipios a comparar (ej. ["CALI", "PALMIRA"]).
            Se normalizan a mayusculas. Maximo 12 por legibilidad.
        metrica: "casos" o "incidencia". Si llega vacia se usa
            ``state.metrica_preferida`` (default "casos").

    Util para "compara Cali y Palmira", "grafica varios municipios",
    "muestrame la evolucion de Cali, Palmira y Buenaventura".
    """
    try:
        if not municipios:
            return _err("Debes enviar al menos un municipio.")
        if not metrica:
            metrica = tool_context.state.get("metrica_preferida", "casos")
        if metrica not in {"casos", "incidencia"}:
            return _err("metrica debe ser 'casos' o 'incidencia'.")

        municipios_norm = _norm_municipios(municipios)
        if not municipios_norm:
            return _err("No se recibieron nombres de municipios validos.")

        max_mun = 12
        graficados = municipios_norm[:max_mun]
        omitidos = municipios_norm[max_mun:]

        # Slug ordenado → misma lista en distinto orden → mismo archivo
        filename = f"series_{_munis_slug(graficados)}_{metrica}.png"

        def _make():
            gdf = cargar_datos()
            col_y = "conteo_dengue" if metrica == "casos" else "incidencia_dengue"
            etiqueta_y = "Casos confirmados" if metrica == "casos" else "Incidencia x100k hab."

            df = (
                gdf[gdf["MPIO_CNMBR"].isin(graficados)]
                .sort_values(["MPIO_CNMBR", "anio"])[["MPIO_CNMBR", "anio", col_y]]
                .copy()
            )
            encontrados = df["MPIO_CNMBR"].dropna().unique().tolist()
            if df.empty:
                raise ValueError(
                    "No hay datos para los municipios solicitados. "
                    "Usa listar_municipios para verificar los nombres."
                )
            g = sns.relplot(
                data=df,
                x="anio",
                y=col_y,
                hue="MPIO_CNMBR",
                kind="line",
                marker="o",
                height=5,
                aspect=2.0,
            )
            g.set_axis_labels("Año", etiqueta_y)
            g.figure.suptitle(
                f"Serie histórica de dengue por municipio — {metrica}", y=1.02
            )
            g.legend.set_title("Municipio")
            return g

        meta = await _get_or_create_artifact(tool_context, filename, _make)

        tool_context.state["last_series_municipios"] = graficados
        tool_context.state["last_metrica"] = metrica
        tool_context.state["last_visual"] = "series"
        if graficados:
            tool_context.state["last_municipio"] = graficados[-1]

        return _ok(
            grafica="series_municipios",
            municipios=graficados,
            municipios_omitidos=omitidos,
            metrica=metrica,
            descripcion=(
                f"Serie historica comparativa por {metrica} para "
                f"{len(graficados)} municipios"
            ),
            **meta,
        )
    except Exception as exc:
        return _err(f"Error generando series de municipios: {exc}")


async def grafica_facet_municipios(
    municipios: list[str],
    tool_context: ToolContext,
    metrica: str = "",
) -> dict:
    """Panel facetado con un subplot individual por municipio (hasta 12).

    Args:
        municipios: Lista de municipios (ej. ["CALI", "PALMIRA",
            "BUENAVENTURA"]). Se normalizan a mayusculas. Maximo 12.
        metrica: "casos" o "incidencia". Si llega vacia se usa
            ``state.metrica_preferida`` (default "casos").

    Util cuando grafica_series_municipios queda ilegible por muchas lineas
    superpuestas, o cuando el usuario pide "uno por uno", "por separado",
    "panel" o "faceta". Cada municipio tiene su propio eje Y.
    """
    try:
        if not municipios:
            return _err("Debes enviar al menos un municipio.")
        if not metrica:
            metrica = tool_context.state.get("metrica_preferida", "casos")
        if metrica not in {"casos", "incidencia"}:
            return _err("metrica debe ser 'casos' o 'incidencia'.")

        municipios_norm = _norm_municipios(municipios)
        if not municipios_norm:
            return _err("No se recibieron nombres de municipios validos.")

        max_mun = 12
        graficados = municipios_norm[:max_mun]
        omitidos = municipios_norm[max_mun:]

        filename = f"facet_{_munis_slug(graficados)}_{metrica}.png"

        def _make():
            gdf = cargar_datos()
            col_y = "conteo_dengue" if metrica == "casos" else "incidencia_dengue"
            etiqueta_y = "Casos confirmados" if metrica == "casos" else "Incidencia x100k hab."

            df = (
                gdf[gdf["MPIO_CNMBR"].isin(graficados)]
                .sort_values(["MPIO_CNMBR", "anio"])[["MPIO_CNMBR", "anio", col_y]]
                .copy()
            )
            if df.empty:
                raise ValueError(
                    "No hay datos para los municipios solicitados. "
                    "Usa listar_municipios para verificar los nombres."
                )
            col_wrap = min(3, len(graficados))
            g = sns.relplot(
                data=df,
                x="anio",
                y=col_y,
                col="MPIO_CNMBR",
                kind="line",
                marker="o",
                col_wrap=col_wrap,
                height=3,
                aspect=1.4,
                facet_kws={"sharey": False},
            )
            g.set_axis_labels("Año", etiqueta_y)
            g.set_titles("{col_name}")
            g.figure.suptitle(
                f"Evolución histórica por municipio — {metrica}",
                y=1.02,
                fontsize=13,
            )
            return g

        meta = await _get_or_create_artifact(tool_context, filename, _make)

        tool_context.state["last_series_municipios"] = graficados
        tool_context.state["last_metrica"] = metrica
        tool_context.state["last_visual"] = "series"
        if graficados:
            tool_context.state["last_municipio"] = graficados[-1]

        return _ok(
            grafica="facet_municipios",
            municipios=graficados,
            municipios_omitidos=omitidos,
            metrica=metrica,
            descripcion=(
                f"Panel facetado de {len(graficados)} municipios por {metrica} "
                f"(un subplot por municipio, ejes Y independientes)"
            ),
            **meta,
        )
    except Exception as exc:
        return _err(f"Error generando panel facetado: {exc}")


async def grafica_poblacion_vs_incidencia(
    anio: int,
    tool_context: ToolContext,
) -> dict:
    """Scatter plot: poblacion (x) vs incidencia (y) por municipio en un anio.

    Args:
        anio: Anio a visualizar (ej. 2024).

    Util para "hay relacion entre tamanio del municipio e incidencia?",
    "muestrame poblacion vs incidencia", o correlacion poblacion-incidencia.
    """
    try:
        anio = int(anio)
        filename = f"scatter_pob_inc_{anio}.png"

        def _make():
            return graficar_scatter_poblacion_incidencia(cargar_datos(), anio=anio)

        meta = await _get_or_create_artifact(tool_context, filename, _make)
        tool_context.state["last_anio"] = anio

        return _ok(
            grafica="poblacion_vs_incidencia",
            anio=anio,
            descripcion=(
                f"Dispersion de poblacion vs incidencia (x100k hab.) "
                f"por municipio en {anio}"
            ),
            **meta,
        )
    except Exception as exc:
        return _err(f"Error generando scatter pob-incidencia: {exc}")