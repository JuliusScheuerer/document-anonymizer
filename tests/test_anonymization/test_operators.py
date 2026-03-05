"""Tests for custom Presidio operators (fake data generators)."""

from unittest.mock import patch

import pytest

from document_anonymizer.anonymization.operators import (
    _FAKER_GENERATORS,
    FakeOperator,
    _fake_id_card,
    _fake_steuer_id,
)


class TestFakeSteuerIdGenerator:
    def test_produces_11_digits(self) -> None:
        for _ in range(20):
            result = _fake_steuer_id()
            assert len(result) == 11
            assert result.isdigit()

    def test_no_leading_zero(self) -> None:
        for _ in range(50):
            result = _fake_steuer_id()
            assert result[0] != "0"

    def test_digit_distribution(self) -> None:
        """First 10 digits: one digit appears exactly twice, rest at most once."""
        for _ in range(20):
            result = _fake_steuer_id()
            first_ten = result[:10]
            counts = {}
            for d in first_ten:
                counts[d] = counts.get(d, 0) + 1
            repeated = [d for d, c in counts.items() if c == 2]
            single = [d for d, c in counts.items() if c == 1]
            assert len(repeated) == 1, f"Expected 1 repeated digit, got {counts}"
            assert len(single) == 8, f"Expected 8 unique digits, got {counts}"


class TestFakeIdCardGenerator:
    def test_produces_10_characters(self) -> None:
        for _ in range(20):
            result = _fake_id_card()
            assert len(result) == 10

    def test_starts_with_valid_letter(self) -> None:
        valid_letters = set("CFGHJKLMNPRTVWXYZ")
        for _ in range(20):
            result = _fake_id_card()
            assert result[0] in valid_letters

    def test_check_digit_valid(self) -> None:
        """Verify the check digit is correctly computed."""
        weights = [7, 3, 1, 7, 3, 1, 7, 3, 1]
        for _ in range(20):
            result = _fake_id_card()
            body = result[:9]
            total = 0
            for i, char in enumerate(body):
                value = int(char) if char.isdigit() else ord(char) - 55
                total += value * weights[i]
            expected_check = total % 10
            assert result[9] == str(expected_check)


class TestFakeOperator:
    def test_known_entity_type(self) -> None:
        op = FakeOperator()
        result = op.operate("Max Mustermann", params={"entity_type": "PERSON"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_unknown_entity_type_falls_back_to_name(self) -> None:
        op = FakeOperator()
        result = op.operate("something", params={"entity_type": "UNKNOWN_TYPE"})
        assert isinstance(result, str)
        assert len(result) > 0

    def test_no_params_falls_back_to_name(self) -> None:
        op = FakeOperator()
        result = op.operate("something", params=None)
        assert isinstance(result, str)

    def test_custom_generator_types(self) -> None:
        """Verify callable generators (Steuer-ID, ID card, Handelsregister)."""
        op = FakeOperator()
        for entity_type in ["DE_TAX_ID", "DE_ID_CARD", "DE_HANDELSREGISTER"]:
            result = op.operate("x", params={"entity_type": entity_type})
            assert isinstance(result, str)
            assert len(result) > 0

    def test_invalid_faker_generator_raises_valueerror(self) -> None:
        with patch.dict(_FAKER_GENERATORS, {"TEST_TYPE": "nonexistent_method"}):
            op = FakeOperator()
            with pytest.raises(ValueError, match="does not exist"):
                op.operate("x", params={"entity_type": "TEST_TYPE"})

    def test_operator_metadata(self) -> None:
        op = FakeOperator()
        assert op.operator_name() == "fake"
        op.validate()  # Should not raise
