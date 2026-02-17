"""German address recognizer: PLZ + city, street patterns."""

from typing import ClassVar

from presidio_analyzer import Pattern, PatternRecognizer

# German PLZ: exactly 5 digits (01000-99999), often followed by city name
_PLZ_PATTERN = r"\b(?:0[1-9]|[1-9]\d)\d{3}\b"

# Street patterns: common German street suffixes
_STREET_PATTERN = (
    r"\b[A-ZÄÖÜ][a-zäöüß]+(?:straße|str\.|weg|allee|platz|ring|gasse|"
    r"damm|ufer|chaussee|berg|steig|pfad)\s+\d{1,4}\s?[a-zA-Z]?\b"
)

_CONTEXT_WORDS = [
    "adresse",
    "anschrift",
    "wohnhaft",
    "wohnort",
    "straße",
    "postleitzahl",
    "plz",
    "hausnummer",
    "wohnung",
    "wohnanschrift",
]


class GermanAddressRecognizer(PatternRecognizer):
    """Detects German postal codes and street addresses."""

    ENTITIES: ClassVar[list[str]] = ["DE_ADDRESS"]

    def __init__(self) -> None:
        patterns = [
            Pattern("german_plz", _PLZ_PATTERN, 0.2),
            Pattern("german_street", _STREET_PATTERN, 0.6),
        ]
        super().__init__(
            supported_entity="DE_ADDRESS",
            patterns=patterns,
            context=_CONTEXT_WORDS,
            supported_language="de",
        )
