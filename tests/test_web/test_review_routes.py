"""Tests for review panel route changes: selected_entities, tier display."""

import base64
import json

import fitz
from fastapi.testclient import TestClient

from document_anonymizer.api.app import app

_HTMX_HEADERS = {"HX-Request": "true"}
client = TestClient(app)


class TestDetectFormTiers:
    def test_detect_includes_tier_data(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann, IBAN DE89 3704 0044 0532 0130 00",
                "score_threshold": "0.35",
            },
        )
        assert r.status_code == 200
        assert "data-tier" in r.text
        assert "data-entity-index" in r.text
        assert "entities-data" in r.text

    def test_detect_includes_tier_sections(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann, IBAN DE89 3704 0044 0532 0130 00",
                "score_threshold": "0.35",
            },
        )
        assert r.status_code == 200
        assert "tier-section" in r.text
        assert "select-all-" in r.text

    def test_detect_includes_review_action_bar(self) -> None:
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann",
                "score_threshold": "0.35",
            },
        )
        assert r.status_code == 200
        assert "review-action-bar" in r.text
        assert "selected-entities-input" in r.text

    def test_detect_escapes_script_in_entities_json(self) -> None:
        """Verify </script> in PII text doesn't break JSON data block."""
        r = client.post(
            "/detect",
            headers=_HTMX_HEADERS,
            data={
                "text": "</script><script>alert(1)</script> Max Mustermann",
                "score_threshold": "0.35",
            },
        )
        assert r.status_code == 200
        # The literal </script> should be escaped as <\/script>
        assert "</script><script>" not in r.text.split("entities-data")[1]


class TestAnonymizeWithSelectedEntities:
    def test_anonymize_with_selected_entities(self) -> None:
        text = "Herr Max Mustermann wohnt in Berlin"
        selected = json.dumps(
            [
                {
                    "entity_type": "PERSON",
                    "start": 5,
                    "end": 19,
                    "score": 0.9,
                },
            ]
        )
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": text,
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
                "selected_entities": selected,
            },
        )
        assert r.status_code == 200
        assert "[PERSON]" in r.text
        # Berlin should NOT be anonymized since it wasn't in selected_entities
        assert "Berlin" in r.text

    def test_anonymize_without_selected_entities_redetects(self) -> None:
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann",
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
                "selected_entities": "",
            },
        )
        assert r.status_code == 200
        assert "diff-panel" in r.text

    def test_anonymize_malformed_entities_returns_error(self) -> None:
        """Non-empty but malformed selected_entities should error, not fallback."""
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": "Herr Max Mustermann",
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
                "selected_entities": "{not valid json}",
            },
            cookies={"lang": "de"},
        )
        assert r.status_code == 200
        assert "konnte nicht verarbeitet werden" in r.text

    def test_anonymize_passes_selected_entities_to_template(self) -> None:
        text = "Max Mustermann"
        selected = json.dumps(
            [
                {
                    "entity_type": "PERSON",
                    "start": 0,
                    "end": 14,
                    "score": 0.9,
                },
            ]
        )

        # Create a real PDF so the template renders the PDF redact form
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), text, fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()
        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": text,
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "true",
                "pdf_b64": pdf_b64,
                "selected_entities": selected,
            },
        )
        assert r.status_code == 200
        assert "selected_entities" in r.text

    def test_anonymize_xss_entity_type_returns_error(self) -> None:
        """XSS in entity_type from selected_entities should return error."""
        text = "Max Mustermann is here"
        selected = json.dumps(
            [
                {
                    "entity_type": '"><script>alert(1)</script>',
                    "start": 0,
                    "end": 14,
                    "score": 0.9,
                },
            ]
        )
        r = client.post(
            "/anonymize-form",
            headers=_HTMX_HEADERS,
            data={
                "text": text,
                "strategy": "replace",
                "score_threshold": "0.35",
                "is_pdf": "false",
                "pdf_b64": "",
                "selected_entities": selected,
            },
            cookies={"lang": "de"},
        )
        assert r.status_code == 200
        assert "konnten nicht" in r.text
        assert "<script>" not in r.text


class TestRedactPdfErrorPaths:
    def test_redact_pdf_incomplete_redaction_returns_error(self) -> None:
        """When entity text can't be found in PDF, return error template."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Some unrelated text", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        # Select an entity that doesn't exist in the PDF text
        selected = json.dumps([{"text": "Nonexistent Person Name"}])

        r = client.post(
            "/redact-pdf",
            headers=_HTMX_HEADERS,
            data={
                "pdf_b64": pdf_b64,
                "score_threshold": "0.35",
                "selected_entities": selected,
            },
        )
        assert r.status_code == 422
        # No lang cookie set — default language (de) is used
        assert "Unvollständige Schwärzung" in r.text

    def test_redact_pdf_page_limit_returns_400(self) -> None:
        """Oversized PDF should return 400 error."""
        from document_anonymizer.document.pdf_handler import MAX_PDF_PAGES

        doc = fitz.open()
        for _ in range(MAX_PDF_PAGES + 1):
            doc.new_page()
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        r = client.post(
            "/redact-pdf",
            headers=_HTMX_HEADERS,
            data={
                "pdf_b64": pdf_b64,
                "score_threshold": "0.35",
                "selected_entities": "",
            },
        )
        assert r.status_code == 400
        assert "exceeding the limit" in r.text


class TestRedactPdfWithSelectedEntities:
    def test_redact_pdf_with_selected_entities(self) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Herr Max Mustermann in Berlin", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_b64 = base64.b64encode(pdf_bytes).decode()
        selected = json.dumps(
            [
                {
                    "text": "Max Mustermann",
                    "entity_type": "PERSON",
                    "start": 5,
                    "end": 19,
                    "score": 0.9,
                },
            ]
        )

        r = client.post(
            "/redact-pdf",
            headers=_HTMX_HEADERS,
            data={
                "pdf_b64": pdf_b64,
                "score_threshold": "0.35",
                "selected_entities": selected,
            },
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"

    def test_redact_pdf_without_selected_entities_redetects(self) -> None:
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Herr Max Mustermann", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        r = client.post(
            "/redact-pdf",
            headers=_HTMX_HEADERS,
            data={
                "pdf_b64": pdf_b64,
                "score_threshold": "0.35",
                "selected_entities": "",
            },
        )
        assert r.status_code == 200
        assert r.headers["content-type"] == "application/pdf"

    def test_redact_pdf_malformed_entities_returns_error(self) -> None:
        """Non-empty but malformed selected_entities should error."""
        doc = fitz.open()
        page = doc.new_page()
        page.insert_text((72, 72), "Max Mustermann", fontsize=12)
        pdf_bytes = doc.tobytes()
        doc.close()

        pdf_b64 = base64.b64encode(pdf_bytes).decode()

        r = client.post(
            "/redact-pdf",
            headers=_HTMX_HEADERS,
            data={
                "pdf_b64": pdf_b64,
                "score_threshold": "0.35",
                "selected_entities": "not valid json",
            },
            cookies={"lang": "de"},
        )
        assert r.status_code == 400
        assert "konnte nicht verarbeitet werden" in r.text
