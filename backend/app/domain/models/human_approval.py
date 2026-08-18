"""HumanApprovalGate contract — M4 foundation only; no workflow persistence."""

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


class ApprovalRequest(BaseModel):
    """Proposal submitted for human review."""

    request_id: UUID
    task_type: str
    summary: str
    context: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None
    resolved_by: str | None = None


class HumanApprovalGate(Protocol):
    """Interface for future approval workflows (MASTER PROMPT §7, AG-37/46)."""

    def requires_approval(self, task_type: str, context: dict[str, Any]) -> bool: ...

    def submit_for_approval(
        self,
        task_type: str,
        summary: str,
        context: dict[str, Any],
    ) -> ApprovalRequest: ...

    def get_status(self, request_id: UUID) -> ApprovalStatus: ...
