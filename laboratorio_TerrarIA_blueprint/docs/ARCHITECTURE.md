# Arquitectura - Laboratorio TerrarIA

## 1. Principio de diseno

TerrarIA funciona como una plataforma matriz. Cada observatorio conserva autonomia tecnica, pero comparte una arquitectura comun:

```text
Fuentes territoriales
        |
        v
PostgreSQL/PostGIS + archivos geoespaciales
        |
        v
src/db.py              carga
src/transform.py       limpieza, pivote, indicadores
src/modelo.py          prediccion, priorizacion, escenarios
src/viz.py             graficas
src/mapa.py            geovisor
src/pipeline.py        orquestacion
        |
        v
outputs/               CSV, PNG, HTML, GeoJSON
        |
        v
frontend/              dashboard o geovisor publico
```

## 2. Capas

### Plataforma

La carpeta `platform/` contiene la landing institucional del laboratorio: lineas estrategicas, componentes, observatorios y aliados.

### Observatorios

La carpeta `observatorios/` agrupa proyectos tematicos. Cada observatorio debe poder ejecutarse, probarse y documentarse por separado.

### Componentes compartidos

En una etapa posterior se puede agregar `packages/terrarIA_core/` para reutilizar componentes comunes:

- Conexion a PostGIS.
- Validacion de esquemas.
- Utilidades geoespaciales.
- Estilos de graficas.
- Exportadores para frontend.
- Plantillas de documentacion.

## 3. Observatorios iniciales

| Observatorio | Estado | Enfoque |
| --- | --- | --- |
| GeoSalud | Avanzado | Dengue, vigilancia epidemiologica, mapas de riesgo, modelos predictivos |
| GeoTurismo | Base propuesta | Flujos de visitantes, atractivos, accesibilidad, seguridad, ocupacion y oportunidades |

## 4. Arquitectura de GeoTurismo

GeoTurismo recicla la estructura de GeoSalud y cambia el dominio:

```text
PostGIS / CSV / APIs turisticas
        |
        v
Carga de atractivos, visitas, oferta, ocupacion, movilidad y seguridad
        |
        v
Normalizacion territorial por municipio, zona, temporada y categoria
        |
        v
Indicadores: demanda, accesibilidad, presion turistica, oportunidad, riesgo
        |
        v
Priorizacion de destinos y corredores
        |
        v
Graficas, mapas y dashboard
```

## 5. Salidas minimas por observatorio

- `outputs/indicadores_*.csv`
- `outputs/priorizacion_*.csv`
- `outputs/graficas/*.png`
- `outputs/mapa_actual.html`
- `frontend/index.html`
- Documentacion tecnica en `docs/`
