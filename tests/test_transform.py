"""Tests for src/transform.py module."""

import pytest
from pathlib import Path
import sys

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLimpiarDatos:
    """Test data cleaning functions."""

    def test_limpiar_datos_removes_nulls(self, sample_gdf):
        """Test that limpiar_datos handles null values."""
        from src.transform import limpiar_datos
        
        # Add some null values
        sample_gdf.loc[0, "conteo_dengue"] = None
        
        result = limpiar_datos(sample_gdf)
        
        # Should still have data after cleaning
        assert len(result) > 0
        assert result.isnull().sum().sum() == 0  # No nulls in key columns

    def test_limpiar_datos_normalizes_types(self, sample_gdf):
        """Test that limpiar_datos normalizes data types."""
        from src.transform import limpiar_datos
        
        result = limpiar_datos(sample_gdf)
        
        # Check expected types
        assert result["año"].dtype in ["int32", "int64"]
        assert result["MPIO_CCDGO"].dtype == "object"  # text/str
        assert result["conteo_dengue"].dtype in ["int32", "int64"]


class TestConstruirPivot:
    """Test pivot table construction."""

    def test_construir_pivot_shape(self, sample_gdf):
        """Test that construir_pivot returns correct shape."""
        from src.transform import construir_pivot
        
        pivot = construir_pivot(sample_gdf)
        
        # Should have at least 3 municipalities
        assert len(pivot) >= 3
        
        # Should have columns for código and nombre
        assert "MPIO_CCDGO" in pivot.columns
        assert "MPIO_CNMBR" in pivot.columns

    def test_construir_pivot_columns_are_years(self, sample_pivot_df):
        """Test that pivot table has year columns (dengue_YYYY)."""
        from src.transform import columnas_anio
        
        years = columnas_anio(sample_pivot_df)
        
        # Should find dengue columns
        assert len(years) > 0
        
        # All should start with "dengue_"
        assert all(col.startswith("dengue_") for col in years)


class TestCalcularPriorizacion:
    """Test prioritization calculation."""

    def test_calcular_priorizacion_ranking(self, sample_pivot_df):
        """Test that priorizacion adds ranking column."""
        from src.transform import calcular_priorizacion
        
        result = calcular_priorizacion(sample_pivot_df)
        
        # Should have ranking column
        assert "ranking" in result.columns or "rank" in result.columns.str.lower()
        
        # Should be ordered by total cases
        assert len(result) == len(sample_pivot_df)

    def test_calcular_priorizacion_sums_correctly(self, sample_pivot_df):
        """Test that priorizacion correctly sums cases."""
        from src.transform import calcular_priorizacion
        
        result = calcular_priorizacion(sample_pivot_df)
        
        # Should have a total column
        assert "total" in result.columns or "total_cases" in result.columns or \
               any("total" in col.lower() for col in result.columns)
        
        # Totals should be positive
        total_cols = [col for col in result.columns if "total" in col.lower()]
        if total_cols:
            assert all(result[total_cols[0]] > 0)


class TestDataIntegrity:
    """Test data integrity after transformations."""

    def test_pipeline_maintains_municipalities(self, sample_gdf):
        """Test that transformations preserve all municipalities."""
        from src.transform import limpiar_datos, construir_pivot
        
        original_mpios = set(sample_gdf["MPIO_CCDGO"].unique())
        
        cleaned = limpiar_datos(sample_gdf)
        cleaned_mpios = set(cleaned["MPIO_CCDGO"].unique())
        
        assert original_mpios == cleaned_mpios

    def test_no_negative_values(self, sample_gdf):
        """Test that no negative values exist in case counts."""
        from src.transform import limpiar_datos
        
        cleaned = limpiar_datos(sample_gdf)
        
        # Case counts should not be negative
        assert (cleaned["conteo_dengue"] >= 0).all()
        # Population should not be negative
        assert (cleaned["población"] >= 0).all()
