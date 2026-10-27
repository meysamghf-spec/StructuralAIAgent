"""
Structural sheets S-001 to S-104, projected from the persisted PEM.

* **S-001** general notes — read out of PEM metadata, never authored here
* **S-101** foundation plan — the actual ``FoundationFooting`` set
* **S-102** column layout — one plan per storey of ``MemberType.COLUMN``
* **S-103** beam layout — one plan per storey of ``MemberType.BEAM``
* **S-104** slab layout — one plan per storey of ``MemberType.SLAB`` plus the
  diaphragm assignment taken from ``DiaphragmDefinition.node_ids``

Each sheet draws its *own* subject. The grid is underlay only: every sheet is
required to carry more building-fabric geometry than grid geometry, which the
regression tests assert. Member marks printed on the plans are grid references,
the way a real framing plan is marked; the full PEM member IDs travel in
``source_element_ids`` on every primitive so the backend can always answer which
PEM element produced a given piece of geometry.

No value is computed here. Section sizes, footing sizes, thicknesses, spans and
utilisations are read from the PEM, and anything the PEM does not hold is
reported as ``N/A — not available in PEM``.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from app.application.drawing.annotation import (
    LAYER_BEAMS,
    LAYER_COLUMNS,
    LAYER_DIAPHRAGM,
    LAYER_FOUNDATIONS,
    LAYER_NOTES,
    LAYER_OUTLINE,
    LAYER_SLABS,
)
from app.application.drawing.pem_solids import PemDrawingContext, Solid3D
from app.application.drawing.projection import project_plan
from app.application.drawing.sheet_builder import SheetBuildContext
from app.application.drawing.view_helpers import (
    ViewCanvas,
    add_overall_plan_dimensions,
    add_plan_grid,
)
from app.domain.models.pem import effective_unit_configuration
from app.domain.models.drawing import (
    Discipline,
    DrawingSheet,
    DrawingView,
    NOT_IN_PEM,
    ProjectionKind as PK,
    SheetAvailability,
    SourceElementKind,
)
from app.domain.models.pem_architecture import Point2D
from app.domain.models.pem_structural import MemberType

#: Layer used to show real elements that a drawing references for coordination
#: only — never to imply geometry the PEM does not hold (e.g. slab openings).
LAYER_COORDINATION = "COORDINATION"

# General-notes sheets are laid out in a fixed "note space" so every column of
# the sheet plots at the same text size.
_NOTE_COLUMN_W = 100.0
_NOTE_COLUMN_H = 170.0
_NOTE_TEXT_H = 2.3
_NOTE_LINE_SPACING = 3.5


def _fmt(value: object, *, suffix: str = "", digits: int = 3) -> str:
    """Format a PEM value, or say plainly that the PEM does not hold it."""
    if value is None or value == "":
        return NOT_IN_PEM
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (int, float)):
        return f"{float(value):.{digits}f}{suffix}".rstrip()
    return f"{value}{suffix}"


def _mm(value: float | None) -> str:
    return NOT_IN_PEM if value is None else f"{float(value) * 1000.0:.0f}"


def _predominant(values: list[str]) -> tuple[str, bool]:
    """
    The most common value and whether it is the *only* value.

    Dense per-level plans follow normal draughting practice: a property shared by
    every member on the view is stated once in a note and only the exceptions are
    tagged on the member. This keeps 36 columns or 60 beams legible at the plotted
    scale without hiding any variation.
    """
    if not values:
        return (NOT_IN_PEM, True)
    counts = Counter(values)
    winner, _ = counts.most_common(1)[0]
    return (winner, len(counts) == 1)


# ---------------------------------------------------------------------------
# S-001 Structural general notes
# ---------------------------------------------------------------------------


def build_structural_notes(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    structural = pem.structural
    report = pem.pem.engineering_report
    _units = effective_unit_configuration(pem.pem.unit_configuration, pem.pem.code_configuration)
    material_ids = [
        item.id
        for item in (
            *structural.materials.concrete,
            *structural.materials.reinforcement,
            *structural.materials.steel,
        )
    ]

    columns = [
        _notes_column(
            "S-001-V1",
            "General notes 1 of 3",
            [
                _NoteBlock(
                    "1. PROJECT INFORMATION",
                    [
                        f"Project name        {context.project_name}",
                        f"Project ID          {pem.pem.project_id}",
                        f"Source model ID     {context.source_model_id}",
                        f"Source snapshot ID  {_fmt(context.source_snapshot_id)}",
                        f"PEM version         {_fmt(context.pem_version, digits=0)}",
                        f"Lifecycle status    {pem.pem.lifecycle_status}",
                        f"Description         {_fmt(pem.pem.metadata.description)}",
                    ],
                    ref_ids=(context.source_model_id,),
                    ref_kind=SourceElementKind.PROJECT,
                ),
                _NoteBlock(
                    "2. STRUCTURAL SYSTEM",
                    [
                        f"System              {pem.building.structural_system.value}",
                        f"Declared system     {_fmt(pem.pem.structural_system.get('system'))}",
                        f"Lateral system      {_fmt(report.get('3_structural_system', {}).get('lateral'))}",
                        f"Storeys             {len(pem.plans)}",
                        f"Building height     {pem.building_height_m:.3f} m above lowest level",
                    ],
                    ref_ids=(context.source_model_id,),
                    ref_kind=SourceElementKind.PROJECT,
                ),
                _NoteBlock(
                    "3. UNITS",
                    [
                        f"Unit system         {_units.system.value}",
                        f"Length              {_units.length_unit}",
                        f"Force               {_units.force_unit}",
                        f"Moment              {_units.moment_unit}",
                        f"Stress              {_units.stress_unit}",
                        f"Drawing geometry    {context.units} (PEM coordinate frame)",
                    ],
                ),
                _NoteBlock(
                    "4. MATERIALS",
                    _material_lines(pem),
                    ref_ids=tuple(material_ids),
                    ref_kind=SourceElementKind.MATERIAL,
                ),
            ],
        ),
        _notes_column(
            "S-001-V2",
            "General notes 2 of 3",
            [
                _NoteBlock("5. DESIGN CODES", _code_lines(pem)),
                _NoteBlock("6. ANALYSIS METHOD", _analysis_lines(pem)),
                _NoteBlock(
                    "7. STRUCTURAL MODEL",
                    _model_lines(pem),
                    ref_ids=(pem.grid.id,) if pem.grid is not None else (),
                    ref_kind=SourceElementKind.GRID,
                ),
            ],
        ),
        _notes_column(
            "S-001-V3",
            "General notes 3 of 3",
            [
                _NoteBlock(
                    "8. LEVELS",
                    _level_lines(pem),
                    ref_ids=tuple(level.id for level in pem.levels_sorted),
                    ref_kind=SourceElementKind.LEVEL,
                ),
                _NoteBlock("9. LIMITATIONS", _wrap_all(context.limitations) or [NOT_IN_PEM]),
                _NoteBlock("10. CAPABILITY CLASSIFICATION", _classification_lines(pem)),
                _NoteBlock("11. DISCLAIMERS", _wrap_all(context.standard_notes())),
                _NoteBlock(
                    "12. DRAWING INDEX",
                    [f"{number}   {title}" for number, title in context.drawing_index]
                    or [NOT_IN_PEM],
                ),
            ],
        ),
    ]
    return context.build_sheet(
        sheet_number="S-001",
        title="Structural general notes",
        discipline=Discipline.STRUCTURAL,
        views=columns,
        columns=3,
        notes=[
            "All values on this sheet are read from the persisted PEM. Items the PEM "
            f"does not hold are shown as '{NOT_IN_PEM}'.",
            "No engineering value on this sheet was authored by the drawing engine.",
        ],
        metadata={
            "level_count": len(pem.levels_sorted),
            "member_count": len(structural.members.members),
            "footing_count": len(structural.footings),
            "diaphragm_count": len(structural.diaphragms),
        },
    )


@dataclass(frozen=True)
class _NoteBlock:
    """A headed block of general-notes lines, optionally traced to PEM elements."""

    heading: str
    lines: list[str] = field(default_factory=list)
    ref_ids: tuple[str, ...] = ()
    ref_kind: SourceElementKind = SourceElementKind.ANNOTATION


def _notes_column(view_id: str, name: str, blocks: list[_NoteBlock]) -> DrawingView:
    """One bordered column of general notes, rendered at a fixed text size."""
    canvas = ViewCanvas(
        view_id=view_id,
        name=name,
        projection=PK.NOTES,
        projection_label="NOTES",
        span_m=_NOTE_COLUMN_H,
        text_height_m=_NOTE_TEXT_H,
        metadata={"note_space": [_NOTE_COLUMN_W, _NOTE_COLUMN_H]},
    )
    # A fixed border gives every notes column identical bounds, so all three plot
    # at the same text size. It is draughting furniture, so it lives with the
    # annotations rather than counting as projected geometry.
    canvas.anno.primitives.append(
        canvas.factory.polygon(
            [
                Point2D(x=0.0, y=0.0),
                Point2D(x=_NOTE_COLUMN_W, y=0.0),
                Point2D(x=_NOTE_COLUMN_W, y=_NOTE_COLUMN_H),
                Point2D(x=0.0, y=_NOTE_COLUMN_H),
            ],
            layer=LAYER_NOTES,
            metadata={"role": "notes-border"},
        )
    )
    cursor = _NOTE_COLUMN_H - _NOTE_LINE_SPACING * 1.4
    for block in blocks:
        if block.heading:
            canvas.anno.note_block(
                Point2D(x=2.5, y=cursor),
                [block.heading],
                line_spacing_m=_NOTE_LINE_SPACING,
                scale=1.15,
            )
            cursor -= _NOTE_LINE_SPACING * 1.35
        if block.lines:
            canvas.anno.note_block(
                Point2D(x=4.0, y=cursor),
                block.lines,
                line_spacing_m=_NOTE_LINE_SPACING,
                source_element_ids=list(block.ref_ids),
                source_element_kind=block.ref_kind,
            )
            cursor -= _NOTE_LINE_SPACING * len(block.lines) + _NOTE_LINE_SPACING * 0.5
    canvas.view.metadata["note_space_used"] = round(
        (_NOTE_COLUMN_H - cursor) / _NOTE_COLUMN_H, 4
    )
    return canvas.finish()


def _material_lines(pem: PemDrawingContext) -> list[str]:
    lines: list[str] = []
    for item in pem.structural.materials.concrete:
        lines.append(f"Concrete {item.id}")
        lines.append(f"   f'c              {_fmt(item.compressive_strength, digits=1)} MPa")
        lines.append(f"   Ec               {_fmt(item.modulus_of_elasticity, digits=1)} MPa")
        lines.append(f"   Unit weight      {_fmt(item.unit_weight, digits=1)} kN/m3")
        lines.append(f"   Poisson ratio    {_fmt(item.poisson_ratio, digits=2)}")
    for item in pem.structural.materials.reinforcement:
        lines.append(f"Reinforcement {item.id}")
        lines.append(f"   fy               {_fmt(item.yield_strength, digits=1)} MPa")
        lines.append(f"   Es               {_fmt(item.modulus_of_elasticity, digits=1)} MPa")
    for item in pem.structural.materials.steel:
        lines.append(f"Structural steel {item.id}")
        lines.append(f"   fy               {_fmt(item.yield_strength, digits=1)} MPa")
    return lines or [NOT_IN_PEM]


def _code_lines(pem: PemDrawingContext) -> list[str]:
    code = pem.pem.code_configuration
    lines = [
        f"Profile type        {code.profile_type.value}",
        f"Jurisdiction        {code.jurisdiction.value}",
        f"Location            {_fmt(code.project_location)}",
        f"Building code       {code.governing_building_code.full_designation}",
        f"Loading standard    {code.loading_standard.full_designation}",
        f"Seismic standard    {code.seismic_standard.full_designation if code.seismic_standard else NOT_IN_PEM}",
        f"Concrete standard   {code.concrete_standard.full_designation}",
        f"Steel standard      {code.steel_standard.full_designation}",
        f"Compatibility       {code.compatibility_status.value}",
        f"Configuration       {code.status.value}",
    ]
    if pem.pem.code_compliance:
        lines.append("Implementation status")
        lines.extend(
            f"   {name:<17} {status}" for name, status in sorted(pem.pem.code_compliance.items())
        )
    return _wrap_all(lines)


def _analysis_lines(pem: PemDrawingContext) -> list[str]:
    configuration = pem.structural.analysis_model.configuration
    report = pem.pem.engineering_report.get("10_analysis_method") or {}
    lines = [
        f"Solver              {_fmt(configuration.get('solver'))}",
        f"Decomposition       {_fmt(configuration.get('decomposition'))}",
        f"Capability status   {pem.structural.analysis_model.capability_status}",
        f"Last status         {_fmt(configuration.get('last_analysis_status'))}",
        f"Peak displacement   {_fmt(configuration.get('max_abs_displacement_m'), digits=6)} m",
        f"Elements solved     {_fmt(configuration.get('member_demand_count'), digits=0)}",
        f"Load cases          {len(pem.structural.load_cases)}",
        f"Load combinations   {len(pem.structural.load_combinations)}",
    ]
    assumptions = report.get("assumptions") if isinstance(report, dict) else None
    if isinstance(assumptions, list) and assumptions:
        lines.append("Analysis assumptions")
        lines.extend(f"   {item}" for item in assumptions)
    return _wrap_all(lines)


def _model_lines(pem: PemDrawingContext) -> list[str]:
    structural = pem.structural
    counts = {
        "Grids": len(structural.geometry.grids),
        "Levels": len(structural.geometry.levels),
        "Nodes": len(structural.geometry.points),
        "Lines": len(structural.geometry.lines),
        "Areas": len(structural.geometry.areas),
        "Columns": len(pem.members_by_type.get(MemberType.COLUMN, [])),
        "Beams": len(pem.members_by_type.get(MemberType.BEAM, [])),
        "Slabs": len(pem.members_by_type.get(MemberType.SLAB, [])),
        "Walls": len(pem.members_by_type.get(MemberType.WALL, [])),
        "Footings": len(structural.footings),
        "Diaphragms": len(structural.diaphragms),
        "Supports": len(structural.supports),
        "Design checks": len(structural.design_checks),
        "Reinforcement sets": len(structural.reinforcement),
    }
    lines = [f"{name:<19} {value}" for name, value in counts.items()]
    lines.append("Sections")
    for section in structural.sections.columns:
        lines.append(f"   Column {section.name:<10} {_mm(section.width)}x{_mm(section.depth)} mm")
    for section in structural.sections.beams:
        lines.append(f"   Beam   {section.name:<10} {_mm(section.width)}x{_mm(section.depth)} mm")
    for section in structural.sections.slabs:
        lines.append(f"   Slab   {section.name:<10} t={_mm(section.thickness)} mm")
    if not structural.sections.foundations:
        lines.append(f"   Foundation sections  {NOT_IN_PEM}")
        lines.append("      (footing sizes are held on the footing entities)")
    if pem.grid is not None:
        lines.append("Grid")
        lines.append(f"   X labels  {', '.join(pem.grid_x_labels) or NOT_IN_PEM}")
        lines.append(f"   X ordinates {', '.join(f'{v:g}' for v in pem.grid_x) or NOT_IN_PEM}")
        lines.append(f"   Y labels  {', '.join(pem.grid_y_labels) or NOT_IN_PEM}")
        lines.append(f"   Y ordinates {', '.join(f'{v:g}' for v in pem.grid_y) or NOT_IN_PEM}")
    return _wrap_all(lines)


def _level_lines(pem: PemDrawingContext) -> list[str]:
    lines = [f"{'Level':<8}{'Elev m':<10}{'Type':<14}{'Storey h':<10}"]
    for level in pem.levels_sorted:
        plan = pem.plan_by_level.get(level.id)
        lines.append(
            f"{level.id:<8}{level.elevation:<10.3f}"
            f"{str(level.metadata.get('floor_type', NOT_IN_PEM)):<14}"
            f"{_fmt(level.metadata.get('storey_height_m')):<10}"
        )
        if plan is not None:
            lines.append(f"   {plan.name} — gross {plan.gross_area_m2:.2f} m²")
    return lines


def _classification_lines(pem: PemDrawingContext) -> list[str]:
    classification = pem.pem.engineering_report.get("classification")
    if not isinstance(classification, dict):
        return [NOT_IN_PEM]
    lines: list[str] = []
    for key in ("IMPLEMENTED", "PRELIMINARY", "NOT_CHECKED"):
        values = classification.get(key)
        if isinstance(values, list) and values:
            lines.append(f"{key}:")
            lines.extend(_wrap_all([f"   {item}" for item in values]))
    if classification.get("REQUIRES_ENGINEER_REVIEW"):
        lines.append("REQUIRES_ENGINEER_REVIEW: Yes")
    return lines or [NOT_IN_PEM]


def _wrap_all(lines: list[str], width: int = 56) -> list[str]:
    """Soft-wrap long note lines, keeping the indent of the first line."""
    wrapped: list[str] = []
    for line in lines:
        text = str(line)
        if len(text) <= width:
            wrapped.append(text)
            continue
        indent = " " * (len(text) - len(text.lstrip()) + 3)
        current = ""
        for word in text.split(" "):
            candidate = f"{current} {word}".strip() if current else word
            if len(candidate) > width and current:
                wrapped.append(current)
                current = indent + word
            else:
                current = candidate
        if current:
            wrapped.append(current)
    return wrapped


# ---------------------------------------------------------------------------
# Shared plan scaffolding for S-101..S-104
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _PlanFrame:
    bounds: tuple[float, float, float, float]
    span: float


def _plan_frame(pem: PemDrawingContext) -> _PlanFrame:
    bounds = pem.footprint_bounds
    min_x, min_y, max_x, max_y = bounds
    return _PlanFrame(bounds=bounds, span=max(max_x - min_x, max_y - min_y, 1.0))


def _structural_plan_canvas(
    pem: PemDrawingContext,
    *,
    view_id: str,
    name: str,
    level_id: str | None,
    metadata: dict,
) -> tuple[ViewCanvas, _PlanFrame]:
    """A plan canvas with the floor outline and the grid underlay in place."""
    frame = _plan_frame(pem)
    canvas = ViewCanvas(
        view_id=view_id,
        name=name,
        projection=PK.PLAN,
        projection_label=f"PLAN:{level_id}" if level_id else "PLAN:FOUNDATION",
        span_m=frame.span,
        source_level_ids=[level_id] if level_id else [],
        metadata=metadata,
    )
    plan = pem.plan_by_level.get(level_id or "")
    if plan is not None and len(plan.boundary.points) >= 3:
        canvas.add_ring(
            plan.boundary,
            layer=LAYER_OUTLINE,
            source_element_ids=[plan.id],
            source_element_kind=SourceElementKind.LEVEL,
            metadata={"role": "floor-outline", "gross_area_m2": plan.gross_area_m2},
        )
    return canvas, frame


def _finish_structural_plan(
    canvas: ViewCanvas,
    pem: PemDrawingContext,
    frame: _PlanFrame,
    *,
    level_id: str | None,
    title: str,
    overall_ref_ids: list[str],
    overall_ref_kind: SourceElementKind,
) -> DrawingView:
    """Grid, bay dimensions, overall dimensions and the view title."""
    add_plan_grid(canvas, pem, bounds=frame.bounds)
    add_overall_plan_dimensions(
        canvas,
        bounds=frame.bounds,
        source_element_ids=overall_ref_ids,
        source_element_kind=overall_ref_kind,
    )
    min_x, min_y, max_x, max_y = frame.bounds
    canvas.anno.north_arrow(
        Point2D(x=max_x + frame.span * 0.13, y=max_y - frame.span * 0.04), frame.span * 0.055
    )
    elevation = pem.level_elevation(level_id) if level_id else None
    heading = title if elevation is None else f"{title}   (+{elevation:.3f} m)"
    canvas.anno.element_label(
        Point2D(x=(min_x + max_x) / 2.0, y=max_y + frame.span * 0.16),
        heading,
        source_element_ids=[level_id] if level_id else [],
        source_element_kind=SourceElementKind.LEVEL,
        scale=1.5,
    )
    return canvas.finish()


def _level_view_title(pem: PemDrawingContext, level_id: str) -> str:
    """``LEVEL L1 — Residential floor 1`` style heading required for level views."""
    level = pem.levels.get(level_id)
    plan = pem.plan_by_level.get(level_id)
    floor_type = str(level.metadata.get("floor_type", "")) if level else ""
    prefix = "ROOF" if floor_type == "ROOF" else f"LEVEL {level_id}"
    name = plan.name if plan is not None else (level.name if level else level_id)
    return f"{prefix} — {name}"


def _member_levels(pem: PemDrawingContext, member_type: MemberType) -> list[str]:
    """Level IDs that actually carry members of this type, in elevation order."""
    present = {
        member.level_id
        for member in pem.members_by_type.get(member_type, [])
        if member.level_id
    }
    ordered = [level.id for level in pem.levels_sorted if level.id in present]
    # Any member level missing from the level table still gets a view.
    ordered.extend(sorted(present - set(ordered)))
    return ordered


# ---------------------------------------------------------------------------
# S-101 Foundation plan
# ---------------------------------------------------------------------------


def build_foundation_plan(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    footings = pem.footing_solids()
    if not footings:
        return context.unavailable_sheet(
            sheet_number="S-101",
            title="Foundation plan",
            discipline=Discipline.STRUCTURAL,
            reason="PEM contains no foundation elements (structural_model.footings is empty)",
        )

    level_ids = sorted({solid.level_id for solid in footings if solid.level_id})
    foundation_level = level_ids[0] if level_ids else None
    canvas, frame = _structural_plan_canvas(
        pem,
        view_id="S-101-V1",
        name="Foundation plan",
        level_id=foundation_level,
        metadata={
            "footing_count": len(footings),
            "foundation_level_ids": level_ids,
        },
    )

    # One dimension pair per distinct footing size keeps 36 footings readable
    # while still dimensioning every size that occurs.
    dimensioned_sizes: set[tuple[float, float]] = set()
    size_groups: dict[tuple[float, float, float], list[str]] = {}

    for solid in footings:
        length = float(solid.metadata["length_m"])
        width = float(solid.metadata["width_m"])
        thickness = float(solid.metadata["thickness_m"])
        column_id = str(solid.metadata.get("column_member_id") or "")
        grid_label = str(solid.metadata.get("grid_label") or "")
        grid_reference = grid_label or pem.grid_reference(
            float(solid.metadata["x"]), float(solid.metadata["y"])
        )
        size_groups.setdefault((length, width, thickness), []).append(solid.element_id)

        canvas.add_projected(
            project_plan([solid], projection_label=canvas.factory.projection),
            layer=LAYER_FOUNDATIONS,
            metadata_keys=(
                "column_member_id",
                "grid_label",
                "point_id",
                "length_m",
                "width_m",
                "thickness_m",
                "top_elevation_m",
                "underside_elevation_m",
                "utilization",
                "status",
                "bearing_demand_kPa",
                "bearing_capacity_kPa",
            ),
        )

        # The column the footing carries, so the association is visible.
        column = pem.members.get(column_id)
        centre = Point2D(x=float(solid.metadata["x"]), y=float(solid.metadata["y"]))
        if column is not None:
            section = pem.column_sections.get(column.section_id)
            if section is not None:
                canvas.add_polygon(
                    _rect(centre, float(section.width), float(section.depth)),
                    layer=LAYER_COLUMNS,
                    source_element_ids=[column.id],
                    source_element_kind=SourceElementKind.COLUMN,
                    metadata={
                        "role": "column-over-footing",
                        "footing_id": solid.element_id,
                        "section": section.name,
                        "level_id": column.level_id,
                    },
                )

        step = canvas.text_height_m
        canvas.anno.element_label(
            Point2D(x=centre.x, y=centre.y + width / 2.0 + step * 1.3),
            solid.element_id,
            source_element_ids=[solid.element_id],
            source_element_kind=SourceElementKind.FOOTING,
            layer=LAYER_FOUNDATIONS,
            scale=0.95,
        )
        canvas.anno.element_label(
            Point2D(x=centre.x, y=centre.y - width / 2.0 - step * 1.4),
            f"{_mm(length)}x{_mm(width)}x{_mm(thickness)}",
            source_element_ids=[solid.element_id],
            source_element_kind=SourceElementKind.FOOTING,
            layer=LAYER_FOUNDATIONS,
            scale=0.85,
        )
        # The label reports the column it carries; the reference stays typed as the
        # footing so a column ID is never recorded under the FOOTING kind.
        canvas.anno.element_label(
            Point2D(x=centre.x, y=centre.y - width / 2.0 - step * 2.7),
            f"{grid_reference or NOT_IN_PEM} / {column_id or NOT_IN_PEM}",
            source_element_ids=[solid.element_id],
            source_element_kind=SourceElementKind.FOOTING,
            layer=LAYER_FOUNDATIONS,
            scale=0.8,
        )

        size_key = (length, width)
        if size_key not in dimensioned_sizes:
            dimensioned_sizes.add(size_key)
            canvas.anno.dimension(
                Point2D(x=centre.x - length / 2.0, y=centre.y - width / 2.0),
                Point2D(x=centre.x + length / 2.0, y=centre.y - width / 2.0),
                offset_m=-canvas.text_height_m * 4.0,
                source_element_ids=[solid.element_id],
                source_element_kind=SourceElementKind.FOOTING,
            )
            canvas.anno.dimension(
                Point2D(x=centre.x + length / 2.0, y=centre.y - width / 2.0),
                Point2D(x=centre.x + length / 2.0, y=centre.y + width / 2.0),
                offset_m=-canvas.text_height_m * 4.0,
                source_element_ids=[solid.element_id],
                source_element_kind=SourceElementKind.FOOTING,
            )

    top = footings[0].max_z
    underside = min(solid.min_z for solid in footings)
    view = _finish_structural_plan(
        canvas,
        pem,
        frame,
        level_id=foundation_level,
        title=f"FOUNDATION PLAN — {_level_view_title(pem, foundation_level) if foundation_level else 'foundation level'}",
        overall_ref_ids=[solid.element_id for solid in footings],
        overall_ref_kind=SourceElementKind.FOOTING,
    )

    size_summary = ", ".join(
        f"{_mm(length)}x{_mm(width)}x{_mm(thickness)} mm ({len(ids)} off)"
        for (length, width, thickness), ids in sorted(size_groups.items())
    )
    statuses = sorted({str(solid.metadata.get("status")) for solid in footings})
    return context.build_sheet(
        sheet_number="S-101",
        title="Foundation plan",
        discipline=Discipline.STRUCTURAL,
        views=[view],
        notes=[
            f"{len(footings)} isolated footings read from the PEM foundation set.",
            f"Footing sizes: {size_summary}.",
            f"Footing top at +{top:.3f} m; underside at {underside:.3f} m, derived as the "
            "footing top elevation minus its PEM thickness.",
            "Excavation depth, blinding, soil profile and lap details are not modelled "
            f"in the PEM ({NOT_IN_PEM}).",
            f"Footing bearing check status present in the PEM: {', '.join(statuses)}. "
            "Status is reported as held in the PEM and is not upgraded here.",
            "Footing dimensions are annotated on every footing; dimension lines are "
            "drawn once per distinct footing size.",
            "Column marks are grid references. Full PEM member IDs are carried in the "
            "drawing element references.",
        ],
        metadata={
            "footing_count": len(footings),
            "footing_ids": [solid.element_id for solid in footings],
            "distinct_sizes": len(size_groups),
            "foundation_level_ids": level_ids,
            "underside_elevation_m": underside,
        },
    )


def _rect(centre: Point2D, width: float, depth: float) -> list[Point2D]:
    half_w = width / 2.0
    half_d = depth / 2.0
    return [
        Point2D(x=centre.x - half_w, y=centre.y - half_d),
        Point2D(x=centre.x + half_w, y=centre.y - half_d),
        Point2D(x=centre.x + half_w, y=centre.y + half_d),
        Point2D(x=centre.x - half_w, y=centre.y + half_d),
    ]


# ---------------------------------------------------------------------------
# S-102 Column layout
# ---------------------------------------------------------------------------


def build_column_layout(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    level_ids = _member_levels(pem, MemberType.COLUMN)
    if not level_ids:
        return context.unavailable_sheet(
            sheet_number="S-102",
            title="Column layout",
            discipline=Discipline.STRUCTURAL,
            reason="PEM contains no column members",
        )

    views: list[DrawingView] = []
    total = 0
    sections_used: set[str] = set()
    for level_id in level_ids:
        solids = pem.column_solids(level_ids={level_id})
        if not solids:
            continue
        total += len(solids)
        views.append(_column_level_view(context, level_id=level_id, solids=solids))
        sections_used.update(str(solid.metadata.get("section")) for solid in solids)

    orientation_known = any(
        solid.metadata.get("orientation_deg") not in (None, NOT_IN_PEM)
        for level_id in level_ids
        for solid in pem.column_solids(level_ids={level_id})
    )
    return context.build_sheet(
        sheet_number="S-102",
        title="Column layout",
        discipline=Discipline.STRUCTURAL,
        views=views,
        notes=[
            f"{total} column members across {len(views)} storeys, one plan per storey. "
            "Storeys are not merged.",
            f"Column sections used: {', '.join(sorted(sections_used)) or NOT_IN_PEM}.",
            "Each column is drawn at its PEM section size, centred on its PEM node.",
            (
                "Column orientation is taken from the PEM."
                if orientation_known
                else f"Column rotation is not stored in the PEM ({NOT_IN_PEM}); sections are "
                "drawn axis-aligned."
            ),
            "Columns bearing directly on a footing are annotated with that footing ID.",
            "Column marks are grid references. Full PEM member IDs (COL-<level>-<mark>) "
            "are carried in the drawing element references.",
        ],
        metadata={
            "column_count": total,
            "level_ids": level_ids,
            "view_level_ids": [view.source_level_ids[0] for view in views if view.source_level_ids],
        },
    )


def _column_level_view(
    context: SheetBuildContext,
    *,
    level_id: str,
    solids: list[Solid3D],
) -> DrawingView:
    pem = context.pem
    canvas, frame = _structural_plan_canvas(
        pem,
        view_id=f"S-102-{level_id}",
        name=_level_view_title(pem, level_id),
        level_id=level_id,
        metadata={
            "level_id": level_id,
            "elevation_m": pem.level_elevation(level_id),
            "column_count": len(solids),
        },
    )
    canvas.add_projected(
        project_plan(solids, projection_label=canvas.factory.projection),
        layer=LAYER_COLUMNS,
        metadata_keys=(
            "section",
            "section_id",
            "width_m",
            "depth_m",
            "node_id",
            "x",
            "y",
            "orientation_deg",
        ),
    )
    step = canvas.text_height_m
    typical_section, section_uniform = _predominant(
        [str(solid.metadata.get("section") or NOT_IN_PEM) for solid in solids]
    )
    for solid in solids:
        centre = Point2D(x=float(solid.metadata["x"]), y=float(solid.metadata["y"]))
        half_depth = float(solid.metadata["depth_m"]) / 2.0
        canvas.anno.element_label(
            Point2D(x=centre.x, y=centre.y + half_depth + step * 1.2),
            solid.label,
            source_element_ids=[solid.element_id],
            source_element_kind=SourceElementKind.COLUMN,
            layer=LAYER_COLUMNS,
        )
        section = str(solid.metadata.get("section") or NOT_IN_PEM)
        if section != typical_section:
            canvas.anno.element_label(
                Point2D(x=centre.x, y=centre.y - half_depth - step * 1.3),
                section,
                source_element_ids=[solid.element_id],
                source_element_kind=SourceElementKind.COLUMN,
                layer=LAYER_COLUMNS,
                scale=0.8,
            )
        # Foundation relationship, only on the storey that actually bears on footings.
        footing = pem.footing_by_column.get(solid.element_id)
        if footing is not None:
            canvas.anno.element_label(
                Point2D(x=centre.x, y=centre.y - half_depth - step * 1.4),
                footing.id,
                source_element_ids=[footing.id],
                source_element_kind=SourceElementKind.FOOTING,
                layer=LAYER_FOUNDATIONS,
                scale=0.7,
            )
    canvas.anno.note_block(
        Point2D(x=frame.bounds[0], y=frame.bounds[1] - frame.span * 0.20),
        [
            f"Columns are {typical_section} unless marked otherwise."
            if section_uniform
            else f"Typical column {typical_section}; sections differing from typical are marked.",
            f"Column marks are grid references; PEM member IDs are COL-{level_id}-<mark>.",
        ],
        line_spacing_m=step * 1.6,
        layer=LAYER_COLUMNS,
        scale=0.95,
        source_element_ids=[solid.element_id for solid in solids],
        source_element_kind=SourceElementKind.COLUMN,
    )
    return _finish_structural_plan(
        canvas,
        pem,
        frame,
        level_id=level_id,
        title=f"COLUMN LAYOUT — {_level_view_title(pem, level_id)}",
        overall_ref_ids=[solid.element_id for solid in solids],
        overall_ref_kind=SourceElementKind.COLUMN,
    )


# ---------------------------------------------------------------------------
# S-103 Beam layout
# ---------------------------------------------------------------------------


def build_beam_layout(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    level_ids = _member_levels(pem, MemberType.BEAM)
    if not level_ids:
        return context.unavailable_sheet(
            sheet_number="S-103",
            title="Beam layout",
            discipline=Discipline.STRUCTURAL,
            reason="PEM contains no beam members",
        )

    views: list[DrawingView] = []
    total = 0
    sections_used: set[str] = set()
    for level_id in level_ids:
        solids = pem.beam_solids(level_ids={level_id})
        if not solids:
            continue
        total += len(solids)
        views.append(_beam_level_view(context, level_id=level_id, solids=solids))
        sections_used.update(str(solid.metadata.get("section")) for solid in solids)

    return context.build_sheet(
        sheet_number="S-103",
        title="Beam layout",
        discipline=Discipline.STRUCTURAL,
        views=views,
        notes=[
            f"{total} beam members across {len(views)} storeys, one framing plan per storey.",
            f"Beam sections used: {', '.join(sorted(sections_used)) or NOT_IN_PEM}.",
            "Beams are drawn as their PEM section width swept along the member "
            "centreline between its start and end nodes; the centreline is drawn over it.",
            "Support nodes mark beam-to-column connections taken from shared PEM nodes.",
            "Beam openings and penetrations are not modelled in the PEM "
            f"({NOT_IN_PEM}).",
            "Beam marks are section mark and clear grid span. Full PEM member IDs "
            "are carried in the drawing element references.",
        ],
        metadata={
            "beam_count": total,
            "level_ids": level_ids,
            "view_level_ids": [view.source_level_ids[0] for view in views if view.source_level_ids],
        },
    )


def _beam_level_view(
    context: SheetBuildContext,
    *,
    level_id: str,
    solids: list[Solid3D],
) -> DrawingView:
    pem = context.pem
    canvas, frame = _structural_plan_canvas(
        pem,
        view_id=f"S-103-{level_id}",
        name=_level_view_title(pem, level_id),
        level_id=level_id,
        metadata={
            "level_id": level_id,
            "elevation_m": pem.level_elevation(level_id),
            "beam_count": len(solids),
        },
    )

    canvas.add_projected(
        project_plan(solids, projection_label=canvas.factory.projection),
        layer=LAYER_BEAMS,
        metadata_keys=(
            "section",
            "section_id",
            "width_m",
            "depth_m",
            "direction",
            "span_m",
            "start_point_id",
            "end_point_id",
            "grid_from",
            "grid_to",
        ),
    )

    step = canvas.text_height_m
    typical_section, section_uniform = _predominant(
        [str(solid.metadata.get("section") or NOT_IN_PEM) for solid in solids]
    )
    support_nodes: dict[str, tuple[float, float]] = {}
    for solid in solids:
        start = solid.metadata.get("start")
        end = solid.metadata.get("end")
        if not start or not end:
            continue
        start_point = Point2D(x=start[0], y=start[1])
        end_point = Point2D(x=end[0], y=end[1])
        canvas.add(
            canvas.factory.line(
                start_point,
                end_point,
                layer=LAYER_BEAMS,
                source_element_ids=[solid.element_id],
                source_element_kind=SourceElementKind.BEAM,
                metadata={
                    "role": "beam-centreline",
                    "start_point_id": solid.metadata.get("start_point_id"),
                    "end_point_id": solid.metadata.get("end_point_id"),
                    "span_m": solid.metadata.get("span_m"),
                    "section": solid.metadata.get("section"),
                },
            )
        )
        for point_id, coords in (
            (solid.metadata.get("start_point_id"), start),
            (solid.metadata.get("end_point_id"), end),
        ):
            if isinstance(point_id, str):
                support_nodes[point_id] = coords

        # Beam mark along the member: span always, section only when it is not the
        # typical section for this framing plan.
        midpoint = Point2D(x=(start[0] + end[0]) / 2.0, y=(start[1] + end[1]) / 2.0)
        rotation = 90.0 if str(solid.metadata.get("direction")) == "Y" else 0.0
        span = solid.metadata.get("span_m")
        section = str(solid.metadata.get("section") or NOT_IN_PEM)
        span_text = f"{float(span):.2f}" if isinstance(span, (int, float)) else NOT_IN_PEM
        mark = span_text if section == typical_section else f"{section}/{span_text}"
        offset = step * 1.0
        canvas.anno.primitives.append(
            canvas.factory.text(
                Point2D(
                    x=midpoint.x + (offset if rotation else 0.0),
                    y=midpoint.y + (0.0 if rotation else offset),
                ),
                mark,
                layer=LAYER_BEAMS,
                height_m=step * 0.85,
                rotation_deg=rotation,
                source_element_ids=[solid.element_id],
                source_element_kind=SourceElementKind.BEAM,
                metadata={
                    "role": "beam-mark",
                    "section": section,
                    "span_m": span,
                    "grid_from": solid.metadata.get("grid_from"),
                    "grid_to": solid.metadata.get("grid_to"),
                },
            )
        )

    # Beam-to-column relationships: mark every beam node that a column also
    # occupies. Columns are matched on both ends, so the roof framing plan picks
    # up the columns arriving from the storey below.
    column_nodes: dict[str, list[str]] = {}
    for column in pem.column_solids():
        for key in ("node_id", "top_node_id"):
            node_id = column.metadata.get(key)
            if isinstance(node_id, str):
                column_nodes.setdefault(node_id, []).append(column.element_id)
    for point_id, coords in sorted(support_nodes.items()):
        columns = column_nodes.get(point_id)
        if not columns:
            continue
        canvas.add_many(
            _node_marker(
                canvas,
                Point2D(x=coords[0], y=coords[1]),
                size=step * 1.1,
                source_element_ids=[point_id],
                metadata={
                    "role": "beam-column-node",
                    "point_id": point_id,
                    "column_member_ids": sorted(columns),
                },
            )
        )

    canvas.anno.note_block(
        Point2D(x=frame.bounds[0], y=frame.bounds[1] - frame.span * 0.20),
        [
            f"Beams are {typical_section} unless marked otherwise."
            if section_uniform
            else f"Typical beam {typical_section}; sections differing from typical are marked.",
            "Beam marks give the clear grid span in metres.",
            f"PEM member IDs are B<direction>-{level_id}-<from>-<to>.",
        ],
        line_spacing_m=step * 1.6,
        layer=LAYER_BEAMS,
        scale=0.95,
        source_element_ids=[solid.element_id for solid in solids],
        source_element_kind=SourceElementKind.BEAM,
    )
    return _finish_structural_plan(
        canvas,
        pem,
        frame,
        level_id=level_id,
        title=f"BEAM LAYOUT — {_level_view_title(pem, level_id)}",
        overall_ref_ids=[solid.element_id for solid in solids],
        overall_ref_kind=SourceElementKind.BEAM,
    )


def _node_marker(
    canvas: ViewCanvas,
    centre: Point2D,
    *,
    size: float,
    source_element_ids: list[str],
    metadata: dict,
) -> list:
    common = {
        "layer": LAYER_COLUMNS,
        "source_element_ids": source_element_ids,
        "source_element_kind": SourceElementKind.NODE,
        "metadata": metadata,
    }
    return [
        canvas.factory.line(
            Point2D(x=centre.x - size, y=centre.y),
            Point2D(x=centre.x + size, y=centre.y),
            **common,
        ),
        canvas.factory.line(
            Point2D(x=centre.x, y=centre.y - size),
            Point2D(x=centre.x, y=centre.y + size),
            **common,
        ),
    ]


# ---------------------------------------------------------------------------
# S-104 Slab layout
# ---------------------------------------------------------------------------


def build_slab_layout(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    level_ids = _member_levels(pem, MemberType.SLAB)
    if not level_ids:
        return context.unavailable_sheet(
            sheet_number="S-104",
            title="Slab layout",
            discipline=Discipline.STRUCTURAL,
            reason="PEM contains no slab members",
        )

    views: list[DrawingView] = []
    total = 0
    thicknesses: set[str] = set()
    diaphragm_ids: list[str] = []
    for level_id in level_ids:
        solids = pem.slab_solids(level_ids={level_id})
        if not solids:
            continue
        total += len(solids)
        diaphragm = pem.diaphragm_by_level.get(level_id)
        if diaphragm is not None:
            diaphragm_ids.append(diaphragm.id)
        views.append(_slab_level_view(context, level_id=level_id, solids=solids))
        thicknesses.update(_mm(solid.metadata.get("thickness_m")) for solid in solids)

    unassigned = [level_id for level_id in level_ids if level_id not in pem.diaphragm_by_level]
    return context.build_sheet(
        sheet_number="S-104",
        title="Slab layout and diaphragm assignment",
        discipline=Discipline.STRUCTURAL,
        views=views,
        notes=[
            f"{total} slab panels across {len(views)} storeys, one plan per storey.",
            f"Slab thickness from the PEM: {', '.join(sorted(thicknesses)) or NOT_IN_PEM} mm.",
            "Panel outlines are the PEM area boundaries, drawn through their own "
            "boundary nodes.",
            f"Diaphragms shown: {', '.join(diaphragm_ids) or NOT_IN_PEM}. The diaphragm "
            "outline is the extent of the nodes the PEM actually assigns to it, each "
            "assigned node is ticked, and the centre of mass is the PEM value.",
            (
                f"Levels with slabs but no diaphragm: {', '.join(unassigned)}."
                if unassigned
                else "Every slab level carries a diaphragm assignment."
            ),
            "Slab openings are not modelled in the PEM "
            f"({NOT_IN_PEM}). Stair and shaft outlines are shown on the "
            f"{LAYER_COORDINATION} layer for coordination only and are not openings.",
            "Supporting beams and columns are shown as underlay.",
            "Panel marks are grid panel references. Full PEM member IDs are carried "
            "in the drawing element references.",
        ],
        metadata={
            "slab_count": total,
            "level_ids": level_ids,
            "diaphragm_ids": diaphragm_ids,
            "levels_without_diaphragm": unassigned,
            "view_level_ids": [view.source_level_ids[0] for view in views if view.source_level_ids],
        },
    )


def _slab_level_view(
    context: SheetBuildContext,
    *,
    level_id: str,
    solids: list[Solid3D],
) -> DrawingView:
    pem = context.pem
    diaphragm = pem.diaphragm_by_level.get(level_id)
    canvas, frame = _structural_plan_canvas(
        pem,
        view_id=f"S-104-{level_id}",
        name=_level_view_title(pem, level_id),
        level_id=level_id,
        metadata={
            "level_id": level_id,
            "elevation_m": pem.level_elevation(level_id),
            "slab_count": len(solids),
            "diaphragm_id": diaphragm.id if diaphragm else NOT_IN_PEM,
        },
    )

    # Supporting members as underlay.
    for beam in pem.beam_solids(level_ids={level_id}):
        start = beam.metadata.get("start")
        end = beam.metadata.get("end")
        if not start or not end:
            continue
        canvas.add(
            canvas.factory.line(
                Point2D(x=start[0], y=start[1]),
                Point2D(x=end[0], y=end[1]),
                layer=LAYER_BEAMS,
                source_element_ids=[beam.element_id],
                source_element_kind=SourceElementKind.BEAM,
                metadata={"role": "supporting-beam", "section": beam.metadata.get("section")},
            )
        )
    for column in pem.column_solids(level_ids={level_id}):
        canvas.add_polygon(
            list(column.footprint),
            layer=LAYER_COLUMNS,
            source_element_ids=[column.element_id],
            source_element_kind=SourceElementKind.COLUMN,
            metadata={"role": "supporting-column", "section": column.metadata.get("section")},
        )

    # Slab panels.
    canvas.add_projected(
        project_plan(solids, projection_label=canvas.factory.projection),
        layer=LAYER_SLABS,
        metadata_keys=(
            "area_id",
            "section",
            "section_id",
            "thickness_m",
            "span_x_m",
            "span_y_m",
            "area_m2",
            "diaphragm_id",
            "boundary_point_ids",
        ),
    )
    step = canvas.text_height_m
    typical_thickness, thickness_uniform = _predominant(
        [_mm(solid.metadata.get("thickness_m")) for solid in solids]
    )
    for solid in solids:
        centroid = _polygon_centroid(solid.footprint)
        span_x = solid.metadata.get("span_x_m")
        span_y = solid.metadata.get("span_y_m")
        canvas.anno.element_label(
            Point2D(x=centroid.x, y=centroid.y + step * 0.9),
            solid.label,
            source_element_ids=[solid.element_id],
            source_element_kind=SourceElementKind.SLAB,
            layer=LAYER_SLABS,
        )
        spans = (
            f"{float(span_x):.2f}x{float(span_y):.2f}"
            if isinstance(span_x, (int, float)) and isinstance(span_y, (int, float))
            else NOT_IN_PEM
        )
        thickness = _mm(solid.metadata.get("thickness_m"))
        detail = spans if thickness == typical_thickness else f"{spans} t={thickness}"
        canvas.anno.element_label(
            Point2D(x=centroid.x, y=centroid.y - step * 0.9),
            detail,
            source_element_ids=[solid.element_id],
            source_element_kind=SourceElementKind.SLAB,
            layer=LAYER_SLABS,
            scale=0.8,
        )
    canvas.anno.note_block(
        Point2D(x=frame.bounds[0], y=frame.bounds[1] - frame.span * 0.20),
        [
            f"Slab is {typical_thickness} mm thick unless marked otherwise."
            if thickness_uniform
            else f"Typical slab {typical_thickness} mm; panels differing from typical are marked.",
            "Panel marks give the grid panel reference and its span in metres.",
            f"PEM member IDs are SLB-{level_id}-P<n>.",
        ],
        line_spacing_m=step * 1.6,
        layer=LAYER_SLABS,
        scale=0.95,
        source_element_ids=[solid.element_id for solid in solids],
        source_element_kind=SourceElementKind.SLAB,
    )

    if diaphragm is not None:
        _add_diaphragm(canvas, pem, diaphragm, level_id=level_id, step=step)

    # Coordination outlines: real stair/shaft elements, explicitly not openings.
    for stair in pem.stair_solids():
        if level_id not in stair.metadata.get("served_level_ids", []):
            continue
        canvas.add_polygon(
            list(stair.footprint),
            layer=LAYER_COORDINATION,
            source_element_ids=[stair.element_id],
            source_element_kind=SourceElementKind.STAIR,
            metadata={
                "role": "coordination-outline",
                "note": "stair shaft shown for coordination; not a modelled slab opening",
            },
        )
        canvas.anno.element_label(
            _polygon_centroid(stair.footprint),
            f"{stair.element_id} (coordination)",
            source_element_ids=[stair.element_id],
            source_element_kind=SourceElementKind.STAIR,
            layer=LAYER_COORDINATION,
            scale=0.75,
        )

    return _finish_structural_plan(
        canvas,
        pem,
        frame,
        level_id=level_id,
        title=f"SLAB LAYOUT — {_level_view_title(pem, level_id)}",
        overall_ref_ids=[solid.element_id for solid in solids],
        overall_ref_kind=SourceElementKind.SLAB,
    )


def _add_diaphragm(
    canvas: ViewCanvas,
    pem: PemDrawingContext,
    diaphragm,
    *,
    level_id: str,
    step: float,
) -> None:
    """
    Draw the diaphragm from the nodes the PEM assigns to it.

    The outline is the extent of those nodes — real model geometry, not a generic
    rectangle — and every assigned node is ticked so the assignment itself is
    visible rather than implied.
    """
    coords = [
        (point.x, point.y)
        for point in (pem.points.get(node_id) for node_id in diaphragm.node_ids)
        if point is not None
    ]
    if coords:
        min_x = min(x for x, _ in coords)
        max_x = max(x for x, _ in coords)
        min_y = min(y for _, y in coords)
        max_y = max(y for _, y in coords)
        canvas.add_polygon(
            [
                Point2D(x=min_x, y=min_y),
                Point2D(x=max_x, y=min_y),
                Point2D(x=max_x, y=max_y),
                Point2D(x=min_x, y=max_y),
            ],
            layer=LAYER_DIAPHRAGM,
            source_element_ids=[diaphragm.id],
            source_element_kind=SourceElementKind.DIAPHRAGM,
            metadata={
                "role": "diaphragm-extent",
                "derivation": "bounding extent of the nodes assigned in DiaphragmDefinition.node_ids",
                "kind": diaphragm.kind.value,
                "level_id": diaphragm.level_id,
                "node_count": len(diaphragm.node_ids),
                "linetype": "DASHED",
            },
        )
        # Each assigned node is ticked so the assignment itself is visible. The
        # tick is typed as a NODE so a node ID is never recorded as a diaphragm.
        for node_id, (x, y) in zip(diaphragm.node_ids, coords, strict=False):
            canvas.add(
                canvas.factory.circle(
                    Point2D(x=x, y=y),
                    step * 0.55,
                    layer=LAYER_DIAPHRAGM,
                    source_element_ids=[node_id],
                    source_element_kind=SourceElementKind.NODE,
                    metadata={
                        "role": "diaphragm-node",
                        "point_id": node_id,
                        "diaphragm_id": diaphragm.id,
                    },
                )
            )

    centre = Point2D(x=diaphragm.center_of_mass_x, y=diaphragm.center_of_mass_y)
    canvas.add_many(
        [
            canvas.factory.circle(
                centre,
                step * 1.6,
                layer=LAYER_DIAPHRAGM,
                source_element_ids=[diaphragm.id],
                source_element_kind=SourceElementKind.DIAPHRAGM,
                metadata={"role": "diaphragm-centre-of-mass"},
            ),
            canvas.factory.line(
                Point2D(x=centre.x - step * 2.2, y=centre.y),
                Point2D(x=centre.x + step * 2.2, y=centre.y),
                layer=LAYER_DIAPHRAGM,
                source_element_ids=[diaphragm.id],
                source_element_kind=SourceElementKind.DIAPHRAGM,
                metadata={"role": "diaphragm-centre-of-mass"},
            ),
            canvas.factory.line(
                Point2D(x=centre.x, y=centre.y - step * 2.2),
                Point2D(x=centre.x, y=centre.y + step * 2.2),
                layer=LAYER_DIAPHRAGM,
                source_element_ids=[diaphragm.id],
                source_element_kind=SourceElementKind.DIAPHRAGM,
                metadata={"role": "diaphragm-centre-of-mass"},
            ),
        ]
    )
    rigidity = (
        f"COR ({diaphragm.center_of_rigidity_x:.3f}, {diaphragm.center_of_rigidity_y:.3f})"
        if diaphragm.center_of_rigidity_x is not None and diaphragm.center_of_rigidity_y is not None
        else f"COR {NOT_IN_PEM}"
    )
    canvas.anno.note_block(
        Point2D(x=centre.x + step * 2.8, y=centre.y + step * 1.8),
        [
            f"{diaphragm.id}  {diaphragm.kind.value} DIAPHRAGM",
            f"Level {diaphragm.level_id}   nodes {len(diaphragm.node_ids)}",
            f"COM ({diaphragm.center_of_mass_x:.3f}, {diaphragm.center_of_mass_y:.3f})",
            rigidity,
            f"Weight {_fmt(diaphragm.weight_kN, digits=1)} kN",
        ],
        line_spacing_m=step * 1.35,
        layer=LAYER_DIAPHRAGM,
        scale=0.85,
    )


def _polygon_centroid(points: list[Point2D]) -> Point2D:
    return Point2D(
        x=sum(point.x for point in points) / len(points),
        y=sum(point.y for point in points) / len(points),
    )
