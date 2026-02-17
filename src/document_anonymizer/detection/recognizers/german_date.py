"""German date recognizer with birth context boosting.

Detects DD.MM.YYYY dates. Score is boosted when birth-related context
words appear nearby (geboren, geb., Geburtsdatum, etc.).
"""

from typing import ClassVar

from presidio_analyzer import Pattern, PatternRecognizer

# DD.MM.YYYY — standard German date format
_DATE_PATTERN = r"\b(?:0[1-9]|[12]\d|3[01])\.(?:0[1-9]|1[0-2])\.\d{4}\b"

# Also match DD.MM.YY (two-digit year)
_DATE_SHORT_PATTERN = r"\b(?:0[1-9]|[12]\d|3[01])\.(?:0[1-9]|1[0-2])\.\d{2}\b"

_CONTEXT_WORDS = [
    "geboren",
    "geb.",
    "geburtsdatum",
    "geburtstag",
    "geburtsjahr",
    "geboren am",
    "geb. am",
    "datum",
    "eintrittsdatum",
    "austrittsdatum",
    "beginn",
    "vertragsanfang",
]


class GermanDateRecognizer(PatternRecognizer):
    """Detects German dates, with boosted confidence for birth-related dates."""

    ENTITIES: ClassVar[list[str]] = ["DE_DATE"]

    def __init__(self) -> None:
        patterns = [
            Pattern("german_date_full", _DATE_PATTERN, 0.3),
            Pattern("german_date_short", _DATE_SHORT_PATTERN, 0.2),
        ]
        super().__init__(
            supported_entity="DE_DATE",
            patterns=patterns,
            context=_CONTEXT_WORDS,
            supported_language="de",
        )
