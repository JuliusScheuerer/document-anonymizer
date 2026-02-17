"""FastAPI dependency injection: engine singletons."""

from functools import lru_cache

from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine

from document_anonymizer.anonymization.engine import create_anonymizer_engine
from document_anonymizer.detection.engine import create_analyzer_engine


@lru_cache(maxsize=1)
def get_analyzer() -> AnalyzerEngine:
    """Get or create the singleton AnalyzerEngine."""
    return create_analyzer_engine()


@lru_cache(maxsize=1)
def get_anonymizer() -> AnonymizerEngine:
    """Get or create the singleton AnonymizerEngine."""
    return create_anonymizer_engine()
