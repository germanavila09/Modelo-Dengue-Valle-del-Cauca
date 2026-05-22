"""
exportar_demografia.py — Geodata Salud Observatory
===================================================
Exporta datos demográficos desde PostgreSQL (esquema demografia en database terrarIA)
a frontend/demografia-data.js como un archivo JS con las constantes demográficas.

Uso:
    python scripts/exportar_demografia.py
"""

import os
import json
import sys
from datetime import date
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL
from dotenv import load_dotenv

# Path setup
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Destino
DEST = ROOT / "frontend" / "demografia-data.js"

def main():
    print("Cargando variables de entorno...")
    load_dotenv(dotenv_path=ROOT / ".env")
    
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", 5432))
    db_user = os.getenv("DB_USER", "postgres")
    db_pass = os.getenv("DB_PASSWORD", "postgres")
    
    print(f"Conectando a base de datos PostgreSQL 'terrarIA' en {db_host}:{db_port}...")
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=db_user,
        password=db_pass,
        host=db_host,
        port=db_port,
        database="terrarIA",
    )
    engine = create_engine(url, connect_args={"client_encoding": "utf8"})
    
    try:
        with engine.connect() as conn:
            # 1. Población total y género por municipio
            print("Consultando totales de población por municipio...")
            q_totales = text("""
                SELECT 
                    codigo_dane, 
                    municipio, 
                    poblacion_total, 
                    poblacion_masculina, 
                    poblacion_femenina, 
                    pct_femenino
                FROM demografia.v_poblacion_municipio_total
                WHERE anio_referencia = 2024;
            """)
            res_totales = conn.execute(q_totales).fetchall()
            
            DEMO_MUN_TOTAL = {}
            total_dept = 0
            masc_dept = 0
            feme_dept = 0
            
            for row in res_totales:
                if row[0] is None:
                    print(f"  Advertencia: Omitiendo fila con codigo_dane nulo en v_poblacion_municipio_total: {row}")
                    continue
                code = row[0].strip()
                name = row[1]
                pop = int(row[2]) if row[2] is not None else 0
                masc = int(row[3]) if row[3] is not None else 0
                feme = int(row[4]) if row[4] is not None else 0
                pct_f = float(row[5]) if row[5] is not None else 0.0
                
                DEMO_MUN_TOTAL[code] = {
                    "codigo_dane": code,
                    "nombre": name,
                    "poblacion_total": pop,
                    "poblacion_masculina": masc,
                    "poblacion_femenina": feme,
                    "pct_femenino": pct_f
                }
                
                total_dept += pop
                masc_dept += masc
                feme_dept += feme
                
            # Agregar el total del departamento
            pct_f_dept = round((feme_dept / total_dept) * 100, 1) if total_dept > 0 else 0.0
            DEMO_MUN_TOTAL["VALLE"] = {
                "codigo_dane": "VALLE",
                "nombre": "Valle del Cauca (Total)",
                "poblacion_total": total_dept,
                "poblacion_masculina": masc_dept,
                "poblacion_femenina": feme_dept,
                "pct_femenino": pct_f_dept
            }
            print(f"  {len(DEMO_MUN_TOTAL) - 1} municipios cargados. Total Departamento: {total_dept} hab.")
            
            # 2. Pirámide poblacional por municipio
            print("Consultando pirámide poblacional...")
            q_piramide = text("""
                SELECT 
                    codigo_dane,
                    grupo_quinquenal,
                    sexo,
                    cantidad,
                    cantidad_piramide,
                    orden
                FROM demografia.v_piramide_poblacional_municipio
                WHERE anio_referencia = 2024
                ORDER BY codigo_dane, orden, sexo;
            """)
            res_piramide = conn.execute(q_piramide).fetchall()
            
            DEMO_PIRAMIDE = {}
            # Para consolidar el total del departamento
            pyr_dept = {} # key: (grupo_quinquenal, sexo, orden) -> {cantidad, cantidad_piramide}
            
            for row in res_piramide:
                if row[0] is None:
                    continue
                code = row[0].strip()
                group = row[1]
                sex = str(row[2])
                qty = int(row[3]) if row[3] is not None else 0
                qty_pyr = int(row[4]) if row[4] is not None else 0
                order = int(row[5]) if row[5] is not None else 0
                
                if code not in DEMO_PIRAMIDE:
                    DEMO_PIRAMIDE[code] = []
                    
                DEMO_PIRAMIDE[code].append({
                    "grupo_quinquenal": group,
                    "sexo": sex,
                    "cantidad": qty,
                    "cantidad_piramide": qty_pyr,
                    "orden": order
                })
                
                # Sumar para el departamento
                key = (group, sex, order)
                if key not in pyr_dept:
                    pyr_dept[key] = {"cantidad": 0, "cantidad_piramide": 0}
                pyr_dept[key]["cantidad"] += qty
                pyr_dept[key]["cantidad_piramide"] += qty_pyr
                
            # Convertir pirámide del departamento a lista ordenada
            pyr_dept_list = []
            for (group, sex, order), vals in pyr_dept.items():
                pyr_dept_list.append({
                    "grupo_quinquenal": group,
                    "sexo": sex,
                    "cantidad": vals["cantidad"],
                    "cantidad_piramide": vals["cantidad_piramide"],
                    "orden": order
                })
            # Ordenar por orden y sexo
            pyr_dept_list.sort(key=lambda x: (x["orden"], x["sexo"]))
            DEMO_PIRAMIDE["VALLE"] = pyr_dept_list
            print(f"  Datos de pirámide procesados para {len(DEMO_PIRAMIDE) - 1} municipios y el departamento.")
            
            # 3. Ciclo de vida por municipio
            print("Consultando ciclos de vida...")
            q_ciclos = text("""
                SELECT 
                    m.codigo_dane,
                    c.nombre AS ciclo_nombre,
                    c.id_ciclo,
                    p.sexo,
                    SUM(p.cantidad) AS cantidad
                FROM demografia.pob_ciclo_vida p
                JOIN demografia.dim_municipio m ON p.id_municipio = m.id_municipio
                JOIN demografia.dim_ciclo_vida c ON p.id_ciclo = c.id_ciclo
                WHERE p.anio_referencia = 2024
                GROUP BY m.codigo_dane, c.nombre, c.id_ciclo, p.sexo
                ORDER BY m.codigo_dane, c.id_ciclo, p.sexo;
            """)
            res_ciclos = conn.execute(q_ciclos).fetchall()
            
            DEMO_CICLOS = {}
            ciclos_dept = {} # key: (ciclo_nombre, id_ciclo, sexo) -> cantidad
            
            for row in res_ciclos:
                if row[0] is None:
                    continue
                code = row[0].strip()
                cycle_name = row[1]
                cycle_id = int(row[2]) if row[2] is not None else 0
                sex = str(row[3])
                qty = int(row[4]) if row[4] is not None else 0
                
                if code not in DEMO_CICLOS:
                    DEMO_CICLOS[code] = []
                    
                DEMO_CICLOS[code].append({
                    "ciclo_nombre": cycle_name,
                    "id_ciclo": cycle_id,
                    "sexo": sex,
                    "cantidad": qty
                })
                
                # Sumar para el departamento
                key = (cycle_name, cycle_id, sex)
                ciclos_dept[key] = ciclos_dept.get(key, 0) + qty
                
            # Convertir ciclos del departamento a lista ordenada
            ciclos_dept_list = []
            for (cycle_name, cycle_id, sex), qty in ciclos_dept.items():
                ciclos_dept_list.append({
                    "ciclo_nombre": cycle_name,
                    "id_ciclo": cycle_id,
                    "sexo": sex,
                    "cantidad": qty
                })
            ciclos_dept_list.sort(key=lambda x: (x["id_ciclo"], x["sexo"]))
            DEMO_CICLOS["VALLE"] = ciclos_dept_list
            print(f"  Datos de ciclos de vida procesados para {len(DEMO_CICLOS) - 1} municipios y el departamento.")
            
            # Escribir el archivo JS
            today = date.today().strftime("%Y-%m-%d")
            print(f"Escribiendo a {DEST}...")
            
            js_content = f"""\
// ─── GEODATA SALUD — Datos Demográficos Reales ───────────────────────────────
// Generado por scripts/exportar_demografia.py — {today}

var DEMO_MUN_TOTAL = {json.dumps(DEMO_MUN_TOTAL, ensure_ascii=False, indent=2)};

var DEMO_PIRAMIDE = {json.dumps(DEMO_PIRAMIDE, ensure_ascii=False, indent=2)};

var DEMO_CICLOS = {json.dumps(DEMO_CICLOS, ensure_ascii=False, indent=2)};

// ─── Helpers de Consulta Demográfica ──────────────────────────────────────────
function getDemoTotal(code) {{
  return DEMO_MUN_TOTAL[code] || DEMO_MUN_TOTAL['VALLE'];
}}

function getDemoPiramide(code) {{
  return DEMO_PIRAMIDE[code] || DEMO_PIRAMIDE['VALLE'];
}}

function getDemoCiclos(code) {{
  return DEMO_CICLOS[code] || DEMO_CICLOS['VALLE'];
}}
"""
            DEST.write_text(js_content, encoding="utf-8")
            print(f"Archivo generado exitosamente: {DEST.name} ({DEST.stat().st_size / 1024:.1f} KB)")
            print("Listo.")
            
    except Exception as e:
        print(f"Error procesando los datos demográficos: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
