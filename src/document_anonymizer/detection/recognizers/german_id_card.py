"""German ID card (Personalausweis) number recognizer.

Format: LDDDDDDDC where:
- L = letter from restricted set (C,F,G,H,J,K,L,M,N,P,R,T,V,W,X,Y,Z)
- D = digit
- C = check digit (mod 7 algorithm)

The restricted letter set excludes visually ambiguous characters
(B/8, D/0, I/1, O/0, etc.)
"""

from typing import ClassVar

from presidio_analyzer import Pattern, PatternRecognizer

# Restricted alphanumeric: letters that cannot be confused with digits
_VALID_LETTERS = "CFGHJKLMNPRTVWXYZ"

# Pattern: 1 letter + 8 alphanumeric (from restricted set) + 1 check digit
_ID_PATTERN = rf"\b[{_VALID_LETTERS}][{_VALID_LETTERS}0-9]{{8}}\d\b"

_CONTEXT_WORDS = [
    "personalausweis",
    "personalausweisnummer",
    "ausweisnummer",
    "ausweis-nr",
    "ausweis",
    "identitätskarte",
    "ausweisdokument",
    "perso",
]


def _check_digit_valid(id_number: str) -> bool:
    """Validate using the German ID card check digit algorithm.

    Uses weights 7, 3, 1 repeating. Letters are mapped to their
    position values (C=12, F=15, etc. using their ordinal - 55).
    """
    if len(id_number) != 10:
        return False

    weights = [7, 3, 1, 7, 3, 1, 7, 3, 1]
    total = 0

    for i, char in enumerate(id_number[:9]):
        if char.isdigit():
            value = int(char)
        elif char.upper() in _VALID_LETTERS:
            value = ord(char.upper()) - 55  # A=10, B=11, ..., Z=35
        else:
            return False
        total += value * weights[i]

    expected_check = total % 10
    return id_number[9].isdigit() and int(id_number[9]) == expected_check


class GermanIdCardRecognizer(PatternRecognizer):
    """Detects German Personalausweisnummer."""

    ENTITIES: ClassVar[list[str]] = ["DE_ID_CARD"]

    def __init__(self) -> None:
        patterns = [
            Pattern("german_id_card", _ID_PATTERN, 0.3),
        ]
        super().__init__(
            supported_entity="DE_ID_CARD",
            patterns=patterns,
            context=_CONTEXT_WORDS,
            supported_language="de",
        )

    def validate_result(self, pattern_text: str) -> bool:
        return _check_digit_valid(pattern_text.strip())
