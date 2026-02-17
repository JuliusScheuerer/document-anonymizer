"""Integration tests for the anonymization API — full round-trip."""

import pytest
from fastapi.testclient import TestClient

from document_anonymizer.api.app import app

pytestmark = pytest.mark.integration

client = TestClient(app)

# Synthetic German text with multiple PII types
_SAMPLE_TEXT = (
    "Herr Max Mustermann, geboren am 15.03.1985, "
    "wohnhaft in 10115 Berlin, Musterstraße 42. "
    "IBAN: DE89 3704 0044 0532 0130 00. "
    "Steuer-ID: 12345679811. "
    "Tel: +49 30 12345678."
)


class TestDetectEndpoint:
    def test_detect_returns_entities(self) -> None:
        r = client.post("/api/detect", json={"text": _SAMPLE_TEXT})
        assert r.status_code == 200
        data = r.json()
        assert data["entity_count"] > 0
        assert len(data["entities"]) == data["entity_count"]

    def test_detect_entity_fields(self) -> None:
        r = client.post("/api/detect", json={"text": _SAMPLE_TEXT})
        data = r.json()
        for entity in data["entities"]:
            assert "entity_type" in entity
            assert "start" in entity
            assert "end" in entity
            assert "score" in entity
            assert "text" in entity
            assert 0 <= entity["score"] <= 1

    def test_detect_finds_iban(self) -> None:
        r = client.post("/api/detect", json={"text": _SAMPLE_TEXT})
        data = r.json()
        entity_types = {e["entity_type"] for e in data["entities"]}
        assert "DE_IBAN" in entity_types or "IBAN_CODE" in entity_types

    def test_detect_with_high_threshold(self) -> None:
        r = client.post(
            "/api/detect",
            json={"text": _SAMPLE_TEXT, "score_threshold": 0.9},
        )
        data = r.json()
        # With very high threshold, fewer entities
        for entity in data["entities"]:
            assert entity["score"] >= 0.9

    def test_detect_rejects_empty_text(self) -> None:
        r = client.post("/api/detect", json={"text": ""})
        assert r.status_code == 422

    def test_detect_has_processing_time(self) -> None:
        r = client.post("/api/detect", json={"text": _SAMPLE_TEXT})
        data = r.json()
        assert data["processing_time_ms"] > 0


class TestAnonymizeEndpoint:
    def test_anonymize_replace(self) -> None:
        r = client.post(
            "/api/anonymize",
            json={"text": _SAMPLE_TEXT, "strategy": "replace"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["entities_found"] > 0
        assert data["strategy"] == "replace"
        # Original PII should not appear in anonymized text
        assert "DE89 3704 0044 0532 0130 00" not in data["anonymized_text"]

    def test_anonymize_fake(self) -> None:
        r = client.post(
            "/api/anonymize",
            json={"text": _SAMPLE_TEXT, "strategy": "fake"},
        )
        data = r.json()
        assert data["strategy"] == "fake"
        assert "Max Mustermann" not in data["anonymized_text"]

    def test_anonymize_redact(self) -> None:
        r = client.post(
            "/api/anonymize",
            json={"text": _SAMPLE_TEXT, "strategy": "redact"},
        )
        data = r.json()
        assert "Max Mustermann" not in data["anonymized_text"]

    def test_anonymize_roundtrip(self) -> None:
        """Full round-trip: detect then anonymize with same results."""
        # Detect
        r1 = client.post("/api/detect", json={"text": _SAMPLE_TEXT})
        detect_data = r1.json()

        # Anonymize
        r2 = client.post(
            "/api/anonymize",
            json={"text": _SAMPLE_TEXT, "strategy": "replace"},
        )
        anon_data = r2.json()

        # Same number of entities detected
        assert detect_data["entity_count"] == anon_data["entities_found"]


class TestStrategiesEndpoint:
    def test_lists_all_strategies(self) -> None:
        r = client.get("/api/strategies")
        assert r.status_code == 200
        data = r.json()
        names = {s["name"] for s in data["strategies"]}
        assert names == {"replace", "mask", "hash", "fake", "redact"}

    def test_strategies_have_descriptions(self) -> None:
        r = client.get("/api/strategies")
        data = r.json()
        for s in data["strategies"]:
            assert len(s["description"]) > 0


class TestSecurityHeaders:
    def test_csp_header(self) -> None:
        r = client.get("/health")
        assert "Content-Security-Policy" in r.headers
        csp = r.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp

    def test_security_headers_present(self) -> None:
        r = client.get("/health")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert r.headers["Referrer-Policy"] == "no-referrer"
        assert "Strict-Transport-Security" in r.headers

    def test_request_id_header(self) -> None:
        r = client.get("/health")
        assert "X-Request-ID" in r.headers
        # Should be a UUID
        request_id = r.headers["X-Request-ID"]
        assert len(request_id) == 36  # UUID format

    def test_different_request_ids(self) -> None:
        r1 = client.get("/health")
        r2 = client.get("/health")
        assert r1.headers["X-Request-ID"] != r2.headers["X-Request-ID"]
