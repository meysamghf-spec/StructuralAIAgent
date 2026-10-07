"""
Shared view-construction helpers.

:class:`ViewCanvas` bundles the three things every view needs — the view record,
the primitive factory that hands out stable IDs, and the annotation engine — so
the sheet builders read as a list of what to draw rather than plumbing.

Geometry goes on ``view.primitives``; dimension lines, grid bubbles, labels and
markers go on ``view.annotations`` with their semantics mirrored into
``view.dimensions``. That split is what lets a sheet report "this much of my
geometry is traceable" without counting draughting furniture.
"""

from __future__ import annotations

from app.application.drawing.annotation import (
    AnnotationEngine,
    LAYER_GRID,
    PrimitiveFactory,
    text_height_for_span,
)
from app.application.drawing.pem_solids import PemDrawingContext
from app.application.drawing.projection import ProjectedPolygon
from app.domain.models.drawing import (
    DrawingPrimitive,
    DrawingView,
    ProjectionKind,
    SectionClip,
    SourceElementKind,
)
from app.domain.models.pem_architecture import Point2D, Polygon2D


class ViewCanvas:
    """Builder for a single :class:`DrawingView`."""

    def __init__(
        self,
        *,
        view_id: str,
        name: str,
        projection: ProjectionKind,
        projection_label: str,
        span_m: float,
        source_level_ids: list[str] | None = None,
        clip: SectionClip | None = None,
        metadata: dict | None = None,
        text_height_m: float | None = None,
    ) -> None:
        self.factory = PrimitiveFactory(view_id, projection_label)
        self.text_height_m = (
            text_height_m if text_height_m is not None else text_height_for_span(span_m)
        )
        self.anno = AnnotationEngine(self.factory, text_height_m=self.text_height_m)
        self._geometry: list[DrawingPrimitive] = []
        self.view = DrawingView(
            id=view_id,
            name=name,
            projection=projection,
            projection_label=projection_label,
            source_level_ids=list(source_level_ids or []),
            clip=clip,
            metadata=dict(metadata or {}),
        )

    # -- geometry ----------------------------------------------------------

    def add(self, primitive: DrawingPrimitive) -> DrawingPrimitive:
        self._geometry.append(primitive)
        return primitive

    def add_many(self, primitives: list[DrawingPrimitive]) -> None:
        self._geometry.extend(primitives)

    def add_polygon(
        self,
        points: list[Point2D],
        *,
        layer: str,
        source_element_ids: list[str],
        source_element_kind: SourceElementKind,
        metadata: dict | None = None,
    ) -> DrawingPrimitive:
        return self.add(
            self.factory.polygon(
                points,
                layer=layer,
                source_element_ids=source_element_ids,
                source_element_kind=source_element_kind,
                metadata=metadata,
            )
        )

    def add_ring(
        self,
        polygon: Polygon2D,
        *,
        layer: str,
        source_element_ids: list[str],
        source_element_kind: SourceElementKind,
        metadata: dict | None = None,
    ) -> DrawingPrimitive | None:
        if len(polygon.points) < 3:
            return None
        return self.add_polygon(
            list(polygon.points),
            layer=layer,
            source_element_ids=source_element_ids,
            source_element_kind=source_element_kind,
            metadata=metadata,
        )

    def add_projected(
        self,
        projected: list[ProjectedPolygon],
        *,
        layer: str,
        metadata_keys: tuple[str, ...] = (),
    ) -> list[DrawingPrimitive]:
        """Turn projected polygons into closed polylines, keeping their refs."""
        created: list[DrawingPrimitive] = []
        for item in projected:
            metadata = {key: item.metadata.get(key) for key in metadata_keys if key in item.metadata}
            metadata.update(
                {
                    "label": item.label,
                    "level_id": item.level_id,
                    "depth_m": item.depth_m,
                }
            )
            if item.metadata.get("clipped"):
                metadata["clipped"] = True
                metadata["clip_axis"] = item.metadata.get("clip_axis")
                metadata["clip_low_m"] = item.metadata.get("clip_low_m")
                metadata["clip_high_m"] = item.metadata.get("clip_high_m")
            created.append(
                self.add(
                    self.factory.polygon(
                        item.points,
                        layer=layer,
                        source_element_ids=[item.element_id],
                        source_element_kind=item.element_kind,
                        metadata=metadata,
                    )
                )
            )
        return created

    # -- finishing ---------------------------------------------------------

    def finish(self) -> DrawingView:
        self.view.primitives = self._geometry
        self.view.annotations = self.anno.primitives
        self.view.dimensions = self.anno.dimensions
        return self.view


