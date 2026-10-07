"""
Sheet assembly: paper layout, title blocks and plotted scales.

Views are built in projected model metres. This module decides where each view
sits on the sheet (:class:`ViewPlacement`, in PDF points) and what scale it is
plotted at. The scale is picked from the standard series and the renderer then
plots at *exactly* that scale, so the number printed in the title block is the
number the sheet was drawn to rather than a best-fit guess.

Views whose content has no meaningful scale — general notes, schedules — carry
``scale_denominator = 0`` (not to scale) and are fitted to their frame instead.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.application.drawing.pem_solids import PemDrawingContext
from app.domain.models.drawing import (
    Discipline,
    DrawingSchedule,
    DrawingSheet,
    DrawingView,
    ProjectionKind,
    SheetAvailability,
    TitleBlock,
    ViewPlacement,
)

PAGE_WIDTH_PT = 1190.0
PAGE_HEIGHT_PT = 842.0
MARGIN_PT = 24.0
TITLE_BLOCK_WIDTH_PT = 446.0
TITLE_BLOCK_HEIGHT_PT = 118.0
VIEW_GUTTER_PT = 18.0

#: Scale denominators a sheet may be plotted at, smallest (most detailed) first.
STANDARD_SCALES: tuple[int, ...] = (5, 10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000)
NOT_TO_SCALE = 0

MM_PER_PT = 25.4 / 72.0

DISCLAIMER_FALLBACK = (
    "Preliminary automated engineering model — requires review and approval by a "
    "qualified engineer."
)


def drawing_window() -> tuple[float, float, float, float]:
    """``(x0, y0, x1, y1)`` of the area available for views, in PDF points."""
    return (
        MARGIN_PT + 8.0,
        MARGIN_PT + TITLE_BLOCK_HEIGHT_PT + 10.0,
        PAGE_WIDTH_PT - MARGIN_PT - 8.0,
        PAGE_HEIGHT_PT - MARGIN_PT - 8.0,
    )


def layout_views(views: list[DrawingView], *, columns: int | None = None) -> None:
    """
    Place views in a left-to-right, top-to-bottom grid inside the window.

    With ``columns`` unset the column count is chosen to maximise the plotted
    scale, which matters for the per-level structural sheets: a tall, narrow
    floor plate plots much larger in a row of narrow cells than in a square grid.
    """
    if not views:
        return
    x0, y0, x1, y1 = drawing_window()
    count = len(views)
    cols = columns or _auto_columns(views, window=(x1 - x0, y1 - y0))
    rows = max(1, math.ceil(count / cols))
    cell_w = (x1 - x0 - VIEW_GUTTER_PT * (cols - 1)) / cols
    cell_h = (y1 - y0 - VIEW_GUTTER_PT * (rows - 1)) / rows
    for index, view in enumerate(views):
        row = index // cols
        col = index % cols
        view.placement = ViewPlacement(
            x_pt=x0 + col * (cell_w + VIEW_GUTTER_PT),
            # Fill from the top of the window downwards.
            y_pt=y1 - (row + 1) * cell_h - row * VIEW_GUTTER_PT,
            width_pt=cell_w,
            height_pt=cell_h,
        )


def _auto_columns(views: list[DrawingView], *, window: tuple[float, float]) -> int:
    """Column count that gives the largest plotted scale for the tightest view."""
    count = len(views)
    if count <= 1:
        return 1
    window_w, window_h = window
    spans = []
    for view in views:
        min_x, min_y, max_x, max_y = view.bounds
        spans.append((max(max_x - min_x, 1e-6), max(max_y - min_y, 1e-6)))

    best_cols = 1
    best_fit = -1.0
    for cols in range(1, count + 1):
        rows = math.ceil(count / cols)
        cell_w = (window_w - VIEW_GUTTER_PT * (cols - 1)) / cols
        cell_h = (window_h - VIEW_GUTTER_PT * (rows - 1)) / rows
        if cell_w <= 0.0 or cell_h <= 0.0:
            continue
        fit = min(min(cell_w / span_x, cell_h / span_y) for span_x, span_y in spans)
        if fit > best_fit:
            best_fit = fit
            best_cols = cols
    return best_cols


def assign_scales(views: list[DrawingView], *, padding_ratio: float = 0.06) -> None:
    """Pick a standard plotted scale for every view that has one."""
    for view in views:
        if view.projection in (ProjectionKind.NOTES, ProjectionKind.SCHEDULE):
            view.scale_denominator = NOT_TO_SCALE
            continue
        if view.placement is None:
            continue
        min_x, min_y, max_x, max_y = view.bounds
        span_x = max(max_x - min_x, 1e-6) * (1.0 + padding_ratio)
        span_y = max(max_y - min_y, 1e-6) * (1.0 + padding_ratio)
        view.scale_denominator = _choose_scale(
            span_x, span_y, view.placement.width_pt, view.placement.height_pt
        )
        view.metadata["plotted_scale"] = f"1:{view.scale_denominator}"
        view.metadata["model_span_m"] = [round(span_x, 4), round(span_y, 4)]


def _choose_scale(span_x_m: float, span_y_m: float, width_pt: float, height_pt: float) -> int:
    for denominator in STANDARD_SCALES:
        width_needed = span_x_m * 1000.0 / denominator / MM_PER_PT
        height_needed = span_y_m * 1000.0 / denominator / MM_PER_PT
        if width_needed <= width_pt and height_needed <= height_pt:
            return denominator
    return STANDARD_SCALES[-1]


def sheet_scale_label(views: list[DrawingView]) -> str:
    denominators = {view.scale_denominator for view in views if view.scale_denominator}
    if not denominators:
        return "NTS"
    if len(denominators) == 1:
        return f"1:{denominators.pop()}"
    return "AS NOTED"


@dataclass
class SheetBuildContext:
    """Everything a sheet builder needs that is not geometry."""

    pem: PemDrawingContext
    project_name: str
    source_model_id: str
    generated_at: datetime
    source_snapshot_id: str | None = None
    pem_version: int | None = None
    revision: str = "0"
    units: str = "m"
    drawing_index: list[tuple[str, str]] = field(default_factory=list)

    @property
    def disclaimer(self) -> str:
        value = self.pem.pem.engineering_report.get("disclaimer")
        return str(value) if value else DISCLAIMER_FALLBACK

    @property
    def limitations(self) -> list[str]:
        value = self.pem.pem.engineering_report.get("19_limitations")
        return [str(item) for item in value] if isinstance(value, list) else []

    def standard_notes(self) -> list[str]:
        """Disclaimers that must appear on every sheet, taken from the PEM."""
        notes = [
            self.disclaimer,
            "PRELIMINARY — NOT FOR CONSTRUCTION. Not a construction-document set.",
            f"Dimensions in {self.units} derived from PEM geometry. Confirm on site.",
        ]
        if self.pem_version is not None:
            notes.append(f"Source PEM version {self.pem_version}.")
        return notes

    def title_block(
        self,
        *,
        sheet_number: str,
        title: str,
        discipline: Discipline,
        scale: str,
        extra: dict[str, str] | None = None,
    ) -> TitleBlock:
        return TitleBlock(
            project_name=self.project_name,
            drawing_number=sheet_number,
            drawing_title=title,
            discipline=discipline,
            revision=self.revision,
            scale=scale,
            units=self.units,
            generated_at=self.generated_at,
            source_model_id=self.source_model_id,
            source_snapshot_id=self.source_snapshot_id,
            extra={
                "pem_version": str(self.pem_version) if self.pem_version is not None else "N/A",
                "lifecycle_status": self.pem.pem.lifecycle_status,
                **(extra or {}),
            },
        )

    def build_sheet(
        self,
        *,
        sheet_number: str,
        title: str,
        discipline: Discipline,
        views: list[DrawingView],
        columns: int | None = None,
        schedule: DrawingSchedule | None = None,
        notes: list[str] | None = None,
        availability: SheetAvailability = SheetAvailability.AVAILABLE,
        missing_data: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DrawingSheet:
        layout_views(views, columns=columns)
        assign_scales(views)
        scale = sheet_scale_label(views)
        sheet_notes = [*(notes or []), *self.standard_notes()]
        return DrawingSheet(
            sheet_number=sheet_number,
            title=title,
            discipline=discipline,
            scale=scale,
            revision=self.revision,
            generated_at=self.generated_at,
            source_model_id=self.source_model_id,
            source_snapshot_id=self.source_snapshot_id,
            views=views,
            schedule=schedule,
            notes=sheet_notes,
            title_block=self.title_block(
                sheet_number=sheet_number,
                title=title,
                discipline=discipline,
                scale=scale,
            ),
            availability=availability,
            missing_data=list(missing_data or []),
            metadata={
                "view_count": len(views),
                "view_projections": [view.projection_label or view.projection.value for view in views],
                **(metadata or {}),
            },
        )

    def unavailable_sheet(
        self,
        *,
        sheet_number: str,
        title: str,
        discipline: Discipline,
        reason: str,
    ) -> DrawingSheet:
        """A sheet that cannot be drawn is marked NOT_AVAILABLE, never faked."""
        return DrawingSheet(
            sheet_number=sheet_number,
            title=title,
            discipline=discipline,
            scale="NTS",
            revision=self.revision,
            generated_at=self.generated_at,
            source_model_id=self.source_model_id,
            source_snapshot_id=self.source_snapshot_id,
            views=[],
            notes=[f"NOT_AVAILABLE — {reason}", *self.standard_notes()],
            title_block=self.title_block(
                sheet_number=sheet_number,
                title=title,
                discipline=discipline,
                scale="NTS",
            ),
            availability=SheetAvailability.NOT_AVAILABLE,
            missing_data=[reason],
            metadata={"not_available_reason": reason},
        )
