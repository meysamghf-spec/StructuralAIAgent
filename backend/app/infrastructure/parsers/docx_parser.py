"""DOCX text extraction parser."""

from __future__ import annotations

import io
from typing import Any

from app.domain.models.document_extraction import DocumentExtractionResult, DocumentExtractionStatus
from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import ExtractionResult
from app.infrastructure.parsers.parser_helpers import extraction_from_document


class DocxTextParser:
    parser_key = "docx_text"

    def supports(self, file_type: FileType, content_type: str | None) -> bool:
        return file_type == FileType.DOCX

    def extract(self, content: bytes, *, filename: str) -> ExtractionResult:
        try:
            import docx
        except ImportError:
            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.DOCX.value,
                status=DocumentExtractionStatus.FAILED,
                limitations=["DOCX extraction library is not installed."],
                extractor=self.parser_key,
            )
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                error_message="DOCX extraction library is not installed.",
            )

        try:
            document_obj = docx.Document(io.BytesIO(content))
            paragraphs: list[dict[str, Any]] = []
            paragraph_lines: list[str] = []
            for index, paragraph in enumerate(document_obj.paragraphs, start=1):
                text = paragraph.text.strip()
                if not text:
                    continue
                paragraphs.append({"index": index, "text": text})
                paragraph_lines.append(text)

            tables: list[list[list[str]]] = []
            table_lines: list[str] = []
            for table_index, table in enumerate(document_obj.tables, start=1):
                rendered_rows: list[list[str]] = []
                table_lines.append(f"--- Table {table_index} ---")
                for row in table.rows:
                    cells = [cell.text.strip() for cell in row.cells]
                    rendered_rows.append(cells)
                    table_lines.append("\t".join(cells))
                tables.append(rendered_rows)

            core_properties: dict[str, Any] = {}
            props = document_obj.core_properties
            for field in ("title", "subject", "creator", "keywords", "category", "comments"):
                value = getattr(props, field, None)
                if value:
                    core_properties[field] = str(value)

            extracted_parts = paragraph_lines + table_lines
            extracted_text = "\n".join(extracted_parts).strip()
            warnings: list[str] = []
            if not extracted_text:
                warnings.append("No extractable paragraph or table text was found in the DOCX file.")
                status = DocumentExtractionStatus.FAILED
            else:
                status = DocumentExtractionStatus.SUCCESS

            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.DOCX.value,
                status=status,
                extracted_text=extracted_text or None,
                structured_data={
                    "paragraphs": paragraphs,
                    "tables": tables,
                    "core_properties": core_properties,
                },
                warnings=warnings,
                extractor=self.parser_key,
                extractor_version=_docx_version(),
                metadata={
                    "paragraph_count": len(paragraphs),
                    "table_count": len(tables),
                    "byte_length": len(content),
                },
            )
            error_message = warnings[0] if status == DocumentExtractionStatus.FAILED else None
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                confidence=0.95 if status == DocumentExtractionStatus.SUCCESS else None,
                error_message=error_message,
            )
        except Exception as exc:
            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.DOCX.value,
                status=DocumentExtractionStatus.FAILED,
                limitations=[f"DOCX extraction failed: {exc}"],
                extractor=self.parser_key,
            )
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                error_message=str(exc),
            )


def _docx_version() -> str | None:
    try:
        import docx

        return getattr(docx, "__version__", None)
    except ImportError:
        return None
