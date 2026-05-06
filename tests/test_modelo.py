"""Tests for src/modelo.py module."""

from unittest.mock import Mock, patch

import pandas as pd


class TestCargarSerieSemanal:
    """Test weekly time-series loading."""

    @patch("src.modelo.pd.read_sql")
    def test_cargar_serie_semanal_uses_query_params(self, mock_read_sql):
        """Municipality filtering should use SQL parameters instead of interpolation."""
        from src.modelo import cargar_serie_semanal

        mock_read_sql.return_value = pd.DataFrame(
            {
                "mpio_ccdgo": ["76001"],
                "anio": [2023],
                "semana": [1],
                "casos": [10],
            }
        )

        result = cargar_serie_semanal(Mock(), mpio_ccdgo="76001")

        assert list(result.columns) == ["mpio_ccdgo", "ds", "y"]
        assert mock_read_sql.call_args.kwargs["params"] == {"mpio_ccdgo": "76001"}
        assert ":mpio_ccdgo" in str(mock_read_sql.call_args.args[0])

    @patch("src.modelo.pd.read_sql")
    def test_cargar_serie_semanal_without_filter_has_no_params(self, mock_read_sql):
        """The all-municipality query should not pass an unused parameter dict."""
        from src.modelo import cargar_serie_semanal

        mock_read_sql.return_value = pd.DataFrame(
            {
                "mpio_ccdgo": ["76001"],
                "anio": [2023],
                "semana": [1],
                "casos": [10],
            }
        )

        cargar_serie_semanal(Mock())

        assert mock_read_sql.call_args.kwargs["params"] is None
