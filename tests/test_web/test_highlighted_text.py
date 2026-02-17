"""Tests for _build_highlighted_text — edge cases and XSS prevention."""

from document_anonymizer.web.routes import _build_highlighted_text


class TestBuildHighlightedText:
    def test_empty_input(self) -> None:
        result = _build_highlighted_text("", [])
        assert result == ""

    def test_no_entities(self) -> None:
        result = _build_highlighted_text("Hello world", [])
        assert result == "Hello world"

    def test_escapes_non_entity_text(self) -> None:
        result = _build_highlighted_text("<script>alert(1)</script>", [])
        assert "<script>" not in result
        assert "&lt;script&gt;" in result

    def test_xss_in_surrounding_text(self) -> None:
        """Verify XSS payloads around entities are escaped."""
        text = "<img onerror=alert(1)> Max Mustermann <script>alert(2)</script>"
        entities = [
            {
                "entity_type": "PERSON",
                "start": 23,
                "end": 38,
                "score": 0.85,
                "text": "Max Mustermann",
            }
        ]
        result = _build_highlighted_text(text, entities)
        assert "<script>" not in result
        assert "<img" not in result
        assert "&lt;script&gt;" in result
        assert "entity-highlight" in result

    def test_entity_text_is_escaped(self) -> None:
        """Entity text itself should be HTML-escaped inside <mark>."""
        text = "Name: <b>bold</b>"
        entities = [
            {
                "entity_type": "PERSON",
                "start": 6,
                "end": 17,
                "score": 0.9,
                "text": "<b>bold</b>",
            }
        ]
        result = _build_highlighted_text(text, entities)
        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_multiple_entities(self) -> None:
        text = "Max Mustermann und Erika Muster"
        entities = [
            {
                "entity_type": "PERSON",
                "start": 0,
                "end": 14,
                "score": 0.9,
                "text": "Max Mustermann",
            },
            {
                "entity_type": "PERSON",
                "start": 19,
                "end": 31,
                "score": 0.85,
                "text": "Erika Muster",
            },
        ]
        result = _build_highlighted_text(text, entities)
        assert result.count("entity-highlight") == 2
        assert " und " in result
