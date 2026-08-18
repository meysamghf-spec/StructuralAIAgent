"""Deterministic basic file type detection for M5 uploads."""

from __future__ import annotations

from pathlib import Path

from app.application.exceptions import UnsupportedFileTypeError
from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import FileTypeDetectionResult

_EXTENSION_MAP: dict[str, FileType] = {
    ".txt": FileType.TEXT,
}

_MIME_MAP: dict[str, FileType] = {
    "text/plain": FileType.TEXT,
}


def detect_file_type(filename: str, content_type: str | None) -> FileTypeDetectionResult:
    extension = Path(filename).suffix.lower()
    if extension in _EXTENSION_MAP:
        return FileTypeDetectionResult(
            file_type=_EXTENSION_MAP[extension],
            content_type=content_type or "text/plain",
            detected_by="extension",
            confidence=1.0,
        )

    normalized_mime = (content_type or "").split(";", 1)[0].strip().lower()
    if normalized_mime in _MIME_MAP:
        return FileTypeDetectionResult(
            file_type=_MIME_MAP[normalized_mime],
            content_type=normalized_mime,
            detected_by="mime",
            confidence=0.9,
        )

    raise UnsupportedFileTypeError(filename=filename, content_type=content_type)
