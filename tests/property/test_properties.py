"""Property-based tests for recognizers — verify they never crash on arbitrary input."""

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from document_anonymizer.detection.recognizers.german_address import (
    GermanAddressRecognizer,
)
from document_anonymizer.detection.recognizers.german_date import GermanDateRecognizer
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

pytestmark = pytest.mark.property

_RECOGNIZERS = [
    ("DE_IBAN", GermanIbanRecognizer()),
    ("DE_TAX_ID", GermanTaxRecognizer()),
    ("DE_PHONE", GermanPhoneRecognizer()),
    ("DE_ID_CARD", GermanIdCardRecognizer()),
    ("DE_HANDELSREGISTER", GermanHandelsregisterRecognizer()),
    ("DE_ADDRESS", GermanAddressRecognizer()),
    ("DE_DATE", GermanDateRecognizer()),
]

# Strategy: arbitrary unicode text (the kind that could appear in real documents)
_UNICODE_TEXT = st.text(
    alphabet=st.characters(categories=("L", "N", "P", "Z", "S")),
    min_size=0,
    max_size=500,
)


@pytest.mark.parametrize(
    ("entity_type", "recognizer"),
    _RECOGNIZERS,
    ids=[name for name, _ in _RECOGNIZERS],
)
@given(text=_UNICODE_TEXT)
@settings(max_examples=100)
def test_recognizer_never_crashes(
    entity_type: str,
    recognizer: object,
    text: str,
) -> None:
    """All recognizers should handle any unicode input without exceptions."""
    results = recognizer.analyze(text, entities=[entity_type])  # type: ignore[union-attr]
    assert isinstance(results, list)
    for r in results:
        assert 0 <= r.start <= r.end <= len(text)
        assert 0.0 <= r.score <= 1.0
