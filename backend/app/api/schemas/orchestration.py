"""Orchestration API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.orchestration import OrchestrationResult, OrchestrationTask


class OrchestrationTaskRequest(BaseModel):
    task_type: str
    project_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_domain(self) -> OrchestrationTask:
        return OrchestrationTask(
            task_type=self.task_type,
            project_id=self.project_id,
            payload=self.payload,
        )


class OrchestrationResultResponse(BaseModel):
    task_type: str
    route: str
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    trace: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, result: OrchestrationResult) -> OrchestrationResultResponse:
        return cls(
            task_type=result.task_type,
            route=result.route.value,
            status=result.status,
            output=result.output,
            trace=result.trace,
        )
