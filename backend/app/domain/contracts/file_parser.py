"""File parser contract — domain-neutral extraction interface."""

from __future__ import annotations

from typing import Protocol

from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import ExtractionResult


class FileParserProtocol(Protocol):
    """Parser selected by file type for synchronous extraction."""

    @property
    def parser_key(self) -> str: ...

    def supports(self, file_type: FileType, content_type: str | None) -> bool: ...

    def extract(self, content: bytes, *, filename: str) -> ExtractionResult: ...
