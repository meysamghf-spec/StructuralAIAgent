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


_SENSITIVE_METADATA_KEYS = {
    "storage_path",
    "path",
    "file_path",
    "absolute_path",
    "password",
    "secret",
    "token",
    "api_key",
    "connection_string",
}


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
    byte_length: int | None = None
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, record: ProjectFile) -> ProjectFileResponse:
        payload = record.model_dump()
        payload.pop("storage_path", None)
        metadata = payload.get("metadata")
        if isinstance(metadata, dict):
            payload["metadata"] = _safe_metadata(metadata)
            payload["byte_length"] = _byte_length(metadata)
        return cls.model_validate(payload)


def _byte_length(metadata: dict[str, Any]) -> int | None:
    ingestion = metadata.get("ingestion")
    if isinstance(ingestion, dict):
        value = ingestion.get("byte_length")
        if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
            return value
    return None


def _safe_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: _safe_metadata(value) if isinstance(value, dict) else value
        for key, value in metadata.items()
        if key.lower() not in _SENSITIVE_METADATA_KEYS and not key.lower().endswith("_path")
    }


class ProjectFileListResponse(BaseModel):
    project_id: UUID
    files: list[ProjectFileResponse]
