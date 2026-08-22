"""Report generation service tests."""

from app.application.service_factory import (
    build_project_service,
    build_report_generation_service,
)
from app.domain.models.reporting import ReportGenerationRequest, ReportType


def test_create_and_generate_project_summary_report(db_session) -> None:
    project = build_project_service().create_project("Report Service").project
    service = build_report_generation_service()

    report = service.create_report(
        project.id,
        report_type=ReportType.PROJECT_SUMMARY,
        created_by="engineer-1",
    )

    version = service.generate_version(
        ReportGenerationRequest(
            project_id=project.id,
            report_id=report.id,
            report_type=ReportType.PROJECT_SUMMARY,
            requested_by="engineer-1",
        )
    )

    assert version.version == 1
    assert "sections" in version.content
    assert "traceability_metadata" in version.content
    assert version.traceability_metadata.get("chain_summary") is not None

    loaded = service.get_report(project.id, report.id)
    assert loaded.current_version == 1
    assert loaded.status.value == "COMPLETED"


def test_report_traceability_payload(db_session) -> None:
    project = build_project_service().create_project("Report Trace").project
    service = build_report_generation_service()

    report = service.create_report(
        project.id,
        report_type=ReportType.DECISION_HISTORY,
    )
    service.generate_version(
        ReportGenerationRequest(
            project_id=project.id,
            report_id=report.id,
            report_type=ReportType.DECISION_HISTORY,
        )
    )

    trace = service.get_report_traceability(project.id, report.id)
    assert trace["report_id"] == str(report.id)
    assert "chain_summary" in trace
    assert "graph" in trace


def test_generate_analysis_report_without_nameerror(db_session) -> None:
    project = build_project_service().create_project("Analysis Report").project
    service = build_report_generation_service()

    report = service.create_report(
        project.id,
        report_type=ReportType.ANALYSIS,
    )
    version = service.generate_version(
        ReportGenerationRequest(
            project_id=project.id,
            report_id=report.id,
            report_type=ReportType.ANALYSIS,
        )
    )

    section_keys = [section["key"] for section in version.content["sections"]]
    assert "analysis_results" in section_keys
    assert version.traceability_metadata.get("missing_data")
    analysis_section = next(
        section for section in version.content["sections"] if section["key"] == "analysis_results"
    )
    assert analysis_section["content"]["data_availability"]["status"] == "unavailable"


def test_structural_design_report_includes_cad_and_missing_data(db_session) -> None:
    project = build_project_service().create_project("Design Report").project
    service = build_report_generation_service()

    report = service.create_report(
        project.id,
        report_type=ReportType.STRUCTURAL_DESIGN,
    )
    version = service.generate_version(
        ReportGenerationRequest(
            project_id=project.id,
            report_id=report.id,
            report_type=ReportType.STRUCTURAL_DESIGN,
        )
    )

    section_keys = [section["key"] for section in version.content["sections"]]
    assert "cad_outputs" in section_keys
    assert "assumptions" in section_keys
    assert "missing_data" in version.traceability_metadata
