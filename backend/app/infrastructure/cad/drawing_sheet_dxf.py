"""
DXF output for a :class:`DrawingSheet`.

This extends the existing DXF infrastructure rather than replacing it: the
header, layer table, result wrapper and LINE entity all come from
``dxf_renderer``. What is added here is CIRCLE output, TEXT with a real height
and rotation, and the sheet frame and title block.

Geometry is written in millimetres in paper space, laid out with the same
:mod:`sheet_render_layout` transforms the PDF writer uses, so the DXF and the PDF
of a sheet are the same drawing. Each primitive's source PEM element ID is
written into the entity's extended data (group code 1000) so traceability
survives the export.
"""

from __future__ import annotations

from app.application.drawing.sheet_render_layout import (
    ViewTransform,
    view_transforms,
)
from app.domain.models.drawing import (
    DrawingPrimitive,
    DrawingSheet,
    PrimitiveKind,
)
from app.infrastructure.cad.dxf_renderer import (
    DxfRenderResult,
    _build_result,
    _line_entity,
)

MM_PER_PT = 25.4 / 72.0

PAGE_WIDTH_MM = 1190.0 * MM_PER_PT
PAGE_HEIGHT_MM = 842.0 * MM_PER_PT
_FRAME_LAYER = "SHEET-FRAME"
_TITLE_LAYER = "TITLE-BLOCK"


def render_sheet_dxf(sheet: DrawingSheet, *, units: str = "MILLIMETERS") -> DxfRenderResult:
    """Render one drawing sheet — geometry, annotations and title block — to DXF."""
    transforms = view_transforms(sheet)
    entities: list[str] = []
    layers: dict[str, int] = {}

    def bump(layer: str, count: int = 1) -> None:
        layers[layer] = layers.get(layer, 0) + count

    for view in sheet.views:
        transform = transforms.get(view.id)
        if transform is None:
            continue
        for primitive in view.all_primitives():
            created = _primitive_entities(primitive, transform)
            if created:
                entities.extend(created)
                bump(primitive.layer)

    frame_count = len(_sheet_frame(entities))
    bump(_FRAME_LAYER, frame_count)
    title_count = len(_title_block(entities, sheet))
    bump(_TITLE_LAYER, title_count)

    kind_counts: dict[str, int] = {}
    for primitive in sheet.all_primitives():
        key = primitive.source_element_kind.value
        kind_counts[key] = kind_counts.get(key, 0) + 1

    return _build_result(
        entities=entities,
        layers=layers,
        drawing_type=f"SHEET_{sheet.sheet_number.replace('-', '_')}",
        units=units,
        metadata={
            "sheet_number": sheet.sheet_number,
            "sheet_title": sheet.title,
            "discipline": sheet.discipline.value,
            "scale": sheet.scale,
            "revision": sheet.revision,
            "source_model_id": sheet.source_model_id,
            "source_snapshot_id": sheet.source_snapshot_id,
            "view_count": len(sheet.views),
            "view_ids": [view.id for view in sheet.views],
            "element_ref_count": len(sheet.element_refs),
            "source_element_kinds": kind_counts,
            "geometry_signature": sheet.geometry_signature,
            "content_signature": sheet.content_signature,
            "capability_status": (
                "COMPLETE" if sheet.availability.value == "AVAILABLE" else sheet.availability.value
            ),
            "missing_data": list(sheet.missing_data),
        },
    )


def _primitive_entities(primitive: DrawingPrimitive, transform: ViewTransform) -> list[str]:
    points_mm = [
        tuple(value * MM_PER_PT for value in transform.to_pt(point.x, point.y))
        for point in primitive.points
    ]
    if primitive.kind is PrimitiveKind.LINE and len(points_mm) >= 2:
        return _traced(
            _line_entity(primitive.layer, *points_mm[0], *points_mm[1]), primitive
        )
    if primitive.kind is PrimitiveKind.POLYLINE and len(points_mm) >= 2:
        entities: list[str] = []
        limit = len(points_mm) if primitive.closed else len(points_mm) - 1
        for index in range(limit):
            start = points_mm[index]
            end = points_mm[(index + 1) % len(points_mm)]
            entities.extend(_line_entity(primitive.layer, *start, *end))
        return _traced(entities, primitive)
    if primitive.kind is PrimitiveKind.CIRCLE and points_mm and primitive.radius_m:
        radius_mm = transform.length_pt(primitive.radius_m) * MM_PER_PT
        return _traced(
            _circle_entity(primitive.layer, points_mm[0][0], points_mm[0][1], radius_mm),
            primitive,
        )
    if primitive.kind is PrimitiveKind.TEXT and points_mm and primitive.text:
        height_mm = transform.text_pt(primitive.text_height_m) * MM_PER_PT
        return _traced(
            _text_entity_sized(
                primitive.layer,
                points_mm[0][0],
                points_mm[0][1],
                primitive.text,
                height_mm,
                primitive.rotation_deg,
                primitive.text_anchor,
            ),
            primitive,
        )
    return []


