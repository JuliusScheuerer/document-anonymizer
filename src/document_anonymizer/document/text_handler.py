"""Plain text document handler."""

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

from document_anonymizer.anonymization.engine import anonymize_text
from document_anonymizer.anonymization.strategies import AnonymizationStrategy


def _deduplicate_overlapping(
    results: list[RecognizerResult],
) -> list[RecognizerResult]:
    """Remove overlapping entity detections, keeping the highest-confidence one.

    When Presidio's built-in recognizers and custom German recognizers both
    match the same text span (e.g., IBAN_CODE + DE_IBAN), this keeps only
    the highest-scoring result for each character range.

    Tiebreaker when scores are equal: longer span wins (more specific match).
    """
    if len(results) <= 1:
        return results

    # Sort by score descending, then span length descending (tiebreaker)
    sorted_results = sorted(results, key=lambda r: (-r.score, -(r.end - r.start)))

    accepted: list[RecognizerResult] = []
    for candidate in sorted_results:
        overlaps = any(
            candidate.start < a.end and candidate.end > a.start for a in accepted
        )
        if not overlaps:
            accepted.append(candidate)

    return accepted


def detect_pii_in_text(
    engine: AnalyzerEngine,
    text: str,
    language: str = "de",
    score_threshold: float = 0.35,
) -> list[RecognizerResult]:
    """Detect PII entities in plain text.

    Args:
        engine: Presidio AnalyzerEngine.
        text: Input text to scan.
        language: Text language code.
        score_threshold: Minimum confidence score.

    Returns:
        Deduplicated list of detected PII entities above the score threshold.
    """
    results = engine.analyze(text=text, language=language)
    filtered = [r for r in results if r.score >= score_threshold]
    return _deduplicate_overlapping(filtered)


def anonymize_plain_text(
    analyzer: AnalyzerEngine,
    anonymizer: AnonymizerEngine,
    text: str,
    strategy: AnonymizationStrategy = AnonymizationStrategy.REPLACE,
    entity_strategies: dict[str, AnonymizationStrategy] | None = None,
    language: str = "de",
    score_threshold: float = 0.35,
) -> tuple[str, list[RecognizerResult]]:
    """Detect and anonymize PII in plain text.

    Returns:
        Tuple of (anonymized_text, detected_entities).
    """
    detections = detect_pii_in_text(
        analyzer, text, language=language, score_threshold=score_threshold
    )
    anonymized = anonymize_text(
        anonymizer,
        text,
        detections,
        strategy=strategy,
        entity_strategies=entity_strategies,
    )
    return anonymized, detections
