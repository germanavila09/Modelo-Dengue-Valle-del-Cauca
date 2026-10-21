"""Contract tests between data normalization and plotting."""

import matplotlib.pyplot as plt

from src.transform import limpiar_datos
from src.viz import (
    graficar_casos_por_anio,
    graficar_incidencia_por_anio,
    graficar_scatter_poblacion_incidencia,
    graficar_top_municipios,
    graficar_top_municipios_incidencia,
)


def test_aggregate_plots_accept_normalized_database_columns(sample_gdf):
    """All aggregate plots use the canonical año/población column contract."""
    normalized = limpiar_datos(
        sample_gdf.rename(columns={"año": "anio", "población": "poblacion"})
    )

    figures = [
        graficar_casos_por_anio(normalized),
        graficar_incidencia_por_anio(normalized),
        graficar_top_municipios(normalized, 2023),
        graficar_top_municipios_incidencia(normalized, 2023),
        graficar_scatter_poblacion_incidencia(normalized, 2023),
    ]

    assert all(fig.axes for fig in figures)
    for fig in figures:
        plt.close(fig)
