"""Pydantic request/response models for the API."""

from pydantic import BaseModel, Field

from document_anonymizer.anonymization.strategies import AnonymizationStrategy

_EXAMPLE_TEXT = (
    "Herr Max Mustermann, geboren am 15.03.1985, "
    "wohnhaft in 10115 Berlin, Musterstraße 42. "
    "IBAN: DE89 3704 0044 0532 0130 00."
)


class DetectionRequest(BaseModel):
    """Request to detect PII in text."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        examples=[_EXAMPLE_TEXT],
    )
    language: str = Field(
        default="de",
        pattern=r"^[a-z]{2}$",
        examples=["de"],
    )
    score_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        examples=[0.35],
    )


class DetectedEntity(BaseModel):
    """A single detected PII entity."""

    entity_type: str = Field(examples=["PERSON"])
    start: int = Field(examples=[5])
    end: int = Field(examples=[20])
    score: float = Field(examples=[0.85])
    text: str = Field(examples=["Max Mustermann"])


class DetectionResponse(BaseModel):
    """Response from PII detection."""

    entities: list[DetectedEntity]
    entity_count: int = Field(examples=[3])
    processing_time_ms: float = Field(examples=[42.5])


class AnonymizeRequest(BaseModel):
    """Request to anonymize text."""

    text: str = Field(
        ...,
        min_length=1,
        max_length=100_000,
        examples=[_EXAMPLE_TEXT],
    )
    language: str = Field(
        default="de",
        pattern=r"^[a-z]{2}$",
        examples=["de"],
    )
    strategy: AnonymizationStrategy = Field(
        default=AnonymizationStrategy.REPLACE,
        examples=["replace"],
    )
    entity_strategies: dict[str, AnonymizationStrategy] | None = Field(
        default=None,
        examples=[{"PERSON": "fake", "DE_IBAN": "mask"}],
    )
    score_threshold: float = Field(
        default=0.35,
        ge=0.0,
        le=1.0,
        examples=[0.35],
    )


class AnonymizeResponse(BaseModel):
    """Response from anonymization."""

    anonymized_text: str = Field(
        examples=["Herr [PERSON], geboren am [DATUM], wohnhaft in [ADRESSE]."],
    )
    entities_found: int = Field(examples=[4])
    strategy: str = Field(examples=["replace"])
    processing_time_ms: float = Field(examples=[55.2])


class StrategyInfo(BaseModel):
    """Information about an anonymization strategy."""

    name: str = Field(examples=["replace"])
    description: str = Field(
        examples=["Replace with entity type label (e.g., [PERSON])"],
    )


class StrategiesResponse(BaseModel):
    """Available anonymization strategies."""

    strategies: list[StrategyInfo]


class ErrorResponse(BaseModel):
    """Error response model for API documentation."""

    detail: str = Field(examples=["Internal server error"])
