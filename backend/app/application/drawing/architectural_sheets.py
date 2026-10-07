"""
Architectural sheets, all projected from the persisted PEM.

* **A-001** site / general plan — plot, setback line, footprint, grid, north arrow
* **A-101** ground / parking plan — the actual PILOTI storey
* **A-102** typical residential plan — the actual first residential storey
* **A-201** elevations — four true orthographic projections of the 3D model
* **A-301** sections — two genuinely clipped cuts through the 3D model

The section cut positions are chosen deterministically from the PEM grid: A-A
takes the grid line nearest the stair so the stair is actually cut, B-B takes the
grid line nearest mid-depth.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from app.application.drawing.annotation import (
    LAYER_DOORS,
    LAYER_ELEVATION,
    LAYER_FOUNDATIONS,
    LAYER_LEVELS,
    LAYER_OUTLINE,
    LAYER_PARKING,
    LAYER_SECTION_CUT,
    LAYER_SITE,
    LAYER_SLABS,
    LAYER_SPACES,
    LAYER_STAIRS,
    LAYER_TEXT,
    LAYER_WALLS,
    LAYER_WINDOWS,
)
from app.application.drawing.pem_solids import PemDrawingContext, Solid3D
from app.application.drawing.projection import (
    ElevationDirection,
    ORIENTATION_NOTE,
    SectionDirection,
    elevation_span,
    filter_near_facade,
    project_elevation,
    project_plan,
    project_section,
    section_span,
)
from app.application.drawing.sheet_builder import SheetBuildContext
from app.application.drawing.view_helpers import (
    ViewCanvas,
    add_level_markers,
    add_overall_plan_dimensions,
    add_plan_grid,
    add_storey_height_dimensions,
    grid_lines_in_elevation,
)
from app.domain.models.drawing import (
    Discipline,
    DrawingSheet,
    DrawingView,
    NOT_IN_PEM,
    ProjectionKind,
    ProjectionKind as PK,
    SectionClip,
    SheetAvailability,
    SourceElementKind,
)
from app.domain.models.pem_architecture import FloorType, Point2D, SpaceUsage

#: Depth of model kept in front of an elevation plane. Wide enough to include the
#: exterior wall and the openings in it, tight enough to exclude the interior.
ELEVATION_DEPTH_WINDOW_M = 0.55

#: Section cut band. Must exceed the widest cut member (columns are 400 mm) so a
#: member centred on the cut line is genuinely intersected.
SECTION_BAND_M = 0.6

_COLUMN_KINDS = (SourceElementKind.COLUMN,)


@dataclass(frozen=True)
class SectionDefinition:
    label: str
    axis: str
    position_m: float
    direction: SectionDirection
    description: str


def section_definitions(pem: PemDrawingContext) -> list[SectionDefinition]:
    """Deterministic cut lines derived from the PEM grid and the stair position."""
    min_x, min_y, max_x, max_y = pem.footprint_bounds
    stair = pem.building.stairs[0] if pem.building.stairs else None
    if stair is not None and stair.boundary.points:
        s_min_x, _, s_max_x, _ = stair.boundary.bounds
        target_x = (s_min_x + s_max_x) / 2.0
    else:
        target_x = (min_x + max_x) / 2.0
    x_position = _nearest_interior(pem.grid_x, target_x, min_x, max_x)
    y_position = _nearest_interior(pem.grid_y, (min_y + max_y) / 2.0, min_y, max_y)
    return [
        SectionDefinition(
            label="A-A",
            axis="x",
            position_m=x_position,
            direction=SectionDirection.LOOKING_WEST,
            description=f"Cut on x = {x_position:.3f} m, looking west (-x); drawing axis follows +y",
        ),
        SectionDefinition(
            label="B-B",
            axis="y",
            position_m=y_position,
            direction=SectionDirection.LOOKING_NORTH,
            description=f"Cut on y = {y_position:.3f} m, looking north (+y); drawing axis follows +x",
        ),
    ]


def _nearest_interior(ordinates: list[float], target: float, low: float, high: float) -> float:
    interior = [value for value in ordinates if low + 1e-6 < value < high - 1e-6]
    if interior:
        return min(interior, key=lambda value: abs(value - target))
    return round((low + high) / 2.0, 6)


# ---------------------------------------------------------------------------
# A-001 Site / general plan
# ---------------------------------------------------------------------------


def build_site_plan(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    site = pem.building.site
    if site is None or len(site.boundary.points) < 3:
        return context.unavailable_sheet(
            sheet_number="A-001",
            title="Site / general plan",
            discipline=Discipline.ARCHITECTURAL,
            reason="PEM contains no site boundary geometry",
        )

    min_x, min_y, max_x, max_y = site.boundary.bounds
    span = max(max_x - min_x, max_y - min_y)
    canvas = ViewCanvas(
        view_id="A-001-V1",
        name="Site plan",
        projection=PK.PLAN,
        projection_label="PLAN:SITE",
        span_m=span,
        metadata={"plot_area_m2": site.plot_area_m2, "buildable_area_m2": site.buildable_area_m2},
    )

    canvas.add_ring(
        site.boundary,
        layer=LAYER_SITE,
        source_element_ids=[site.id],
        source_element_kind=SourceElementKind.SITE,
        metadata={"role": "plot-boundary", "plot_area_m2": site.plot_area_m2},
    )
    buildable = site.buildable_boundary
    setbacks = (
        site.setback_front_m + site.setback_rear_m + site.setback_left_m + site.setback_right_m
    )
    if buildable.points and setbacks > 0.0:
        canvas.add_ring(
            buildable,
            layer=LAYER_SITE,
            source_element_ids=[site.id],
            source_element_kind=SourceElementKind.SITE,
            metadata={"role": "setback-line", "buildable_area_m2": site.buildable_area_m2},
        )

    ground = pem.plans[0] if pem.plans else None
    if ground is not None:
        canvas.add_ring(
            ground.boundary,
            layer=LAYER_OUTLINE,
            source_element_ids=[ground.id],
            source_element_kind=SourceElementKind.LEVEL,
            metadata={"role": "building-footprint", "gross_area_m2": ground.gross_area_m2},
        )
        f_min_x, f_min_y, f_max_x, f_max_y = ground.boundary.bounds
        canvas.anno.dimension(
            Point2D(x=f_min_x, y=f_max_y),
            Point2D(x=f_max_x, y=f_max_y),
            offset_m=canvas.text_height_m * 4.0,
            source_element_ids=[ground.id],
            source_element_kind=SourceElementKind.LEVEL,
        )

    add_plan_grid(canvas, pem, bounds=(min_x, min_y, max_x, max_y))
    add_overall_plan_dimensions(
        canvas,
        bounds=(min_x, min_y, max_x, max_y),
        source_element_ids=[site.id],
        source_element_kind=SourceElementKind.SITE,
    )
    canvas.anno.north_arrow(
        Point2D(x=max_x + span * 0.14, y=max_y - span * 0.05),
        span * 0.06,
        site_id=site.id,
    )
    for direction in ElevationDirection:
        canvas.anno.elevation_marker(
            _elevation_marker_position(direction, (min_x, min_y, max_x, max_y), span),
            label=direction.value[0],
            direction=direction.value,
            target_sheet="A-201",
        )

    canvas.anno.element_label(
        Point2D(x=site.boundary.centroid.x, y=min_y + span * 0.03),
        f"PLOT {site.frontage_m:.2f} x {site.depth_m:.2f} m = {site.plot_area_m2:.2f} m²",
        source_element_ids=[site.id],
        source_element_kind=SourceElementKind.SITE,
    )

    info = [
        f"Project: {context.project_name}",
        f"Plot area: {site.plot_area_m2:.2f} m²   Buildable: {site.buildable_area_m2:.2f} m²",
        f"Frontage: {site.frontage_m:.2f} m   Depth: {site.depth_m:.2f} m",
        f"Storeys: {len(pem.plans)}   Building height: {pem.building_height_m:.3f} m",
        f"Structural system: {pem.building.structural_system.value}",
        "Levels:",
        *[f"   {level.name}  +{level.elevation:.3f} m" for level in pem.levels_sorted],
    ]
    canvas.anno.note_block(Point2D(x=max_x + span * 0.06, y=min_y + span * 0.45), info)

    view = canvas.finish()
    notes = [ORIENTATION_NOTE]
    if setbacks <= 0.0:
        notes.append("Setbacks are zero in the PEM; no setback line is drawn.")
    return context.build_sheet(
        sheet_number="A-001",
        title="Site / general plan",
        discipline=Discipline.ARCHITECTURAL,
        views=[view],
        notes=notes,
        metadata={"plot_area_m2": site.plot_area_m2, "storey_count": len(pem.plans)},
    )


def _elevation_marker_position(
    direction: ElevationDirection,
    bounds: tuple[float, float, float, float],
    span: float,
) -> Point2D:
    min_x, min_y, max_x, max_y = bounds
    offset = span * 0.07
    mid_x = (min_x + max_x) / 2.0
    mid_y = (min_y + max_y) / 2.0
    if direction is ElevationDirection.SOUTH:
        return Point2D(x=mid_x, y=min_y - offset)
    if direction is ElevationDirection.NORTH:
        return Point2D(x=mid_x, y=max_y + offset)
    if direction is ElevationDirection.EAST:
        return Point2D(x=max_x + offset, y=mid_y)
    return Point2D(x=min_x - offset, y=mid_y)


# ---------------------------------------------------------------------------
# A-101 / A-102 floor plans
# ---------------------------------------------------------------------------


def build_ground_plan(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    plan = pem.plan_of_type(FloorType.PILOTI) or pem.plan_of_type(FloorType.PARKING)
    if plan is None:
        return context.unavailable_sheet(
            sheet_number="A-101",
            title="Ground / parking plan",
            discipline=Discipline.ARCHITECTURAL,
            reason="PEM contains no piloti or parking storey",
        )
    view = _floor_plan_view(
        context,
        plan_level_id=plan.level_id,
        view_id="A-101-V1",
        name=f"{plan.name} — plan",
        include_parking=True,
        include_beams=False,
    )
    sections = section_definitions(pem)
    return context.build_sheet(
        sheet_number="A-101",
        title=f"Ground / parking plan — {plan.name}",
        discipline=Discipline.ARCHITECTURAL,
        views=[view],
        notes=[
            f"Storey {plan.name} at +{plan.elevation_m:.3f} m, storey height {plan.storey_height_m:.3f} m.",
            f"Parking bays shown: {len(plan.parking_spaces)}.",
            "Door and window host walls are derived geometrically; the PEM stores no wall_id.",
            *[f"Section {item.label}: {item.description}" for item in sections],
        ],
        metadata={
            "level_id": plan.level_id,
            "space_count": len(plan.spaces),
            "parking_count": len(plan.parking_spaces),
        },
    )


def build_typical_residential_plan(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    residential = pem.plans_of_type(FloorType.RESIDENTIAL)
    if not residential:
        return context.unavailable_sheet(
            sheet_number="A-102",
            title="Typical residential plan",
            discipline=Discipline.ARCHITECTURAL,
            reason="PEM contains no residential storey",
        )
    plan = residential[0]
    view = _floor_plan_view(
        context,
        plan_level_id=plan.level_id,
        view_id="A-102-V1",
        name=f"{plan.name} — plan",
        include_parking=False,
        include_beams=True,
    )
    repeated = [item.name for item in residential]
    return context.build_sheet(
        sheet_number="A-102",
        title=f"Typical residential plan — {plan.name}",
        discipline=Discipline.ARCHITECTURAL,
        views=[view],
        notes=[
            f"Storey {plan.name} at +{plan.elevation_m:.3f} m, storey height {plan.storey_height_m:.3f} m.",
            f"Layout repeats at: {', '.join(repeated)}.",
            f"Apartments on this storey: {len(plan.apartments)}.",
            "Beams are shown dashed over, at the slab above this storey.",
        ],
        metadata={
            "level_id": plan.level_id,
            "space_count": len(plan.spaces),
            "repeated_levels": [item.level_id for item in residential],
        },
    )


def _floor_plan_view(
    context: SheetBuildContext,
    *,
    plan_level_id: str,
    view_id: str,
    name: str,
    include_parking: bool,
    include_beams: bool,
) -> DrawingView:
    pem = context.pem
    plan = pem.plan_by_level[plan_level_id]
    level_ids = {plan_level_id}
    min_x, min_y, max_x, max_y = plan.boundary.bounds
    span = max(max_x - min_x, max_y - min_y)
    canvas = ViewCanvas(
        view_id=view_id,
        name=name,
        projection=PK.PLAN,
        projection_label=f"PLAN:{plan_level_id}",
        span_m=span,
        source_level_ids=[plan_level_id],
        metadata={
            "level_id": plan_level_id,
            "elevation_m": plan.elevation_m,
            "floor_type": plan.floor_type.value,
        },
    )

    canvas.add_ring(
        plan.boundary,
        layer=LAYER_OUTLINE,
        source_element_ids=[plan.id],
        source_element_kind=SourceElementKind.LEVEL,
        metadata={"role": "floor-outline", "gross_area_m2": plan.gross_area_m2},
    )

    # Spaces first so walls and openings draw over them.
    canvas.add_projected(
        project_plan(pem.space_solids(level_ids=level_ids), projection_label=canvas.factory.projection),
        layer=LAYER_SPACES,
        metadata_keys=("usage", "area_m2", "apartment_id"),
    )
    for space in plan.spaces:
        if space.area_m2 <= 0.0:
            continue
        canvas.anno.room_label(
            space.boundary.centroid,
            space_id=space.id,
            name=space.name,
            area_m2=space.area_m2,
            usage=space.usage.value,
        )

    canvas.add_projected(
        project_plan(pem.wall_solids(level_ids=level_ids), projection_label=canvas.factory.projection),
        layer=LAYER_WALLS,
        metadata_keys=("wall_type", "thickness_m", "height_m", "length_m", "is_load_bearing"),
    )

    openings = pem.opening_solids(level_ids=level_ids)
    doors = [item for item in openings if item.element_kind is SourceElementKind.DOOR]
    windows = [item for item in openings if item.element_kind is SourceElementKind.WINDOW]
    canvas.add_projected(
        project_plan(doors, projection_label=canvas.factory.projection),
        layer=LAYER_DOORS,
        metadata_keys=("width_m", "height_m", "run_axis", "derived_wall_id", "wall_association"),
    )
    canvas.add_projected(
        project_plan(windows, projection_label=canvas.factory.projection),
        layer=LAYER_WINDOWS,
        metadata_keys=("width_m", "height_m", "sill_height_m", "run_axis", "derived_wall_id"),
    )
    for door in doors:
        canvas.add_many(_door_swing(canvas, door))

    if include_parking:
        for slot_id, label, boundary in pem.parking_polygons(plan):
            canvas.add_ring(
                boundary,
                layer=LAYER_PARKING,
                source_element_ids=[slot_id],
                source_element_kind=SourceElementKind.PARKING,
                metadata={"role": "parking-bay", "label": label, "area_m2": boundary.area},
            )
            canvas.anno.element_label(
                boundary.centroid,
                label,
                source_element_ids=[slot_id],
                source_element_kind=SourceElementKind.PARKING,
                layer=LAYER_PARKING,
            )
            b_min_x, b_min_y, b_max_x, b_max_y = boundary.bounds
            canvas.anno.dimension(
                Point2D(x=b_min_x, y=b_min_y),
                Point2D(x=b_max_x, y=b_min_y),
                offset_m=-canvas.text_height_m * 2.0,
                source_element_ids=[slot_id],
                source_element_kind=SourceElementKind.PARKING,
            )

    # Stairs that serve this storey.
    for stair in pem.stair_solids():
        if plan_level_id not in stair.metadata.get("served_level_ids", []):
            continue
        canvas.add_projected(
            project_plan([stair], projection_label=canvas.factory.projection),
            layer=LAYER_STAIRS,
            metadata_keys=("served_level_ids", "clear_width_m", "riser_height_m", "tread_depth_m"),
        )
        canvas.add_many(_stair_treads(canvas, stair))
        centroid = _centroid(stair.footprint)
        canvas.anno.element_label(
            centroid,
            f"{stair.label} ({stair.element_id})",
            source_element_ids=[stair.element_id],
            source_element_kind=SourceElementKind.STAIR,
            layer=LAYER_STAIRS,
        )

    # Columns passing through this storey.
    columns = pem.column_solids(level_ids=level_ids)
    canvas.add_projected(
        project_plan(columns, projection_label=canvas.factory.projection),
        layer="COLUMNS",
        metadata_keys=("section", "width_m", "depth_m", "node_id"),
    )
    for column in columns:
        centroid = _centroid(column.footprint)
        canvas.anno.element_label(
            Point2D(x=centroid.x, y=centroid.y - canvas.text_height_m * 1.6),
            column.label,
            source_element_ids=[column.element_id],
            source_element_kind=SourceElementKind.COLUMN,
            layer="COLUMNS",
            scale=0.85,
        )

    if include_beams:
        for beam in pem.beam_solids(level_ids=level_ids):
            start = beam.metadata.get("start")
            end = beam.metadata.get("end")
            if not start or not end:
                continue
            canvas.add(
                canvas.factory.line(
                    Point2D(x=start[0], y=start[1]),
                    Point2D(x=end[0], y=end[1]),
                    layer="BEAMS",
                    source_element_ids=[beam.element_id],
                    source_element_kind=SourceElementKind.BEAM,
                    metadata={
                        "role": "beam-over",
                        "section": beam.metadata.get("section"),
                        "span_m": beam.metadata.get("span_m"),
                        "linetype": "DASHED",
                    },
                )
            )

    add_plan_grid(canvas, pem, bounds=(min_x, min_y, max_x, max_y))
    add_overall_plan_dimensions(
        canvas,
        bounds=(min_x, min_y, max_x, max_y),
        source_element_ids=[plan.id],
        source_element_kind=SourceElementKind.LEVEL,
    )
    canvas.anno.north_arrow(
        Point2D(x=max_x + span * 0.13, y=max_y - span * 0.04), span * 0.055
    )

    # Section markers so the plan cross-references A-301 / S-301.
    for definition in section_definitions(pem):
        if definition.axis == "x":
            start = Point2D(x=definition.position_m, y=min_y - span * 0.09)
            end = Point2D(x=definition.position_m, y=max_y + span * 0.09)
        else:
            start = Point2D(x=min_x - span * 0.09, y=definition.position_m)
            end = Point2D(x=max_x + span * 0.09, y=definition.position_m)
        canvas.anno.section_marker(
            start=start,
            end=end,
            label=definition.label,
            target_sheet="A-301",
        )
    return canvas.finish()


def _door_swing(canvas: ViewCanvas, door: Solid3D) -> list:
    """Leaf and swing chord for a door, drawn from its own width and axis."""
    center = door.metadata.get("center")
    width = float(door.metadata.get("width_m") or 0.0)
    axis = door.metadata.get("run_axis", "x")
    if not center or width <= 0.0:
        return []
    cx, cy = center
    if axis == "y":
        leaf_end = Point2D(x=cx + width, y=cy - width / 2.0)
        hinge = Point2D(x=cx, y=cy - width / 2.0)
    else:
        leaf_end = Point2D(x=cx - width / 2.0, y=cy + width)
        hinge = Point2D(x=cx - width / 2.0, y=cy)
    common = {
        "layer": LAYER_DOORS,
        "source_element_ids": [door.element_id],
        "source_element_kind": SourceElementKind.DOOR,
    }
    return [
        canvas.factory.line(hinge, leaf_end, **common, metadata={"role": "door-leaf"}),
        canvas.factory.circle(
            hinge, width, **common, metadata={"role": "door-swing", "width_m": width}
        ),
    ]


def _stair_treads(canvas: ViewCanvas, stair: Solid3D) -> list:
    """Tread lines across the stair footprint, spaced by the PEM tread depth."""
    tread = float(stair.metadata.get("tread_depth_m") or 0.0)
    if tread <= 0.0:
        return []
    min_x, min_y, max_x, max_y = stair.bounds_xy
    count = int((max_y - min_y) / tread)
    if count <= 1 or count > 200:
        return []
    lines = []
    for index in range(1, count):
        y = min_y + index * tread
        lines.append(
            canvas.factory.line(
                Point2D(x=min_x, y=y),
                Point2D(x=max_x, y=y),
                layer=LAYER_STAIRS,
                source_element_ids=[stair.element_id],
                source_element_kind=SourceElementKind.STAIR,
                metadata={"role": "stair-tread", "tread_depth_m": tread, "index": index},
            )
        )
    return lines


def _centroid(points: list[Point2D]) -> Point2D:
    return Point2D(
        x=sum(point.x for point in points) / len(points),
        y=sum(point.y for point in points) / len(points),
    )


# ---------------------------------------------------------------------------
# A-201 Elevations
# ---------------------------------------------------------------------------


def build_elevations(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    if not pem.plans:
        return context.unavailable_sheet(
            sheet_number="A-201",
            title="Elevations",
            discipline=Discipline.ARCHITECTURAL,
            reason="PEM contains no storeys to project",
        )
    bounds = pem.footprint_bounds
    solids = [
        *pem.wall_solids(),
        *pem.opening_solids(),
        *pem.slab_solids(),
        *pem.stair_solids(),
    ]
    views = [
        _elevation_view(context, direction=direction, solids=solids, model_bounds=bounds)
        for direction in (
            ElevationDirection.NORTH,
            ElevationDirection.SOUTH,
            ElevationDirection.EAST,
            ElevationDirection.WEST,
        )
    ]
    return context.build_sheet(
        sheet_number="A-201",
        title="Elevations — north, south, east, west",
        discipline=Discipline.ARCHITECTURAL,
        views=views,
        columns=2,
        notes=[
            ORIENTATION_NOTE,
            "True orthographic projections of the 3D PEM. No hidden-line removal is "
            f"applied; geometry deeper than {ELEVATION_DEPTH_WINDOW_M:.2f} m behind each "
            "facade plane is excluded.",
            f"Building height {pem.building_height_m:.3f} m above the lowest level.",
            "Parapets, roof falls and external finishes are not modelled in the PEM.",
        ],
        metadata={
            "elevation_directions": [view.metadata.get("elevation_direction") for view in views],
            "depth_window_m": ELEVATION_DEPTH_WINDOW_M,
            "building_height_m": pem.building_height_m,
        },
    )


def _elevation_view(
    context: SheetBuildContext,
    *,
    direction: ElevationDirection,
    solids: list[Solid3D],
    model_bounds: tuple[float, float, float, float],
) -> DrawingView:
    pem = context.pem
    span = elevation_span(direction, model_bounds)
    base = min((level.elevation for level in pem.levels_sorted), default=0.0)
    top = max(
        (plan.elevation_m + plan.storey_height_m for plan in pem.plans),
        default=base,
    )
    canvas = ViewCanvas(
        view_id=f"A-201-{direction.value}",
        name=f"{direction.value.title()} elevation",
        projection=PK.ELEVATION,
        projection_label=f"ELEVATION:{direction.value}",
        span_m=max(span, top - base),
        source_level_ids=[level.id for level in pem.levels_sorted],
        metadata={"elevation_direction": direction.value, "facade_span_m": round(span, 4)},
    )

    projected = filter_near_facade(
        project_elevation(solids, direction=direction, model_bounds=model_bounds),
        depth_window_m=ELEVATION_DEPTH_WINDOW_M,
    )
    by_kind: dict[SourceElementKind, list] = {}
    for item in projected:
        by_kind.setdefault(item.element_kind, []).append(item)

    canvas.add_projected(
        by_kind.get(SourceElementKind.WALL, []),
        layer=LAYER_WALLS,
        metadata_keys=("wall_type", "thickness_m", "height_m", "depth_near_m"),
    )
    canvas.add_projected(
        by_kind.get(SourceElementKind.SLAB, []),
        layer=LAYER_SLABS,
        metadata_keys=("thickness_m", "section", "depth_near_m"),
    )
    canvas.add_projected(
        by_kind.get(SourceElementKind.STAIR, []),
        layer=LAYER_STAIRS,
        metadata_keys=("served_level_ids", "depth_near_m"),
    )
    canvas.add_projected(
        by_kind.get(SourceElementKind.WINDOW, []),
        layer=LAYER_WINDOWS,
        metadata_keys=("width_m", "height_m", "sill_height_m", "depth_near_m"),
    )
    canvas.add_projected(
        by_kind.get(SourceElementKind.DOOR, []),
        layer=LAYER_DOORS,
        metadata_keys=("width_m", "height_m", "is_entrance", "depth_near_m"),
    )

    # Overall silhouette and roof line, both derived from the projected extents.
    canvas.add_polygon(
        [
            Point2D(x=0.0, y=base),
            Point2D(x=span, y=base),
            Point2D(x=span, y=top),
            Point2D(x=0.0, y=top),
        ],
        layer=LAYER_ELEVATION,
        source_element_ids=[plan.id for plan in pem.plans],
        source_element_kind=SourceElementKind.LEVEL,
        metadata={"role": "building-outline", "height_m": round(top - base, 4)},
    )
    roof_plan = pem.plan_of_type(FloorType.ROOF)
    if roof_plan is not None:
        canvas.add(
            canvas.factory.line(
                Point2D(x=0.0, y=roof_plan.elevation_m),
                Point2D(x=span, y=roof_plan.elevation_m),
                layer=LAYER_ELEVATION,
                source_element_ids=[roof_plan.id],
                source_element_kind=SourceElementKind.LEVEL,
                metadata={"role": "roof-line", "elevation_m": roof_plan.elevation_m},
            )
        )

    add_level_markers(canvas, pem, u_start=0.0, u_end=span)
    add_storey_height_dimensions(canvas, pem, u_position=span + canvas.text_height_m * 22.0)
    canvas.anno.dimension(
        Point2D(x=0.0, y=base - canvas.text_height_m * 6.0),
        Point2D(x=span, y=base - canvas.text_height_m * 6.0),
        offset_m=0.0,
        source_element_ids=[plan.id for plan in pem.plans],
        source_element_kind=SourceElementKind.LEVEL,
    )
    canvas.anno.element_label(
        Point2D(x=span / 2.0, y=base - canvas.text_height_m * 12.0),
        f"{direction.value} ELEVATION   height {top - base:.3f} m",
        source_element_ids=[plan.id for plan in pem.plans],
        source_element_kind=SourceElementKind.LEVEL,
        scale=1.3,
    )
    canvas.view.metadata["projected_element_count"] = len(projected)
    return canvas.finish()


# ---------------------------------------------------------------------------
# A-301 Sections
# ---------------------------------------------------------------------------


def build_architectural_sections(context: SheetBuildContext) -> DrawingSheet:
    pem = context.pem
    if not pem.plans:
        return context.unavailable_sheet(
            sheet_number="A-301",
            title="Sections",
            discipline=Discipline.ARCHITECTURAL,
            reason="PEM contains no storeys to section",
        )
    solids = [
        *pem.wall_solids(),
        *pem.slab_solids(),
        *pem.beam_solids(),
        *pem.column_solids(),
        *pem.footing_solids(),
        *pem.stair_solids(),
        *pem.opening_solids(),
    ]
    views = [
        _section_view(
            context,
            definition=definition,
            solids=solids,
            view_id=f"A-301-{definition.label}",
            include_openings=True,
        )
        for definition in section_definitions(pem)
    ]
    return context.build_sheet(
        sheet_number="A-301",
        title="Sections A-A and B-B",
        discipline=Discipline.ARCHITECTURAL,
        views=views,
        columns=1,
        notes=[
            ORIENTATION_NOTE,
            f"Geometry is clipped to a {SECTION_BAND_M:.2f} m cut band; elements that do "
            "not intersect the band are not drawn.",
            *[f"Section {item.label}: {item.description}" for item in section_definitions(pem)],
            "Foundation underside is derived as the footing top elevation minus its "
            "thickness. Excavation depth and soil profile are not modelled in the PEM.",
        ],
        metadata={
            "section_labels": [item.label for item in section_definitions(pem)],
            "band_width_m": SECTION_BAND_M,
        },
    )


def _section_view(
    context: SheetBuildContext,
    *,
    definition: SectionDefinition,
    solids: list[Solid3D],
    view_id: str,
    include_openings: bool,
    include_element_ids: bool = False,
) -> DrawingView:
    pem = context.pem
    model_bounds = pem.footprint_bounds
    span = section_span(definition.direction, model_bounds)
    projection_label = f"SECTION:{definition.label}"
    candidates = (
        solids
        if include_openings
        else [
            item
            for item in solids
            if item.element_kind
            not in (SourceElementKind.DOOR, SourceElementKind.WINDOW)
        ]
    )
    projected = project_section(
        candidates,
        direction=definition.direction,
        position_m=definition.position_m,
        band_width_m=SECTION_BAND_M,
        model_bounds=model_bounds,
        projection_label=projection_label,
    )
    base = min((item.points[0].y for item in projected), default=0.0)
    top = max((item.points[2].y for item in projected), default=0.0)
    canvas = ViewCanvas(
        view_id=view_id,
        name=f"Section {definition.label}",
        projection=PK.SECTION,
        projection_label=projection_label,
        span_m=max(span, top - base),
        source_level_ids=[level.id for level in pem.levels_sorted],
        clip=SectionClip(
            axis=definition.axis,
            position_m=definition.position_m,
            band_width_m=SECTION_BAND_M,
            view_direction=definition.direction.value,
        ),
        metadata={
            "section_label": definition.label,
            "section_description": definition.description,
            "clipped_element_count": len(projected),
            "candidate_element_count": len(candidates),
        },
    )

    layers = {
        SourceElementKind.FOOTING: LAYER_FOUNDATIONS,
        SourceElementKind.SLAB: LAYER_SLABS,
        SourceElementKind.BEAM: "BEAMS",
        SourceElementKind.COLUMN: "COLUMNS",
        SourceElementKind.WALL: LAYER_WALLS,
        SourceElementKind.STAIR: LAYER_STAIRS,
        SourceElementKind.DOOR: LAYER_DOORS,
        SourceElementKind.WINDOW: LAYER_WINDOWS,
    }
    by_kind: dict[SourceElementKind, list] = {}
    for item in projected:
        by_kind.setdefault(item.element_kind, []).append(item)
    for kind, layer in layers.items():
        canvas.add_projected(
            by_kind.get(kind, []),
            layer=layer,
            metadata_keys=(
                "section",
                "thickness_m",
                "width_m",
                "depth_m",
                "length_m",
                "wall_type",
                "utilization",
                "status",
                "underside_elevation_m",
            ),
        )

    if include_element_ids:
        for item in projected:
            if item.element_kind not in (
                SourceElementKind.COLUMN,
                SourceElementKind.BEAM,
                SourceElementKind.FOOTING,
                SourceElementKind.SLAB,
            ):
                continue
            min_u, min_v, max_u, max_v = item.bounds
            canvas.anno.element_label(
                Point2D(x=(min_u + max_u) / 2.0, y=max_v + canvas.text_height_m * 0.9),
                item.element_id,
                source_element_ids=[item.element_id],
                source_element_kind=item.element_kind,
                layer=layers.get(item.element_kind, LAYER_TEXT),
                scale=0.8,
            )

    # Ground level datum across the cut.
    ground = pem.levels_sorted[0] if pem.levels_sorted else None
    if ground is not None:
        canvas.add(
            canvas.factory.line(
                Point2D(x=-canvas.text_height_m * 4.0, y=ground.elevation),
                Point2D(x=span + canvas.text_height_m * 4.0, y=ground.elevation),
                layer=LAYER_LEVELS,
                source_element_ids=[ground.id],
                source_element_kind=SourceElementKind.LEVEL,
                metadata={"role": "ground-level", "elevation_m": ground.elevation},
            )
        )
    add_level_markers(canvas, pem, u_start=0.0, u_end=span)
    add_storey_height_dimensions(canvas, pem, u_position=span + canvas.text_height_m * 22.0)
    canvas.anno.dimension(
        Point2D(x=0.0, y=base - canvas.text_height_m * 5.0),
        Point2D(x=span, y=base - canvas.text_height_m * 5.0),
        offset_m=0.0,
        source_element_ids=[level.id for level in pem.levels_sorted],
        source_element_kind=SourceElementKind.LEVEL,
    )
    if base < (ground.elevation if ground else 0.0):
        canvas.anno.element_label(
            Point2D(x=canvas.text_height_m * 2.0, y=base - canvas.text_height_m * 2.0),
            f"Foundation underside {base:.3f} m (derived from footing thickness)",
            source_element_ids=[item.element_id for item in projected
                                if item.element_kind is SourceElementKind.FOOTING],
            source_element_kind=SourceElementKind.FOOTING,
            layer=LAYER_FOUNDATIONS,
            scale=0.9,
        )
    secondary_axis = "y" if definition.axis == "x" else "x"
    grid_lines_in_elevation(
        canvas,
        pem,
        ordinates=pem.grid_y if secondary_axis == "y" else pem.grid_x,
        labels=pem.grid_y_labels if secondary_axis == "y" else pem.grid_x_labels,
        origin=model_bounds[1] if secondary_axis == "y" else model_bounds[0],
        flip=definition.direction is SectionDirection.LOOKING_WEST and secondary_axis != "y",
        span=span,
        z_low=base - canvas.text_height_m * 2.0,
        z_high=top + canvas.text_height_m * 2.0,
    )
    canvas.anno.element_label(
        Point2D(x=span / 2.0, y=base - canvas.text_height_m * 11.0),
        f"SECTION {definition.label}   {definition.description}",
        source_element_ids=[level.id for level in pem.levels_sorted],
        source_element_kind=SourceElementKind.LEVEL,
        scale=1.2,
    )
    return canvas.finish()
