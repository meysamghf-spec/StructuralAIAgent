"""API schemas for CAD drawing generation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.cad import CadDrawing, CadDrawingRequest, CadOutputFormat


class CadDrawingRequestBody(BaseModel):
    project_id: UUID
    drawing_type: str
    output_format: CadOutputFormat = CadOutputFormat.DXF
    pem_version: int | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> CadDrawingRequest:
        return CadDrawingRequest.model_validate(self.model_dump())


class CadDrawingResponse(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    drawing_type: str
    output_format: str
    status: str
    validation_status: str
    message: str
    file_path: str | None = None
    layer_summary: dict[str, Any] = Field(default_factory=dict)
    drawing_metadata: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_domain(cls, drawing: CadDrawing) -> CadDrawingResponse:
        payload = drawing.model_dump(mode="json")
        payload["output_format"] = drawing.output_format.value
        payload["status"] = drawing.status.value
        payload["validation_status"] = drawing.validation_status.value
        return cls.model_validate(payload)


class CadDrawingListResponse(BaseModel):
    project_id: UUID
    drawings: list[CadDrawingResponse]


class CadCapabilityResponse(BaseModel):
    software: str
    availability: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
