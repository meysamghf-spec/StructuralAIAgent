"""Integration API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.integration import IntegrationOperation, IntegrationRequest, IntegrationResult, IntegrationSoftware


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
