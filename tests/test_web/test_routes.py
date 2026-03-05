"""Tests for web frontend routes."""

import base64

import fitz
from fastapi.testclient import TestClient

from document_anonymizer.api.app import app

# HTMX sends HX-Request header; our CSRF protection requires it on POSTs
_HTMX_HEADERS = {"HX-Request": "true"}
client = TestClient(app)


class TestIndexPage:
    def test_renders_index(self) -> None:
        r = client.get("/")
        assert r.status_code == 200
        assert "Document Anonymizer" in r.text
        assert "htmx.min.js" in r.text

    def test_has_text_input(self) -> None:
        r = client.get("/")
        assert "textarea" in r.text
        assert 'name="text"' in r.text

    def test_has_file_upload(self) -> None:
        r = client.get("/")
        assert 'type="file"' in r.text


class TestDetectForm:
    def test_detect_returns_results(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann, IBAN DE89 3704 0044 0532 0130 00",
                "score_threshold": "0.35",
            },
        )
        assert r.status_code == 200
        assert "entity-badge" in r.text

    def test_detect_empty_text_error(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={"text": "", "score_threshold": "0.35"},
        )
        assert r.status_code == 200
        assert "Bitte Text eingeben" in r.text

    def test_detect_highlights_entities(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={
                "text": "IBAN: DE89 3704 0044 0532 0130 00",
                "score_threshold": "0.35",
            },
        )
        assert "entity-highlight" in r.text

    def test_detect_xss_attempt(self) -> None:
        """Verify XSS in text input is escaped."""
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={
                "text": '<script>alert("xss")</script> Max Mustermann',
                "score_threshold": "0.35",
            },
        )
        assert r.status_code == 200
        assert "<script>" not in r.text
        assert "&lt;script&gt;" in r.text

    def test_detect_with_file_upload(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={"score_threshold": "0.35", "text": ""},
            files={"file": ("test.txt", b"Herr Max Mustermann", "text/plain")},
        )
        assert r.status_code == 200

    def test_detect_pdf_upload(self) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Herr Max Mustermann", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={"score_threshold": "0.35", "text": ""},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert r.status_code == 200


class TestAnonymizeForm:
    def test_anonymize_returns_diff(self) -> None:
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann",
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
            },
        )
        assert r.status_code == 200
        assert "diff-panel" in r.text

    def test_anonymize_all_strategies(self) -> None:
        for strategy in ["replace", "fake", "mask", "hash", "redact"]:
            r = client.post(
                "/anonymize-form",
                headers=_HTMX_HEADERS,
                data={
                    "text": "Max Mustermann",
                    "strategy": strategy,
                    "score_threshold": "0.35",
                    "is_pdf": "false",
                    "pdf_b64": "",
                },
            )
            assert r.status_code == 200

    def test_invalid_strategy_returns_error(self) -> None:
        """Invalid strategy should return error fragment, not 500."""
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
        )
        assert r.status_code == 200
        assert "Unbekannte Strategie" in r.text

    def test_replace_strategy_uses_brackets(self) -> None:
        """Verify that replace strategy uses [PERSON] bracket format."""
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann",
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
            },
        )
        assert r.status_code == 200
        assert "[PERSON]" in r.text
        assert "&lt;PERSON&gt;" not in r.text


def _make_pdf_b64(text: str = "Herr Max Mustermann") -> str:
    """Create a minimal single-page PDF and return its base64 encoding."""
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), text, fontsize=12)
    pdf_bytes = doc.tobytes()
    doc.close()
    return base64.b64encode(pdf_bytes).decode()


class TestRedactPdf:
    def test_redact_pdf_download(self) -> None:
        pdf_b64 = _make_pdf_b64()
        r = client.post(
            "/redact-pdf",
            data={"pdf_b64": pdf_b64, "score_threshold": "0.35"},
            headers=_HTMX_HEADERS,
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["content-disposition"] == "attachment; filename=redacted.pdf"
        assert r.content[:4] == b"%PDF"

    def test_redact_pdf_rejects_without_htmx_header(self) -> None:
        """POST /redact-pdf without HX-Request header should be rejected (CSRF)."""
        pdf_b64 = _make_pdf_b64()
        r = client.post(
            "/redact-pdf",
            data={"pdf_b64": pdf_b64, "score_threshold": "0.35"},
        )
        assert r.status_code == 403

    def test_redact_pdf_rejects_invalid_content(self) -> None:
        """Non-PDF content should return 400, not crash."""
        fake_b64 = base64.b64encode(b"not a pdf").decode()
        r = client.post(
            "/redact-pdf",
            data={"pdf_b64": fake_b64, "score_threshold": "0.35"},
            headers=_HTMX_HEADERS,
        )
        assert r.status_code == 400

    def test_redact_pdf_rejects_malformed_base64(self) -> None:
        """Malformed base64 should return 400 with a clear error message."""
        r = client.post(
            "/redact-pdf",
            data={"pdf_b64": "!!!not-valid-base64!!!", "score_threshold": "0.35"},
            headers=_HTMX_HEADERS,
        )
        assert r.status_code == 400
        assert "PDF-Daten" in r.text


class TestCsrfProtection:
    def test_detect_without_htmx_header_rejected(self) -> None:
        """POST /detect without HX-Request header should be rejected."""
        r = client.post(
            "/detect",
            data={"text": "test", "score_threshold": "0.35"},
        )
        assert r.status_code == 403

    def test_anonymize_without_htmx_header_rejected(self) -> None:
        """POST /anonymize-form without HX-Request header should be rejected."""
        r = client.post(
            "/anonymize-form",
            data={
                "text": "Max Mustermann",
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
            },
        )
        assert r.status_code == 403


class TestSecurityHeaders:
    def test_cache_control_headers(self) -> None:
        """Responses should include anti-caching headers to prevent PII leakage."""
        r = client.get("/")
        assert r.headers["Cache-Control"] == "no-store, no-cache, must-revalidate"
        assert r.headers["Pragma"] == "no-cache"

    def test_security_headers_present(self) -> None:
        """Core security headers should be set on all responses."""
        r = client.get("/")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"
        assert "no-referrer" in r.headers["Referrer-Policy"]

    def test_csp_header_present(self) -> None:
        r = client.get("/")
        csp = r.headers["Content-Security-Policy"]
        assert "default-src 'self'" in csp
        assert "frame-ancestors 'none'" in csp


class TestFormValidation:
    def test_score_threshold_above_max_rejected(self) -> None:
        """score_threshold > 1.0 should be rejected by Pydantic validation."""
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={"text": "Max Mustermann", "score_threshold": "2.0"},
        )
        assert r.status_code == 422

    def test_score_threshold_below_min_rejected(self) -> None:
        """Negative score_threshold should be rejected by Pydantic validation."""
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={"text": "Max Mustermann", "score_threshold": "-0.5"},
        )
        assert r.status_code == 422

    def test_text_exceeding_max_length_rejected(self) -> None:
        """Text exceeding _MAX_TEXT_LENGTH should be rejected."""
        long_text = "A" * 100_001
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={"text": long_text, "score_threshold": "0.35"},
        )
        assert r.status_code == 422


class TestXssDefenseInDepth:
    def test_invalid_strategy_is_escaped(self) -> None:
        """XSS payload in strategy field should be HTML-escaped in the error message.

        html.escape() + Jinja2 auto-escape = double-escaping (defense-in-depth).
        The key assertion: no raw <script> tag in the output.
        """
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": "Max Mustermann",
                "strategy": '<script>alert("xss")</script>',
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
            },
        )
        assert r.status_code == 200
        assert "<script>" not in r.text
