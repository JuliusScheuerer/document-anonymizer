"""PDF document handler: extraction, physical redaction, metadata scrubbing.

Uses PyMuPDF (fitz) for physical redaction via add_redact_annot() +
apply_redactions(), which removes text from the PDF content stream.
This is NOT cosmetic overlay — the original text is permanently gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import fitz

from document_anonymizer.anonymization.engine import anonymize_text
from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.document.text_handler import detect_pii_in_text

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult


@dataclass
class PdfDetection:
    """A PII detection with its PDF location."""

    entity_type: str
    text: str
    score: float
    page_number: int
    rect: fitz.Rect


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF document.

    Args:
        pdf_bytes: Raw PDF file content.

    Returns:
        Concatenated text from all pages.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        pages = []
        for page in doc:
            pages.append(page.get_text())
        return "\n".join(pages)


def detect_pii_in_pdf(
    analyzer: AnalyzerEngine,
    pdf_bytes: bytes,
    language: str = "de",
    score_threshold: float = 0.35,
) -> list[PdfDetection]:
    """Detect PII in a PDF with page and position metadata.

    For each detected entity in the text, finds the corresponding
    bounding rectangles on the PDF pages.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        detections: list[PdfDetection] = []

        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            if not page_text.strip():
                continue

            results = detect_pii_in_text(
                analyzer, page_text, language=language, score_threshold=score_threshold
            )

            for result in results:
                pii_text = page_text[result.start : result.end]
                rects = page.search_for(pii_text)
                for rect in rects:
                    detections.append(
                        PdfDetection(
                            entity_type=result.entity_type,
                            text=pii_text,
                            score=result.score,
                            page_number=page_num,
                            rect=rect,
                        )
                    )

        return detections


def redact_pdf(
    analyzer: AnalyzerEngine,
    pdf_bytes: bytes,
    language: str = "de",
    score_threshold: float = 0.35,
) -> tuple[bytes, list[PdfDetection]]:
    """Physically redact PII from a PDF document.

    Uses PyMuPDF's add_redact_annot() + apply_redactions() which removes
    text from the content stream. Also scrubs document metadata.

    Args:
        analyzer: Presidio AnalyzerEngine.
        pdf_bytes: Raw PDF file content.
        language: Text language code.
        score_threshold: Minimum confidence score.

    Returns:
        Tuple of (redacted_pdf_bytes, detected_entities).
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        all_detections: list[PdfDetection] = []

        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            if not page_text.strip():
                continue

            results = detect_pii_in_text(
                analyzer, page_text, language=language, score_threshold=score_threshold
            )

            for result in results:
                pii_text = page_text[result.start : result.end]
                rects = page.search_for(pii_text)

                for rect in rects:
                    all_detections.append(
                        PdfDetection(
                            entity_type=result.entity_type,
                            text=pii_text,
                            score=result.score,
                            page_number=page_num,
                            rect=rect,
                        )
                    )
                    # Physical redaction: mark area for removal
                    page.add_redact_annot(rect, fill=(0, 0, 0))

            # Apply all redactions on this page
            page.apply_redactions()

        # Scrub document metadata
        doc.set_metadata({})

        # Save with garbage collection to remove unreferenced objects
        redacted_bytes = doc.tobytes(garbage=4, deflate=True)

    return redacted_bytes, all_detections


def anonymize_pdf_text(
    analyzer: AnalyzerEngine,
    anonymizer: object,
    pdf_bytes: bytes,
    strategy: AnonymizationStrategy = AnonymizationStrategy.REPLACE,
    language: str = "de",
    score_threshold: float = 0.35,
) -> tuple[str, list[RecognizerResult]]:
    """Extract text from PDF, detect and anonymize PII.

    Returns anonymized text (not a PDF). For PDF redaction, use redact_pdf().
    """
    text = extract_text_from_pdf(pdf_bytes)
    detections = detect_pii_in_text(
        analyzer, text, language=language, score_threshold=score_threshold
    )
    anonymized = anonymize_text(
        anonymizer,  # type: ignore[arg-type]
        text,
        detections,
        strategy=strategy,
    )
    return anonymized, detections
