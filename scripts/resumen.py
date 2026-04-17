"""
Imprime un resumen estadístico de los datos de dengue en consola.

Uso:
    python scripts/resumen.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db import cargar_datos, crear_engine
from src.transform import calcular_priorizacion, construir_pivot, limpiar_datos


def main():
    print("Cargando datos...")
    engine = crear_engine()
    gdf = limpiar_datos(cargar_datos(engine))

    anios = sorted(gdf["año"].dropna().astype(int).unique().tolist())

    print("\n-- Resumen general --------------------------")
    print(f"  Registros      : {len(gdf)}")
    print(f"  Municipios     : {gdf['MPIO_CNMBR'].nunique()}")
    print(f"  Anos           : {anios[0]} - {anios[-1]}")
    print(f"  Casos totales  : {gdf['conteo_dengue'].sum():,.0f}")
    print(f"  Nulos (casos)  : {gdf['conteo_dengue'].isna().sum()}")

    print("\n-- Casos por ano ----------------------------")
    por_anio = gdf.groupby("año")["conteo_dengue"].sum().sort_index()
    for anio, casos in por_anio.items():
        barra = "#" * int(casos / por_anio.max() * 30)
        print(f"  {anio}  {barra} {casos:,.0f}")

    print("\n-- Incidencia promedio por ano (x 100k) -----")
    inc_anio = gdf.groupby("año")["incidencia_dengue"].mean().sort_index()
    for anio, inc in inc_anio.items():
        barra = "#" * int(inc / inc_anio.max() * 30)
        print(f"  {anio}  {barra} {inc:,.1f}")

    print("\n-- Top 5 por carga historica (casos) --------")
    pivot = construir_pivot(gdf)
    top5 = calcular_priorizacion(pivot).head(5)
    for _, row in top5.iterrows():
        print(f"  {row['MPIO_CNMBR']:<30} {row['total']:,.0f} casos")

    print("\n-- Top 5 por incidencia promedio ------------")
    inc_mun = (
        gdf.groupby("MPIO_CNMBR")["incidencia_dengue"]
        .mean()
        .sort_values(ascending=False)
        .head(5)
    )
    for mun, inc in inc_mun.items():
        print(f"  {mun:<30} {inc:,.1f} x 100k")

    print()


if __name__ == "__main__":
    main()
