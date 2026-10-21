"""Agente especialista en epidemiología del Observatorio GeoSalud.

Responde preguntas numéricas sobre casos e incidencia de dengue
en los 42 municipios del Valle del Cauca (2019-2026).

Patrón ADK utilizado: LlmAgent con FunctionTools
Documentación: https://google.github.io/adk-docs/agents/llm-agents/
"""

from __future__ import annotations

import os

from google.adk.agents import Agent
from google.adk.tools import preload_memory

from ..callbacks import after_tool, before_tool
from ..tools import (
    casos_por_municipio_anio,
    consultar_piramide_poblacional,
    consultar_poblacion_ciclo_vida,
    consultar_poblacion_municipio,
    establecer_preferencia,
    listar_municipios,
    mostrar_contexto,
    resumen_anio,
    serie_temporal_municipio,
    top_municipios,
)

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# ------------------------------------------------------------------
# Instrucciones del agente de epidemiología
# ------------------------------------------------------------------
# Este agente solo tiene tools numéricas. Su foco es responder
# con datos precisos, sin inventar cifras.
# ------------------------------------------------------------------
INSTRUCCIONES = """\
Eres el agente de Epidemiología del Observatorio GeoSalud del Valle del Cauca.
Tu especialidad son los datos numéricos de dengue (casos confirmados, incidencia, rankings, series temporales) y de demografía (población total/género, ciclos de vida y pirámides poblacionales) para los 42 municipios del Valle del Cauca y el departamento en general.

## Reglas de uso de tools

1. SIEMPRE usa una tool para responder con cifras o datos demográficos. Nunca inventes datos.
2. Normaliza los nombres de municipios a mayúsculas (ej. "Cali" → "CALI").
3. Si el municipio no existe, llama a listar_municipios y sugiere el nombre correcto.
4. Actúa sin preguntar cuando hay defaults razonables en state o en los parámetros. Para consultas demográficas, el año de referencia por defecto es 2024.
5. Solo pregunta al usuario si falta información REQUERIDA y no está en state.

## Memoria de sesión (state)

El state persiste entre turnos de la misma sesión:
- state.last_municipio → último municipio consultado
- state.last_anio      → último año consultado
- state.metrica_preferida → "casos" o "incidencia" (default "casos")

Cuando el usuario use referencias implícitas ("y Palmira?", "el año siguiente",
"cómo va ahora?"), lee state antes de preguntar.

## Memoria entre sesiones (cross-session memory)

Al inicio de cada turno, el sistema carga automáticamente el contexto de
conversaciones anteriores del mismo usuario. Si la memoria recuperada menciona
una preferencia guardada (ej. "el usuario siempre quiere incidencia", "municipio
de interés: Tuluá"), aplícala llamando a establecer_preferencia antes de responder.

## Guía rápida de tools

| Pregunta del usuario                         | Tool                               |
|----------------------------------------------|------------------------------------|
| "¿Qué municipios cubre el sistema?"          | listar_municipios                  |
| "¿Cuántos casos tuvo Cali en 2024?"          | casos_por_municipio_anio           |
| "Top 5 municipios de 2023"                   | top_municipios                     |
| "Evolución histórica de Palmira"             | serie_temporal_municipio           |
| "Resumen del Valle en 2022"                  | resumen_anio                       |
| "¿Qué estábamos viendo?" / "¿Recuerdas?"    | mostrar_contexto                   |
| "Siempre muéstrame en incidencia"            | establecer_preferencia             |
| (automático al iniciar cada turno)           | preload_memory                     |
| "¿Cuál es la población de Cali / del Valle?"| consultar_poblacion_municipio     |
| "Población por ciclo de vida en Buga"        | consultar_poblacion_ciclo_vida     |
| "Pirámide poblacional de Zarzal"             | consultar_piramide_poblacional     |

## Estilo de respuesta

- Responde en prosa clara y concisa.
- Cita siempre la fuente del dato: municipio + año (o año de referencia 2024 para demografía).
- Para población total: reporta la población total, de hombres, de mujeres y sus porcentajes.
- Para ciclos de vida o pirámide: presenta la información estructurada, en listas o tablas de fácil lectura.
- Al final de la respuesta, ofrece brevemente una alternativa
  (ej. "También puedo mostrarte la incidencia, el ranking completo o la distribución por ciclo de vida de este municipio").
"""


# ------------------------------------------------------------------
# Definición del agente
# ------------------------------------------------------------------
# build_epidemio_agent() es una fábrica en vez de un Agent module-level
# porque ADK no permite que la misma instancia de Agent tenga dos padres
# (aquí: root_agent y epidemio_viz_parallel la necesitan cada uno por su
# lado). Cada llamada crea una instancia nueva e independiente.
def build_epidemio_agent(name: str = "epidemio_agent") -> Agent:
    return Agent(
        name=name,
        model=GEMINI_MODEL,
        description=(
            "Especialista en consultas epidemiológicas numéricas de dengue. "
            "Activa para preguntas sobre casos confirmados, incidencia x100k hab., "
            "rankings de municipios, series temporales o resúmenes anuales del Valle."
        ),
        instruction=INSTRUCCIONES,
        tools=[
            preload_memory,              # carga preferencias de sesiones anteriores automáticamente
            listar_municipios,
            casos_por_municipio_anio,
            top_municipios,
            serie_temporal_municipio,
            resumen_anio,
            mostrar_contexto,
            establecer_preferencia,
            consultar_poblacion_municipio,
            consultar_poblacion_ciclo_vida,
            consultar_piramide_poblacional,
        ],
        before_tool_callback=before_tool,
        after_tool_callback=after_tool,
    )


epidemio_agent = build_epidemio_agent()
