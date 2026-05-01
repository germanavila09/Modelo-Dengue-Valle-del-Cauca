import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import seaborn as sns
import pandas as pd
from pathlib import Path

from .transform import columnas_anio

sns.set_theme(style="whitegrid")
plt.rcParams["figure.figsize"] = (12, 6)


def graficar_casos_por_anio(gdf):
    casos = (
        gdf.groupby("año", as_index=False)["conteo_dengue"]
        .sum()
        .sort_values("año")
    )
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.barplot(data=casos, x="año", y="conteo_dengue", ax=ax)
    ax.set_title("Casos de dengue por año")
    ax.set_xlabel("Año")
    ax.set_ylabel("Casos")
    plt.tight_layout()
    return fig


def graficar_top_municipios(gdf, anio, n=15):
    df = gdf[gdf["año"] == anio].sort_values("conteo_dengue", ascending=False).head(n)
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.barplot(data=df, y="MPIO_CNMBR", x="conteo_dengue", ax=ax)
    ax.set_title(f"Top {n} municipios — dengue {anio}")
    ax.set_xlabel("Casos")
    ax.set_ylabel("Municipio")
    plt.tight_layout()
    return fig


def graficar_heatmap(pivot, n=20):
    cols = columnas_anio(pivot)
    tabla = pivot.set_index("MPIO_CNMBR")[cols].copy()
    tabla["total"] = tabla.sum(axis=1)
    tabla = tabla.sort_values("total", ascending=False).drop(columns="total").head(n)
    fig, ax = plt.subplots(figsize=(12, 8))
    sns.heatmap(tabla, annot=True, fmt=".0f", cmap="Reds", ax=ax)
    ax.set_title("Heatmap de casos de dengue por municipio y año")
    plt.tight_layout()
    return fig


def graficar_incidencia_por_anio(gdf):
    inc = (
        gdf.groupby("año", as_index=False)["incidencia_dengue"]
        .mean()
        .sort_values("año")
    )
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.barplot(data=inc, x="año", y="incidencia_dengue", ax=ax, color="#e74c3c")
    ax.set_title("Incidencia promedio de dengue por año (x 100 000 hab.)")
    ax.set_xlabel("Año")
    ax.set_ylabel("Incidencia x 100k")
    plt.tight_layout()
    return fig


def graficar_top_municipios_incidencia(gdf, anio, n=15):
    df = gdf[gdf["año"] == anio].sort_values("incidencia_dengue", ascending=False).head(n)
    fig, ax = plt.subplots(figsize=(12, 7))
    sns.barplot(data=df, y="MPIO_CNMBR", x="incidencia_dengue", ax=ax, color="#e74c3c")
    ax.set_title(f"Top {n} municipios por incidencia — {anio} (x 100k hab.)")
    ax.set_xlabel("Incidencia x 100k")
    ax.set_ylabel("Municipio")
    plt.tight_layout()
    return fig


def graficar_scatter_poblacion_incidencia(gdf, anio):
    df = gdf[gdf["año"] == anio].dropna(subset=["población", "incidencia_dengue"]).copy()
    fig, ax = plt.subplots(figsize=(11, 7))
    sns.scatterplot(
        data=df, x="población", y="incidencia_dengue",
        size="conteo_dengue", sizes=(40, 600),
        hue="incidencia_dengue", palette="Reds", legend=False, ax=ax
    )
    for _, row in df.iterrows():
        ax.annotate(
            row["MPIO_CNMBR"],
            (row["población"], row["incidencia_dengue"]),
            fontsize=7, alpha=0.75,
            xytext=(4, 3), textcoords="offset points"
        )
    ax.set_title(f"Población vs Incidencia por municipio — {anio}")
    ax.set_xlabel("Población")
    ax.set_ylabel("Incidencia x 100k hab.")
    ax.xaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"{int(x):,}"))
    plt.tight_layout()
    return fig


def graficar_serie_municipio(pivot, municipio):
    cols = columnas_anio(pivot)
    fila = pivot[pivot["MPIO_CNMBR"] == municipio]
    if fila.empty:
        print(f"Municipio '{municipio}' no encontrado.")
        return None
    serie = fila[cols].T.reset_index()
    serie.columns = ["anio_col", "casos"]
    serie["año"] = serie["anio_col"].str.replace("dengue_", "", regex=False).astype(int)
    serie = serie[["año", "casos"]].sort_values("año")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=serie, x="año", y="casos", marker="o", ax=ax)
    ax.set_title(f"Serie histórica — {municipio}")
    ax.set_xlabel("Año")
    ax.set_ylabel("Casos")
    plt.tight_layout()
    return fig


