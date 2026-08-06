from fastapi.testclient import TestClient

from aerolink.main import app

client = TestClient(app)


def test_health_is_public_and_reports_service() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "aerolink"


def test_api_index_declares_standalone_scope() -> None:
    response = client.get("/api/v1")

    assert response.status_code == 200
    assert response.json()["scope"] == "standalone-dji-gateway"
