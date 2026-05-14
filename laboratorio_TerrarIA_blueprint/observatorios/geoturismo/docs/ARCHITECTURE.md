# Arquitectura - GeoTurismo

GeoTurismo recicla la arquitectura de GeoSalud para turismo inteligente.

## Flujo

```text
PostgreSQL/PostGIS
        |
        v
src/db.py
        |
        v
src/transform.py
        |
        +--> indicadores_turisticos.csv
        +--> priorizacion_destinos.csv
        |
        v
src/viz.py + src/mapa.py
        |
        v
outputs/graficas + outputs/mapa_actual.html
```

## Variables esperadas

- `municipio`
- `anio`
- `visitantes`
- `atractivos`
- `ocupacion_hotelera`
- `gasto_estimado`
- `indice_seguridad`
- `tiempo_acceso_min`
- `geom`

## Indicador principal

El `indice_oportunidad_turistica` combina demanda, oferta, ocupacion, gasto, seguridad y accesibilidad.
