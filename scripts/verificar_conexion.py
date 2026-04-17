"""
Verifica la conexión a PostgreSQL y la estructura de la tabla esperada.

Uso:
    python scripts/verificar_conexion.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from sqlalchemy import text

from src.config import DB_CONFIG, SCHEMA, TABLE
from src.db import crear_engine


def main():
    print(f"Conectando a {DB_CONFIG['host']}:{DB_CONFIG['port']} / {DB_CONFIG['database']}...")

    try:
        engine = crear_engine()
        with engine.connect() as conn:
            db = conn.execute(text("SELECT current_database();")).scalar()
            print(f"  Base de datos activa: {db}")
    except Exception as e:
        print(f"  ERROR de conexión: {e}")
        sys.exit(1)

    print(f"\nVerificando tabla {SCHEMA}.{TABLE}...")

    query = f"""
    SELECT column_name, data_type
    FROM information_schema.columns
    WHERE table_schema = '{SCHEMA}' AND table_name = '{TABLE}'
    ORDER BY ordinal_position;
    """

    try:
        cols = pd.read_sql(query, engine)
        if cols.empty:
            print(f"  ERROR: tabla '{SCHEMA}.{TABLE}' no encontrada.")
            sys.exit(1)
        print(f"  Columnas encontradas ({len(cols)}):")
        for _, row in cols.iterrows():
            print(f"    - {row['column_name']} ({row['data_type']})")
    except Exception as e:
        print(f"  ERROR al consultar estructura: {e}")
        sys.exit(1)

    print("\nConexión y estructura verificadas correctamente.")


if __name__ == "__main__":
    main()
