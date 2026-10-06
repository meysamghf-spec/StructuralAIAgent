"""Register production document parsers."""

from __future__ import annotations

from app.infrastructure.parsers.docx_parser import DocxTextParser
from app.infrastructure.parsers.pdf_parser import PdfTextParser
from app.infrastructure.parsers.spreadsheet_parser import SpreadsheetParser
from app.infrastructure.parsers.stub_parser import StubTextParser


def build_document_parsers() -> list:
    return [
        StubTextParser(),
        PdfTextParser(),
        DocxTextParser(),
        SpreadsheetParser(),
    ]
