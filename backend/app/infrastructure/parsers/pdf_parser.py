"""PDF text extraction parser."""

from __future__ import annotations

import io
from typing import Any

from app.domain.models.document_extraction import DocumentExtractionResult, DocumentExtractionStatus
from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import ExtractionResult
from app.infrastructure.parsers.parser_helpers import extraction_from_document


class PdfTextParser:
    parser_key = "pdf_text"

    def supports(self, file_type: FileType, content_type: str | None) -> bool:
        return file_type == FileType.PDF

    def extract(self, content: bytes, *, filename: str) -> ExtractionResult:
        try:
            from pypdf import PdfReader
        except ImportError:
            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.PDF.value,
                status=DocumentExtractionStatus.FAILED,
                limitations=["PDF extraction library is not installed."],
                extractor=self.parser_key,
            )
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                error_message="PDF extraction library is not installed.",
            )

        try:
            reader = PdfReader(io.BytesIO(content))
            pages: list[dict[str, Any]] = []
            page_text_blocks: list[str] = []
            warnings: list[str] = []

            for index, page in enumerate(reader.pages, start=1):
                text = (page.extract_text() or "").strip()
                pages.append({"page_number": index, "text": text})
                page_text_blocks.append(f"--- Page {index} ---\n{text}")

            extracted_text = "\n\n".join(block for block in page_text_blocks if block.strip())
            pdf_metadata: dict[str, Any] = {}
            if reader.metadata:
                for key in ("/Title", "/Author", "/Subject", "/Creator", "/Producer"):
                    value = reader.metadata.get(key)
                    if value:
                        pdf_metadata[key.lstrip("/").lower()] = str(value)

            if not extracted_text.strip():
                warnings.append(
                    "No extractable text was found. The PDF may be scanned/image-only or encrypted."
                )
                status = DocumentExtractionStatus.PARTIAL if pages else DocumentExtractionStatus.FAILED
            else:
                status = DocumentExtractionStatus.SUCCESS

            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.PDF.value,
                status=status,
                extracted_text=extracted_text or None,
                structured_data={"pages": pages, "page_count": len(pages), "pdf_metadata": pdf_metadata},
                warnings=warnings,
                extractor=self.parser_key,
                extractor_version=_pypdf_version(),
                metadata={"page_count": len(pages), "byte_length": len(content)},
            )
            error_message = warnings[0] if status == DocumentExtractionStatus.FAILED else None
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                confidence=0.9 if status == DocumentExtractionStatus.SUCCESS else 0.4,
                error_message=error_message,
            )
        except Exception as exc:
            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.PDF.value,
                status=DocumentExtractionStatus.FAILED,
                limitations=[f"PDF extraction failed: {exc}"],
                extractor=self.parser_key,
            )
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                error_message=str(exc),
            )


def _pypdf_version() -> str | None:
    try:
        import pypdf

        return getattr(pypdf, "__version__", None)
    except ImportError:
        return None
