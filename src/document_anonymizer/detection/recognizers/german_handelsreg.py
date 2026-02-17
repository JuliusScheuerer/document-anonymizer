"""German Handelsregister (commercial register) number recognizer.

Format: HRA/HRB + number, usually with Registergericht context.
Examples: HRB 12345, HRA 98765 B, HRB 86786 (Amtsgericht München)
"""

from typing import ClassVar

from presidio_analyzer import Pattern, PatternRecognizer

_HANDELSREG_PATTERN = r"\bHR[AB]\s?\d{3,6}\s?[A-Z]?\b"

_CONTEXT_WORDS = [
    "handelsregister",
    "handelsregisternummer",
    "registergericht",
    "amtsgericht",
    "registernummer",
    "hr-nummer",
    "eingetragen",
    "eintragung",
    "handelsreg",
]


class GermanHandelsregisterRecognizer(PatternRecognizer):
    """Detects German Handelsregister numbers (HRA/HRB)."""

    ENTITIES: ClassVar[list[str]] = ["DE_HANDELSREGISTER"]

    def __init__(self) -> None:
        patterns = [
            Pattern("german_handelsregister", _HANDELSREG_PATTERN, 0.5),
        ]
        super().__init__(
            supported_entity="DE_HANDELSREGISTER",
            patterns=patterns,
            context=_CONTEXT_WORDS,
            supported_language="de",
        )
