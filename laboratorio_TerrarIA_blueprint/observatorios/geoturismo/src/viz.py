from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns


def configurar_estilo():
    sns.set_theme(style="whitegrid")


def graficar_top_destinos(priorizacion, ruta_salida):
    configurar_estilo()
    ruta = Path(ruta_salida)
    ruta.mkdir(parents=True, exist_ok=True)
    top = priorizacion.head(10).sort_values("indice_oportunidad_turistica")

    fig, ax = plt.subplots(figsize=(10, 6))
    ax.barh(top["municipio"], top["indice_oportunidad_turistica"], color="#0f766e")
    ax.set_title("Top destinos por oportunidad turistica")
    ax.set_xlabel("Indice de oportunidad")
    ax.set_ylabel("")
    fig.tight_layout()
    fig.savefig(ruta / "top_destinos_oportunidad.png", dpi=150)
    plt.close(fig)


def graficar_visitantes_por_anio(df, ruta_salida):
    configurar_estilo()
    ruta = Path(ruta_salida)
    ruta.mkdir(parents=True, exist_ok=True)
    serie = df.groupby("anio")["visitantes"].sum().reset_index()

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(serie["anio"], serie["visitantes"], marker="o", color="#2563eb")
    ax.set_title("Visitantes por anio")
    ax.set_xlabel("Anio")
    ax.set_ylabel("Visitantes")
    fig.tight_layout()
    fig.savefig(ruta / "visitantes_por_anio.png", dpi=150)
    plt.close(fig)
