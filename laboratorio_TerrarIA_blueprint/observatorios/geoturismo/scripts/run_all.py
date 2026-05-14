import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.pipeline import ejecutar


def main():
    parser = argparse.ArgumentParser(description="Pipeline GeoTurismo")
    parser.add_argument("--anio", type=int, default=None)
    parser.add_argument("--municipio", type=str, default=None)
    parser.add_argument("--salida", type=str, default=None)
    args = parser.parse_args()
    ejecutar(anio=args.anio, municipio=args.municipio, ruta_salida=args.salida)


if __name__ == "__main__":
    main()
