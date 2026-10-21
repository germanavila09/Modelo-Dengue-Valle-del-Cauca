# Manual de Usuario — Asistente GeoSalud

El **Asistente GeoSalud** es el chat integrado en el dashboard. Responde preguntas en lenguaje natural sobre dengue en el Valle del Cauca: datos por municipio, rankings, series históricas, mapas, y más.

No necesitas saber SQL ni manejar filtros — escribe como hablarías con un analista.

---

## Cómo acceder

1. Abre `frontend/Geodata Salud.html` en tu navegador.
2. El ícono de chat aparece en la esquina inferior derecha del dashboard.
3. Asegúrate de que el servidor esté corriendo en `http://localhost:8080` (ve el README para el arranque).

---

## Tipos de consultas

### Datos puntuales

Pregunta por casos o incidencia de un municipio en un año específico.

```
¿Cuántos casos de dengue tuvo Cali en 2024?
¿Cuál fue la incidencia de Palmira en 2023?
Dame los datos de Buenaventura para 2022
```

La respuesta incluye: casos confirmados, incidencia por 100.000 hab. y población estimada.

---

### Rankings (Top N municipios)

```
Top 5 municipios con más casos en 2024
¿Cuáles son los 10 municipios con mayor incidencia en 2023?
Muéstrame el ranking de casos del Valle en 2022
```

Puedes pedir entre 1 y 42 municipios. La métrica por defecto es casos absolutos; añade "incidencia" para cambiarla.

---

### Series históricas

```
Evolución histórica de dengue en Tuluá
Serie temporal de Palmira
¿Cómo ha cambiado la incidencia en Buga entre 2019 y 2026?
```

Para comparar municipios, mencionarlos juntos:

```
Compara la serie de casos entre Cali, Palmira y Buenaventura
Serie de los 5 municipios con más casos históricos
```

Para ajustar una serie ya mostrada:
```
Agrega Cartago a la comparación
Quita Cali de la gráfica
Cambia a incidencia
```

---

### Resúmenes anuales del departamento

```
¿Cómo estuvo el dengue en el Valle en 2023?
Resumen del departamento para 2024
¿Qué pasó con el dengue en 2020?
```

Muestra: total de casos, incidencia departamental, municipios más afectados y municipios con datos.

---

### Demografía y población

```
¿Cuál es la población de Cali en 2024?
¿Cuántos habitantes tiene Palmira?
Distribución por ciclo de vida en Buga
Pirámide poblacional de Zarzal
Población del Valle del Cauca en 2024
```

Los datos demográficos incluyen: total, hombres, mujeres y porcentajes. Los ciclos de vida muestran distribución por etapa (primera infancia, infancia, adolescencia, etc.). La pirámide muestra grupos quinquenales.

---

### Navegación del dashboard (control por voz)

El asistente puede abrir módulos y cambiar vistas del dashboard directamente:

```
Abre el panel de indicadores
Muéstrame el módulo de tendencias
Ve a priorización
Abre demografía para 2023
```

**Módulos disponibles:** Panel · Indicadores · Tendencias · Priorización · Demografía

---

### Mapas y visualizaciones geoespaciales

```
Muéstrame el mapa de casos del Valle en 2024
Mapa coroplético de incidencia para 2023
Mapa de nivel de riesgo
Mapa sin Cali para ver mejor los demás municipios
```

Variables disponibles: `casos` (absolutos), `incidencia` (x100k hab.), `riesgo` (nivel calculado), `delta` (cambio 2023–24).

Para el Geovisor interactivo:

```
Abre el geovisor en modo burbujas
Geovisor de calor para 2024
Mapa interactivo con casos
```

---

### Consultas combinadas

El asistente puede resolver datos y navegar en el mismo mensaje:

```
Dame el top 5 de 2024 y abre el módulo de tendencias
Muéstrame los casos de Tuluá y abre el geovisor
```

---

## Contexto de conversación

El asistente recuerda lo que preguntaste antes en la misma sesión:

```
Usuario: "¿Cuántos casos tuvo Cali en 2024?"
→ Asistente: "4.823 casos..."

Usuario: "¿Y en 2023?"
→ Asistente entiende que preguntas por Cali nuevamente
```

```
Usuario: "Top 5 de 2024"
→ Asistente muestra el ranking

Usuario: "Agrega el 6° y el 7°"
→ Asistente extiende la lista
```

---

## Corrección automática de nombres

El asistente corrige errores tipográficos y aliases comunes automáticamente:

| Lo que escribes | Lo que entiende |
|-----------------|----------------|
| Buga | Guadalajara de Buga |
| Santiago de Cali | Cali |
| Jamundí / Jamundiì / Jamundi | JAMUNDÍ |
| Tulua / Tuluá | TULUÁ |
| Calima el Darién | CALIMA |

---

## Preguntas frecuentes

**¿Qué período cubre el observatorio?**
2019 a 2026, con 42 municipios del Valle del Cauca.

**¿Cuándo el asistente genera una imagen?**
Cuando pides un "top", "ranking", "gráfica", "visualiza" o "compara visualmente". Las imágenes aparecen en el panel de tendencias del dashboard.

**¿El asistente funciona sin internet?**
Para consultas de datos estructurados (rankings, casos, series) funciona completamente sin conexión. Para preguntas en lenguaje libre requiere conexión a Gemini.

**¿Puedo preguntar sobre enfermedades distintas al dengue?**
El observatorio está especializado en dengue. Para otras enfermedades, el asistente lo indicará.

**¿Qué significa "incidencia"?**
Casos por 100.000 habitantes. Permite comparar municipios de distinto tamaño de forma justa.

---

## Ejemplos de sesión completa

```
👤 Hola, ¿qué puedes hacer?
🤖 Soy el asistente del Observatorio GeoSalud...

👤 ¿Cuáles fueron los 5 municipios con más casos en 2024?
🤖 Los 5 municipios con mayor número de casos en 2024 fueron:
   1. Santiago de Cali: 4.823 casos
   2. Buenaventura: 1.205 casos
   ...
   [Gráfica generada: top5_casos_2024.png]

👤 Y en incidencia, ¿cuáles salieron peor?
🤖 Por incidencia x100k en 2024:
   1. El Dovio: 892.4 por 100.000 hab.
   ...

👤 Muéstrame la serie histórica de El Dovio
🤖 [Abre módulo Tendencias con la serie de El Dovio]
   2019: 45 casos (inc. 380.2) ...

👤 Agrega Versalles a la comparación
🤖 Listo, agregué Versalles. Actualicé la serie...

👤 Abre el mapa de incidencia para 2024 sin Cali
🤖 Listo. Actualicé el mapa coroplético para incidencia x100k en 2024 (sin Cali).
```
