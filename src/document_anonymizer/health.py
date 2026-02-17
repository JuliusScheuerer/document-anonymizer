"""Health check models and logic."""

import importlib.metadata
from dataclasses import dataclass, field

import structlog

logger = structlog.get_logger(__name__)


def _get_version() -> str:
    """Read version from package metadata."""
    try:
        return importlib.metadata.version("document-anonymizer")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


@dataclass
class HealthResponse:
    """Health check response."""

    status: str = "ok"
    version: str = field(default_factory=_get_version)
    analyzer_ready: bool = False


def check_health() -> HealthResponse:
    """Run health checks against dependencies."""
    response = HealthResponse()

    try:
        from document_anonymizer.api.dependencies import get_analyzer

        get_analyzer()
        response.analyzer_ready = True
    except Exception:
        logger.warning("health_check_failed", component="analyzer")
        response.status = "degraded"

    return response
