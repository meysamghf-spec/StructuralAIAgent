"""Deterministic DXF generation from ProjectEngineeringModel geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import (
    AreaDefinition,
    BeamSection,
    ColumnSection,
    MemberType,
    SlabSection,
    StructuralMember,
)


@dataclass(frozen=True)
class DxfRenderResult:
    content: str
    entity_count: int
    layer_summary: dict[str, int]
    metadata: dict[str, Any]


PLAN_DRAWING_TYPES = frozenset(
    {
        "FRAMING_PLAN",
        "COLUMN_PLAN",
        "COLUMN_LAYOUT",
        "BEAM_PLAN",
        "BEAM_LAYOUT",
        "SLAB_PLAN",
    }
)


def render_plan_dxf(
    pem: ProjectEngineeringModel,
    *,
    drawing_type: str,
    units: str = "METERS",
) -> DxfRenderResult:
    normalized = drawing_type.strip().upper()
    if normalized in {"COLUMN_PLAN", "COLUMN_LAYOUT"}:
        return render_column_plan_dxf(pem, drawing_type=normalized, units=units)
    if normalized in {"BEAM_PLAN", "BEAM_LAYOUT"}:
        return render_beam_plan_dxf(pem, drawing_type=normalized, units=units)
    if normalized == "SLAB_PLAN":
        return render_slab_plan_dxf(pem, drawing_type=normalized, units=units)
    return render_framing_plan_dxf(pem, drawing_type=normalized, units=units)


def render_framing_plan_dxf(
    pem: ProjectEngineeringModel,
    *,
    drawing_type: str,
    units: str = "METERS",
) -> DxfRenderResult:
    structural = pem.structural_model
    points = _points_map(structural.geometry.points)
    layers = {"GRID": 0, "MEMBERS": 0, "TEXT": 0}
    entities: list[str] = []

    for line in sorted(structural.geometry.lines, key=lambda item: item.id):
        start = points.get(line.start_point_id)
        end = points.get(line.end_point_id)
        if start is None or end is None:
            continue
        entities.extend(_line_entity("GRID", start.x, start.y, end.x, end.y))
        layers["GRID"] += 1

    for member in sorted(structural.members.members, key=lambda item: item.id):
        start, end = _member_endpoints(member, structural, points)
        if start is None or end is None:
            continue
        entities.extend(_line_entity("MEMBERS", start.x, start.y, end.x, end.y))
        label_x = (start.x + end.x) / 2.0
        label_y = (start.y + end.y) / 2.0
        entities.extend(_text_entity("TEXT", label_x, label_y, member.name))
        layers["MEMBERS"] += 1
        layers["TEXT"] += 1

    return _build_result(
        entities=entities,
        layers=layers,
        drawing_type=drawing_type,
        units=units,
        metadata={
            "member_count": len(structural.members.members),
            "line_count": len(structural.geometry.lines),
            "capability_status": "COMPLETE" if layers["MEMBERS"] > 0 else "INCOMPLETE",
        },
    )


def render_column_plan_dxf(
    pem: ProjectEngineeringModel,
    *,
    drawing_type: str,
    units: str = "METERS",
) -> DxfRenderResult:
    structural = pem.structural_model
    points = _points_map(structural.geometry.points)
    levels = {level.id: level.name for level in structural.geometry.levels}
    grids = {grid.id: grid.name for grid in structural.geometry.grids}
    layers = {"GRID": 0, "COLUMNS": 0, "TEXT": 0, "DIMENSIONS": 0}
    entities: list[str] = []
    missing: list[str] = []
    column_members = sorted(
        [member for member in structural.members.members if member.member_type == MemberType.COLUMN],
        key=lambda item: item.id,
    )

    for line in sorted(structural.geometry.lines, key=lambda item: item.id):
        start = points.get(line.start_point_id)
        end = points.get(line.end_point_id)
        if start is None or end is None:
            continue
        entities.extend(_line_entity("GRID", start.x, start.y, end.x, end.y))
        layers["GRID"] += 1

    if not column_members:
        missing.append("No column members are defined in the engineering model")

    for member in column_members:
        location = _column_plan_location(member, points)
        if location is None:
            missing.append(f"Column '{member.name}' has no plan location")
            continue
        section = _find_column_section(structural.sections, member.section_id)
        width = float(section.width if section else 16.0)
        depth = float(section.depth if section else 16.0)
        entities.extend(_rectangle_symbol("COLUMNS", location.x, location.y, width, depth))
        layers["COLUMNS"] += 1

        level_name = levels.get(member.level_id or "", "")
        grid_ref = ""
        point = points.get(member.start_point_id or member.end_point_id or "")
        if point and point.grid_id:
            grid_ref = grids.get(point.grid_id, "")

        label_parts = [member.name]
        if section is not None:
            label_parts.append(section.name)
        if level_name:
            label_parts.append(level_name)
        if grid_ref:
            label_parts.append(f"Grid {grid_ref}")
        entities.extend(_text_entity("TEXT", location.x, location.y + depth / 2.0 + 1.0, " / ".join(label_parts)))
        layers["TEXT"] += 1

        entities.extend(
            _dimension_entity(
                "DIMENSIONS",
                location.x - width / 2.0,
                location.y - depth / 2.0 - 1.0,
                location.x + width / 2.0,
                location.y - depth / 2.0 - 1.0,
                f"{width:g}",
            )
        )
        layers["DIMENSIONS"] += 1

    capability_status = _capability_status(layers.get("COLUMNS", 0), missing)
    return _build_result(
        entities=entities,
        layers=layers,
        drawing_type=drawing_type,
        units=units,
        metadata={
            "column_count": len(column_members),
            "columns_drawn": layers.get("COLUMNS", 0),
            "capability_status": capability_status,
            "missing_data": missing,
        },
    )


def render_beam_plan_dxf(
    pem: ProjectEngineeringModel,
    *,
    drawing_type: str,
    units: str = "METERS",
) -> DxfRenderResult:
    structural = pem.structural_model
    points = _points_map(structural.geometry.points)
    levels = {level.id: level.name for level in structural.geometry.levels}
    support_points = {support.point_id for support in structural.supports}
    layers = {"GRID": 0, "BEAMS": 0, "SUPPORTS": 0, "TEXT": 0, "DIMENSIONS": 0}
    entities: list[str] = []
    missing: list[str] = []
    beam_members = sorted(
        [
            member
            for member in structural.members.members
            if member.member_type in {MemberType.BEAM, MemberType.BRACE}
        ],
        key=lambda item: item.id,
    )

    for line in sorted(structural.geometry.lines, key=lambda item: item.id):
        start = points.get(line.start_point_id)
        end = points.get(line.end_point_id)
        if start is None or end is None:
            continue
        entities.extend(_line_entity("GRID", start.x, start.y, end.x, end.y))
        layers["GRID"] += 1

    if not beam_members:
        missing.append("No beam members are defined in the engineering model")

    for member in beam_members:
        start, end = _member_endpoints(member, structural, points)
        if start is None or end is None:
            missing.append(f"Beam '{member.name}' has no centerline geometry")
            continue
        entities.extend(_line_entity("BEAMS", start.x, start.y, end.x, end.y))
        layers["BEAMS"] += 1

        span = ((end.x - start.x) ** 2 + (end.y - start.y) ** 2) ** 0.5
        section = _find_beam_section(structural.sections, member.section_id)
        depth = section.depth if section else None
        level_name = levels.get(member.level_id or "", "")

        label_parts = [member.name]
        if section is not None:
            label_parts.append(section.name)
        if depth is not None:
            label_parts.append(f"d={depth:g}")
        if level_name:
            label_parts.append(level_name)
        label_x = (start.x + end.x) / 2.0
        label_y = (start.y + end.y) / 2.0
        entities.extend(_text_entity("TEXT", label_x, label_y, " / ".join(label_parts)))
        layers["TEXT"] += 1

        entities.extend(
            _dimension_entity(
                "DIMENSIONS",
                start.x,
                start.y - 1.0,
                end.x,
                end.y - 1.0,
                f"{span:g}",
            )
        )
        layers["DIMENSIONS"] += 1

        for point_id in (member.start_point_id, member.end_point_id):
            if point_id and point_id in support_points:
                point = points.get(point_id)
                if point is not None:
                    entities.extend(_point_marker("SUPPORTS", point.x, point.y, "SUP"))
                    layers["SUPPORTS"] += 1

    capability_status = _capability_status(layers.get("BEAMS", 0), missing)
    return _build_result(
        entities=entities,
        layers=layers,
        drawing_type=drawing_type,
        units=units,
        metadata={
            "beam_count": len(beam_members),
            "beams_drawn": layers.get("BEAMS", 0),
            "capability_status": capability_status,
            "missing_data": missing,
        },
    )


def render_slab_plan_dxf(
    pem: ProjectEngineeringModel,
    *,
    drawing_type: str,
    units: str = "METERS",
) -> DxfRenderResult:
    structural = pem.structural_model
    points = _points_map(structural.geometry.points)
    levels = {level.id: level.name for level in structural.geometry.levels}
    layers = {"GRID": 0, "SLABS": 0, "TEXT": 0, "SUPPORTS": 0}
    entities: list[str] = []
    missing: list[str] = []

    for line in sorted(structural.geometry.lines, key=lambda item: item.id):
        start = points.get(line.start_point_id)
        end = points.get(line.end_point_id)
        if start is None or end is None:
            continue
        entities.extend(_line_entity("GRID", start.x, start.y, end.x, end.y))
        layers["GRID"] += 1

    slab_members = sorted(
        [member for member in structural.members.members if member.member_type == MemberType.SLAB],
        key=lambda item: item.id,
    )
    slab_areas = _resolve_slab_areas(structural.geometry.areas, slab_members)

    if not slab_areas:
        missing.append("Slab boundaries are not defined in the engineering model")

    for area, member in slab_areas:
        boundary = [points.get(point_id) for point_id in area.boundary_point_ids]
        if any(item is None for item in boundary):
            missing.append(f"Slab area '{area.id}' has incomplete boundary points")
            continue
        coords = [(point.x, point.y) for point in boundary if point is not None]
        entities.extend(_closed_polyline("SLABS", coords))
        layers["SLABS"] += 1

        section = _find_slab_section(structural.sections, member.section_id if member else "")
        thickness = section.thickness if section else None
        level_name = levels.get(area.level_id or (member.level_id if member else "") or "", "")
        centroid_x = sum(x for x, _ in coords) / len(coords)
        centroid_y = sum(y for _, y in coords) / len(coords)

        label_parts = [member.name if member else area.id]
        if section is not None:
            label_parts.append(section.name)
        if thickness is not None:
            label_parts.append(f"t={thickness:g}")
        if level_name:
            label_parts.append(level_name)
        entities.extend(_text_entity("TEXT", centroid_x, centroid_y, " / ".join(label_parts)))
        layers["TEXT"] += 1

        for column in sorted(
            [item for item in structural.members.members if item.member_type == MemberType.COLUMN],
            key=lambda item: item.id,
        ):
            location = _column_plan_location(column, points)
            if location is None:
                continue
            if _point_in_polygon(location.x, location.y, coords):
                entities.extend(_point_marker("SUPPORTS", location.x, location.y, column.name))
                layers["SUPPORTS"] += 1

    capability_status = _capability_status(layers.get("SLABS", 0), missing)
    return _build_result(
        entities=entities,
        layers=layers,
        drawing_type=drawing_type,
        units=units,
        metadata={
            "slab_area_count": len(slab_areas),
            "slabs_drawn": layers.get("SLABS", 0),
            "capability_status": capability_status,
            "missing_data": missing,
        },
    )


def _build_result(
    *,
    entities: list[str],
    layers: dict[str, int],
    drawing_type: str,
    units: str,
    metadata: dict[str, Any],
) -> DxfRenderResult:
    active_layers = [layer for layer, count in layers.items() if count > 0]
    header = _dxf_header(units)
    tables = _dxf_tables(active_layers or ["0"])
    body = "\n".join(entities)
    content = f"{header}{tables}0\nSECTION\n2\nENTITIES\n{body}0\nENDSEC\n0\nEOF\n"
    return DxfRenderResult(
        content=content,
        entity_count=len(entities),
        layer_summary=layers,
        metadata={
            "drawing_type": drawing_type,
            "units": units,
            **metadata,
        },
    )


def _capability_status(primary_count: int, missing: list[str]) -> str:
    if primary_count > 0 and not missing:
        return "COMPLETE"
    if primary_count > 0 and missing:
        return "PARTIAL"
    return "INCOMPLETE"


def _points_map(points: list[Any]) -> dict[str, Any]:
    return {point.id: point for point in points}


def _member_endpoints(member: StructuralMember, structural, points: dict[str, Any]):
    line = next((item for item in structural.geometry.lines if item.id == member.line_id), None)
    if line is not None:
        return points.get(line.start_point_id), points.get(line.end_point_id)
    start = points.get(member.start_point_id or "")
    end = points.get(member.end_point_id or "")
    return start, end


def _column_plan_location(member: StructuralMember, points: dict[str, Any]):
    if member.start_point_id and member.start_point_id in points:
        return points[member.start_point_id]
    if member.end_point_id and member.end_point_id in points:
        return points[member.end_point_id]
    return None


def _find_column_section(sections, section_id: str) -> ColumnSection | None:
    for section in sections.columns:
        if section.id == section_id:
            return section
    return None


def _find_beam_section(sections, section_id: str) -> BeamSection | None:
    for section in sections.beams:
        if section.id == section_id:
            return section
    return None


def _find_slab_section(sections, section_id: str) -> SlabSection | None:
    if not section_id:
        return None
    for section in sections.slabs:
        if section.id == section_id:
            return section
    return None


def _resolve_slab_areas(
    areas: list[AreaDefinition],
    slab_members: list[StructuralMember],
) -> list[tuple[AreaDefinition, StructuralMember | None]]:
    member_by_area = {member.area_id: member for member in slab_members if member.area_id}
    resolved: list[tuple[AreaDefinition, StructuralMember | None]] = []
    seen: set[str] = set()

    for member in slab_members:
        if member.area_id:
            area = next((item for item in areas if item.id == member.area_id), None)
            if area is not None and area.id not in seen:
                resolved.append((area, member))
                seen.add(area.id)

    for area in sorted(areas, key=lambda item: item.id):
        if area.id in seen:
            continue
        if len(area.boundary_point_ids) >= 3:
            member = member_by_area.get(area.id) or next(
                (item for item in slab_members if item.id == area.member_id),
                None,
            )
            if member is not None or area.member_id:
                resolved.append((area, member))
                seen.add(area.id)

    return resolved


def _point_in_polygon(x: float, y: float, polygon: list[tuple[float, float]]) -> bool:
    inside = False
    count = len(polygon)
    for index in range(count):
        x1, y1 = polygon[index]
        x2, y2 = polygon[(index + 1) % count]
        intersects = (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / ((y2 - y1) or 1e-9) + x1
        if intersects:
            inside = not inside
    return inside


def _dxf_header(units: str) -> str:
    return (
        "0\nSECTION\n2\nHEADER\n"
        "9\n$INSUNITS\n70\n6\n"
        f"9\n$PROJECT_UNITS\n1\n{units}\n"
        "0\nENDSEC\n"
    )


def _dxf_tables(layers: list[str]) -> str:
    rows = ["0\nSECTION\n2\nTABLES\n0\nTABLE\n2\nLAYER\n70\n{count}".format(count=len(layers))]
    for layer in layers:
        rows.extend(
            [
                "0\nLAYER",
                f"2\n{layer}",
                "70\n0",
                "62\n7",
                "6\nCONTINUOUS",
            ]
        )
    rows.append("0\nENDTAB\n0\nENDSEC")
    return "\n".join(rows) + "\n"


def _line_entity(layer: str, x1: float, y1: float, x2: float, y2: float) -> list[str]:
    return [
        "0\nLINE",
        f"8\n{layer}",
        f"10\n{x1}",
        f"20\n{y1}",
        f"30\n0.0",
        f"11\n{x2}",
        f"21\n{y2}",
        f"31\n0.0",
    ]


def _text_entity(layer: str, x: float, y: float, text: str) -> list[str]:
    safe = text.replace("\n", " ")
    return [
        "0\nTEXT",
        f"8\n{layer}",
        f"10\n{x}",
        f"20\n{y}",
        f"30\n0.0",
        "40\n0.5",
        f"1\n{safe}",
    ]


def _rectangle_symbol(layer: str, center_x: float, center_y: float, width: float, depth: float) -> list[str]:
    half_w = width / 2.0
    half_d = depth / 2.0
    corners = [
        (center_x - half_w, center_y - half_d),
        (center_x + half_w, center_y - half_d),
        (center_x + half_w, center_y + half_d),
        (center_x - half_w, center_y + half_d),
    ]
    entities: list[str] = []
    for index in range(4):
        x1, y1 = corners[index]
        x2, y2 = corners[(index + 1) % 4]
        entities.extend(_line_entity(layer, x1, y1, x2, y2))
    return entities


def _closed_polyline(layer: str, coords: list[tuple[float, float]]) -> list[str]:
    entities: list[str] = []
    for index in range(len(coords)):
        x1, y1 = coords[index]
        x2, y2 = coords[(index + 1) % len(coords)]
        entities.extend(_line_entity(layer, x1, y1, x2, y2))
    return entities


def _dimension_entity(layer: str, x1: float, y1: float, x2: float, y2: float, label: str) -> list[str]:
    mid_x = (x1 + x2) / 2.0
    mid_y = (y1 + y2) / 2.0
    entities = _line_entity(layer, x1, y1, x2, y2)
    entities.extend(_text_entity(layer, mid_x, mid_y - 0.5, label))
    return entities


def _point_marker(layer: str, x: float, y: float, label: str) -> list[str]:
    size = 0.75
    entities = _line_entity(layer, x - size, y, x + size, y)
    entities.extend(_line_entity(layer, x, y - size, x, y + size))
    entities.extend(_text_entity(layer, x + size, y + size, label))
    return entities
