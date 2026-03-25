"""Shared test fixtures."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from document_anonymizer.api.app import app
from document_anonymizer.security.rate_limiter import RateLimiterMiddleware


def _find_rate_limiter(app_obj: object) -> RateLimiterMiddleware | None:
    """Walk the middleware stack to find the RateLimiterMiddleware instance."""
    current: object | None = getattr(app_obj, "middleware_stack", None)
    while current is not None:
        if isinstance(current, RateLimiterMiddleware):
            return current
        current = getattr(current, "app", None)
    return None


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Clear rate limiter state before each test to prevent 429 cascade."""
    limiter = _find_rate_limiter(app)
    if limiter is not None:
        limiter._requests.clear()


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)
