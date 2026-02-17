"""Tests for document-anonymizer."""

from document_anonymizer import __version__


def test_version() -> None:
    """Test version is set."""
    assert __version__ == "0.1.0"
