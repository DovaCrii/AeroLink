import logging
import time
import uuid
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from aerolink.config import get_settings
from aerolink.db import engine, get_db
from aerolink.devices_api import router as devices_router
from aerolink.metrics import refresh_ingestion_metrics
from aerolink.observability import configure_logging
from aerolink.pilot2 import diagnostic_page

REQUEST_COUNT = Counter(
    "aerolink_http_requests_total",
    "Total HTTP requests handled by AeroLink.",
    ("method", "path", "status_code"),
)
REQUEST_DURATION = Histogram(
    "aerolink_http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("method", "path"),
)


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(title=settings.app_name, version=settings.app_version)
    logger = logging.getLogger("aerolink.http")

    @app.middleware("http")
    async def observe_requests(request: Request, call_next) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        started_at = time.perf_counter()
        response: Response | None = None
        try:
            response = await call_next(request)
            return response
        except Exception:
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                },
            )
            raise
        finally:
            duration_seconds = time.perf_counter() - started_at
            route = request.scope.get("route")
            path = getattr(route, "path", request.url.path)
            status_code = response.status_code if response is not None else 500
            REQUEST_COUNT.labels(request.method, path, str(status_code)).inc()
            REQUEST_DURATION.labels(request.method, path).observe(duration_seconds)
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": path,
                    "status_code": status_code,
                    "duration_ms": round(duration_seconds * 1000, 2),
                },
            )
            if response is not None:
                response.headers["X-Request-ID"] = request_id

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

    @app.get("/metrics", include_in_schema=False)
    def metrics(session: Annotated[Session, Depends(get_db)]) -> Response:
        """Expose process metrics for a loopback-only Prometheus scraper.

        The ingestion gauges are refreshed here rather than collected
        continuously: they are three cheap aggregates and a scrape is the only
        moment anyone reads them. `get_db` builds the session without touching
        the network, so a database that cannot answer lowers
        `aerolink_ingestion_metrics_available` inside the refresh instead of
        failing the scrape.
        """
        refresh_ingestion_metrics(lambda: session)
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/pilot2/diagnostic", include_in_schema=False)
    def pilot2_diagnostic() -> Response:
        """Render a diagnostic H5 page; the license is verified only in Pilot 2."""
        return diagnostic_page(
            settings.dji_app_id,
            settings.dji_app_key,
            settings.dji_app_license,
        )

    @app.get("/api/v1", tags=["system"])
    def api_index() -> dict[str, str]:
        return {
            "service": "aerolink",
            "version": "v1",
            "scope": "standalone-dji-gateway",
        }

    # AL-107: the AeroControl integration surface. A router rather than another
    # closure here -- it carries auth, a query and an audit write, which is more
    # than main.py should hold.
    app.include_router(devices_router)

    return app


app = create_app()
