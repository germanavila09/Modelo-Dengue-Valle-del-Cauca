import json
from pathlib import Path


def _filtrar_capa_mapa(gdf, anio, incluir_cali=True):
    gdf_filtrado = gdf[gdf["año"] == anio].copy()
    if not incluir_cali:
        gdf_filtrado = gdf_filtrado[gdf_filtrado["MPIO_CNMBR"] != "CALI"]
    return gdf_filtrado


def _preparar_para_folium(gdf):
    gdf_map = gdf.copy()
    if gdf_map.crs is not None:
        try:
            if gdf_map.crs.to_epsg() != 4326:
                gdf_map = gdf_map.to_crs(4326)
        except Exception:
            pass
    return gdf_map


def _corregir_geometrias(gdf):
    gdf_fix = gdf.copy()
    gdf_fix["geom"] = gdf_fix.geometry.buffer(0)
    return gdf_fix.set_geometry("geom")


def _preparar_dataset_mapa(gdf, anios):
    datasets = {}
    for anio in anios:
        for incluir_cali in [True, False]:
            clave = f"{anio}_{'con_cali' if incluir_cali else 'sin_cali'}"
            gdf_tmp = _filtrar_capa_mapa(gdf, anio=anio, incluir_cali=incluir_cali)
            if gdf_tmp.empty:
                continue
            gdf_tmp = _corregir_geometrias(gdf_tmp)
            gdf_tmp = _preparar_para_folium(gdf_tmp)
            if not gdf_tmp.empty:
                datasets[clave] = json.loads(gdf_tmp.to_json())
    return datasets


def _preparar_heat_data(puntos_df):
    heat_data = {}
    for anio, grupo in puntos_df.groupby("anio"):
        anio_str = str(anio)
        heat_data[f"{anio_str}_con_cali"] = grupo[["lat", "lng"]].values.tolist()
        sin_cali = grupo[grupo["mpio_ccdgo"].notna() & (grupo["mpio_ccdgo"] != "76001")]
        heat_data[f"{anio_str}_sin_cali"] = sin_cali[["lat", "lng"]].values.tolist()
    return heat_data


def generar_mapa_html(gdf, anios_disponibles, ruta_salida, anio_default, puntos_df=None, nombre="mapa_actual.html"):
    datasets = _preparar_dataset_mapa(gdf, anios_disponibles)

    gdf_base = _preparar_para_folium(_corregir_geometrias(gdf.copy()))
    minx, miny, maxx, maxy = gdf_base.total_bounds
    centro_lat = (miny + maxy) / 2
    centro_lon = (minx + maxx) / 2

    datasets_json = json.dumps(datasets, ensure_ascii=False)
    anios_json = json.dumps(anios_disponibles, ensure_ascii=False)

    heat_data = _preparar_heat_data(puntos_df) if puntos_df is not None else {}
    heat_json = json.dumps(heat_data, ensure_ascii=False)

    html = f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="utf-8" />
    <title>Mapa dengue Valle del Cauca</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
    <style>
        html, body {{ width: 100%; height: 100%; margin: 0; padding: 0; font-family: Arial, sans-serif; }}
        #map {{ width: 100%; height: 100vh; background: #eef2f5; }}
        #control-panel {{
            position: absolute; top: 20px; left: 20px; width: 280px; z-index: 9999;
            background: white; padding: 14px; border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.25); font-size: 14px;
        }}
        #control-panel h4 {{ margin: 0 0 10px 0; }}
        #control-panel select, #control-panel button {{
            width: 100%; margin-top: 4px; margin-bottom: 10px; padding: 8px;
            border-radius: 6px; border: 1px solid #999; box-sizing: border-box; font-size: 14px;
        }}
        #btnAplicarMapa {{ background: #2e7d32; color: white; border: none; cursor: pointer; }}
        #btnLimpiarMapa {{ background: #9e9e9e; color: white; border: none; cursor: pointer; }}
        #btnCalor {{ background: #c0392b; color: white; border: none; cursor: pointer; margin-bottom: 10px; }}
        #resumenMapa {{
            margin-top: 10px; font-size: 12px; color: #222;
            background: #f7f7f7; padding: 8px; border-radius: 6px; line-height: 1.5;
        }}
        #estadoMapa {{ margin-top: 10px; font-size: 12px; color: #444; }}
        .legend-box {{
            background: white; padding: 10px; border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.2); font-size: 12px; line-height: 1.5;
        }}
        .legend-item {{ display: flex; align-items: center; margin-bottom: 4px; }}
        .legend-color {{ width: 14px; height: 14px; display: inline-block; margin-right: 6px; }}
    </style>
