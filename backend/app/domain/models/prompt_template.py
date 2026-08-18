"""Prompt template domain model — versioned per AgentVersion."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class PromptTemplateStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    ARCHIVED = "ARCHIVED"


class PromptTemplate(BaseModel):
    id: UUID
    agent_version_id: UUID
    version: int
    name: str
    template: str
    variables_schema: dict[str, Any] = Field(default_factory=dict)
    status: PromptTemplateStatus = PromptTemplateStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    created_by: str | None = None
