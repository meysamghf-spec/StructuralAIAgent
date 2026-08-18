"""Engineering reporting API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.reporting import (
    Report,
    ReportGenerationRequest,
    ReportOutputFormat,
    ReportType,
    ReportVersion,
)


class ReportCreateRequest(BaseModel):
    project_id: UUID
    report_type: ReportType
    title: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None


class ReportGenerateRequest(BaseModel):
    report_type: ReportType
    output_format: ReportOutputFormat = ReportOutputFormat.STRUCTURED
    requested_by: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class ReportResponse(BaseModel):
    id: UUID
    project_id: UUID
    report_type: ReportType
    title: str
    status: str
    current_version: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_domain(cls, report: Report) -> ReportResponse:
        payload = report.model_dump()
        payload["status"] = report.status.value
        return cls.model_validate(payload)


class ReportListResponse(BaseModel):
    reports: list[ReportResponse]


class ReportVersionResponse(BaseModel):
    id: UUID
    report_id: UUID
    project_id: UUID
    version: int
    status: str
    output_format: ReportOutputFormat
    content: dict[str, Any] = Field(default_factory=dict)
    traceability_metadata: dict[str, Any] = Field(default_factory=dict)
    generated_at: datetime
    generated_by: str | None = None
    created_at: datetime

    @classmethod
    def from_domain(cls, version: ReportVersion) -> ReportVersionResponse:
        payload = version.model_dump()
        payload["status"] = version.status.value
        return cls.model_validate(payload)


class ReportTraceabilityResponse(BaseModel):
    report_id: UUID
    report_type: str
    current_version: int
    chain_summary: list[str]
    graph: dict[str, Any] = Field(default_factory=dict)
    latest_version_traceability: dict[str, Any] = Field(default_factory=dict)
