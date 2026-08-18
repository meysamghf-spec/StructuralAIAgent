"""Analysis engine domain models."""

from __future__ import annotations

from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisStatus(StrEnum):
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    FAILED = "FAILED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"


class AnalysisRequest(BaseModel):
    project_id: UUID
    analysis_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BaseModel):
    project_id: UUID
    analysis_type: str
    status: AnalysisStatus
    message: str
    model_version_id: UUID | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
