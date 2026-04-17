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
