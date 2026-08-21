"""Application service tests — PemModelService."""

import pytest

from app.application.exceptions import PemValidationError
from app.application.service_factory import build_pem_model_service, build_project_service
from app.domain.models.pem_structural import GeometryModel, LevelDefinition, LineDefinition
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _create_project(name: str = "Model Service Project"):
    return build_project_service().create_project(name).project


def test_get_current_model_includes_structural_model(db_session) -> None:
    project = _create_project()
    service = build_pem_model_service()
    pem, version, snapshot_id = service.get_current_model(project.id)
    assert version == 1
    assert snapshot_id is not None
    assert pem.structural_model.geometry.levels == []


def test_update_geometry_creates_revision(db_session) -> None:
    project = _create_project()
    service = build_pem_model_service()
    geometry = sample_geometry()
    result = service.update_geometry(
        project.id,
        geometry,
        summary="Added grid and levels",
        created_by="tester",
    )
    assert result.pem_version == 2
    assert result.revision_number == 2
    assert result.validation.overall_status.value == "PASS"

    pem, version, _ = service.get_current_model(project.id)
    assert version == 2
    assert len(pem.structural_model.geometry.levels) == 2


def test_update_geometry_rejects_invalid_model(db_session) -> None:
    project = _create_project()
    service = build_pem_model_service()
    bad_geometry = GeometryModel(
        lines=[
            LineDefinition(
                id="ln-bad",
                start_point_id="missing",
                end_point_id="also-missing",
            )
        ]
    )
    with pytest.raises(PemValidationError) as exc_info:
        service.update_geometry(
            project.id,
            bad_geometry,
            summary="Invalid geometry",
        )
    assert exc_info.value.code == "PEM_VALIDATION_FAILED"


def test_full_structural_update_sequence(db_session) -> None:
    project = _create_project()
    service = build_pem_model_service()

    service.update_geometry(project.id, sample_geometry(), summary="Geometry")
    service.update_materials(project.id, sample_materials(), summary="Materials")
    service.update_sections(project.id, sample_sections(), summary="Sections")
    service.update_members(project.id, sample_members(), summary="Members")
    service.update_supports(project.id, sample_supports(), summary="Supports")
    service.update_load_cases(project.id, sample_load_cases(), summary="Loads")
    service.update_load_combinations(
        project.id, sample_load_combinations(), summary="Combinations"
    )

    summary = service.get_model_summary(project.id)
    assert summary.level_count == 2
    assert summary.material_count == 1
    assert summary.member_count == 1
    assert summary.load_case_count == 1
    assert summary.validation_status == "PASS"


def test_validate_model_returns_report(db_session) -> None:
    project = _create_project()
    service = build_pem_model_service()
    service.update_geometry(
        project.id,
        GeometryModel(levels=[LevelDefinition(id="lvl", name="L1", elevation=0.0)]),
        summary="One level",
    )
    report = service.validate_model(project.id)
    assert report.project_id == project.id
    assert report.overall_status.value == "PASS"
