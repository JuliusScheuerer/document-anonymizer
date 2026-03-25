"""Document processor — type dispatch for text vs PDF."""

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.constants import DEFAULT_SCORE_THRESHOLD
from document_anonymizer.document.pdf_handler import PdfDetection, redact_pdf
from document_anonymizer.document.text_handler import anonymize_plain_text


def process_text(
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
    text: str,
    strategy: AnonymizationStrategy = AnonymizationStrategy.REPLACE,
    entity_strategies: dict[str, AnonymizationStrategy] | None = None,
    language: str = "de",
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> tuple[str, list[RecognizerResult]]:
    """Process plain text: detect and anonymize PII."""
    return anonymize_plain_text(
        analyzer,
        anonymizer,
        text,
        strategy=strategy,
        entity_strategies=entity_strategies,
        language=language,
        score_threshold=score_threshold,
    )


def process_pdf(
    analyzer: AnalyzerEngine,
    pdf_bytes: bytes,
    language: str = "de",
    score_threshold: float = DEFAULT_SCORE_THRESHOLD,
) -> tuple[bytes, list[PdfDetection]]:
    """Process PDF: detect PII and apply physical redaction."""
    return redact_pdf(
        analyzer,
        pdf_bytes,
        language=language,
        score_threshold=score_threshold,
    )
