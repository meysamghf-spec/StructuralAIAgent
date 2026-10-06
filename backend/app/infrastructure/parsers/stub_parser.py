"""Minimal text parser for TXT/CSV uploads."""

from __future__ import annotations

from app.domain.models.document_extraction import DocumentExtractionResult, DocumentExtractionStatus
from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import ExtractionResult
from app.infrastructure.parsers.parser_helpers import extraction_from_document


class StubTextParser:
    parser_key = "text_plain"

    def supports(self, file_type: FileType, content_type: str | None) -> bool:
        return file_type == FileType.TEXT

    def extract(self, content: bytes, *, filename: str) -> ExtractionResult:
        text = content.decode("utf-8", errors="replace")
        lines = text.splitlines()
        document = DocumentExtractionResult(
            filename=filename,
            file_type=FileType.TEXT.value,
            status=DocumentExtractionStatus.SUCCESS,
            extracted_text=text,
            structured_data={"lines": lines, "line_count": len(lines)},
            extractor=self.parser_key,
            metadata={"line_count": len(lines), "byte_length": len(content)},
        )
        return extraction_from_document(document, parser_key=self.parser_key, confidence=1.0)
