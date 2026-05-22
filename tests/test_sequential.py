import sys
from pathlib import Path

# Add project roots to ensure correct imports
_CHATBOT_DIR = Path(__file__).resolve().parents[1] / "chatbot"
if str(_CHATBOT_DIR) not in sys.path:
    sys.path.insert(0, str(_CHATBOT_DIR))

from server import _extract_navigation_action
from fastapi.testclient import TestClient
from server import app

from unittest.mock import patch
import geopandas as gpd
from shapely.geometry import Point

client = TestClient(app)

def test_extract_navigation_action():
    # Test case 1: mixed navigation and query
    clean, action = _extract_navigation_action("Abre demografía y dime la población de Cali")
    assert clean == "dime la población de Cali"
    assert action == {"type": "navigate", "section": "demografia"}

    # Test case 2: navigation and trailing connector
    clean, action = _extract_navigation_action("Navega a tendencias y grafica Cali")
    assert clean == "grafica Cali"
    assert action == {"type": "navigate", "section": "tendencias"}

    # Test case 3: query first, then navigation
    clean, action = _extract_navigation_action("Muéstrame la población de Cali y abre demografía")
    assert clean == "Muéstrame la población de Cali"
    assert action == {"type": "navigate", "section": "demografia"}

    # Test case 4: pure navigation (no mixed query) should return None action
    clean, action = _extract_navigation_action("abre demografía")
    assert action is None

    # Test case 5: no navigation keywords
    clean, action = _extract_navigation_action("cuál es la población de Cali")
    assert action is None

@patch("server.cargar_datos")
def test_chat_sequential_endpoint(mock_cargar_datos, mock_env_vars):
    # Setup mock GeoDataFrame with Cali's population in 2024
    mock_gdf = gpd.GeoDataFrame(
        {
            "MPIO_CCDGO": ["76001"],
            "MPIO_CNMBR": ["CALI"],
            "año": [2024],
            "poblacion": [2250000],
            "conteo_dengue": [1250],
            "incidencia_dengue": [55.5],
            "geom": [Point(0, 0)],
        },
        geometry="geom",
    )
    mock_cargar_datos.return_value = mock_gdf

    # Reset any cached municipios in server to ensure mock data is loaded
    import server
    if hasattr(server._all_municipios, "_cache"):
        delattr(server._all_municipios, "_cache")

    # Check that a mixed query gets mapped correctly and prepends the navigation action
    response = client.post("/chat", json={"session_id": "test_suite_session", "message": "Abre demografía y dime la población de Cali"})
    assert response.status_code == 200
    data = response.json()
    assert "Cali" in data["reply"]
    assert len(data["actions"]) >= 1
    assert data["actions"][0] == {"type": "navigate", "section": "demografia"}


@patch("server.cargar_datos")
def test_chat_yearless_trends_query(mock_cargar_datos, mock_env_vars):
    mock_gdf = gpd.GeoDataFrame(
        {
            "MPIO_CCDGO": ["76001", "76001"],
            "MPIO_CNMBR": ["CALI", "CALI"],
            "año": [2023, 2024],
            "poblacion": [2250000, 2250000],
            "conteo_dengue": [1100, 1250],
            "incidencia_dengue": [48.8, 55.5],
            "geom": [Point(0, 0), Point(0, 0)],
        },
        geometry="geom",
    )
    mock_cargar_datos.return_value = mock_gdf

    import server
    if hasattr(server._all_municipios, "_cache"):
        delattr(server._all_municipios, "_cache")

    response = client.post("/chat", json={"session_id": "test_suite_session", "message": "muestrame los casos de dengue de cali"})
    assert response.status_code == 200
    data = response.json()
    assert "Cali" in data["reply"]
    assert "1,250" in data["reply"]
    assert "1,100" in data["reply"]
    assert len(data["artifacts"]) == 1
    assert "serie_historica_casos_cali.png" in data["artifacts"]
    assert len(data["actions"]) == 1
    assert data["actions"][0] == {
        "type": "show_tendencias",
        "municipios": ["Cali"],
        "metrica": "casos",
        "anio": None,
    }


@patch("server.cargar_datos")
def test_chat_navigate_tendencias_with_municipio(mock_cargar_datos, mock_env_vars):
    mock_gdf = gpd.GeoDataFrame(
        {
            "MPIO_CCDGO": ["76001", "76001"],
            "MPIO_CNMBR": ["CALI", "CALI"],
            "año": [2023, 2024],
            "poblacion": [2250000, 2250000],
            "conteo_dengue": [1100, 1250],
            "incidencia_dengue": [48.8, 55.5],
            "geom": [Point(0, 0), Point(0, 0)],
        },
        geometry="geom",
    )
    mock_cargar_datos.return_value = mock_gdf

    import server
    if hasattr(server._all_municipios, "_cache"):
        delattr(server._all_municipios, "_cache")

    response = client.post("/chat", json={"session_id": "test_suite_session", "message": "abre tendencias de cali"})
    assert response.status_code == 200
    data = response.json()
    assert "Cali" in data["reply"]
    assert len(data["actions"]) == 2
    assert data["actions"][0] == {"type": "navigate", "section": "tendencias"}
    assert data["actions"][1] == {
        "type": "show_tendencias",
        "municipios": ["Cali"],
        "metrica": "casos",
        "anio": None,
    }


