"""Tests for deterministic design calculations."""

from __future__ import annotations

from app.application.design_calculations import (
    extract_member_force_demand,
    run_concrete_beam_design,
    run_concrete_column_design,
    run_steel_member_design,
)
from app.application.service_factory import build_code_engine_service, build_pem_model_service, build_project_service
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _build_pem(db_session):
    project = build_project_service().create_project("Design Calc Project").project
    model = build_pem_model_service()
    model.update_geometry(project.id, sample_geometry(), summary="Geometry")
    model.update_materials(project.id, sample_materials(), summary="Materials")
    model.update_sections(project.id, sample_sections(), summary="Sections")
    model.update_members(project.id, sample_members(), summary="Members")
    model.update_supports(project.id, sample_supports(), summary="Supports")
    model.update_load_cases(project.id, sample_load_cases(), summary="Loads")
    model.update_load_combinations(project.id, sample_load_combinations(), summary="Combos")
    pem, _, _ = model.get_current_model(project.id)
    return pem


def test_extract_member_force_demand(db_session) -> None:
    demand = extract_member_force_demand(
        {
            "frame_forces": [
                {"source_identifier": "mbr-1", "values": [10.0, 2.0, -4.0], "load_case": "lc-dead"}
            ]
        },
        "mbr-1",
        component="moment",
    )
    assert demand == 10.0


def test_concrete_beam_design_passes_with_low_demand(db_session) -> None:
    pem = _build_pem(db_session)
    member = pem.structural_model.members.members[0]
    result = run_concrete_beam_design(
        pem=pem,
        member=member,
        engineering_results={
            "frame_forces": [
                {"source_identifier": "mbr-1", "values": [5.0], "load_case": "lc-dead"}
            ]
        },
        code_engine=build_code_engine_service(),
        parameters={},
    )
    assert result["status"] == "PASS"
    assert result["checks"]


def test_concrete_column_design_passes_with_low_demand(db_session) -> None:
    pem = _build_pem(db_session)
    member = pem.structural_model.members.members[0]
    result = run_concrete_column_design(
        pem=pem,
        member=member,
        engineering_results={
            "frame_forces": [
                {"source_identifier": "mbr-1", "values": [5.0, 10.0], "load_case": "lc-dead"}
            ]
        },
        code_engine=build_code_engine_service(),
        parameters={},
    )
    assert result["status"] == "PASS"
    assert any(check["check_id"] == "CONCRETE_COLUMN_COMBINED" for check in result["checks"])


def test_steel_member_design_uses_interaction_when_axial_and_moment_present(db_session) -> None:
    pem = _build_pem(db_session)
    member = pem.structural_model.members.members[0]
    result = run_steel_member_design(
        pem=pem,
        member=member,
        engineering_results={
            "frame_forces": [
                {"source_identifier": "mbr-1", "values": [5.0, 12.0], "load_case": "lc-dead"}
            ]
        },
        code_engine=build_code_engine_service(),
        parameters={},
    )
    assert result["status"] == "PASS"
    assert any(check["check_id"] == "STEEL_MEMBER_INTERACTION" for check in result["checks"])
