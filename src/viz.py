import matplotlib.pyplot as plt
import seaborn as sns

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
