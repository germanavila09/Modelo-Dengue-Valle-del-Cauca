import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(dotenv_path="e:/laboratorio_TerrarIA/observatorios/observatorio_geosalud/.env")
db_host = os.getenv("DB_HOST", "localhost")
db_port = int(os.getenv("DB_PORT", 5432))
db_user = os.getenv("DB_USER", "postgres")
db_pass = os.getenv("DB_PASSWORD", "postgres")

url_dengue = f"postgresql+psycopg2://{db_user}:{db_pass}@{db_host}:{db_port}/dengue"
engine = create_engine(url_dengue)

with engine.connect() as conn:
    res = conn.execute(text("SELECT DISTINCT \"MPIO_CCDGO\", \"MPIO_CNMBR\" FROM public.valle_mun LIMIT 5;")).fetchall()
    print("Dengue table samples:")
    for r in res:
        print(f"MPIO_CCDGO: {repr(r[0])} | MPIO_CNMBR: {repr(r[1])}")
