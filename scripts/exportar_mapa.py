"""
Genera el mapa HTML interactivo para un año dado.

Uso:
    python scripts/exportar_mapa.py
    python scripts/exportar_mapa.py --anio 2023
    python scripts/exportar_mapa.py --anio 2023 --salida ruta/salida
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import ANIO, RUTA_SALIDA
from src.db import cargar_datos, cargar_puntos_calor, crear_engine
from src.mapa import generar_mapa_html
from src.transform import limpiar_datos


def main():
    parser = argparse.ArgumentParser(description="Exportar mapa HTML de dengue")
    parser.add_argument("--anio",   type=int, default=None, help="Año de referencia (default: ANIO_DEFAULT del .env)")
    parser.add_argument("--salida", type=str, default=None, help="Ruta de salida (default: RUTA_SALIDA del .env)")
    args = parser.parse_args()

    anio_default = args.anio or ANIO
    ruta_salida  = args.salida or RUTA_SALIDA

    print("Cargando datos...")
    engine = crear_engine()
    gdf = limpiar_datos(cargar_datos(engine))
    anios_disponibles = sorted(gdf["año"].dropna().astype(int).unique().tolist())

    if anio_default not in anios_disponibles:
        print(f"ERROR: año {anio_default} no disponible. Anos validos: {anios_disponibles}")
        sys.exit(1)

    print(f"Cargando puntos de calor...")
    puntos_df = cargar_puntos_calor(engine)

    print(f"Generando mapa para {anio_default}...")
    ruta = generar_mapa_html(gdf, anios_disponibles, ruta_salida, anio_default=anio_default, puntos_df=puntos_df)
    print(f"Mapa guardado en: {ruta}")


if __name__ == "__main__":
    main()
