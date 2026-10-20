"""Human Approval Gate API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.human_approval import (
    ApprovalEvent,
    ApprovalEventType,
    ApprovalStatus,
    ApprovalTargetType,
    HumanApprovalRequest,
)


class ApprovalCreateRequest(BaseModel):
    project_id: UUID
    requester: str = Field(..., min_length=1)
    target_type: ApprovalTargetType
    target_action: str = Field(..., min_length=1)
    summary: str = Field(..., min_length=1)
    target_object_type: str | None = None
    target_object_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalDecisionRequest(BaseModel):
    approver: str = Field(..., min_length=1)
    decision_note: str | None = None


class ApprovalRejectRequest(BaseModel):
    approver: str = Field(..., min_length=1)
    rejection_reason: str = Field(..., min_length=1)


class ApprovalCancelRequest(BaseModel):
    actor: str = Field(..., min_length=1)
    reason: str | None = None


class HumanApprovalResponse(BaseModel):
    id: UUID
    project_id: UUID
    requester: str
    target_type: ApprovalTargetType
    target_action: str
    target_object_type: str | None = None
    target_object_id: UUID | None = None
    summary: str
    status: ApprovalStatus
    approver: str | None = None
    decision: ApprovalStatus | None = None
    rejection_reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    requested_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    # set on reject of an engineering-run approval: "revised" (next_approval_id = revision N+1) | "clarify"
    revision_outcome: str | None = None
    next_approval_id: UUID | None = None
    revision_message: str | None = None

    @classmethod
    def from_domain(cls, request: HumanApprovalRequest) -> HumanApprovalResponse:
        return cls.model_validate(request.model_dump())


class ApprovalListResponse(BaseModel):
    requests: list[HumanApprovalResponse]


class ApprovalEventResponse(BaseModel):
    id: UUID
    approval_request_id: UUID
    project_id: UUID
    event_type: ApprovalEventType
    actor: str
    reason: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_domain(cls, event: ApprovalEvent) -> ApprovalEventResponse:
        return cls.model_validate(event.model_dump())


class ApprovalHistoryResponse(BaseModel):
    events: list[ApprovalEventResponse]
