"""Tests for German IBAN recognizer."""

import pytest

from document_anonymizer.detection.recognizers.german_iban import (
    GermanIbanRecognizer,
    _validate_iban_checksum,
)

RECOGNIZER = GermanIbanRecognizer()


class TestIbanChecksum:
    """Test IBAN checksum validation (ISO 7064 Mod 97-10)."""

    @pytest.mark.parametrize(
        "iban",
        [
            "DE89370400440532013000",
            "DE89 3704 0044 0532 0130 00",
            "DE02120300000000202051",
            "DE02 1203 0000 0000 2020 51",
        ],
    )
    def test_valid_ibans(self, iban: str) -> None:
        assert _validate_iban_checksum(iban) is True

    @pytest.mark.parametrize(
        "iban",
        [
            "DE00370400440532013000",
            "DE89370400440532013001",
            "DE123704004405320130",  # too short
            "DE1237040044053201300099",  # too long
        ],
    )
    def test_invalid_ibans(self, iban: str) -> None:
        assert _validate_iban_checksum(iban) is False


class TestGermanIbanRecognizer:
    """Test IBAN detection in German text."""

    def test_detects_iban_with_spaces(self) -> None:
        text = "Meine IBAN ist DE89 3704 0044 0532 0130 00 bitte überweisen."
        results = RECOGNIZER.analyze(text, entities=["DE_IBAN"])
        assert len(results) >= 1
        match = text[results[0].start : results[0].end]
        assert match.replace(" ", "").startswith("DE89")

    def test_detects_iban_without_spaces(self) -> None:
        text = "IBAN: DE89370400440532013000"
        results = RECOGNIZER.analyze(text, entities=["DE_IBAN"])
        assert len(results) >= 1

    def test_context_boosts_score(self) -> None:
        text_with_ctx = "Bankverbindung: DE89 3704 0044 0532 0130 00"
        text_no_ctx = "Code: DE89 3704 0044 0532 0130 00"
        results_ctx = RECOGNIZER.analyze(text_with_ctx, entities=["DE_IBAN"])
        results_no_ctx = RECOGNIZER.analyze(text_no_ctx, entities=["DE_IBAN"])
        assert len(results_ctx) >= 1
        assert len(results_no_ctx) >= 1
        assert results_ctx[0].score >= results_no_ctx[0].score

    def test_rejects_non_german_iban_pattern(self) -> None:
        text = "Die Nummer ist FR7630006000011234567890189"
        results = RECOGNIZER.analyze(text, entities=["DE_IBAN"])
        assert len(results) == 0
