"""Tests for the text handler module."""

from unittest.mock import MagicMock, patch

from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.document.text_handler import (
    anonymize_plain_text,
    detect_pii_in_text,
)


class TestDetectPiiInText:
    def test_filters_by_score_threshold(self) -> None:
        mock_analyzer = MagicMock()
        low_score = MagicMock(score=0.2, entity_type="PERSON", start=0, end=5)
        high_score = MagicMock(score=0.8, entity_type="PERSON", start=0, end=5)
        mock_analyzer.analyze.return_value = [low_score, high_score]

        results = detect_pii_in_text(mock_analyzer, "test", score_threshold=0.5)
        assert len(results) == 1
        assert results[0].score == 0.8

    def test_default_threshold(self) -> None:
        mock_analyzer = MagicMock()
        low = MagicMock(score=0.1, entity_type="X", start=0, end=1)
        mid = MagicMock(score=0.35, entity_type="X", start=0, end=1)
        mock_analyzer.analyze.return_value = [low, mid]

        results = detect_pii_in_text(mock_analyzer, "test")
        assert len(results) == 1
        assert results[0].score == 0.35


class TestAnonymizePlainText:
    def test_returns_tuple(self) -> None:
        mock_analyzer = MagicMock()
        mock_anonymizer = MagicMock()

        mock_result = MagicMock(score=0.9, entity_type="PERSON", start=0, end=4)
        mock_analyzer.analyze.return_value = [mock_result]

        with patch(
            "document_anonymizer.document.text_handler.anonymize_text",
            return_value="[PERSON]",
        ):
            text, detections = anonymize_plain_text(
                mock_analyzer,
                mock_anonymizer,
                "test",
                strategy=AnonymizationStrategy.REPLACE,
            )
            assert text == "[PERSON]"
            assert len(detections) == 1

    def test_passes_entity_strategies(self) -> None:
        mock_analyzer = MagicMock()
        mock_anonymizer = MagicMock()
        mock_analyzer.analyze.return_value = []

        with patch(
            "document_anonymizer.document.text_handler.anonymize_text",
            return_value="text",
        ) as mock_anon:
            entity_strats = {"PERSON": AnonymizationStrategy.MASK}
            anonymize_plain_text(
                mock_analyzer,
                mock_anonymizer,
                "text",
                entity_strategies=entity_strats,
            )
            _, kwargs = mock_anon.call_args
            assert kwargs["entity_strategies"] == entity_strats
