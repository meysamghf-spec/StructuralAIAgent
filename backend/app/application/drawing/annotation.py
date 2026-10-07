"""
Reusable annotation engine.

Everything a draughtsman adds on top of projected geometry lives here:
dimension lines with extension lines and ticks, grid bubbles, level markers, a
north arrow, element and room labels, and section/elevation markers.

Annotations are *generated from geometry* — a dimension is told which two points
it measures and derives its own text from the distance, rather than being handed
a number. Primitive IDs are allocated sequentially from the owning view ID, so a
deterministic build produces deterministic IDs.

Text heights are expressed in model metres. :func:`text_height_for_span` ties
them to the view extent so a 1:100 floor plan and a 1:10 rebar detail both come
out legible once the renderer fits the view to its frame.
"""

from __future__ import annotations

import math

from app.domain.models.drawing import (
    DimensionOrientation,
    DrawingDimension,
    DrawingPrimitive,
    PrimitiveKind,
    SourceElementKind,
)
from app.domain.models.pem_architecture import Point2D

LAYER_SITE = "SITE"
LAYER_OUTLINE = "OUTLINE"
LAYER_GRID = "GRID"
LAYER_GRID_BUBBLE = "GRID-BUBBLE"
LAYER_DIMENSIONS = "DIMENSIONS"
LAYER_TEXT = "TEXT"
LAYER_WALLS = "WALLS"
LAYER_SPACES = "SPACES"
LAYER_DOORS = "DOORS"
LAYER_WINDOWS = "WINDOWS"
LAYER_PARKING = "PARKING"
LAYER_STAIRS = "STAIRS"
LAYER_COLUMNS = "COLUMNS"
LAYER_BEAMS = "BEAMS"
LAYER_SLABS = "SLABS"
LAYER_FOUNDATIONS = "FOUNDATIONS"
LAYER_DIAPHRAGM = "DIAPHRAGM"
LAYER_SECTION_CUT = "SECTION-CUT"
LAYER_SECTION_BEYOND = "SECTION-BEYOND"
LAYER_ELEVATION = "ELEVATION"
LAYER_LEVELS = "LEVELS"
LAYER_MARKERS = "MARKERS"
LAYER_REINFORCEMENT = "REINFORCEMENT"
LAYER_NOTES = "NOTES"
LAYER_SCHEDULE = "SCHEDULE"
LAYER_NORTH_ARROW = "NORTH-ARROW"


def text_height_for_span(span_m: float, *, ratio: float = 110.0) -> float:
    """Model-space text height that stays legible at any view scale."""
    return max(abs(span_m), 1e-6) / ratio


class PrimitiveFactory:
    """Allocates stable, sequential primitive IDs inside one view."""

    def __init__(self, view_id: str, projection: str = "") -> None:
        self._view_id = view_id
        self._projection = projection
        self._counter = 0

    @property
    def projection(self) -> str:
        return self._projection

    def next_id(self) -> str:
        self._counter += 1
        return f"{self._view_id}#{self._counter:04d}"

    def _next_id(self) -> str:
        return self.next_id()

    def line(
        self,
        start: Point2D,
        end: Point2D,
        *,
        layer: str,
        source_element_ids: list[str] | None = None,
        source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION,
        metadata: dict | None = None,
    ) -> DrawingPrimitive:
        return DrawingPrimitive(
            id=self._next_id(),
            kind=PrimitiveKind.LINE,
            layer=layer,
            points=[start, end],
            source_element_ids=list(source_element_ids or []),
            source_element_kind=source_element_kind,
            projection=self._projection,
            metadata=dict(metadata or {}),
        )

    def polyline(
        self,
        points: list[Point2D],
        *,
        layer: str,
        closed: bool = False,
        source_element_ids: list[str] | None = None,
        source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION,
        metadata: dict | None = None,
    ) -> DrawingPrimitive:
        return DrawingPrimitive(
            id=self._next_id(),
            kind=PrimitiveKind.POLYLINE,
            layer=layer,
            points=list(points),
            closed=closed,
            source_element_ids=list(source_element_ids or []),
            source_element_kind=source_element_kind,
            projection=self._projection,
            metadata=dict(metadata or {}),
        )

    def polygon(self, points: list[Point2D], **kwargs) -> DrawingPrimitive:
        return self.polyline(points, closed=True, **kwargs)

    def circle(
        self,
        center: Point2D,
        radius_m: float,
        *,
        layer: str,
        source_element_ids: list[str] | None = None,
        source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION,
        metadata: dict | None = None,
    ) -> DrawingPrimitive:
        return DrawingPrimitive(
            id=self._next_id(),
            kind=PrimitiveKind.CIRCLE,
            layer=layer,
            points=[center],
            radius_m=radius_m,
            source_element_ids=list(source_element_ids or []),
            source_element_kind=source_element_kind,
            projection=self._projection,
            metadata=dict(metadata or {}),
        )

    def text(
        self,
        position: Point2D,
        value: str,
        *,
        layer: str = LAYER_TEXT,
        height_m: float = 0.25,
        rotation_deg: float = 0.0,
        anchor: str = "CENTER",
        source_element_ids: list[str] | None = None,
        source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION,
        metadata: dict | None = None,
    ) -> DrawingPrimitive:
        return DrawingPrimitive(
            id=self._next_id(),
            kind=PrimitiveKind.TEXT,
            layer=layer,
            points=[position],
            text=value,
            text_height_m=height_m,
            rotation_deg=rotation_deg,
            text_anchor=anchor,
            source_element_ids=list(source_element_ids or []),
            source_element_kind=source_element_kind,
            projection=self._projection,
            metadata=dict(metadata or {}),
        )


