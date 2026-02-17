"""Tests for German address recognizer."""

from document_anonymizer.detection.recognizers.german_address import (
    GermanAddressRecognizer,
)

RECOGNIZER = GermanAddressRecognizer()


class TestGermanAddressRecognizer:
    def test_detects_plz_with_context(self) -> None:
        text = "Wohnhaft in 10115 Berlin"
        results = RECOGNIZER.analyze(text, entities=["DE_ADDRESS"])
        assert len(results) >= 1
        # Should detect PLZ
        plz_results = [r for r in results if "10115" in text[r.start : r.end]]
        assert len(plz_results) >= 1

    def test_detects_street_with_strasse(self) -> None:
        text = "Adresse: Musterstraße 42"
        results = RECOGNIZER.analyze(text, entities=["DE_ADDRESS"])
        assert len(results) >= 1

    def test_detects_street_with_weg(self) -> None:
        text = "Anschrift: Birkenweg 7"
        results = RECOGNIZER.analyze(text, entities=["DE_ADDRESS"])
        assert len(results) >= 1

    def test_detects_street_with_allee(self) -> None:
        text = "Wohnung: Lindenallee 15a"
        results = RECOGNIZER.analyze(text, entities=["DE_ADDRESS"])
        assert len(results) >= 1

    def test_plz_range(self) -> None:
        # Valid PLZ range: 01000-99999
        text = "PLZ: 01067"
        results = RECOGNIZER.analyze(text, entities=["DE_ADDRESS"])
        assert len(results) >= 1

    def test_rejects_invalid_plz(self) -> None:
        text = "Die Zahl 00123 ist keine PLZ."
        results = RECOGNIZER.analyze(text, entities=["DE_ADDRESS"])
        # 00xxx should not match (starts with 00)
        plz_matches = [r for r in results if "00123" in text[r.start : r.end]]
        assert len(plz_matches) == 0
