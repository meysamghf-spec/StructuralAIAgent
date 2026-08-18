"""PEM API request/response schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.api.schemas.common import RevisionResponse
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.revision import RevisionChangeType


class PemEnvelopeResponse(BaseModel):
    project_id: UUID
    version: int
    snapshot_id: UUID
    is_current: bool
    pem: ProjectEngineeringModel


class PemVersionListResponse(BaseModel):
    project_id: UUID
    versions: list[int]


class UpdatePemRequest(BaseModel):
    pem: ProjectEngineeringModel
    change_type: RevisionChangeType
    summary: str = Field(..., min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class UpdatePemResponse(BaseModel):
    pem_version: int
    snapshot_id: UUID
    before_snapshot_id: UUID
    revision: RevisionResponse
