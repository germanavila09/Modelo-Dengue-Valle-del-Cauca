import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.db import crear_engine


def main():
    engine = crear_engine()
    with engine.connect() as conn:
        version = conn.exec_driver_sql("SELECT version()").scalar()
    print("Conexion OK")
    print(version)


if __name__ == "__main__":
    main()
