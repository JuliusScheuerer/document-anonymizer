"""E2E tests: PDF upload, redaction, and verification."""

import fitz
import pytest

from document_anonymizer.detection.engine import create_analyzer_engine
from document_anonymizer.document.pdf_handler import (
    extract_text_from_pdf,
    redact_pdf,
)

pytestmark = pytest.mark.e2e


def _create_arbeitsvertrag_pdf() -> bytes:
    """Create a synthetic German employment contract PDF for testing."""
    doc = fitz.open()
    page = doc.new_page()

    text_lines = [
        "ARBEITSVERTRAG",
        "",
        "zwischen",
        "Muster GmbH, HRB 12345, Amtsgericht München",
        "und",
        "Herrn Max Mustermann",
        "geboren am 15.03.1985",
        "wohnhaft in 10115 Berlin, Musterstraße 42",
        "",
        "Steuer-ID: 12345679811",
        "IBAN: DE89 3704 0044 0532 0130 00",
        "Telefon: +49 30 12345678",
        "",
        "Beginn des Arbeitsverhältnisses: 01.04.2024",
    ]

    y = 72
    for line in text_lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 18

    # Set metadata that should be scrubbed
    doc.set_metadata(
        {
            "author": "Max Mustermann",
            "title": "Arbeitsvertrag Mustermann",
            "subject": "Vertraulich",
        }
    )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


class TestPdfRedactionE2E:
    """End-to-end PDF redaction tests with a realistic German document."""

    def test_full_redaction_workflow(self) -> None:
        """Complete workflow: create PDF -> detect -> redact -> verify."""
        analyzer = create_analyzer_engine()
        pdf_bytes = _create_arbeitsvertrag_pdf()

        # Verify original contains PII
        original_text = extract_text_from_pdf(pdf_bytes)
        assert "Max Mustermann" in original_text
        assert "DE89" in original_text

        # Redact
        redacted_bytes, detections = redact_pdf(analyzer, pdf_bytes)

        # Verify detections were found
        assert len(detections) > 0
        detected_types = {d.entity_type for d in detections}
        assert len(detected_types) > 0

        # Verify PII removed from redacted PDF text
        redacted_text = extract_text_from_pdf(redacted_bytes)
        # High-confidence detections should be gone
        for d in detections:
            if d.score >= 0.5 and len(d.text) > 3:
                assert d.text not in redacted_text, (
                    f"PII '{d.text}' ({d.entity_type}, score={d.score:.2f}) "
                    f"still present after redaction"
                )

    def test_metadata_completely_scrubbed(self) -> None:
        """Verify document metadata is removed after redaction."""
        analyzer = create_analyzer_engine()
        pdf_bytes = _create_arbeitsvertrag_pdf()

        # Verify original has metadata
        orig_doc = fitz.open(stream=pdf_bytes, filetype="pdf")
        assert orig_doc.metadata.get("author") == "Max Mustermann"
        orig_doc.close()

        # Redact
        redacted_bytes, _ = redact_pdf(analyzer, pdf_bytes)

        # Verify metadata is gone
        red_doc = fitz.open(stream=redacted_bytes, filetype="pdf")
        for key in ["author", "title", "subject", "creator"]:
            assert not red_doc.metadata.get(key), (
                f"Metadata '{key}' still present: {red_doc.metadata.get(key)}"
            )
        red_doc.close()

    def test_redacted_pdf_is_valid_and_readable(self) -> None:
        """Verify the redacted PDF is structurally valid."""
        analyzer = create_analyzer_engine()
        pdf_bytes = _create_arbeitsvertrag_pdf()
        redacted_bytes, _ = redact_pdf(analyzer, pdf_bytes)

        doc = fitz.open(stream=redacted_bytes, filetype="pdf")
        assert len(doc) == 1
        # Should be able to extract text without errors
        text = doc[0].get_text()
        assert isinstance(text, str)
        doc.close()

    def test_non_pii_text_preserved(self) -> None:
        """Verify that non-PII text is preserved after redaction."""
        analyzer = create_analyzer_engine()
        pdf_bytes = _create_arbeitsvertrag_pdf()
        redacted_bytes, _ = redact_pdf(analyzer, pdf_bytes)

        redacted_text = extract_text_from_pdf(redacted_bytes)
        # Structural text that isn't PII should remain
        assert "zwischen" in redacted_text
        assert "und" in redacted_text
        assert "Steuer-ID:" in redacted_text or "IBAN:" in redacted_text
