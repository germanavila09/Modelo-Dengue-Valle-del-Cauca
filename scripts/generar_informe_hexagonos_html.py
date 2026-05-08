"""Genera un informe HTML paso a paso para el analisis de dengue por hexagonos."""

from __future__ import annotations

import csv
import html
import os
import subprocess
from io import StringIO
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
OUTPUT = ROOT / "outputs" / "informe_dengue_hexagonos_paso_a_paso.html"
PSQL = Path(r"C:\Program Files\PostgreSQL\17\bin\psql.exe")


def load_env() -> dict[str, str]:
    env_path = ROOT / ".env"
    values: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def query(sql: str) -> list[dict[str, str]]:
    db = load_env()
    env = os.environ.copy()
    env["PGPASSWORD"] = db.get("DB_PASSWORD", "")
    env["PGCLIENTENCODING"] = "UTF8"

    result = subprocess.run(
        [
            str(PSQL),
            "-h",
            db.get("DB_HOST", "localhost"),
            "-p",
            db.get("DB_PORT", "5432"),
            "-U",
            db.get("DB_USER", "postgres"),
            "-d",
            db.get("DB_NAME", "dengue"),
            "-P",
            "pager=off",
            "-A",
            "-F",
            ",",
            "-c",
            f"COPY ({sql}) TO STDOUT WITH CSV HEADER",
        ],
        cwd=ROOT,
        env=env,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    return list(csv.DictReader(StringIO(result.stdout)))


def fmt_number(value: str) -> str:
    if value is None or value == "":
        return ""
    try:
        n = float(value)
    except ValueError:
        return value
    if n.is_integer():
        return f"{int(n):,}".replace(",", ".")
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def table(rows: list[dict[str, str]], headers: list[tuple[str, str]]) -> str:
    if not rows:
        return "<p class='muted'>Sin resultados.</p>"
    thead = "".join(f"<th>{html.escape(label)}</th>" for key, label in headers)
    body_rows = []
    for row in rows:
        cells = []
        for key, _label in headers:
            value = row.get(key, "")
            cells.append(f"<td>{html.escape(fmt_number(value))}</td>")
        body_rows.append(f"<tr>{''.join(cells)}</tr>")
    return f"<div class='table-wrap'><table><thead><tr>{thead}</tr></thead><tbody>{''.join(body_rows)}</tbody></table></div>"


def card(title: str, value: str, caption: str = "") -> str:
    return (
        "<article class='metric'>"
        f"<span>{html.escape(title)}</span>"
        f"<strong>{html.escape(fmt_number(value))}</strong>"
        f"<small>{html.escape(caption)}</small>"
        "</article>"
    )


SQL = {
    "hex_info": """
        select count(*) as total_hexagonos,
               count(distinct "MPIO_CCDGO") as municipios,
               count(*) filter (where geometry is null) as sin_geometria,
               count(*) filter (where geometry is not null and not ST_IsValid(geometry)) as invalidas,
               count(*) filter (where GeometryType(geometry) = 'POLYGON') as polygon,
               count(*) filter (where GeometryType(geometry) = 'MULTIPOLYGON') as multipolygon,
               round(avg(ST_Area(geometry::geography))::numeric, 2) as area_prom_m2
        from public.hexagonos
    """,
    "casos_info": """
        select count(*) as total_casos,
               count(geom) as con_geom,
               count(*) filter (where geom is null) as sin_geom,
               count(*) filter (where geom is not null and not ST_IsValid(geom)) as invalidas,
               count(*) filter (where geom is not null and (ST_X(geom) = 0 or ST_Y(geom) = 0)) as coord_cero
        from public.dengue_m
    """,
    "casos_anio": """
        select U&"a\\00F1o"::int as anio,
               count(*) as casos,
               count(*) filter (where geom is not null and ST_X(geom) <> 0 and ST_Y(geom) <> 0) as casos_coord_validas,
               count(*) filter (where geom is not null and (ST_X(geom) = 0 or ST_Y(geom) = 0)) as coord_cero
        from public.dengue_m
        where U&"a\\00F1o" ~ '^[0-9]{4}$'
        group by U&"a\\00F1o"::int
        order by anio
    """,
    "resumen_hex_anio": """
        with casos_limpios as (
          select U&"a\\00F1o"::int as anio, geom
          from public.dengue_m
          where geom is not null
            and ST_X(geom) <> 0
            and ST_Y(geom) <> 0
            and U&"a\\00F1o" ~ '^[0-9]{4}$'
        ), join_hex as (
          select c.anio,
                 h.id_3 as hex_id,
                 h."MPIO_CCDGO" as mpio_ccdgo,
                 h."MPIO_CNMBR" as municipio
          from casos_limpios c
          join public.hexagonos h
            on h.geometry && c.geom
           and ST_Covers(h.geometry, c.geom)
        )
        select anio,
               count(*) as casos_en_hexagonos,
               count(distinct hex_id) as hexagonos_con_casos,
               count(distinct mpio_ccdgo) as municipios,
               max(casos_hex) as max_casos_en_un_hexagono
        from (
          select anio, hex_id, mpio_ccdgo, municipio, count(*) over (partition by anio, hex_id) as casos_hex
          from join_hex
        ) s
        group by anio
        order by anio
    """,
    "ranking_municipal": """
        with join_hex as (
          select U&"a\\00F1o"::int as anio,
                 h."MPIO_CCDGO" as mpio_ccdgo,
                 h."MPIO_CNMBR" as municipio,
                 h.id_3 as hex_id
          from public.dengue_m d
          join public.hexagonos h
            on h.geometry && d.geom
           and ST_Covers(h.geometry, d.geom)
          where d.geom is not null
            and ST_X(d.geom) <> 0
            and ST_Y(d.geom) <> 0
            and U&"a\\00F1o" ~ '^[0-9]{4}$'
        )
        select mpio_ccdgo,
               max(municipio) as municipio,
               count(*) as casos,
               count(distinct hex_id) as hexagonos_con_casos,
               count(*) filter (where anio = 2024) as casos_2024
        from join_hex
        group by mpio_ccdgo
        order by casos desc
        limit 20
    """,
    "ranking_hex": """
        with join_hex as (
          select U&"a\\00F1o"::int as anio,
                 h.id_3 as hex_id,
                 h."MPIO_CCDGO" as mpio_ccdgo,
                 h."MPIO_CNMBR" as municipio
          from public.dengue_m d
          join public.hexagonos h
            on h.geometry && d.geom
           and ST_Covers(h.geometry, d.geom)
          where d.geom is not null
            and ST_X(d.geom) <> 0
            and ST_Y(d.geom) <> 0
            and U&"a\\00F1o" ~ '^[0-9]{4}$'
        )
        select hex_id,
               max(mpio_ccdgo) as mpio_ccdgo,
               max(municipio) as municipio,
               count(*) as casos_total,
               count(*) filter (where anio = 2024) as casos_2024,
               count(distinct anio) as anios_con_casos
        from join_hex
        group by hex_id
        order by casos_total desc
        limit 20
    """,
}


STYLE = """
html { scroll-behavior: smooth; }
body {
  margin: 0;
  font-family: Inter, Segoe UI, Arial, sans-serif;
  background: #f5f7fb;
  color: #11233f;
}
.page { max-width: 1180px; margin: 0 auto; padding: 34px 22px 70px; }
.observatory-back {
  display: inline-flex;
  align-items: center;
  margin-bottom: 16px;
  padding: 10px 13px;
  border: 1px solid #0f5d65;
  border-radius: 6px;
  background: white;
  color: #0f5d65;
  font-size: 13px;
  font-weight: 800;
  text-decoration: none;
}
.observatory-back:hover { background: #eef8f7; color: #0f2b46; }
.hero {
  background: linear-gradient(135deg, #0f2b46, #155c63);
  color: white;
  padding: 36px;
  border-radius: 8px;
  box-shadow: 0 18px 45px rgba(17, 35, 63, .18);
}
.hero h1 { margin: 0 0 12px; font-size: clamp(30px, 4vw, 48px); line-height: 1.05; }
.hero p { max-width: 780px; margin: 0; color: #dceef2; font-size: 17px; line-height: 1.6; }
.toc { display: flex; flex-wrap: wrap; gap: 8px; margin: 18px 0 8px; }
.toc a {
  color: #0f5d65;
  background: white;
  border: 1px solid #d6e2ec;
  padding: 8px 10px;
  border-radius: 6px;
  text-decoration: none;
  font-size: 13px;
  font-weight: 700;
}
section {
  background: white;
  margin-top: 22px;
  padding: 26px;
  border: 1px solid #dce5ee;
  border-radius: 8px;
  box-shadow: 0 10px 28px rgba(17, 35, 63, .06);
}
h2 { margin: 0 0 10px; font-size: 25px; color: #0f2b46; }
h3 { margin: 20px 0 8px; color: #25415f; }
p { line-height: 1.6; }
.muted { color: #62748a; }
.metrics {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: 12px;
  margin: 18px 0;
}
.metric {
  border: 1px solid #d8e3ee;
  border-left: 4px solid #159a9c;
  padding: 14px;
  border-radius: 8px;
  background: #fbfdff;
}
.metric span { display: block; color: #62748a; font-size: 12px; font-weight: 800; text-transform: uppercase; }
.metric strong { display: block; font-size: 26px; margin: 7px 0 2px; color: #0f2b46; }
.metric small { color: #68788b; }
.callout {
  border-left: 5px solid #d95f02;
  background: #fff7ed;
  padding: 13px 15px;
  border-radius: 6px;
  margin: 15px 0;
}
.table-wrap { overflow-x: auto; border: 1px solid #dce5ee; border-radius: 8px; margin-top: 12px; }
table { width: 100%; border-collapse: collapse; background: white; min-width: 680px; }
th, td { padding: 11px 12px; border-bottom: 1px solid #e9eff5; text-align: left; font-size: 14px; }
th { background: #eef5f8; color: #1f3b57; font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
tr:last-child td { border-bottom: 0; }
td:not(:first-child) { text-align: right; }
.next {
  margin-top: 20px;
  padding: 15px;
  background: #eef8f7;
  border: 1px solid #b8dcda;
  border-radius: 8px;
}
.button-link {
  display: inline-block;
  margin-top: 12px;
  background: #0f5d65;
  color: white;
  text-decoration: none;
  font-weight: 800;
  padding: 10px 14px;
  border-radius: 6px;
}
code { background: #eef2f6; padding: 2px 5px; border-radius: 4px; }
"""


def build_html() -> str:
    hex_info = query(SQL["hex_info"])[0]
    casos_info = query(SQL["casos_info"])[0]
    casos_anio = query(SQL["casos_anio"])
    resumen_hex_anio = query(SQL["resumen_hex_anio"])
    ranking_municipal = query(SQL["ranking_municipal"])
    ranking_hex = query(SQL["ranking_hex"])

    metrics = "\n".join(
        [
            card("Hexagonos", hex_info["total_hexagonos"], "public.hexagonos"),
            card("Municipios", hex_info["municipios"], "Cobertura departamental"),
            card("Casos", casos_info["total_casos"], "public.dengue_m"),
            card("Coordenadas cero", casos_info["coord_cero"], "Se excluyen del analisis espacial"),
        ]
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Informe dengue por hexagonos</title>
  <style>{STYLE}</style>
</head>
<body>
  <main class="page">
    <a class="observatory-back" href="../frontend/Geodata%20Salud.html">Volver al observatorio</a>
    <header class="hero">
      <h1>Analisis de dengue por hexagonos</h1>
      <p>Informe visual paso a paso para revisar los insumos, la calidad de datos y el geoproceso espacial entre <code>public.dengue_m</code> y <code>public.hexagonos</code>.</p>
    </header>

    <nav class="toc">
      <a href="#insumos">1. Insumos</a>
      <a href="#anios">2. Casos por ano</a>
      <a href="#geoproceso">3. Geoproceso</a>
      <a href="#municipios">4. Ranking municipal</a>
      <a href="#hexagonos">5. Hexagonos criticos</a>
      <a href="#siguiente">Siguiente paso</a>
    </nav>

    <section id="insumos">
      <h2>1. Insumos base</h2>
      <p>La base responde con PostGIS activo. La malla tiene geometria valida y cubre los 42 municipios del Valle del Cauca.</p>
      <div class="metrics">{metrics}</div>
      <h3>Revision de la grilla</h3>
      {table([hex_info], [
        ("total_hexagonos", "Hexagonos"),
        ("municipios", "Municipios"),
        ("sin_geometria", "Sin geometria"),
        ("invalidas", "Invalidas"),
        ("polygon", "Polygon"),
        ("multipolygon", "Multipolygon"),
        ("area_prom_m2", "Area prom. m2"),
      ])}
      <h3>Revision de casos puntuales</h3>
      {table([casos_info], [
        ("total_casos", "Casos"),
        ("con_geom", "Con geom"),
        ("sin_geom", "Sin geom"),
        ("invalidas", "Invalidas"),
        ("coord_cero", "Coord. cero"),
      ])}
    </section>

    <section id="anios">
      <h2>2. Casos por ano</h2>
      <p>Este bloque separa el total notificado de los casos con coordenadas validas. Los registros con coordenadas cero quedan documentados para excluirlos del cruce espacial.</p>
      <div class="callout"><strong>Nota de calidad:</strong> 2024 es el ano con mayor volumen y tambien concentra la mayor cantidad de coordenadas cero.</div>
      {table(casos_anio, [
        ("anio", "Ano"),
        ("casos", "Casos"),
        ("casos_coord_validas", "Coord. validas"),
        ("coord_cero", "Coord. cero"),
      ])}
    </section>

    <section id="geoproceso">
      <h2>3. Geoproceso espacial</h2>
      <p>Se usa <code>ST_Covers(hexagono, punto)</code> para asignar cada caso valido al hexagono que lo contiene, incluyendo puntos sobre borde.</p>
      {table(resumen_hex_anio, [
        ("anio", "Ano"),
        ("casos_en_hexagonos", "Casos en hexagonos"),
        ("hexagonos_con_casos", "Hexagonos con casos"),
        ("municipios", "Municipios"),
        ("max_casos_en_un_hexagono", "Max. en un hexagono"),
      ])}
    </section>

    <section id="municipios">
      <h2>4. Ranking municipal</h2>
      <p>Municipios con mayor carga de casos asignados a hexagonos. Esta tabla ayuda a priorizar la lectura del mapa dinamico.</p>
      {table(ranking_municipal, [
        ("mpio_ccdgo", "Codigo"),
        ("municipio", "Municipio"),
        ("casos", "Casos"),
        ("hexagonos_con_casos", "Hexagonos"),
        ("casos_2024", "Casos 2024"),
      ])}
    </section>

    <section id="hexagonos">
      <h2>5. Hexagonos criticos</h2>
      <p>Hexagonos con mayor acumulado de casos y persistencia temporal. Estos son candidatos para inspeccion puntual y seguimiento territorial.</p>
      {table(ranking_hex, [
        ("hex_id", "Hex ID"),
        ("mpio_ccdgo", "Codigo"),
        ("municipio", "Municipio"),
        ("casos_total", "Casos total"),
        ("casos_2024", "Casos 2024"),
        ("anios_con_casos", "Anos con casos"),
      ])}
    </section>

    <section id="siguiente">
      <h2>Siguiente paso</h2>
      <div class="next">
        Abrir el mapa dinamico <code>outputs/mapa_dengue_hexagonos.html</code> y revisar visualmente 2024, luego comparar contra 2020 y 2023 para distinguir focos persistentes de brotes coyunturales.
        <br><a class="button-link" href="mapa_dengue_hexagonos.html">Abrir mapa dinamico</a>
      </div>
    </section>
  </main>
</body>
</html>"""


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(build_html(), encoding="utf-8")
    print(f"Informe guardado: {OUTPUT}")


if __name__ == "__main__":
    main()
