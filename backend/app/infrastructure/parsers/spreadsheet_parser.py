"""Spreadsheet extraction parser for XLSX and legacy XLS."""

from __future__ import annotations

import io
from pathlib import Path
from typing import Any

from app.domain.models.document_extraction import DocumentExtractionResult, DocumentExtractionStatus
from app.domain.models.file_artifact import FileType
from app.domain.models.ingestion import ExtractionResult
from app.infrastructure.parsers.parser_helpers import extraction_from_document

_MAX_ROWS_PER_SHEET = 200
_MAX_COLUMNS = 50


class SpreadsheetParser:
    parser_key = "spreadsheet"

    def supports(self, file_type: FileType, content_type: str | None) -> bool:
        return file_type == FileType.SPREADSHEET

    def extract(self, content: bytes, *, filename: str) -> ExtractionResult:
        extension = Path(filename).suffix.lower()
        try:
            if extension == ".xls":
                sheets, warnings = _extract_xls(content, filename)
            else:
                sheets, warnings = _extract_xlsx(content, filename)
        except ImportError as exc:
            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.SPREADSHEET.value,
                status=DocumentExtractionStatus.FAILED,
                limitations=[str(exc)],
                extractor=self.parser_key,
            )
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                error_message=str(exc),
            )
        except Exception as exc:
            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.SPREADSHEET.value,
                status=DocumentExtractionStatus.FAILED,
                limitations=[f"Spreadsheet extraction failed: {exc}"],
                extractor=self.parser_key,
            )
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                error_message=str(exc),
            )

        if not sheets:
            document = DocumentExtractionResult(
                filename=filename,
                file_type=FileType.SPREADSHEET.value,
                status=DocumentExtractionStatus.FAILED,
                warnings=warnings,
                limitations=["No worksheet data could be extracted."],
                extractor=self.parser_key,
            )
            return extraction_from_document(
                document,
                parser_key=self.parser_key,
                error_message="No worksheet data could be extracted.",
            )

        extracted_text = _format_sheets_as_text(sheets)
        document = DocumentExtractionResult(
            filename=filename,
            file_type=FileType.SPREADSHEET.value,
            status=DocumentExtractionStatus.SUCCESS,
            extracted_text=extracted_text,
            structured_data={"workbook": filename, "sheets": sheets},
            warnings=warnings,
            extractor=self.parser_key,
            extractor_version=_openpyxl_version(),
            metadata={"sheet_count": len(sheets), "byte_length": len(content)},
        )
        return extraction_from_document(document, parser_key=self.parser_key, confidence=0.95)


def _extract_xlsx(content: bytes, filename: str) -> tuple[list[dict[str, Any]], list[str]]:
    from openpyxl import load_workbook
    from openpyxl.utils import get_column_letter

    workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    warnings: list[str] = []
    sheets: list[dict[str, Any]] = []
    try:
        for worksheet in workbook.worksheets:
            rows: list[dict[str, Any]] = []
            max_row = min(worksheet.max_row or 0, _MAX_ROWS_PER_SHEET)
            max_col = min(worksheet.max_column or 0, _MAX_COLUMNS)
            if max_row == 0 or max_col == 0:
                continue
            for row_index in range(1, max_row + 1):
                cells: list[dict[str, Any]] = []
                for col_index in range(1, max_col + 1):
                    value = worksheet.cell(row=row_index, column=col_index).value
                    if value is None or value == "":
                        continue
                    cells.append(
                        {
                            "column": get_column_letter(col_index),
                            "column_index": col_index,
                            "value": _json_safe_value(value),
                        }
                    )
                if cells:
                    rows.append({"row_index": row_index, "cells": cells})
            used_range = f"A1:{get_column_letter(max_col)}{max_row}"
            sheets.append({"name": worksheet.title, "used_range": used_range, "rows": rows})
            if (worksheet.max_row or 0) > _MAX_ROWS_PER_SHEET:
                warnings.append(
                    f"Sheet '{worksheet.title}' truncated to {_MAX_ROWS_PER_SHEET} rows for extraction."
                )
    finally:
        workbook.close()
    if not sheets:
        warnings.append(f"No used cell ranges were found in workbook '{filename}'.")
    return sheets, warnings


def _extract_xls(content: bytes, filename: str) -> tuple[list[dict[str, Any]], list[str]]:
    import xlrd

    workbook = xlrd.open_workbook(file_contents=content)
    warnings: list[str] = []
    sheets: list[dict[str, Any]] = []
    for worksheet in workbook.sheets():
        rows: list[dict[str, Any]] = []
        max_row = min(worksheet.nrows, _MAX_ROWS_PER_SHEET)
        max_col = min(worksheet.ncols, _MAX_COLUMNS)
        if max_row == 0 or max_col == 0:
            continue
        for row_index in range(max_row):
            cells: list[dict[str, Any]] = []
            for col_index in range(max_col):
                value = worksheet.cell_value(row_index, col_index)
                if value in ("", None):
                    continue
                cells.append(
                    {
                        "column": _column_letter(col_index + 1),
                        "column_index": col_index + 1,
                        "value": _json_safe_value(value),
                    }
                )
            if cells:
                rows.append({"row_index": row_index + 1, "cells": cells})
        used_range = f"A1:{_column_letter(max_col)}{max_row}"
        sheets.append({"name": worksheet.name, "used_range": used_range, "rows": rows})
        if worksheet.nrows > _MAX_ROWS_PER_SHEET:
            warnings.append(
                f"Sheet '{worksheet.name}' truncated to {_MAX_ROWS_PER_SHEET} rows for extraction."
            )
    if not sheets:
        warnings.append(f"No used cell ranges were found in workbook '{filename}'.")
    return sheets, warnings


def _format_sheets_as_text(sheets: list[dict[str, Any]]) -> str:
    lines: list[str] = []
    for sheet in sheets:
        name = sheet.get("name", "Sheet")
        used_range = sheet.get("used_range")
        header = f"--- Sheet: {name}"
        if used_range:
            header += f" ({used_range})"
        lines.append(header)
        rows = sheet.get("rows")
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            cells = row.get("cells")
            if not isinstance(cells, list):
                continue
            rendered = []
            for cell in cells:
                if not isinstance(cell, dict):
                    continue
                rendered.append(f"{cell.get('column')}={cell.get('value')}")
            if rendered:
                lines.append(f"Row {row.get('row_index')}: " + ", ".join(rendered))
    return "\n".join(lines)


def _json_safe_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _column_letter(index: int) -> str:
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _openpyxl_version() -> str | None:
    try:
        import openpyxl

        return getattr(openpyxl, "__version__", None)
    except ImportError:
        return None
