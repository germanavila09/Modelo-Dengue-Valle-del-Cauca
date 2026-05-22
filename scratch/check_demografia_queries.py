import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(dotenv_path="e:/laboratorio_TerrarIA/observatorios/observatorio_geosalud/.env")
db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", 5432))
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASSWORD", "postgres")

url = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/terrarIA"
engine = create_engine(url)

with engine.connect() as conn:
    print("--- 1. Single municipality population total (e.g. ZARZAL) ---")
    query1 = text("""
        SELECT m.nombre, m.codigo_dane, v.poblacion_total, v.poblacion_masculina, v.poblacion_femenina, v.pct_femenino
        FROM demografia.v_poblacion_municipio_total v
        JOIN demografia.dim_municipio m ON v.id_municipio = m.id_municipio
        WHERE m.nombre_normalizado = 'ZARZAL';
    """)
    print(conn.execute(query1).fetchone())

    print("\n--- 2. Single municipality cycle of life counts (e.g. ZARZAL) ---")
    query2 = text("""
        SELECT cv.nombre AS ciclo_vida, SUM(p.cantidad) AS total,
               SUM(CASE WHEN p.sexo = 'M' THEN p.cantidad ELSE 0 END) AS masculino,
               SUM(CASE WHEN p.sexo = 'F' THEN p.cantidad ELSE 0 END) AS femenino
        FROM demografia.pob_ciclo_vida p
        JOIN demografia.dim_municipio m ON p.id_municipio = m.id_municipio
        JOIN demografia.dim_ciclo_vida cv ON p.id_ciclo = cv.id_ciclo
        WHERE m.nombre_normalizado = 'ZARZAL'
        GROUP BY cv.orden, cv.nombre
        ORDER BY cv.orden;
    """)
    for row in conn.execute(query2).fetchall():
        print(row)

    print("\n--- 3. Department totals (VALLE DEL CAUCA) ---")
    query3 = text("""
        SELECT SUM(poblacion_total) as total,
               SUM(poblacion_masculina) as masc,
               SUM(poblacion_femenina) as fem
        FROM demografia.v_poblacion_municipio_total;
    """)
    print(conn.execute(query3).fetchone())

    print("\n--- 4. Department cycle of life counts (VALLE DEL CAUCA) ---")
    query4 = text("""
        SELECT cv.nombre AS ciclo_vida, SUM(p.cantidad) AS total,
               SUM(CASE WHEN p.sexo = 'M' THEN p.cantidad ELSE 0 END) AS masculino,
               SUM(CASE WHEN p.sexo = 'F' THEN p.cantidad ELSE 0 END) AS femenino
        FROM demografia.pob_ciclo_vida p
        JOIN demografia.dim_ciclo_vida cv ON p.id_ciclo = cv.id_ciclo
        GROUP BY cv.orden, cv.nombre
        ORDER BY cv.orden;
    """)
    for row in conn.execute(query4).fetchall():
        print(row)
