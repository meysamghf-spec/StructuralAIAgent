"""Agent Builder domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentBuilderAction(StrEnum):
    PUBLISH = "publish"
    ROLLBACK = "rollback"
    DEACTIVATE = "deactivate"


class AgentBuilderPublicationStatus(StrEnum):
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class AgentBuilderValidationIssue(BaseModel):
    code: str
    message: str
    severity: str = "ERROR"


class AgentBuilderValidationResult(BaseModel):
    valid: bool
    issues: list[AgentBuilderValidationIssue] = Field(default_factory=list)


class AgentVersionTestRecord(BaseModel):
    id: UUID
    agent_definition_id: UUID
    agent_version: int
    project_id: UUID
    test_input: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    validation_status: str | None = None
    errors: list[str] = Field(default_factory=list)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class AgentBuilderPublicationRecord(BaseModel):
    id: UUID
    agent_definition_id: UUID
    agent_version: int
    project_id: UUID | None = None
    action: AgentBuilderAction
    status: AgentBuilderPublicationStatus
    approval_request_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
