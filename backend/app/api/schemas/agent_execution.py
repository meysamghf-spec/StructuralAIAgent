"""Agent execution API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
)


class CreateAgentExecutionRequest(BaseModel):
    project_id: UUID
    agent_definition_id: UUID | None = None
    agent_type: EngineeringAgentType | None = None
    user_request: str = Field(..., min_length=1)
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_by: str | None = None
    requires_approval: bool | None = None


class AgentResultResponse(BaseModel):
    structured_output: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = None
    generated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    validation_information: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, result: AgentResult | None) -> AgentResultResponse | None:
        if result is None:
            return None
        return cls.model_validate(result.model_dump())


class AgentExecutionResponse(BaseModel):
    id: UUID
    project_id: UUID
    agent_definition_id: UUID
    agent_version: int
    execution_status: AgentExecutionStatus
    input_request: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    agent_result: AgentResultResponse | None = None
    validation_status: AgentValidationStatus | None = None
    traceability_metadata: dict[str, Any] = Field(default_factory=dict)
    prompt_generation: dict[str, Any] | None = None
    approval_request_id: UUID | None = None
    error_metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: AgentExecutionRecord) -> AgentExecutionResponse:
        payload = record.model_dump()
        payload["agent_result"] = AgentResultResponse.from_domain(record.agent_result)
        return cls.model_validate(payload)


class AgentExecutionListResponse(BaseModel):
    executions: list[AgentExecutionResponse]
