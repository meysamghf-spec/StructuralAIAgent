"""Report output renderer contract — future PDF, DOCX, HTML backends."""

from __future__ import annotations

from typing import Any, Protocol

from pydantic import BaseModel, Field

from app.domain.models.reporting import ReportOutputFormat, ReportVersion


class RenderedReportOutput(BaseModel):
    output_format: ReportOutputFormat
    content_type: str
    payload: str | bytes
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReportOutputRenderer(Protocol):
    @property
    def output_format(self) -> ReportOutputFormat: ...

    def render(self, report_version: ReportVersion) -> RenderedReportOutput: ...
