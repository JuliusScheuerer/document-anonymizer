"""PII detection engine wrapping Presidio with German spaCy NLP."""

from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from document_anonymizer.detection.recognizers import get_german_recognizers


def create_analyzer_engine() -> AnalyzerEngine:
    """Create a Presidio AnalyzerEngine configured for German PII detection.

    Uses spaCy de_core_news_lg for NER (PERSON, ORG, LOC) and registers
    custom regex-based recognizers for German-specific patterns.
    """
    nlp_config = {
        "nlp_engine_name": "spacy",
        "models": [{"lang_code": "de", "model_name": "de_core_news_lg"}],
    }
    nlp_engine = NlpEngineProvider(nlp_configuration=nlp_config).create_engine()

    engine = AnalyzerEngine(
        nlp_engine=nlp_engine,
        supported_languages=["de"],
    )

    for recognizer in get_german_recognizers():
        engine.registry.add_recognizer(recognizer)

    return engine
