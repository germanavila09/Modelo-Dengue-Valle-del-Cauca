from pathlib import Path

import folium


def generar_mapa_html(gdf, ruta_salida, columna="indice_oportunidad_turistica"):
    ruta = Path(ruta_salida)
    ruta.mkdir(parents=True, exist_ok=True)
    mapa = folium.Map(location=[3.45, -76.53], zoom_start=8, tiles="CartoDB positron")

    if hasattr(gdf, "geometry") and not gdf.empty:
        folium.Choropleth(
            geo_data=gdf.to_json(),
            data=gdf,
            columns=["municipio", columna],
            key_on="feature.properties.municipio",
            fill_color="YlGnBu",
            fill_opacity=0.75,
            line_opacity=0.25,
            legend_name="Indice de oportunidad turistica",
        ).add_to(mapa)

        folium.GeoJson(
            gdf,
            name="Municipios",
            tooltip=folium.GeoJsonTooltip(
                fields=[field for field in ["municipio", columna] if field in gdf.columns],
                aliases=["Municipio", "Indice"],
            ),
        ).add_to(mapa)

    salida = ruta / "mapa_actual.html"
    mapa.save(salida)
    return salida
