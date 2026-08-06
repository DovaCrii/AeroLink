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
    mqtt_public_host: str | None = None
    mqtt_tls_port: int = 8883
    mqtt_tls_cert_file: str | None = None
    mqtt_tls_key_file: str | None = None
    log_level: str = "INFO"
    telemetry_retention_days: int = 90
    evidence_retention_days: int = 1825

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
