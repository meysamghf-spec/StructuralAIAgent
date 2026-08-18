"""Orchestration domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OrchestrationRoute(StrEnum):
    DETERMINISTIC = "DETERMINISTIC"
    ENGINE = "ENGINE"
    AGENT = "AGENT"
    AI = "AI"
    VALIDATION = "VALIDATION"


class OrchestrationTask(BaseModel):
    task_type: str
    project_id: UUID | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class OrchestrationResult(BaseModel):
    task_type: str
    route: OrchestrationRoute
    status: str
    output: dict[str, Any] = Field(default_factory=dict)
    trace: list[str] = Field(default_factory=list)
