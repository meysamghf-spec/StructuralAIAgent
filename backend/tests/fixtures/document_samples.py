"""Deterministic in-memory document fixtures for extraction tests."""

from __future__ import annotations


def sample_pdf_bytes(*, text: str = "Structural load case LC1") -> bytes:
    escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    content = f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("ascii")
    return (
        b"%PDF-1.4\n"
        b"1 0 obj<< /Type /Catalog /Pages 2 0 R >>endobj\n"
        b"2 0 obj<< /Type /Pages /Kids [3 0 R] /Count 1 >>endobj\n"
        b"3 0 obj<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources<< /Font<< /F1 5 0 R >> >> >>endobj\n"
        b"4 0 obj<< /Length "
        + str(len(content)).encode("ascii")
        + b" >>stream\n"
        + content
        + b"\nendstream endobj\n"
        b"5 0 obj<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>endobj\n"
        b"xref\n0 6\n0000000000 65535 f \n0000000009 00000 n \n0000000058 00000 n \n"
        b"0000000115 00000 n \n0000000267 00000 n \n0000000400 00000 n \n"
        b"trailer<< /Size 6 /Root 1 0 R >>\nstartxref\n480\n%%EOF\n"
    )


def sample_docx_bytes(*, paragraph: str = "Concrete f'c = 30 MPa", table_row: tuple[str, ...] = ("Load", "Value")) -> bytes:
    import io

    import docx

    document = docx.Document()
    document.add_paragraph(paragraph)
    table = document.add_table(rows=1, cols=len(table_row))
    for index, value in enumerate(table_row):
        table.rows[0].cells[index].text = value
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def sample_xlsx_bytes(*, sheet_name: str = "Loads", rows: list[list[str]] | None = None) -> bytes:
    import io

    from openpyxl import Workbook

    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = sheet_name
    for row in rows or [["Case", "Value"], ["DL", "6"], ["LL", "4"]]:
        worksheet.append(row)
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
