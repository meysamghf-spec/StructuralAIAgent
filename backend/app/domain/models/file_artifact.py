"""Project file / artifact domain model — project-scoped registry."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class FileType(StrEnum):
    TEXT = "TEXT"
    PDF = "PDF"
    DOCX = "DOCX"
    SPREADSHEET = "SPREADSHEET"
    IMAGE = "IMAGE"
    UNKNOWN = "UNKNOWN"


class FileSource(StrEnum):
    USER_UPLOAD = "USER_UPLOAD"
    AGENT_GENERATED = "AGENT_GENERATED"
    IMPORTED = "IMPORTED"


class ParsingStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ExtractionStatus(StrEnum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class ProjectFile(BaseModel):
    """Persisted file registry record (Phase 0 FileRecord subset for M5)."""

    id: UUID
    project_id: UUID
    filename: str
    content_type: str | None = None
    file_type: FileType
    file_version: int
    source: FileSource
    upload_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    parsing_status: ParsingStatus = ParsingStatus.PENDING
    extraction_status: ExtractionStatus = ExtractionStatus.PENDING
    confidence: float | None = None
    storage_path: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
