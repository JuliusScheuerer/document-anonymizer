"""Tests for health check module."""

from unittest.mock import patch

from document_anonymizer.health import HealthResponse, check_health


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
