import numpy as np
import pandas as pd


def limpiar_datos(gdf):
    gdf = gdf.copy()
    gdf["MPIO_CNMBR"] = gdf["MPIO_CNMBR"].astype(str).str.upper().str.strip()
    gdf["año"] = pd.to_numeric(gdf["año"], errors="coerce").astype("Int64")
    gdf["conteo_dengue"] = pd.to_numeric(gdf["conteo_dengue"], errors="coerce")
    return gdf


def construir_pivot(gdf):
    pivot = pd.pivot_table(
        gdf.drop(columns="geom"),
        index=["MPIO_CCDGO", "MPIO_CNMBR"],
        columns="año",
        values="conteo_dengue",
        aggfunc="sum",
        fill_value=0,
    ).reset_index()
    pivot.columns.name = None

    pivot.columns = [
        f"dengue_{int(col)}" if isinstance(col, (int, float, np.integer, np.floating)) else col
        for col in pivot.columns
    ]
    return pivot


def columnas_anio(pivot):
    return [col for col in pivot.columns if str(col).startswith("dengue_")]


def calcular_priorizacion(pivot):
    cols = columnas_anio(pivot)
    result = pivot.copy()
    result["total"] = result[cols].sum(axis=1)
    return result.sort_values("total", ascending=False).reset_index(drop=True)
