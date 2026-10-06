"""CAD drawing domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CadDrawingType(StrEnum):
    GRID_PLAN = "GRID_PLAN"
    FRAMING_PLAN = "FRAMING_PLAN"
    COLUMN_PLAN = "COLUMN_PLAN"
    BEAM_PLAN = "BEAM_PLAN"
    SLAB_PLAN = "SLAB_PLAN"
    COLUMN_LAYOUT = "COLUMN_LAYOUT"
    BEAM_LAYOUT = "BEAM_LAYOUT"
    FOUNDATION_LAYOUT = "FOUNDATION_LAYOUT"
    ELEVATION = "ELEVATION"
    SECTION = "SECTION"
    SITE_PLAN = "SITE_PLAN"
    PARKING_PLAN = "PARKING_PLAN"
    ARCHITECTURAL_FLOOR_PLAN = "ARCHITECTURAL_FLOOR_PLAN"
    ROOF_PLAN = "ROOF_PLAN"
    COLUMN_SCHEDULE = "COLUMN_SCHEDULE"
    BEAM_SCHEDULE = "BEAM_SCHEDULE"
    SLAB_SCHEDULE = "SLAB_SCHEDULE"


SUPPORTED_CAD_DRAWING_TYPES = frozenset(item.value for item in CadDrawingType)


class CadOutputFormat(StrEnum):
    DXF = "DXF"
    DWG = "DWG"


class CadDrawingStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REQUIRES_LOCAL_SOFTWARE = "REQUIRES_LOCAL_SOFTWARE"


class CadValidationStatus(StrEnum):
    VALIDATED = "VALIDATED"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"


class CadDrawingRequest(BaseModel):
    project_id: UUID
    drawing_type: str
    output_format: CadOutputFormat = CadOutputFormat.DXF
    pem_version: int | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class CadDrawing(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    drawing_type: str
    output_format: CadOutputFormat
    status: CadDrawingStatus
    validation_status: CadValidationStatus
    message: str
    file_path: str | None = None
    layer_summary: dict[str, Any] = Field(default_factory=dict)
    drawing_metadata: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None
