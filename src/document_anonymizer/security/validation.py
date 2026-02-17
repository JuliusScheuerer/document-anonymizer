"""File validation: magic bytes, size limits, MIME type checking."""

import magic

# Allowed MIME types and their extensions
ALLOWED_MIME_TYPES: dict[str, list[str]] = {
    "text/plain": [".txt"],
    "application/pdf": [".pdf"],
}

# Maximum file size: 10 MB
MAX_FILE_SIZE = 10 * 1024 * 1024


class FileValidationError(Exception):
    """Raised when file validation fails."""


def validate_file_content(
    content: bytes,
    filename: str | None = None,  # noqa: ARG001
    max_size: int = MAX_FILE_SIZE,
) -> str:
    """Validate file content using magic bytes (not file extension).

    Args:
        content: Raw file bytes.
        filename: Optional filename for logging (not used for validation).
        max_size: Maximum allowed file size in bytes.

    Returns:
        Detected MIME type string.

    Raises:
        FileValidationError: If file is too large, empty, or has disallowed type.
    """
    if len(content) == 0:
        raise FileValidationError("File is empty")  # noqa: TRY003

    if len(content) > max_size:
        raise FileValidationError(  # noqa: TRY003
            f"File exceeds maximum size of {max_size // (1024 * 1024)} MB"
        )

    detected_mime = magic.from_buffer(content, mime=True)

    if detected_mime not in ALLOWED_MIME_TYPES:
        raise FileValidationError(  # noqa: TRY003
            f"File type '{detected_mime}' is not allowed. "
            f"Allowed types: {', '.join(ALLOWED_MIME_TYPES.keys())}"
        )

    return detected_mime


def validate_pdf_structure(content: bytes) -> None:
    """Basic PDF structure validation.

    Checks that the file starts with the PDF magic bytes
    and contains required PDF markers.

    Raises:
        FileValidationError: If content is not a valid PDF structure.
    """
    if not content.startswith(b"%PDF"):
        raise FileValidationError("Invalid PDF: missing PDF header")  # noqa: TRY003

    if b"%%EOF" not in content[-1024:]:
        raise FileValidationError("Invalid PDF: missing EOF marker")  # noqa: TRY003
