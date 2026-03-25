"""Tests for the text handler module."""

from unittest.mock import MagicMock, patch

from presidio_analyzer import RecognizerResult

from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.document.text_handler import (
    _deduplicate_overlapping,
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


def _make_result(
    entity_type: str, start: int, end: int, score: float
) -> RecognizerResult:
    """Helper to create a RecognizerResult for tests."""
    return RecognizerResult(entity_type=entity_type, start=start, end=end, score=score)


class TestDeduplicateOverlapping:
    def test_empty_list(self) -> None:
        assert _deduplicate_overlapping([]) == []

    def test_single_result_unchanged(self) -> None:
        result = _make_result("PERSON", 0, 10, 0.9)
        assert _deduplicate_overlapping([result]) == [result]

    def test_exact_overlap_keeps_higher_score(self) -> None:
        """IBAN_CODE (0.4) and DE_IBAN (0.85) on same span → keep DE_IBAN."""
        builtin = _make_result("IBAN_CODE", 10, 32, 0.4)
        custom = _make_result("DE_IBAN", 10, 32, 0.85)
        results = _deduplicate_overlapping([builtin, custom])
        assert len(results) == 1
        assert results[0].entity_type == "DE_IBAN"

    def test_partial_overlap_keeps_higher_score(self) -> None:
        """Two entities that partially overlap — higher score wins."""
        a = _make_result("PERSON", 0, 15, 0.7)
        b = _make_result("LOCATION", 10, 25, 0.9)
        results = _deduplicate_overlapping([a, b])
        assert len(results) == 1
        assert results[0].entity_type == "LOCATION"

    def test_non_overlapping_both_kept(self) -> None:
        """Two entities at different positions are both kept."""
        a = _make_result("PERSON", 0, 10, 0.9)
        b = _make_result("DE_IBAN", 20, 42, 0.85)
        results = _deduplicate_overlapping([a, b])
        assert len(results) == 2

    def test_equal_score_longer_span_wins(self) -> None:
        """Same score on overlapping spans — longer span is preferred."""
        short = _make_result("PHONE_NUMBER", 5, 15, 0.6)
        long = _make_result("DE_PHONE", 5, 20, 0.6)
        results = _deduplicate_overlapping([short, long])
        assert len(results) == 1
        assert results[0].entity_type == "DE_PHONE"

    def test_adjacent_not_overlapping(self) -> None:
        """Entities that touch but don't overlap are both kept."""
        a = _make_result("PERSON", 0, 10, 0.9)
        b = _make_result("LOCATION", 10, 20, 0.8)
        results = _deduplicate_overlapping([a, b])
        assert len(results) == 2

    def test_three_way_overlap(self) -> None:
        """Three overlapping entities — only the highest-scoring survives."""
        a = _make_result("PERSON", 0, 10, 0.5)
        b = _make_result("LOCATION", 2, 12, 0.7)
        c = _make_result("ORG", 5, 15, 0.9)
        results = _deduplicate_overlapping([a, b, c])
        assert len(results) == 1
        assert results[0].entity_type == "ORG"

    def test_phone_dedup_de_phone_vs_phone_number(self) -> None:
        """DE_PHONE vs PHONE_NUMBER on same span — higher score wins."""
        builtin = _make_result("PHONE_NUMBER", 0, 14, 0.4)
        custom = _make_result("DE_PHONE", 0, 14, 0.6)
        results = _deduplicate_overlapping([builtin, custom])
        assert len(results) == 1
        assert results[0].entity_type == "DE_PHONE"

    def test_detect_pii_deduplicates(self) -> None:
        """Integration: detect_pii_in_text returns deduplicated results."""
        mock_analyzer = MagicMock()
        overlap_a = MagicMock(score=0.85, entity_type="DE_IBAN", start=0, end=22)
        overlap_b = MagicMock(score=0.4, entity_type="IBAN_CODE", start=0, end=22)
        separate = MagicMock(score=0.9, entity_type="PERSON", start=30, end=45)
        mock_analyzer.analyze.return_value = [overlap_a, overlap_b, separate]

        results = detect_pii_in_text(mock_analyzer, "test text")
        assert len(results) == 2
        entity_types = {r.entity_type for r in results}
        assert "IBAN_CODE" not in entity_types
        assert "DE_IBAN" in entity_types
        assert "PERSON" in entity_types
