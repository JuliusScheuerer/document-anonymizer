"""Custom Presidio operators for German PII anonymization."""

import random
from typing import Any

from faker import Faker
from presidio_anonymizer.operators import Operator, OperatorType

_FAKER = Faker("de_DE")

_ID_CARD_LETTERS = "CFGHJKLMNPRTVWXYZ"
_ID_CARD_ALPHANUM = _ID_CARD_LETTERS + "0123456789"


def _fake_steuer_id() -> str:
    """Generate a fake 11-digit Steuer-ID with valid structure.

    Rules: no leading zero, exactly one digit appears twice
    in the first 10 positions, all others appear at most once.
    """
    # Pick one digit to repeat (appears twice)
    repeat_digit = str(random.randint(0, 9))  # noqa: S311  # nosec B311
    # Build first 10 digits: 8 unique + 1 repeated
    available = [str(d) for d in range(10) if str(d) != repeat_digit]
    random.shuffle(available)
    digits = [*available[:8], repeat_digit, repeat_digit]
    random.shuffle(digits)
    # Ensure no leading zero
    if digits[0] == "0":
        for i in range(1, len(digits)):
            if digits[i] != "0":
                digits[0], digits[i] = digits[i], digits[0]
                break
    # 11th digit is a check digit placeholder (0-9)
    digits.append(str(random.randint(0, 9)))  # noqa: S311  # nosec B311
    return "".join(digits)


def _fake_id_card() -> str:
    """Generate a fake German ID card number (10 chars) with valid check digit.

    Format: 1 restricted letter + 8 alphanumeric + 1 check digit.
    Uses weights 7, 3, 1 repeating; letters mapped via ord(c) - 55.
    """
    first = random.choice(_ID_CARD_LETTERS)  # noqa: S311  # nosec B311
    middle = "".join(random.choice(_ID_CARD_ALPHANUM) for _ in range(8))  # noqa: S311  # nosec B311
    body = first + middle

    # Compute check digit
    weights = [7, 3, 1, 7, 3, 1, 7, 3, 1]
    total = 0
    for i, char in enumerate(body):
        value = int(char) if char.isdigit() else ord(char) - 55
        total += value * weights[i]
    check = total % 10

    return body + str(check)


def _fake_handelsregister() -> str:
    """Generate a fake Handelsregister entry."""
    prefix = _FAKER.random_element(["HRB", "HRA"])
    number = _FAKER.random_int(min=1000, max=999999)
    return f"{prefix} {number}"


# Map entity types to Faker generator callables
_FAKER_GENERATORS: dict[str, Any] = {
    "PERSON": "name",
    "LOCATION": "city",
    "ORGANIZATION": "company",
    "DE_IBAN": "iban",
    "DE_PHONE": "phone_number",
    "DE_ADDRESS": "address",
    "DE_DATE": "date",
    "DE_TAX_ID": _fake_steuer_id,
    "DE_ID_CARD": _fake_id_card,
    "DE_HANDELSREGISTER": _fake_handelsregister,
    "EMAIL_ADDRESS": "email",
    "PHONE_NUMBER": "phone_number",
    "IBAN_CODE": "iban",
}


class FakeOperator(Operator):
    """Replace PII with realistic German fake data using Faker de_DE locale."""

    def operate(
        self,
        text: str,  # noqa: ARG002
        params: dict[str, Any] | None = None,
    ) -> str:
        """Generate a fake value for the given entity type."""
        params = params or {}
        entity_type = params.get("entity_type", "")
        generator = _FAKER_GENERATORS.get(entity_type)

        if generator is None:
            return str(_FAKER.name())

        # Callable (custom generator function)
        if callable(generator) and not isinstance(generator, str):
            return str(generator())

        # String (Faker method name)
        if hasattr(_FAKER, generator):
            return str(getattr(_FAKER, generator)())

        return str(_FAKER.name())

    def validate(self, params: dict[str, Any] | None = None) -> None:
        """No special validation required."""

    def operator_name(self) -> str:
        return "fake"

    def operator_type(self) -> OperatorType:
        return OperatorType.Anonymize
