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
    casos_totales = gdf["conteo_dengue"].sum()
    nulos = gdf["conteo_dengue"].isna().sum()

    print("\n── Resumen general ─────────────────────────")
    print(f"  Registros      : {len(gdf)}")
    print(f"  Municipios     : {gdf['MPIO_CNMBR'].nunique()}")
    print(f"  Años           : {anios[0]} – {anios[-1]}")
    print(f"  Casos totales  : {casos_totales:,.0f}")
    print(f"  Valores nulos  : {nulos}")

    print("\n── Casos por año ───────────────────────────")
    por_anio = (
        gdf.groupby("año")["conteo_dengue"]
        .sum()
        .sort_index()
    )
    for anio, casos in por_anio.items():
        barra = "█" * int(casos / por_anio.max() * 30)
        print(f"  {anio}  {barra} {casos:,.0f}")

    print("\n── Top 5 municipios (carga histórica) ──────")
    pivot = construir_pivot(gdf)
    top5 = calcular_priorizacion(pivot).head(5)
    for _, row in top5.iterrows():
        print(f"  {row['MPIO_CNMBR']:<30} {row['total']:,.0f}")

    print()


if __name__ == "__main__":
    main()
