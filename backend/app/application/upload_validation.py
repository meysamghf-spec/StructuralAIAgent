"""Basic upload validation — filename, size, and allowlist checks."""

from __future__ import annotations

import re
from pathlib import Path

from app.application.exceptions import InvalidUploadError, UploadTooLargeError

_FILENAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,254}$")
_ALLOWED_EXTENSIONS = {
    ".txt",
    ".pdf",
    ".dwg",
    ".dxf",
    ".edb",
    ".sdb",
    ".f2k",
    ".xlsx",
    ".xls",
    ".docx",
    ".doc",
    ".csv",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}


def validate_filename(filename: str) -> str:
    cleaned = filename.strip()
    if not cleaned or cleaned in {".", ".."}:
        raise InvalidUploadError("Filename is required")
    if Path(cleaned).name != cleaned:
        raise InvalidUploadError("Filename must not contain path separators")
    if ".." in cleaned or "/" in cleaned or "\\" in cleaned:
        raise InvalidUploadError("Filename must not contain path traversal sequences")
    if not _FILENAME_PATTERN.match(cleaned):
        raise InvalidUploadError("Filename contains invalid characters")
    extension = Path(cleaned).suffix.lower()
    if extension not in _ALLOWED_EXTENSIONS:
        raise InvalidUploadError("File extension is not allowed")
    return cleaned


def validate_upload_size(content: bytes, *, max_bytes: int) -> None:
    if len(content) > max_bytes:
        raise UploadTooLargeError(max_bytes=max_bytes, actual_bytes=len(content))
