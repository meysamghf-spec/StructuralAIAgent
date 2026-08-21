from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RevisionChangeType(StrEnum):
    INITIAL = "INITIAL"
    CODE_CONFIGURATION = "CODE_CONFIGURATION"
    UNIT_CONFIGURATION = "UNIT_CONFIGURATION"
    PEM_UPDATE = "PEM_UPDATE"
    GEOMETRY_UPDATE = "GEOMETRY_UPDATE"
    MATERIALS_UPDATE = "MATERIALS_UPDATE"
    SECTIONS_UPDATE = "SECTIONS_UPDATE"
    MEMBERS_UPDATE = "MEMBERS_UPDATE"
    SUPPORTS_UPDATE = "SUPPORTS_UPDATE"
    LOADS_UPDATE = "LOADS_UPDATE"
    LOAD_COMBINATIONS_UPDATE = "LOAD_COMBINATIONS_UPDATE"
    ANALYSIS_MODEL_UPDATE = "ANALYSIS_MODEL_UPDATE"
    DESIGN_PARAMETERS_UPDATE = "DESIGN_PARAMETERS_UPDATE"


class Revision(BaseModel):
    id: UUID
    project_id: UUID
    revision_number: int
    change_type: RevisionChangeType
    summary: str
    before_snapshot_id: UUID | None = None
    after_snapshot_id: UUID
    created_by: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
