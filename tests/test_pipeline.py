"""Tests for src/pipeline.py module."""

from contextlib import ExitStack
from unittest.mock import Mock, patch

import pandas as pd


def _mock_fig():
    fig = Mock()
    fig.savefig = Mock()
    fig.clf = Mock()
    return fig


def _mock_pipeline_dependencies(sample_gdf, sample_pivot_df, tmp_path):
    priorizacion = sample_pivot_df.copy()
    priorizacion["total"] = priorizacion.filter(like="dengue_").sum(axis=1)
    priorizacion = priorizacion.sort_values("total", ascending=False).reset_index(drop=True)
    priorizacion["ranking"] = priorizacion.index + 1

    patches = {
        "crear_engine": patch("src.pipeline.crear_engine", return_value=Mock()),
        "cargar_datos": patch("src.pipeline.cargar_datos", return_value=sample_gdf),
        "limpiar_datos": patch("src.pipeline.limpiar_datos", return_value=sample_gdf),
        "construir_pivot": patch("src.pipeline.construir_pivot", return_value=sample_pivot_df),
        "calcular_priorizacion": patch("src.pipeline.calcular_priorizacion", return_value=priorizacion),
        "cargar_puntos_calor": patch(
            "src.pipeline.cargar_puntos_calor",
            return_value=pd.DataFrame(
                {"anio": ["2023"], "mpio_ccdgo": ["76001"], "lat": [3.45], "lng": [-76.53]}
            ),
        ),
        "generar_mapa_html": patch("src.pipeline.generar_mapa_html", return_value=tmp_path / "mapa.html"),
    }

    graph_names = [
        "graficar_casos_por_anio",
        "graficar_incidencia_por_anio",
        "graficar_top_municipios",
        "graficar_top_municipios_incidencia",
        "graficar_heatmap",
        "graficar_scatter_poblacion_incidencia",
        "graficar_serie_municipio",
    ]
    patches.update({name: patch(f"src.pipeline.{name}", return_value=_mock_fig()) for name in graph_names})
    return patches


def _enter_all(patches):
    stack = ExitStack()
    mocks = {name: stack.enter_context(patch_obj) for name, patch_obj in patches.items()}
    return stack, mocks


class TestPipelineExecution:
    """Test pipeline execution."""

    def test_ejecutar_creates_output_dirs(self, sample_gdf, sample_pivot_df, tmp_path, mock_env_vars):
        """Test that ejecutar creates output directories."""
        from src.pipeline import ejecutar

        patches = _mock_pipeline_dependencies(sample_gdf, sample_pivot_df, tmp_path)
        stack, _ = _enter_all(patches)
        with stack:
            ejecutar(ruta_salida=str(tmp_path))

        assert (tmp_path / "graficas").exists()

    def test_ejecutar_with_custom_year(self, sample_gdf, sample_pivot_df, tmp_path, mock_env_vars):
        """Test that ejecutar respects custom year parameter."""
        from src.pipeline import ejecutar

        patches = _mock_pipeline_dependencies(sample_gdf, sample_pivot_df, tmp_path)
        stack, mocks = _enter_all(patches)
        with stack:
            ejecutar(anio=2020, ruta_salida=str(tmp_path))

        mocks["crear_engine"].assert_called_once()
        assert mocks["graficar_top_municipios"].call_args.args[1] == 2020
        assert mocks["graficar_top_municipios_incidencia"].call_args.args[1] == 2020
        assert mocks["graficar_scatter_poblacion_incidencia"].call_args.args[1] == 2020


class TestForecastExecution:
    """Test forecast execution."""

    @patch("src.pipeline.crear_engine")
    @patch("src.pipeline.cargar_datos")
    @patch("src.pipeline.limpiar_datos")
    @patch("src.pipeline.pronosticar_municipio")
    @patch("src.pipeline.graficar_forecast_municipio")
    def test_ejecutar_forecast_single_municipality(
        self,
        mock_grafica,
        mock_pronosticar,
        mock_limpiar,
        mock_cargar,
        mock_engine_creator,
        sample_gdf,
        tmp_path,
        mock_env_vars,
    ):
        """Test forecast for single municipality."""
        from src.pipeline import ejecutar_forecast

        mock_engine = Mock()
        mock_engine_creator.return_value = mock_engine
        mock_cargar.return_value = sample_gdf
        mock_limpiar.return_value = sample_gdf

        mock_forecast = pd.DataFrame(
            {
                "ds": pd.date_range("2023-01-01", periods=52, freq="W"),
                "y": [None] * 52,
                "yhat1": [100] * 52,
            }
        )
        mock_pronosticar.return_value = mock_forecast
        mock_grafica.return_value = _mock_fig()

        result = ejecutar_forecast(municipio="CALI", todos=False, ruta_salida=str(tmp_path))

        assert isinstance(result, pd.DataFrame)
        mock_pronosticar.assert_called_once_with(mock_engine, "76001", periodos=52, accelerator="gpu")


class TestPipelineIntegration:
    """Integration tests for pipeline."""

    def test_pipeline_imports_all_modules(self):
        """Test that all required modules can be imported."""
        from src import config, db, mapa, modelo, pipeline, transform, viz

        assert all([config, db, mapa, modelo, pipeline, transform, viz])

    @patch("src.pipeline.Path.mkdir")
    def test_output_directories_created(self, mock_mkdir, sample_gdf, sample_pivot_df, tmp_path, mock_env_vars):
        """Test that output directories are properly created."""
        from src.pipeline import ejecutar

        patches = _mock_pipeline_dependencies(sample_gdf, sample_pivot_df, tmp_path)
        stack, _ = _enter_all(patches)
        with stack:
            ejecutar(ruta_salida=str(tmp_path))

        mock_mkdir.assert_called()
