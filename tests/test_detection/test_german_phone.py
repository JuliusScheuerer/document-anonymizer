"""Tests for German phone number recognizer."""

from document_anonymizer.detection.recognizers.german_phone import (
    GermanPhoneRecognizer,
)

RECOGNIZER = GermanPhoneRecognizer()


class TestGermanPhoneRecognizer:
    """Test German phone number detection."""

    def test_detects_international_format(self) -> None:
        text = "Tel: +49 30 12345678"
        results = RECOGNIZER.analyze(text, entities=["DE_PHONE"])
        assert len(results) >= 1

    def test_detects_domestic_format(self) -> None:
        text = "Telefon: 030 12345678"
        results = RECOGNIZER.analyze(text, entities=["DE_PHONE"])
        assert len(results) >= 1

    def test_detects_mobile_format(self) -> None:
        text = "Mobil: +49 170 1234567"
        results = RECOGNIZER.analyze(text, entities=["DE_PHONE"])
        assert len(results) >= 1

    def test_detects_mobile_domestic(self) -> None:
        text = "Handy: 0170-1234567"
        results = RECOGNIZER.analyze(text, entities=["DE_PHONE"])
        assert len(results) >= 1

    def test_detects_with_area_code_slash(self) -> None:
        text = "Telefonnummer: 089/12345678"
        results = RECOGNIZER.analyze(text, entities=["DE_PHONE"])
        assert len(results) >= 1

    def test_context_boosts_score(self) -> None:
        text_ctx = "Erreichbar unter Telefon: +49 30 12345678"
        text_no_ctx = "Daten: +49 30 12345678"
        results_ctx = RECOGNIZER.analyze(text_ctx, entities=["DE_PHONE"])
        results_no_ctx = RECOGNIZER.analyze(text_no_ctx, entities=["DE_PHONE"])
        assert len(results_ctx) >= 1
        assert len(results_no_ctx) >= 1
        assert results_ctx[0].score >= results_no_ctx[0].score
