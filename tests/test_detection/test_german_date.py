"""Tests for German date recognizer."""

from document_anonymizer.detection.recognizers.german_date import (
    GermanDateRecognizer,
)

RECOGNIZER = GermanDateRecognizer()


class TestGermanDateRecognizer:
    def test_detects_full_date(self) -> None:
        text = "Geburtsdatum: 15.03.1985"
        results = RECOGNIZER.analyze(text, entities=["DE_DATE"])
        assert len(results) >= 1
        match = text[results[0].start : results[0].end]
        assert match == "15.03.1985"

    def test_detects_short_date(self) -> None:
        text = "geb. am 15.03.85"
        results = RECOGNIZER.analyze(text, entities=["DE_DATE"])
        assert len(results) >= 1

    def test_birth_context_boosts(self) -> None:
        text_birth = "geboren am 15.03.1985"
        text_no_ctx = "Datum 15.03.1985"
        results_birth = RECOGNIZER.analyze(text_birth, entities=["DE_DATE"])
        results_no_ctx = RECOGNIZER.analyze(text_no_ctx, entities=["DE_DATE"])
        assert len(results_birth) >= 1
        assert len(results_no_ctx) >= 1
        assert results_birth[0].score >= results_no_ctx[0].score

    def test_rejects_invalid_month(self) -> None:
        text = "Nummer: 15.13.1985"
        results = RECOGNIZER.analyze(text, entities=["DE_DATE"])
        # Month 13 should not match
        assert len(results) == 0

    def test_rejects_invalid_day(self) -> None:
        text = "Code: 32.01.2000"
        results = RECOGNIZER.analyze(text, entities=["DE_DATE"])
        assert len(results) == 0

    def test_detects_contract_date(self) -> None:
        text = "Eintrittsdatum: 01.04.2024"
        results = RECOGNIZER.analyze(text, entities=["DE_DATE"])
        assert len(results) >= 1
