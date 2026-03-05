"""Tests for redact_pdf_with_entities — human-in-the-loop PDF redaction."""

import fitz
import pytest

from document_anonymizer.document.pdf_handler import (
    MAX_PDF_PAGES,
    IncompleteRedactionError,
    PdfPageLimitExceededError,
    extract_text_from_pdf,
    redact_pdf_with_entities,
)


def _create_test_pdf(text: str) -> bytes:
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestRedactPdfWithEntities:
    def test_redacts_selected_entities(self) -> None:
        pdf = _create_test_pdf("Max Mustermann, Berlin")
        entities = [{"text": "Max Mustermann"}]
        redacted_bytes, count = redact_pdf_with_entities(pdf, entities)
        assert count > 0
        text = extract_text_from_pdf(redacted_bytes)
        assert "Max Mustermann" not in text
        assert "Berlin" in text

    def test_empty_entities_scrubs_metadata(self) -> None:
        pdf = _create_test_pdf("Max Mustermann")
        redacted_bytes, count = redact_pdf_with_entities(pdf, [])
        assert count == 0
        doc = fitz.open(stream=redacted_bytes, filetype="pdf")
        for key in ["author", "title", "subject"]:
            assert not doc.metadata.get(key)
        doc.close()

    def test_deduplicates_entity_texts(self) -> None:
        pdf = _create_test_pdf("Max Mustermann")
        entities = [{"text": "Max Mustermann"}, {"text": "Max Mustermann"}]
        redacted_bytes, count = redact_pdf_with_entities(pdf, entities)
        assert count >= 1
        text = extract_text_from_pdf(redacted_bytes)
        assert "Max Mustermann" not in text

    def test_raises_on_missing_entity(self) -> None:
        pdf = _create_test_pdf("Max Mustermann")
        entities = [{"text": "Nonexistent Person"}]
        with pytest.raises(IncompleteRedactionError) as exc_info:
            redact_pdf_with_entities(pdf, entities)
        assert exc_info.value.unredacted_count == 1
        assert exc_info.value.total_count == 1

    def test_metadata_scrubbed(self) -> None:
        pdf = _create_test_pdf("Max Mustermann")
        entities = [{"text": "Max Mustermann"}]
        redacted_bytes, _ = redact_pdf_with_entities(pdf, entities)
        doc = fitz.open(stream=redacted_bytes, filetype="pdf")
        for key in ["author", "title", "subject", "creator", "producer"]:
            assert not doc.metadata.get(key)
        doc.close()

    def test_valid_pdf_output(self) -> None:
        pdf = _create_test_pdf("Max Mustermann, IBAN DE89 3704 0044")
        entities = [{"text": "Max Mustermann"}]
        redacted_bytes, _ = redact_pdf_with_entities(pdf, entities)
        doc = fitz.open(stream=redacted_bytes, filetype="pdf")
        assert len(doc) > 0
        doc.close()

    def test_partial_redaction_mixed_found_and_missing(self) -> None:
        """When some entities are found and others aren't, exception reports counts."""
        pdf = _create_test_pdf("Max Mustermann in Berlin")
        entities = [{"text": "Max Mustermann"}, {"text": "Nonexistent"}]
        with pytest.raises(IncompleteRedactionError) as exc_info:
            redact_pdf_with_entities(pdf, entities)
        assert exc_info.value.unredacted_count == 1
        assert exc_info.value.total_count == 2

    def test_page_limit_enforced(self) -> None:
        """PDFs exceeding MAX_PDF_PAGES should raise PdfPageLimitExceededError."""
        doc = fitz.open()
        for _ in range(MAX_PDF_PAGES + 1):
            doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()

        with pytest.raises(PdfPageLimitExceededError):
            redact_pdf_with_entities(pdf_bytes, [{"text": "test"}])

    def test_empty_text_entities_skipped(self) -> None:
        """Entities with empty text should be skipped."""
        pdf = _create_test_pdf("Max Mustermann")
        entities = [{"text": ""}, {"text": "   "}]  # type: ignore[typeddict-item]
        _, count = redact_pdf_with_entities(pdf, entities)
        assert count == 0
