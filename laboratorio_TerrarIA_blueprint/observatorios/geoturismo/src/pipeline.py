from pathlib import Path

from .config import ANIO, MUNICIPIO, RUTA_SALIDA
from .db import cargar_datos, crear_engine
from .mapa import generar_mapa_html
from .modelo import construir_escenarios
from .transform import calcular_indice_oportunidad, calcular_priorizacion, construir_pivot, limpiar_datos
from .viz import graficar_top_destinos, graficar_visitantes_por_anio


def ejecutar(anio=None, municipio=None, ruta_salida=None):
    anio = anio or ANIO
    municipio = (municipio or MUNICIPIO).upper()
    ruta = Path(ruta_salida or RUTA_SALIDA)
    graficas = ruta / "graficas"
    ruta.mkdir(parents=True, exist_ok=True)
    graficas.mkdir(parents=True, exist_ok=True)

    engine = crear_engine()
    gdf = limpiar_datos(cargar_datos(engine))
    gdf = calcular_indice_oportunidad(gdf)
    pivot = construir_pivot(gdf)
    priorizacion = calcular_priorizacion(gdf)
    escenarios = construir_escenarios(priorizacion)

    gdf.to_csv(ruta / "indicadores_turisticos.csv", index=False)
    priorizacion.to_csv(ruta / "priorizacion_destinos.csv", index=False)
    escenarios.to_csv(ruta / "escenarios_turisticos.csv", index=False)

    graficar_visitantes_por_anio(gdf, graficas)
    graficar_top_destinos(priorizacion, graficas)
    ruta_mapa = generar_mapa_html(gdf, ruta)

    return {
        "gdf": gdf,
        "pivot": pivot,
        "priorizacion": priorizacion,
        "ruta_mapa": ruta_mapa,
        "municipio": municipio,
        "anio": anio,
    }
