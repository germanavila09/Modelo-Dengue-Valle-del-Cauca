"""
Genera el mapa HTML interactivo para un año dado.

Uso:
    python scripts/exportar_mapa.py          # usa ANIO_DEFAULT del .env
    python scripts/exportar_mapa.py 2023     # año específico
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.config import ANIO, RUTA_SALIDA
from src.db import cargar_datos, crear_engine
from src.mapa import generar_mapa_html
from src.transform import limpiar_datos


def main():
    anio_default = int(sys.argv[1]) if len(sys.argv) > 1 else ANIO

    print("Cargando datos...")
    engine = crear_engine()
    gdf = limpiar_datos(cargar_datos(engine))

    anios_disponibles = sorted(gdf["año"].dropna().astype(int).unique().tolist())

    if anio_default not in anios_disponibles:
        print(f"ERROR: año {anio_default} no disponible. Años válidos: {anios_disponibles}")
        sys.exit(1)

    print(f"Generando mapa para {anio_default}...")
    ruta = generar_mapa_html(gdf, anios_disponibles, RUTA_SALIDA, anio_default=anio_default)
    print(f"Mapa guardado en: {ruta}")


if __name__ == "__main__":
    main()
