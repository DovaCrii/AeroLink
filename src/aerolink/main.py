from fastapi import FastAPI

from aerolink.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "aerolink", "version": settings.app_version}

    @app.get("/api/v1", tags=["system"])
    def api_index() -> dict[str, str]:
        return {
            "service": "aerolink",
            "version": "v1",
            "scope": "standalone-dji-gateway",
        }

    return app


app = create_app()
