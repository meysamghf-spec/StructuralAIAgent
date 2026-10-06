"""Spatial coordination between architecture and structure on the shared metre frame."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models.pem_architecture import BuildingModel, SpaceUsage
from app.domain.models.pem_structural import MemberType, PointDefinition, StructuralModel


@dataclass
class CoordinationConflict:
    severity: str  # HARD_CONFLICT | SOFT_CONFLICT | WARNING
    code: str
    message: str
    element_ids: list[str] = field(default_factory=list)
    auto_resolved: bool = False


@dataclass
class CoordinationResult:
    conflicts: list[CoordinationConflict]
    hard_count: int
    soft_count: int

    @property
    def requires_review(self) -> bool:
        return self.hard_count > 0


class CoordinationService:
    def check(self, building: BuildingModel, structural: StructuralModel) -> CoordinationResult:
        points = {point.id: point for point in structural.geometry.points}
        conflicts: list[CoordinationConflict] = []
        columns = [member for member in structural.members.members if member.member_type is MemberType.COLUMN]
        sections = {item.id: item for item in structural.sections.columns}
        for member in columns:
            point = points.get(member.start_point_id or "")
            if point is None:
                continue
            section = sections.get(member.section_id)
            half = max(
                float(getattr(section, "width", 0.4) or 0.4),
                float(getattr(section, "depth", 0.4) or 0.4),
            ) / 2.0
            end = points.get(member.end_point_id or "")
            occupied_levels = {member.level_id, point.level_id, end.level_id if end is not None else None}
            occupied_levels.discard(None)
            for plan in building.floor_plans:
                if occupied_levels and plan.level_id not in occupied_levels:
                    continue
                for door in plan.doors:
                    if _near(point, door.center.x, door.center.y, door.width_m / 2.0 + 0.15):
                        conflicts.append(
                            CoordinationConflict(
                                "HARD_CONFLICT",
                                "COLUMN_IN_DOOR",
                                f"{member.id} intersects door {door.id} on {plan.name}.",
                                [member.id, door.id],
                            )
                        )
                for space in plan.spaces:
                    if space.usage not in (SpaceUsage.STAIR, SpaceUsage.ELEVATOR):
                        continue
                    if not _inside_polygon(point, space.boundary.points):
                        continue
                    if _on_boundary(point, space.boundary.points, tol=half):
                        conflicts.append(
                            CoordinationConflict(
                                "WARNING",
                                "COLUMN_ON_CORE_WALL",
                                f"{member.id} sits on the {space.usage.value} enclosure wall {space.id} "
                                "(typical grid/core coincidence, not a blocked flight).",
                                [member.id, space.id],
                            )
                        )
                        continue
                    conflicts.append(
                        CoordinationConflict(
                            "HARD_CONFLICT",
                            "COLUMN_IN_CORE",
                            f"{member.id} sits inside {space.usage.value} {space.id}.",
                            [member.id, space.id],
                        )
                    )
                for slot in plan.parking_spaces:
                    if _inside_polygon(point, slot.boundary.points) and not _on_boundary(point, slot.boundary.points):
                        conflicts.append(
                            CoordinationConflict(
                                "SOFT_CONFLICT",
                                "COLUMN_IN_PARKING",
                                f"{member.id} is inside parking stall {slot.label}; stall still usable if the column is at a corner.",
                                [member.id, slot.id],
                            )
                        )
        beams = [member for member in structural.members.members if member.member_type is MemberType.BEAM]
        for member in beams:
            start = points.get(member.start_point_id or "")
            end = points.get(member.end_point_id or "")
            if start is None or end is None:
                continue
            for plan in building.floor_plans:
                if plan.level_id != member.level_id:
                    continue
                for door in plan.doors:
                    if _segment_near_point(start, end, door.center.x, door.center.y, 0.25):
                        conflicts.append(
                            CoordinationConflict(
                                "WARNING",
                                "BEAM_NEAR_OPENING",
                                f"{member.id} passes close to door {door.id}.",
                                [member.id, door.id],
                            )
                        )
        hard = sum(1 for item in conflicts if item.severity == "HARD_CONFLICT")
        soft = sum(1 for item in conflicts if item.severity == "SOFT_CONFLICT")
        return CoordinationResult(conflicts=conflicts, hard_count=hard, soft_count=soft)


def _near(point: PointDefinition, x: float, y: float, radius: float) -> bool:
    return (point.x - x) ** 2 + (point.y - y) ** 2 <= radius**2


def _inside_polygon(point: PointDefinition, vertices) -> bool:
    if len(vertices) < 3:
        return False
    inside = False
    j = len(vertices) - 1
    for i, vertex in enumerate(vertices):
        vi, vj = vertex, vertices[j]
        if (vi.y > point.y) != (vj.y > point.y) and point.x < (vj.x - vi.x) * (point.y - vi.y) / (vj.y - vi.y + 1e-16) + vi.x:
            inside = not inside
        j = i
    return inside


def _on_boundary(point: PointDefinition, vertices, tol: float = 0.20) -> bool:
    count = len(vertices)
    for index in range(count):
        a = vertices[index]
        b = vertices[(index + 1) % count]
        if _dist_point_segment(point.x, point.y, a.x, a.y, b.x, b.y) <= tol:
            return True
    return False


def _segment_near_point(start: PointDefinition, end: PointDefinition, x: float, y: float, tol: float) -> bool:
    return _dist_point_segment(x, y, start.x, start.y, end.x, end.y) <= tol


def _dist_point_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    dx, dy = bx - ax, by - ay
    length2 = dx * dx + dy * dy
    if length2 <= 1e-12:
        return ((px - ax) ** 2 + (py - ay) ** 2) ** 0.5
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length2))
    qx, qy = ax + t * dx, ay + t * dy
    return ((px - qx) ** 2 + (py - qy) ** 2) ** 0.5
