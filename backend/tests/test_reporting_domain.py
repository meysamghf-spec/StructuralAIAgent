"""Domain tests for engineering reporting."""

from app.domain.models.reporting import ReportOutputFormat, ReportType
from app.domain.report_templates import REPORT_TEMPLATES, get_report_template


def test_report_types_include_extension_points() -> None:
    assert ReportType.STRUCTURAL_DESIGN.value == "STRUCTURAL_DESIGN"
    assert ReportType.DECISION_HISTORY.value == "DECISION_HISTORY"
    assert len(REPORT_TEMPLATES) == 5


def test_report_template_for_project_summary() -> None:
    template = get_report_template(ReportType.PROJECT_SUMMARY)
    assert "project_information" in template.section_keys
    assert "traceability_chain" in template.section_keys


def test_output_formats_include_future_renderers() -> None:
    formats = {item.value for item in ReportOutputFormat}
    assert {"STRUCTURED", "HTML", "PDF", "DOCX"} <= formats
