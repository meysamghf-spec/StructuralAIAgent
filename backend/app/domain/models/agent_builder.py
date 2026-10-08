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
    DISABLE = "disable"
    ENABLE = "enable"


class AgentProductLifecycle(StrEnum):
    """Product view of a version. Stored rows stay DRAFT, ACTIVE, INACTIVE, or ARCHIVED."""

    DRAFT = "DRAFT"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


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


def resolve_product_lifecycle(
    version_status: str,
    *,
    publication_status: str | None = None,
    approval_status: str | None = None,
) -> AgentProductLifecycle:
    """Map persisted version state onto the product lifecycle.

    ACTIVE remains the stored published status. APPROVED is the approval
    stamp on a version that is not the current published version.
    """

    if version_status == "ARCHIVED":
        return AgentProductLifecycle.ARCHIVED
    if version_status == "ACTIVE":
        return AgentProductLifecycle.PUBLISHED
    if version_status == "INACTIVE":
        if approval_status == "APPROVED":
            return AgentProductLifecycle.APPROVED
        return AgentProductLifecycle.ARCHIVED
    if publication_status == AgentBuilderPublicationStatus.PENDING_APPROVAL.value:
        return AgentProductLifecycle.REVIEW
    if approval_status == "APPROVED":
        return AgentProductLifecycle.APPROVED
    return AgentProductLifecycle.DRAFT


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
