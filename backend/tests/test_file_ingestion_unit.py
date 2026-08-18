"""File type detection and upload validation tests."""

import pytest

from app.application.exceptions import InvalidUploadError, UnsupportedFileTypeError, UploadTooLargeError
from app.application.file_type_detection import detect_file_type
from app.application.upload_validation import validate_filename, validate_upload_size
from app.domain.models.file_artifact import FileType
from app.infrastructure.parsers.stub_parser import StubTextParser


def test_detect_file_type_by_extension() -> None:
    result = detect_file_type("notes.txt", "application/octet-stream")
    assert result.file_type == FileType.TEXT
    assert result.detected_by == "extension"


def test_detect_file_type_by_mime_when_extension_missing() -> None:
    result = detect_file_type("notes", "text/plain")
    assert result.file_type == FileType.TEXT
    assert result.detected_by == "mime"


def test_detect_file_type_rejects_unsupported() -> None:
    with pytest.raises(UnsupportedFileTypeError):
        detect_file_type("drawing.dwg", "application/octet-stream")


def test_validate_filename_rejects_path_traversal() -> None:
    with pytest.raises(InvalidUploadError):
        validate_filename("../evil.txt")
    with pytest.raises(InvalidUploadError):
        validate_filename("folder/evil.txt")


def test_validate_upload_size_limit() -> None:
    with pytest.raises(UploadTooLargeError):
        validate_upload_size(b"x" * 11, max_bytes=10)


def test_stub_parser_contract() -> None:
    parser = StubTextParser()
    assert parser.supports(FileType.TEXT, "text/plain")
    result = parser.extract(b"line1\nline2", filename="sample.txt")
    assert result.success is True
    assert result.parser_key == "stub_text"
    assert result.metadata["line_count"] == 2
