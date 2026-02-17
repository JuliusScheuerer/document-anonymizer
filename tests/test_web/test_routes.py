"""Tests for web frontend routes."""

import base64

import fitz
from fastapi.testclient import TestClient

from document_anonymizer.api.app import app

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
            data={"text": "", "score_threshold": "0.35"},
        )
        assert r.status_code == 200
        assert "Bitte Text eingeben" in r.text

    def test_detect_highlights_entities(self) -> None:
        r = client.post(
            "/detect",
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
            data={"score_threshold": "0.35", "text": ""},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert r.status_code == 200


class TestAnonymizeForm:
    def test_anonymize_returns_diff(self) -> None:
        r = client.post(
            "/anonymize-form",
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


class TestRedactPdf:
    def test_redact_pdf_download(self) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Herr Max Mustermann", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        r = client.post(
            "/redact-pdf",
            data={"pdf_b64": pdf_b64, "score_threshold": "0.35"},
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"
        assert r.headers["content-disposition"] == "attachment; filename=redacted.pdf"
        assert r.content[:4] == b"%PDF"

    def test_redact_pdf_rejects_invalid_content(self) -> None:
        """Non-PDF content should return an error, not crash."""
        fake_b64 = base64.b64encode(b"not a pdf").decode()
        r = client.post(
            "/redact-pdf",
            data={"pdf_b64": fake_b64, "score_threshold": "0.35"},
        )
        # Returns 500 with error message (PyMuPDF can't open non-PDF)
        assert r.status_code == 500
        assert "fehlgeschlagen" in r.text.lower()
