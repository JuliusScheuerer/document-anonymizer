"""Tests for German Handelsregister recognizer."""

from document_anonymizer.detection.recognizers.german_handelsreg import (
    GermanHandelsregisterRecognizer,
)

RECOGNIZER = GermanHandelsregisterRecognizer()


class TestGermanHandelsregisterRecognizer:
    def test_detects_hrb(self) -> None:
        text = "Handelsregister: HRB 12345"
        results = RECOGNIZER.analyze(text, entities=["DE_HANDELSREGISTER"])
        assert len(results) >= 1

    def test_detects_hra(self) -> None:
        text = "Registergericht: HRA 98765"
        results = RECOGNIZER.analyze(text, entities=["DE_HANDELSREGISTER"])
        assert len(results) >= 1

    def test_detects_with_suffix(self) -> None:
        text = "Amtsgericht München, HRB 86786 B"
        results = RECOGNIZER.analyze(text, entities=["DE_HANDELSREGISTER"])
        assert len(results) >= 1

    def test_context_boosts_score(self) -> None:
        text_ctx = "Eingetragen beim Amtsgericht unter HRB 12345"
        text_no_ctx = "Code HRB 12345"
        results_ctx = RECOGNIZER.analyze(text_ctx, entities=["DE_HANDELSREGISTER"])
        results_no_ctx = RECOGNIZER.analyze(
            text_no_ctx, entities=["DE_HANDELSREGISTER"]
        )
        assert len(results_ctx) >= 1
        assert len(results_no_ctx) >= 1
        assert results_ctx[0].score >= results_no_ctx[0].score
