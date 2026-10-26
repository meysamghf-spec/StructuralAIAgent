"""ValidationEngine service tests."""

from uuid import uuid4

from app.application.service_factory import (
    build_project_service,
    build_validation_engine_service,
)


def test_validate_new_project_passes_with_iranian_default_profile(db_session) -> None:
    project = build_project_service().create_project("Validation Target").project
    report = build_validation_engine_service().validate_project(project.id)
    assert report.overall_status.value == "PASS"
    assert not any(finding.code == "CODE_SOFTWARE_DEFAULT" for finding in report.findings)


def test_non_iranian_software_default_still_requires_review() -> None:
    from app.application.code_engine_service import CodeEngineService
    from app.domain.models.pem import create_software_default_code_configuration

    result = CodeEngineService(plugins={}).validate_configuration(create_software_default_code_configuration())
    assert result.warnings


def test_validate_unknown_project_raises(db_session) -> None:
    import pytest

    from app.application.exceptions import ProjectNotFoundError

    with pytest.raises(ProjectNotFoundError):
        build_validation_engine_service().validate_project(uuid4())
