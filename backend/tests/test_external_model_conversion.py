"""Tests for PEM external model conversion."""

from uuid import uuid4

from app.application.external_model_conversion import (
    build_external_model_export,
    parse_external_analysis_results,
    validate_external_model_export,
    validate_imported_results,
)
from app.application.service_factory import build_pem_service, build_project_service
from app.domain.models.integration import IntegrationSoftware
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_materials,
    sample_members,
    sample_sections,
)
from app.application.service_factory import build_pem_model_service


def _sample_pem():
    project = build_project_service().create_project("Export Conversion Project").project
    service = build_pem_model_service()
    service.update_geometry(project.id, sample_geometry(), summary="Geometry")
    service.update_materials(project.id, sample_materials(), summary="Materials")
    service.update_sections(project.id, sample_sections(), summary="Sections")
    service.update_members(project.id, sample_members(), summary="Members")
    service.update_load_cases(project.id, sample_load_cases(), summary="Loads")
    pem = build_pem_service().get_current_pem(project.id)
    assert pem is not None
    return project.id, pem


def test_build_external_model_export_includes_structural_model(db_session) -> None:
    project_id, pem = _sample_pem()
    snapshot_id = uuid4()
    export = build_external_model_export(
        project_id=project_id,
        pem=pem,
        pem_snapshot_id=snapshot_id,
        pem_version=2,
        software=IntegrationSoftware.ETABS,
        software_version="23",
    )
    assert export.project_id == project_id
    assert export.pem_snapshot_id == snapshot_id
    assert export.structural_model["members"]


def test_validate_external_model_export_requires_members(db_session) -> None:
    project = build_project_service().create_project("Empty Export Project").project
    pem = build_pem_service().get_current_pem(project.id)
    assert pem is not None
    export = build_external_model_export(
        project_id=project.id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        software=IntegrationSoftware.SAFE,
        software_version="23",
    )
    valid, issues = validate_external_model_export(export)
    assert valid is False
    assert issues


def test_mock_results_are_not_valid_engineering_outputs() -> None:
    parsed = parse_external_analysis_results(
        software=IntegrationSoftware.ETABS,
        software_version="23",
        project_id=uuid4(),
        pem_snapshot_id=uuid4(),
        pem_version=1,
        raw_results={"execution_mode": "mock", "reactions": []},
    )
    valid, issues = validate_imported_results(parsed)
    assert valid is False
    assert any("Mock" in issue for issue in issues)
