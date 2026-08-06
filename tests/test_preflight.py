from aerolink.config import Settings
from aerolink.preflight import pilot2_readiness


def test_preflight_reports_blockers_for_default_development_settings() -> None:
    settings = Settings(_env_file=None)
    statuses = {check.name: check.status for check in pilot2_readiness(settings)}

    assert statuses["https_endpoint"] == "blocker"
    assert statuses["dji_app_license"] == "blocker"
    assert statuses["mqtt_host"] == "blocker"


def test_preflight_accepts_complete_pilot2_test_configuration(monkeypatch) -> None:
    monkeypatch.setattr("aerolink.preflight.Path.is_file", lambda _path: True)
    settings = Settings(
        app_base_url="https://pilot.aerolink.example",
        dji_app_id="app-id",
        dji_app_key="app-key",
        dji_app_license="license",
        mqtt_public_host="mqtt.aerolink.example",
        mqtt_tls_cert_file="C:/private/server.crt",
        mqtt_tls_key_file="C:/private/server.key",
    )

    checks = pilot2_readiness(settings)

    assert all(check.status == "pass" for check in checks)


def test_license_scope_does_not_require_mqtt_or_certificate_files() -> None:
    settings = Settings(
        app_base_url="https://pilot.aerolink.example",
        dji_app_id="app-id",
        dji_app_key="app-key",
        dji_app_license="license",
    )

    checks = pilot2_readiness(settings, scope="license")

    assert [check.name for check in checks] == [
        "https_endpoint",
        "dji_app_id",
        "dji_app_key",
        "dji_app_license",
    ]
    assert all(check.status == "pass" for check in checks)
