"""Project file API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.file_artifact import (
    ExtractionStatus,
    FileSource,
    FileType,
    ParsingStatus,
    ProjectFile,
)


class ProjectFileResponse(BaseModel):
    id: UUID
    project_id: UUID
    filename: str
    content_type: str | None = None
    file_type: FileType
    file_version: int
    source: FileSource
    upload_time: datetime
    parsing_status: ParsingStatus
    extraction_status: ExtractionStatus
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: ProjectFile) -> ProjectFileResponse:
        payload = record.model_dump()
        payload.pop("storage_path", None)
        return cls.model_validate(payload)


class ProjectFileListResponse(BaseModel):
    project_id: UUID
    files: list[ProjectFileResponse]
