"""PDF document handler: extraction, physical redaction, metadata scrubbing.

Uses PyMuPDF (fitz) for physical redaction via add_redact_annot() +
apply_redactions(), which removes text from the PDF content stream.
This is NOT cosmetic overlay — the original text is permanently gone.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, TypedDict

import fitz
import structlog

from document_anonymizer.anonymization.engine import anonymize_text
from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.document.text_handler import detect_pii_in_text

if TYPE_CHECKING:
    from presidio_analyzer import AnalyzerEngine, RecognizerResult

logger = structlog.get_logger(__name__)

# Maximum pages to process (defense against DoS via large PDFs)
MAX_PDF_PAGES = 200


@dataclass
class PdfDetection:
    """A PII detection with its PDF location."""

    entity_type: str
    text: str
    score: float
    page_number: int
    rect: fitz.Rect


class PdfPageLimitExceededError(Exception):
    """Raised when a PDF exceeds the maximum allowed page count."""

    def __init__(self, total_pages: int) -> None:
        self.total_pages = total_pages
        super().__init__(
            f"PDF has {total_pages} pages, exceeding the limit of {MAX_PDF_PAGES}."
        )


class IncompleteRedactionError(Exception):
    """Raised when some detected PII could not be located for redaction."""

    def __init__(self, unredacted_count: int, total_count: int) -> None:
        self.unredacted_count = unredacted_count
        self.total_count = total_count
        super().__init__(
            f"{unredacted_count} of {total_count} detected PII entities "
            f"could not be visually located for redaction. "
            f"Manual review recommended."
        )


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Extract all text from a PDF document.

    Args:
        pdf_bytes: Raw PDF file content.

    Returns:
        Concatenated text from all pages.

    Raises:
        PdfPageLimitExceededError: If the PDF exceeds MAX_PDF_PAGES.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if len(doc) > MAX_PDF_PAGES:
            raise PdfPageLimitExceededError(len(doc))
        return "\n".join(page.get_text() for page in doc)


def detect_pii_in_pdf(
    analyzer: AnalyzerEngine,
    pdf_bytes: bytes,
    language: str = "de",
    score_threshold: float = 0.35,
) -> list[PdfDetection]:
    """Detect PII in a PDF with page and position metadata.

    For each detected entity in the text, finds the corresponding
    bounding rectangles on the PDF pages.

    Raises:
        PdfPageLimitExceededError: If the PDF exceeds MAX_PDF_PAGES.
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if len(doc) > MAX_PDF_PAGES:
            raise PdfPageLimitExceededError(len(doc))

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
                if not rects:
                    logger.warning(
                        "pii_detection_visual_miss",
                        entity_type=result.entity_type,
                        page=page_num,
                        score=round(result.score, 3),
                    )
                    continue
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

    Raises IncompleteRedactionError if any detected PII cannot be
    visually located for redaction.

    Args:
        analyzer: Presidio AnalyzerEngine.
        pdf_bytes: Raw PDF file content.
        language: Text language code.
        score_threshold: Minimum confidence score.

    Returns:
        Tuple of (redacted_pdf_bytes, successfully_redacted_entities).
    """
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if len(doc) > MAX_PDF_PAGES:
            raise PdfPageLimitExceededError(len(doc))

        all_detections: list[PdfDetection] = []
        total_entities = 0
        unredacted_entities = 0

        for page_num, page in enumerate(doc):
            page_text = page.get_text()
            if not page_text.strip():
                continue

            results = detect_pii_in_text(
                analyzer, page_text, language=language, score_threshold=score_threshold
            )

            for result in results:
                total_entities += 1
                pii_text = page_text[result.start : result.end]
                rects = page.search_for(pii_text)

                if not rects:
                    unredacted_entities += 1
                    logger.warning(
                        "pii_redaction_miss",
                        entity_type=result.entity_type,
                        page=page_num,
                        score=round(result.score, 3),
                    )
                    continue

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

        if unredacted_entities > 0:
            raise IncompleteRedactionError(unredacted_entities, total_entities)

    return redacted_bytes, all_detections


class RedactionTarget(TypedDict):
    """A PII entity text to redact from a PDF."""

    text: str


def redact_pdf_with_entities(
    pdf_bytes: bytes,
    entities: list[RedactionTarget],
) -> tuple[bytes, int]:
    """Physically redact pre-selected PII entities from a PDF.

    Unlike redact_pdf(), this does NOT run detection — it takes a list of
    entity texts already confirmed by the user (human-in-the-loop review).

    Args:
        pdf_bytes: Raw PDF file content.
        entities: List of RedactionTarget dicts with a ``text`` key.

    Returns:
        Tuple of (redacted_pdf_bytes, number_of_redactions_applied).

    Raises:
        IncompleteRedactionError: If some entity texts cannot be found
            on any page.
    """
    # Deduplicate entity texts, skip empty strings
    entity_texts = list({e["text"] for e in entities if e["text"].strip()})

    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if len(doc) > MAX_PDF_PAGES:
            raise PdfPageLimitExceededError(len(doc))

        total_redactions = 0
        found_texts: set[str] = set()

        for page in doc:
            for entity_text in entity_texts:
                rects = page.search_for(entity_text)
                if rects:
                    found_texts.add(entity_text)
                for rect in rects:
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    total_redactions += 1

            page.apply_redactions()

        # Scrub document metadata
        doc.set_metadata({})
        redacted_bytes = doc.tobytes(garbage=4, deflate=True)

        missing_texts = set(entity_texts) - found_texts
        if missing_texts:
            logger.warning(
                "redact_with_entities_miss",
                missing_count=len(missing_texts),
                total_count=len(entity_texts),
            )
            raise IncompleteRedactionError(len(missing_texts), len(entity_texts))

    return redacted_bytes, total_redactions


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
