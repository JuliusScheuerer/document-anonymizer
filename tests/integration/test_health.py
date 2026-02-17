"""Integration tests for health endpoint."""

import pytest
from fastapi.testclient import TestClient

from document_anonymizer.api.app import app

pytestmark = pytest.mark.integration


def test_health_endpoint_returns_ok() -> None:
    """Test that the health endpoint returns a valid response."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
