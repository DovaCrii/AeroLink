from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings with safe development defaults."""

    app_env: str = "dev"
    app_name: str = "AeroLink"
    app_version: str = "0.1.0"
    app_secret_key: str = "development-only-change-me"
    app_base_url: str = "http://127.0.0.1:8000"
    database_url: str = "postgresql+psycopg://aerolink:aerolink@127.0.0.1:5432/aerolink"
    dji_app_id: str | None = None
    dji_app_key: str | None = None
    dji_app_license: str | None = None
    # AL-003/AL-R1: p340 has no inbound TCP path from the public internet
    # (confirmed 2026-08-10 -- neither 443 nor 8883 answer from outside its
    # Tailscale network), so the broker DJI Pilot 2 connects to cannot live
    # on p340. `mqtt_public_host`/`mqtt_tls_port` now name the *external
    # relay's* address -- the one place with a real public IP -- not p340
    # itself. The worker below is a client of that relay, not its server.
    mqtt_public_host: str | None = None
    mqtt_tls_port: int = 8883
    mqtt_tls_cert_file: str | None = None
    mqtt_tls_key_file: str | None = None
    # Credentials the AeroLink worker uses to subscribe to the relay -- a
    # separate identity from whatever DJI Pilot 2 is issued to publish.
    mqtt_worker_client_id: str = "aerolink-worker"
    mqtt_worker_username: str | None = None
    mqtt_worker_password: str | None = None
    # DJI Cloud API's documented Thing Model topic shape
    # (thing/product/{gateway_sn}/...). Kept configurable rather than
    # hardcoded: AL-204 captures real fixtures before this is trusted as
    # exact, and a relay's ACL may namespace it differently.
    mqtt_worker_topic: str = "thing/product/+/#"
    log_level: str = "INFO"
    telemetry_retention_days: int = 90
    evidence_retention_days: int = 1825
    # AL-107 / ADR-0003: the service credential AeroControl presents to read the
    # device inventory. Unset by default and the endpoint fails closed (503),
    # so a deployment that never configures it exposes nothing.
    service_token: str | None = None
    service_token_workspace: str | None = None
    service_token_subject: str = "svc:aerocontrol"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
