"""
Deterministic structural layout generator.

The structural grid is *derived from the architecture* rather than being an
unrelated second model: candidate grid ordinates come from the building footprint,
the corridor spine, the core walls and the parking bay boundaries, all read from
the :class:`BuildingModel` that :class:`BuildingLayoutGenerator` produced in the
same coordinate frame.

Ordinates are then conditioned so the frame is buildable:

1. candidates inside a *forbidden* region (parking bay interior, stair, corridor,
   door opening) are snapped to the nearest preferred position, such as a bay
   boundary;
2. ordinates closer together than ``min_span_m`` are merged;
3. any span longer than ``max_span_m`` is subdivided evenly.

The result is written into the existing :class:`StructuralModel` (grids, levels,
points, lines, areas, materials, sections, members, supports, analysis model), so
every downstream consumer — validation, DXF rendering, the design engine — keeps
working unchanged.

Units are SI: metres for geometry and section dimensions, MPa for strengths,
kN/m^3 for unit weight.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.domain.models.pem_architecture import (
    BuildingModel,
    FloorPlanDefinition,
    FloorType,
    Polygon2D,
    SpaceUsage,
    StructuralSystem,
)
from app.domain.models.pem_structural import (
    AnalysisElementReference,
    AnalysisModelReference,
    AreaDefinition,
    BeamSection,
    ColumnSection,
    ConcreteMaterial,
    GridDefinition,
    LevelDefinition,
    LineDefinition,
    MemberType,
    PointDefinition,
    ReinforcementMaterial,
    SlabSection,
    StructuralMember,
    StructuralModel,
    SupportDefinition,
    SupportType,
)

_COLUMN_LETTERS = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # I and O omitted, as on real drawings


@dataclass(frozen=True)
class StructuralLayoutDefaults:
    min_span_m: float = 2.0
    max_span_m: float = 6.0
    max_grid_lines: int = 8
    snap_tolerance_m: float = 1.6
    # Circulation only excludes columns in the direction it is *narrow*: a 1.4 m
    # corridor spine must stay clear, but a 12 m wide parking circulation area is
    # expected to contain columns.
    narrow_circulation_m: float = 3.0

    column_width_m: float = 0.40
    column_depth_m: float = 0.40
    beam_width_m: float = 0.30
    beam_depth_m: float = 0.50
    slab_thickness_m: float = 0.15

    concrete_fc_mpa: float = 25.0
    concrete_unit_weight_kn_m3: float = 25.0
    concrete_poisson: float = 0.20
    rebar_fy_mpa: float = 400.0
    rebar_modulus_mpa: float = 200000.0


@dataclass
class GridAxis:
    """One direction of the building grid."""

    ordinates: list[float]
    labels: list[str]

    def spans(self) -> list[float]:
        return [
            round(self.ordinates[index + 1] - self.ordinates[index], 6)
            for index in range(len(self.ordinates) - 1)
        ]


@dataclass
class StructuralLayoutResult:
    structural_model: StructuralModel
    grid_x: GridAxis
    grid_y: GridAxis
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    placement_conflicts: list[str] = field(default_factory=list)
    column_count: int = 0
    beam_count: int = 0
    slab_count: int = 0


class StructuralLayoutGenerator:
    """Generates a preliminary RC frame from a generated :class:`BuildingModel`."""

    def __init__(self, defaults: StructuralLayoutDefaults | None = None) -> None:
        self._d = defaults or StructuralLayoutDefaults()

    # -- public API --------------------------------------------------------

    def generate(self, building: BuildingModel) -> StructuralLayoutResult:
        if not building.is_populated or building.site is None:
            raise ValueError("A populated building model is required to generate a structural layout")

        assumptions: list[str] = []
        warnings: list[str] = []

        footprint = building.site.buildable_boundary
        min_x, min_y, max_x, max_y = footprint.bounds

        grid_x = self._build_axis(
            low=min_x,
            high=max_x,
            candidates=self._x_candidates(building),
            forbidden=self._forbidden_x(building),
            preferred=self._preferred_x(building),
            labels_are_letters=True,
        )
        grid_y = self._build_axis(
            low=min_y,
            high=max_y,
            candidates=self._y_candidates(building),
            forbidden=self._forbidden_y(building),
            preferred=self._preferred_y(building),
            labels_are_letters=False,
        )

        system = building.structural_system
        if system is StructuralSystem.STEEL_MOMENT_FRAME:
            warnings.append(
                "A steel moment frame was requested. The preliminary generator produces a "
                "reinforced-concrete frame; steel framing is not yet generated."
            )
        if system is StructuralSystem.RC_FRAME_WITH_SHEAR_WALLS:
            warnings.append(
                "Shear walls were requested but are not yet generated. A moment frame was "
                "produced and the lateral system must be revisited before any lateral design."
            )

        assumptions.append(
            f"Structural grid derived from the architectural layout with spans limited to "
            f"{self._d.min_span_m:.2f}-{self._d.max_span_m:.2f} m. "
            f"X spans: {grid_x.spans()}. Y spans: {grid_y.spans()}."
        )
        assumptions.append(
            f"Preliminary member sizes assumed: columns "
            f"{self._d.column_width_m * 1000:.0f}x{self._d.column_depth_m * 1000:.0f} mm, beams "
            f"{self._d.beam_width_m * 1000:.0f}x{self._d.beam_depth_m * 1000:.0f} mm, slab "
            f"{self._d.slab_thickness_m * 1000:.0f} mm. These are starting points for the "
            "design iteration loop, not final sizes."
        )
        assumptions.append(
            f"Concrete f'c = {self._d.concrete_fc_mpa:.0f} MPa, reinforcement fy = "
            f"{self._d.rebar_fy_mpa:.0f} MPa, concrete unit weight "
            f"{self._d.concrete_unit_weight_kn_m3:.0f} kN/m3."
        )

        model = StructuralModel()
        self._add_materials_and_sections(model)
        self._add_grid(model, grid_x, grid_y, footprint)

        levels = self._add_levels(model, building)
        points_by_level = self._add_points(model, grid_x, grid_y, levels)
        column_count = self._add_columns(model, grid_x, grid_y, levels, points_by_level)
        beam_count = self._add_beams(model, grid_x, grid_y, levels, points_by_level)
        slab_count = self._add_slabs(model, grid_x, grid_y, levels, points_by_level)
        self._add_supports(model, levels, points_by_level, grid_x, grid_y)
        self._add_analysis_model(model)

        conflicts = self._placement_conflicts(building, grid_x, grid_y)
        if conflicts:
            warnings.append(
                f"{len(conflicts)} column positions conflict with architectural elements; "
                "see placement_conflicts for the list."
            )

        return StructuralLayoutResult(
            structural_model=model,
            grid_x=grid_x,
            grid_y=grid_y,
            assumptions=assumptions,
            warnings=warnings,
            placement_conflicts=conflicts,
            column_count=column_count,
            beam_count=beam_count,
            slab_count=slab_count,
        )

    # -- grid derivation ---------------------------------------------------

    def _x_candidates(self, building: BuildingModel) -> list[float]:
        assert building.site is not None
        min_x, _, max_x, _ = building.site.buildable_boundary.bounds
        candidates = [min_x, max_x]
        for plan in building.floor_plans:
            for space in plan.spaces:
                if space.usage in (SpaceUsage.CORRIDOR, SpaceUsage.STAIR, SpaceUsage.ELEVATOR):
                    s_min_x, _, s_max_x, _ = space.boundary.bounds
                    candidates.extend((s_min_x, s_max_x))
            for slot in plan.parking_spaces:
                s_min_x, _, s_max_x, _ = slot.boundary.bounds
                candidates.extend((s_min_x, s_max_x))
        return candidates

    def _y_candidates(self, building: BuildingModel) -> list[float]:
        assert building.site is not None
        _, min_y, _, max_y = building.site.buildable_boundary.bounds
        candidates = [min_y, max_y]
        for plan in building.floor_plans:
            for space in plan.spaces:
                if space.usage in (
                    SpaceUsage.STAIR,
                    SpaceUsage.DRIVE_AISLE,
                    SpaceUsage.LOBBY,
                    SpaceUsage.ENTRANCE,
                ):
                    _, s_min_y, _, s_max_y = space.boundary.bounds
                    candidates.extend((s_min_y, s_max_y))
            for slot in plan.parking_spaces:
                _, s_min_y, _, s_max_y = slot.boundary.bounds
                candidates.extend((s_min_y, s_max_y))
        return candidates

    _ALWAYS_CLEAR = (SpaceUsage.STAIR, SpaceUsage.ELEVATOR)
    _NARROW_CLEAR = (
        SpaceUsage.CORRIDOR,
        SpaceUsage.DRIVE_AISLE,
        SpaceUsage.LOBBY,
        SpaceUsage.ENTRANCE,
    )

    # An ordinate constraint applies across the whole axis, so only elements that
    # must stay clear *along their entire run* belong here: parking bays (a column
    # mid-bay makes the bay unusable) and the narrow corridor spine (a column
    # mid-corridor blocks circulation). A stair or lift is a single small object
    # whose corner may legitimately coincide with a column, so it is handled by
    # the conflict report and the door-coordination pass instead of distorting the
    # entire grid.
    def _forbidden_x(self, building: BuildingModel) -> list[tuple[float, float]]:
        """x-intervals a column ordinate must not fall strictly inside."""
        intervals: list[tuple[float, float]] = []
        for plan in building.floor_plans:
            for slot in plan.parking_spaces:
                x0, _, x1, _ = slot.boundary.bounds
                intervals.append((x0, x1))
            for space in plan.spaces:
                x0, _, x1, _ = space.boundary.bounds
                if space.usage in self._NARROW_CLEAR and (x1 - x0) <= self._d.narrow_circulation_m:
                    intervals.append((x0, x1))
        return intervals

    def _forbidden_y(self, building: BuildingModel) -> list[tuple[float, float]]:
        intervals: list[tuple[float, float]] = []
        for plan in building.floor_plans:
            for slot in plan.parking_spaces:
                _, y0, _, y1 = slot.boundary.bounds
                intervals.append((y0, y1))
            for space in plan.spaces:
                _, y0, _, y1 = space.boundary.bounds
                if space.usage in self._NARROW_CLEAR and (y1 - y0) <= self._d.narrow_circulation_m:
                    intervals.append((y0, y1))
        return intervals

    # -- architecture / structure coordination -----------------------------

    def coordinate_doors(
        self,
        building: BuildingModel,
        grid_x: GridAxis,
        grid_y: GridAxis,
    ) -> list[str]:
        """
        Resolve door-versus-column clashes by sliding the door along its wall.

        Geometry is the architecture's to give here: a column position is driven by
        the frame, whereas a door can move along the same wall without changing any
        room boundary. Every move is returned so the caller can record it in
        traceability rather than changing the model silently.
        """
        adjustments: list[str] = []
        for plan in building.floor_plans:
            for door in plan.doors:
                axis = str(door.metadata.get("edge_axis", ""))
                low = door.metadata.get("edge_low")
                high = door.metadata.get("edge_high")
                if axis not in ("x", "y") or low is None or high is None:
                    continue
                blocked = self._door_blocking_ordinates(door, axis, grid_x, grid_y)
                if not blocked:
                    continue
                original = door.center.x if axis == "x" else door.center.y
                relocated = self._free_position(
                    blocked=blocked,
                    low=float(low),
                    high=float(high),
                    preferred=original,
                    clearance=(door.width_m + max(self._d.column_width_m, self._d.column_depth_m)) / 2.0,
                )
                if relocated is None:
                    adjustments.append(
                        f"{plan.name}: door {door.id} clashes with a column and the wall is too "
                        "short to relocate it; the opening needs manual resolution."
                    )
                    continue
                if axis == "x":
                    door.center.x = round(relocated, 4)
                else:
                    door.center.y = round(relocated, 4)
                door.metadata["relocated_from"] = round(original, 4)
                door.metadata["relocated_reason"] = "column clash resolved by structural coordination"
                adjustments.append(
                    f"{plan.name}: door {door.id} moved along its wall from {original:.2f} m to "
                    f"{relocated:.2f} m to clear a column."
                )
        return adjustments

    def _door_blocking_ordinates(
        self,
        door,
        axis: str,
        grid_x: GridAxis,
        grid_y: GridAxis,
    ) -> list[float]:
        """Column ordinates along the door's wall that sit on the same wall line."""
        if axis == "x":
            along, across = grid_x.ordinates, grid_y.ordinates
            wall_position = door.center.y
            half_across = self._d.column_depth_m / 2.0
        else:
            along, across = grid_y.ordinates, grid_x.ordinates
            wall_position = door.center.x
            half_across = self._d.column_width_m / 2.0
        if not any(abs(value - wall_position) <= half_across for value in across):
            return []
        return list(along)

    @staticmethod
    def _free_position(
        *,
        blocked: list[float],
        low: float,
        high: float,
        preferred: float,
        clearance: float,
    ) -> float | None:
        """Nearest point to ``preferred`` in ``[low, high]`` at least ``clearance`` from every blocker."""
        margin = clearance
        if high - low <= 2.0 * margin:
            return None
        candidates: list[float] = [preferred]
        for blocker in blocked:
            candidates.extend((blocker - margin, blocker + margin))
        candidates.extend((low + margin, high - margin))
        feasible = [
            value
            for value in candidates
            if low + margin - 1e-9 <= value <= high - margin + 1e-9
            and all(abs(value - blocker) >= margin - 1e-9 for blocker in blocked)
        ]
        if not feasible:
            return None
        return min(feasible, key=lambda value: abs(value - preferred))

    @staticmethod
    def _preferred_x(building: BuildingModel) -> list[float]:
        """Positions a snapped ordinate may move to — parking bay lines first."""
        preferred: list[float] = []
        for plan in building.floor_plans:
            for slot in plan.parking_spaces:
                x0, _, x1, _ = slot.boundary.bounds
                preferred.extend((x0, x1))
        if building.site is not None:
            min_x, _, max_x, _ = building.site.buildable_boundary.bounds
            preferred.extend((min_x, max_x))
        return preferred

    @staticmethod
    def _preferred_y(building: BuildingModel) -> list[float]:
        preferred: list[float] = []
        for plan in building.floor_plans:
            for slot in plan.parking_spaces:
                _, y0, _, y1 = slot.boundary.bounds
                preferred.extend((y0, y1))
        if building.site is not None:
            _, min_y, _, max_y = building.site.buildable_boundary.bounds
            preferred.extend((min_y, max_y))
        return preferred

    def _build_axis(
        self,
        *,
        low: float,
        high: float,
        candidates: list[float],
        forbidden: list[tuple[float, float]],
        preferred: list[float],
        labels_are_letters: bool,
    ) -> GridAxis:
        tolerance = 1e-6
        allowed_preferred = sorted(
            {
                round(value, 6)
                for value in list(preferred) + [low, high]
                if low - tolerance <= value <= high + tolerance
                and not _strictly_inside(value, forbidden)
            }
        )

        working: list[float] = []
        for value in sorted({round(value, 6) for value in candidates}):
            if value < low - tolerance or value > high + tolerance:
                continue
            if _strictly_inside(value, forbidden):
                snapped = _nearest(value, allowed_preferred, self._d.snap_tolerance_m)
                if snapped is None:
                    continue
                value = snapped
            working.append(round(value, 6))

        working = sorted(set(working) | {round(low, 6), round(high, 6)})

        # Merge ordinates that are too close to carry separate columns.
        merged: list[float] = [working[0]]
        for value in working[1:]:
            if value - merged[-1] < self._d.min_span_m - tolerance:
                if abs(value - high) < tolerance:
                    merged[-1] = value  # never discard the far boundary
                continue
            merged.append(value)
        if len(merged) == 1:
            merged = [round(low, 6), round(high, 6)]

        # Subdivide spans that exceed the maximum, snapping inserted lines away
        # from forbidden regions where a preferred position is close enough.
        final: list[float] = [merged[0]]
        for index in range(len(merged) - 1):
            start = merged[index]
            end = merged[index + 1]
            span = end - start
            divisions = max(1, math.ceil((span - tolerance) / self._d.max_span_m))
            for step in range(1, divisions):
                raw = start + span * step / divisions
                if _strictly_inside(raw, forbidden):
                    snapped = _nearest(raw, allowed_preferred, self._d.snap_tolerance_m)
                    if snapped is not None and start + tolerance < snapped < end - tolerance:
                        raw = snapped
                if final and raw - final[-1] < self._d.min_span_m - tolerance:
                    continue
                final.append(round(raw, 6))
            if end - final[-1] < self._d.min_span_m - tolerance and len(final) > 1:
                final[-1] = round(end, 6)
            else:
                final.append(round(end, 6))

        ordinates = sorted(set(final))
        if len(ordinates) > self._d.max_grid_lines:
            count = self._d.max_grid_lines
            ordinates = [round(low + (high - low) * index / (count - 1), 6) for index in range(count)]
        labels = [
            _column_label(index) if labels_are_letters else str(index + 1)
            for index in range(len(ordinates))
        ]
        return GridAxis(ordinates=ordinates, labels=labels)

    def _placement_conflicts(
        self,
        building: BuildingModel,
        grid_x: GridAxis,
        grid_y: GridAxis,
    ) -> list[str]:
        """
        Report columns that land in a parking bay, door, stair or narrow corridor.

        A column whose centre sits on a space boundary is normal construction (the
        space is bounded *by* the column line), so a conflict is only reported when
        the centre is at least half a column dimension inside the blocker.
        """
        conflicts: list[str] = []
        half_x = self._d.column_width_m / 2.0
        half_y = self._d.column_depth_m / 2.0
        for plan in building.floor_plans:
            blockers: list[tuple[str, Polygon2D]] = [
                (f"parking bay {slot.label}", slot.boundary) for slot in plan.parking_spaces
            ]
            for space in plan.spaces:
                x0, y0, x1, y1 = space.boundary.bounds
                if space.usage in self._ALWAYS_CLEAR or (
                    space.usage in self._NARROW_CLEAR
                    and min(x1 - x0, y1 - y0) <= self._d.narrow_circulation_m
                ):
                    blockers.append((f"{space.usage.value.lower()} '{space.name}'", space.boundary))

            for x_index, x_value in enumerate(grid_x.ordinates):
                for y_index, y_value in enumerate(grid_y.ordinates):
                    label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}"
                    for blocker_name, boundary in blockers:
                        b_min_x, b_min_y, b_max_x, b_max_y = boundary.bounds
                        inside_x = b_min_x + half_x < x_value < b_max_x - half_x
                        inside_y = b_min_y + half_y < y_value < b_max_y - half_y
                        if inside_x and inside_y:
                            conflicts.append(
                                f"{plan.name}: column {label} at ({x_value:.2f}, {y_value:.2f}) "
                                f"intrudes into {blocker_name}"
                            )
            for door in plan.doors:
                for x_index, x_value in enumerate(grid_x.ordinates):
                    for y_index, y_value in enumerate(grid_y.ordinates):
                        if (
                            abs(door.center.x - x_value) < door.width_m / 2.0
                            and abs(door.center.y - y_value) < door.width_m / 2.0
                        ):
                            label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}"
                            conflicts.append(
                                f"{plan.name}: column {label} coincides with door {door.id}"
                            )
        return conflicts

    # -- structural model assembly ----------------------------------------

    def _add_materials_and_sections(self, model: StructuralModel) -> None:
        elastic_modulus = 4700.0 * math.sqrt(self._d.concrete_fc_mpa)
        model.materials.concrete.append(
            ConcreteMaterial(
                id="CONC-C25",
                name=f"Concrete f'c={self._d.concrete_fc_mpa:.0f} MPa",
                compressive_strength=self._d.concrete_fc_mpa,
                modulus_of_elasticity=round(elastic_modulus, 2),
                unit_weight=self._d.concrete_unit_weight_kn_m3,
                poisson_ratio=self._d.concrete_poisson,
                metadata={
                    "units": {"strength": "MPa", "modulus": "MPa", "unit_weight": "kN/m3"},
                    "modulus_basis": "ACI 318 Eq. 19.2.2.1.b for normalweight concrete: Ec = 4700*sqrt(f'c) MPa",
                },
            )
        )
        model.materials.reinforcement.append(
            ReinforcementMaterial(
                id="REBAR-G400",
                name=f"Reinforcement fy={self._d.rebar_fy_mpa:.0f} MPa",
                yield_strength=self._d.rebar_fy_mpa,
                modulus_of_elasticity=self._d.rebar_modulus_mpa,
                metadata={"units": {"strength": "MPa"}},
            )
        )
        model.sections.columns.append(
            ColumnSection(
                id="COL-C1",
                name=f"C{self._d.column_width_m * 1000:.0f}x{self._d.column_depth_m * 1000:.0f}",
                width=self._d.column_width_m,
                depth=self._d.column_depth_m,
                metadata={"units": "m", "width_mm": self._d.column_width_m * 1000},
            )
        )
        model.sections.beams.append(
            BeamSection(
                id="BEAM-B1",
                name=f"B{self._d.beam_width_m * 1000:.0f}x{self._d.beam_depth_m * 1000:.0f}",
                width=self._d.beam_width_m,
                depth=self._d.beam_depth_m,
                metadata={"units": "m", "width_mm": self._d.beam_width_m * 1000},
            )
        )
        model.sections.slabs.append(
            SlabSection(
                id="SLAB-S1",
                name=f"S{self._d.slab_thickness_m * 1000:.0f}",
                thickness=self._d.slab_thickness_m,
                metadata={"units": "m", "thickness_mm": self._d.slab_thickness_m * 1000},
            )
        )

    def _add_grid(
        self,
        model: StructuralModel,
        grid_x: GridAxis,
        grid_y: GridAxis,
        footprint: Polygon2D,
    ) -> None:
        min_x, min_y, max_x, max_y = footprint.bounds
        model.geometry.grids.append(
            GridDefinition(
                id="GRID-1",
                name="Building grid",
                origin_x=min_x,
                origin_y=min_y,
                orientation_deg=0.0,
                metadata={
                    "units": "m",
                    "x_ordinates": grid_x.ordinates,
                    "x_labels": grid_x.labels,
                    "y_ordinates": grid_y.ordinates,
                    "y_labels": grid_y.labels,
                    "x_spans": grid_x.spans(),
                    "y_spans": grid_y.spans(),
                    "extent": {"min_x": min_x, "min_y": min_y, "max_x": max_x, "max_y": max_y},
                    "derived_from": "architectural layout (footprint, corridor, core, parking bays)",
                },
            )
        )

    @staticmethod
    def _add_levels(model: StructuralModel, building: BuildingModel) -> list[FloorPlanDefinition]:
        plans = sorted(building.floor_plans, key=lambda plan: plan.elevation_m)
        for order, plan in enumerate(plans):
            model.geometry.levels.append(
                LevelDefinition(
                    id=plan.level_id,
                    name=plan.name,
                    elevation=plan.elevation_m,
                    sort_order=order,
                    metadata={
                        "units": "m",
                        "floor_type": plan.floor_type.value,
                        "storey_height_m": plan.storey_height_m,
                    },
                )
            )
        return plans

    @staticmethod
    def _add_points(
        model: StructuralModel,
        grid_x: GridAxis,
        grid_y: GridAxis,
        levels: list[FloorPlanDefinition],
    ) -> dict[str, dict[tuple[int, int], str]]:
        points_by_level: dict[str, dict[tuple[int, int], str]] = {}
        for plan in levels:
            level_points: dict[tuple[int, int], str] = {}
            for x_index, x_value in enumerate(grid_x.ordinates):
                for y_index, y_value in enumerate(grid_y.ordinates):
                    label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}"
                    point_id = f"PT-{plan.level_id}-{label}"
                    model.geometry.points.append(
                        PointDefinition(
                            id=point_id,
                            x=x_value,
                            y=y_value,
                            z=plan.elevation_m,
                            level_id=plan.level_id,
                            grid_id="GRID-1",
                            metadata={"grid_label": label},
                        )
                    )
                    level_points[(x_index, y_index)] = point_id
            points_by_level[plan.level_id] = level_points
        return points_by_level

    def _add_columns(
        self,
        model: StructuralModel,
        grid_x: GridAxis,
        grid_y: GridAxis,
        levels: list[FloorPlanDefinition],
        points_by_level: dict[str, dict[tuple[int, int], str]],
    ) -> int:
        count = 0
        for storey_index in range(len(levels) - 1):
            lower = levels[storey_index]
            upper = levels[storey_index + 1]
            for x_index in range(len(grid_x.ordinates)):
                for y_index in range(len(grid_y.ordinates)):
                    label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}"
                    start_point = points_by_level[lower.level_id][(x_index, y_index)]
                    end_point = points_by_level[upper.level_id][(x_index, y_index)]
                    line_id = f"LN-COL-{lower.level_id}-{label}"
                    member_id = f"COL-{lower.level_id}-{label}"
                    model.geometry.lines.append(
                        LineDefinition(
                            id=line_id,
                            start_point_id=start_point,
                            end_point_id=end_point,
                            member_id=member_id,
                            metadata={"element_role": "column"},
                        )
                    )
                    model.members.members.append(
                        StructuralMember(
                            id=member_id,
                            member_type=MemberType.COLUMN,
                            name=f"C-{label} ({lower.name} to {upper.name})",
                            section_id="COL-C1",
                            material_id="CONC-C25",
                            level_id=lower.level_id,
                            start_point_id=start_point,
                            end_point_id=end_point,
                            line_id=line_id,
                            metadata={
                                "grid_label": label,
                                "storey": lower.level_id,
                                "clear_height_m": round(upper.elevation_m - lower.elevation_m, 4),
                            },
                        )
                    )
                    count += 1
        return count

    def _add_beams(
        self,
        model: StructuralModel,
        grid_x: GridAxis,
        grid_y: GridAxis,
        levels: list[FloorPlanDefinition],
        points_by_level: dict[str, dict[tuple[int, int], str]],
    ) -> int:
        count = 0
        for plan in levels[1:]:  # no beams at the foundation level
            for y_index in range(len(grid_y.ordinates)):
                for x_index in range(len(grid_x.ordinates) - 1):
                    start_label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}"
                    end_label = f"{grid_x.labels[x_index + 1]}{grid_y.labels[y_index]}"
                    count += self._append_beam(
                        model,
                        plan=plan,
                        start_point=points_by_level[plan.level_id][(x_index, y_index)],
                        end_point=points_by_level[plan.level_id][(x_index + 1, y_index)],
                        start_label=start_label,
                        end_label=end_label,
                        direction="X",
                        span=grid_x.ordinates[x_index + 1] - grid_x.ordinates[x_index],
                    )
            for x_index in range(len(grid_x.ordinates)):
                for y_index in range(len(grid_y.ordinates) - 1):
                    start_label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}"
                    end_label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index + 1]}"
                    count += self._append_beam(
                        model,
                        plan=plan,
                        start_point=points_by_level[plan.level_id][(x_index, y_index)],
                        end_point=points_by_level[plan.level_id][(x_index, y_index + 1)],
                        start_label=start_label,
                        end_label=end_label,
                        direction="Y",
                        span=grid_y.ordinates[y_index + 1] - grid_y.ordinates[y_index],
                    )
        return count

    @staticmethod
    def _append_beam(
        model: StructuralModel,
        *,
        plan: FloorPlanDefinition,
        start_point: str,
        end_point: str,
        start_label: str,
        end_label: str,
        direction: str,
        span: float,
    ) -> int:
        member_id = f"B{direction}-{plan.level_id}-{start_label}-{end_label}"
        line_id = f"LN-{member_id}"
        model.geometry.lines.append(
            LineDefinition(
                id=line_id,
                start_point_id=start_point,
                end_point_id=end_point,
                member_id=member_id,
                metadata={"element_role": "beam", "direction": direction},
            )
        )
        model.members.members.append(
            StructuralMember(
                id=member_id,
                member_type=MemberType.BEAM,
                name=f"B-{start_label}/{end_label} ({plan.name})",
                section_id="BEAM-B1",
                material_id="CONC-C25",
                level_id=plan.level_id,
                start_point_id=start_point,
                end_point_id=end_point,
                line_id=line_id,
                metadata={
                    "direction": direction,
                    "span_m": round(span, 4),
                    "grid_from": start_label,
                    "grid_to": end_label,
                },
            )
        )
        return 1

    def _add_slabs(
        self,
        model: StructuralModel,
        grid_x: GridAxis,
        grid_y: GridAxis,
        levels: list[FloorPlanDefinition],
        points_by_level: dict[str, dict[tuple[int, int], str]],
    ) -> int:
        count = 0
        for plan in levels[1:]:
            panel_index = 0
            for x_index in range(len(grid_x.ordinates) - 1):
                for y_index in range(len(grid_y.ordinates) - 1):
                    panel_index += 1
                    corners = [
                        points_by_level[plan.level_id][(x_index, y_index)],
                        points_by_level[plan.level_id][(x_index + 1, y_index)],
                        points_by_level[plan.level_id][(x_index + 1, y_index + 1)],
                        points_by_level[plan.level_id][(x_index, y_index + 1)],
                    ]
                    span_x = grid_x.ordinates[x_index + 1] - grid_x.ordinates[x_index]
                    span_y = grid_y.ordinates[y_index + 1] - grid_y.ordinates[y_index]
                    panel_label = (
                        f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}-"
                        f"{grid_x.labels[x_index + 1]}{grid_y.labels[y_index + 1]}"
                    )
                    area_id = f"AR-{plan.level_id}-P{panel_index}"
                    member_id = f"SLB-{plan.level_id}-P{panel_index}"
                    model.geometry.areas.append(
                        AreaDefinition(
                            id=area_id,
                            boundary_point_ids=corners,
                            level_id=plan.level_id,
                            member_id=member_id,
                            metadata={
                                "panel_label": panel_label,
                                "span_x_m": round(span_x, 4),
                                "span_y_m": round(span_y, 4),
                            },
                        )
                    )
                    model.members.members.append(
                        StructuralMember(
                            id=member_id,
                            member_type=MemberType.SLAB,
                            name=f"Slab panel {panel_label} ({plan.name})",
                            section_id="SLAB-S1",
                            material_id="CONC-C25",
                            level_id=plan.level_id,
                            area_id=area_id,
                            metadata={
                                "panel_label": panel_label,
                                "span_x_m": round(span_x, 4),
                                "span_y_m": round(span_y, 4),
                                "area_m2": round(span_x * span_y, 4),
                                "floor_type": plan.floor_type.value,
                            },
                        )
                    )
                    count += 1
        return count

    @staticmethod
    def _add_supports(
        model: StructuralModel,
        levels: list[FloorPlanDefinition],
        points_by_level: dict[str, dict[tuple[int, int], str]],
        grid_x: GridAxis,
        grid_y: GridAxis,
    ) -> None:
        base = levels[0]
        for x_index in range(len(grid_x.ordinates)):
            for y_index in range(len(grid_y.ordinates)):
                label = f"{grid_x.labels[x_index]}{grid_y.labels[y_index]}"
                point_id = points_by_level[base.level_id][(x_index, y_index)]
                model.supports.append(
                    SupportDefinition(
                        id=f"SUP-{label}",
                        point_id=point_id,
                        support_type=SupportType.FIXED,
                        restraint_tx=True,
                        restraint_ty=True,
                        restraint_tz=True,
                        restraint_rx=True,
                        restraint_ry=True,
                        restraint_rz=True,
                        metadata={
                            "grid_label": label,
                            "assumption": (
                                "Column bases assumed fixed on isolated footings. Foundation "
                                "design is not performed; verify against the geotechnical report."
                            ),
                        },
                    )
                )

    @staticmethod
    def _add_analysis_model(model: StructuralModel) -> None:
        model.analysis_model = AnalysisModelReference(
            nodes=[],
            elements=[
                AnalysisElementReference(id=f"AE-{member.id}", member_id=member.id)
                for member in model.members.members
                if member.member_type in (MemberType.BEAM, MemberType.COLUMN)
            ],
            load_case_ids=[],
            load_combination_ids=[],
            configuration={
                "solver": "internal_direct_stiffness_3d",
                "decomposition": "3D space frame with rigid floor diaphragms",
                "units": {"length": "m", "force": "kN", "stress": "MPa"},
            },
            capability_status="READY_FOR_ANALYSIS_ENGINE",
        )


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _column_label(index: int) -> str:
    letters = _COLUMN_LETTERS
    if index < len(letters):
        return letters[index]
    first, second = divmod(index, len(letters))
    return f"{letters[first - 1]}{letters[second]}"


def _strictly_inside(
    value: float,
    intervals: list[tuple[float, float]],
    *,
    tolerance: float = 1e-6,
) -> bool:
    return any(low + tolerance < value < high - tolerance for low, high in intervals)


def _nearest(value: float, options: list[float], tolerance: float) -> float | None:
    best: float | None = None
    best_distance = tolerance
    for option in options:
        distance = abs(option - value)
        if distance <= best_distance:
            best = option
            best_distance = distance
    return best
