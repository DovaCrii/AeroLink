import logging
import time
import uuid

from fastapi import FastAPI, HTTPException, Request, Response, status
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from aerolink.config import get_settings
from aerolink.db import engine
from aerolink.observability import configure_logging

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
    def metrics() -> Response:
        """Expose process metrics for a loopback-only Prometheus scraper."""
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.get("/api/v1", tags=["system"])
    def api_index() -> dict[str, str]:
        return {
            "service": "aerolink",
            "version": "v1",
            "scope": "standalone-dji-gateway",
        }

    return app


app = create_app()
