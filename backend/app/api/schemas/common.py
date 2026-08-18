"""Shared API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.revision import Revision, RevisionChangeType


class ProjectResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class RevisionResponse(BaseModel):
    id: UUID
    project_id: UUID
    revision_number: int
    change_type: RevisionChangeType
    summary: str
    before_snapshot_id: UUID | None = None
    after_snapshot_id: UUID
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_domain(cls, revision: Revision) -> RevisionResponse:
        return cls.model_validate(revision.model_dump())
