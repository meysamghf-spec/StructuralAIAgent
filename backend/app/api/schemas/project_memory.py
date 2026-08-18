"""Project Memory API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.project_memory import MemoryType, ProjectMemory, ProjectMemoryContext


class ProjectMemoryCreateRequest(BaseModel):
    memory_type: MemoryType
    content: str
    source_type: str | None = None
    source_id: UUID | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None


class ProjectMemoryResponse(BaseModel):
    id: UUID
    project_id: UUID
    memory_type: MemoryType
    content: str
    source_type: str | None = None
    source_id: UUID | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, memory: ProjectMemory) -> ProjectMemoryResponse:
        return cls.model_validate(memory.model_dump())


class ProjectMemoryListResponse(BaseModel):
    memories: list[ProjectMemoryResponse]


class ProjectMemoryContextResponse(BaseModel):
    project_id: UUID
    memories: list[ProjectMemoryResponse]
    total_count: int
    counts_by_type: dict[str, int] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, context: ProjectMemoryContext) -> ProjectMemoryContextResponse:
        return cls(
            project_id=context.project_id,
            memories=[ProjectMemoryResponse.from_domain(m) for m in context.memories],
            total_count=context.total_count,
            counts_by_type=context.counts_by_type,
        )
