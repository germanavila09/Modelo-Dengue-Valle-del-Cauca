import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(dotenv_path="e:/laboratorio_TerrarIA/observatorios/observatorio_geosalud/.env")
db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", 5432))
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASSWORD", "postgres")

url_dengue = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/dengue"
url_terr = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/terrarIA"

e_dengue = create_engine(url_dengue)
e_terr = create_engine(url_terr)

with e_dengue.connect() as conn:
    print("Dengue table names like ALCALA or BUGA:")
    res = conn.execute(text("SELECT DISTINCT \"MPIO_CNMBR\" FROM public.valle_mun WHERE \"MPIO_CNMBR\" LIKE '%ALCAL%' OR \"MPIO_CNMBR\" LIKE '%BUG%';")).fetchall()
    for r in res:
        print(repr(r[0]))

with e_terr.connect() as conn:
    print("\nTerraria dim_municipio names like ALCALA or BUGA:")
    res = conn.execute(text("SELECT nombre, nombre_normalizado, codigo_dane FROM demografia.dim_municipio WHERE nombre_normalizado LIKE '%ALCAL%' OR nombre_normalizado LIKE '%BUG%';")).fetchall()
    for r in res:
        print("nombre:", repr(r[0]), "normalizado:", repr(r[1]), "dane:", repr(r[2]))
