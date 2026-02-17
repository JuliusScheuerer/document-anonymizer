"""Anonymization engine wrapping Presidio with configurable strategies."""

from presidio_analyzer import RecognizerResult
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

from document_anonymizer.anonymization.operators import FakeOperator
from document_anonymizer.anonymization.strategies import (
    ENTITY_LABELS,
    AnonymizationStrategy,
)


def _build_operator_config(
    strategy: AnonymizationStrategy,
    entity_type: str,
) -> OperatorConfig:
    """Build a Presidio OperatorConfig for the given strategy and entity type."""
    match strategy:
        case AnonymizationStrategy.REPLACE:
            label = ENTITY_LABELS.get(entity_type, f"<{entity_type}>")
            return OperatorConfig("replace", {"new_value": label})
        case AnonymizationStrategy.MASK:
            return OperatorConfig(
                "mask", {"chars_to_mask": 12, "masking_char": "*", "from_end": False}
            )
        case AnonymizationStrategy.HASH:
            return OperatorConfig("hash", {"hash_type": "sha256"})
        case AnonymizationStrategy.FAKE:
            return OperatorConfig("fake", {"entity_type": entity_type})
        case AnonymizationStrategy.REDACT:
            return OperatorConfig("redact")
        case _:
            msg = f"Unknown strategy: {strategy}"
            raise ValueError(msg)


def create_anonymizer_engine() -> AnonymizerEngine:
    """Create a Presidio AnonymizerEngine with custom operators registered."""
    engine = AnonymizerEngine()  # type: ignore[no-untyped-call]
    engine.add_anonymizer(FakeOperator)
    return engine


def anonymize_text(
    engine: AnonymizerEngine,
    text: str,
    analyzer_results: list[RecognizerResult],
    strategy: AnonymizationStrategy = AnonymizationStrategy.REPLACE,
    entity_strategies: dict[str, AnonymizationStrategy] | None = None,
) -> str:
    """Anonymize text using the given strategy.

    Args:
        engine: The Presidio AnonymizerEngine.
        text: Original text containing PII.
        analyzer_results: Detection results from the analyzer.
        strategy: Default strategy for all entity types.
        entity_strategies: Optional per-entity-type strategy overrides.

    Returns:
        Anonymized text.
    """
    entity_strategies = entity_strategies or {}

    # Build operator config per entity type
    operators: dict[str, OperatorConfig] = {}
    seen_types = {r.entity_type for r in analyzer_results}

    for entity_type in seen_types:
        effective_strategy = entity_strategies.get(entity_type, strategy)
        operators[entity_type] = _build_operator_config(effective_strategy, entity_type)

    result = engine.anonymize(
        text=text,
        analyzer_results=analyzer_results,  # type: ignore[arg-type]
        operators=operators,
    )
    return result.text