</head>
<body>
    <div id="map"></div>
    <div id="control-panel">
        <h4>Filtros mapa dengue</h4>
        <label><b>Año</b></label>
        <select id="anioSelect"></select>
        <label><b>Variable</b></label>
        <select id="variableSelect">
            <option value="conteo_dengue" selected>Casos absolutos</option>
            <option value="incidencia_dengue">Incidencia x 100k hab.</option>
        </select>
        <label><b>Cali</b></label>
        <select id="caliSelect">
            <option value="sin_cali" selected>Sin Cali</option>
            <option value="con_cali">Con Cali</option>
        </select>
        <div style="display:flex; gap:8px;">
            <button id="btnAplicarMapa">Aplicar</button>
            <button id="btnLimpiarMapa">Limpiar</button>
        </div>
        <button id="btnCalor">Mapa de calor: OFF</button>
        <div id="estadoMapa">Selecciona filtros.</div>
        <div id="resumenMapa">Sin resumen.</div>
    </div>
    <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
    <script src="https://unpkg.com/leaflet.heat@0.2.0/dist/leaflet-heat.js"></script>
    <script>
        const datasetsDengue = {datasets_json};
        const aniosDisponibles = {anios_json};
        const anioDefault = {anio_default};
        const centroInicial = [{centro_lat}, {centro_lon}];
        const zoomInicial = 7;
        const heatData = {heat_json};

        const map = L.map('map', {{ zoomControl: true, preferCanvas: true }}).setView(centroInicial, zoomInicial);

        L.tileLayer('https://{{s}}.basemaps.cartocdn.com/light_all/{{z}}/{{x}}/{{y}}{{r}}.png', {{
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 19
        }}).addTo(map);

        let capaActual = null;
        let leyendaActual = null;
        let capaCalor = null;
        let calorActivo = false;

        function formatNumber(x) {{ return Number(x).toLocaleString('es-CO'); }}

        function poblarAnios() {{
            const sel = document.getElementById('anioSelect');
            sel.innerHTML = '';
            aniosDisponibles.forEach(a => {{
                const opt = document.createElement('option');
                opt.value = a; opt.textContent = a;
                if (a === anioDefault) opt.selected = true;
                sel.appendChild(opt);
            }});
        }}

        function getColor(valor, bins) {{
            if (valor > bins[4]) return '#bd0026';
            if (valor > bins[3]) return '#f03b20';
            if (valor > bins[2]) return '#fd8d3c';
            if (valor > bins[1]) return '#fecc5c';
            return '#ffffb2';
        }}

        function calcularBins(valores) {{
            const vals = valores.filter(v => v !== null && !isNaN(v)).map(v => Number(v)).sort((a, b) => a - b);
            if (vals.length === 0) return [0, 1, 2, 3, 4];
            const quant = frac => vals[Math.floor((vals.length - 1) * frac)];
            return [quant(0.2), quant(0.4), quant(0.6), quant(0.8), quant(0.95)];
        }}

        function crearLeyenda(bins, anio, etiqueta) {{
            if (leyendaActual) map.removeControl(leyendaActual);
            leyendaActual = L.control({{ position: 'topright' }});
            leyendaActual.onAdd = function() {{
                const div = L.DomUtil.create('div', 'legend-box');
                const colores = ['#ffffb2','#fecc5c','#fd8d3c','#f03b20','#bd0026'];
                div.innerHTML = '<b>' + etiqueta + ' ' + anio + '</b><br>';
                let desde = 0;
                for (let i = 0; i < bins.length; i++) {{
                    const hasta = Math.round(bins[i]);
                    div.innerHTML += `<div class="legend-item"><span class="legend-color" style="background:${{colores[i]}}"></span><span>${{formatNumber(desde)}} - ${{formatNumber(hasta)}}</span></div>`;
                    desde = hasta + 1;
                }}
                return div;
            }};
            leyendaActual.addTo(map);
        }}

        function actualizarMapaDengue() {{
            const anio = document.getElementById('anioSelect').value;
            const cali = document.getElementById('caliSelect').value;
            const variable = document.getElementById('variableSelect').value;
            const data = datasetsDengue[anio + '_' + cali];

            if (!data || !data.features || data.features.length === 0) {{
                document.getElementById('estadoMapa').innerHTML = 'No hay datos para esa combinación.';
                document.getElementById('resumenMapa').innerHTML = 'Sin resumen.';
                return;
            }}

            if (capaActual) map.removeLayer(capaActual);

            const valores = data.features.map(f => f.properties[variable]);
            const bins = calcularBins(valores);
            const totalCasos = data.features.map(f => f.properties["conteo_dengue"]).reduce((acc, v) => acc + Number(v || 0), 0);

            capaActual = L.geoJSON(data, {{
                style: feature => ({{
                    fillColor: calorActivo ? 'transparent' : getColor(feature.properties[variable], bins),
                    weight: calorActivo ? 1.5 : 1,
                    opacity: 1,
                    color: calorActivo ? '#555' : 'black',
                    fillOpacity: calorActivo ? 0 : 0.75
                }}),
                onEachFeature: (feature, layer) => {{
                    const p = feature.properties || {{}};

                    layer.bindTooltip(
                        '<b>' + (p["MPIO_CNMBR"] || '') + '</b><br>' +
                        'Casos: ' + formatNumber(p["conteo_dengue"] || 0) + '<br>' +
                        'Incidencia: ' + formatNumber(p["incidencia_dengue"] || 0) + ' x 100k'
                    );

                    const inc = Number(p["incidencia_dengue"] || 0);
                    const pct = totalCasos > 0 ? (Number(p["conteo_dengue"] || 0) / totalCasos * 100).toFixed(1) : '0.0';
                    const nivel = inc > 1000 ? ['Critico', '#bd0026'] :
                                  inc > 500  ? ['Alto',    '#f03b20'] :
                                  inc > 100  ? ['Medio',   '#fd8d3c'] :
                                               ['Bajo',    '#2e7d32'];

                    layer.bindPopup(`
                        <div style="min-width:210px; font-size:13px">
                            <div style="background:${{nivel[1]}}; color:white; padding:8px 10px; margin:-13px -20px 10px; border-radius:4px 4px 0 0; font-weight:bold; font-size:14px">
                                ${{p["MPIO_CNMBR"] || ''}}
                            </div>
                            <table style="width:100%; border-collapse:collapse">
                                <tr>
                                    <td style="color:#666; padding:3px 0">Código DANE</td>
                                    <td style="text-align:right"><b>${{p["MPIO_CCDGO"] || ''}}</b></td>
                                </tr>
                                <tr>
                                    <td style="color:#666; padding:3px 0">Año</td>
                                    <td style="text-align:right"><b>${{p["año"] || ''}}</b></td>
                                </tr>
                                <tr>
                                    <td style="color:#666; padding:3px 0">Población</td>
                                    <td style="text-align:right"><b>${{formatNumber(p["población"] || 0)}}</b></td>
                                </tr>
                                <tr>
                                    <td style="color:#666; padding:3px 0">Casos</td>
                                    <td style="text-align:right"><b>${{formatNumber(p["conteo_dengue"] || 0)}}</b></td>
                                </tr>
                                <tr>
                                    <td style="color:#666; padding:3px 0">% del total</td>
                                    <td style="text-align:right"><b>${{pct}}%</b></td>
                                </tr>
                                <tr>
                                    <td style="color:#666; padding:3px 0">Incidencia</td>
                                    <td style="text-align:right"><b>${{formatNumber(inc)}} x 100k</b></td>
                                </tr>
                                <tr>
                                    <td style="color:#666; padding:3px 0">Nivel</td>
                                    <td style="text-align:right">
                                        <span style="background:${{nivel[1]}}; color:white; padding:2px 8px; border-radius:10px; font-size:12px">
                                            ${{nivel[0]}}
                                        </span>
                                    </td>
                                </tr>
                            </table>
                        </div>
                    `);
                    layer.on({{
                        mouseover: e => e.target.setStyle({{ weight: 3, color: '#333', fillOpacity: 0.9 }}),
                        mouseout: e => {{ if (capaActual) capaActual.resetStyle(e.target); }}
                    }});
                }}
            }}).addTo(map);

            try {{ map.fitBounds(capaActual.getBounds()); }}
            catch (err) {{ map.setView(centroInicial, zoomInicial); }}

            const etiquetaVariable = variable === 'conteo_dengue' ? 'Casos absolutos' : 'Incidencia x 100k';
            crearLeyenda(bins, anio, etiquetaVariable);
            document.getElementById('estadoMapa').innerHTML = 'Mostrando <b>' + anio + '</b> — ' + cali.replace('_', ' ');
            document.getElementById('resumenMapa').innerHTML =
                '<b>Municipios:</b> ' + formatNumber(data.features.length) + '<br>' +
                '<b>Total casos:</b> ' + formatNumber(totalCasos);
        }}

        function limpiarMapa() {{
            document.getElementById('anioSelect').value = String(anioDefault);
            document.getElementById('caliSelect').value = 'sin_cali';
            document.getElementById('variableSelect').value = 'conteo_dengue';
            actualizarMapaDengue();
        }}

        function actualizarCapaCalor() {{
            const anio = document.getElementById('anioSelect').value;
            const cali = document.getElementById('caliSelect').value;
            if (capaCalor) {{ map.removeLayer(capaCalor); capaCalor = null; }}
            if (!calorActivo) return;
            const puntos = heatData[anio + '_' + cali];
            if (!puntos || puntos.length === 0) return;
            capaCalor = L.heatLayer(puntos, {{
                radius: 18,
                blur: 22,
                maxZoom: 12,
                gradient: {{ 0.2: '#ffffb2', 0.4: '#fecc5c', 0.6: '#fd8d3c', 0.8: '#f03b20', 1.0: '#bd0026' }}
            }}).addTo(map);
        }}

        function refrescarEstiloCoropletico() {{
            if (!capaActual) return;
            const variable = document.getElementById('variableSelect').value;
            const data = capaActual.toGeoJSON();
            const valores = data.features.map(f => f.properties[variable]);
            const bins = calcularBins(valores);
            capaActual.setStyle(feature => ({{
                fillColor: calorActivo ? 'transparent' : getColor(feature.properties[variable], bins),
                weight: calorActivo ? 1.5 : 1,
                opacity: 1,
                color: calorActivo ? '#555' : 'black',
                fillOpacity: calorActivo ? 0 : 0.75
            }}));
        }}

        document.getElementById('btnCalor').addEventListener('click', function() {{
            calorActivo = !calorActivo;
            this.textContent = 'Mapa de calor: ' + (calorActivo ? 'ON' : 'OFF');
            this.style.background = calorActivo ? '#2c3e50' : '#c0392b';
            refrescarEstiloCoropletico();
            actualizarCapaCalor();
        }});

        document.getElementById('btnAplicarMapa').addEventListener('click', function() {{
            actualizarMapaDengue();
            actualizarCapaCalor();
        }});
        document.getElementById('btnLimpiarMapa').addEventListener('click', limpiarMapa);
        document.getElementById('anioSelect').addEventListener('change', function() {{
            actualizarMapaDengue();
            actualizarCapaCalor();
        }});
        document.getElementById('caliSelect').addEventListener('change', function() {{
            actualizarMapaDengue();
            actualizarCapaCalor();
        }});
        document.getElementById('variableSelect').addEventListener('change', actualizarMapaDengue);

        poblarAnios();
        actualizarMapaDengue();
    </script>
</body>
</html>"""

    ruta_salida = Path(ruta_salida)
    ruta_salida.mkdir(parents=True, exist_ok=True)
    ruta_html = ruta_salida / nombre
    ruta_html.write_text(html, encoding="utf-8")
    print(f"Mapa guardado en: {ruta_html}")
    return ruta_html