class AnnotationEngine:
    """
    Collects annotation primitives and dimension records for one view.

    ``primitives`` is the geometry a renderer draws; ``dimensions`` is the
    semantic record of what was measured, which the API and the regression tests
    read.
    """

    def __init__(self, factory: PrimitiveFactory, *, text_height_m: float) -> None:
        self.factory = factory
        self.primitives: list[DrawingPrimitive] = []
        self.dimensions: list[DrawingDimension] = []
        self._text_height = text_height_m
        self._dimension_counter = 0

    @property
    def text_height_m(self) -> float:
        return self._text_height

    # -- dimensions --------------------------------------------------------

    def dimension(
        self,
        start: Point2D,
        end: Point2D,
        *,
        offset_m: float,
        source_element_ids: list[str] | None = None,
        source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION,
        text: str | None = None,
        unit_suffix: str = "",
        layer: str = LAYER_DIMENSIONS,
    ) -> DrawingDimension | None:
        """
        A dimension line, its two extension lines, end ticks and its text.

        ``offset_m`` shifts the dimension line along the segment's left normal;
        the measured value is always derived from the geometry.
        """
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy)
        if length <= 1e-9:
            return None
        self._dimension_counter += 1
        ux, uy = dx / length, dy / length
        nx, ny = -uy, ux
        dim_start = Point2D(x=start.x + nx * offset_m, y=start.y + ny * offset_m)
        dim_end = Point2D(x=end.x + nx * offset_m, y=end.y + ny * offset_m)

        if abs(dy) <= 1e-9:
            orientation = DimensionOrientation.HORIZONTAL
        elif abs(dx) <= 1e-9:
            orientation = DimensionOrientation.VERTICAL
        else:
            orientation = DimensionOrientation.ALIGNED

        label = text if text is not None else f"{length:.2f}{unit_suffix or ' m'}"
        record = DrawingDimension(
            id=f"{self.factory.next_id()}-DIM{self._dimension_counter:03d}",
            start=start,
            end=end,
            offset_m=offset_m,
            orientation=orientation,
            value_m=round(length, 6),
            text=label,
            layer=layer,
            source_element_ids=list(source_element_ids or []),
            source_element_kind=source_element_kind,
        )
        self.dimensions.append(record)

        common = {
            "layer": layer,
            "source_element_ids": list(source_element_ids or []),
            "source_element_kind": source_element_kind,
            "metadata": {"dimension_id": record.id, "role": "dimension"},
        }
        self.primitives.append(self.factory.line(dim_start, dim_end, **common))
        # Extension lines run from the measured point just past the dimension line.
        overshoot = self._text_height * 0.8
        for base, tip in ((start, dim_start), (end, dim_end)):
            self.primitives.append(
                self.factory.line(
                    base,
                    Point2D(x=tip.x + nx * math.copysign(overshoot, offset_m or 1.0),
                            y=tip.y + ny * math.copysign(overshoot, offset_m or 1.0)),
                    **{**common, "metadata": {"dimension_id": record.id, "role": "extension"}},
                )
            )
        tick = self._text_height * 0.9
        for anchor in (dim_start, dim_end):
            self.primitives.append(
                self.factory.line(
                    Point2D(x=anchor.x - (ux + nx) * tick / 2.0, y=anchor.y - (uy + ny) * tick / 2.0),
                    Point2D(x=anchor.x + (ux + nx) * tick / 2.0, y=anchor.y + (uy + ny) * tick / 2.0),
                    **{**common, "metadata": {"dimension_id": record.id, "role": "tick"}},
                )
            )
        mid = Point2D(
            x=(dim_start.x + dim_end.x) / 2.0 + nx * self._text_height * 0.5,
            y=(dim_start.y + dim_end.y) / 2.0 + ny * self._text_height * 0.5,
        )
        rotation = 90.0 if orientation is DimensionOrientation.VERTICAL else 0.0
        self.primitives.append(
            self.factory.text(
                mid,
                label,
                layer=layer,
                height_m=self._text_height,
                rotation_deg=rotation,
                source_element_ids=list(source_element_ids or []),
                source_element_kind=source_element_kind,
                metadata={"dimension_id": record.id, "role": "dimension-text"},
            )
        )
        return record

    def dimension_chain(
        self,
        ordinates: list[float],
        *,
        axis: str,
        fixed: float,
        offset_m: float,
        source_element_ids: list[str] | None = None,
        source_element_kind: SourceElementKind = SourceElementKind.GRID,
    ) -> list[DrawingDimension]:
        """A running chain of dimensions between consecutive grid ordinates."""
        records: list[DrawingDimension] = []
        for index in range(len(ordinates) - 1):
            low, high = ordinates[index], ordinates[index + 1]
            if axis == "x":
                start, end = Point2D(x=low, y=fixed), Point2D(x=high, y=fixed)
            else:
                start, end = Point2D(x=fixed, y=low), Point2D(x=fixed, y=high)
            record = self.dimension(
                start,
                end,
                offset_m=offset_m,
                source_element_ids=source_element_ids,
                source_element_kind=source_element_kind,
            )
            if record is not None:
                records.append(record)
        return records

    # -- grids -------------------------------------------------------------

    def grid(
        self,
        *,
        x_ordinates: list[float],
        x_labels: list[str],
        y_ordinates: list[float],
        y_labels: list[str],
        bounds: tuple[float, float, float, float],
        grid_id: str,
        extension_m: float,
    ) -> None:
        """Grid lines plus lettered/numbered bubbles at both ends of each line."""
        min_x, min_y, max_x, max_y = bounds
        radius = self._text_height * 1.6
        for ordinate, label in zip(x_ordinates, x_labels, strict=False):
            self.primitives.append(
                self.factory.line(
                    Point2D(x=ordinate, y=min_y - extension_m),
                    Point2D(x=ordinate, y=max_y + extension_m),
                    layer=LAYER_GRID,
                    source_element_ids=[grid_id],
                    source_element_kind=SourceElementKind.GRID,
                    metadata={"axis": "x", "ordinate_m": ordinate, "grid_label": label},
                )
            )
            for y_anchor in (min_y - extension_m - radius, max_y + extension_m + radius):
                self.grid_bubble(Point2D(x=ordinate, y=y_anchor), label, radius, grid_id, "x")
        for ordinate, label in zip(y_ordinates, y_labels, strict=False):
            self.primitives.append(
                self.factory.line(
                    Point2D(x=min_x - extension_m, y=ordinate),
                    Point2D(x=max_x + extension_m, y=ordinate),
                    layer=LAYER_GRID,
                    source_element_ids=[grid_id],
                    source_element_kind=SourceElementKind.GRID,
                    metadata={"axis": "y", "ordinate_m": ordinate, "grid_label": label},
                )
            )
            for x_anchor in (min_x - extension_m - radius, max_x + extension_m + radius):
                self.grid_bubble(Point2D(x=x_anchor, y=ordinate), label, radius, grid_id, "y")

    def grid_bubble(self, center: Point2D, label: str, radius: float, grid_id: str, axis: str) -> None:
        """A single grid bubble: ring plus its label."""
        self.primitives.append(
            self.factory.circle(
                center,
                radius,
                layer=LAYER_GRID_BUBBLE,
                source_element_ids=[grid_id],
                source_element_kind=SourceElementKind.GRID,
                metadata={"grid_label": label, "axis": axis, "role": "grid-bubble"},
            )
        )
        self.primitives.append(
            self.factory.text(
                Point2D(x=center.x, y=center.y - self._text_height * 0.35),
                label,
                layer=LAYER_GRID_BUBBLE,
                height_m=self._text_height,
                source_element_ids=[grid_id],
                source_element_kind=SourceElementKind.GRID,
                metadata={"grid_label": label, "axis": axis, "role": "grid-bubble-text"},
            )
        )

    # -- markers -----------------------------------------------------------

    def north_arrow(self, center: Point2D, size_m: float, *, site_id: str | None = None) -> None:
        tip = Point2D(x=center.x, y=center.y + size_m)
        left = Point2D(x=center.x - size_m * 0.32, y=center.y - size_m * 0.45)
        right = Point2D(x=center.x + size_m * 0.32, y=center.y - size_m * 0.45)
        tail = Point2D(x=center.x, y=center.y - size_m * 0.12)
        refs = [site_id] if site_id else []
        self.primitives.append(
            self.factory.polygon(
                [tip, right, tail, left],
                layer=LAYER_NORTH_ARROW,
                source_element_ids=refs,
                source_element_kind=SourceElementKind.SITE if site_id else SourceElementKind.ANNOTATION,
                metadata={"role": "north-arrow"},
            )
        )
        self.primitives.append(
            self.factory.circle(
                center,
                size_m * 0.75,
                layer=LAYER_NORTH_ARROW,
                source_element_ids=refs,
                source_element_kind=SourceElementKind.SITE if site_id else SourceElementKind.ANNOTATION,
                metadata={"role": "north-arrow-ring"},
            )
        )
        self.primitives.append(
            self.factory.text(
                Point2D(x=center.x, y=center.y + size_m * 1.15),
                "N",
                layer=LAYER_NORTH_ARROW,
                height_m=self._text_height * 1.2,
                metadata={"role": "north-arrow-text"},
            )
        )

    def level_marker(
        self,
        *,
        u_start: float,
        u_end: float,
        elevation_m: float,
        label: str,
        level_id: str,
    ) -> None:
        """A level datum line with a triangular tick and an elevation tag."""
        self.primitives.append(
            self.factory.line(
                Point2D(x=u_start, y=elevation_m),
                Point2D(x=u_end, y=elevation_m),
                layer=LAYER_LEVELS,
                source_element_ids=[level_id],
                source_element_kind=SourceElementKind.LEVEL,
                metadata={"role": "level-datum", "elevation_m": elevation_m},
            )
        )
        size = self._text_height * 1.1
        self.primitives.append(
            self.factory.polygon(
                [
                    Point2D(x=u_end, y=elevation_m),
                    Point2D(x=u_end + size, y=elevation_m + size * 0.7),
                    Point2D(x=u_end + size, y=elevation_m - size * 0.7),
                ],
                layer=LAYER_LEVELS,
                source_element_ids=[level_id],
                source_element_kind=SourceElementKind.LEVEL,
                metadata={"role": "level-tick"},
            )
        )
        self.primitives.append(
            self.factory.text(
                Point2D(x=u_end + size * 1.4, y=elevation_m + self._text_height * 0.3),
                f"{label}  +{elevation_m:.3f}",
                layer=LAYER_LEVELS,
                height_m=self._text_height,
                anchor="LEFT",
                source_element_ids=[level_id],
                source_element_kind=SourceElementKind.LEVEL,
                metadata={"role": "level-text", "elevation_m": elevation_m},
            )
        )

    def element_label(
        self,
        position: Point2D,
        value: str,
        *,
        source_element_ids: list[str],
        source_element_kind: SourceElementKind,
        layer: str = LAYER_TEXT,
        scale: float = 1.0,
    ) -> None:
        self.primitives.append(
            self.factory.text(
                position,
                value,
                layer=layer,
                height_m=self._text_height * scale,
                source_element_ids=source_element_ids,
                source_element_kind=source_element_kind,
                metadata={"role": "element-label"},
            )
        )

    def room_label(
        self,
        centroid: Point2D,
        *,
        space_id: str,
        name: str,
        area_m2: float | None,
        usage: str,
    ) -> None:
        self.primitives.append(
            self.factory.text(
                Point2D(x=centroid.x, y=centroid.y + self._text_height * 0.7),
                name,
                layer=LAYER_TEXT,
                height_m=self._text_height,
                source_element_ids=[space_id],
                source_element_kind=SourceElementKind.SPACE,
                metadata={"role": "room-name", "usage": usage},
            )
        )
        area_text = f"{area_m2:.2f} m²" if area_m2 is not None else "area N/A"
        self.primitives.append(
            self.factory.text(
                Point2D(x=centroid.x, y=centroid.y - self._text_height * 0.6),
                area_text,
                layer=LAYER_TEXT,
                height_m=self._text_height * 0.85,
                source_element_ids=[space_id],
                source_element_kind=SourceElementKind.SPACE,
                metadata={"role": "room-area", "area_m2": area_m2},
            )
        )

    def section_marker(
        self,
        *,
        start: Point2D,
        end: Point2D,
        label: str,
        target_sheet: str,
        source_element_ids: list[str] | None = None,
    ) -> None:
        """The cut line and the two flagged heads of a section marker."""
        self.primitives.append(
            self.factory.line(
                start,
                end,
                layer=LAYER_MARKERS,
                source_element_ids=list(source_element_ids or []),
                source_element_kind=SourceElementKind.ANNOTATION,
                metadata={"role": "section-cut-line", "section_label": label, "target_sheet": target_sheet},
            )
        )
        radius = self._text_height * 1.8
        dx = end.x - start.x
        dy = end.y - start.y
        length = math.hypot(dx, dy) or 1.0
        ux, uy = dx / length, dy / length
        for anchor, sign in ((start, -1.0), (end, 1.0)):
            center = Point2D(x=anchor.x + ux * sign * radius, y=anchor.y + uy * sign * radius)
            self.primitives.append(
                self.factory.circle(
                    center,
                    radius,
                    layer=LAYER_MARKERS,
                    metadata={"role": "section-marker-head", "section_label": label},
                )
            )
            self.primitives.append(
                self.factory.text(
                    Point2D(x=center.x, y=center.y - self._text_height * 0.35),
                    label,
                    layer=LAYER_MARKERS,
                    height_m=self._text_height,
                    metadata={"role": "section-marker-text", "target_sheet": target_sheet},
                )
            )
            # Direction-of-view flag.
            self.primitives.append(
                self.factory.line(
                    center,
                    Point2D(x=center.x - uy * radius * 1.4, y=center.y + ux * radius * 1.4),
                    layer=LAYER_MARKERS,
                    metadata={"role": "section-view-direction", "section_label": label},
                )
            )

    def elevation_marker(
        self,
        center: Point2D,
        *,
        label: str,
        direction: str,
        target_sheet: str,
    ) -> None:
        radius = self._text_height * 1.8
        self.primitives.append(
            self.factory.circle(
                center,
                radius,
                layer=LAYER_MARKERS,
                metadata={"role": "elevation-marker", "direction": direction, "target_sheet": target_sheet},
            )
        )
        self.primitives.append(
            self.factory.text(
                Point2D(x=center.x, y=center.y - self._text_height * 0.35),
                label,
                layer=LAYER_MARKERS,
                height_m=self._text_height,
                metadata={"role": "elevation-marker-text", "direction": direction},
            )
        )

    def note_block(
        self,
        origin: Point2D,
        lines: list[str],
        *,
        line_spacing_m: float | None = None,
        layer: str = LAYER_NOTES,
        scale: float = 1.0,
        source_element_ids: list[str] | None = None,
        source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION,
    ) -> None:
        """
        A block of note lines.

        ``source_element_ids`` lets a note that reports PEM data — a level table,
        a material list — stay traceable to the elements it was read from.
        """
        spacing = line_spacing_m if line_spacing_m is not None else self._text_height * 1.8
        for index, line in enumerate(lines):
            self.primitives.append(
                self.factory.text(
                    Point2D(x=origin.x, y=origin.y - index * spacing),
                    line,
                    layer=layer,
                    height_m=self._text_height * scale,
                    anchor="LEFT",
                    source_element_ids=list(source_element_ids or []),
                    source_element_kind=source_element_kind,
                    metadata={"role": "note", "line_index": index},
                )
            )
