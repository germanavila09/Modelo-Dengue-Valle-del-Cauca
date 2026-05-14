import pandas as pd


def limpiar_datos(gdf):
    df = gdf.copy()
    if "municipio" in df.columns:
        df["municipio"] = df["municipio"].astype(str).str.upper().str.strip()
    if "anio" in df.columns:
        df["anio"] = pd.to_numeric(df["anio"], errors="coerce").astype("Int64")

    numericas = [
        "visitantes",
        "atractivos",
        "ocupacion_hotelera",
        "gasto_estimado",
        "indice_seguridad",
        "tiempo_acceso_min",
    ]
    for col in numericas:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
    return df


def construir_pivot(df, valor="visitantes"):
    if not {"municipio", "anio", valor}.issubset(df.columns):
        return pd.DataFrame()
    return df.pivot_table(
        index="municipio",
        columns="anio",
        values=valor,
        aggfunc="sum",
        fill_value=0,
    )


def calcular_indice_oportunidad(df):
    data = df.copy()
    defaults = {
        "visitantes": 0,
        "atractivos": 0,
        "ocupacion_hotelera": 0,
        "gasto_estimado": 0,
        "indice_seguridad": 0,
        "tiempo_acceso_min": 0,
    }
    for col, default in defaults.items():
        if col not in data.columns:
            data[col] = default

    def norm(col):
        serie = data[col].astype(float)
        rango = serie.max() - serie.min()
        if rango == 0:
            return serie * 0
        return (serie - serie.min()) / rango

    accesibilidad = 1 - norm("tiempo_acceso_min")
    data["indice_oportunidad_turistica"] = (
        norm("visitantes") * 0.25
        + norm("atractivos") * 0.20
        + norm("ocupacion_hotelera") * 0.15
        + norm("gasto_estimado") * 0.15
        + norm("indice_seguridad") * 0.15
        + accesibilidad * 0.10
    ).round(4)
    return data


def calcular_priorizacion(df):
    data = calcular_indice_oportunidad(df)
    if "municipio" not in data.columns:
        return pd.DataFrame()
    columnas = [
        "municipio",
        "visitantes",
        "atractivos",
        "ocupacion_hotelera",
        "gasto_estimado",
        "indice_oportunidad_turistica",
    ]
    columnas = [col for col in columnas if col in data.columns]
    return (
        data.groupby("municipio", as_index=False)[columnas[1:]]
        .mean(numeric_only=True)
        .sort_values("indice_oportunidad_turistica", ascending=False)
    )
