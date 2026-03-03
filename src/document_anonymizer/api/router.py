"""API routes: /api/detect, /api/anonymize, /api/strategies."""

import time

from fastapi import APIRouter, Depends
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from document_anonymizer.anonymization.engine import anonymize_text
from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.api.dependencies import get_analyzer, get_anonymizer
from document_anonymizer.api.schemas import (
    AnonymizeRequest,
    AnonymizeResponse,
    DetectedEntity,
    DetectionRequest,
    DetectionResponse,
    ErrorResponse,
    StrategiesResponse,
    StrategyInfo,
)
from document_anonymizer.audit.logging import get_logger
from document_anonymizer.document.text_handler import detect_pii_in_text

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["anonymization"])

_STRATEGY_DESCRIPTIONS: dict[str, str] = {
    "replace": "Replace with entity type label (e.g., [PERSON])",
    "mask": "Partially mask the value with asterisks",
    "hash": "Replace with SHA-256 hash for pseudonymization",
    "fake": "Replace with realistic German fake data",
    "redact": "Completely remove the detected PII",
}


@router.post(
    "/detect",
    response_model=DetectionResponse,
    summary="Detect PII entities in text",
    responses={500: {"model": ErrorResponse}},
)
async def detect_pii(
    request: DetectionRequest,
    analyzer: AnalyzerEngine = Depends(get_analyzer),  # noqa: B008
) -> DetectionResponse:
    """Detect PII entities in German text using spaCy NER and custom recognizers."""
    start = time.perf_counter()

    results = detect_pii_in_text(
        analyzer,
        request.text,
        language=request.language,
        score_threshold=request.score_threshold,
    )

    entities = [
        DetectedEntity(
            entity_type=r.entity_type,
            start=r.start,
            end=r.end,
            score=round(r.score, 3),
            text=request.text[r.start : r.end],
        )
        for r in results
    ]

    elapsed_ms = (time.perf_counter() - start) * 1000

    # Audit log: entity counts only, never PII content
    logger.info(
        "pii_detection",
        entity_count=len(entities),
        entity_types=[e.entity_type for e in entities],
        processing_time_ms=round(elapsed_ms, 2),
    )

    return DetectionResponse(
        entities=entities,
        entity_count=len(entities),
        processing_time_ms=round(elapsed_ms, 2),
    )


@router.post(
    "/anonymize",
    response_model=AnonymizeResponse,
    summary="Anonymize PII in text",
    responses={500: {"model": ErrorResponse}},
)
async def anonymize(
    request: AnonymizeRequest,
    analyzer: AnalyzerEngine = Depends(get_analyzer),  # noqa: B008
    anonymizer: AnonymizerEngine = Depends(get_anonymizer),  # noqa: B008
) -> AnonymizeResponse:
    """Detect and anonymize PII using the selected strategy."""
    start = time.perf_counter()

    detections = detect_pii_in_text(
        analyzer,
        request.text,
        language=request.language,
        score_threshold=request.score_threshold,
    )

    anonymized = anonymize_text(
        anonymizer,
        request.text,
        detections,
        strategy=request.strategy,
        entity_strategies=request.entity_strategies,
    )

    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "pii_anonymization",
        entity_count=len(detections),
        strategy=request.strategy.value,
        processing_time_ms=round(elapsed_ms, 2),
    )

    return AnonymizeResponse(
        anonymized_text=anonymized,
        entities_found=len(detections),
        strategy=request.strategy.value,
        processing_time_ms=round(elapsed_ms, 2),
    )


@router.get(
    "/strategies",
    response_model=StrategiesResponse,
    summary="List available anonymization strategies",
)
async def list_strategies() -> StrategiesResponse:
    """Return all available anonymization strategies with descriptions."""
    return StrategiesResponse(
        strategies=[
            StrategyInfo(
                name=s.value,
                description=_STRATEGY_DESCRIPTIONS.get(s.value, ""),
            )
            for s in AnonymizationStrategy
        ]
    )
