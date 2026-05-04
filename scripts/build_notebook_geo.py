"""Inserta sección de geoprocesos y coropléticos en analisis_dengue.ipynb"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NB   = ROOT / "notebooks" / "analisis_dengue.ipynb"

with open(NB, encoding="utf-8") as f:
    nb = json.load(f)

def md(src):
    return {"cell_type":"markdown","id":"","metadata":{},"source":[src]}

def code(src):
    return {"cell_type":"code","execution_count":None,"id":"","metadata":{},"outputs":[],"source":[src]}

# ── Celdas nuevas ─────────────────────────────────────────────────────────────
cells = [

md("""---
## 11. Geoprocesos y Mapas Coropléticos

Unión espacial de `valle_mun` (casos por municipio y año) con los polígonos de
`municipios_valle` para construir mapas coropléticos de distribución del dengue 2019–2026."""),

code("""\
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import matplotlib.cm as cm
from matplotlib.colors import Normalize
import numpy as np
import warnings
warnings.filterwarnings("ignore")

# Polígonos municipales desde PostGIS
municipios_geo = gpd.read_postgis(
    "SELECT mpio_ccdgo_full, mpio_cnmbr, geometry FROM municipios_valle",
    engine, geom_col="geometry"
)
print(f"Polígonos cargados : {len(municipios_geo)}")
print(f"CRS                : {municipios_geo.crs}")
municipios_geo.head(3)"""),

code("""\
# Verificación geométrica y áreas
print(f"Tipos de geometría   : {municipios_geo.geometry.geom_type.value_counts().to_dict()}")
print(f"Geometrías inválidas : {(~municipios_geo.geometry.is_valid).sum()}")
print(f"Bbox (WGS84)         : {municipios_geo.total_bounds.round(4)}")

mun_m = municipios_geo.to_crs(3115)
mun_m["area_km2"] = (mun_m.geometry.area / 1e6).round(2)

print(f"\\nÁrea total Valle del Cauca : {mun_m['area_km2'].sum():.0f} km²")
print(f"Municipio mayor : {mun_m.loc[mun_m['area_km2'].idxmax(), 'mpio_cnmbr']} — {mun_m['area_km2'].max():.0f} km²")
print(f"Municipio menor : {mun_m.loc[mun_m['area_km2'].idxmin(), 'mpio_cnmbr']} — {mun_m['area_km2'].min():.0f} km²")
mun_m[["mpio_cnmbr","area_km2"]].sort_values("area_km2", ascending=False).head(10)"""),

code("""\
# Join espacial: polígonos + datos de dengue (todos los años)
_gdf = gdf.copy()
_gdf.columns = _gdf.columns.str.upper()

gdf_geo = municipios_geo.merge(
    _gdf[["MPIO_CCDGO","AÑO","CONTEO_DENGUE","INCIDENCIA_DENGUE","POBLACIÓN"]],
    left_on="mpio_ccdgo_full",
    right_on="MPIO_CCDGO",
    how="left",
)
gdf_geo.columns = gdf_geo.columns.str.lower()

print(f"Registros tras join : {len(gdf_geo)}")
print(f"Años disponibles    : {sorted(gdf_geo['año'].dropna().astype(int).unique())}")
print(f"Nulos incidencia    : {gdf_geo['incidencia_dengue'].isna().sum()}")
gdf_geo[["mpio_cnmbr","año","conteo_dengue","incidencia_dengue"]].head(8)"""),

md("### 11.1 Coroplético año seleccionado — Incidencia y Casos"),

code("""\
anio_vis = ANIO
df_anio  = gdf_geo[gdf_geo["año"] == anio_vis].copy()

fig, axes = plt.subplots(1, 2, figsize=(16, 9))

for ax, col, title, cmap in [
    (axes[0], "incidencia_dengue", f"Incidencia x 100k hab ({anio_vis})", "YlOrRd"),
    (axes[1], "conteo_dengue",     f"Casos absolutos ({anio_vis})",        "OrRd"),
]:
    df_anio.plot(
        column=col, ax=ax,
        cmap=cmap, scheme="quantiles", k=5,
        edgecolor="white", linewidth=0.6,
        missing_kwds={"color": "#cccccc"},
        legend=True,
        legend_kwds={"title": col.replace("_"," ").title(),
                     "loc": "lower left", "fontsize": 8},
    )
    top8 = df_anio.nlargest(8, col)
    for _, r in top8.iterrows():
        cx, cy = r.geometry.centroid.x, r.geometry.centroid.y
        ax.annotate(r["mpio_cnmbr"].title(), (cx, cy),
                    fontsize=6.5, ha="center", color="#1a1a1a", fontweight="bold")
    ax.set_title(title, fontsize=12, pad=10)
    ax.set_axis_off()

