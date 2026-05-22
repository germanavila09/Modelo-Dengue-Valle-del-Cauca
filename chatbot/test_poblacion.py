"""Prueba consultas de población en modo local."""
import httpx

BASE = "http://localhost:8080"
SESSION = "test-pob-001"

casos = [
    "Cual es la poblacion de Cali?",
    "Cuantos habitantes tiene Palmira?",
    "Cual es la poblacion del Valle del Cauca?",
    "Cual es la poblacion de Cali en 2022?",
    "Hola, que puedes hacer?",
]

for msg in casos:
    print(f"\n>>> {msg}")
    r = httpx.post(f"{BASE}/chat", json={"session_id": SESSION, "message": msg}, timeout=30)
    data = r.json()
    if r.status_code == 200:
        print(f"  {data['reply'][:300]}")
    else:
        print(f"  ERROR {r.status_code}: {r.text[:200]}")
