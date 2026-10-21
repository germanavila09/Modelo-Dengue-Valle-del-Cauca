"""Mapas y gráficos estáticos (PNG) del Objetivo 1 para el informe Word.

Lee los resultados de ``scripts/clusters_hexagonos.py`` y escribe las figuras en
``outputs/clusters_hexagonos/figuras/``.

Privacidad en los mapas: no se rotulan conteos; los atípicos HL/LH solo se
dibujan cuando el hexágono tiene al menos MIN_CASOS_ZONA casos en el periodo
mostrado (si no, se muestran como no significativos), para no señalar casos
aislados.

Uso:
    python scripts/figuras_objetivo1.py [--fuente html|db] [--puntos-legado outputs/mapa_actual.html]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import clusters_hexagonos as ch  # noqa: E402

ENTRADA = ROOT / "outputs" / "clusters_hexagonos"
SALIDA = ENTRADA / "figuras"
CRS = ch.CRS_METRICO
CORTO = {"Guadalajara de Buga": "Buga"}
ORDEN = ["76520", "76111", "76834", "76364"]
ANIOS = [str(a) for a in ch.ANIOS]

INK, INK2, MUTED, GRID = "#1b1b1a", "#52514e", "#6f6d68", "#e1e0d9"
LISA_COL = {"HH": "#b2182b", "LL": "#2166ac", "HL": "#ef8a62", "LH": "#67a9cf", "ns": "#e4e3de"}
LISA_LAB = {"HH": "Alto-alto", "LL": "Bajo-bajo", "HL": "Alto-bajo", "LH": "Bajo-alto", "ns": "No significativo"}
SIG_COL = {"0.001": "#00441b", "0.01": "#238b45", "0.05": "#74c476", "ns": "#e4e3de"}
GI_COL = {"c99": "#b2182b", "c95": "#ef8a62", "c90": "#fddbc7", "f90": "#d1e5f0", "f95": "#67a9cf", "f99": "#2166ac", "ns": "#e4e3de"}
GI_LAB = {"c99": "Caliente 99 %", "c95": "Caliente 95 %", "c90": "Caliente 90 %",
          "f90": "Frío 90 %", "f95": "Frío 95 %", "f99": "Frío 99 %", "ns": "No significativo"}
PERS_COL = {"persistente": "#b2182b", "intermitente": "#d6604d", "esporadico": "#ee9068", "nunca": "#e4e3de"}
SERIE = {"76520": "#2a78d6", "76111": "#eb6834", "76834": "#1baf7a", "76364": "#eda100"}

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9.5, "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 10.5, "figure.dpi": 100, "savefig.dpi": 200,
})


def nombre(m: str) -> str:
    n = ch.MUNICIPIOS[m]
    return CORTO.get(n, n)


def guardar(fig, archivo: str):
    fig.savefig(SALIDA / archivo, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("  ", archivo)


# ── Datos ─────────────────────────────────────────────────────────────────────

def cargar(fuente: str, puntos_legado: Path | None):
    if fuente == "db":
        conteos = ch.cargar_desde_db()
    else:
        conteos = ch.cargar_desde_html(ROOT / "outputs" / "mapa_dengue_hexagonos.html")
        if puntos_legado and puntos_legado.exists():
            conteos = ch.clasificar_geocodificacion_legado(conteos, puntos_legado)
    malla, panel = ch.construir_panel(conteos)
    urbana = {}
    for m in ORDEN:
        sub, _ = ch.area_urbana(malla[malla["mpio_ccdgo"] == m].reset_index(drop=True))
        urbana[m] = sub.to_crs(CRS)
    res = pd.read_csv(ENTRADA / "interno" / "lisa_gi_hexagono_anio.csv", dtype={"mpio_ccdgo": str, "anio": str})
    res = res[res["variante"] == "principal"]
    met = pd.read_csv(ENTRADA / "metricas_municipio_anio.csv", dtype={"mpio_ccdgo": str, "anio": str})
    municipios = gpd.read_file(ROOT / "shp" / "Municipios.shp")
    municipios = municipios[municipios["DPTO_CCDGO"] == "76"].copy()
    municipios["codigo"] = municipios["DPTO_CCDGO"] + municipios["MPIO_CCDGO"]
    municipios = municipios.to_crs(CRS)
    return malla, panel, urbana, res, met, municipios


def categoria_lisa(df: pd.DataFrame) -> pd.Series:
    cat = df["lisa"].where(df["lisa"].isin(LISA_COL), "ns")
    atipico_pequeno = cat.isin(["HL", "LH"]) & (df["casos"] < ch.MIN_CASOS_ZONA)
    return cat.mask(atipico_pequeno, "ns")


def categoria_sig(df: pd.DataFrame) -> pd.Series:
    cat = categoria_lisa(df)
    p = df["lisa_p"]
    out = np.where(cat == "ns", "ns", np.where(p <= 0.001, "0.001", np.where(p <= 0.01, "0.01", "0.05")))
    return pd.Series(out, index=df.index)


def categoria_gi(df: pd.DataFrame) -> pd.Series:
    p, z = df["gi_p"], df["gi_z"]
    nivel = np.where(p <= 0.01, "99", np.where(p <= 0.05, "95", np.where(p <= 0.10, "90", "")))
    lado = np.where(z > 0, "c", "f")
    return pd.Series(np.where(nivel == "", "ns", np.char.add(lado.astype(str), nivel.astype(str))), index=df.index)


# ── Elementos de mapa ─────────────────────────────────────────────────────────

def encuadre(gdf: gpd.GeoDataFrame):
    """Encuadre en el componente urbano más grande (cabecera)."""
    w, _ = ch.pesos_hexagonales(gdf.to_crs(4326))
    etiquetas = pd.Series(w.component_labels, index=w.id_order)
    cab = gdf[gdf["hex_id"].isin(etiquetas[etiquetas == etiquetas.value_counts().idxmax()].index)]
    x0, y0, x1, y1 = cab.total_bounds
    lado = max(x1 - x0, y1 - y0) * 1.08
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return cx - lado / 2, cx + lado / 2, cy - lado / 2, cy + lado / 2


def adornos(ax, escala=True):
    from matplotlib_scalebar.scalebar import ScaleBar

    if escala:
        ax.add_artist(ScaleBar(1, units="m", location="lower left", box_alpha=0.75, font_properties={"size": 7.5},
                               length_fraction=0.25, color=INK2))
    ax.annotate("N", xy=(0.95, 0.95), xytext=(0.95, 0.84), xycoords="axes fraction", ha="center", va="center",
                fontsize=9, fontweight="bold", color=INK2,
                arrowprops=dict(arrowstyle="-|>", color=INK2, lw=1.2))
    ax.set_xticks([]), ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(True), s.set_color("#d6d5ce"), s.set_linewidth(0.6)


def mapa_categorias(ax, base, valores, colores, limites, titulo=None):
    g = base.merge(valores, on="hex_id", how="left").fillna({"cat": "ns"})
    g.plot(ax=ax, color=g["cat"].map(colores), edgecolor="white", linewidth=0.15)
    ax.set_xlim(limites[0], limites[1]), ax.set_ylim(limites[2], limites[3])
    if titulo:
        ax.set_title(titulo, loc="left")
    adornos(ax)


def leyenda(fig, colores, etiquetas, orden, ncol=None, y=0.0):
    fig.legend(handles=[Patch(facecolor=colores[k], edgecolor="none", label=etiquetas[k]) for k in orden],
               loc="lower center", ncol=ncol or len(orden), frameon=False, bbox_to_anchor=(0.5, y), fontsize=8.5)


# ── Figuras ───────────────────────────────────────────────────────────────────

def fig_localizacion(municipios):
    fig, ax = plt.subplots(figsize=(5.2, 6.4))
    municipios.plot(ax=ax, color="#efeee9", edgecolor="#b9b7ae", linewidth=0.4)
    sel = municipios[municipios["codigo"].isin(ORDEN)]
    sel.plot(ax=ax, color=[SERIE[c] for c in sel["codigo"]], edgecolor="white", linewidth=0.6, alpha=0.9)
    for _, r in sel.iterrows():
        p = r.geometry.representative_point()
        ax.annotate(nombre(r["codigo"]), xy=(p.x, p.y), xytext=(14, 0), textcoords="offset points", fontsize=9,
                    fontweight="bold", color=INK, va="center",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="none", alpha=0.85))
    adornos(ax)
    ax.set_title("Valle del Cauca: municipios de estudio", loc="left")
    guardar(fig, "f01_localizacion.png")


def fig_geocodificacion():
    cal = pd.read_csv(ENTRADA / "calidad_geocodificacion.csv", dtype={"mpio_ccdgo": str}).set_index("mpio_ccdgo").loc[ORDEN]
    ok = 100 - cal["pct_sumidero"] - cal["pct_centroide"]
    fig, ax = plt.subplots(figsize=(7.2, 2.7))
    y = np.arange(len(ORDEN))[::-1]
    segs = [(ok, "#2a78d6", "Ubicación individual"), (cal["pct_centroide"], "#f0a36e", "Probable centroide de barrio"),
            (cal["pct_sumidero"], "#c4501f", "Punto por defecto (excluido)")]
    izq = np.zeros(len(ORDEN))
    for vals, col, lab in segs:
        v = vals.to_numpy()
        ax.barh(y, v, left=izq, color=col, height=0.62, label=lab, edgecolor="white", linewidth=1.5)
        for yi, xi, vi in zip(y, izq, v):
            if vi >= 7:
                ax.text(xi + vi / 2, yi, f"{vi:.0f} %", ha="center", va="center", fontsize=8.5, fontweight="bold",
                        color="white" if col != "#f0a36e" else INK)
        izq += v
    ax.set_yticks(y, [nombre(m) for m in ORDEN]), ax.set_xlim(0, 100), ax.set_xlabel("% de los casos 2019–2023")
    ax.spines["left"].set_visible(False), ax.tick_params(axis="y", length=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.32), ncol=3, frameon=False, fontsize=8.5)
    guardar(fig, "f02_geocodificacion.png")


def fig_moran_anual(met):
    fig, ax = plt.subplots(figsize=(7.2, 3.4))
    for m in ORDEN:
        d = met[(met["variante"] == "principal") & (met["mpio_ccdgo"] == m) & (met["anio"].isin(ANIOS))].sort_values("anio")
        x = d["anio"].astype(int)
        ax.plot(x, d["moran_I"], color=SERIE[m], lw=2, zorder=2)
        sig = d["moran_p"] < 0.05
        ax.scatter(x[sig], d["moran_I"][sig], s=36, color=SERIE[m], zorder=3, edgecolor="white", linewidth=1)
        ax.scatter(x[~sig], d["moran_I"][~sig], s=36, facecolor="white", edgecolor=SERIE[m], linewidth=1.6, zorder=3)
        ax.annotate(nombre(m), xy=(x.iloc[-1], d["moran_I"].iloc[-1]), xytext=(8, 0), textcoords="offset points",
                    va="center", fontsize=8.5, color=INK2)
    ax.axhline(0, color="#c3c2b7", lw=1)
    ax.grid(axis="y", color=GRID, lw=0.8), ax.set_axisbelow(True)
    ax.set_xticks([int(a) for a in ANIOS]), ax.set_xlim(2018.7, 2023.8)
    ax.set_ylabel("I de Moran")
    ax.legend(handles=[Line2D([], [], marker="o", ls="", color=INK2, label="p < 0,05"),
                       Line2D([], [], marker="o", ls="", mfc="white", mec=INK2, label="No significativo")],
              loc="upper right", frameon=False, fontsize=8.5)
    guardar(fig, "f03_moran_anual.png")


def fig_moran_dispersion(urbana, res, met):
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 6.6))
    for ax, m in zip(axes.flat, ORDEN):
        w, _ = ch.pesos_hexagonales(urbana[m].to_crs(4326))
        d = res[(res["mpio_ccdgo"] == m) & (res["anio"] == "2019-2023")].set_index("hex_id").reindex(w.id_order)
        y = d["casos"].to_numpy(float)
        z = (y - y.mean()) / y.std()
        lag = np.array([np.mean(z[[w.id_order.index(n) for n in w.neighbors[h]]]) if w.neighbors[h] else np.nan
                        for h in w.id_order])
        cat = categoria_lisa(d.reset_index()).to_numpy()
        ok = ~np.isnan(lag)
        ax.scatter(z[ok], lag[ok], s=9, c=[LISA_COL[c] for c in cat[ok]], alpha=0.85, linewidths=0)
        ax.axhline(0, color="#c3c2b7", lw=0.8), ax.axvline(0, color="#c3c2b7", lw=0.8)
        b = np.polyfit(z[ok], lag[ok], 1)
        xs = np.linspace(z[ok].min(), z[ok].max(), 10)
        ax.plot(xs, np.polyval(b, xs), color=INK, lw=1.2)
        r = met[(met["variante"] == "principal") & (met["mpio_ccdgo"] == m) & (met["anio"] == "2019-2023")].iloc[0]
        ax.set_title(f"{nombre(m)}   I = {r['moran_I']:.3f}  (p = {r['moran_p']:.3f})", loc="left", fontsize=9.5)
        ax.set_xlabel("Casos estandarizados (z)", fontsize=8.5), ax.set_ylabel("Rezago espacial de z", fontsize=8.5)
        ax.grid(color=GRID, lw=0.6), ax.set_axisbelow(True)
    leyenda(fig, LISA_COL, LISA_LAB, ["HH", "LL", "HL", "LH", "ns"], y=-0.02)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    guardar(fig, "f04_moran_dispersion.png")


def fig_lisa_municipio(urbana, res, municipios):
    """Una figura por municipio: mapa de clústeres LISA y mapa de significancia (2019–2023)."""
    for i, m in enumerate(ORDEN, start=5):
        base = urbana[m]
        d = res[(res["mpio_ccdgo"] == m) & (res["anio"] == "2019-2023")].copy()
        d["cat"] = categoria_lisa(d)
        s = d[["hex_id"]].assign(cat=categoria_sig(d))
        lim = encuadre(base)
        fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.1))
        borde = municipios[municipios["codigo"] == m]
        for ax in axes:
            borde.boundary.plot(ax=ax, color="#b9b7ae", lw=0.8)
            base.plot(ax=ax, color="#f3f2ee", edgecolor="white", linewidth=0.15)
        mapa_categorias(axes[0], base, d[["hex_id", "cat"]], LISA_COL, lim, "Mapa de clústeres LISA")
        mapa_categorias(axes[1], base, s, SIG_COL, lim, "Mapa de significancia")
        h1 = [Patch(facecolor=LISA_COL[k], label=LISA_LAB[k]) for k in ["HH", "LL", "HL", "LH", "ns"]]
        h2 = [Patch(facecolor=SIG_COL[k], label=lab) for k, lab in
              [("0.001", "p ≤ 0,001"), ("0.01", "p ≤ 0,01"), ("0.05", "p ≤ 0,05"), ("ns", "No significativo")]]
        axes[0].legend(handles=h1, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=3, frameon=False, fontsize=7.5)
        axes[1].legend(handles=h2, loc="upper center", bbox_to_anchor=(0.5, -0.02), ncol=2, frameon=False, fontsize=7.5)
        fig.suptitle(f"{nombre(m)} · casos de dengue 2019–2023 por hexágono de 200 m", x=0.01, ha="left",
                     fontsize=11, fontweight="bold")
        fig.tight_layout()
        guardar(fig, f"f{i:02d}_lisa_{nombre(m).lower().replace('á', 'a').replace('í', 'i')}.png")


def fig_lisa_anual(urbana, res):
    fig, axes = plt.subplots(len(ORDEN), len(ANIOS), figsize=(7.4, 6.6))
    for i, m in enumerate(ORDEN):
        base = urbana[m]
        lim = encuadre(base)
        for j, a in enumerate(ANIOS):
            ax = axes[i, j]
            d = res[(res["mpio_ccdgo"] == m) & (res["anio"] == a)].copy()
            d["cat"] = categoria_lisa(d)
            g = base.merge(d[["hex_id", "cat"]], on="hex_id", how="left").fillna({"cat": "ns"})
            g.plot(ax=ax, color=g["cat"].map(LISA_COL), linewidth=0)
            ax.set_xlim(lim[0], lim[1]), ax.set_ylim(lim[2], lim[3])
            ax.set_xticks([]), ax.set_yticks([])
            for s in ax.spines.values():
                s.set_visible(False)
            if i == 0:
                ax.set_title(a, fontsize=9.5)
            if j == 0:
                ax.set_ylabel(nombre(m), fontsize=9.5, color=INK)
    leyenda(fig, LISA_COL, LISA_LAB, ["HH", "LL", "HL", "LH", "ns"], y=-0.01)
    fig.tight_layout(rect=(0, 0.035, 1, 1), h_pad=0.4, w_pad=0.2)
    guardar(fig, "f09_lisa_anual.png")


def fig_gi(urbana, res, municipios):
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 7.4))
    for ax, m in zip(axes.flat, ORDEN):
        base = urbana[m]
        d = res[(res["mpio_ccdgo"] == m) & (res["anio"] == "2019-2023")].copy()
        d["cat"] = categoria_gi(d)
        municipios[municipios["codigo"] == m].boundary.plot(ax=ax, color="#b9b7ae", lw=0.8)
        mapa_categorias(ax, base, d[["hex_id", "cat"]], GI_COL, encuadre(base), nombre(m))
    leyenda(fig, GI_COL, GI_LAB, ["c99", "c95", "c90", "ns", "f90", "f95", "f99"], ncol=4, y=-0.02)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    guardar(fig, "f10_gi_hotspots.png")


def fig_persistencia_mapa(urbana, res, municipios):
    anual = res[res["anio"].isin(ANIOS)]
    pers = anual.assign(hh=categoria_lisa(anual) == "HH").groupby("hex_id")["hh"].sum()
    clase = pd.cut(pers, [-1, 0, 1, 2, 5], labels=["nunca", "esporadico", "intermitente", "persistente"]).astype(str)
    etiquetas = {"persistente": "Persistente (≥3 años)", "intermitente": "Intermitente (2 años)",
                 "esporadico": "Esporádico (1 año)", "nunca": "Nunca alto-alto"}
    fig, axes = plt.subplots(2, 2, figsize=(7.4, 7.4))
    for ax, m in zip(axes.flat, ORDEN):
        base = urbana[m]
        municipios[municipios["codigo"] == m].boundary.plot(ax=ax, color="#b9b7ae", lw=0.8)
        v = clase.rename("cat").reset_index()
        mapa_categorias(ax, base, v, PERS_COL, encuadre(base), nombre(m))
    leyenda(fig, PERS_COL, etiquetas, ["persistente", "intermitente", "esporadico", "nunca"], y=-0.01)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    guardar(fig, "f11_persistencia_mapa.png")


def fig_concentracion(met):
    d = met[(met["variante"] == "principal") & (met["anio"] == "2019-2023")].set_index("mpio_ccdgo").loc[ORDEN]
    fig, ax = plt.subplots(figsize=(7.2, 3.2))
    x = np.arange(len(ORDEN)); bw = 0.34
    for k, (col, c, lab) in enumerate([("pct_area_HH", "#a8a69e", "% del área urbana"), ("pct_casos_en_HH", "#b2182b", "% de los casos")]):
        xs = x + (k - 0.5) * (bw + 0.02)
        ax.bar(xs, d[col], width=bw, color=c, label=lab)
        for xi, v in zip(xs, d[col]):
            ax.text(xi, v + 0.6, f"{v:.0f} %", ha="center", fontsize=8.5, color=INK2)
    ax.set_xticks(x, [nombre(m) for m in ORDEN]), ax.set_ylabel("%")
    ax.grid(axis="y", color=GRID, lw=0.8), ax.set_axisbelow(True)
    ax.legend(frameon=False, fontsize=8.5, loc="upper left")
    guardar(fig, "f12_concentracion.png")


def fig_persistencia_barras():
    p = pd.read_csv(ENTRADA / "persistencia_resumen.csv")
    p = p[p["variante"] == "principal"]
    nombres = {ch.MUNICIPIOS[m]: m for m in ORDEN}
    fig, ax = plt.subplots(figsize=(7.2, 2.8))
    y = np.arange(len(ORDEN))[::-1]
    izq = np.zeros(len(ORDEN))
    etiquetas = [("persistente", "Persistente (≥3 años)"), ("intermitente", "Intermitente (2 años)"),
                 ("esporadico", "Esporádico (1 año)"), ("nunca", "Nunca alto-alto")]
    for k, lab in etiquetas:
        v = np.array([p[(p["municipio"] == ch.MUNICIPIOS[m]) & (p["clase"] == k)]["pct_casos_mpio"].sum() for m in ORDEN])
        ax.barh(y, v, left=izq, color=PERS_COL[k], height=0.62, label=lab, edgecolor="white", linewidth=1.5)
        for yi, xi, vi in zip(y, izq, v):
            if vi >= 6:
                ax.text(xi + vi / 2, yi, f"{vi:.0f} %", ha="center", va="center", fontsize=8.5, fontweight="bold",
                        color="white" if k in ("persistente", "intermitente") else INK)
        izq += v
    del nombres
    ax.set_yticks(y, [nombre(m) for m in ORDEN]), ax.set_xlim(0, 100), ax.set_xlabel("% de los casos 2019–2023 del municipio")
    ax.spines["left"].set_visible(False), ax.tick_params(axis="y", length=0)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.3), ncol=4, frameon=False, fontsize=8)
    guardar(fig, "f13_persistencia_barras.png")


def fig_clima():
    c = pd.read_csv(ENTRADA / "clima_anual_municipio.csv", dtype={"mpio_ccdgo": str})
    tabla = np.zeros((len(ORDEN), len(ANIOS)))
    for i, m in enumerate(ORDEN):
        for j, a in enumerate(ANIOS):
            r = c[(c["mpio_ccdgo"] == m) & (c["anio"] == int(a))]
            tabla[i, j] = r["meses_validos"].iloc[0] if len(r) else 0
    fig, ax = plt.subplots(figsize=(5.4, 2.6))
    from matplotlib.colors import BoundaryNorm, ListedColormap
    cmap = ListedColormap(["#eef4fc", "#cde2fb", "#86b6ef", "#3987e5", "#1c5cab"])
    norm = BoundaryNorm([0, 0.5, 4.5, 8.5, 11.5, 12.5], cmap.N)
    ax.imshow(tabla, cmap=cmap, norm=norm, aspect="auto")
    for i in range(len(ORDEN)):
        for j in range(len(ANIOS)):
            v = int(tabla[i, j])
            ax.text(j, i, v, ha="center", va="center", fontsize=9, fontweight="bold", color="white" if v >= 9 else INK)
    ax.set_xticks(range(len(ANIOS)), ANIOS), ax.set_yticks(range(len(ORDEN)), [nombre(m) for m in ORDEN])
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xticks(np.arange(-.5, len(ANIOS)), minor=True), ax.set_yticks(np.arange(-.5, len(ORDEN)), minor=True)
    ax.grid(which="minor", color="white", lw=2), ax.tick_params(which="minor", length=0)
    ax.set_title("Meses con dato climático válido (de 12)", loc="left")
    guardar(fig, "f14_clima_cobertura.png")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--fuente", choices=["db", "html"], default="db")
    parser.add_argument("--puntos-legado", default=None)
    args = parser.parse_args(argv)
    SALIDA.mkdir(parents=True, exist_ok=True)
    malla, panel, urbana, res, met, municipios = cargar(args.fuente, Path(args.puntos_legado) if args.puntos_legado else None)
    print("Figuras en", SALIDA)
    fig_localizacion(municipios)
    fig_geocodificacion()
    fig_moran_anual(met)
    fig_moran_dispersion(urbana, res, met)
    fig_lisa_municipio(urbana, res, municipios)
    fig_lisa_anual(urbana, res)
    fig_gi(urbana, res, municipios)
    fig_persistencia_mapa(urbana, res, municipios)
    fig_concentracion(met)
    fig_persistencia_barras()
    fig_clima()
    # Resumen de Gi* y LISA por municipio para el informe (solo agregados).
    filas = []
    for m in ORDEN:
        d = res[(res["mpio_ccdgo"] == m) & (res["anio"] == "2019-2023")].copy()
        lisa, gi = categoria_lisa(d), categoria_gi(d)
        filas.append({"mpio_ccdgo": m, "municipio": ch.MUNICIPIOS[m], "hexagonos": len(d),
                      **{f"lisa_{k}": int((lisa == k).sum()) for k in ["HH", "LL", "HL", "LH"]},
                      "lisa_atipicos_suprimidos": int((d["lisa"].isin(["HL", "LH"]) & (lisa == "ns")).sum()),
                      **{f"gi_{k}": int((gi == k).sum()) for k in ["c99", "c95", "c90", "f90", "f95", "f99"]}})
    pd.DataFrame(filas).to_csv(ENTRADA / "resumen_lisa_gi_2019_2023.csv", index=False)
    print("   resumen_lisa_gi_2019_2023.csv")


if __name__ == "__main__":
    main()
