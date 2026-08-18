"""AgentExecution contract — M4 foundation only; no persistence or executor."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AgentExecutionStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class AgentExecution(BaseModel):
    """Contract shape for future orchestration/execution layers."""

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
