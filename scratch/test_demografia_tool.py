import os
import sys
from pathlib import Path
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv(dotenv_path="e:/laboratorio_TerrarIA/observatorios/observatorio_geosalud/.env")

# Recreate the system path setup like tools.py
_PROJECT_ROOT = Path("e:/laboratorio_TerrarIA/observatorios/observatorio_geosalud")
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from src.config import SCHEMA, TABLE, DB_CONFIG
from src.db import crear_engine

def _crear_engine_terraria():
    from sqlalchemy.engine import URL
    cfg = DB_CONFIG.copy()
    cfg["database"] = "terrarIA"
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg["port"],
        database=cfg["database"],
    )
    return create_engine(url, connect_args={"client_encoding": "utf8"})

def test_consulta_demografica(municipio: str | None = None, anio: int | None = None, ciclo_vida: str | None = None):
    # 1. Normalizar municipio
    muni = (municipio or "VALLE").strip().upper()
    if muni in ["VALLE", "VALLE DEL CAUCA", "DEPARTAMENTO", "TOTAL"]:
        muni = "VALLE"
    
    # 2. Normalizar anio
    year = anio or 2024
    if year not in [2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]:
        year = 2024

    # 3. Normalizar ciclo
    ciclo = "ALL"
    if ciclo_vida and ciclo_vida.strip():
        c_lower = ciclo_vida.strip().lower()
        if c_lower in ["todos", "todas", "all", "general", "total"]:
            ciclo = "ALL"
        elif "primera" in c_lower:
            ciclo = "Primera infancia"
        elif "infancia" in c_lower:
            ciclo = "Infancia"
        elif "adolescencia" in c_lower:
            ciclo = "Adolescencia"
        elif "juventud" in c_lower:
            ciclo = "Juventud"
        elif "adultez" in c_lower:
            ciclo = "Adultez"
        elif "vejez" in c_lower:
            ciclo = "Vejez"

    # 4. Get base totals and metadata from terrarIA database first
    engine_terr = _crear_engine_terraria()
    with engine_terr.connect() as conn:
        if muni != "VALLE":
            # Map name to dim_municipio using normalized uppercase
            # E.g. 'ALCALA' or 'GUADALAJARA DE BUGA'
            muni_norm = muni
            if muni_norm in ["BUGA", "GUADALAJARA DE BUGA"]:
                muni_norm = "GUADALAJARA DE BUGA"
            
            q_muni = text("SELECT id_municipio, nombre, codigo_dane FROM demografia.dim_municipio WHERE nombre_normalizado = :muni;")
            res_muni = conn.execute(q_muni, {"muni": muni_norm}).fetchone()
            if not res_muni:
                return {"status": "error", "error_message": f"Municipio '{municipio}' no encontrado. Revisa el nombre."}
            id_municipio, official_name, codigo_dane = res_muni
        else:
            id_municipio = None
            official_name = "Valle del Cauca (Total)"
            codigo_dane = "VALLE"

        # Get base total (from 2024)
        if muni == "VALLE":
            q_base = text("""
                SELECT SUM(poblacion_total) as total,
                       SUM(poblacion_masculina) as masc,
                       SUM(poblacion_femenina) as fem
                FROM demografia.v_poblacion_municipio_total;
            """)
            res_base = conn.execute(q_base).fetchone()
            base_pop = int(res_base[0]) if res_base and res_base[0] is not None else 1
            base_masc = int(res_base[1]) if res_base and res_base[1] is not None else 0
            base_feme = int(res_base[2]) if res_base and res_base[2] is not None else 0
        else:
            q_base = text("""
                SELECT poblacion_total, poblacion_masculina, poblacion_femenina
                FROM demografia.v_poblacion_municipio_total
                WHERE id_municipio = :id_muni;
            """)
            res_base = conn.execute(q_base, {"id_muni": id_municipio}).fetchone()
            base_pop = int(res_base[0]) if res_base and res_base[0] is not None else 1
            base_masc = int(res_base[1]) if res_base and res_base[1] is not None else 0
            base_feme = int(res_base[2]) if res_base and res_base[2] is not None else 0

        # Now get real pop from dengue database (valle_mun table) using DANE code
        engine_dengue = crear_engine()
        real_pop = None
        with engine_dengue.connect() as conn_dengue:
            if muni == "VALLE":
                q = text(f'SELECT SUM("población") FROM "{SCHEMA}"."{TABLE}" WHERE "año" = :year;')
                res = conn_dengue.execute(q, {"year": year}).fetchone()
                real_pop = int(res[0]) if res and res[0] is not None else None
            else:
                q = text(f'SELECT "población" FROM "{SCHEMA}"."{TABLE}" WHERE "MPIO_CCDGO" = :dane AND "año" = :year;')
                res = conn_dengue.execute(q, {"dane": codigo_dane, "year": year}).fetchone()
                real_pop = int(res[0]) if res and res[0] is not None else None

        # Calculate factor
        factor = 1.0
        if real_pop is not None and base_pop > 0:
            factor = float(real_pop) / float(base_pop)

        print(f"DEBUG: muni={official_name}, real_pop={real_pop}, base_pop={base_pop}, factor={factor}")

        # Query cycles of life
        if muni == "VALLE":
            q_cycles = text("""
                SELECT cv.nombre AS ciclo_nombre,
                       SUM(p.cantidad) AS total,
                       SUM(CASE WHEN p.sexo = 'M' THEN p.cantidad ELSE 0 END) AS masculino,
                       SUM(CASE WHEN p.sexo = 'F' THEN p.cantidad ELSE 0 END) AS femenino
                FROM demografia.pob_ciclo_vida p
                JOIN demografia.dim_ciclo_vida cv ON p.id_ciclo = cv.id_ciclo
                GROUP BY cv.orden, cv.nombre
                ORDER BY cv.orden;
            """)
            res_cycles = conn.execute(q_cycles).fetchall()
        else:
            q_cycles = text("""
                SELECT cv.nombre AS ciclo_nombre,
                       SUM(p.cantidad) AS total,
                       SUM(CASE WHEN p.sexo = 'M' THEN p.cantidad ELSE 0 END) AS masculino,
                       SUM(CASE WHEN p.sexo = 'F' THEN p.cantidad ELSE 0 END) AS femenino
                FROM demografia.pob_ciclo_vida p
                JOIN demografia.dim_ciclo_vida cv ON p.id_ciclo = cv.id_ciclo
                WHERE p.id_municipio = :id_muni
                GROUP BY cv.orden, cv.nombre
                ORDER BY cv.orden;
            """)
            res_cycles = conn.execute(q_cycles, {"id_muni": id_municipio}).fetchall()

        # Build list of scaled cycles
        cycles_list = []
        for r in res_cycles:
            c_name = r[0]
            c_tot = round(int(r[1]) * factor)
            c_masc = round(int(r[2]) * factor)
            c_feme = round(int(r[3]) * factor)
            c_pct_masc = round((c_masc / c_tot * 100), 1) if c_tot > 0 else 0.0
            c_pct_feme = round((c_feme / c_tot * 100), 1) if c_tot > 0 else 0.0
            cycles_list.append({
                "ciclo_vida": c_name,
                "poblacion_total": c_tot,
                "poblacion_masculina": c_masc,
                "poblacion_femenina": c_feme,
                "pct_masculino": c_pct_masc,
                "pct_femenino": c_pct_feme
            })

        # Determine target output values based on selected cycle_vida
        if ciclo == "ALL":
            target_total = round(base_pop * factor)
            target_masc = round(base_masc * factor)
            target_feme = round(base_feme * factor)
        else:
            # Find the specific cycle
            match_cycle = next((c for c in cycles_list if c["ciclo_vida"] == ciclo), None)
            if match_cycle:
                target_total = match_cycle["poblacion_total"]
                target_masc = match_cycle["poblacion_masculina"]
                target_feme = match_cycle["poblacion_femenina"]
            else:
                target_total = 0
                target_masc = 0
                target_feme = 0

        target_pct_masc = round((target_masc / target_total * 100), 1) if target_total > 0 else 0.0
        target_pct_feme = round((target_feme / target_total * 100), 1) if target_total > 0 else 0.0

        return {
            "status": "success",
            "municipio": official_name,
            "codigo_dane": codigo_dane,
            "anio": year,
            "ciclo_vida": ciclo,
            "poblacion_total": target_total,
            "poblacion_masculina": target_masc,
            "poblacion_femenina": target_feme,
            "pct_masculino": target_pct_masc,
            "pct_femenino": target_pct_feme,
            "ciclos_de_vida": cycles_list if ciclo == "ALL" else None
        }

# Test runs
print("Zarzal 2024:", test_consulta_demografica("ZARZAL", 2024))
print("\nAlcala Adolescencia 2024:", test_consulta_demografica("ALCALA", 2024, "Adolescencia"))
print("\nValle 2024:", test_consulta_demografica("VALLE", 2024))
