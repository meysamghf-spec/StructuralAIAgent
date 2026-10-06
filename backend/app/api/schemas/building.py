"""Building generation API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class GenerateBuildingRequest(BaseModel):
    brief: str = Field(..., min_length=3)
    max_iterations: int = Field(default=5, ge=0, le=12)
    generate_drawings: bool = True


class BuildingGenerateResponse(BaseModel):
    project_id: UUID
    status: str
    pem_version: int | None = None
    snapshot_id: UUID | None = None
    approval_request_id: UUID | None = None
    drawing_ids: list[str] = Field(default_factory=list)
    sheet_paths: list[str] = Field(default_factory=list)
    missing_inputs: list[str] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)
    view: dict[str, Any] = Field(default_factory=dict)


class BuildingViewResponse(BaseModel):
    project_id: UUID
    pem_version: int
    snapshot_id: UUID
    view: dict[str, Any]
    sheet_names: list[str] = Field(default_factory=list)
