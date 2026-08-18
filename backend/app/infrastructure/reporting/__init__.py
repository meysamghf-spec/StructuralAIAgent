"""Default report renderer registry."""

from app.domain.models.reporting import ReportOutputFormat
from app.infrastructure.reporting.report_renderers import (
    StructuredReportRenderer,
    StubDocumentReportRenderer,
)

__all__ = ["build_report_renderers"]


def build_report_renderers() -> dict[ReportOutputFormat, object]:
    return {
        ReportOutputFormat.STRUCTURED: StructuredReportRenderer(),
        ReportOutputFormat.HTML: StubDocumentReportRenderer(
            ReportOutputFormat.HTML,
            "text/html",
        ),
        ReportOutputFormat.PDF: StubDocumentReportRenderer(
            ReportOutputFormat.PDF,
            "application/pdf",
        ),
        ReportOutputFormat.DOCX: StubDocumentReportRenderer(
            ReportOutputFormat.DOCX,
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    }