def _traced(entities: list[str], primitive: DrawingPrimitive) -> list[str]:
    """Attach the source PEM element IDs to an entity as extended data."""
    if not entities or not primitive.source_element_ids:
        return entities
    tail = [
        "1001\nSTRUCTURALAIAGENT",
        f"1000\nsource_element_kind={primitive.source_element_kind.value}",
        f"1000\nsource_element_ids={','.join(primitive.source_element_ids)}",
    ]
    if primitive.projection:
        tail.append(f"1000\nprojection={primitive.projection}")
    return [*entities, *tail]


def _circle_entity(layer: str, x: float, y: float, radius: float) -> list[str]:
    return [
        "0\nCIRCLE",
        f"8\n{layer}",
        f"10\n{x}",
        f"20\n{y}",
        "30\n0.0",
        f"40\n{radius}",
    ]


def _text_entity_sized(
    layer: str,
    x: float,
    y: float,
    text: str,
    height: float,
    rotation: float,
    anchor: str,
) -> list[str]:
    safe = text.replace("\n", " ")
    entity = [
        "0\nTEXT",
        f"8\n{layer}",
        f"10\n{x}",
        f"20\n{y}",
        "30\n0.0",
        f"40\n{height}",
        f"50\n{rotation}",
        # 72 = horizontal justification: 0 left, 1 centre.
        f"72\n{0 if anchor == 'LEFT' else 1}",
        f"11\n{x}",
        f"21\n{y}",
        "31\n0.0",
        f"1\n{safe}",
    ]
    return entity


def _sheet_frame(entities: list[str]) -> list[str]:
    """Outer border, appended in place; returns the segments added."""
    margin = 24.0 * MM_PER_PT
    corners = [
        (margin, margin),
        (PAGE_WIDTH_MM - margin, margin),
        (PAGE_WIDTH_MM - margin, PAGE_HEIGHT_MM - margin),
        (margin, PAGE_HEIGHT_MM - margin),
    ]
    added: list[str] = []
    for index in range(4):
        start = corners[index]
        end = corners[(index + 1) % 4]
        added.extend(_line_entity(_FRAME_LAYER, *start, *end))
    entities.extend(added)
    return added


def _title_block(entities: list[str], sheet: DrawingSheet) -> list[str]:
    """Title block box and its fields, appended in place."""
    from app.application.drawing.sheet_builder import (
        MARGIN_PT,
        TITLE_BLOCK_HEIGHT_PT,
        TITLE_BLOCK_WIDTH_PT,
    )

    block = sheet.title_block
    x0 = (1190.0 - MARGIN_PT - TITLE_BLOCK_WIDTH_PT) * MM_PER_PT
    y0 = MARGIN_PT * MM_PER_PT
    width = TITLE_BLOCK_WIDTH_PT * MM_PER_PT
    height = TITLE_BLOCK_HEIGHT_PT * MM_PER_PT

    added: list[str] = []
    corners = [(x0, y0), (x0 + width, y0), (x0 + width, y0 + height), (x0, y0 + height)]
    for index in range(4):
        added.extend(_line_entity(_TITLE_LAYER, *corners[index], *corners[(index + 1) % 4]))

    rows = [
        f"PROJECT: {block.project_name}",
        f"TITLE: {block.drawing_title}",
        f"DRAWING No: {block.drawing_number}    REV: {block.revision}",
        f"DISCIPLINE: {block.discipline.value}    SCALE: {block.scale}    UNITS: {block.units}",
        f"GENERATED: {block.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
        f"SOURCE MODEL: {block.source_model_id}",
        f"SOURCE SNAPSHOT: {block.source_snapshot_id or 'N/A'}",
        block.status_note,
    ]
    text_height = 7.0 * MM_PER_PT
    for index, row in enumerate(rows):
        y = y0 + height - (index + 1) * (height / (len(rows) + 0.5))
        added.extend(
            _text_entity_sized(_TITLE_LAYER, x0 + 4.0, y, row, text_height, 0.0, "LEFT")
        )
    entities.extend(added)
    return added
