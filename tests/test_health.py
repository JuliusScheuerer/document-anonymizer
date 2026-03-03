"""Tests for health check module."""

import importlib.metadata
from unittest.mock import patch

from fastapi.testclient import TestClient

from document_anonymizer.api.app import app
from document_anonymizer.health import HealthResponse, check_health

client = TestClient(app)


class TestHealthResponse:
    def test_defaults(self) -> None:
        resp = HealthResponse()
        assert resp.status == "ok"
        assert resp.analyzer_ready is False

    def test_version_is_set(self) -> None:
        resp = HealthResponse()
        assert resp.version is not None
        assert len(resp.version) > 0


class TestCheckHealth:
    def test_healthy_when_analyzer_available(self) -> None:
        resp = check_health()
        assert resp.status == "ok"
        assert resp.analyzer_ready is True

    def test_degraded_when_analyzer_fails(self) -> None:
        with patch(
            "document_anonymizer.api.dependencies.get_analyzer",
            side_effect=RuntimeError("model not found"),
        ):
            resp = check_health()
            assert resp.status == "degraded"
            assert resp.analyzer_ready is False

    def test_version_fallback_when_package_not_found(self) -> None:
        with patch(
            "document_anonymizer.health.importlib.metadata.version",
            side_effect=importlib.metadata.PackageNotFoundError,
        ):
            from document_anonymizer.health import _get_version

            assert _get_version() == "unknown"


class TestHealthEndpoint:
    def test_healthy_returns_200(self) -> None:
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "ok"

    def test_degraded_returns_503(self) -> None:
        with patch(
            "document_anonymizer.api.app.check_health",
            return_value=HealthResponse(status="degraded", analyzer_ready=False),
        ):
            r = client.get("/health")
            assert r.status_code == 503
            data = r.json()
            assert data["status"] == "degraded"
            assert data["analyzer_ready"] is False
