"""Custom Presidio operators for German PII anonymization."""

from typing import Any

from faker import Faker
from presidio_anonymizer.operators import Operator, OperatorType

_FAKER = Faker("de_DE")


def _fake_steuer_id() -> str:
    """Generate a fake 11-digit Steuer-ID."""
    return _FAKER.numerify("##########" + "#")


def _fake_id_card() -> str:
    """Generate a fake German ID card number (9 alphanumeric chars)."""
    return _FAKER.bothify("?########").upper()


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
