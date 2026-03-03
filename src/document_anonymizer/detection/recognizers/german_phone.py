"""German phone number recognizer."""

from typing import ClassVar

from presidio_analyzer import Pattern, PatternRecognizer

# International format: +49 followed by area code and number
_INTL_PATTERN = r"\+49\s?\(?\d{2,4}\)?\s?\d{3,8}(?:[\s-]?\d{1,5})?\b"

# Domestic format: 0 + area code + number (minimum 7 total digits)
_DOMESTIC_PATTERN = r"\b0\d{2,4}[\s/-]?\d{3,8}[\s/-]?\d{1,5}\b"

# Mobile format: +49 1xx or 01xx
_MOBILE_PATTERN = r"(?:\+49\s?|0)1[567]\d[\s/-]?\d{3,4}[\s/-]?\d{3,4}"

_CONTEXT_WORDS = [
    "tel",
    "telefon",
    "telefonnummer",
    "mobil",
    "mobilnummer",
    "handy",
    "handynummer",
    "fax",
    "faxnummer",
    "rufnummer",
    "durchwahl",
    "erreichbar",
    "anrufen",
]


class GermanPhoneRecognizer(PatternRecognizer):
    """Detects German phone numbers in international and domestic formats."""

    ENTITIES: ClassVar[list[str]] = ["DE_PHONE"]

    def __init__(self) -> None:
        patterns = [
            Pattern("german_phone_intl", _INTL_PATTERN, 0.5),
            Pattern("german_phone_domestic", _DOMESTIC_PATTERN, 0.3),
            Pattern("german_phone_mobile", _MOBILE_PATTERN, 0.6),
        ]
        super().__init__(
            supported_entity="DE_PHONE",
            patterns=patterns,
            context=_CONTEXT_WORDS,
            supported_language="de",
        )
