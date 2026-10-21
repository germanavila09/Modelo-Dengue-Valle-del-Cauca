"""Auditoria reproducible de solo lectura; no imprime credenciales ni microdatos.
Uso: python scripts/auditar_integridad.py [--output outputs/auditoria_integridad.json]
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
import pandas as pd
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.db import crear_engine, _quote_identifier
from src.config import SCHEMA, TABLE


def auditar():
    report = {"checked_at": datetime.now(timezone.utc).isoformat(), "read_only": True,
              "scope": "Agregados de dengue, clima y demografia; no certifica microdatos ausentes.",
              "checks": {}, "findings": []}
    table = f"{_quote_identifier(SCHEMA)}.{_quote_identifier(TABLE)}"
    engine = crear_engine()
    with engine.connect() as connection:
        with connection.begin():
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
            connection.execute(text("SET LOCAL statement_timeout = '45s'"))
            def query(name, sql):
                rows = [dict(r) for r in connection.execute(text(sql)).mappings()]
                report["checks"][name] = rows
                return rows
            query("annual_summary", f'''SELECT count(*) records, count(DISTINCT "MPIO_CCDGO") municipalities,
                min(anio) first_year, max(anio) last_year,
                count(*) FILTER(WHERE anio IS NULL OR anio < 1900 OR anio > extract(year from current_date)) invalid_year,
                count(*) FILTER(WHERE "MPIO_CCDGO" IS NULL OR "MPIO_CCDGO" !~ '^76[0-9]{{3}}$') invalid_code,
                count(*) FILTER(WHERE poblacion IS NULL OR poblacion<=0) invalid_population,
                count(*) FILTER(WHERE conteo_dengue IS NULL OR conteo_dengue<0) invalid_cases,
                count(*) FILTER(WHERE incidencia_dengue IS NULL OR incidencia_dengue<0) invalid_incidence,
                count(*) FILTER(WHERE abs(incidencia_dengue-conteo_dengue*100000.0/NULLIF(poblacion,0))>0.051) incidence_mismatch,
                count(*) FILTER(WHERE geom IS NULL OR ST_IsEmpty(geom)) missing_geometry,
                count(*) FILTER(WHERE NOT ST_IsValid(geom)) invalid_geometry FROM {table}''')
            query("annual_duplicates", f'''SELECT "MPIO_CCDGO",anio,count(*) records FROM {table} GROUP BY 1,2 HAVING count(*)>1''')
            query("annual_coverage", f'''SELECT anio,count(*) records,count(DISTINCT "MPIO_CCDGO") municipalities,
                sum(conteo_dengue) cases,sum(poblacion) population FROM {table} GROUP BY anio ORDER BY anio''')
            query("annual_missing_pairs", f'''WITH codes AS (SELECT DISTINCT "MPIO_CCDGO" code FROM {table}),
                years AS (SELECT generate_series(min(anio),max(anio)) audit_year FROM {table})
                SELECT code,audit_year FROM codes CROSS JOIN years LEFT JOIN {table} v ON v."MPIO_CCDGO"=code AND v.anio=audit_year WHERE v.id IS NULL''')
            query("municipal_name_variants", f'''SELECT "MPIO_CCDGO",count(DISTINCT "MPIO_CNMBR") names FROM {table} GROUP BY 1 HAVING count(DISTINCT "MPIO_CNMBR")>1''')
            query("name_encoding", f'''SELECT DISTINCT "MPIO_CCDGO", "MPIO_CNMBR" FROM {table} WHERE "MPIO_CNMBR" LIKE '%?%' OR "MPIO_CNMBR" LIKE '%�%' ''' )
            query("spatial_reference", f'''SELECT ST_SRID(geom) srid,GeometryType(geom) geometry_type,count(*) records FROM {table} GROUP BY 1,2''')
            query("geometry_variants", f'''SELECT "MPIO_CCDGO", count(DISTINCT md5(ST_AsEWKB(geom))) variants FROM {table} GROUP BY 1 HAVING count(DISTINCT md5(ST_AsEWKB(geom)))>1''')
            query("population_changes_over_10pct", f'''WITH history AS (SELECT "MPIO_CCDGO",anio,poblacion,
                lag(poblacion) OVER(PARTITION BY "MPIO_CCDGO" ORDER BY anio) previous FROM {table})
                SELECT *, round(100.0*(poblacion-previous)/NULLIF(previous,0),2) change_pct FROM history
                WHERE abs(poblacion-previous)>0.10*previous''')
            query("constraints", f'''SELECT conrelid::regclass::text table_name,contype,pg_get_constraintdef(oid) definition
                FROM pg_constraint WHERE connamespace IN (SELECT oid FROM pg_namespace WHERE nspname IN ('{SCHEMA}','demografia'))''')
            query("indexes", f'''SELECT tablename,indexdef FROM pg_indexes WHERE schemaname='{SCHEMA}' AND tablename IN ('{TABLE}','clima_mensual_municipio')''')
            tables = query("available_sources", "SELECT table_schema,table_name FROM information_schema.tables WHERE table_schema IN ('public','demografia') ORDER BY 1,2")
            sources = {(r['table_schema'],r['table_name']) for r in tables}
            if ('public','dengue_m') not in sources:
                report['findings'].append('Falta public.dengue_m: no se pueden cotejar casos individuales, fechas, semanas, duplicados de notificaciones ni geolocalizacion puntual.')
            if ('public','clima_mensual_municipio') in sources:
                query("climate_coverage", '''SELECT "año" anio,count(*) records,count(DISTINCT "MPIO_CCDGO") municipalities,min(mes) first_month,max(mes) last_month FROM public.clima_mensual_municipio GROUP BY 1 ORDER BY 1''')
                query("climate_missing_pairs", f'''WITH codes AS (SELECT DISTINCT "MPIO_CCDGO" code FROM {table}),
                    years AS (SELECT DISTINCT "año" audit_year FROM public.clima_mensual_municipio),
                    expected AS (SELECT code,audit_year,generate_series(1,CASE WHEN audit_year=extract(year from current_date) THEN extract(month from current_date)::int-1 ELSE 12 END) audit_month FROM codes CROSS JOIN years)
                    SELECT audit_year,count(*) missing_months FROM expected e LEFT JOIN public.clima_mensual_municipio c
                    ON c."MPIO_CCDGO"=e.code AND c."año"=e.audit_year AND c.mes=e.audit_month WHERE c.mes IS NULL GROUP BY audit_year ORDER BY audit_year''')
                query("climate_validity", f'''SELECT count(*) FILTER(WHERE mes IS NULL OR mes NOT BETWEEN 1 AND 12) invalid_month,
                    count(*) FILTER(WHERE total_precipitation IS NULL OR mean_max_temperature IS NULL OR mean_min_temperature IS NULL OR mean_max_humidity IS NULL OR mean_min_humidity IS NULL) missing_values,
                    count(*) FILTER(WHERE total_precipitation<0 OR mean_min_temperature>mean_max_temperature OR mean_min_humidity>mean_max_humidity OR mean_min_humidity<0 OR mean_max_humidity>100) inconsistent_values,
                    count(*) FILTER(WHERE "MPIO_CCDGO" NOT IN (SELECT "MPIO_CCDGO" FROM {table})) orphan_codes FROM public.clima_mensual_municipio''')
                query("climate_duplicates", '''SELECT "MPIO_CCDGO","año",mes,count(*) records FROM public.clima_mensual_municipio GROUP BY 1,2,3 HAVING count(*)>1''')
            if ('demografia','dim_municipio') in sources:
                query("demography_catalog_missing", f'''SELECT DISTINCT v."MPIO_CCDGO" FROM {table} v LEFT JOIN demografia.dim_municipio m ON trim(m.codigo_dane)=v."MPIO_CCDGO" WHERE m.id_municipio IS NULL''')
                for name,dimensions in [('pob_edad_simple','edad,sexo'),('pob_quinquenal','id_grupo,sexo'),('pob_ciclo_vida','id_ciclo,zona,sexo')]:
                    if ('demografia',name) not in sources:
                        report['findings'].append(f'Falta demografia.{name}')
                        continue
                    query(name+'_coverage', f'SELECT anio_referencia,count(*) records,count(DISTINCT id_municipio) municipalities FROM demografia.{name} GROUP BY 1')
                    query(name+'_validity', f'''SELECT count(*) FILTER(WHERE cantidad IS NULL OR cantidad<0) invalid_counts,
                        count(*) FILTER(WHERE anio_referencia IS NULL) missing_reference_year,
                        count(*) FILTER(WHERE id_municipio IS NULL OR id_municipio NOT IN (SELECT id_municipio FROM demografia.dim_municipio)) orphans FROM demografia.{name}''')
                    query(name+'_duplicates', f'SELECT id_municipio,anio_referencia,{dimensions},count(*) records FROM demografia.{name} GROUP BY id_municipio,anio_referencia,{dimensions} HAVING count(*)>1')
                query("demography_cross_totals", '''WITH a AS (SELECT id_municipio,anio_referencia,sum(cantidad) total FROM demografia.pob_edad_simple GROUP BY 1,2),
                    q AS (SELECT id_municipio,anio_referencia,sum(cantidad) total FROM demografia.pob_quinquenal GROUP BY 1,2),
                    c AS (SELECT id_municipio,anio_referencia,sum(cantidad) total FROM demografia.pob_ciclo_vida GROUP BY 1,2)
                    SELECT coalesce(a.id_municipio,q.id_municipio,c.id_municipio) id_municipio,
                    coalesce(a.anio_referencia,q.anio_referencia,c.anio_referencia) anio_referencia,a.total edad_simple,q.total quinquenal,c.total ciclos
                    FROM a FULL JOIN q USING(id_municipio,anio_referencia) FULL JOIN c USING(id_municipio,anio_referencia)
                    WHERE a.total IS DISTINCT FROM q.total OR a.total IS DISTINCT FROM c.total''')
                query("demography_vs_dengue_population", f'''SELECT v."MPIO_CCDGO",v.anio,v.poblacion dengue_population,d.poblacion_total demographic_population
                    FROM {table} v JOIN demografia.v_poblacion_municipio_total d ON trim(d.codigo_dane)=v."MPIO_CCDGO" AND d.anio_referencia=v.anio
                    WHERE v.poblacion IS DISTINCT FROM d.poblacion_total''')
            # Save only municipal aggregates for reproducible frontend parity checks.
            query("annual_records", f'''SELECT "MPIO_CCDGO",anio,poblacion,conteo_dengue,incidencia_dengue FROM {table} ORDER BY 1,2''')
    engine.dispose()
    report['findings'].append('La presencia de un registro anual no certifica cierre: la fuente no incluye fecha de corte ni estado de consolidacion.')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT/'outputs'/'auditoria_integridad.json'))
    args = parser.parse_args()
    result = auditar()
    path = Path(args.output)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=True))
    for name, rows in result['checks'].items():
        if name != 'annual_records': print(name, json.dumps(rows[:8],ensure_ascii=True,default=str), 'total_rows=',len(rows))
    print('Report:',path)
