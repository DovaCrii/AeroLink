from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed settings with safe development defaults."""

    app_env: str = "dev"
    app_name: str = "AeroLink"
    app_version: str = "0.1.0"
    app_secret_key: str = "development-only-change-me"
    app_base_url: str = "http://127.0.0.1:8000"
    # Prefijo público cuando algo delante nos sirve bajo una ruta y la recorta
    # antes de reenviar. En p340 es `/aerolink`: Tailscale Funnel ya publica
    # AeroControl en `/` del mismo nodo, así que AeroLink entra por
    # `funnel --set-path /aerolink`, que reenvía a `/` local. Sin esto la app
    # responde igual pero genera URLs sin el prefijo, y la H5 de Pilot 2 depende
    # de que su propia URL sea la pública.
    app_root_path: str = ""
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
    # AL-106: the worker is a separate process from the API, so its counters
    # cannot appear on the API's /metrics. It exposes its own, loopback-only in
    # compose. Set to 0 to disable the exposition entirely.
    worker_metrics_port: int = 9100
    log_level: str = "INFO"
    telemetry_retention_days: int = 90
    evidence_retention_days: int = 1825
    # AL-105: where the evidence objects live. Read through the S3 API, so the
    # endpoint is MinIO on p340 today and could be a real bucket without code
    # changes. Unset credentials fail closed: `build_evidence_store` refuses to
    # build a client rather than falling back to an anonymous one.
    object_storage_endpoint: str = "http://127.0.0.1:9000"
    object_storage_bucket: str = "aerolink-evidence"
    object_storage_access_key: str | None = None
    object_storage_secret_key: str | None = None
    object_storage_region: str = "us-east-1"
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
