"""Unit tests for API endpoints (not marked as integration)."""

from fastapi.testclient import TestClient

from document_anonymizer.api.app import app

client = TestClient(app)


class TestApiDetect:
    def test_detect_returns_entities(self) -> None:
        r = client.post(
            "/api/detect",
            json={"text": "Herr Max Mustermann, IBAN DE89 3704 0044 0532 0130 00"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["entity_count"] > 0
        assert len(data["entities"]) == data["entity_count"]
        assert data["processing_time_ms"] > 0

    def test_detect_entity_structure(self) -> None:
        r = client.post("/api/detect", json={"text": "Max Mustermann"})
        data = r.json()
        for entity in data["entities"]:
            assert "entity_type" in entity
            assert "start" in entity
            assert "end" in entity
            assert "score" in entity
            assert "text" in entity

    def test_detect_with_custom_threshold(self) -> None:
        r = client.post(
            "/api/detect",
            json={"text": "Max Mustermann", "score_threshold": 0.9},
        )
        assert r.status_code == 200
        data = r.json()
        for entity in data["entities"]:
            assert entity["score"] >= 0.9


class TestApiAnonymize:
    def test_anonymize_replace(self) -> None:
        r = client.post(
            "/api/anonymize",
            json={"text": "Herr Max Mustermann", "strategy": "replace"},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["strategy"] == "replace"
        assert data["entities_found"] > 0
        assert "Max Mustermann" not in data["anonymized_text"]
        assert data["processing_time_ms"] > 0

    def test_anonymize_mask(self) -> None:
        r = client.post(
            "/api/anonymize",
            json={"text": "Max Mustermann", "strategy": "mask"},
        )
        assert r.status_code == 200
        assert "Max Mustermann" not in r.json()["anonymized_text"]

    def test_anonymize_with_entity_strategies(self) -> None:
        r = client.post(
            "/api/anonymize",
            json={
                "text": "Herr Max Mustermann, IBAN DE89 3704 0044 0532 0130 00",
                "strategy": "replace",
                "entity_strategies": {"PERSON": "redact"},
            },
        )
        assert r.status_code == 200


class TestApiStrategies:
    def test_lists_strategies(self) -> None:
        r = client.get("/api/strategies")
        assert r.status_code == 200
        data = r.json()
        names = {s["name"] for s in data["strategies"]}
        assert names == {"replace", "mask", "hash", "fake", "redact"}
