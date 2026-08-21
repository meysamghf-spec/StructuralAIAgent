"""CSI vendor result extraction capability and summary models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class CsiExtractionStatus(StrEnum):
    COMPLETE = "COMPLETE"
    PARTIAL = "PARTIAL"
    NOT_SUPPORTED = "NOT_SUPPORTED"
    NOT_CONNECTED = "NOT_CONNECTED"
    NOT_ANALYZED = "NOT_ANALYZED"
    FAILED = "FAILED"


class CsiResultCategory(StrEnum):
    FRAME_FORCES = "frame_forces"
    JOINT_DISPLACEMENTS = "joint_displacements"
    JOINT_REACTIONS = "joint_reactions"
    LOAD_CASES = "load_cases"
    LOAD_COMBINATIONS = "load_combinations"
    SHELL_RESULTS = "shell_results"
    MODAL_PERIODS = "modal_periods"
    STORY_DRIFTS = "story_drifts"


class CsiCategoryExtractionReport(BaseModel):
    category: CsiResultCategory
    status: CsiExtractionStatus
    row_count: int = 0
    message: str = ""
    unmapped_entities: list[str] = Field(default_factory=list)


class CsiExtractionSummary(BaseModel):
    overall_status: CsiExtractionStatus
    vendor: str
    vendor_model_identity: str | None = None
    pem_version: int | None = None
    analyzed: bool = False
    categories: list[CsiCategoryExtractionReport] = Field(default_factory=list)
    validation_findings: list[dict[str, Any]] = Field(default_factory=list)
    unmapped_entities: list[str] = Field(default_factory=list)
    source_units: dict[str, str] = Field(default_factory=dict)
    target_units: dict[str, str] = Field(default_factory=dict)
    extracted_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
