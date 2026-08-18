from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryType(StrEnum):
    DECISION = "DECISION"
    ASSUMPTION = "ASSUMPTION"
    REJECTION = "REJECTION"
    REQUIREMENT = "REQUIREMENT"
    DESIGN_CHOICE = "DESIGN_CHOICE"
    MODEL_VERSION = "MODEL_VERSION"
    EXTRACTED_INFORMATION = "EXTRACTED_INFORMATION"
    VALIDATION_RESULT = "VALIDATION_RESULT"
    CONVERSATION = "CONVERSATION"
    REVISION = "REVISION"


FILE_MEMORY_SOURCE_TYPE = "file"


class ProjectMemory(BaseModel):
    id: UUID
    project_id: UUID
    memory_type: MemoryType
    content: str
    source_type: str | None = None
    source_id: UUID | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ProjectMemoryContext(BaseModel):
    """Aggregated project-scoped memory for context retrieval."""

    project_id: UUID
    memories: list[ProjectMemory]
    total_count: int
    counts_by_type: dict[str, int] = Field(default_factory=dict)
