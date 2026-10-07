"""
Drawing-set domain model.

A :class:`DrawingSet` is a *derived* view of the PEM, never a second model. Every
piece of geometry on a sheet carries ``source_element_ids`` pointing back at the
PEM element it was projected from, so the question "which PEM element generated
this drawing geometry?" always has an answer.

Coordinates follow the PEM convention: metres, ``+x`` along the frontage, ``+y``
into the plot depth, ``+z`` up. View geometry stays in *projected model metres*;
turning that into paper units is the renderer's job, driven by
:class:`ViewPlacement`.

:class:`Point2D` is reused from ``pem_architecture`` on purpose — this module adds
no new geometry primitives of its own.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, computed_field

from app.domain.models.pem_architecture import Point2D

# Engineering-safety sentinels. A drawing must say that something is unknown
# rather than invent it.
NOT_AVAILABLE = "NOT_AVAILABLE"
NOT_IN_PEM = "N/A — not available in PEM"


class Discipline(StrEnum):
    ARCHITECTURAL = "ARCHITECTURAL"
    STRUCTURAL = "STRUCTURAL"


class ProjectionKind(StrEnum):
    PLAN = "PLAN"
    ELEVATION = "ELEVATION"
    SECTION = "SECTION"
    DETAIL = "DETAIL"
    SCHEDULE = "SCHEDULE"
    NOTES = "NOTES"


class PrimitiveKind(StrEnum):
    LINE = "LINE"
    POLYLINE = "POLYLINE"
    CIRCLE = "CIRCLE"
    TEXT = "TEXT"


class SourceElementKind(StrEnum):
    """What kind of PEM element a drawing primitive was derived from."""

    PROJECT = "PROJECT"
    SITE = "SITE"
    LEVEL = "LEVEL"
    GRID = "GRID"
    #: A ``PointDefinition`` — an analysis node, e.g. a beam-to-column joint or a
    #: node assigned to a diaphragm.
    NODE = "NODE"
    MATERIAL = "MATERIAL"
    SPACE = "SPACE"
    APARTMENT = "APARTMENT"
    WALL = "WALL"
    DOOR = "DOOR"
    WINDOW = "WINDOW"
    OPENING = "OPENING"
    PARKING = "PARKING"
    STAIR = "STAIR"
    CORE = "CORE"
    COLUMN = "COLUMN"
    BEAM = "BEAM"
    SLAB = "SLAB"
    #: A ``FoundationFooting``. Named for the element the PEM actually holds — a
    #: pad footing — rather than the looser "foundation", which would also imply
    #: rafts and piles the PEM does not model.
    FOOTING = "FOOTING"
    DIAPHRAGM = "DIAPHRAGM"
    SUPPORT = "SUPPORT"
    SECTION_PROFILE = "SECTION_PROFILE"
    REINFORCEMENT = "REINFORCEMENT"
    DESIGN_CHECK = "DESIGN_CHECK"
    # Pure draughting furniture with no single PEM parent.
    ANNOTATION = "ANNOTATION"


#: Element kinds that represent real building fabric rather than draughting
#: furniture. Used for the "is this sheet actually about its subject?" checks.
BUILDING_FABRIC_KINDS = frozenset(
    {
        SourceElementKind.SITE,
        SourceElementKind.SPACE,
        SourceElementKind.WALL,
        SourceElementKind.DOOR,
        SourceElementKind.WINDOW,
        SourceElementKind.OPENING,
        SourceElementKind.PARKING,
        SourceElementKind.STAIR,
        SourceElementKind.COLUMN,
        SourceElementKind.BEAM,
        SourceElementKind.SLAB,
        SourceElementKind.FOOTING,
        SourceElementKind.DIAPHRAGM,
    }
)


class DrawingPrimitive(BaseModel):
    """One drawn entity, traceable back to the PEM element it came from."""

    id: str
    kind: PrimitiveKind
    layer: str
    points: list[Point2D] = Field(default_factory=list)
    closed: bool = False
    text: str | None = None
    text_height_m: float = 0.25
    rotation_deg: float = 0.0
    #: ``CENTER`` or ``LEFT``. Labels sit centred on their anchor; note lines and
    #: level tags read away from theirs.
    text_anchor: str = "CENTER"
    radius_m: float | None = None
    source_element_ids: list[str] = Field(default_factory=list)
    source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION
    #: Which projection produced this geometry, e.g. ``PLAN:L1``,
    #: ``ELEVATION:NORTH``, ``SECTION:A-A``. Part of the traceability record.
    projection: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_traceable(self) -> bool:
        return bool(self.source_element_ids)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        if not self.points:
            return (0.0, 0.0, 0.0, 0.0)
        xs = [point.x for point in self.points]
        ys = [point.y for point in self.points]
        if self.radius_m:
            return (
                min(xs) - self.radius_m,
                min(ys) - self.radius_m,
                max(xs) + self.radius_m,
                max(ys) + self.radius_m,
            )
        return (min(xs), min(ys), max(xs), max(ys))

    def signature_parts(self, *, include_text: bool) -> tuple[str, ...]:
        coords = ";".join(f"{point.x:.4f},{point.y:.4f}" for point in self.points)
        parts = [
            self.kind.value,
            self.layer,
            self.projection,
            self.source_element_kind.value,
            ",".join(sorted(self.source_element_ids)),
            coords,
            f"{self.radius_m:.4f}" if self.radius_m is not None else "",
        ]
        if include_text:
            parts.append(self.text or "")
        return tuple(parts)


class DimensionOrientation(StrEnum):
    HORIZONTAL = "HORIZONTAL"
    VERTICAL = "VERTICAL"
    ALIGNED = "ALIGNED"


class DrawingDimension(BaseModel):
    """
    The *semantics* of a dimension. The matching dimension line, extension lines
    and text live in :attr:`DrawingView.annotations` so renderers only ever walk
    one geometry list.
    """

    id: str
    start: Point2D
    end: Point2D
    offset_m: float = 0.0
    orientation: DimensionOrientation = DimensionOrientation.ALIGNED
    value_m: float = 0.0
    text: str = ""
    layer: str = "DIMENSIONS"
    source_element_ids: list[str] = Field(default_factory=list)
    source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionClip(BaseModel):
    """The clipping band a section view was cut with — part of the audit trail."""

    axis: str
    position_m: float
    band_width_m: float
    view_direction: str

    @property
    def low(self) -> float:
        return self.position_m - self.band_width_m / 2.0

    @property
    def high(self) -> float:
        return self.position_m + self.band_width_m / 2.0


class ViewPlacement(BaseModel):
    """Where a view sits on the sheet, in PDF points from the bottom-left."""

    x_pt: float
    y_pt: float
    width_pt: float
    height_pt: float


class ElementRef(BaseModel):
    """A PEM element referenced by at least one primitive on a sheet."""

    element_id: str
    element_kind: SourceElementKind
    primitive_count: int = 0
    #: IDs of the primitives this element produced, so the question "which PEM
    #: element generated this geometry?" can be answered in either direction
    #: without rescanning the sheet.
    primitive_ids: list[str] = Field(default_factory=list)


class DrawingView(BaseModel):
    """One projection of the PEM placed on a sheet."""

    id: str
    name: str
    projection: ProjectionKind
    #: Human/machine readable projection tag, e.g. ``SECTION:A-A``.
    projection_label: str = ""
    scale_denominator: int = 100
    primitives: list[DrawingPrimitive] = Field(default_factory=list)
    annotations: list[DrawingPrimitive] = Field(default_factory=list)
    dimensions: list[DrawingDimension] = Field(default_factory=list)
    placement: ViewPlacement | None = None
    source_level_ids: list[str] = Field(default_factory=list)
    clip: SectionClip | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def all_primitives(self) -> list[DrawingPrimitive]:
        return [*self.primitives, *self.annotations]

    @property
    def geometry_primitives(self) -> list[DrawingPrimitive]:
        return [item for item in self.primitives if item.kind is not PrimitiveKind.TEXT]

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        boxes = [item.bounds for item in self.all_primitives() if item.points]
        if not boxes:
            return (0.0, 0.0, 1.0, 1.0)
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    def element_refs(self) -> list[ElementRef]:
        return _collect_refs(self.all_primitives())


class ScheduleRow(BaseModel):
    cells: list[str] = Field(default_factory=list)
    source_element_ids: list[str] = Field(default_factory=list)
    source_element_kind: SourceElementKind = SourceElementKind.ANNOTATION
    metadata: dict[str, Any] = Field(default_factory=dict)


class DrawingSchedule(BaseModel):
    """A tabular sheet body (beam/column/slab schedules)."""

    id: str
    title: str
    columns: list[str] = Field(default_factory=list)
    rows: list[ScheduleRow] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    def element_refs(self) -> list[ElementRef]:
        counts: dict[tuple[str, SourceElementKind], int] = {}
        for row in self.rows:
            for element_id in row.source_element_ids:
                key = (element_id, row.source_element_kind)
                counts[key] = counts.get(key, 0) + 1
        return [
            ElementRef(element_id=element_id, element_kind=kind, primitive_count=count)
            for (element_id, kind), count in sorted(counts.items(), key=lambda item: item[0][0])
        ]


class TitleBlock(BaseModel):
    """Consistent title block carried by every sheet."""

    project_name: str
    drawing_number: str
    drawing_title: str
    discipline: Discipline
    revision: str
    scale: str
    units: str
    generated_at: datetime
    source_model_id: str
    source_snapshot_id: str | None = None
    sheet_size: str = "A3"
    status_note: str = "PRELIMINARY — NOT FOR CONSTRUCTION"
    extra: dict[str, str] = Field(default_factory=dict)


class SheetAvailability(StrEnum):
    AVAILABLE = "AVAILABLE"
    PARTIAL = "PARTIAL"
    NOT_AVAILABLE = NOT_AVAILABLE


class DrawingSheet(BaseModel):
    """One drawing sheet generated from the PEM."""

    sheet_number: str
    title: str
    discipline: Discipline
    scale: str = "1:100"
    revision: str = "0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    source_model_id: str
    source_snapshot_id: str | None = None
    views: list[DrawingView] = Field(default_factory=list)
    schedule: DrawingSchedule | None = None
    notes: list[str] = Field(default_factory=list)
    title_block: TitleBlock
    availability: SheetAvailability = SheetAvailability.AVAILABLE
    missing_data: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # -- aggregates (plain properties: never duplicated into the JSON payload) --

    @property
    def primitives(self) -> list[DrawingPrimitive]:
        return [item for view in self.views for item in view.primitives]

    @property
    def annotations(self) -> list[DrawingPrimitive]:
        return [item for view in self.views for item in view.annotations]

    @property
    def dimensions(self) -> list[DrawingDimension]:
        return [item for view in self.views for item in view.dimensions]

    def all_primitives(self) -> list[DrawingPrimitive]:
        return [item for view in self.views for item in view.all_primitives()]

    @property
    def geometry_primitives(self) -> list[DrawingPrimitive]:
        """
        Projected model geometry only.

        Annotations — grid lines, bubbles, dimension lines, note borders — are
        excluded. They are draughting furniture that looks the same on every
        sheet, so counting them would both flatter the traceability figure and
        blunt :attr:`geometry_signature` as a test that two sheets really differ.
        """
        return [item for item in self.primitives if item.kind is not PrimitiveKind.TEXT]

    @property
    def annotation_primitives(self) -> list[DrawingPrimitive]:
        return self.annotations

    @property
    def geometry_bounds(self) -> tuple[float, float, float, float]:
        """Model extent of the projected geometry, in metres."""
        boxes = [item.bounds for item in self.geometry_primitives if item.points]
        if not boxes:
            return (0.0, 0.0, 0.0, 0.0)
        return (
            min(box[0] for box in boxes),
            min(box[1] for box in boxes),
            max(box[2] for box in boxes),
            max(box[3] for box in boxes),
        )

    # -- traceability ------------------------------------------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def element_refs(self) -> list[ElementRef]:
        refs = _collect_refs(self.all_primitives())
        if self.schedule is not None:
            merged = {(ref.element_id, ref.element_kind): ref for ref in refs}
            for ref in self.schedule.element_refs():
                key = (ref.element_id, ref.element_kind)
                if key in merged:
                    merged[key].primitive_count += ref.primitive_count
                    merged[key].primitive_ids.extend(ref.primitive_ids)
                else:
                    merged[key] = ref
            refs = sorted(merged.values(), key=lambda item: item.element_id)
        return refs

    @computed_field  # type: ignore[prop-decorator]
    @property
    def primitive_count(self) -> int:
        return len(self.all_primitives())

    @computed_field  # type: ignore[prop-decorator]
    @property
    def traceable_primitive_count(self) -> int:
        return sum(1 for item in self.all_primitives() if item.is_traceable)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def traceability_coverage(self) -> float:
        """
        Fraction of *geometric* primitives that name a source PEM element.

        A sheet with no projected geometry at all — a general-notes sheet, say —
        has nothing that could be left untraced and reports full coverage. Read it
        alongside :attr:`geometry_primitive_count` for the denominator.
        """
        geometry = self.geometry_primitives
        if not geometry:
            return 1.0
        traced = sum(1 for item in geometry if item.is_traceable)
        return round(traced / len(geometry), 6)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def geometry_primitive_count(self) -> int:
        return len(self.geometry_primitives)

    def element_ids_of_kind(self, kind: SourceElementKind) -> list[str]:
        return sorted({ref.element_id for ref in self.element_refs if ref.element_kind is kind})

    def element_kinds(self) -> set[SourceElementKind]:
        return {ref.element_kind for ref in self.element_refs}

    # -- distinctness ------------------------------------------------------

    @computed_field  # type: ignore[prop-decorator]
    @property
    def content_signature(self) -> str:
        """
        Hash of everything drawn on the sheet, excluding the title block and the
        ``generated_at`` stamp, so two sheets can only share a signature when
        they genuinely show the same thing.
        """
        return _hash_primitives(self.all_primitives(), include_text=True, schedule=self.schedule)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def geometry_signature(self) -> str:
        """
        Hash of non-text geometry only. This is the strict check: re-titling the
        same grid plot cannot change it.
        """
        return _hash_primitives(self.geometry_primitives, include_text=False, schedule=None)


class DrawingSet(BaseModel):
    """The full PEM-derived sheet set for one PEM snapshot."""

    id: str
    project_id: UUID
    project_name: str
    source_model_id: str
    source_snapshot_id: str | None = None
    pem_version: int | None = None
    revision: str = "0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    units: str = "m"
    sheets: list[DrawingSheet] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sheet_numbers(self) -> list[str]:
        return [sheet.sheet_number for sheet in self.sheets]

    def sheet(self, sheet_number: str) -> DrawingSheet | None:
        for sheet in self.sheets:
            if sheet.sheet_number == sheet_number:
                return sheet
        return None

    def require_sheet(self, sheet_number: str) -> DrawingSheet:
        sheet = self.sheet(sheet_number)
        if sheet is None:
            raise KeyError(f"Drawing set has no sheet {sheet_number}")
        return sheet


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _collect_refs(primitives: list[DrawingPrimitive]) -> list[ElementRef]:
    produced: dict[tuple[str, SourceElementKind], list[str]] = {}
    for item in primitives:
        for element_id in item.source_element_ids:
            produced.setdefault((element_id, item.source_element_kind), []).append(item.id)
    return [
        ElementRef(
            element_id=element_id,
            element_kind=kind,
            primitive_count=len(primitive_ids),
            primitive_ids=primitive_ids,
        )
        for (element_id, kind), primitive_ids in sorted(
            produced.items(), key=lambda item: (item[0][0], item[0][1].value)
        )
    ]


def _hash_primitives(
    primitives: list[DrawingPrimitive],
    *,
    include_text: bool,
    schedule: DrawingSchedule | None,
) -> str:
    rows = sorted("|".join(item.signature_parts(include_text=include_text)) for item in primitives)
    if schedule is not None:
        rows.append("SCHEDULE|" + "|".join(schedule.columns))
        rows.extend(
            "ROW|" + "|".join(row.cells) + "|" + ",".join(sorted(row.source_element_ids))
            for row in schedule.rows
        )
    digest = hashlib.sha256()
    for row in rows:
        digest.update(row.encode("utf-8"))
        digest.update(b"\n")
    return digest.hexdigest()
