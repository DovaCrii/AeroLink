"""Public, credential-free H5 endpoint for Pilot 2 connectivity testing."""

from fastapi import FastAPI, Response

from aerolink.pilot2 import diagnostic_page

app = FastAPI(
    title="AeroLink Pilot 2 Connectivity Diagnostic",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)


@app.get("/", include_in_schema=False)
def diagnostic() -> Response:
    """Serve a diagnostic H5 page without any runtime DJI credentials."""
    return diagnostic_page()
