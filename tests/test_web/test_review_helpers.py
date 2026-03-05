"""Tests for review panel helpers: tier scoring, grouping, entity reconstruction."""

import json

import pytest

from document_anonymizer.web.routes import (
    _group_entities_by_tier,
    _normalize_line_endings,
    _reconstruct_recognizer_results,
    _reconstruct_selected_entities_for_pdf,
    _score_to_tier,
)


class TestNormalizeLineEndings:
    def test_crlf_to_lf(self) -> None:
        assert _normalize_line_endings("hello\r\nworld") == "hello\nworld"

    def test_lone_cr_to_lf(self) -> None:
        assert _normalize_line_endings("hello\rworld") == "hello\nworld"

    def test_lf_unchanged(self) -> None:
        assert _normalize_line_endings("hello\nworld") == "hello\nworld"

    def test_mixed_endings(self) -> None:
        assert _normalize_line_endings("a\r\nb\rc\n") == "a\nb\nc\n"

    def test_empty_string(self) -> None:
        assert _normalize_line_endings("") == ""

    def test_no_newlines_unchanged(self) -> None:
        assert _normalize_line_endings("no newlines") == "no newlines"

    def test_crlf_does_not_double_replace(self) -> None:
        """Ensure \\r\\n becomes \\n, not \\n\\n (replacement order matters)."""
        result = _normalize_line_endings("a\r\nb")
        assert result == "a\nb"
        assert result.count("\n") == 1


class TestScoreToTier:
    def test_high_threshold(self) -> None:
        assert _score_to_tier(0.7) == "high"

    def test_high_above_threshold(self) -> None:
        assert _score_to_tier(0.95) == "high"

    def test_medium_threshold(self) -> None:
        assert _score_to_tier(0.5) == "medium"

    def test_medium_mid_range(self) -> None:
        assert _score_to_tier(0.65) == "medium"

    def test_low_below_medium(self) -> None:
        assert _score_to_tier(0.49) == "low"

    def test_low_at_minimum(self) -> None:
        assert _score_to_tier(0.35) == "low"


class TestGroupEntitiesByTier:
    def test_groups_by_tier(self) -> None:
        entities = [
            {
                "entity_type": "PERSON",
                "start": 0,
                "end": 5,
                "score": 0.9,
                "text": "Max",
                "index": 0,
                "tier": "high",
            },
            {
                "entity_type": "IBAN",
                "start": 10,
                "end": 20,
                "score": 0.6,
                "text": "DE89",
                "index": 1,
                "tier": "medium",
            },
            {
                "entity_type": "PHONE",
                "start": 25,
                "end": 30,
                "score": 0.4,
                "text": "0170",
                "index": 2,
                "tier": "low",
            },
        ]
        groups = _group_entities_by_tier(entities)  # type: ignore[arg-type]
        assert len(groups["high"]) == 1
        assert len(groups["medium"]) == 1
        assert len(groups["low"]) == 1

    def test_empty_tiers(self) -> None:
        groups = _group_entities_by_tier([])
        assert groups == {"high": [], "medium": [], "low": []}


