"""Tests for src/db.py module."""

import pytest
from unittest.mock import Mock, patch


class TestDBConfig:
    """Test database configuration."""

    def test_db_config_from_env(self, mock_env_vars):
        """Test that DB_CONFIG is loaded from environment variables."""
        from src.config import DB_CONFIG
        
        assert DB_CONFIG["host"] == "localhost"
        assert DB_CONFIG["port"] == 5432
        assert DB_CONFIG["database"] == "test_dengue"
        assert DB_CONFIG["user"] == "postgres"


class TestCrearEngine:
    """Test database engine creation."""

    @patch("src.db.create_engine")
    def test_crear_engine_returns_engine(self, mock_create_engine, mock_env_vars):
        """Test that crear_engine returns a valid SQLAlchemy engine."""
        from src.db import crear_engine
        
        mock_engine = Mock()
        mock_create_engine.return_value = mock_engine
        
        engine = crear_engine()
        
        assert engine is mock_engine
        mock_create_engine.assert_called_once()

    def test_crear_engine_url_format(self, mock_env_vars):
        """Test that engine URL is properly formatted."""
        from src.db import crear_engine
        from sqlalchemy.engine import URL
        
        with patch("src.db.create_engine") as mock_create:
            crear_engine()
            
            # Get the URL object passed to create_engine
            call_args = mock_create.call_args
            url = call_args[0][0]
            
            assert isinstance(url, URL)
            assert url.drivername == "postgresql+psycopg2"


class TestCargarDatos:
    """Test data loading functions."""

    @patch("src.db.gpd.read_postgis")
    def test_cargar_datos_returns_geodataframe(self, mock_read_postgis, mock_env_vars):
        """Test that cargar_datos returns a GeoDataFrame."""
        from src.db import cargar_datos
        import geopandas as gpd
        from shapely.geometry import Point

        mock_gdf = gpd.GeoDataFrame(
            {
                "MPIO_CCDGO": ["76001"],
                "MPIO_CNMBR": ["Cali"],
                "año": [2023],
                "población": [2250000],
                "conteo_dengue": [1250.0],
                "incidencia_dengue": [55.5],
                "geom": [Point(0, 0)],
            },
            geometry="geom",
        )
        mock_read_postgis.return_value = mock_gdf

        result = cargar_datos(Mock())

        assert isinstance(result, gpd.GeoDataFrame)
        mock_read_postgis.assert_called_once()

    def test_quote_identifier_rejects_invalid_names(self):
        """Test that SQL identifiers from config reject unsafe characters."""
        from src.db import _quote_identifier

        with pytest.raises(ValueError):
            _quote_identifier("public; DROP TABLE valle_mun")


class TestCargarPuntosCalor:
    """Test heat point data loading."""

    @patch("src.db.pd.read_sql")
    def test_cargar_puntos_calor_structure(self, mock_read_sql, mock_env_vars):
        """Test that cargar_puntos_calor returns expected columns."""
        from src.db import cargar_puntos_calor
        
        # Mock result with expected columns
        mock_df = {
            "mpio_ccdgo": ["76001", "76109"],
            "latitud": [3.4516, 3.8801],
            "longitud": [-76.5320, -77.0311],
        }
        mock_read_sql.return_value = mock_df
        
        mock_engine = Mock()
        result = cargar_puntos_calor(mock_engine)
        
        mock_read_sql.assert_called_once()
