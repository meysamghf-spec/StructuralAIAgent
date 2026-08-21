"""Integration API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.integration import (
    IntegrationExecution,
    IntegrationOperation,
    IntegrationRequest,
    IntegrationResult,
    IntegrationSoftware,
    SoftwareCapabilityReport,
)


class IntegrationRequestBody(BaseModel):
    project_id: UUID
    software: IntegrationSoftware
    operation: IntegrationOperation
    parameters: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> IntegrationRequest:
        return IntegrationRequest(
            project_id=self.project_id,
            software=self.software,
            operation=self.operation,
            parameters=self.parameters,
        )


class IntegrationResultResponse(BaseModel):
    software: IntegrationSoftware
    operation: IntegrationOperation
    status: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, result: IntegrationResult) -> IntegrationResultResponse:
        return cls(
            software=result.software,
            operation=result.operation,
            status=result.status.value,
            message=result.message,
            metadata=result.metadata,
        )


class SoftwareCapabilityResponse(BaseModel):
    software: IntegrationSoftware
    expected_version: str
    availability: str
    detected_version: str | None = None
    install_path: str | None = None
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, report: SoftwareCapabilityReport) -> SoftwareCapabilityResponse:
        payload = report.model_dump(mode="json")
        payload["availability"] = report.availability.value
        return cls.model_validate(payload)


class IntegrationExecutionResponse(BaseModel):
    id: UUID
    project_id: UUID
    software: IntegrationSoftware
    operation: IntegrationOperation
    status: str
    pem_snapshot_id: UUID | None = None
    pem_version: int | None = None
    analysis_run_id: UUID | None = None
    message: str
    outputs: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_domain(cls, execution: IntegrationExecution) -> IntegrationExecutionResponse:
        payload = execution.model_dump(mode="json")
        payload["status"] = execution.status.value
        return cls.model_validate(payload)