@patch("server.cargar_datos")
def test_chat_multi_municipios_sequential_flow(mock_cargar_datos, mock_env_vars):
    # Setup mock GeoDataFrame with multiple municipalities and years
    mock_gdf = gpd.GeoDataFrame(
        {
            "MPIO_CCDGO": ["76001", "76001", "76520", "76520", "76892", "76892", "76111", "76111", "76147", "76147", "76364", "76364"],
            "MPIO_CNMBR": ["CALI", "CALI", "PALMIRA", "PALMIRA", "YUMBO", "YUMBO", "GUADALAJARA DE BUGA", "GUADALAJARA DE BUGA", "CARTAGO", "CARTAGO", "JAMUND?", "JAMUND?"],
            "año": [2023, 2024, 2023, 2024, 2023, 2024, 2023, 2024, 2023, 2024, 2023, 2024],
            "poblacion": [2200000, 2200000, 350000, 350000, 120000, 120000, 130000, 130000, 140000, 140000, 150000, 150000],
            "conteo_dengue": [1100, 1250, 500, 600, 200, 250, 150, 180, 100, 120, 80, 90],
            "incidencia_dengue": [50.0, 56.8, 142.8, 171.4, 166.7, 208.3, 115.4, 138.5, 71.4, 85.7, 53.3, 60.0],
            "geom": [Point(0, 0)] * 12,
        },
        geometry="geom",
    )
    mock_cargar_datos.return_value = mock_gdf

    import server
    if hasattr(server._all_municipios, "_cache"):
        delattr(server._all_municipios, "_cache")

    session_id = "test_multi_muni_session"

    # Step 1: compare Cali and Palmira
    response = client.post("/chat", json={"session_id": session_id, "message": "compara Cali y Palmira"})
    assert response.status_code == 200
    data = response.json()
    assert "Cali" in data["reply"]
    assert "Palmira" in data["reply"]
    assert len(data["artifacts"]) == 1
    assert "serie_" in data["artifacts"][0]
    assert len(data["actions"]) == 1
    assert data["actions"][0]["type"] == "show_tendencias"
    assert sorted(data["actions"][0]["municipios"]) == ["Cali", "Palmira"]
    assert data["actions"][0]["metrica"] == "casos"

    # Step 2: agrega Yumbo
    response = client.post("/chat", json={"session_id": session_id, "message": "agrega Yumbo"})
    assert response.status_code == 200
    data = response.json()
    assert "Yumbo" in data["reply"]
    assert len(data["artifacts"]) == 1
    assert len(data["actions"]) == 1
    assert data["actions"][0]["type"] == "show_tendencias"
    assert sorted(data["actions"][0]["municipios"]) == ["Cali", "Palmira", "Yumbo"]
    assert data["actions"][0]["metrica"] == "casos"

    # Step 3: quita Cali
    response = client.post("/chat", json={"session_id": session_id, "message": "quita Cali"})
    assert response.status_code == 200
    data = response.json()
    assert "Cali" in data["reply"]  # Mentioned as removed
    assert len(data["artifacts"]) == 1
    assert len(data["actions"]) == 1
    assert data["actions"][0]["type"] == "show_tendencias"
    assert sorted(data["actions"][0]["municipios"]) == ["Palmira", "Yumbo"]
    assert data["actions"][0]["metrica"] == "casos"

    # Step 4: cambia a incidencia
    response = client.post("/chat", json={"session_id": session_id, "message": "cambia a incidencia"})
    assert response.status_code == 200
    data = response.json()
    assert "incidencia" in data["reply"]
    assert len(data["artifacts"]) == 1
    assert len(data["actions"]) == 1
    assert data["actions"][0]["type"] == "show_tendencias"
    assert sorted(data["actions"][0]["municipios"]) == ["Palmira", "Yumbo"]
    assert data["actions"][0]["metrica"] == "incidencia"

    # Step 5: top 5 de municipios con casos
    response = client.post("/chat", json={"session_id": session_id, "message": "top 5 de municipios con casos"})
    assert response.status_code == 200
    data = response.json()
    assert len(data["artifacts"]) == 1
    assert len(data["actions"]) == 1
    assert data["actions"][0]["type"] == "show_tendencias"
    # Cali: 2350, Palmira: 1100, Yumbo: 450, Buga: 330, Cartago: 220, Jamundi: 170
    # Top 5 should be Cali, Palmira, Yumbo, Buga, Cartago (sorted)
    top_expected = ["Cali", "Palmira", "Yumbo", "Guadalajara De Buga", "Cartago"]
    assert sorted(data["actions"][0]["municipios"]) == sorted(top_expected)
    assert data["actions"][0]["metrica"] == "casos"


