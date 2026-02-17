"""FastAPI application with security middleware and API routes."""

import importlib.metadata

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from document_anonymizer.api.router import router as api_router
from document_anonymizer.audit.logging import configure_logging
from document_anonymizer.health import HealthResponse, check_health
from document_anonymizer.security.middleware import SecurityHeadersMiddleware
from document_anonymizer.security.rate_limiter import RateLimiterMiddleware
from document_anonymizer.web.routes import web_router

configure_logging()
logger = structlog.get_logger(__name__)

_VERSION = importlib.metadata.version("document-anonymizer")

app = FastAPI(
    title="document-anonymizer",
    description="Privacy-first document anonymization tool with German PII detection",
    version=_VERSION,
    docs_url="/docs",
    redoc_url=None,
    openapi_tags=[
        {
            "name": "anonymization",
            "description": "Detect and anonymize PII in text documents",
        },
        {
            "name": "web",
            "description": "HTMX-powered web interface for interactive anonymization",
        },
    ],
)

# Security middleware (outermost = first to execute)
app.add_middleware(RateLimiterMiddleware, requests_per_window=60, window_seconds=60)
app.add_middleware(SecurityHeadersMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:  # noqa: ARG001
    """Catch unhandled exceptions — log details, return generic 500."""
    logger.exception("unhandled_exception", path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


# API routes
app.include_router(api_router)
app.include_router(web_router)


@app.get("/health")
async def health() -> HealthResponse:
    """Health check endpoint — verifies dependencies are loaded."""
    return check_health()


def mount_static_files() -> None:
    """Mount static files for the web frontend.

    Called separately to avoid import errors when static dir doesn't exist
    (e.g., in test environments).
    """
    from pathlib import Path

    static_dir = Path(__file__).parent.parent / "web" / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


mount_static_files()
