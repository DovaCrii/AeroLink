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


def test_request_id_is_returned_and_can_be_provided_by_caller() -> None:
    response = client.get("/health", headers={"X-Request-ID": "trace-123"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "trace-123"


def test_metrics_exposes_http_request_signals() -> None:
    response = client.get("/metrics")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "aerolink_http_requests_total" in response.text
    assert "aerolink_http_request_duration_seconds" in response.text


def test_pilot2_diagnostic_page_is_safe_to_open_without_a_controller() -> None:
    response = client.get("/pilot2/diagnostic")

    assert response.status_code == 200
    assert "JSBridge" in response.text
    assert "Licencia no configurada" in response.text
    assert response.headers["cache-control"] == "no-store"
    assert "Content-Security-Policy" in response.headers
