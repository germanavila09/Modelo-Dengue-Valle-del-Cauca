# Laboratorio TerrarIA

Laboratorio de Inteligencia Territorial para articular observatorios, modelos y geovisores orientados a retos urbanos y regionales.

Este repositorio esta pensado como una casa comun para multiples observatorios territoriales. El primer referente es GeoSalud, ya avanzado en el proyecto `observatorio_geosalud`; el segundo observatorio propuesto es GeoTurismo, reutilizando la arquitectura de carga, transformacion, analitica, visualizacion y publicacion.

## Vision

TerrarIA organiza iniciativas territoriales como productos replicables:

- Observatorios tematicos: salud, turismo, ciudad, ambiente, riesgo, movilidad y servicios.
- Modelos predictivos y de priorizacion.
- Geovisores y tableros interactivos.
- Pipelines reproducibles para datos espaciales.
- Documentacion tecnica y de transferencia.

## Estructura propuesta

```text
laboratorio_TerrarIA/
|-- README.md
|-- docs/
|   |-- ARCHITECTURE.md
|   |-- ROADMAP.md
|   `-- OBSERVATORIOS.md
|-- platform/
|   `-- frontend/
|       |-- index.html
|       |-- platform.css
|       `-- platform.js
|-- observatorios/
|   |-- geosalud/
|   |   `-- README.md
|   `-- geoturismo/
|       |-- README.md
|       |-- .env.example
|       |-- pyproject.toml
|       |-- requirements.txt
|       |-- src/
|       |-- scripts/
|       |-- docs/
|       |-- frontend/
|       |-- tests/
|       `-- outputs/
`-- scripts/
    `-- crear_estructura.ps1
```

## Observatorios iniciales

### GeoSalud

Observatorio Inteligente de Salud Publica. Parte del avance existente en `E:\observatorio_geosalud`, con pipeline para vigilancia epidemiologica, indicadores, mapas de riesgo, AEDE y modelos predictivos.

### GeoTurismo

Observatorio de Turismo Inteligente. Replica la arquitectura de GeoSalud para analizar flujos de visitantes, atractivos, accesibilidad, seguridad, gasto, ocupacion, estacionalidad y oportunidades economicas.

## Comando objetivo

Cada observatorio debe poder producir una salida reproducible con un comando:

```powershell
python scripts/run_all.py
```

El resultado esperado es una carpeta `outputs/` con datos procesados, graficas, indicadores, geovisores y archivos listos para informe o presentacion.
