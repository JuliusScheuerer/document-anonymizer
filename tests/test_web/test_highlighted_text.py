"""Tests for _build_highlighted_text — edge cases and XSS prevention."""

from document_anonymizer.web.routes import (
    _build_highlighted_text,
    _make_entity_highlight,
)


def _ent(
    entity_type: str, start: int, end: int, score: float, text: str, index: int = 0
) -> dict:  # type: ignore[type-arg]
    """Shorthand to build a complete _EntityHighlight dict for tests."""
    return _make_entity_highlight(
        entity_type=entity_type,
        start=start,
        end=end,
        score=score,
        text=text,
        index=index,
    )


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
        entities = [_ent("PERSON", 23, 38, 0.85, "Max Mustermann")]
        result = _build_highlighted_text(text, entities)  # type: ignore[arg-type]
        assert "<script>" not in result
        assert "<img" not in result
        assert "&lt;script&gt;" in result
        assert "entity-highlight" in result

    def test_entity_text_is_escaped(self) -> None:
        """Entity text itself should be HTML-escaped inside <mark>."""
        text = "Name: <b>bold</b>"
        entities = [_ent("PERSON", 6, 17, 0.9, "<b>bold</b>")]
        result = _build_highlighted_text(text, entities)  # type: ignore[arg-type]
        assert "<b>" not in result
        assert "&lt;b&gt;" in result

    def test_multiple_entities(self) -> None:
        text = "Max Mustermann und Erika Muster"
        entities = [
            _ent("PERSON", 0, 14, 0.9, "Max Mustermann", index=0),
            _ent("PERSON", 19, 31, 0.85, "Erika Muster", index=1),
        ]
        result = _build_highlighted_text(text, entities)  # type: ignore[arg-type]
        assert result.count("entity-highlight") == 2
        assert " und " in result

    def test_overlapping_entities_first_wins(self) -> None:
        """When entities overlap, only the first (by start position) is highlighted."""
        text = "Max Mustermann from Berlin"
        entities = [
            _ent("PERSON", 0, 14, 0.9, "Max Mustermann", index=0),
            _ent("PERSON", 4, 14, 0.7, "Mustermann", index=1),
        ]
        result = _build_highlighted_text(text, entities)  # type: ignore[arg-type]
        # Only 1 highlight — the overlapping entity is skipped
        assert result.count("entity-highlight") == 1
        assert "Max Mustermann" in result

    def test_english_tooltip(self) -> None:
        """Verify lang='en' produces English tooltip text."""
        text = "Max Mustermann"
        entities = [_ent("PERSON", 0, 14, 0.85, "Max Mustermann")]
        result = _build_highlighted_text(text, entities, lang="en")  # type: ignore[arg-type]
        assert "Confidence:" in result
        assert "Konfidenz:" not in result

    def test_german_tooltip_default(self) -> None:
        """Default lang produces German tooltip text."""
        text = "Max Mustermann"
        entities = [_ent("PERSON", 0, 14, 0.85, "Max Mustermann")]
        result = _build_highlighted_text(text, entities)  # type: ignore[arg-type]
        assert "Konfidenz:" in result

    def test_adjacent_entities_not_merged(self) -> None:
        """Adjacent (non-overlapping) entities should each get their own highlight."""
        text = "AB"
        entities = [
            _ent("PERSON", 0, 1, 0.9, "A", index=0),
            _ent("LOCATION", 1, 2, 0.8, "B", index=1),
        ]
        result = _build_highlighted_text(text, entities)  # type: ignore[arg-type]
        assert result.count("entity-highlight") == 2
