"""
Modelado predictivo de dengue con NeuralProphet + GPU (RTX 4060 Ti).
Entrena series semanales por municipio y proyecta 52 semanas hacia adelante.
"""

import warnings
warnings.filterwarnings("ignore")

import pandas as pd
from pathlib import Path

from neuralprophet import NeuralProphet, set_log_level
set_log_level("ERROR")


def _semana_a_fecha(anio: int, semana: int) -> pd.Timestamp:
    """Semana epidemiológica (ISO) + año → fecha del lunes de esa semana."""
    try:
        return pd.to_datetime(f"{int(anio)}-W{int(semana):02d}-1", format="%G-W%V-%u")
    except Exception:
        return pd.NaT


def cargar_serie_semanal(engine, mpio_ccdgo: str = None) -> pd.DataFrame:
    """
    Agrega casos individuales de dengue_m en series semanales por municipio.
    Retorna columnas: mpio_ccdgo, ds (lunes de cada semana ISO), y (casos)
    """
    filtro = f"AND mpio_ccdgo = '{mpio_ccdgo}'" if mpio_ccdgo else ""

    query = f"""
    SELECT
        mpio_ccdgo,
        año::int    AS anio,
        semana::int AS semana,
        COUNT(*)    AS casos
    FROM public.dengue_m
    WHERE año IS NOT NULL AND semana IS NOT NULL
    {filtro}
    GROUP BY mpio_ccdgo, año, semana
    ORDER BY mpio_ccdgo, año, semana
    """

    df = pd.read_sql(query, engine)
    df["ds"] = df.apply(lambda r: _semana_a_fecha(r["anio"], r["semana"]), axis=1)
    df = df.dropna(subset=["ds"])
    df["y"] = df["casos"].astype(float)
    # colapsa posibles duplicados por fecha (semana 53 puede coincidir con semana 1 del año siguiente)
    df = (
        df.groupby(["mpio_ccdgo", "ds"], as_index=False)["y"]
        .sum()
        .sort_values(["mpio_ccdgo", "ds"])
        .reset_index(drop=True)
    )
    return df[["mpio_ccdgo", "ds", "y"]]


def _construir_modelo(accelerator: str = "gpu") -> NeuralProphet:
    return NeuralProphet(
        n_forecasts=1,
        n_lags=52,
        yearly_seasonality=True,
        weekly_seasonality=False,
        daily_seasonality=False,
        epochs=150,
        batch_size=64,
        learning_rate=5e-4,
        quantiles=[0.10, 0.90],
        accelerator=accelerator,
    )


def entrenar_pronosticar(
    serie: pd.DataFrame,
    periodos: int = 52,
    accelerator: str = "gpu",
) -> pd.DataFrame:
    """
    Recibe DataFrame con columnas [ds, y], entrena NeuralProphet y devuelve forecast.
    Columnas en el resultado: ds, y, yhat1, yhat1 10.0%, yhat1 90.0%
    """
    serie = (
        serie[["ds", "y"]]
        .sort_values("ds")
        .dropna(subset=["y"])
        .reset_index(drop=True)
    )
    model = _construir_modelo(accelerator)
    model.fit(serie, freq="W")
    future = model.make_future_dataframe(serie, periods=periodos)
    return model.predict(future)


def pronosticar_municipio(
    engine,
    mpio_ccdgo: str,
    periodos: int = 52,
    accelerator: str = "gpu",
) -> pd.DataFrame:
    """Entrena y pronostica para un municipio. Retorna DataFrame con forecast."""
    df = cargar_serie_semanal(engine, mpio_ccdgo)
    forecast = entrenar_pronosticar(df[["ds", "y"]], periodos, accelerator)
    forecast["mpio_ccdgo"] = mpio_ccdgo
    return forecast


def pronosticar_todos(
    engine,
    periodos: int = 52,
    accelerator: str = "gpu",
    ruta_salida: str = None,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Entrena y pronostica para los 42 municipios del Valle del Cauca.
    Si se indica ruta_salida, guarda pronosticos_municipios.csv con las filas futuras.
    """
    df_all = cargar_serie_semanal(engine)
    municipios = sorted(df_all["mpio_ccdgo"].unique())

    resultados = []
    for i, mpio in enumerate(municipios, 1):
        if verbose:
            print(f"[{i:2d}/{len(municipios)}] {mpio} ... ", end="", flush=True)
        serie = df_all[df_all["mpio_ccdgo"] == mpio][["ds", "y"]].copy()
        try:
            forecast = entrenar_pronosticar(serie, periodos, accelerator)
            forecast["mpio_ccdgo"] = mpio
            resultados.append(forecast)
            if verbose:
                print("OK")
        except Exception as exc:
            if verbose:
                print(f"ERROR - {exc}")

    if not resultados:
        return pd.DataFrame()

    df_result = pd.concat(resultados, ignore_index=True)

    if ruta_salida:
        ruta = Path(ruta_salida)
        ruta.mkdir(parents=True, exist_ok=True)
        archivo = ruta / "pronosticos_municipios.csv"
        df_result[df_result["y"].isna()].to_csv(archivo, index=False)
        if verbose:
            print(f"\nForecast guardado en: {archivo}")

    return df_result
