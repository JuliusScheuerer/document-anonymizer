"""Anonymization strategy definitions."""

from enum import StrEnum


class AnonymizationStrategy(StrEnum):
    """Available anonymization strategies."""

    REPLACE = "replace"  # Replace with entity type label: [PERSON], [IBAN]
    MASK = "mask"  # Partial masking: DE89 **** **** **** **** 00
    HASH = "hash"  # Deterministic SHA-256 pseudonymization
    FAKE = "fake"  # Realistic German substitute via Faker de_DE
    REDACT = "redact"  # Complete removal


# Default entity type labels for REPLACE strategy
ENTITY_LABELS: dict[str, str] = {
    "PERSON": "[PERSON]",
    "LOCATION": "[ADRESSE]",
    "ORGANIZATION": "[ORGANISATION]",
    "DE_IBAN": "[IBAN]",
    "DE_TAX_ID": "[STEUER-ID]",
    "DE_PHONE": "[TELEFON]",
    "DE_ID_CARD": "[AUSWEISNR]",
    "DE_HANDELSREGISTER": "[HANDELSREG]",
    "DE_ADDRESS": "[ADRESSE]",
    "DE_DATE": "[DATUM]",
    "EMAIL_ADDRESS": "[EMAIL]",
    "PHONE_NUMBER": "[TELEFON]",
    "IBAN_CODE": "[IBAN]",
}
