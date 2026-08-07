"""A deliberately minimal public surface for the temporary Pilot 2 H5 test."""

from fastapi import FastAPI, Response

from aerolink.config import get_settings
from aerolink.pilot2 import diagnostic_page

settings = get_settings()
app = FastAPI(
    title="AeroLink Pilot 2 Diagnostic",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/", include_in_schema=False)
def diagnostic() -> Response:
    """Expose only the credential-free H5 diagnostic surface through a tunnel."""
    return diagnostic_page(
        settings.dji_app_id,
        settings.dji_app_key,
        settings.dji_app_license,
    )
