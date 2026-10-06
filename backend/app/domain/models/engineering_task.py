"""Structured engineering task and workflow domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.models.agent import EngineeringAgentType


class EngineeringTaskStatus(StrEnum):
    DRAFT = "DRAFT"
    READY = "READY"
    WAITING_FOR_INPUT = "WAITING_FOR_INPUT"
    WAITING_FOR_APPROVAL = "WAITING_FOR_APPROVAL"
    RUNNING = "RUNNING"
    PARTIALLY_COMPLETED = "PARTIALLY_COMPLETED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class WorkflowStepStatus(StrEnum):
    PLANNED = "PLANNED"
    EXECUTABLE = "EXECUTABLE"
    EXECUTED = "EXECUTED"
    BLOCKED = "BLOCKED"
    UNSUPPORTED = "UNSUPPORTED"
    FAILED = "FAILED"


class AssumptionSource(StrEnum):
    USER_PROVIDED = "USER_PROVIDED"
    PROJECT_CONFIGURED = "PROJECT_CONFIGURED"
    CODE_DEFINED = "CODE_DEFINED"
    CODE_DEFAULT = "CODE_DEFAULT"
    SYSTEM_DEFAULT = "SYSTEM_DEFAULT"
    ENGINEER_PROPOSED = "ENGINEER_PROPOSED"
    ENGINEER_ASSUMED = "ENGINEER_ASSUMED"
    MISSING = "MISSING"
    UNKNOWN = "UNKNOWN"


class EngineeringAssumption(BaseModel):
    field_name: str
    value: str | None = None
    source: AssumptionSource = AssumptionSource.UNKNOWN
    notes: str | None = None


class EngineeringTaskStep(BaseModel):
    step_id: str = Field(default_factory=lambda: str(uuid4()))
    step_number: int
    title: str
    description: str
    capability: str
    capability_kind: str
    agent_type: EngineeringAgentType | None = None
    dependencies: list[str] = Field(default_factory=list)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    assumptions: list[EngineeringAssumption] = Field(default_factory=list)
    status: WorkflowStepStatus = WorkflowStepStatus.PLANNED
    requires_approval: bool = False
    approval_required: bool = False
    missing_inputs: list[str] = Field(default_factory=list)
    blocking_reason: str | None = None
    execution_result: dict[str, Any] | None = None
    limitations: list[str] = Field(default_factory=list)
    step_artifacts: list[EngineeringTaskArtifact] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class EngineeringTaskArtifact(BaseModel):
    artifact_id: str
    artifact_type: str
    filename: str | None = None
    generation_status: str
    producing_capability: str | None = None
    producing_agent_type: EngineeringAgentType | None = None
    source_step_id: str | None = None
    input_provenance: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    validation_status: str | None = None
    file_id: str | None = None
    report_id: str | None = None
    drawing_id: str | None = None
    href: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class EngineeringTask(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    conversation_id: UUID | None = None
    project_id: UUID
    account_id: str | None = None
    original_request: str
    normalized_objective: str
    requested_deliverables: list[str] = Field(default_factory=list)
    required_disciplines: list[str] = Field(default_factory=list)
    input_file_ids: list[str] = Field(default_factory=list)
    assumptions: list[EngineeringAssumption] = Field(default_factory=list)
    missing_required_inputs: list[str] = Field(default_factory=list)
    steps: list[EngineeringTaskStep] = Field(default_factory=list)
    artifacts: list[EngineeringTaskArtifact] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    shared_context: dict[str, Any] = Field(default_factory=dict)
    status: EngineeringTaskStatus = EngineeringTaskStatus.DRAFT
    primary_agent_type: EngineeringAgentType | None = None
    execution_id: UUID | None = None
    paused_step_id: str | None = None
    resume_from_step_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def touch(self) -> None:
        self.updated_at = datetime.now(UTC)


EngineeringTaskArtifact.model_rebuild()
EngineeringTaskStep.model_rebuild()
EngineeringTask.model_rebuild()
