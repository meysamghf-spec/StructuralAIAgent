"""
Multi-page PDF output for a :class:`DrawingSet`.

One page per sheet, A3 landscape, each with its own frame, title block, notes
panel and views. Like the existing single-sheet renderer this writes PDF 1.4 by
hand so no third-party PDF dependency is introduced; unlike it, it emits a real
page tree so a drawing set is one document of genuinely distinct sheets.

Views are placed with the shared :mod:`sheet_render_layout` transforms, so a
sheet's PDF page and its DXF are the same drawing at the same scale.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.application.drawing.sheet_builder import (
    MARGIN_PT,
    PAGE_HEIGHT_PT,
    PAGE_WIDTH_PT,
    TITLE_BLOCK_HEIGHT_PT,
    TITLE_BLOCK_WIDTH_PT,
)
from app.application.drawing.sheet_render_layout import (
    ViewTransform,
    estimate_text_width_pt,
    view_transforms,
)
from app.domain.models.drawing import (
    DrawingPrimitive,
    DrawingSet,
    DrawingSheet,
    PrimitiveKind,
)

#: Bezier constant for approximating a quarter circle.
_KAPPA = 0.5522847498


def render_drawing_set_pdf(drawing_set: DrawingSet) -> bytes:
    """The whole set as one multi-page PDF, one page per sheet."""
    return _build_pdf([_sheet_content(sheet) for sheet in drawing_set.sheets])


def render_sheet_pdf(sheet: DrawingSheet) -> bytes:
    """A single sheet as a one-page PDF."""
    return _build_pdf([_sheet_content(sheet)])


def write_drawing_set_pdf(path: Path, drawing_set: DrawingSet) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_drawing_set_pdf(drawing_set))
    return path


def write_sheet_pdf(path: Path, sheet: DrawingSheet) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(render_sheet_pdf(sheet))
    return path


# ---------------------------------------------------------------------------
# Page content
# ---------------------------------------------------------------------------


def _sheet_content(sheet: DrawingSheet) -> str:
    ops: list[str] = ["0.4 w", "0 G", "0 g"]
    ops.extend(_frame_ops())
    ops.extend(_views_ops(sheet))
    ops.extend(_title_block_ops(sheet))
    ops.extend(_notes_ops(sheet))
    return "\n".join(ops)


def _frame_ops() -> list[str]:
    return [
        "0.8 w",
        _rect_op(MARGIN_PT, MARGIN_PT, PAGE_WIDTH_PT - 2 * MARGIN_PT, PAGE_HEIGHT_PT - 2 * MARGIN_PT),
        "0.4 w",
    ]


def _views_ops(sheet: DrawingSheet) -> list[str]:
    transforms = view_transforms(sheet)
    ops: list[str] = []
    for view in sheet.views:
        transform = transforms.get(view.id)
        if transform is None:
            continue
        ops.append(f"% view {view.id} {view.projection_label} 1:{view.scale_denominator}")
        for primitive in view.all_primitives():
            ops.extend(_primitive_ops(primitive, transform))
        # View caption with its own plotted scale.
        scale_text = (
            f"1:{view.scale_denominator}" if view.scale_denominator else "NTS"
        )
        caption = f"{view.name}   {scale_text}"
        ops.append(
            _text_op(
                transform.placement.x_pt + 4.0,
                transform.placement.y_pt + 2.0,
                caption,
                7.5,
            )
        )
    return ops


def _primitive_ops(primitive: DrawingPrimitive, transform: ViewTransform) -> list[str]:
    if primitive.kind is PrimitiveKind.TEXT:
        if not primitive.text or not primitive.points:
            return []
        x, y = transform.to_pt(primitive.points[0].x, primitive.points[0].y)
        size = transform.text_pt(primitive.text_height_m)
        if primitive.text_anchor == "CENTER":
            if primitive.rotation_deg:
                y -= estimate_text_width_pt(primitive.text, size) / 2.0
            else:
                x -= estimate_text_width_pt(primitive.text, size) / 2.0
        return [_text_op(x, y, primitive.text, size, rotation_deg=primitive.rotation_deg)]

    if primitive.kind is PrimitiveKind.CIRCLE:
        if not primitive.points or not primitive.radius_m:
            return []
        x, y = transform.to_pt(primitive.points[0].x, primitive.points[0].y)
        radius = transform.length_pt(primitive.radius_m)
        if radius < 0.3:
            return []
        return _circle_ops(x, y, radius)

    points = [transform.to_pt(point.x, point.y) for point in primitive.points]
    if len(points) < 2:
        return []
    if primitive.kind is PrimitiveKind.LINE:
        return [f"{points[0][0]:.2f} {points[0][1]:.2f} m {points[1][0]:.2f} {points[1][1]:.2f} l S"]
    segments = [f"{points[0][0]:.2f} {points[0][1]:.2f} m"]
    segments.extend(f"{x:.2f} {y:.2f} l" for x, y in points[1:])
    segments.append("h S" if primitive.closed else "S")
    return [" ".join(segments)]


def _circle_ops(x: float, y: float, radius: float) -> list[str]:
    offset = radius * _KAPPA
    return [
        f"{x + radius:.2f} {y:.2f} m",
        f"{x + radius:.2f} {y + offset:.2f} {x + offset:.2f} {y + radius:.2f} {x:.2f} {y + radius:.2f} c",
        f"{x - offset:.2f} {y + radius:.2f} {x - radius:.2f} {y + offset:.2f} {x - radius:.2f} {y:.2f} c",
        f"{x - radius:.2f} {y - offset:.2f} {x - offset:.2f} {y - radius:.2f} {x:.2f} {y - radius:.2f} c",
        f"{x + offset:.2f} {y - radius:.2f} {x + radius:.2f} {y - offset:.2f} {x + radius:.2f} {y:.2f} c",
        "S",
    ]


def _title_block_ops(sheet: DrawingSheet) -> list[str]:
    block = sheet.title_block
    x0 = PAGE_WIDTH_PT - MARGIN_PT - TITLE_BLOCK_WIDTH_PT
    y0 = MARGIN_PT
    ops = ["0.8 w", _rect_op(x0, y0, TITLE_BLOCK_WIDTH_PT, TITLE_BLOCK_HEIGHT_PT), "0.4 w"]

    rows: list[tuple[str, str, float]] = [
        ("PROJECT", block.project_name, 9.0),
        ("TITLE", block.drawing_title, 9.5),
        (
            "DRAWING No",
            f"{block.drawing_number}      REV {block.revision}      {block.discipline.value}",
            9.5,
        ),
        ("SCALE / UNITS", f"{block.scale}      {block.units}", 8.0),
        ("GENERATED", block.generated_at.strftime("%Y-%m-%d %H:%M UTC"), 8.0),
        ("SOURCE MODEL", block.source_model_id, 7.0),
        ("SOURCE SNAPSHOT", block.source_snapshot_id or "N/A", 7.0),
    ]
    row_height = (TITLE_BLOCK_HEIGHT_PT - 16.0) / len(rows)
    for index, (label, value, size) in enumerate(rows):
        y = y0 + TITLE_BLOCK_HEIGHT_PT - 12.0 - index * row_height
        ops.append(_text_op(x0 + 5.0, y, label, 5.6))
        ops.append(_text_op(x0 + 86.0, y, value[:72], size))
    ops.append(_text_op(x0 + 5.0, y0 + 4.0, block.status_note, 7.0))
    # Divider between the label gutter and the values.
    ops.append(
        f"{x0 + 82.0:.2f} {y0:.2f} m {x0 + 82.0:.2f} {y0 + TITLE_BLOCK_HEIGHT_PT - 14.0:.2f} l S"
    )
    return ops


def _notes_ops(sheet: DrawingSheet) -> list[str]:
    x0 = MARGIN_PT + 6.0
    y_top = MARGIN_PT + TITLE_BLOCK_HEIGHT_PT - 10.0
    width = PAGE_WIDTH_PT - 2 * MARGIN_PT - TITLE_BLOCK_WIDTH_PT - 20.0
    ops = [_text_op(x0, y_top + 2.0, "NOTES", 7.5)]
    wrapped: list[str] = []
    for index, note in enumerate(sheet.notes, start=1):
        wrapped.extend(_wrap(f"{index}. {note}", width=int(width / 3.05)))
    if sheet.availability.value != "AVAILABLE":
        wrapped.insert(0, f"SHEET STATUS: {sheet.availability.value}")
    for index, line in enumerate(wrapped[:11]):
        ops.append(_text_op(x0, y_top - 9.0 - index * 7.6, line, 6.2))
    return ops


def _wrap(text: str, *, width: int) -> list[str]:
    words = text.split(" ")
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip() if current else word
        if len(candidate) > width and current:
            lines.append(current)
            current = f"   {word}"
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def _rect_op(x: float, y: float, width: float, height: float) -> str:
    return f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re S"


def _text_op(x: float, y: float, text: str, size: float, *, rotation_deg: float = 0.0) -> str:
    safe = _escape(text)
    if abs(rotation_deg - 90.0) < 1e-6:
        return f"BT /F1 {size:.2f} Tf 0 1 -1 0 {x:.2f} {y:.2f} Tm ({safe}) Tj ET"
    if rotation_deg:
        import math

        radians = math.radians(rotation_deg)
        cos = math.cos(radians)
        sin = math.sin(radians)
        return (
            f"BT /F1 {size:.2f} Tf {cos:.4f} {sin:.4f} {-sin:.4f} {cos:.4f} "
            f"{x:.2f} {y:.2f} Tm ({safe}) Tj ET"
        )
    return f"BT /F1 {size:.2f} Tf {x:.2f} {y:.2f} Td ({safe}) Tj ET"


def _escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("(", "\\(")
        .replace(")", "\\)")
        .replace("\n", " ")
    )


# ---------------------------------------------------------------------------
# PDF assembly
# ---------------------------------------------------------------------------


def _build_pdf(pages: list[str]) -> bytes:
    """
    Assemble a PDF 1.4 document.

    Object numbering: 1 catalog, 2 page tree, 3 font, then for page ``i`` the
    page object is ``4 + 2i`` and its content stream ``5 + 2i``.
    """
    if not pages:
        pages = [""]
    page_object_numbers = [4 + 2 * index for index in range(len(pages))]
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)

    objects: list[str] = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    for index, content in enumerate(pages):
        content_number = 5 + 2 * index
        objects.append(
            f"<< /Type /Page /Parent 2 0 R "
            f"/MediaBox [0 0 {PAGE_WIDTH_PT:.0f} {PAGE_HEIGHT_PT:.0f}] "
            f"/Contents {content_number} 0 R "
            "/Resources << /Font << /F1 3 0 R >> >> >>"
        )
        encoded = content.encode("latin-1", "replace")
        objects.append(f"<< /Length {len(encoded)} >>\nstream\n{content}\nendstream")

    header = b"%PDF-1.4\n"
    body_parts: list[bytes] = []
    offsets: list[int] = []
    cursor = len(header)
    for index, body in enumerate(objects, start=1):
        offsets.append(cursor)
        chunk = f"{index} 0 obj\n{body}\nendobj\n".encode("latin-1", "replace")
        body_parts.append(chunk)
        cursor += len(chunk)

    xref_position = cursor
    xref = [f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"]
    xref.extend(f"{offset:010d} 00000 n \n" for offset in offsets)
    stamp = datetime.now(UTC).strftime("D:%Y%m%d%H%M%SZ")
    trailer = (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R "
        f"/Info << /Producer (SAAI drawing engine) /CreationDate ({stamp}) >> >>\n"
        f"startxref\n{xref_position}\n%%EOF\n"
    )
    return header + b"".join(body_parts) + "".join(xref).encode("ascii") + trailer.encode("latin-1", "replace")