plt.suptitle("Valle del Cauca — Distribución espacial del dengue", fontsize=14, y=1.01)
plt.tight_layout()
plt.show()"""),

md("### 11.2 Panel multianual — Incidencia x 100k (2019–2024)\n\nEscala de color común para comparar años directamente."),

code("""\
anios_panel  = [a for a in sorted(gdf_geo["año"].dropna().astype(int).unique()) if a <= 2024]
vmax_global  = gdf_geo[gdf_geo["año"].isin(anios_panel)]["incidencia_dengue"].quantile(0.97)
norm_inc     = Normalize(vmin=0, vmax=vmax_global)
cmap_inc     = plt.get_cmap("YlOrRd")

ncols = 3
nrows = -(-len(anios_panel) // ncols)

fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 5.5, nrows * 6))
axes = axes.flatten()

for i, anio in enumerate(anios_panel):
    ax  = axes[i]
    dfa = gdf_geo[gdf_geo["año"] == anio].copy()
    dfa.plot(column="incidencia_dengue", ax=ax, cmap=cmap_inc, norm=norm_inc,
             edgecolor="white", linewidth=0.5, missing_kwds={"color":"#dddddd"})
    if dfa["incidencia_dengue"].notna().any():
        top = dfa.loc[dfa["incidencia_dengue"].idxmax()]
        cx, cy = top.geometry.centroid.x, top.geometry.centroid.y
        ax.annotate(top["mpio_cnmbr"].title(), (cx, cy),
                    fontsize=6, ha="center", color="#1a1a1a", fontweight="bold", va="bottom")
        total = dfa["conteo_dengue"].sum()
        ax.set_title(f"{anio}\\n{total:,.0f} casos totales", fontsize=10, pad=6)
    ax.set_axis_off()

for j in range(len(anios_panel), len(axes)):
    axes[j].set_visible(False)

sm = cm.ScalarMappable(cmap=cmap_inc, norm=norm_inc)
sm.set_array([])
cbar = fig.colorbar(sm, ax=axes[:len(anios_panel)], shrink=0.4, aspect=15, pad=0.02)
cbar.set_label("Incidencia x 100k hab", fontsize=9)

plt.suptitle("Valle del Cauca — Incidencia de dengue por año (escala común)", fontsize=14, y=1.01)
plt.tight_layout()
plt.show()"""),

md("### 11.3 Panel multianual — Casos absolutos (2019–2024)"),

code("""\
vmax_casos  = gdf_geo[gdf_geo["año"].isin(anios_panel)]["conteo_dengue"].quantile(0.95)
norm_casos  = Normalize(vmin=0, vmax=vmax_casos)
cmap_casos  = plt.get_cmap("OrRd")

fig, axes = plt.subplots(nrows, ncols, figsize=(ncols * 5.5, nrows * 6))
axes = axes.flatten()

for i, anio in enumerate(anios_panel):
    ax  = axes[i]
    dfa = gdf_geo[gdf_geo["año"] == anio].copy()
    dfa.plot(column="conteo_dengue", ax=ax, cmap=cmap_casos, norm=norm_casos,
             edgecolor="white", linewidth=0.5, missing_kwds={"color":"#dddddd"})
    inc_med = dfa["incidencia_dengue"].median()
    ax.set_title(f"{anio} — med. inc. {inc_med:.0f}", fontsize=10, pad=6)
    ax.set_axis_off()

for j in range(len(anios_panel), len(axes)):
    axes[j].set_visible(False)

sm2 = cm.ScalarMappable(cmap=cmap_casos, norm=norm_casos)
sm2.set_array([])
cbar2 = fig.colorbar(sm2, ax=axes[:len(anios_panel)], shrink=0.4, aspect=15, pad=0.02)
cbar2.set_label("Casos absolutos", fontsize=9)

plt.suptitle("Valle del Cauca — Casos absolutos de dengue por año (escala común)", fontsize=14, y=1.01)
plt.tight_layout()
plt.show()"""),

md("### 11.4 Clasificación de riesgo — incidencia promedio 2022–2024"),

code("""\
ANIOS_RIESGO = [2022, 2023, 2024]

df_riesgo = (
    gdf_geo[gdf_geo["año"].isin(ANIOS_RIESGO)]
    .groupby("mpio_ccdgo_full", as_index=False)
    .agg(
        inc_prom   = ("incidencia_dengue", "mean"),
        inc_max    = ("incidencia_dengue", "max"),
        casos_sum  = ("conteo_dengue",     "sum"),
        mpio_cnmbr = ("mpio_cnmbr",        "first"),
    )
)

def nivel_riesgo(inc):
    if   inc >= 600:  return "Crítico"
    elif inc >= 300:  return "Alto"
    elif inc >= 100:  return "Medio"
    else:             return "Bajo"

df_riesgo["nivel"] = df_riesgo["inc_prom"].apply(nivel_riesgo)

