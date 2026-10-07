"""
Read-only 3D extraction from the PEM for the drawing engine.

:class:`PemDrawingContext` indexes a :class:`ProjectEngineeringModel` once so the
sheet builders never rescan the member list (the 12x22 slice has 484 members and
730 design checks, so repeated linear scans would be quadratic).

:class:`Solid3D` is the one intermediate shape the projection engine consumes: a
plan footprint polygon plus a vertical extent, tagged with the PEM element it was
read from. It is a *projection input*, not a stored model — nothing here is ever
written back into the PEM.

Documented modelling conventions (all of them derivations of PEM data, never
invented values):

* A column occupies its section rectangle, axis-aligned, between the elevations
  of its two end nodes. The PEM carries no column rotation, so orientation is
  reported as unavailable rather than guessed.
* A beam occupies its section rectangle swept along its centreline, hanging below
  the level elevation by the section depth (level elevation = top of slab).
* A slab occupies its area boundary, between ``elevation - thickness`` and
  ``elevation``.
* A footing occupies ``length x width`` centred on its column node, with its top
  at the node elevation and its underside one thickness below. Excavation depth
  is not modelled.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.domain.models.drawing import NOT_IN_PEM, SourceElementKind
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_architecture import (
    DoorDefinition,
    FloorPlanDefinition,
    FloorType,
    Point2D,
    Polygon2D,
    WallDefinition,
    WindowDefinition,
)
from app.domain.models.pem_structural import (
    AreaDefinition,
    DiaphragmDefinition,
    FoundationFooting,
    GridDefinition,
    LevelDefinition,
    MemberDesignCheck,
    MemberReinforcement,
    MemberType,
    PointDefinition,
    StructuralMember,
)

#: Fallback thickness used only to give a zero-height element a drawable extent.
_MIN_EXTENT_M = 1e-4


@dataclass
class Solid3D:
    """A plan footprint with a vertical extent, traced to one PEM element."""

    element_id: str
    element_kind: SourceElementKind
    footprint: list[Point2D]
    min_z: float
    max_z: float
    level_id: str | None = None
    label: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def bounds_xy(self) -> tuple[float, float, float, float]:
        xs = [point.x for point in self.footprint]
        ys = [point.y for point in self.footprint]
        return (min(xs), min(ys), max(xs), max(ys))

    def interval(self, axis: str) -> tuple[float, float]:
        min_x, min_y, max_x, max_y = self.bounds_xy
        if axis == "x":
            return (min_x, max_x)
        if axis == "y":
            return (min_y, max_y)
        return (self.min_z, self.max_z)

    def intersects_band(self, axis: str, low: float, high: float) -> bool:
        start, end = self.interval(axis)
        return end > low and start < high


# ---------------------------------------------------------------------------
# PEM index
# ---------------------------------------------------------------------------


class PemDrawingContext:
    """One-pass index over the PEM, shared by every sheet builder."""

    def __init__(self, pem: ProjectEngineeringModel) -> None:
        self.pem = pem
        self.building = pem.building_model
        self.structural = pem.structural_model

        self.points: dict[str, PointDefinition] = {
            point.id: point for point in self.structural.geometry.points
        }
        self.levels: dict[str, LevelDefinition] = {
            level.id: level for level in self.structural.geometry.levels
        }
        self.levels_sorted: list[LevelDefinition] = sorted(
            self.structural.geometry.levels, key=lambda item: (item.elevation, item.sort_order)
        )
        self.areas: dict[str, AreaDefinition] = {
            area.id: area for area in self.structural.geometry.areas
        }
        self.lines = {line.id: line for line in self.structural.geometry.lines}

        self.grid: GridDefinition | None = (
            self.structural.geometry.grids[0] if self.structural.geometry.grids else None
        )
        grid_meta = self.grid.metadata if self.grid is not None else {}
        self.grid_x: list[float] = [float(value) for value in grid_meta.get("x_ordinates") or []]
        self.grid_y: list[float] = [float(value) for value in grid_meta.get("y_ordinates") or []]
        self.grid_x_labels: list[str] = [str(value) for value in grid_meta.get("x_labels") or []]
        self.grid_y_labels: list[str] = [str(value) for value in grid_meta.get("y_labels") or []]

        self.column_sections = {item.id: item for item in self.structural.sections.columns}
        self.beam_sections = {item.id: item for item in self.structural.sections.beams}
        self.slab_sections = {item.id: item for item in self.structural.sections.slabs}
        self.wall_sections = {item.id: item for item in self.structural.sections.walls}
        self.foundation_sections = {item.id: item for item in self.structural.sections.foundations}

        self.concrete = {item.id: item for item in self.structural.materials.concrete}
        self.steel = {item.id: item for item in self.structural.materials.steel}
        self.rebar_materials = {item.id: item for item in self.structural.materials.reinforcement}

        self.members: dict[str, StructuralMember] = {
            member.id: member for member in self.structural.members.members
        }
        self.members_by_type: dict[MemberType, list[StructuralMember]] = {}
        for member in self.structural.members.members:
            self.members_by_type.setdefault(member.member_type, []).append(member)
        for bucket in self.members_by_type.values():
            bucket.sort(key=lambda item: item.id)

        self.reinforcement: dict[str, MemberReinforcement] = {
            item.member_id: item for item in self.structural.reinforcement
        }
        self.checks: dict[str, list[MemberDesignCheck]] = {}
        for check in self.structural.design_checks:
            self.checks.setdefault(check.member_id, []).append(check)

        self.footings: list[FoundationFooting] = sorted(
            self.structural.footings, key=lambda item: item.id
        )
        self.footing_by_column: dict[str, FoundationFooting] = {
            item.column_member_id: item for item in self.structural.footings
        }
        self.diaphragm_by_level: dict[str, DiaphragmDefinition] = {
            item.level_id: item for item in self.structural.diaphragms
        }
        self.drift_by_level = {item.level_id: item for item in self.structural.story_drifts}
        self.mass_by_level = {item.level_id: item for item in self.structural.story_masses}

        self.plans: list[FloorPlanDefinition] = sorted(
            self.building.floor_plans, key=lambda item: item.elevation_m
        )
        self.plan_by_level: dict[str, FloorPlanDefinition] = {
            plan.level_id: plan for plan in self.plans
        }
        self.supports_by_point = {item.point_id: item for item in self.structural.supports}

    # -- lookups -----------------------------------------------------------

    @property
    def has_geometry(self) -> bool:
        return bool(self.plans) and self.building.site is not None

    def plan_of_type(self, floor_type: FloorType) -> FloorPlanDefinition | None:
        for plan in self.plans:
            if plan.floor_type is floor_type:
                return plan
        return None

    def plans_of_type(self, floor_type: FloorType) -> list[FloorPlanDefinition]:
        return [plan for plan in self.plans if plan.floor_type is floor_type]

    def level_elevation(self, level_id: str | None) -> float:
        level = self.levels.get(level_id or "")
        if level is not None:
            return level.elevation
        plan = self.plan_by_level.get(level_id or "")
        return plan.elevation_m if plan is not None else 0.0

    def level_name(self, level_id: str | None) -> str:
        level = self.levels.get(level_id or "")
        if level is not None:
            return level.name
        return level_id or NOT_IN_PEM

    def grid_label_for_point(self, point_id: str | None) -> str:
        point = self.points.get(point_id or "")
        if point is None:
            return ""
        return str(point.metadata.get("grid_label", ""))

    def grid_reference(self, x: float, y: float, *, tolerance: float = 0.05) -> str:
        """Nearest grid intersection label, or '' when the point is off-grid."""
        x_label = _nearest_label(x, self.grid_x, self.grid_x_labels, tolerance)
        y_label = _nearest_label(y, self.grid_y, self.grid_y_labels, tolerance)
        if x_label and y_label:
            return f"{x_label}{y_label}"
        return ""

    def member_endpoints(self, member: StructuralMember) -> tuple[PointDefinition | None, PointDefinition | None]:
        line = self.lines.get(member.line_id or "")
        if line is not None:
            return self.points.get(line.start_point_id), self.points.get(line.end_point_id)
        return self.points.get(member.start_point_id or ""), self.points.get(member.end_point_id or "")

    def member_length_m(self, member: StructuralMember) -> float | None:
        start, end = self.member_endpoints(member)
        if start is None or end is None:
            return None
        return math.dist((start.x, start.y, start.z), (end.x, end.y, end.z))

    def section_name(self, member: StructuralMember) -> str:
        for table in (self.column_sections, self.beam_sections, self.slab_sections, self.wall_sections):
            section = table.get(member.section_id)
            if section is not None:
                return section.name
        return NOT_IN_PEM

    def governing_check(self, member_id: str) -> MemberDesignCheck | None:
        bucket = self.checks.get(member_id) or []
        if not bucket:
            return None
        return max(bucket, key=lambda item: item.utilization)

    def material_name(self, material_id: str) -> str:
        for table in (self.concrete, self.steel, self.rebar_materials):
            material = table.get(material_id)
            if material is not None:
                return material.name
        return NOT_IN_PEM

    @property
    def site_bounds(self) -> tuple[float, float, float, float]:
        site = self.building.site
        if site is None:
            return (0.0, 0.0, 1.0, 1.0)
        return site.boundary.bounds

    @property
    def footprint_bounds(self) -> tuple[float, float, float, float]:
        """Bounding box of the built footprint across all storeys."""
        boxes = [plan.boundary.bounds for plan in self.plans if plan.boundary.points]
        if not boxes:
            return self.site_bounds
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    @property
    def building_height_m(self) -> float:
        if not self.plans:
            return 0.0
        top = max(plan.elevation_m + plan.storey_height_m for plan in self.plans)
        base = min(plan.elevation_m for plan in self.plans)
        return round(top - base, 4)

    # -- 3D extraction -----------------------------------------------------

    def column_solids(self, *, level_ids: set[str] | None = None) -> list[Solid3D]:
        solids: list[Solid3D] = []
        for member in self.members_by_type.get(MemberType.COLUMN, []):
            if level_ids is not None and member.level_id not in level_ids:
                continue
            start, end = self.member_endpoints(member)
            node = start or end
            if node is None:
                continue
            section = self.column_sections.get(member.section_id)
            width = float(section.width) if section else 0.0
            depth = float(section.depth) if section else 0.0
            if width <= 0.0 or depth <= 0.0:
                continue
            z_low = min(start.z, end.z) if (start and end) else node.z
            z_high = max(start.z, end.z) if (start and end) else node.z + _MIN_EXTENT_M
            solids.append(
                Solid3D(
                    element_id=member.id,
                    element_kind=SourceElementKind.COLUMN,
                    footprint=_rect_points(node.x, node.y, width, depth),
                    min_z=z_low,
                    max_z=z_high,
                    level_id=member.level_id,
                    label=str(member.metadata.get("grid_label", member.name)),
                    metadata={
                        "section": section.name if section else NOT_IN_PEM,
                        "section_id": member.section_id,
                        "width_m": width,
                        "depth_m": depth,
                        "node_id": node.id,
                        "top_node_id": end.id if end is not None else None,
                        "x": node.x,
                        "y": node.y,
                        "orientation_deg": member.metadata.get("orientation_deg", NOT_IN_PEM),
                    },
                )
            )
        return solids

    def beam_solids(self, *, level_ids: set[str] | None = None) -> list[Solid3D]:
        solids: list[Solid3D] = []
        for member in self.members_by_type.get(MemberType.BEAM, []):
            if level_ids is not None and member.level_id not in level_ids:
                continue
            start, end = self.member_endpoints(member)
            if start is None or end is None:
                continue
            section = self.beam_sections.get(member.section_id)
            width = float(section.width) if section else 0.0
            depth = float(section.depth) if section else 0.0
            footprint = _swept_rect(start.x, start.y, end.x, end.y, max(width, _MIN_EXTENT_M))
            if footprint is None:
                continue
            top = self.level_elevation(member.level_id)
            grid_from = str(member.metadata.get("grid_from", ""))
            grid_to = str(member.metadata.get("grid_to", ""))
            label = f"{grid_from}-{grid_to}" if grid_from and grid_to else member.name
            solids.append(
                Solid3D(
                    element_id=member.id,
                    element_kind=SourceElementKind.BEAM,
                    footprint=footprint,
                    min_z=top - max(depth, _MIN_EXTENT_M),
                    max_z=top,
                    level_id=member.level_id,
                    label=label,
                    metadata={
                        "section": section.name if section else NOT_IN_PEM,
                        "section_id": member.section_id,
                        "width_m": width,
                        "depth_m": depth,
                        "direction": member.metadata.get("direction", NOT_IN_PEM),
                        "span_m": member.metadata.get("span_m"),
                        "start_point_id": start.id,
                        "end_point_id": end.id,
                        "start": (start.x, start.y),
                        "end": (end.x, end.y),
                        "grid_from": member.metadata.get("grid_from", ""),
                        "grid_to": member.metadata.get("grid_to", ""),
                    },
                )
            )
        return solids

    def slab_solids(self, *, level_ids: set[str] | None = None) -> list[Solid3D]:
        solids: list[Solid3D] = []
        for member in self.members_by_type.get(MemberType.SLAB, []):
            if level_ids is not None and member.level_id not in level_ids:
                continue
            area = self.areas.get(member.area_id or "")
            if area is None:
                continue
            boundary = [self.points.get(point_id) for point_id in area.boundary_point_ids]
            if any(point is None for point in boundary) or len(boundary) < 3:
                continue
            section = self.slab_sections.get(member.section_id)
            thickness = float(section.thickness) if section else 0.0
            top = self.level_elevation(member.level_id)
            diaphragm = self.diaphragm_by_level.get(member.level_id or "")
            solids.append(
                Solid3D(
                    element_id=member.id,
                    element_kind=SourceElementKind.SLAB,
                    footprint=[Point2D(x=point.x, y=point.y) for point in boundary if point],
                    min_z=top - max(thickness, _MIN_EXTENT_M),
                    max_z=top,
                    level_id=member.level_id,
                    label=str(member.metadata.get("panel_label", member.name)),
                    metadata={
                        "area_id": area.id,
                        "section": section.name if section else NOT_IN_PEM,
                        "section_id": member.section_id,
                        "thickness_m": thickness,
                        "span_x_m": member.metadata.get("span_x_m"),
                        "span_y_m": member.metadata.get("span_y_m"),
                        "area_m2": member.metadata.get("area_m2"),
                        "diaphragm_id": diaphragm.id if diaphragm else NOT_IN_PEM,
                        "boundary_point_ids": list(area.boundary_point_ids),
                    },
                )
            )
        return solids

    def footing_solids(self) -> list[Solid3D]:
        solids: list[Solid3D] = []
        for footing in self.footings:
            node = self.points.get(footing.point_id)
            if node is None:
                continue
            length = float(footing.length_m)
            width = float(footing.width_m)
            thickness = float(footing.thickness_m)
            if length <= 0.0 or width <= 0.0:
                continue
            top = node.z
            column = self.members.get(footing.column_member_id)
            solids.append(
                Solid3D(
                    element_id=footing.id,
                    element_kind=SourceElementKind.FOOTING,
                    footprint=_rect_points(node.x, node.y, length, width),
                    min_z=top - max(thickness, _MIN_EXTENT_M),
                    max_z=top,
                    level_id=column.level_id if column else node.level_id,
                    label=footing.id,
                    metadata={
                        "column_member_id": footing.column_member_id,
                        "grid_label": self.grid_label_for_point(footing.point_id),
                        "point_id": footing.point_id,
                        "length_m": length,
                        "width_m": width,
                        "thickness_m": thickness,
                        "top_elevation_m": top,
                        "underside_elevation_m": round(top - thickness, 4),
                        "utilization": footing.utilization,
                        "status": footing.status.value,
                        "bearing_demand_kPa": footing.bearing_demand_kPa,
                        "bearing_capacity_kPa": footing.bearing_capacity_kPa,
                        "x": node.x,
                        "y": node.y,
                    },
                )
            )
        return solids

    def wall_solids(self, *, level_ids: set[str] | None = None) -> list[Solid3D]:
        solids: list[Solid3D] = []
        for plan in self.plans:
            if level_ids is not None and plan.level_id not in level_ids:
                continue
            for wall in plan.walls:
                footprint = _swept_rect(
                    wall.start.x, wall.start.y, wall.end.x, wall.end.y, max(wall.thickness_m, _MIN_EXTENT_M)
                )
                if footprint is None:
                    continue
                solids.append(
                    Solid3D(
                        element_id=wall.id,
                        element_kind=SourceElementKind.WALL,
                        footprint=footprint,
                        min_z=plan.elevation_m,
                        max_z=plan.elevation_m + max(wall.height_m, _MIN_EXTENT_M),
                        level_id=plan.level_id,
                        label=wall.wall_type.value,
                        metadata={
                            "wall_type": wall.wall_type.value,
                            "thickness_m": wall.thickness_m,
                            "height_m": wall.height_m,
                            "length_m": wall.length_m,
                            "is_load_bearing": wall.is_load_bearing,
                            "start": (wall.start.x, wall.start.y),
                            "end": (wall.end.x, wall.end.y),
                        },
                    )
                )
        return solids

    def space_solids(self, *, level_ids: set[str] | None = None) -> list[Solid3D]:
        solids: list[Solid3D] = []
        for plan in self.plans:
            if level_ids is not None and plan.level_id not in level_ids:
                continue
            for space in plan.spaces:
                if len(space.boundary.points) < 3:
                    continue
                solids.append(
                    Solid3D(
                        element_id=space.id,
                        element_kind=SourceElementKind.SPACE,
                        footprint=list(space.boundary.points),
                        min_z=plan.elevation_m,
                        max_z=plan.elevation_m + max(plan.storey_height_m, _MIN_EXTENT_M),
                        level_id=plan.level_id,
                        label=space.name,
                        metadata={
                            "usage": space.usage.value,
                            "area_m2": space.area_m2,
                            "apartment_id": space.apartment_id or NOT_IN_PEM,
                        },
                    )
                )
        return solids

    def stair_solids(self) -> list[Solid3D]:
        solids: list[Solid3D] = []
        for stair in self.building.stairs:
            if len(stair.boundary.points) < 3:
                continue
            served = [self.level_elevation(level_id) for level_id in stair.served_level_ids]
            if served:
                low, high = min(served), max(served)
            else:
                low, high = 0.0, self.building_height_m
            solids.append(
                Solid3D(
                    element_id=stair.id,
                    element_kind=SourceElementKind.STAIR,
                    footprint=list(stair.boundary.points),
                    min_z=low,
                    max_z=max(high, low + _MIN_EXTENT_M),
                    level_id=stair.served_level_ids[0] if stair.served_level_ids else None,
                    label=stair.name,
                    metadata={
                        "served_level_ids": list(stair.served_level_ids),
                        "clear_width_m": stair.clear_width_m,
                        "riser_height_m": stair.riser_height_m,
                        "tread_depth_m": stair.tread_depth_m,
                        "flight_count_per_storey": stair.flight_count_per_storey,
                        "riser_count_per_storey": stair.riser_count_per_storey or NOT_IN_PEM,
                    },
                )
            )
        return solids

    def opening_solids(self, *, level_ids: set[str] | None = None) -> list[Solid3D]:
        """
        Doors and windows as 3D openings.

        The PEM leaves ``wall_id`` unset on doors and windows, so the host wall is
        *derived* by testing which wall segment the opening centre lies on. The
        derivation is recorded in metadata as ``wall_association`` so a reviewer
        can tell it apart from a stored relationship.
        """
        solids: list[Solid3D] = []
        for plan in self.plans:
            if level_ids is not None and plan.level_id not in level_ids:
                continue
            for door in plan.doors:
                solids.append(self._opening_solid(plan, door, is_door=True))
            for window in plan.windows:
                solids.append(self._opening_solid(plan, window, is_door=False))
        return solids

    def _opening_solid(
        self,
        plan: FloorPlanDefinition,
        opening: DoorDefinition | WindowDefinition,
        *,
        is_door: bool,
    ) -> Solid3D:
        host, axis = self._host_wall(plan, opening)
        if axis is None:
            axis = str(opening.metadata.get("edge_axis", "")) or "x"
        width = float(opening.width_m)
        thickness = float(host.thickness_m) if host is not None else 0.1
        if axis == "y":
            footprint = _rect_points(opening.center.x, opening.center.y, thickness, width)
        else:
            footprint = _rect_points(opening.center.x, opening.center.y, width, thickness)
        sill = 0.0 if is_door else float(getattr(opening, "sill_height_m", 0.0))
        return Solid3D(
            element_id=opening.id,
            element_kind=SourceElementKind.DOOR if is_door else SourceElementKind.WINDOW,
            footprint=footprint,
            min_z=plan.elevation_m + sill,
            max_z=plan.elevation_m + sill + max(float(opening.height_m), _MIN_EXTENT_M),
            level_id=plan.level_id,
            label=opening.id,
            metadata={
                "kind": "DOOR" if is_door else "WINDOW",
                "width_m": width,
                "height_m": opening.height_m,
                "sill_height_m": sill if not is_door else 0.0,
                "run_axis": axis,
                "center": (opening.center.x, opening.center.y),
                "wall_id": opening.wall_id or NOT_IN_PEM,
                "derived_wall_id": host.id if host is not None else NOT_IN_PEM,
                "wall_association": "DERIVED_BY_GEOMETRY" if host is not None else NOT_IN_PEM,
                "is_entrance": bool(getattr(opening, "is_entrance", False)),
            },
        )

    @staticmethod
    def _host_wall(
        plan: FloorPlanDefinition,
        opening: DoorDefinition | WindowDefinition,
    ) -> tuple[WallDefinition | None, str | None]:
        """Wall whose centreline the opening sits on, plus the axis it runs along."""
        best: WallDefinition | None = None
        best_distance = 0.35
        for wall in plan.walls:
            distance = _point_segment_distance(opening.center, wall.start, wall.end)
            if distance < best_distance:
                best = wall
                best_distance = distance
        if best is None:
            return (None, None)
        axis = "x" if abs(best.end.x - best.start.x) >= abs(best.end.y - best.start.y) else "y"
        return (best, axis)

    def parking_polygons(self, plan: FloorPlanDefinition) -> list[tuple[str, str, Polygon2D]]:
        return [(slot.id, slot.label, slot.boundary) for slot in plan.parking_spaces]


# ---------------------------------------------------------------------------
# geometry helpers
# ---------------------------------------------------------------------------


def _rect_points(center_x: float, center_y: float, width: float, depth: float) -> list[Point2D]:
    half_w = width / 2.0
    half_d = depth / 2.0
    return [
        Point2D(x=center_x - half_w, y=center_y - half_d),
        Point2D(x=center_x + half_w, y=center_y - half_d),
        Point2D(x=center_x + half_w, y=center_y + half_d),
        Point2D(x=center_x - half_w, y=center_y + half_d),
    ]


def _swept_rect(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    width: float,
) -> list[Point2D] | None:
    """The section rectangle of ``width`` swept along the segment."""
    dx = x2 - x1
    dy = y2 - y1
    length = math.hypot(dx, dy)
    if length <= _MIN_EXTENT_M:
        return None
    nx = -dy / length * width / 2.0
    ny = dx / length * width / 2.0
    return [
        Point2D(x=x1 + nx, y=y1 + ny),
        Point2D(x=x2 + nx, y=y2 + ny),
        Point2D(x=x2 - nx, y=y2 - ny),
        Point2D(x=x1 - nx, y=y1 - ny),
    ]


def _point_segment_distance(point: Point2D, start: Point2D, end: Point2D) -> float:
    dx = end.x - start.x
    dy = end.y - start.y
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return point.distance_to(start)
    t = ((point.x - start.x) * dx + (point.y - start.y) * dy) / length_squared
    t = max(0.0, min(1.0, t))
    return math.hypot(point.x - (start.x + t * dx), point.y - (start.y + t * dy))


def _nearest_label(
    value: float,
    ordinates: list[float],
    labels: list[str],
    tolerance: float,
) -> str:
    best = ""
    best_distance = tolerance
    for index, ordinate in enumerate(ordinates):
        distance = abs(ordinate - value)
        if distance <= best_distance and index < len(labels):
            best = labels[index]
            best_distance = distance
    return best
