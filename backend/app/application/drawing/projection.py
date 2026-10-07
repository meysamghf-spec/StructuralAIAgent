"""
Reusable geometry projections for the drawing engine.

Three projections, all consuming :class:`Solid3D` and all deterministic:

**Plan** (``3D -> XY``) keeps the footprint polygon unchanged.

**Elevation** (``3D -> XZ`` or ``YZ``) is a true orthographic projection. The
camera basis is derived as ``right = forward x up`` with ``up = +z``, so the
drawing reads left-to-right the way the viewer sees it:

===========  ================  ==============  ==================
Elevation    viewer stands at  forward         drawing u axis
===========  ================  ==============  ==================
SOUTH        ``-y``            ``(0, +1, 0)``  ``x - min_x``
NORTH        ``+y``            ``(0, -1, 0)``  ``max_x - x``
EAST         ``+x``            ``(-1, 0, 0)``  ``y - min_y``
WEST         ``-x``            ``(+1, 0, 0)``  ``max_y - y``
===========  ================  ==============  ==================

Each projected polygon carries its depth from the viewing plane so a sheet
builder can keep the near facade and drop what sits behind it.

**Section** clips first and projects second. :func:`clip_solids_to_band` runs a
Sutherland-Hodgman clip of every footprint against the two half-planes of the
cut band and *discards* solids that fall outside it, so a section view contains
strictly less geometry than the model it came from.

Compass names assume the site is unrotated (plot north = ``+y``). Callers are
expected to say so on the sheet; :data:`ORIENTATION_NOTE` carries the wording.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.application.drawing.pem_solids import Solid3D
from app.domain.models.drawing import SourceElementKind
from app.domain.models.pem_architecture import Point2D

ORIENTATION_NOTE = (
    "Elevation and section compass names assume the site is unrotated "
    "(plot north = +y, site orientation 0°). Confirm against the survey."
)

_AREA_TOLERANCE = 1e-9


class ElevationDirection(StrEnum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"


class SectionDirection(StrEnum):
    #: Cut on a plane of constant x, looking in -x. Drawing u axis follows +y.
    LOOKING_WEST = "LOOKING_WEST"
    #: Cut on a plane of constant y, looking in +y. Drawing u axis follows +x.
    LOOKING_NORTH = "LOOKING_NORTH"


@dataclass(frozen=True)
class ProjectedPolygon:
    """A solid projected onto a drawing plane, still traced to its PEM element."""

    element_id: str
    element_kind: SourceElementKind
    points: list[Point2D]
    depth_m: float
    label: str = ""
    level_id: str | None = None
    projection: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        xs = [point.x for point in self.points]
        ys = [point.y for point in self.points]
        return (min(xs), min(ys), max(xs), max(ys))


# ---------------------------------------------------------------------------
# Plan projection: 3D -> XY
# ---------------------------------------------------------------------------


def project_plan(solids: list[Solid3D], *, projection_label: str) -> list[ProjectedPolygon]:
    """Drop the vertical extent and keep the footprint."""
    projected: list[ProjectedPolygon] = []
    for solid in solids:
        if len(solid.footprint) < 3:
            continue
        projected.append(
            ProjectedPolygon(
                element_id=solid.element_id,
                element_kind=solid.element_kind,
                points=list(solid.footprint),
                depth_m=solid.max_z,
                label=solid.label,
                level_id=solid.level_id,
                projection=projection_label,
                metadata=dict(solid.metadata),
            )
        )
    return projected


# ---------------------------------------------------------------------------
# Elevation projection: 3D -> XZ / YZ
# ---------------------------------------------------------------------------


def project_elevation(
    solids: list[Solid3D],
    *,
    direction: ElevationDirection,
    model_bounds: tuple[float, float, float, float],
    projection_label: str | None = None,
) -> list[ProjectedPolygon]:
    """
    Orthographic projection of each solid onto the elevation plane.

    Returns polygons sorted nearest-viewer first, so a caller can apply its own
    depth window without re-sorting.
    """
    label = projection_label or f"ELEVATION:{direction.value}"
    projected: list[ProjectedPolygon] = []
    for solid in solids:
        if len(solid.footprint) < 3:
            continue
        us = [_elevation_u(point.x, point.y, direction, model_bounds) for point in solid.footprint]
        depths = [_elevation_depth(point.x, point.y, direction, model_bounds) for point in solid.footprint]
        u_min, u_max = min(us), max(us)
        if u_max - u_min <= _AREA_TOLERANCE or solid.max_z - solid.min_z <= _AREA_TOLERANCE:
            continue
        projected.append(
            ProjectedPolygon(
                element_id=solid.element_id,
                element_kind=solid.element_kind,
                points=[
                    Point2D(x=u_min, y=solid.min_z),
                    Point2D(x=u_max, y=solid.min_z),
                    Point2D(x=u_max, y=solid.max_z),
                    Point2D(x=u_min, y=solid.max_z),
                ],
                depth_m=round(min(depths), 6),
                label=solid.label,
                level_id=solid.level_id,
                projection=label,
                metadata={
                    **solid.metadata,
                    "elevation_direction": direction.value,
                    "depth_near_m": round(min(depths), 6),
                    "depth_far_m": round(max(depths), 6),
                    "z_range_m": (solid.min_z, solid.max_z),
                },
            )
        )
    projected.sort(key=lambda item: (item.depth_m, item.element_id))
    return projected


def elevation_span(
    direction: ElevationDirection,
    model_bounds: tuple[float, float, float, float],
) -> float:
    """Width of the elevation drawing for a given facade."""
    min_x, min_y, max_x, max_y = model_bounds
    if direction in (ElevationDirection.NORTH, ElevationDirection.SOUTH):
        return max_x - min_x
    return max_y - min_y


def _elevation_u(
    x: float,
    y: float,
    direction: ElevationDirection,
    bounds: tuple[float, float, float, float],
) -> float:
    min_x, min_y, max_x, max_y = bounds
    if direction is ElevationDirection.SOUTH:
        return x - min_x
    if direction is ElevationDirection.NORTH:
        return max_x - x
    if direction is ElevationDirection.EAST:
        return y - min_y
    return max_y - y


def _elevation_depth(
    x: float,
    y: float,
    direction: ElevationDirection,
    bounds: tuple[float, float, float, float],
) -> float:
    min_x, min_y, max_x, max_y = bounds
    if direction is ElevationDirection.SOUTH:
        return y - min_y
    if direction is ElevationDirection.NORTH:
        return max_y - y
    if direction is ElevationDirection.EAST:
        return max_x - x
    return x - min_x


def filter_near_facade(
    projected: list[ProjectedPolygon],
    *,
    depth_window_m: float,
) -> list[ProjectedPolygon]:
    """Keep only what sits within ``depth_window_m`` of the viewing plane."""
    return [item for item in projected if item.depth_m <= depth_window_m + _AREA_TOLERANCE]


# ---------------------------------------------------------------------------
# Section: clip, then project
# ---------------------------------------------------------------------------


def clip_solids_to_band(
    solids: list[Solid3D],
    *,
    axis: str,
    position_m: float,
    band_width_m: float,
) -> list[Solid3D]:
    """
    Clip footprints to the cut band on ``axis`` and drop everything outside it.

    This is a real clip: survivors come back with their footprints trimmed to the
    band, and solids that do not reach the band are not returned at all.
    """
    if axis not in ("x", "y"):
        raise ValueError(f"Section clipping expects axis 'x' or 'y', got {axis!r}")
    low = position_m - band_width_m / 2.0
    high = position_m + band_width_m / 2.0
    index = 0 if axis == "x" else 1

    clipped: list[Solid3D] = []
    for solid in solids:
        if not solid.intersects_band(axis, low, high):
            continue
        polygon = _clip_half_plane(solid.footprint, index, low, keep_greater=True)
        polygon = _clip_half_plane(polygon, index, high, keep_greater=False)
        if len(polygon) < 3 or _polygon_area(polygon) <= _AREA_TOLERANCE:
            continue
        clipped.append(
            Solid3D(
                element_id=solid.element_id,
                element_kind=solid.element_kind,
                footprint=polygon,
                min_z=solid.min_z,
                max_z=solid.max_z,
                level_id=solid.level_id,
                label=solid.label,
                metadata={
                    **solid.metadata,
                    "clipped": True,
                    "clip_axis": axis,
                    "clip_low_m": round(low, 6),
                    "clip_high_m": round(high, 6),
                },
            )
        )
    return clipped


def project_section(
    solids: list[Solid3D],
    *,
    direction: SectionDirection,
    position_m: float,
    band_width_m: float,
    model_bounds: tuple[float, float, float, float],
    projection_label: str,
) -> list[ProjectedPolygon]:
    """Clip against the cut band, then project the survivors onto the cut plane."""
    axis = "x" if direction is SectionDirection.LOOKING_WEST else "y"
    clipped = clip_solids_to_band(
        solids, axis=axis, position_m=position_m, band_width_m=band_width_m
    )
    min_x, min_y, max_x, max_y = model_bounds
    projected: list[ProjectedPolygon] = []
    for solid in clipped:
        if direction is SectionDirection.LOOKING_WEST:
            us = [point.y - min_y for point in solid.footprint]
            depths = [max_x - point.x for point in solid.footprint]
        else:
            us = [point.x - min_x for point in solid.footprint]
            depths = [point.y - min_y for point in solid.footprint]
        u_min, u_max = min(us), max(us)
        if u_max - u_min <= _AREA_TOLERANCE or solid.max_z - solid.min_z <= _AREA_TOLERANCE:
            continue
        projected.append(
            ProjectedPolygon(
                element_id=solid.element_id,
                element_kind=solid.element_kind,
                points=[
                    Point2D(x=u_min, y=solid.min_z),
                    Point2D(x=u_max, y=solid.min_z),
                    Point2D(x=u_max, y=solid.max_z),
                    Point2D(x=u_min, y=solid.max_z),
                ],
                depth_m=round(min(depths), 6),
                label=solid.label,
                level_id=solid.level_id,
                projection=projection_label,
                metadata={
                    **solid.metadata,
                    "section_direction": direction.value,
                    "section_position_m": position_m,
                    "section_band_width_m": band_width_m,
                    "z_range_m": (solid.min_z, solid.max_z),
                },
            )
        )
    projected.sort(key=lambda item: (item.element_kind.value, item.element_id))
    return projected


def section_span(
    direction: SectionDirection,
    model_bounds: tuple[float, float, float, float],
) -> float:
    min_x, min_y, max_x, max_y = model_bounds
    if direction is SectionDirection.LOOKING_WEST:
        return max_y - min_y
    return max_x - min_x


def _clip_half_plane(
    points: list[Point2D],
    index: int,
    value: float,
    *,
    keep_greater: bool,
) -> list[Point2D]:
    """Sutherland-Hodgman clip against an axis-aligned half-plane."""
    if not points:
        return []

    def inside(point: Point2D) -> bool:
        coordinate = point.x if index == 0 else point.y
        return coordinate >= value - _AREA_TOLERANCE if keep_greater else coordinate <= value + _AREA_TOLERANCE

    def intersect(start: Point2D, end: Point2D) -> Point2D:
        start_c = start.x if index == 0 else start.y
        end_c = end.x if index == 0 else end.y
        span = end_c - start_c
        if abs(span) <= _AREA_TOLERANCE:
            return Point2D(x=end.x, y=end.y)
        t = (value - start_c) / span
        return Point2D(x=start.x + (end.x - start.x) * t, y=start.y + (end.y - start.y) * t)

    result: list[Point2D] = []
    count = len(points)
    for position in range(count):
        current = points[position]
        following = points[(position + 1) % count]
        current_in = inside(current)
        following_in = inside(following)
        if current_in:
            result.append(current)
        if current_in != following_in:
            result.append(intersect(current, following))
    return result


def _polygon_area(points: list[Point2D]) -> float:
    if len(points) < 3:
        return 0.0
    total = 0.0
    count = len(points)
    for index in range(count):
        current = points[index]
        following = points[(index + 1) % count]
        total += current.x * following.y - following.x * current.y
    return abs(total) / 2.0
