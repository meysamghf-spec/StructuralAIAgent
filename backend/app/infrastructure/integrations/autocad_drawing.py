"""Turn a PEM drawing set into AutoCAD entity commands.

Coordinates in the drawing set are metres. Commands are millimetres. This module
does not open AutoCAD and does not treat a command list as a saved drawing.
"""

from __future__ import annotations

from typing import Any

from app.domain.models.drawing import DrawingSet


def commands_from_drawing_set(drawing_set: DrawingSet) -> dict[str, Any]:
    commands: list[dict[str, Any]] = []
    sheets: list[dict[str, Any]] = []
    for index, sheet in enumerate(drawing_set.sheets):
        origin_x = index * 50000.0
        geometry = 0
        annotations = 0
        for primitive in sheet.all_primitives():
            kind = primitive.kind.value
            points = [
                [origin_x + point.x * 1000.0, point.y * 1000.0, 0.0]
                for point in primitive.points
            ]
            if kind in {"LINE", "POLYLINE", "CIRCLE"} and points:
                geometry += 1
            else:
                annotations += 1
            commands.append(
                {
                    "kind": kind,
                    "layer": primitive.layer,
                    "points": points,
                    "closed": primitive.closed,
                    "text": primitive.text,
                    "text_height_mm": float(primitive.text_height_m) * 1000.0,
                    "radius_mm": None if primitive.radius_m is None else float(primitive.radius_m) * 1000.0,
                    "sheet": sheet.sheet_number,
                    "source_element_ids": list(primitive.source_element_ids),
                }
            )
        sheets.append(
            {
                "sheet": sheet.sheet_number,
                "title": sheet.title,
                "geometry_count": geometry,
                "annotation_count": annotations,
            }
        )
    missing = [
        item
        for item in (drawing_set.metadata.get("pending_milestones") or [])
        if isinstance(item, str)
    ]
    geometry_count = sum(item["geometry_count"] for item in sheets)
    return {
        "commands": commands,
        "geometry_count": geometry_count,
        "annotation_count": sum(item["annotation_count"] for item in sheets),
        "sheets": sheets,
        "missing_construction_details": missing,
        "units": "mm",
        "scale_from_pem": "1 m = 1000 mm",
        "construction_ready": False,
        "source_snapshot_id": drawing_set.source_snapshot_id,
        "pem_version": drawing_set.pem_version,
    }


def validate_sheet_plan(plan: dict[str, Any] | None) -> tuple[bool, str]:
    if not isinstance(plan, dict):
        return False, "AutoCAD generation requires a PEM sheet plan."
    geometry = int(plan.get("geometry_count") or 0)
    commands = plan.get("commands") or []
    drawable = [
        item
        for item in commands
        if item.get("kind") in {"LINE", "POLYLINE", "CIRCLE"} and item.get("points")
    ]
    if geometry <= 0 or not drawable:
        missing = plan.get("missing_construction_details") or []
        detail = f" Missing construction details: {', '.join(missing)}." if missing else ""
        return False, "The PEM sheet plan has no drawable geometry." + detail
    return True, "The PEM sheet plan has drawable geometry."
