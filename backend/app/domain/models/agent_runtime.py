"""Engineering agent runtime domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


from app.domain.models.agent import EngineeringAgentType


class AgentExecutionStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    CANCELLED = "CANCELLED"
    PENDING = "PENDING"


class AgentValidationStatus(StrEnum):
    NOT_RUN = "NOT_RUN"
    PASS = "PASS"
    WARNING = "WARNING"
    ERROR = "ERROR"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"


class AgentResult(BaseModel):
    structured_output: dict[str, Any] = Field(default_factory=dict)
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    generated_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    validation_information: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionRequest(BaseModel):
    project_id: UUID
    agent_definition_id: UUID | None = None
    agent_type: EngineeringAgentType | None = None
    user_request: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    requested_by: str | None = None
    requires_approval: bool | None = None


class AgentExecutionRecord(BaseModel):
    id: UUID
    project_id: UUID
    agent_definition_id: UUID
    agent_version: int
    execution_status: AgentExecutionStatus = AgentExecutionStatus.CREATED
    input_request: dict[str, Any] = Field(default_factory=dict)
    context_snapshot: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    agent_result: AgentResult | None = None
    validation_status: AgentValidationStatus | None = None
    traceability_metadata: dict[str, Any] = Field(default_factory=dict)
    prompt_generation: dict[str, Any] | None = None
    approval_request_id: UUID | None = None
    error_metadata: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PromptGenerationResult(BaseModel):
    selected_agent_type: EngineeringAgentType
    generated_prompt: str
    context_requirements: list[str] = Field(default_factory=list)
    constraints: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


# Backward-compatible contract alias used by earlier milestones.
class AgentExecution(BaseModel):
    execution_id: UUID
    agent_definition_id: UUID
    agent_version: int
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] | None = None
    status: AgentExecutionStatus = AgentExecutionStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @classmethod
    def from_record(cls, record: AgentExecutionRecord) -> AgentExecution:
        return cls(
            execution_id=record.id,
            agent_definition_id=record.agent_definition_id,
            agent_version=record.agent_version,
            input=record.input_request,
            output=record.output,
            status=record.execution_status,
            started_at=record.started_at,
            completed_at=record.completed_at,
            error_metadata=record.error_metadata,
            created_at=record.created_at,
        )
