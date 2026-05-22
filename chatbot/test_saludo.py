"""Test aislado del saludo."""
import httpx, traceback

BASE = "http://localhost:8080"

try:
    r = httpx.post(f"{BASE}/chat", json={"session_id": "test-saludo-001", "message": "Hola, que puedes hacer?"}, timeout=60)
    print(f"Status: {r.status_code}")
    print(f"Body: {r.text[:2000]}")
except Exception as e:
    traceback.print_exc()
