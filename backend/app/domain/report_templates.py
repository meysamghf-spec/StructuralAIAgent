"""Report template registry and type extension points."""

from __future__ import annotations

from app.domain.models.reporting import ReportTemplate, ReportType

REPORT_TEMPLATES: dict[ReportType, ReportTemplate] = {
    ReportType.STRUCTURAL_DESIGN: ReportTemplate(
        report_type=ReportType.STRUCTURAL_DESIGN,
        title="Structural Design Report",
        description="Design inputs, code configuration, model context, and traceability.",
        section_keys=[
            "project_information",
            "code_configuration",
            "engineering_model",
            "design_results",
            "optimization_results",
            "traceability_chain",
        ],
    ),
    ReportType.ANALYSIS: ReportTemplate(
        report_type=ReportType.ANALYSIS,
        title="Analysis Report",
        description="Analysis models, load combinations, and analysis outputs.",
        section_keys=[
            "project_information",
            "engineering_model",
            "analysis_results",
            "traceability_chain",
        ],
    ),
    ReportType.VALIDATION: ReportTemplate(
        report_type=ReportType.VALIDATION,
        title="Validation Report",
        description="Validation findings and compliance status.",
        section_keys=[
            "project_information",
            "validation_results",
            "traceability_chain",
        ],
    ),
    ReportType.PROJECT_SUMMARY: ReportTemplate(
        report_type=ReportType.PROJECT_SUMMARY,
        title="Project Summary",
        description="High-level project overview, files, memory, and configuration.",
        section_keys=[
            "project_information",
            "configuration",
            "project_memory",
            "files",
            "traceability_chain",
        ],
    ),
    ReportType.DECISION_HISTORY: ReportTemplate(
        report_type=ReportType.DECISION_HISTORY,
        title="Decision History",
        description="Decisions, approvals, and supporting traceability.",
        section_keys=[
            "project_information",
            "decisions",
            "approvals",
            "traceability_chain",
        ],
    ),
}


def get_report_template(report_type: ReportType) -> ReportTemplate:
    return REPORT_TEMPLATES[report_type]
