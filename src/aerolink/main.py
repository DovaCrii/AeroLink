from fastapi import FastAPI, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from aerolink.config import get_settings
from aerolink.db import engine


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version=settings.app_version)

    @app.get("/health", tags=["system"])
    def health() -> dict[str, str]:
        """Liveness probe: confirms the API process can answer requests."""
        return {"status": "ok", "service": "aerolink", "version": settings.app_version}

    @app.get("/ready", tags=["system"])
    def readiness() -> dict[str, str]:
        """Readiness probe: confirms the durable store is reachable."""
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError as error:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="database unavailable",
            ) from error

        return {"status": "ready", "dependency": "database"}

    @app.get("/api/v1", tags=["system"])
    def api_index() -> dict[str, str]:
        return {
            "service": "aerolink",
            "version": "v1",
            "scope": "standalone-dji-gateway",
        }

    return app


app = create_app()
