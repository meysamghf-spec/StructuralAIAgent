"""Structured JSON report renderer — default reproducible output."""

from __future__ import annotations

import json

from app.domain.contracts.report_renderer import RenderedReportOutput
from app.domain.models.reporting import ReportOutputFormat, ReportVersion


class StructuredReportRenderer:
    @property
    def output_format(self) -> ReportOutputFormat:
        return ReportOutputFormat.STRUCTURED

    def render(self, report_version: ReportVersion) -> RenderedReportOutput:
        payload = json.dumps(report_version.content, indent=2, default=str)
        return RenderedReportOutput(
            output_format=self.output_format,
            content_type="application/json",
            payload=payload,
            metadata={"version": report_version.version},
        )


class StubDocumentReportRenderer:
    def __init__(self, output_format: ReportOutputFormat, content_type: str) -> None:
        self._output_format = output_format
        self._content_type = content_type

    @property
    def output_format(self) -> ReportOutputFormat:
        return self._output_format

    def render(self, report_version: ReportVersion) -> RenderedReportOutput:
        return RenderedReportOutput(
            output_format=self._output_format,
            content_type=self._content_type,
            payload="",
            metadata={
                "status": "NOT_IMPLEMENTED",
                "message": f"{self._output_format.value} rendering is not implemented yet",
                "version": report_version.version,
            },
        )
