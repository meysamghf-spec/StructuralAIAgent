"""Minimal stub parser for M5 foundation testing — not a production extractor."""

from __future__ import annotations

from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import ExtractionResult


class StubTextParser:
    parser_key = "stub_text"

    def supports(self, file_type: FileType, content_type: str | None) -> bool:
        return file_type == FileType.TEXT

    def extract(self, content: bytes, *, filename: str) -> ExtractionResult:
        text = content.decode("utf-8", errors="replace")
        lines = text.splitlines()
        return ExtractionResult(
            parser_key=self.parser_key,
            success=True,
            confidence=1.0,
            metadata={
                "filename": filename,
                "byte_length": len(content),
                "line_count": len(lines),
                "stub": True,
            },
        )
