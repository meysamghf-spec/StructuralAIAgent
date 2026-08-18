"""Human Approval Gate domain models and extension contract."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol
from uuid import UUID

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


class ApprovalTargetType(StrEnum):
    AGENT_ACTION = "AGENT_ACTION"
    DESIGN_DECISION = "DESIGN_DECISION"
    CONFIGURATION_CHANGE = "CONFIGURATION_CHANGE"
    MODEL_CHANGE = "MODEL_CHANGE"


class ApprovalEventType(StrEnum):
    CREATED = "CREATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    CANCELLED = "CANCELLED"


APPROVAL_MEMORY_SOURCE_TYPE = "approval"


class HumanApprovalRequest(BaseModel):
    """Persisted approval workflow request."""

    id: UUID
    project_id: UUID
    requester: str
    target_type: ApprovalTargetType
    target_action: str
    target_object_type: str | None = None
    target_object_id: UUID | None = None
    summary: str
    status: ApprovalStatus = ApprovalStatus.PENDING
    approver: str | None = None
    decision: ApprovalStatus | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalEvent(BaseModel):
    """Audit event for approval workflow history."""

    id: UUID
    approval_request_id: UUID
    project_id: UUID
    event_type: ApprovalEventType
    actor: str
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalRequest(BaseModel):
    """Lightweight proposal shape for HumanApprovalGate protocol consumers."""

    request_id: UUID
    task_type: str
    summary: str
    context: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class HumanApprovalGate(Protocol):
    """Interface for high-impact operations requiring human review."""

    def requires_approval(self, task_type: str, context: dict[str, Any]) -> bool: ...

    def submit_for_approval(
        self,
        task_type: str,
        summary: str,
        context: dict[str, Any],
    ) -> ApprovalRequest: ...

    def get_status(self, request_id: UUID) -> ApprovalStatus: ...
