"""Tests for file validation (magic bytes, size limits)."""

import pytest

from document_anonymizer.security.validation import (
    FileValidationError,
    validate_file_content,
    validate_pdf_structure,
)


class TestValidateFileContent:
    def test_accepts_plain_text(self) -> None:
        content = b"Hello, this is a test file."
        mime = validate_file_content(content)
        assert mime == "text/plain"

    def test_accepts_pdf(self) -> None:
        # Minimal PDF structure
        content = (
            b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog >>\nendobj\n"
            b"xref\n0 1\ntrailer\n<< /Root 1 0 R >>\nstartxref\n9\n%%EOF"
        )
        mime = validate_file_content(content)
        assert mime == "application/pdf"

    def test_rejects_empty_file(self) -> None:
        with pytest.raises(FileValidationError, match="empty"):
            validate_file_content(b"")

    def test_rejects_oversized_file(self) -> None:
        content = b"x" * (10 * 1024 * 1024 + 1)
        with pytest.raises(FileValidationError, match="maximum size"):
            validate_file_content(content)

    def test_rejects_disallowed_mime_type(self) -> None:
        # PNG header
        content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with pytest.raises(FileValidationError, match="not allowed"):
            validate_file_content(content)

    def test_custom_max_size(self) -> None:
        content = b"x" * 200
        with pytest.raises(FileValidationError, match="maximum size"):
            validate_file_content(content, max_size=100)


class TestValidatePdfStructure:
    def test_valid_pdf_structure(self) -> None:
        content = b"%PDF-1.4\nsome content\n%%EOF"
        # Should not raise
        validate_pdf_structure(content)

    def test_rejects_missing_header(self) -> None:
        content = b"Not a PDF\n%%EOF"
        with pytest.raises(FileValidationError, match="missing PDF header"):
            validate_pdf_structure(content)

    def test_rejects_missing_eof(self) -> None:
        content = b"%PDF-1.4\nsome content without eof marker"
        with pytest.raises(FileValidationError, match="missing EOF"):
            validate_pdf_structure(content)
