"""German tax number recognizers: Steuernummer and Steuer-ID."""

from typing import ClassVar

from presidio_analyzer import Pattern, PatternRecognizer

# Steuer-ID: exactly 11 digits, no leading zero
_STEUER_ID_PATTERN = r"\b[1-9]\d{10}\b"

# Steuernummer: regional format varies, common patterns:
#   FF/BBB/UUUUP  (e.g., 93/815/08152)
#   FFF/BBB/UUUUP (e.g., 181/815/08155)
_STEUERNUMMER_PATTERN = r"\b\d{2,3}/\d{3}/\d{4,5}\b"

_STEUER_ID_CONTEXT = [
    "steuer-id",
    "steueridentifikationsnummer",
    "identifikationsnummer",
    "steuerliche identifikationsnummer",
    "tin",
    "idnr",
]

_STEUERNUMMER_CONTEXT = [
    "steuernummer",
    "st.-nr",
    "st.nr",
    "stnr",
    "steuer-nr",
    "finanzamt",
    "steuererklärung",
]


def _validate_steuer_id(text: str) -> bool:
    """Validate Steuer-ID with basic structural checks.

    The Steuer-ID has exactly 11 digits. One digit appears exactly twice
    or three times; all others appear at most once. The 11th digit is a
    check digit (we validate structural rules only).
    """
    clean = text.strip()
    if len(clean) != 11 or not clean.isdigit():
        return False
    if clean[0] == "0":
        return False

    # Check digit distribution: in first 10 digits, exactly one digit
    # appears 2 or 3 times, no digit appears more than 3 times
    first_ten = clean[:10]
    from collections import Counter

    counts = Counter(first_ten)

    # Must have at most one digit appearing 2-3 times
    multi = sum(1 for c in counts.values() if c >= 2)
    return multi == 1 and max(counts.values()) <= 3


class GermanTaxRecognizer(PatternRecognizer):
    """Detects German Steuernummer and Steuer-ID."""

    ENTITIES: ClassVar[list[str]] = ["DE_TAX_ID"]

    def __init__(self) -> None:
        patterns = [
            Pattern(
                "steuer_id",
                _STEUER_ID_PATTERN,
                0.3,  # Low base — 11 digits are common; context boosts it
            ),
            Pattern(
                "steuernummer",
                _STEUERNUMMER_PATTERN,
                0.4,
            ),
        ]
        super().__init__(
            supported_entity="DE_TAX_ID",
            patterns=patterns,
            context=_STEUER_ID_CONTEXT + _STEUERNUMMER_CONTEXT,
            supported_language="de",
        )

    def validate_result(self, pattern_text: str) -> bool:
        """Additional validation for Steuer-ID format."""
        clean = pattern_text.strip()
        # Steuernummer format (contains /) — accept as-is
        if "/" in clean:
            return True
        # Steuer-ID format — run structural check
        return _validate_steuer_id(clean)
