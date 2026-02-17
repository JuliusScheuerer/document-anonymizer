"""Tests for anonymization engine."""

from presidio_analyzer import RecognizerResult

from document_anonymizer.anonymization.engine import (
    anonymize_text,
    create_anonymizer_engine,
)
from document_anonymizer.anonymization.strategies import AnonymizationStrategy

ENGINE = create_anonymizer_engine()


def _make_result(
    entity_type: str, start: int, end: int, score: float = 0.85
) -> RecognizerResult:
    return RecognizerResult(entity_type=entity_type, start=start, end=end, score=score)


class TestReplaceStrategy:
    def test_replaces_person_with_label(self) -> None:
        text = "Herr Max Mustermann ist hier."
        results = [_make_result("PERSON", 5, 20)]
        anon = anonymize_text(ENGINE, text, results, AnonymizationStrategy.REPLACE)
        assert "[PERSON]" in anon
        assert "Max Mustermann" not in anon

    def test_replaces_iban_with_label(self) -> None:
        text = "IBAN: DE89370400440532013000"
        results = [_make_result("DE_IBAN", 6, 28)]
        anon = anonymize_text(ENGINE, text, results, AnonymizationStrategy.REPLACE)
        assert "[IBAN]" in anon
        assert "DE89" not in anon


class TestMaskStrategy:
    def test_masks_text(self) -> None:
        text = "Name: Max Mustermann"
        results = [_make_result("PERSON", 6, 20)]
        anon = anonymize_text(ENGINE, text, results, AnonymizationStrategy.MASK)
        assert "*" in anon
        assert "Max Mustermann" not in anon


class TestHashStrategy:
    def test_replaces_with_hex_hash(self) -> None:
        text = "Name: Max Mustermann"
        results = [_make_result("PERSON", 6, 20)]
        anon = anonymize_text(ENGINE, text, results, AnonymizationStrategy.HASH)
        assert "Max Mustermann" not in anon
        # Hash output should be hex string
        hash_part = anon.replace("Name: ", "")
        assert all(c in "0123456789abcdef" for c in hash_part)

    def test_hash_is_hex_string(self) -> None:
        text = "Name: Max Mustermann"
        results = [_make_result("PERSON", 6, 20)]
        anon = anonymize_text(ENGINE, text, results, AnonymizationStrategy.HASH)
        # SHA-256 hex is 64 chars
        hash_value = anon.replace("Name: ", "")
        assert len(hash_value) == 64


class TestFakeStrategy:
    def test_replaces_with_fake_data(self) -> None:
        text = "Name: Max Mustermann"
        results = [_make_result("PERSON", 6, 20)]
        anon = anonymize_text(ENGINE, text, results, AnonymizationStrategy.FAKE)
        assert "Max Mustermann" not in anon
        assert len(anon) > len("Name: ")


class TestRedactStrategy:
    def test_removes_pii(self) -> None:
        text = "Name: Max Mustermann ist hier."
        results = [_make_result("PERSON", 6, 20)]
        anon = anonymize_text(ENGINE, text, results, AnonymizationStrategy.REDACT)
        assert "Max Mustermann" not in anon
        assert "Name: " in anon


class TestPerEntityStrategy:
    def test_different_strategies_per_entity(self) -> None:
        text = "Herr Max Mustermann, IBAN DE89370400440532013000"
        results = [
            _make_result("PERSON", 5, 20),
            _make_result("DE_IBAN", 26, 48),
        ]
        entity_strategies = {
            "PERSON": AnonymizationStrategy.FAKE,
            "DE_IBAN": AnonymizationStrategy.REPLACE,
        }
        anon = anonymize_text(
            ENGINE,
            text,
            results,
            strategy=AnonymizationStrategy.REPLACE,
            entity_strategies=entity_strategies,
        )
        assert "[IBAN]" in anon
        assert "Max Mustermann" not in anon
        assert "DE89" not in anon
