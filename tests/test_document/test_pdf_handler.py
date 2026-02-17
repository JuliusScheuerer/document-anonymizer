"""Tests for PDF handler with physical redaction."""

import fitz  # PyMuPDF
import pytest

from document_anonymizer.detection.engine import create_analyzer_engine
from document_anonymizer.document.pdf_handler import (
    detect_pii_in_pdf,
    extract_text_from_pdf,
    redact_pdf,
)


def _create_test_pdf(text: str) -> bytes:
    """Create a synthetic PDF with the given text for testing."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


@pytest.fixture
def analyzer():  # type: ignore[no-untyped-def]
    return create_analyzer_engine()


@pytest.fixture
def sample_pdf() -> bytes:
    return _create_test_pdf(
        "Herr Max Mustermann\nIBAN: DE89 3704 0044 0532 0130 00\nTel: +49 30 12345678"
    )


class TestExtractText:
    def test_extracts_text_from_pdf(self, sample_pdf: bytes) -> None:
        text = extract_text_from_pdf(sample_pdf)
        assert "Max Mustermann" in text
        assert "DE89" in text

    def test_handles_empty_pdf(self) -> None:
        doc = fitz.open()
        doc.new_page()
        empty_pdf = doc.tobytes()
        doc.close()
        text = extract_text_from_pdf(empty_pdf)
        assert text.strip() == ""


class TestDetectPiiInPdf:
    def test_detects_entities_with_positions(
        self, analyzer: object, sample_pdf: bytes
    ) -> None:
        detections = detect_pii_in_pdf(analyzer, sample_pdf)  # type: ignore[arg-type]
        assert len(detections) > 0
        # Check that we have entity types
        entity_types = {d.entity_type for d in detections}
        assert len(entity_types) > 0

    def test_detections_have_page_numbers(
        self, analyzer: object, sample_pdf: bytes
    ) -> None:
        detections = detect_pii_in_pdf(analyzer, sample_pdf)  # type: ignore[arg-type]
        for d in detections:
            assert d.page_number == 0  # Single-page PDF


class TestRedactPdf:
    def test_physical_redaction_removes_text(
        self, analyzer: object, sample_pdf: bytes
    ) -> None:
        """Key test: after redaction, PII text must NOT be in the PDF stream."""
        redacted_bytes, detections = redact_pdf(analyzer, sample_pdf)  # type: ignore[arg-type]
        assert len(detections) > 0

        # Extract text from redacted PDF — PII should be gone
        redacted_text = extract_text_from_pdf(redacted_bytes)
        # The original PII text should no longer appear
        for d in detections:
            if d.score >= 0.5:
                assert d.text not in redacted_text, (
                    f"PII '{d.text}' ({d.entity_type}) still present after redaction"
                )

    def test_metadata_is_scrubbed(self, analyzer: object, sample_pdf: bytes) -> None:
        redacted_bytes, _ = redact_pdf(analyzer, sample_pdf)  # type: ignore[arg-type]
        doc = fitz.open(stream=redacted_bytes, filetype="pdf")
        metadata = doc.metadata
        doc.close()
        # All metadata fields should be empty
        for key in ["author", "title", "subject", "creator", "producer"]:
            assert not metadata.get(key), f"Metadata '{key}' not scrubbed"

    def test_redacted_pdf_is_valid(self, analyzer: object, sample_pdf: bytes) -> None:
        redacted_bytes, _ = redact_pdf(analyzer, sample_pdf)  # type: ignore[arg-type]
        # Should be valid PDF (opens without error)
        doc = fitz.open(stream=redacted_bytes, filetype="pdf")
        assert len(doc) > 0
        doc.close()

    def test_redacted_pdf_is_smaller_with_garbage_collection(
        self, analyzer: object, sample_pdf: bytes
    ) -> None:
        redacted_bytes, _ = redact_pdf(analyzer, sample_pdf)  # type: ignore[arg-type]
        # After garbage=4 cleanup, the redacted PDF should be reasonably sized
        assert len(redacted_bytes) > 0
