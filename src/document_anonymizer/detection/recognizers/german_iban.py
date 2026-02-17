"""German IBAN recognizer with checksum validation."""

from typing import ClassVar

from presidio_analyzer import Pattern, PatternRecognizer

# DE + 2 check digits + 18 digits (bank code + account number)
# Allows optional spaces every 4 characters
_IBAN_PATTERN = r"\bDE\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{2}\b"

_CONTEXT_WORDS = [
    "iban",
    "konto",
    "kontonummer",
    "bankverbindung",
    "überweisen",
    "überweisung",
    "bankkonto",
    "zahlungsverbindung",
]


def _validate_iban_checksum(iban: str) -> bool:
    """Validate German IBAN using ISO 7064 Mod 97-10 checksum."""
    clean = iban.replace(" ", "")
    if len(clean) != 22:
        return False

    # Move first 4 chars to end, convert letters to numbers (A=10, B=11, ...)
    rearranged = clean[4:] + clean[:4]
    numeric = ""
    for ch in rearranged:
        if ch.isdigit():
            numeric += ch
        else:
            numeric += str(ord(ch.upper()) - ord("A") + 10)

    return int(numeric) % 97 == 1


class GermanIbanRecognizer(PatternRecognizer):
    """Detects German IBANs with context boosting and checksum validation."""

    ENTITIES: ClassVar[list[str]] = ["DE_IBAN"]
    DEFAULT_SCORE = 0.5

    def __init__(self) -> None:
        patterns = [
            Pattern(
                "german_iban",
                _IBAN_PATTERN,
                self.DEFAULT_SCORE,
            ),
        ]
        super().__init__(
            supported_entity="DE_IBAN",
            patterns=patterns,
            context=_CONTEXT_WORDS,
            supported_language="de",
        )

    def validate_result(self, pattern_text: str) -> bool:
        """Boost or reject based on IBAN checksum."""
        return _validate_iban_checksum(pattern_text)
