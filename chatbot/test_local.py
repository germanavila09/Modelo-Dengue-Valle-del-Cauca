"""Prueba todos los handlers locales directamente (sin necesitar la API de Gemini)."""
import httpx

BASE = "http://localhost:8080"
SESSION = "test-local-001"

casos = [
    ("Info / saludo",            "Hola, que puedes hacer?"),
    ("Casos municipio+año",      "Cuantos casos de dengue tuvo Cali en 2024?"),
    ("Casos municipio+año",      "Cuantos casos tuvo Palmira en 2023?"),
    ("Top 5 casos 2024",         "Top 5 municipios con mas casos en 2024"),
    ("Top 5 incidencia 2023",    "Top 5 municipios por incidencia en 2023"),
    ("Resumen anual Valle",      "Como estuvo el dengue en el Valle en 2022?"),
    ("Serie histórica municipio","Evolucion historica de Buenaventura"),
    ("Mapa coroplético",         "Muestra el mapa coropletico de incidencia 2024"),
    ("Navegar indicadores",      "Abre los indicadores"),
]

for label, msg in casos:
    print(f"\n[{label}]")
    print(f"  Pregunta: {msg}")
    try:
        r = httpx.post(f"{BASE}/chat", json={"session_id": SESSION, "message": msg}, timeout=30)
        data = r.json()
        if r.status_code == 200:
            reply_short = data["reply"].replace("\n", " ")[:200]
            artifacts = data.get("artifacts", [])
            actions = data.get("actions", [])
            print(f"  Reply: {reply_short}")
            if artifacts:
                print(f"  Artifacts: {artifacts}")
            if actions:
                print(f"  Actions: {[a.get('type') for a in actions]}")
        else:
            print(f"  ERROR {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"  EXCEPTION: {e}")
