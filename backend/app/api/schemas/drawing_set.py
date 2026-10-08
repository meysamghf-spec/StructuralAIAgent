"""Index of the PEM-derived drawing set. Geometry stays in the PDF."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DrawingSheetIndexItem(BaseModel):
    sheet_number: str
    title: str
    discipline: str
    availability: str
    schedule_family: str | None = None
    missing_data: list[str] = Field(default_factory=list)
    content_signature: str


class PendingDrawingSheet(BaseModel):
    sheet_number: str
    title: str
    availability: str = "NOT_GENERATED"


class DrawingSetIndexResponse(BaseModel):
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    drawing_set_id: str
    generated_at: datetime
    sheets: list[DrawingSheetIndexItem]
    pending_sheets: list[PendingDrawingSheet]
    disclaimers: list[str]
