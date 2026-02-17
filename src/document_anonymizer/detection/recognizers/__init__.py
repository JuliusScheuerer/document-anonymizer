"""German PII recognizer registry."""

from presidio_analyzer import EntityRecognizer

from document_anonymizer.detection.recognizers.german_address import (
    GermanAddressRecognizer,
)
from document_anonymizer.detection.recognizers.german_date import (
    GermanDateRecognizer,
)
from document_anonymizer.detection.recognizers.german_handelsreg import (
    GermanHandelsregisterRecognizer,
)
from document_anonymizer.detection.recognizers.german_iban import GermanIbanRecognizer
from document_anonymizer.detection.recognizers.german_id_card import (
    GermanIdCardRecognizer,
)
from document_anonymizer.detection.recognizers.german_phone import (
    GermanPhoneRecognizer,
)
from document_anonymizer.detection.recognizers.german_tax import GermanTaxRecognizer


def get_german_recognizers() -> list[EntityRecognizer]:
    """Return all custom German PII recognizers."""
    return [
        GermanIbanRecognizer(),
        GermanTaxRecognizer(),
        GermanPhoneRecognizer(),
        GermanIdCardRecognizer(),
        GermanHandelsregisterRecognizer(),
        GermanAddressRecognizer(),
        GermanDateRecognizer(),
    ]
