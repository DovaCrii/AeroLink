from fastapi.testclient import TestClient

from aerolink.pilot2 import diagnostic_page
from aerolink.pilot2_connectivity_server import app as connectivity_app
from aerolink.pilot2_diagnostic_server import app as diagnostic_app

diagnostic_client = TestClient(diagnostic_app)
connectivity_client = TestClient(connectivity_app)


def test_diagnostic_page_only_embeds_a_complete_runtime_license() -> None:
    without_license = diagnostic_page(app_id="app-id")
    with_license = diagnostic_page("app-id", "app-key", "license")

    assert "const licenseConfig = null" in without_license.body.decode()
    assert '"appId": "app-id"' in with_license.body.decode()


def test_diagnostic_page_is_not_cacheable() -> None:
    response = diagnostic_page("app-id", "app-key", "license")

    assert response.headers["cache-control"] == "no-store"


def test_temporary_diagnostic_server_exposes_no_api_or_documentation() -> None:
    assert diagnostic_client.get("/").status_code == 200
    assert diagnostic_client.get("/docs").status_code == 404
    assert diagnostic_client.get("/openapi.json").status_code == 404


def test_public_connectivity_server_never_embeds_a_runtime_license() -> None:
    response = connectivity_client.get("/")

    assert response.status_code == 200
    assert "const licenseConfig = null;" in response.text
    assert connectivity_client.get("/docs").status_code == 404
