# 📚 Documentación — Observatorio GeoSalud

Bienvenido a la documentación completa del Observatorio GeoSalud. Aquí encontrarás toda la información necesaria para instalar, usar y entender el proyecto.

## 🚀 Comenzar Rápido

**Nuevo en el proyecto?** Comienza aquí:

1. [📦 SETUP.md](SETUP.md) — Instalación paso-a-paso (5-10 minutos)
2. [▶️ README.md](../README.md) — Overview y quick start

Luego explora:
- [🏗️ ARCHITECTURE.md](ARCHITECTURE.md) — Cómo está estructurado el proyecto
- [📖 API.md](API.md) — Referencia de funciones

---

## 📖 Documentación Completa

### Para Usuarios

| Documento | Descripción | Tiempo |
|-----------|-------------|--------|
| [SETUP.md](SETUP.md) | Instalación, configuración de BD, troubleshooting | 20 min |
| [README.md](../README.md) | Descripción del proyecto, uso de scripts, ejemplos | 10 min |
| [QUICK_START.md](#) | 5 comandos para empezar (próximamente) | 5 min |

### Para Desarrolladores

| Documento | Descripción | Nivel |
|-----------|-------------|-------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | Diseño del sistema, componentes, flujos de datos | Intermedio |
| [API.md](API.md) | Referencia completa de funciones públicas | Intermedio |
| [CONTRIBUTING.md](#) | Guía para contribuir al proyecto (próximamente) | Intermedio |
| [TESTING.md](#) | Cómo escribir y ejecutar tests (próximamente) | Avanzado |

### Para DevOps/Deployment

| Documento | Descripción |
|-----------|-------------|
| [DEPLOYMENT.md](#) | Docker, Kubernetes, CI/CD (próximamente) |
| [PERFORMANCE.md](#) | Benchmarking, optimización (próximamente) |

---

## 🗺️ Mapa del Proyecto

```
observatorio_geosalud/
├── 📖 README.md                    ◄─── Empieza aquí
├── docs/
│   ├── INDEX.md                    ◄─── Eres aquí
│   ├── SETUP.md                    ◄─── Instalación
│   ├── ARCHITECTURE.md             ◄─── Diseño técnico
│   ├── API.md                      ◄─── Referencia de funciones
│   ├── CONTRIBUTING.md             ◄─── (próximamente)
│   └── DEPLOYMENT.md               ◄─── (próximamente)
│
├── src/                            ◄─── Código principal
│   ├── config.py                   
│   ├── db.py                       
│   ├── transform.py                
│   ├── viz.py                      
│   ├── mapa.py                     
│   ├── modelo.py                   
│   └── pipeline.py                 
│
├── scripts/                        ◄─── Scripts ejecutables
│   ├── run_all.py                  ◄─── Main entry point
│   ├── verificar_conexion.py       
│   ├── resumen.py                  
│   ├── exportar_mapa.py            
│   └── exportar_datos_obs.py       
│
├── notebooks/                      ◄─── Análisis exploratorio
│   └── analisis_dengue.ipynb       
│
├── tests/                          ◄─── Tests unitarios
│   ├── conftest.py
│   ├── test_db.py
│   ├── test_transform.py
│   └── test_pipeline.py
│
├── frontend/                       ◄─── Dashboard HTML
│   ├── Geodata Salud.html
│   ├── geodata-app.js
│   └── geodata-data.js
│
└── outputs/                        ◄─── Archivos generados
    ├── graficas/
    ├── lightning_logs/
    └── *.csv
```

---

## 📋 Tareas Comunes

### "¿Cómo instalo el proyecto?"
👉 [SETUP.md](SETUP.md) — Sigue la sección **1-8** (20 minutos)

### "¿Cómo ejecuto el análisis?"
👉 [README.md](../README.md) — Sección **Uso** → `python scripts/run_all.py`

### "¿Cómo genero el mapa interactivo?"
👉 [README.md](../README.md) — `python scripts/exportar_mapa.py --anio 2024`

### "¿Cómo agrego una nueva gráfica?"
👉 [ARCHITECTURE.md](ARCHITECTURE.md) — Sección **7. Extensibilidad**

### "¿Cuáles son todas las funciones disponibles?"
👉 [API.md](API.md) — Referencia completa con ejemplos

### "¿Cómo hago pronósticos?"
👉 [API.md](API.md) → Sección `src.pipeline` → `ejecutar_forecast()`

### "¿Cuál es el flujo de datos?"
👉 [ARCHITECTURE.md](ARCHITECTURE.md) — Sección **3. Flujo de Datos**

### "¿Cómo ejecuto tests?"
👉 [README.md](../README.md) — Sección **🛠️ Desarrollo** → `pytest -v`

### "¿Cómo instalo herramientas de desarrollo?"
👉 [SETUP.md](SETUP.md) — Sección **3. Instalar Dependencias** → "Con Herramientas de Desarrollo"

### "¿Cómo soluciono errores de conexión a BD?"
👉 [SETUP.md](SETUP.md) — Sección **Troubleshooting** → "Connection refused"

---

## 🎓 Learning Path

### Nivel 1: Usuario (30 minutos)
1. Leer [SETUP.md](SETUP.md) — instalar
2. Leer [README.md](../README.md) — usar
3. Ejecutar `python scripts/run_all.py`
4. Abrir `outputs/mapa_actual.html` en navegador

### Nivel 2: Desarrollador (2 horas)
1. Completar Nivel 1
2. Leer [ARCHITECTURE.md](ARCHITECTURE.md) — entender diseño
3. Leer [API.md](API.md) — conocer funciones
4. Modificar `src/viz.py` — agregar nueva gráfica
5. Ejecutar tests: `pytest -v`

### Nivel 3: Contribuidor (4+ horas)
1. Completar Nivel 2
2. Leer código fuente completamente
3. Crear feature branch: `git checkout -b feature/nuevo-analisis`
4. Escribir tests en `tests/`
5. Hacer PR a `main`

---

## 🔗 Enlaces Rápidos

| Tema | Enlace |
|------|--------|
| **Instalación** | [SETUP.md](SETUP.md) |
| **Quick Start** | [README.md](../README.md#-quick-start) |
| **Usar Scripts** | [README.md](../README.md#-uso) |
| **Arquitectura** | [ARCHITECTURE.md](ARCHITECTURE.md) |
| **Referencia API** | [API.md](API.md) |
| **Desarrollo** | [README.md](../README.md#-desarrollo) |
| **Troubleshooting** | [SETUP.md](SETUP.md#troubleshooting) |
| **GitHub** | https://github.com/germanavila09/Observatorio-GeoSalud |
| **Issues** | https://github.com/germanavila09/Observatorio-GeoSalud/issues |

---

## ❓ FAQ

### ¿Python 3.9 es suficiente?
No, se requiere Python 3.10+. Algunos paquetes (neuralprophet) requieren 3.10 mínimo.

### ¿Puedo usar SQLite en lugar de PostgreSQL?
No. El proyecto usa características específicas de PostGIS (geometrías). Requiere PostgreSQL 13+.

### ¿Necesito GPU para usar el proyecto?
No, es opcional. GPU acelera pronósticos (12-15 min GPU vs 30-45 min CPU), pero no es obligatorio.

### ¿Qué versión de PostGIS necesito?
PostGIS 3.0+. Instálalo con PostgreSQL desde https://postgis.net/install/

### ¿Cómo creo la base de datos?
Ver [SETUP.md](SETUP.md) — Sección **4. Configurar PostgreSQL**

### ¿Dónde se guardan los resultados?
En la carpeta definida por `RUTA_SALIDA` en `.env` (default: `outputs/`)

### ¿Qué es el mapa interactivo?
Dashboard HTML (Leaflet.js) con:
- 3 modos de visualización (coroplético, calor, cluster)
- Filtros por año, variable, municipios
- Información de riesgo e indicadores

### ¿Cuántos municipios hay?
42 municipios del Valle del Cauca, desde 2019-2026.

### ¿Puedo modificar el código?
Sí. Ver [ARCHITECTURE.md](ARCHITECTURE.md) — Sección **7. Extensibilidad** para agregar nuevas funciones.

### ¿Cómo reporte bugs?
En https://github.com/germanavila09/Observatorio-GeoSalud/issues

---

## 🤝 Soporte

- 📧 **Email**: germanavila09@gmail.com
- 🐛 **Issues**: [GitHub Issues](https://github.com/germanavila09/Observatorio-GeoSalud/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/germanavila09/Observatorio-GeoSalud/discussions)

---

## 📄 Versionamiento

- **Versión actual**: 0.1.0 (Alpha)
- **Última actualización**: Abril 2026
- **Próxima versión**: 0.2.0 (planeado para Mayo 2026)

---

**¿Nuevo en Git/GitHub?** Ver [Git Guide](https://guides.github.com/) para comenzar.

**¿Problemas?** Busca en [SETUP.md](SETUP.md) → Troubleshooting o crea un [issue](https://github.com/germanavila09/Observatorio-GeoSalud/issues).

Bienvenido al Observatorio GeoSalud 🌍 📊
