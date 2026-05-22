"""Script de prueba rápida del chatbot."""
import httpx, json, sys

BASE = "http://localhost:8080"
SESSION = "test-001"

def chat(msg: str) -> dict:
    r = httpx.post(f"{BASE}/chat", json={"session_id": SESSION, "message": msg}, timeout=60)
    r.raise_for_status()
    return r.json()

def print_response(label: str, resp: dict):
    print(f"\n{'='*60}")
    print(f"[{label}]")
    print(f"reply: {resp['reply']}")
    print(f"artifacts: {resp.get('artifacts', [])}")
    print(f"actions: {resp.get('actions', [])}")

if __name__ == "__main__":
    preguntas = [
        ("Saludo básico", "Hola, ¿qué puedes hacer?"),
        ("Casos 2024 Cali", "¿Cuántos casos de dengue hubo en Cali en 2024?"),
        ("Top 5 municipios 2024", "¿Cuáles fueron los 5 municipios con más casos en 2024?"),
    ]
    for label, msg in preguntas:
        print(f"\n>>> Enviando: {msg}")
        try:
            resp = chat(msg)
            print_response(label, resp)
        except Exception as e:
            print(f"ERROR: {e}")