def graficar_forecast_municipio(
    forecast_df: pd.DataFrame,
    mpio_ccdgo: str,
    nombre_municipio: str = None,
    ruta_salida: str = None,
):
    """
    Grafica la serie histórica + pronóstico de 52 semanas con intervalo de confianza.
    forecast_df debe provenir de modelo.pronosticar_municipio o pronosticar_todos.
    """
    if "mpio_ccdgo" in forecast_df.columns:
        df = forecast_df[forecast_df["mpio_ccdgo"] == mpio_ccdgo].copy()
    else:
        df = forecast_df.copy()

    df = df.sort_values("ds").reset_index(drop=True)
    hist   = df[df["y"].notna()].copy()
    futuro = df[df["y"].isna()].copy()

    col_low  = next((c for c in df.columns if "10.0%" in c), None)
    col_high = next((c for c in df.columns if "90.0%" in c), None)

    fig, ax = plt.subplots(figsize=(14, 5))

    ax.plot(hist["ds"], hist["y"],     color="#2c7bb6", linewidth=1.2, label="Histórico")
    ax.plot(hist["ds"], hist["yhat1"], color="#abd9e9", linewidth=0.8, linestyle="--", alpha=0.7, label="Ajuste modelo")

    ax.plot(futuro["ds"], futuro["yhat1"], color="#d7191c", linewidth=2, label="Pronóstico 52 sem.")

    if col_low and col_high:
        ax.fill_between(
            futuro["ds"], futuro[col_low], futuro[col_high],
            color="#d7191c", alpha=0.15, label="IC 80%"
        )

    ax.axvline(hist["ds"].max(), color="gray", linewidth=1, linestyle=":", alpha=0.6)

    nombre = nombre_municipio or mpio_ccdgo
    ax.set_title(f"Pronóstico semanal de dengue — {nombre}", fontsize=13, pad=12)
    ax.set_xlabel("Semana epidemiológica")
    ax.set_ylabel("Casos semanales")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.legend(fontsize=9)
    ax.grid(axis="y", alpha=0.3)
    plt.tight_layout()

    if ruta_salida:
        ruta = Path(ruta_salida)
        ruta.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta / f"forecast_{mpio_ccdgo}.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    return fig


def graficar_forecast_top(
    forecast_df: pd.DataFrame,
    nombres: dict,
    mpios: list = None,
    n: int = 6,
    ruta_salida: str = None,
):
    """
    Grid de pronósticos para los N municipios indicados (o los primeros N del DataFrame).
    nombres: dict {mpio_ccdgo: MPIO_CNMBR}
    """
    if mpios is None:
        mpios = forecast_df["mpio_ccdgo"].unique()[:n]
    else:
        mpios = mpios[:n]

    cols_grid = 2
    rows_grid = (len(mpios) + 1) // cols_grid
    fig, axes = plt.subplots(rows_grid, cols_grid, figsize=(15, 4 * rows_grid))
    axes = axes.flatten()

    col_low  = next((c for c in forecast_df.columns if "10.0%" in c), None)
    col_high = next((c for c in forecast_df.columns if "90.0%" in c), None)

    for idx, mpio in enumerate(mpios):
        ax = axes[idx]
        df = forecast_df[forecast_df["mpio_ccdgo"] == mpio].sort_values("ds")
        hist   = df[df["y"].notna()]
        futuro = df[df["y"].isna()]

        ax.plot(hist["ds"], hist["y"],     color="#2c7bb6", linewidth=1,   label="Histórico")
        ax.plot(futuro["ds"], futuro["yhat1"], color="#d7191c", linewidth=1.5, label="Pronóstico")

        if col_low and col_high:
            ax.fill_between(futuro["ds"], futuro[col_low], futuro[col_high],
                            color="#d7191c", alpha=0.15)

        ax.axvline(hist["ds"].max(), color="gray", linewidth=0.8, linestyle=":")
        ax.set_title(nombres.get(mpio, mpio), fontsize=10)
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
        ax.xaxis.set_major_locator(mdates.YearLocator())
        ax.grid(axis="y", alpha=0.3)
        ax.tick_params(labelsize=7)

    for idx in range(len(mpios), len(axes)):
        axes[idx].set_visible(False)

    fig.suptitle("Pronóstico semanal de dengue — top municipios", fontsize=13, y=1.01)
    plt.tight_layout()

    if ruta_salida:
        ruta = Path(ruta_salida)
        ruta.mkdir(parents=True, exist_ok=True)
        fig.savefig(ruta / "forecast_top_municipios.png", dpi=150, bbox_inches="tight")
        plt.close(fig)

    return fig
