"""
Orquesta el análisis completo de dengue:
carga → limpia → pivot → gráficas → mapa HTML

Uso desde Python:
    from src.pipeline import ejecutar
    ejecutar()
"""

from pathlib import Path

from .config import ANIO, MUNICIPIO, RUTA_SALIDA
from .db import cargar_datos, crear_engine
from .mapa import generar_mapa_html
from .transform import calcular_priorizacion, construir_pivot, limpiar_datos
from .viz import (
    graficar_casos_por_anio,
    graficar_heatmap,
    graficar_incidencia_por_anio,
    graficar_scatter_poblacion_incidencia,
    graficar_serie_municipio,
    graficar_top_municipios,
    graficar_top_municipios_incidencia,
)


def ejecutar(anio=None, municipio=None, ruta_salida=None):
    anio = anio or ANIO
    municipio = municipio or MUNICIPIO
    ruta_salida = Path(ruta_salida or RUTA_SALIDA)
    ruta_graficas = ruta_salida / "graficas"
    ruta_graficas.mkdir(parents=True, exist_ok=True)

    # 1. Carga
    print("[1/5] Cargando datos desde PostgreSQL...")
    engine = crear_engine()
    gdf = limpiar_datos(cargar_datos(engine))
    anios = sorted(gdf["año"].dropna().astype(int).unique().tolist())
    print(f"      {len(gdf)} registros | {gdf['MPIO_CNMBR'].nunique()} municipios | {anios[0]}-{anios[-1]}")

    # 2. Pivot y priorización
    print("[2/5] Construyendo tabla pivote...")
    pivot = construir_pivot(gdf)
    priorizacion = calcular_priorizacion(pivot)
    priorizacion.to_csv(ruta_salida / "priorizacion_municipios.csv", index=False)
    print(f"      Exportada: {ruta_salida / 'priorizacion_municipios.csv'}")

    # 3. Gráficas
    print("[3/5] Generando graficas...")
    _guardar(graficar_casos_por_anio(gdf),                        ruta_graficas / "casos_por_anio.png")
    _guardar(graficar_incidencia_por_anio(gdf),                   ruta_graficas / "incidencia_por_anio.png")
    _guardar(graficar_top_municipios(gdf, anio),                  ruta_graficas / f"top_municipios_{anio}.png")
    _guardar(graficar_top_municipios_incidencia(gdf, anio),       ruta_graficas / f"top_incidencia_{anio}.png")
    _guardar(graficar_heatmap(pivot),                             ruta_graficas / "heatmap.png")
    _guardar(graficar_scatter_poblacion_incidencia(gdf, anio),    ruta_graficas / f"scatter_poblacion_{anio}.png")
    fig_serie = graficar_serie_municipio(pivot, municipio)
    if fig_serie:
        _guardar(fig_serie, ruta_graficas / f"serie_{municipio.lower()}.png")

    # 4. Mapa HTML
    print("[4/5] Generando mapa HTML interactivo...")
    ruta_mapa = generar_mapa_html(gdf, anios, ruta_salida, anio_default=anio)

    # 5. Resumen
    print("[5/5] Resumen:")
    print(f"      Casos totales  : {gdf['conteo_dengue'].sum():,.0f}")
    print(f"      Año con mas casos: {gdf.groupby('año')['conteo_dengue'].sum().idxmax()}")
    print(f"      Municipio top  : {priorizacion.iloc[0]['MPIO_CNMBR']}")
    print(f"\nOutputs en: {ruta_salida}")

    return {
        "gdf": gdf,
        "pivot": pivot,
        "priorizacion": priorizacion,
        "ruta_mapa": ruta_mapa,
        "ruta_graficas": ruta_graficas,
    }


def _guardar(fig, ruta):
    fig.savefig(ruta, dpi=150, bbox_inches="tight")
    fig.clf()
    print(f"      Guardada: {ruta.name}")
