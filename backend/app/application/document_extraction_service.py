"""Helpers for normalized document extraction results on project files."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from app.domain.models.document_extraction import DocumentExtractionResult, DocumentExtractionStatus
from app.domain.models.file_artifact import ProjectFile

_MAX_PREVIEW_CHARS = 8000


def document_from_file_record(record: ProjectFile) -> DocumentExtractionResult | None:
    extraction = record.metadata.get("extraction")
    if not isinstance(extraction, dict):
        return None
    raw_document = extraction.get("metadata", {}).get("document")
    if not isinstance(raw_document, dict):
        return None
    try:
        document = DocumentExtractionResult.model_validate(raw_document)
    except Exception:
        return None
    if document.file_id is None:
        document.file_id = record.id
    return document


def build_agent_preview(document: DocumentExtractionResult, *, max_chars: int = _MAX_PREVIEW_CHARS) -> str | None:
    if not document.is_usable:
        return None

    sections: list[str] = []
    if document.extracted_text and document.extracted_text.strip():
        sections.append(document.extracted_text.strip())

    structured = document.structured_data or {}
    sheets = structured.get("sheets")
    if isinstance(sheets, list) and sheets and not sections:
        sections.append(_format_sheets_preview(sheets))

    if document.warnings:
        sections.append("Warnings:\n" + "\n".join(f"- {item}" for item in document.warnings))

    if not sections:
        return None

    combined = "\n\n".join(sections)
    if len(combined) <= max_chars:
        return combined
    return f"{combined[:max_chars]}\n...[truncated]"


def build_index_content(record: ProjectFile, document: DocumentExtractionResult) -> str:
    filename = record.filename
    if document.file_type == "TEXT":
        line_count = document.metadata.get("line_count")
        if line_count is not None:
            return f"Document '{filename}' indexed ({line_count} lines)."
    if document.file_type == "PDF":
        page_count = document.metadata.get("page_count")
        if page_count is not None:
            return f"Document '{filename}' indexed ({page_count} pages)."
    if document.file_type == "DOCX":
        paragraph_count = document.metadata.get("paragraph_count")
        table_count = document.metadata.get("table_count")
        if paragraph_count is not None:
            suffix = f", {table_count} tables" if table_count else ""
            return f"Document '{filename}' indexed ({paragraph_count} paragraphs{suffix})."
    if document.file_type == "SPREADSHEET":
        sheet_count = document.metadata.get("sheet_count")
        if sheet_count is not None:
            return f"Document '{filename}' indexed ({sheet_count} sheets)."
    preview = build_agent_preview(document, max_chars=500)
    if preview:
        return f"Document '{filename}' indexed.\n{preview}"
    return f"Document '{filename}' indexed."


def limitation_from_document(document: DocumentExtractionResult | None) -> str | None:
    if document is None:
        return None
    if document.limitations:
        return document.limitations[0]
    if document.status == DocumentExtractionStatus.FAILED:
        return "Document extraction failed."
    return None


def _format_sheets_preview(sheets: list[Any]) -> str:
    lines = ["Spreadsheet structure:"]
    for sheet in sheets[:5]:
        if not isinstance(sheet, dict):
            continue
        name = sheet.get("name", "Sheet")
        used_range = sheet.get("used_range")
        header = f"Sheet: {name}"
        if used_range:
            header += f" ({used_range})"
        lines.append(header)
        rows = sheet.get("rows")
        if not isinstance(rows, list):
            continue
        for row in rows[:50]:
            if not isinstance(row, dict):
                continue
            cells = row.get("cells")
            if not isinstance(cells, list):
                continue
            rendered = []
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                column = cell.get("column", "?")
                value = cell.get("value")
                rendered.append(f"{column}={json.dumps(value, ensure_ascii=False)}")
            if rendered:
                row_index = row.get("row_index", "?")
                lines.append(f"  Row {row_index}: " + ", ".join(rendered))
    return "\n".join(lines)
