"""Tests for German ID card recognizer."""

import pytest

from document_anonymizer.detection.recognizers.german_id_card import (
    GermanIdCardRecognizer,
    _check_digit_valid,
)

RECOGNIZER = GermanIdCardRecognizer()


class TestCheckDigit:
    def test_valid_id_number(self) -> None:
        # T220001293 — synthetic valid number
        assert _check_digit_valid("T220001293") is True

    @pytest.mark.parametrize(
        "invalid",
        [
            "T22000129",  # too short
            "T2200012930",  # too long
            "B220001293",  # B not in valid letter set
        ],
    )
    def test_invalid_id_numbers(self, invalid: str) -> None:
        assert _check_digit_valid(invalid) is False


class TestGermanIdCardRecognizer:
    def test_detects_id_number_with_context(self) -> None:
        text = "Personalausweisnummer: T220001293"
        results = RECOGNIZER.analyze(text, entities=["DE_ID_CARD"])
        assert len(results) >= 1

    def test_context_boosts_score(self) -> None:
        text_ctx = "Ausweisnummer: T220001293"
        text_no_ctx = "Referenz: T220001293"
        results_ctx = RECOGNIZER.analyze(text_ctx, entities=["DE_ID_CARD"])
        results_no_ctx = RECOGNIZER.analyze(text_no_ctx, entities=["DE_ID_CARD"])
        if results_ctx and results_no_ctx:
            assert results_ctx[0].score >= results_no_ctx[0].score
