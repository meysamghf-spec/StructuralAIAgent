"""Engineering reporting domain models."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ReportType(StrEnum):
    STRUCTURAL_DESIGN = "STRUCTURAL_DESIGN"
    ANALYSIS = "ANALYSIS"
    VALIDATION = "VALIDATION"
    PROJECT_SUMMARY = "PROJECT_SUMMARY"
    DECISION_HISTORY = "DECISION_HISTORY"


class ReportStatus(StrEnum):
    DRAFT = "DRAFT"
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReportVersionStatus(StrEnum):
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ReportOutputFormat(StrEnum):
    STRUCTURED = "STRUCTURED"
    HTML = "HTML"
    PDF = "PDF"
    DOCX = "DOCX"


class ReportSection(BaseModel):
    key: str
    title: str
    content: dict[str, Any] = Field(default_factory=dict)


class ReportTemplate(BaseModel):
    report_type: ReportType
    title: str
    description: str
    section_keys: list[str] = Field(default_factory=list)


class ReportGenerationRequest(BaseModel):
    project_id: UUID
    report_id: UUID
    report_type: ReportType
    output_format: ReportOutputFormat = ReportOutputFormat.STRUCTURED
    requested_by: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class Report(BaseModel):
    id: UUID
    project_id: UUID
    report_type: ReportType
    title: str
    status: ReportStatus = ReportStatus.DRAFT
    current_version: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReportVersion(BaseModel):
    id: UUID
    report_id: UUID
    project_id: UUID
    version: int
    status: ReportVersionStatus
    output_format: ReportOutputFormat = ReportOutputFormat.STRUCTURED
    content: dict[str, Any] = Field(default_factory=dict)
    traceability_metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    generated_by: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class GeneratedReportData(BaseModel):
    report_type: ReportType
    project_id: UUID
    project_name: str
    generated_at: datetime
    sections: list[ReportSection] = Field(default_factory=list)
    traceability_metadata: dict[str, Any] = Field(default_factory=dict)
