import pandas as pd

from src.transform import calcular_indice_oportunidad, construir_pivot, limpiar_datos


def test_limpieza_normaliza_municipio():
    df = pd.DataFrame({"municipio": [" cali "], "anio": ["2025"], "visitantes": ["10"]})
    limpio = limpiar_datos(df)
    assert limpio.loc[0, "municipio"] == "CALI"
    assert limpio.loc[0, "visitantes"] == 10


def test_pivot_visitantes():
    df = pd.DataFrame({"municipio": ["CALI"], "anio": [2025], "visitantes": [100]})
    pivot = construir_pivot(df)
    assert pivot.loc["CALI", 2025] == 100


def test_indice_oportunidad_existe():
    df = pd.DataFrame({"municipio": ["CALI"], "visitantes": [100], "atractivos": [5]})
    result = calcular_indice_oportunidad(df)
    assert "indice_oportunidad_turistica" in result.columns
