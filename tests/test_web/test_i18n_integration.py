"""Integration tests for i18n in web routes."""

from fastapi.testclient import TestClient

from document_anonymizer.api.app import app

_HTMX_HEADERS = {"HX-Request": "true"}
client = TestClient(app)


class TestLanguageSwitching:
    def test_default_language_is_german(self) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "Dokument anonymisieren" in r.text

    def test_english_via_query_param(self) -> None:
        r = client.get("/?lang=en")
        assert r.status_code == 200
        assert "Anonymize document" in r.text

    def test_german_via_query_param(self) -> None:
        r = client.get("/?lang=de")
        assert r.status_code == 200
        assert "Dokument anonymisieren" in r.text

    def test_unsupported_lang_falls_back_to_default(self) -> None:
        r = client.get("/?lang=fr")
        assert r.status_code == 200
        assert "Dokument anonymisieren" in r.text

    def test_lang_cookie_set_on_explicit_switch(self) -> None:
        r = client.get("/?lang=en")
        assert "lang" in r.cookies
        assert r.cookies["lang"] == "en"

    def test_unsupported_lang_does_not_set_cookie(self) -> None:
        r = client.get("/?lang=fr")
        assert "lang" not in r.cookies

    def test_cookie_persists_language(self) -> None:
        """After setting lang=en via query param, subsequent requests use English."""
        r = client.get("/", cookies={"lang": "en"})
        assert "Anonymize document" in r.text

    def test_query_param_overrides_cookie(self) -> None:
        """Query param ?lang= should take precedence over cookie."""
        r = client.get("/?lang=en", cookies={"lang": "de"})
        assert "Anonymize document" in r.text
        r = client.get("/?lang=de", cookies={"lang": "en"})
        assert "Dokument anonymisieren" in r.text


class TestEnglishErrorMessages:
    def test_empty_text_error_in_english(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={"text": "", "score_threshold": "0.35"},
            cookies={"lang": "en"},
        )
        assert r.status_code == 200
        assert "Please enter text or upload a file" in r.text

    def test_invalid_strategy_error_in_english(self) -> None:
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": "Max Mustermann",
                "strategy": "nonexistent",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
            },
            cookies={"lang": "en"},
        )
        assert r.status_code == 200
        assert "Unknown strategy" in r.text


class TestTranslationsJsonSecurity:
    def test_translations_json_escapes_script_breakout(self) -> None:
        """The translations_json block must escape </ to prevent </script> XSS."""
        r = client.get("/")
        assert r.status_code == 200
        # translations JSON is in a <script> tag; </ must be escaped
        body = r.text
        assert "window.__translations" in body
        # No literal </ inside the translations JSON block
        parts = body.split("window.__translations")
        if len(parts) > 1:
            segment = parts[1].split("</script>")[0]
            assert "</" not in segment


class TestLanguageSwitcherPresent:
    def test_language_switcher_present(self) -> None:
        r = client.get("/")
        assert "?lang=en" in r.text
        assert "?lang=de" in r.text

    def test_html_lang_attribute_german(self) -> None:
        r = client.get("/")
        assert 'lang="de"' in r.text

    def test_html_lang_attribute_english(self) -> None:
        r = client.get("/?lang=en")
        assert 'lang="en"' in r.text
