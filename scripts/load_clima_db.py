import sys
import re
import pandas as pd
from pathlib import Path
from sqlalchemy import text

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.db import crear_engine

def clean_db_name(name):
    if not name:
        return ""
    name = str(name).upper()
    name = name.replace('ALCAL?', 'ALCALA')
    name = name.replace('ANDALUC?A', 'ANDALUCIA')
    name = name.replace('BOL?VAR', 'BOLIVAR')
    name = name.replace('EL ?GUILA', 'EL AGUILA')
    name = name.replace('GUACAR?', 'GUACARI')
    name = name.replace('JAMUND?', 'JAMUNDI')
    name = name.replace('LA UNI?N', 'LA UNION')
    name = name.replace('RIOFR?O', 'RIOFRIO')
    name = name.replace('TULU?', 'TULUA')
    return name

def normalize(name):
    if not name:
        return ""
    name = str(name).strip().upper()
    name = re.sub(r'[ÁÄÂÀ]', 'A', name)
    name = re.sub(r'[ÉËÊÈ]', 'E', name)
    name = re.sub(r'[ÍÏÎÌ]', 'I', name)
    name = re.sub(r'[ÓÖÔÒ]', 'O', name)
    name = re.sub(r'[ÚÜÛÙ]', 'U', name)
    name = re.sub(r'[Ñ]', 'N', name)
    name = re.sub(r'[^A-Z0-9 ]', '', name)
    return name

def main():
    print("Iniciando carga de datos climáticos...")
    
    csv_path = "E:/Dengue_IA/dengue_ia_valle/data/processed/monthly_climate_indices.csv"
    if not Path(csv_path).exists():
        print(f"Error: No se encontró el archivo CSV en {csv_path}")
        sys.exit(1)
        
    df = pd.read_csv(csv_path)
    print(f"Cargados {len(df)} registros desde el CSV.")

    # Agrupar datos por municipio, año y mes calculando el promedio
    df_agg = df.groupby(['municipio', 'year', 'month']).agg({
        'total_precipitation': 'mean',
        'mean_max_temperature': 'mean',
        'mean_min_temperature': 'mean',
        'mean_max_humidity': 'mean',
        'mean_min_humidity': 'mean'
    }).reset_index()
    print(f"Agregados los datos: {len(df_agg)} combinaciones municipio/año/mes.")

    # Conectar a la base de datos para mapear códigos
    engine = crear_engine()
    with engine.connect() as conn:
        # Obtener listado de municipios y códigos desde valle_mun
        res = conn.execute(text("SELECT DISTINCT \"MPIO_CCDGO\", \"MPIO_CNMBR\" FROM public.valle_mun"))
        db_munes = res.fetchall()
        
    db_map = {}
    for code, name in db_munes:
        cleaned_name = clean_db_name(name)
        db_map[normalize(cleaned_name)] = (code, name)

    # Mapear municipio en df_agg a código y nombre oficial en la BD
    records = []
    unmapped = set()
    
    for _, row in df_agg.iterrows():
        orig_name = row['municipio']
        norm_name = normalize(orig_name)
        
        # Corrección especial para Buga
        if norm_name == 'BUGA':
            norm_name = 'GUADALAJARA DE BUGA'
            
        if norm_name in db_map:
            code, db_name = db_map[norm_name]
            records.append({
                'MPIO_CCDGO': code,
                'MPIO_CNMBR': db_name,
                'año': int(row['year']),
                'mes': int(row['month']),
                'total_precipitation': row['total_precipitation'] if pd.notna(row['total_precipitation']) else None,
                'mean_max_temperature': row['mean_max_temperature'] if pd.notna(row['mean_max_temperature']) else None,
                'mean_min_temperature': row['mean_min_temperature'] if pd.notna(row['mean_min_temperature']) else None,
                'mean_max_humidity': row['mean_max_humidity'] if pd.notna(row['mean_max_humidity']) else None,
                'mean_min_humidity': row['mean_min_humidity'] if pd.notna(row['mean_min_humidity']) else None
            })
        else:
            unmapped.add(orig_name)
            
    if unmapped:
        print(f"Advertencia: No se pudieron mapear los siguientes municipios: {unmapped}")

    df_final = pd.DataFrame(records)
    print(f"Listos para insertar {len(df_final)} registros mapeados.")

    # Crear tabla e insertar registros usando psycopg2 para mayor control de transacciones
    conn_raw = engine.raw_connection()
    try:
        cur = conn_raw.cursor()
        
        # 1. Crear tabla
        print("Creando tabla public.clima_mensual_municipio...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS public.clima_mensual_municipio (
                "MPIO_CCDGO" VARCHAR(5) NOT NULL,
                "MPIO_CNMBR" VARCHAR(100) NOT NULL,
                año INT NOT NULL,
                mes INT NOT NULL,
                total_precipitation NUMERIC,
                mean_max_temperature NUMERIC,
                mean_min_temperature NUMERIC,
                mean_max_humidity NUMERIC,
                mean_min_humidity NUMERIC,
                PRIMARY KEY ("MPIO_CCDGO", año, mes)
            );
        """)
        
        # 2. Limpiar datos existentes
        cur.execute("TRUNCATE TABLE public.clima_mensual_municipio;")
        
        # 3. Insertar datos
        insert_query = """
            INSERT INTO public.clima_mensual_municipio (
                "MPIO_CCDGO", "MPIO_CNMBR", año, mes,
                total_precipitation, mean_max_temperature, mean_min_temperature,
                mean_max_humidity, mean_min_humidity
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);
        """
        
        tuples = [
            (
                r['MPIO_CCDGO'], r['MPIO_CNMBR'], r['año'], r['mes'],
                r['total_precipitation'], r['mean_max_temperature'], r['mean_min_temperature'],
                r['mean_max_humidity'], r['mean_min_humidity']
            )
            for _, r in df_final.iterrows()
        ]
        
        cur.executemany(insert_query, tuples)
        
        # 4. Crear índice
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_clima_muni_year_month 
            ON public.clima_mensual_municipio (año, mes);
        """)
        
        conn_raw.commit()
        print(f"Carga completa. Se insertaron {len(tuples)} registros exitosamente.")
    except Exception as e:
        conn_raw.rollback()
        print(f"Error al escribir en la base de datos: {e}")
        sys.exit(1)
    finally:
        conn_raw.close()

if __name__ == "__main__":
    main()
