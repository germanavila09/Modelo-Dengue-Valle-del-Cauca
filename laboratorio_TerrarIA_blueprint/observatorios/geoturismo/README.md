# GeoTurismo - Observatorio de Turismo Inteligente

GeoTurismo reutiliza la arquitectura de GeoSalud para analizar oportunidades turisticas desde inteligencia territorial.

## Pregunta guia

Donde se concentran las oportunidades turisticas, que territorios tienen mayor potencial y que factores limitan o habilitan su desarrollo.

## Indicadores iniciales

- Visitantes por municipio, zona o atractivo.
- Atractivos turisticos por categoria.
- Accesibilidad a atractivos y servicios.
- Ocupacion hotelera y capacidad instalada.
- Gasto estimado y dinamica economica.
- Seguridad, riesgos y restricciones territoriales.
- Estacionalidad por temporada.
- Indice de oportunidad turistica.

## Pipeline

```text
1. Carga        src/db.py
2. Limpieza     src/transform.py
3. Indicadores  src/transform.py
4. Graficas     src/viz.py
5. Mapa         src/mapa.py
6. Pipeline     src/pipeline.py
```

## Ejecucion

```powershell
python scripts/run_all.py
```

## Salidas esperadas

- `outputs/indicadores_turisticos.csv`
- `outputs/priorizacion_destinos.csv`
- `outputs/graficas/*.png`
- `outputs/mapa_actual.html`
