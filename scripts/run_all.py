"""
Ejecuta el análisis completo de dengue.

Uso:
    python scripts/run_all.py
    python scripts/run_all.py --anio 2023
    python scripts/run_all.py --anio 2023 --municipio PALMIRA
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import ejecutar


def main():
    parser = argparse.ArgumentParser(description="Análisis de dengue Valle del Cauca")
    parser.add_argument("--anio",      type=int,   default=None, help="Año de referencia (default: ANIO_DEFAULT del .env)")
    parser.add_argument("--municipio", type=str,   default=None, help="Municipio para serie temporal (default: MUNICIPIO_DEFAULT del .env)")
    parser.add_argument("--salida",    type=str,   default=None, help="Ruta de salida (default: RUTA_SALIDA del .env)")
    args = parser.parse_args()

    ejecutar(anio=args.anio, municipio=args.municipio, ruta_salida=args.salida)


if __name__ == "__main__":
    main()
