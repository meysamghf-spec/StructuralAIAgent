"""Persistence tests for report repository."""

from app.application.service_factory import build_project_service
from app.domain.models.reporting import (
    ReportOutputFormat,
    ReportStatus,
    ReportType,
    ReportVersionStatus,
)
from app.infrastructure.repositories.postgres_report_repository import PostgresReportRepository


def test_report_repository_create_list_and_version(db_session) -> None:
    project = build_project_service().create_project("Report Repo").project
    repo = PostgresReportRepository()

    report = repo.create_report(
        project.id,
        report_type=ReportType.PROJECT_SUMMARY,
        title="Summary Report",
        created_by="engineer-1",
    )
    assert report.status == ReportStatus.DRAFT
    assert report.current_version == 0

    version = repo.create_version(
        project.id,
        report.id,
        version=1,
        status=ReportVersionStatus.COMPLETED,
        output_format=ReportOutputFormat.STRUCTURED,
        content={"sections": []},
        traceability_metadata={"chain_summary": ["REPORT"]},
        generated_by="engineer-1",
    )
    assert version.version == 1

    updated = repo.update_report_status(
        project.id,
        report.id,
        status=ReportStatus.COMPLETED,
        current_version=1,
    )
    assert updated is not None
    assert updated.current_version == 1

    listed = repo.list_reports(project.id)
    assert len(listed) == 1
    assert repo.get_latest_version(project.id, report.id) is not None


def test_report_repository_project_scoped(db_session) -> None:
    service = build_project_service()
    project_a = service.create_project("Report A").project
    project_b = service.create_project("Report B").project
    repo = PostgresReportRepository()

    report = repo.create_report(
        project_a.id,
        report_type=ReportType.VALIDATION,
        title="Validation Report",
    )

    assert repo.get_report(project_b.id, report.id) is None
    assert repo.list_reports(project_b.id) == []