def add_plan_grid(
    canvas: ViewCanvas,
    pem: PemDrawingContext,
    *,
    bounds: tuple[float, float, float, float],
    extension_m: float | None = None,
    dimension_chains: bool = True,
) -> None:
    """Grid lines, bubbles and the running dimension chains along both axes."""
    if pem.grid is None or not pem.grid_x or not pem.grid_y:
        return
    min_x, min_y, max_x, max_y = bounds
    extension = extension_m if extension_m is not None else max(max_x - min_x, max_y - min_y) * 0.05
    canvas.anno.grid(
        x_ordinates=pem.grid_x,
        x_labels=pem.grid_x_labels,
        y_ordinates=pem.grid_y,
        y_labels=pem.grid_y_labels,
        bounds=bounds,
        grid_id=pem.grid.id,
        extension_m=extension,
    )
    if not dimension_chains:
        return
    step = canvas.text_height_m
    canvas.anno.dimension_chain(
        pem.grid_x,
        axis="x",
        fixed=min_y - extension - step * 10.0,
        offset_m=0.0,
        source_element_ids=[pem.grid.id],
    )
    canvas.anno.dimension_chain(
        pem.grid_y,
        axis="y",
        fixed=min_x - extension - step * 10.0,
        offset_m=0.0,
        source_element_ids=[pem.grid.id],
    )


def add_overall_plan_dimensions(
    canvas: ViewCanvas,
    *,
    bounds: tuple[float, float, float, float],
    source_element_ids: list[str],
    source_element_kind: SourceElementKind,
    offset_m: float | None = None,
) -> None:
    """Overall width and depth dimensions outside the grid dimension chains."""
    min_x, min_y, max_x, max_y = bounds
    step = canvas.text_height_m
    gap = offset_m if offset_m is not None else step * 16.0
    canvas.anno.dimension(
        Point2D(x=min_x, y=min_y - gap),
        Point2D(x=max_x, y=min_y - gap),
        offset_m=0.0,
        source_element_ids=source_element_ids,
        source_element_kind=source_element_kind,
    )
    canvas.anno.dimension(
        Point2D(x=min_x - gap, y=max_y),
        Point2D(x=min_x - gap, y=min_y),
        offset_m=0.0,
        source_element_ids=source_element_ids,
        source_element_kind=source_element_kind,
    )


def add_level_markers(
    canvas: ViewCanvas,
    pem: PemDrawingContext,
    *,
    u_start: float,
    u_end: float,
) -> None:
    """A datum line and elevation tag for every PEM level."""
    for level in pem.levels_sorted:
        canvas.anno.level_marker(
            u_start=u_start,
            u_end=u_end,
            elevation_m=level.elevation,
            label=level.name,
            level_id=level.id,
        )


def add_storey_height_dimensions(
    canvas: ViewCanvas,
    pem: PemDrawingContext,
    *,
    u_position: float,
) -> None:
    """A vertical dimension chain of storey heights plus the overall height."""
    elevations = [level.elevation for level in pem.levels_sorted]
    if len(elevations) < 2:
        return
    for index in range(len(elevations) - 1):
        lower = pem.levels_sorted[index]
        upper = pem.levels_sorted[index + 1]
        canvas.anno.dimension(
            Point2D(x=u_position, y=lower.elevation),
            Point2D(x=u_position, y=upper.elevation),
            offset_m=0.0,
            source_element_ids=[lower.id, upper.id],
            source_element_kind=SourceElementKind.LEVEL,
        )
    overall = canvas.text_height_m * 10.0
    canvas.anno.dimension(
        Point2D(x=u_position - overall, y=elevations[0]),
        Point2D(x=u_position - overall, y=elevations[-1]),
        offset_m=0.0,
        text=f"{elevations[-1] - elevations[0]:.3f} m overall",
        source_element_ids=[level.id for level in pem.levels_sorted],
        source_element_kind=SourceElementKind.LEVEL,
    )


def grid_lines_in_elevation(
    canvas: ViewCanvas,
    pem: PemDrawingContext,
    *,
    ordinates: list[float],
    labels: list[str],
    origin: float,
    flip: bool,
    span: float,
    z_low: float,
    z_high: float,
) -> None:
    """Vertical grid lines on an elevation or section, with bubbles on top."""
    if pem.grid is None:
        return
    radius = canvas.text_height_m * 1.6
    for ordinate, label in zip(ordinates, labels, strict=False):
        u = (origin + span - ordinate) if flip else (ordinate - origin)
        canvas.add(
            canvas.factory.line(
                Point2D(x=u, y=z_low),
                Point2D(x=u, y=z_high),
                layer=LAYER_GRID,
                source_element_ids=[pem.grid.id],
                source_element_kind=SourceElementKind.GRID,
                metadata={"grid_label": label, "ordinate_m": ordinate},
            )
        )
        canvas.anno.grid_bubble(
            Point2D(x=u, y=z_high + radius * 1.4), label, radius, pem.grid.id, "elevation"
        )
