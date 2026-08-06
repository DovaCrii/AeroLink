from fastapi.testclient import TestClient

from aerolink import main

client = TestClient(main.app)


def test_health_is_public_and_reports_service() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["service"] == "aerolink"


def test_api_index_declares_standalone_scope() -> None:
    response = client.get("/api/v1")

    assert response.status_code == 200
    assert response.json()["scope"] == "standalone-dji-gateway"


def test_readiness_reports_database_availability(monkeypatch) -> None:
    class Connection:
        def __enter__(self):
            return self

        def __exit__(self, *_args) -> None:
            return None

        def execute(self, _statement) -> None:
            return None

    class Engine:
        def connect(self) -> Connection:
            return Connection()

    monkeypatch.setattr(main, "engine", Engine())

    response = client.get("/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ready", "dependency": "database"}


def test_readiness_returns_503_when_database_is_unavailable(monkeypatch) -> None:
    from sqlalchemy.exc import OperationalError

    class UnavailableEngine:
        def connect(self):
            raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(main, "engine", UnavailableEngine())

    response = client.get("/ready")

    assert response.status_code == 503
    assert response.json()["detail"] == "database unavailable"
