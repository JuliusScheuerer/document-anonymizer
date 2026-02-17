"""Shared test fixtures."""

import pytest
from fastapi.testclient import TestClient

from document_anonymizer.api.app import app


@pytest.fixture
def client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)
