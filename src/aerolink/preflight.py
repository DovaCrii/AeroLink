"""Offline readiness checks for a controlled DJI Pilot 2 connection test."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlparse

from aerolink.config import Settings, get_settings


@dataclass(frozen=True)
class Check:
    name: str
    status: str
    message: str


def pilot2_readiness(settings: Settings) -> list[Check]:
    """Validate configuration only; this never contacts DJI, a controller or MQTT."""
    checks: list[Check] = []
    parsed_url = urlparse(settings.app_base_url)
    public_host = parsed_url.hostname or ""
    is_public_https = parsed_url.scheme == "https" and public_host not in {
        "",
        "127.0.0.1",
        "localhost",
    }
    checks.append(
        Check(
            "https_endpoint",
            "pass" if is_public_https else "blocker",
            "APP_BASE_URL must be a non-local HTTPS URL for Pilot 2.",
        )
    )

    for name, value in (
        ("dji_app_id", settings.dji_app_id),
        ("dji_app_key", settings.dji_app_key),
        ("dji_app_license", settings.dji_app_license),
    ):
        checks.append(
            Check(
                name,
                "pass" if value else "blocker",
                f"{name.upper()} must be supplied from the DJI Developer Cloud API app.",
            )
        )

    mqtt_host = settings.mqtt_public_host or ""
    mqtt_is_public = mqtt_host not in {"", "127.0.0.1", "localhost"}
    checks.append(
        Check(
            "mqtt_host",
            "pass" if mqtt_is_public else "blocker",
            "MQTT_PUBLIC_HOST must be reachable from the controller network.",
        )
    )
    checks.append(
        Check(
            "mqtt_tls_port",
            "pass" if settings.mqtt_tls_port == 8883 else "blocker",
            "MQTT_TLS_PORT must be 8883 for the planned MQTTS listener.",
        )
    )

    for name, value in (
        ("mqtt_tls_cert_file", settings.mqtt_tls_cert_file),
        ("mqtt_tls_key_file", settings.mqtt_tls_key_file),
    ):
        exists = bool(value) and Path(value).is_file()
        checks.append(
            Check(
                name,
                "pass" if exists else "blocker",
                f"{name.upper()} must reference a provisioned local TLS file.",
            )
        )
    return checks


def main() -> int:
    checks = pilot2_readiness(get_settings())
    print(json.dumps([asdict(check) for check in checks], indent=2))
    return 1 if any(check.status == "blocker" for check in checks) else 0


if __name__ == "__main__":
    raise SystemExit(main())
