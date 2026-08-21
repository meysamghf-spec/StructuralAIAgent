"""API schemas for validated engineering results."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.engineering_results import EngineeringResultSet


class EngineeringResultSetResponse(BaseModel):
    id: UUID
    project_id: UUID
    analysis_run_id: UUID | None = None
    integration_execution_id: UUID | None = None
    pem_snapshot_id: UUID
    pem_version: int
    software: str
    software_version: str
    analysis_type: str
    validation_status: str
    engineering_results_available: bool
    result_types: list[str] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime

    @classmethod
    def from_domain(cls, result: EngineeringResultSet) -> EngineeringResultSetResponse:
        payload = result.model_dump(mode="json")
        payload["validation_status"] = result.validation_status.value
        return cls.model_validate(payload)


class EngineeringResultListResponse(BaseModel):
    project_id: UUID
    results: list[EngineeringResultSetResponse]


class EngineeringResultValidationResponse(BaseModel):
    result_set_id: UUID
    validation_status: str
    engineering_results_available: bool
    result_types: list[str]
    validation_summary: dict[str, Any]
