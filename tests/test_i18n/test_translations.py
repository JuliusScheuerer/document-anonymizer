"""Tests for the i18n translation module."""

from typing import get_args
from unittest.mock import patch

from document_anonymizer.i18n import (
    DEFAULT_LANGUAGE,
    SUPPORTED_LANGUAGES,
    Lang,
    get_translations,
    jinja_translate,
    translate,
)


class TestTranslate:
    def test_returns_german_string(self) -> None:
        result = translate("brand.name", lang="de")
        assert result == "Dokument-Anonymisierer"

    def test_returns_english_string(self) -> None:
        result = translate("brand.name", lang="en")
        assert result == "Document Anonymizer"

    def test_missing_key_returns_key(self) -> None:
        result = translate("nonexistent.key", lang="de")
        assert result == "nonexistent.key"

    def test_missing_key_logs_warning(self) -> None:
        with patch("document_anonymizer.i18n.logger") as mock_logger:
            translate("nonexistent.key", lang="de")
            mock_logger.warning.assert_called_once_with(
                "translation_key_missing", key="nonexistent.key", lang="de"
            )

    def test_format_interpolation(self) -> None:
        result = translate("results.entities_found", lang="de", count=5)
        assert "5" in result

    def test_format_error_returns_template(self) -> None:
        """Missing format arg should return the template without interpolation."""
        result = translate("results.entities_found", lang="de", wrong_key="x")
        assert "{count}" in result

    def test_format_error_logs_warning(self) -> None:
        with patch("document_anonymizer.i18n.logger") as mock_logger:
            translate("results.entities_found", lang="de", wrong_key="x")
            mock_logger.warning.assert_called_with(
                "translation_format_error", key="results.entities_found", lang="de"
            )

    def test_unsupported_lang_falls_back_to_default(self) -> None:
        result = translate("brand.name", lang="fr")  # type: ignore[arg-type]
        assert result == translate("brand.name", lang=DEFAULT_LANGUAGE)

    def test_default_lang_is_german(self) -> None:
        assert DEFAULT_LANGUAGE == "de"
        result = translate("brand.name")
        assert result == "Dokument-Anonymisierer"


class TestGetTranslations:
    def test_loads_german(self) -> None:
        data = get_translations("de")
        assert "brand.name" in data

    def test_loads_english(self) -> None:
        data = get_translations("en")
        assert "brand.name" in data

    def test_unsupported_lang_falls_back(self) -> None:
        data = get_translations("fr")
        assert data == get_translations(DEFAULT_LANGUAGE)


class TestJinjaTranslate:
    def test_german_context(self) -> None:
        result = jinja_translate({"lang": "de"}, "brand.name")
        assert result == "Dokument-Anonymisierer"

    def test_english_context(self) -> None:
        result = jinja_translate({"lang": "en"}, "brand.name")
        assert result == "Document Anonymizer"

    def test_unsupported_lang_falls_back(self) -> None:
        result = jinja_translate({"lang": "fr"}, "brand.name")
        assert result == translate("brand.name", lang=DEFAULT_LANGUAGE)

    def test_missing_lang_uses_default(self) -> None:
        result = jinja_translate({}, "brand.name")
        assert result == translate("brand.name", lang=DEFAULT_LANGUAGE)


class TestTranslationFiles:
    def test_de_and_en_have_same_keys(self) -> None:
        de = get_translations("de")
        en = get_translations("en")
        assert set(de.keys()) == set(en.keys()), (
            f"Key mismatch: de_only={set(de) - set(en)}, en_only={set(en) - set(de)}"
        )

    def test_supported_languages_matches_lang_type(self) -> None:
        assert set(get_args(Lang)) == SUPPORTED_LANGUAGES

    def test_all_supported_languages_load(self) -> None:
        for lang in SUPPORTED_LANGUAGES:
            data = get_translations(lang)
            assert len(data) > 0, f"Empty translations for {lang}"
