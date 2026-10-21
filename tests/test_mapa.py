"""Privacy contract tests for map heat data."""

import pandas as pd

from src.mapa import _preparar_heat_data


def test_heat_data_contains_only_aggregate_cells_and_weights():
    cells = pd.DataFrame(
        {
            "anio": ["2024", "2024"],
            "mpio_ccdgo": ["76001", "76520"],
            "lat": [3.455, 3.535],
            "lng": [-76.535, -76.305],
            "peso": [15, 8],
        }
    )

    result = _preparar_heat_data(cells)

    assert result["2024_con_cali"] == [[3.455, -76.535, 15.0], [3.535, -76.305, 8.0]]
    assert result["2024_sin_cali"] == [[3.535, -76.305, 8.0]]
