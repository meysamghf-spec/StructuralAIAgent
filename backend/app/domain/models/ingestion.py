"""Ingestion domain types — detection and extraction results."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.domain.models.file_artifact import FileType


class FileTypeDetectionResult(BaseModel):
    file_type: FileType
    content_type: str | None = None
    detected_by: str
    confidence: float | None = None


class ExtractionResult(BaseModel):
    parser_key: str
    success: bool
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    error_message: str | None = None