# Drop mpio_cnmbr before merge — municipios_geo ya la tiene
gdf_riesgo = municipios_geo.merge(
    df_riesgo.drop(columns=["mpio_cnmbr"]), on="mpio_ccdgo_full", how="left"
)

RIESGO_COLORS = {"Crítico":"#b30000","Alto":"#e34a33","Medio":"#fc8d59","Bajo":"#ffffcc"}
ORDEN = ["Crítico","Alto","Medio","Bajo"]

fig, ax = plt.subplots(figsize=(9, 11))
for nivel in ORDEN:
    sub = gdf_riesgo[gdf_riesgo["nivel"] == nivel]
    if len(sub):
        sub.plot(ax=ax, color=RIESGO_COLORS[nivel], edgecolor="white",
                 linewidth=0.7, label=f"{nivel} ({len(sub)} mun.)")

for _, r in gdf_riesgo[gdf_riesgo["nivel"].isin(["Crítico","Alto"])].iterrows():
    cx, cy = r.geometry.centroid.x, r.geometry.centroid.y
    ax.annotate(r["mpio_cnmbr"].title(), (cx, cy),
                fontsize=6.5, ha="center", fontweight="bold", color="#fff")

ax.legend(title="Nivel de riesgo (inc. prom. 2022-2024)", loc="lower left",
          framealpha=0.85, fontsize=9)
ax.set_title("Valle del Cauca — Clasificación de riesgo de dengue\\n"
             "(incidencia promedio 2022–2024 x 100k hab)", fontsize=12, pad=10)
ax.set_axis_off()
plt.tight_layout()
plt.show()

print(df_riesgo.sort_values("inc_prom", ascending=False)
      [["mpio_cnmbr","inc_prom","inc_max","casos_sum","nivel"]]
      .rename(columns={"inc_prom":"Inc. prom","inc_max":"Inc. max","casos_sum":"Casos total"})
      .to_string(index=False))"""),

md("### 11.5 Cambio relativo de incidencia 2023 → 2024"),

code("""\
df_23 = (gdf_geo[gdf_geo["año"]==2023][["mpio_ccdgo_full","incidencia_dengue"]]
         .rename(columns={"incidencia_dengue":"inc_2023"}))
df_24 = (gdf_geo[gdf_geo["año"]==2024][["mpio_ccdgo_full","incidencia_dengue"]]
         .rename(columns={"incidencia_dengue":"inc_2024"}))

df_cambio = df_23.merge(df_24, on="mpio_ccdgo_full")
df_cambio["delta_pct"] = ((df_cambio["inc_2024"] - df_cambio["inc_2023"])
                           / df_cambio["inc_2023"] * 100).round(1)

gdf_cambio = municipios_geo.merge(df_cambio, on="mpio_ccdgo_full", how="left")

fig, axes = plt.subplots(1, 2, figsize=(16, 9))

vabs = df_cambio["delta_pct"].abs().quantile(0.95)
gdf_cambio.plot(
    column="delta_pct", ax=axes[0],
    cmap="RdYlGn_r", vmin=-vabs, vmax=vabs,
    edgecolor="white", linewidth=0.5,
    legend=True, legend_kwds={"label":"Δ% incidencia","shrink":0.5},
)
axes[0].set_title("Cambio relativo de incidencia 2023→2024 (%)", fontsize=11)
axes[0].set_axis_off()

nombres = (gdf_geo[gdf_geo["año"]==2024][["mpio_ccdgo_full","mpio_cnmbr"]]
           .drop_duplicates())
top_pos = df_cambio.nlargest(5,  "delta_pct")
top_neg = df_cambio.nsmallest(5, "delta_pct")
df_top  = (pd.concat([top_pos, top_neg])
           .merge(nombres, on="mpio_ccdgo_full")
           .sort_values("delta_pct", ascending=True))

colors_bar = ["#2166ac" if v < 0 else "#d73027" for v in df_top["delta_pct"]]
axes[1].barh(df_top["mpio_cnmbr"].str.title(), df_top["delta_pct"],
             color=colors_bar, edgecolor="white")
axes[1].axvline(0, color="#666", linewidth=1)
axes[1].set_xlabel("Δ% incidencia 2023→2024")
axes[1].set_title("Top 5 aumentos y reducciones", fontsize=11)
axes[1].tick_params(axis="y", labelsize=8)

plt.suptitle("Variación de incidencia de dengue 2023 → 2024 — Valle del Cauca",
             fontsize=13, y=1.01)
plt.tight_layout()
plt.show()"""),

]

# Insertar antes de la última celda
insert_pos = len(nb["cells"]) - 1
for i, cell in enumerate(cells):
    cell["id"] = f"geo_{i:03d}"
    nb["cells"].insert(insert_pos + i, cell)

print(f"Celdas insertadas : {len(cells)}")
print(f"Total celdas ahora: {len(nb['cells'])}")

with open(NB, "w", encoding="utf-8") as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print("Guardado OK ->", NB)
