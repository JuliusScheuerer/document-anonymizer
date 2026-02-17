"""Tests for the document processor module."""

from unittest.mock import MagicMock, patch

from document_anonymizer.anonymization.strategies import AnonymizationStrategy
from document_anonymizer.document.processor import process_pdf, process_text


class TestProcessText:
    def test_detects_and_anonymizes(self) -> None:
        mock_analyzer = MagicMock()
        mock_anonymizer = MagicMock()

        # Mock detect_pii_in_text to return a fake result
        mock_result = MagicMock()
        mock_result.entity_type = "PERSON"
        mock_result.start = 0
        mock_result.end = 15
        mock_result.score = 0.9

        with (
            patch(
                "document_anonymizer.document.text_handler.detect_pii_in_text",
                return_value=[mock_result],
            ) as mock_detect,
            patch(
                "document_anonymizer.document.text_handler.anonymize_text",
                return_value="[PERSON]",
            ) as mock_anon,
        ):
            text, detections = process_text(
                mock_analyzer,
                mock_anonymizer,
                "Max Mustermann",
                strategy=AnonymizationStrategy.REPLACE,
            )

            mock_detect.assert_called_once()
            mock_anon.assert_called_once()
            assert text == "[PERSON]"
            assert len(detections) == 1

    def test_passes_entity_strategies(self) -> None:
        mock_analyzer = MagicMock()
        mock_anonymizer = MagicMock()

        with (
            patch(
                "document_anonymizer.document.text_handler.detect_pii_in_text",
                return_value=[],
            ),
            patch(
                "document_anonymizer.document.text_handler.anonymize_text",
                return_value="text",
            ) as mock_anon,
        ):
            entity_strats = {"PERSON": AnonymizationStrategy.FAKE}
            process_text(
                mock_analyzer,
                mock_anonymizer,
                "text",
                entity_strategies=entity_strats,
            )
            _, kwargs = mock_anon.call_args
            assert kwargs["entity_strategies"] == entity_strats


class TestProcessPdf:
    def test_delegates_to_redact_pdf(self) -> None:
        mock_analyzer = MagicMock()
        with patch(
            "document_anonymizer.document.processor.redact_pdf",
            return_value=(b"redacted", []),
        ) as mock_redact:
            result_bytes, detections = process_pdf(mock_analyzer, b"fake-pdf")
            mock_redact.assert_called_once_with(
                mock_analyzer,
                b"fake-pdf",
                language="de",
                score_threshold=0.35,
            )
            assert result_bytes == b"redacted"
            assert detections == []