class TestReconstructRecognizerResults:
    def test_valid_json(self) -> None:
        data = [
            {"entity_type": "PERSON", "start": 0, "end": 14, "score": 0.85},
        ]
        results = _reconstruct_recognizer_results(json.dumps(data), "Max Mustermann")
        assert results is not None
        assert len(results) == 1
        assert results[0].entity_type == "PERSON"
        assert results[0].start == 0
        assert results[0].end == 14

    def test_empty_string_returns_none(self) -> None:
        assert _reconstruct_recognizer_results("", "text") is None

    def test_whitespace_only_returns_none(self) -> None:
        assert _reconstruct_recognizer_results("   ", "text") is None

    def test_invalid_json_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            _reconstruct_recognizer_results("{bad json}", "text")

    def test_non_list_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            _reconstruct_recognizer_results('{"a": 1}', "text")

    def test_out_of_bounds_raises_valueerror(self) -> None:
        data = [
            {"entity_type": "PERSON", "start": 0, "end": 100, "score": 0.9},
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "short")

    def test_negative_start_raises_valueerror(self) -> None:
        data = [
            {"entity_type": "PERSON", "start": -1, "end": 5, "score": 0.9},
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "hello world")

    def test_zero_length_entity_raises_valueerror(self) -> None:
        """Zero-length entity (start == end) should be rejected."""
        data = [
            {"entity_type": "PERSON", "start": 0, "end": 0, "score": 0.9},
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "hello")

    def test_missing_fields_raises_valueerror(self) -> None:
        data = [
            {"entity_type": "PERSON"},  # missing start/end/score
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "hello world")

    def test_non_dict_items_raises_valueerror(self) -> None:
        data = [
            42,
            "string",
            None,
            {"entity_type": "PERSON", "start": 0, "end": 5, "score": 0.9},
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "hello")

    def test_multiple_entities(self) -> None:
        text = "Max Mustermann und Erika Muster"
        data = [
            {"entity_type": "PERSON", "start": 0, "end": 14, "score": 0.9},
            {"entity_type": "PERSON", "start": 19, "end": 31, "score": 0.85},
        ]
        results = _reconstruct_recognizer_results(json.dumps(data), text)
        assert results is not None
        assert len(results) == 2

    def test_exceeding_max_entities_raises_valueerror(self) -> None:
        """Lists exceeding _MAX_SELECTED_ENTITIES should raise ValueError."""
        data = [
            {"entity_type": "PERSON", "start": i, "end": i + 1, "score": 0.9}
            for i in range(501)
        ]
        with pytest.raises(ValueError):
            _reconstruct_recognizer_results(json.dumps(data), "x" * 600)

    def test_xss_entity_type_raises_valueerror(self) -> None:
        """Entity types with special characters should be rejected."""
        data = [
            {
                "entity_type": "<script>alert(1)</script>",
                "start": 0,
                "end": 5,
                "score": 0.9,
            },
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "hello")

    def test_score_above_one_raises_valueerror(self) -> None:
        data = [
            {"entity_type": "PERSON", "start": 0, "end": 5, "score": 1.5},
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "hello")

    def test_score_below_zero_raises_valueerror(self) -> None:
        data = [
            {"entity_type": "PERSON", "start": 0, "end": 5, "score": -0.1},
        ]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_recognizer_results(json.dumps(data), "hello")

    def test_valid_entity_type_formats(self) -> None:
        """Standard Presidio entity types should be accepted."""
        for et in ["PERSON", "DE_IBAN", "PHONE_NUMBER", "DE_TAX_ID"]:
            data = [{"entity_type": et, "start": 0, "end": 5, "score": 0.9}]
            result = _reconstruct_recognizer_results(json.dumps(data), "hello")
            assert result is not None, f"Rejected valid entity_type: {et}"


class TestReconstructSelectedEntitiesForPdf:
    def test_valid_entities(self) -> None:
        data = [{"text": "Max Mustermann"}, {"text": "DE89 3704 0044"}]
        result = _reconstruct_selected_entities_for_pdf(json.dumps(data))
        assert result is not None
        assert len(result) == 2
        assert result[0]["text"] == "Max Mustermann"

    def test_empty_returns_none(self) -> None:
        assert _reconstruct_selected_entities_for_pdf("") is None

    def test_invalid_json_raises_valueerror(self) -> None:
        with pytest.raises(ValueError):
            _reconstruct_selected_entities_for_pdf("not json")

    def test_missing_text_field_raises_valueerror(self) -> None:
        data = [{"entity_type": "PERSON"}]  # no "text" key
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_selected_entities_for_pdf(json.dumps(data))

    def test_exceeding_max_entities_raises_valueerror(self) -> None:
        data = [{"text": f"person{i}"} for i in range(501)]
        with pytest.raises(ValueError):
            _reconstruct_selected_entities_for_pdf(json.dumps(data))

    def test_oversized_text_raises_valueerror(self) -> None:
        """Entity text exceeding 1000 chars should raise ValueError."""
        data = [{"text": "x" * 1001}]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_selected_entities_for_pdf(json.dumps(data))

    def test_empty_text_raises_valueerror(self) -> None:
        """Empty text values should raise ValueError."""
        data = [{"text": ""}, {"text": "   "}]
        with pytest.raises(ValueError, match="konnten nicht"):
            _reconstruct_selected_entities_for_pdf(json.dumps(data))

    def test_non_string_text_coerced(self) -> None:
        data = [{"text": 12345}]
        result = _reconstruct_selected_entities_for_pdf(json.dumps(data))
        assert result is not None
        assert result[0]["text"] == "12345"
