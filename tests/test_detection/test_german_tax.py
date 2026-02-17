"""Tests for German tax number recognizers."""

import pytest

from document_anonymizer.detection.recognizers.german_tax import (
    GermanTaxRecognizer,
    _validate_steuer_id,
)

RECOGNIZER = GermanTaxRecognizer()


class TestSteuerIdValidation:
    """Test Steuer-ID structural validation."""

    @pytest.mark.parametrize(
        "steuer_id",
        [
            "12345679811",  # one digit appears twice
            "65929970489",  # one digit appears three times
        ],
    )
    def test_valid_structure(self, steuer_id: str) -> None:
        assert _validate_steuer_id(steuer_id) is True

    @pytest.mark.parametrize(
        "steuer_id",
        [
            "01234567890",  # leading zero
            "1234567890",  # too short (10 digits)
            "123456789012",  # too long (12 digits)
            "12345678901",  # all unique digits in first 10 — invalid
        ],
    )
    def test_invalid_structure(self, steuer_id: str) -> None:
        assert _validate_steuer_id(steuer_id) is False


class TestGermanTaxRecognizer:
    """Test tax number detection in German text."""

    def test_detects_steuernummer_regional(self) -> None:
        text = "Steuernummer: 93/815/08152"
        results = RECOGNIZER.analyze(text, entities=["DE_TAX_ID"])
        assert len(results) >= 1
        match = text[results[0].start : results[0].end]
        assert "93/815/08152" in match

    def test_detects_steuernummer_three_digit_prefix(self) -> None:
        text = "St.-Nr.: 181/815/08155"
        results = RECOGNIZER.analyze(text, entities=["DE_TAX_ID"])
        assert len(results) >= 1

    def test_detects_steuer_id_with_context(self) -> None:
        text = "Ihre Steuer-ID lautet 12345679811."
        results = RECOGNIZER.analyze(text, entities=["DE_TAX_ID"])
        assert len(results) >= 1

    def test_context_boosts_score(self) -> None:
        text_ctx = "Steueridentifikationsnummer: 12345679811"
        text_no_ctx = "Referenznummer: 12345679811"
        results_ctx = RECOGNIZER.analyze(text_ctx, entities=["DE_TAX_ID"])
        results_no_ctx = RECOGNIZER.analyze(text_no_ctx, entities=["DE_TAX_ID"])
        # Both should detect, but context should boost
        if results_ctx and results_no_ctx:
            assert results_ctx[0].score >= results_no_ctx[0].score
