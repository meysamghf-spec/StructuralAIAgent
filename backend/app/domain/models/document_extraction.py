"""Normalized document extraction representation for ingestion and chat context."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentExtractionStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class DocumentExtractionResult(BaseModel):
    """Common extraction payload stored under extraction.metadata.document."""

    filename: str
    file_type: str
    status: DocumentExtractionStatus
    extracted_text: str | None = None
    structured_data: dict[str, Any] | None = None
    warnings: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    extractor: str | None = None
    extractor_version: str | None = None
    file_id: UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def is_usable(self) -> bool:
        if self.status not in {DocumentExtractionStatus.SUCCESS, DocumentExtractionStatus.PARTIAL}:
            return False
        if self.extracted_text and self.extracted_text.strip():
            return True
        structured = self.structured_data or {}
        return bool(structured.get("pages") or structured.get("sheets") or structured.get("paragraphs"))
