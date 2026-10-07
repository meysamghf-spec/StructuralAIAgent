"""
Model-to-paper transforms shared by the PDF and DXF writers.

Both renderers go through :func:`view_transforms` so a sheet plots identically in
either format — same scale, same placement, same text sizes. A view with a
standard scale is plotted at exactly that scale and centred in its frame; a
not-to-scale view (general notes) is fitted to its frame instead.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.application.drawing.sheet_builder import MM_PER_PT
from app.domain.models.drawing import DrawingSheet, DrawingView, ViewPlacement

#: Text smaller than this is unreadable on a plot, larger is out of proportion.
MIN_TEXT_PT = 4.2
MAX_TEXT_PT = 13.0
FIT_MARGIN = 0.94


@dataclass(frozen=True)
class ViewTransform:
    """Maps a view's projected model metres onto the sheet, in PDF points."""

    view_id: str
    scale_pt_per_m: float
    offset_x_pt: float
    offset_y_pt: float
    placement: ViewPlacement
    scale_denominator: int

    def to_pt(self, x: float, y: float) -> tuple[float, float]:
        return (
            self.offset_x_pt + x * self.scale_pt_per_m,
            self.offset_y_pt + y * self.scale_pt_per_m,
        )

    def length_pt(self, value_m: float) -> float:
        return value_m * self.scale_pt_per_m

    def text_pt(self, height_m: float) -> float:
        return max(MIN_TEXT_PT, min(MAX_TEXT_PT, height_m * self.scale_pt_per_m))


def view_transforms(sheet: DrawingSheet) -> dict[str, ViewTransform]:
    return {
        view.id: _transform(view)
        for view in sheet.views
        if view.placement is not None
    }


def _transform(view: DrawingView) -> ViewTransform:
    placement = view.placement
    assert placement is not None
    min_x, min_y, max_x, max_y = view.bounds
    span_x = max(max_x - min_x, 1e-6)
    span_y = max(max_y - min_y, 1e-6)

    if view.scale_denominator > 0:
        scale = 1000.0 / view.scale_denominator / MM_PER_PT
    else:
        scale = min(placement.width_pt / span_x, placement.height_pt / span_y) * FIT_MARGIN

    # Centre the content in its frame.
    content_w = span_x * scale
    content_h = span_y * scale
    offset_x = placement.x_pt + (placement.width_pt - content_w) / 2.0 - min_x * scale
    offset_y = placement.y_pt + (placement.height_pt - content_h) / 2.0 - min_y * scale
    return ViewTransform(
        view_id=view.id,
        scale_pt_per_m=scale,
        offset_x_pt=offset_x,
        offset_y_pt=offset_y,
        placement=placement,
        scale_denominator=view.scale_denominator,
    )


def estimate_text_width_pt(text: str, size_pt: float) -> float:
    """Rough Helvetica advance width, good enough to centre a label."""
    return len(text) * size_pt * 0.5
