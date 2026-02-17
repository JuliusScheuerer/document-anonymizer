"""Plain text document handler."""

from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_anonymizer import AnonymizerEngine

from document_anonymizer.anonymization.engine import anonymize_text
from document_anonymizer.anonymization.strategies import AnonymizationStrategy


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
        List of detected PII entities.
    """
    results = engine.analyze(text=text, language=language)
    return [r for r in results if r.score >= score_threshold]


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
