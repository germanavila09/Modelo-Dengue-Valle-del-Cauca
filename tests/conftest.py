"""
Pytest configuration and shared fixtures for observatorio_geosalud tests.
"""

import pytest
import os
from pathlib import Path
from dotenv import load_dotenv

# Load test environment
test_dir = Path(__file__).parent
env_file = test_dir / ".env.test"
if env_file.exists():
    load_dotenv(env_file)


@pytest.fixture
def test_data_dir():
    """Return path to test data directory."""
    return test_dir / "data"


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    test_env = {
        "DB_HOST": "localhost",
        "DB_PORT": "5432",
        "DB_NAME": "test_dengue",
        "DB_USER": "postgres",
        "DB_PASSWORD": "test",
        "DB_SCHEMA": "public",
        "DB_TABLE": "valle_mun",
        "ANIO_DEFAULT": "2024",
        "MUNICIPIO_DEFAULT": "CALI",
        "RUTA_SALIDA": "outputs",
    }
    for key, value in test_env.items():
        monkeypatch.setenv(key, value)
    return test_env


@pytest.fixture
def mock_db_config(mock_env_vars):
    """Mock database configuration."""
    return {
        "host": "localhost",
        "port": 5432,
        "database": "test_dengue",
        "user": "postgres",
        "password": "test",
    }


@pytest.fixture
def sample_gdf():
    """Sample GeoDataFrame for testing."""
    import geopandas as gpd
    import pandas as pd
    from shapely.geometry import MultiPolygon, Polygon

    # Create sample data
    data = {
        "MPIO_CCDGO": ["76001", "76109", "76520"],
        "MPIO_CNMBR": ["Cali", "Buenaventura", "Palmira"],
        "año": [2023, 2023, 2023],
        "población": [2250000, 425000, 322000],
        "conteo_dengue": [1250, 580, 340],
        "incidencia_dengue": [55.5, 136.4, 105.6],
    }

    gdf = gpd.GeoDataFrame(data)
    
    # Add simple polygons
    polygons = [
        Polygon([(0, 0), (1, 0), (1, 1), (0, 1)]),
        Polygon([(1, 0), (2, 0), (2, 1), (1, 1)]),
        Polygon([(0, 1), (1, 1), (1, 2), (0, 2)]),
    ]
    gdf["geometry"] = polygons
    gdf.set_crs("EPSG:3857", inplace=True)

    return gdf


@pytest.fixture
def sample_pivot_df():
    """Sample pivot DataFrame for testing."""
    import pandas as pd

    return pd.DataFrame({
        "MPIO_CCDGO": ["76001", "76109", "76520"],
        "MPIO_CNMBR": ["Cali", "Buenaventura", "Palmira"],
        "dengue_2019": [1200, 450, 280],
        "dengue_2020": [950, 380, 220],
        "dengue_2021": [1450, 520, 350],
        "dengue_2022": [1100, 410, 310],
        "dengue_2023": [1250, 580, 340],
    })
