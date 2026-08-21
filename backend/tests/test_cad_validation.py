"""Tests for CAD drawing validation rules."""

from __future__ import annotations

from app.application.cad_validation import validate_cad_drawing
from app.application.service_factory import build_pem_model_service, build_project_service
from tests.fixtures.pem_structural_samples import sample_geometry, sample_materials, sample_members, sample_sections


def _build_pem(db_session):
    project = build_project_service().create_project("CAD Validation Project").project
    model = build_pem_model_service()
    model.update_geometry(project.id, sample_geometry(), summary="Geometry")
    model.update_materials(project.id, sample_materials(), summary="Materials")
    model.update_sections(project.id, sample_sections(), summary="Sections")
    model.update_members(project.id, sample_members(), summary="Members")
    pem, _, version = model.get_current_model(project.id)
    return pem, version


def test_validate_framing_plan_requires_members(db_session) -> None:
    pem, version = _build_pem(db_session)
    status, summary = validate_cad_drawing(
        pem=pem,
        pem_version=version,
        drawing_type="FRAMING_PLAN",
        layer_summary={"MEMBERS": 1, "TEXT": 1},
        drawing_metadata={"pem_version": version, "capability_status": "COMPLETE"},
        entity_count=4,
    )
    assert status.value == "VALIDATED"
    assert summary["capability_status"] == "COMPLETE"


def test_validate_slab_plan_incomplete_without_slabs(db_session) -> None:
    pem, version = _build_pem(db_session)
    status, summary = validate_cad_drawing(
        pem=pem,
        pem_version=version,
        drawing_type="SLAB_PLAN",
        layer_summary={"GRID": 1, "SLABS": 0},
        drawing_metadata={
            "pem_version": version,
            "capability_status": "INCOMPLETE",
            "missing_data": ["Slab boundaries are not defined in the engineering model"],
        },
        entity_count=2,
    )
    assert status.value == "INCOMPLETE"
    assert any("slab boundary" in item.lower() for item in summary["missing_requirements"])
