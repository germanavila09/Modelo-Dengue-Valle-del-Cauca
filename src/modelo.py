"""
Modelado predictivo de dengue con NeuralProphet + GPU (RTX 4060 Ti).
Entrena series semanales por municipio y proyecta 52 semanas hacia adelante.
"""

from datetime import date, timedelta
import numpy as np

import pandas as pd
from pathlib import Path
from sqlalchemy import text


def _get_neuralprophet():
    """Lazy import — evita cargar PyTorch/NeuralProphet al importar el módulo."""
    from neuralprophet import NeuralProphet, set_log_level  # noqa: PLC0415
    set_log_level("ERROR")
    return NeuralProphet


def _semana_a_fecha(anio: int, semana: int) -> pd.Timestamp:
    """Semana epidemiológica INS/MMWR → domingo inicial de la semana."""
    try:
        anio = int(anio)
        semana = int(semana)
        jan4 = date(anio, 1, 4)
        week_one = jan4 - timedelta(days=(jan4.weekday() + 1) % 7)
        next_jan4 = date(anio + 1, 1, 4)
        next_week_one = next_jan4 - timedelta(days=(next_jan4.weekday() + 1) % 7)
        weeks_in_year = (next_week_one - week_one).days // 7
        if not 1 <= semana <= weeks_in_year:
            return pd.NaT
        return pd.Timestamp(week_one + timedelta(weeks=semana - 1))
    except (TypeError, ValueError, OverflowError):
        return pd.NaT


def cargar_serie_semanal(engine, mpio_ccdgo: str = None) -> pd.DataFrame:
    """
    Carga series semanales anonimizadas por municipio.
    Retorna columnas: mpio_ccdgo, ds (lunes de cada semana ISO), y (casos)
    """
    filtro = "AND mpio_ccdgo = :mpio_ccdgo" if mpio_ccdgo else ""
    params = {"mpio_ccdgo": mpio_ccdgo} if mpio_ccdgo else None

    query = text(f"""
    SELECT
        mpio_ccdgo,
        anio::int   AS anio,
        semana::int AS semana,
        SUM(casos)  AS casos
    FROM public.dengue_semana_municipio
    WHERE anio IS NOT NULL AND semana IS NOT NULL
    {filtro}
    GROUP BY mpio_ccdgo, anio, semana
    ORDER BY mpio_ccdgo, anio, semana
    """)

    df = pd.read_sql(query, engine, params=params)
    if df.empty:
        raise ValueError("No hay registros semanales para el municipio solicitado.")
    df["ds"] = df.apply(lambda r: _semana_a_fecha(r["anio"], r["semana"]), axis=1)
    if df["ds"].isna().any():
        raise ValueError("Hay semanas incompatibles con el calendario ISO; validar el calendario de la fuente.")
    df["y"] = df["casos"].astype(float)
    # Colapsa los dos códigos de evento y completa semanas sin casos con cero.
    df = (
        df.groupby(["mpio_ccdgo", "ds"], as_index=False)["y"]
        .sum()
        .sort_values(["mpio_ccdgo", "ds"])
        .reset_index(drop=True)
    )
    completas = []
    for codigo, grupo in df.groupby("mpio_ccdgo", sort=True):
        fechas = pd.date_range(grupo["ds"].min(), grupo["ds"].max(), freq="W-SUN")
        serie = grupo.set_index("ds")["y"].reindex(fechas, fill_value=0.0)
        completas.append(
            pd.DataFrame({"mpio_ccdgo": codigo, "ds": fechas, "y": serie.to_numpy()})
        )
    return pd.concat(completas, ignore_index=True)[["mpio_ccdgo", "ds", "y"]]


def _construir_modelo(accelerator: str = "gpu", periodos: int = 52):
    NeuralProphet = _get_neuralprophet()
    return NeuralProphet(
        n_forecasts=periodos,
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
    if not isinstance(periodos, int) or isinstance(periodos, bool) or not 1 <= periodos <= 52:
        raise ValueError("El horizonte debe ser un entero entre 1 y 52 semanas.")
    serie = serie[["ds", "y"]].copy().sort_values("ds").reset_index(drop=True)
    serie["ds"] = pd.to_datetime(serie["ds"], errors="coerce")
    serie["y"] = pd.to_numeric(serie["y"], errors="coerce")
    if serie["ds"].isna().any() or serie["ds"].duplicated().any():
        raise ValueError("Las fechas semanales deben ser válidas y únicas.")
    if not np.isfinite(serie["y"]).all() or (serie["y"] < 0).any():
        raise ValueError("Los casos deben ser observaciones no negativas; no se imputan faltantes.")
    if len(serie) < 52 + periodos + 1:
        raise ValueError("Historia insuficiente para 52 rezagos y el horizonte solicitado.")
    if not serie["ds"].diff().dropna().eq(pd.Timedelta(days=7)).all():
        raise ValueError("Hay semanas faltantes; distinguir ausencia de reporte de cero casos antes de entrenar.")
    model = _construir_modelo(accelerator, periodos=periodos)
    frequency = "W-" + ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"][serie["ds"].iloc[0].dayofweek]
    model.fit(serie, freq=frequency)
    future = model.make_future_dataframe(serie, periods=periodos)
    raw = model.predict(future)
    future_rows = raw[raw["ds"] > serie["ds"].max()].sort_values("ds")
    expected_dates = pd.date_range(serie["ds"].max() + pd.Timedelta(days=7), periods=periodos, freq=frequency)
    if len(future_rows) != periodos or list(future_rows["ds"]) != list(expected_dates):
        raise ValueError("El modelo no produjo todas las semanas futuras solicitadas.")
    # NeuralProphet stores each lead in yhat{lead}; expose the last-origin forecast
    # in the stable yhat1 interface consumed by plots and CSV export.
    predictions = []
    for lead, (_, row) in enumerate(future_rows.iterrows(), 1):
        item = {"ds": row["ds"], "y": float("nan")}
        for suffix in ("", " 10.0%", " 90.0%"):
            value = row.get(f"yhat{lead}{suffix}")
            if value is None or not np.isfinite(value):
                raise ValueError(f"Pronóstico incompleto en horizonte {lead} ({suffix or 'central'}).")
            item[f"yhat1{suffix}"] = max(0.0, float(value))
        if not item["yhat1 10.0%"] <= item["yhat1"] <= item["yhat1 90.0%"]:
            raise ValueError("Cuantiles cruzados: el pronóstico requiere validación.")
        predictions.append(item)
    return pd.concat([serie, pd.DataFrame(predictions)], ignore_index=True)


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
