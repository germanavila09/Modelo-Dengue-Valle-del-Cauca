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
        query = str(mock_read_sql.call_args.args[0])
        assert "dengue_semana_municipio" in query
        assert "public.dengue_m" not in query

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


def test_semana_53_uses_epidemiological_calendar():
    """INS reports week 53 in 2025 even though ISO-8601 does not."""
    from src.modelo import _semana_a_fecha

    assert _semana_a_fecha(2025, 53) == pd.Timestamp("2025-12-28")
    assert _semana_a_fecha(2026, 1) == pd.Timestamp("2026-01-04")


@patch("src.modelo.pd.read_sql")
def test_cargar_serie_semanal_fills_weeks_without_cases(mock_read_sql):
    """An event-level source makes absent internal weeks explicit zero counts."""
    from src.modelo import cargar_serie_semanal

    mock_read_sql.return_value = pd.DataFrame(
        {
            "mpio_ccdgo": ["76001", "76001"],
            "anio": [2025, 2025],
            "semana": [1, 3],
            "casos": [4, 7],
        }
    )

    result = cargar_serie_semanal(Mock(), "76001")

    assert result["y"].tolist() == [4.0, 0.0, 7.0]
