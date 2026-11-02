"""Deterministic basic file type detection for M5 uploads."""

from __future__ import annotations

from pathlib import Path

from app.application.exceptions import UnsupportedFileTypeError
from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import FileTypeDetectionResult

_EXTENSION_MAP: dict[str, FileType] = {
    ".txt": FileType.TEXT,
    ".csv": FileType.TEXT,
    ".pdf": FileType.PDF,
    ".docx": FileType.DOCX,
    ".doc": FileType.UNKNOWN,
    ".xlsx": FileType.SPREADSHEET,
    ".xls": FileType.SPREADSHEET,
    ".png": FileType.IMAGE,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".gif": FileType.IMAGE,
    ".webp": FileType.IMAGE,
    ".dwg": FileType.UNKNOWN,
    ".dxf": FileType.UNKNOWN,
    ".edb": FileType.UNKNOWN,
    ".sdb": FileType.UNKNOWN,
    ".f2k": FileType.UNKNOWN,
    ".e2k": FileType.TEXT,
    ".s2k": FileType.TEXT,
    ".json": FileType.TEXT,
}

_MIME_MAP: dict[str, FileType] = {
    "text/plain": FileType.TEXT,
    "text/csv": FileType.TEXT,
    "application/pdf": FileType.PDF,
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": FileType.SPREADSHEET,
    "application/vnd.ms-excel": FileType.SPREADSHEET,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": FileType.DOCX,
    "application/msword": FileType.UNKNOWN,
    "image/png": FileType.IMAGE,
    "image/jpeg": FileType.IMAGE,
    "image/gif": FileType.IMAGE,
    "image/webp": FileType.IMAGE,
}


def detect_file_type(filename: str, content_type: str | None) -> FileTypeDetectionResult:
    extension = Path(filename).suffix.lower()
    if extension in _EXTENSION_MAP:
        return FileTypeDetectionResult(
            file_type=_EXTENSION_MAP[extension],
            content_type=content_type or _default_content_type(_EXTENSION_MAP[extension]),
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


def _default_content_type(file_type: FileType) -> str:
    mapping = {
        FileType.TEXT: "text/plain",
        FileType.PDF: "application/pdf",
        FileType.DOCX: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        FileType.SPREADSHEET: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        FileType.IMAGE: "application/octet-stream",
        FileType.UNKNOWN: "application/octet-stream",
    }
    return mapping.get(file_type, "application/octet-stream")
