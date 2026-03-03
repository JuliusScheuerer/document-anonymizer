"""Tests for custom Presidio operators (fake data generators)."""

from document_anonymizer.anonymization.operators import _fake_id_card, _fake_steuer_id


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
