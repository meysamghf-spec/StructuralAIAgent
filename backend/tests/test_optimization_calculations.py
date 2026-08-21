"""Tests for deterministic multi-member optimization calculations."""

from __future__ import annotations

from uuid import UUID

from app.application.optimization_calculations import run_multi_member_optimization
from app.application.service_factory import (
    build_code_engine_service,
    build_engineering_result_service,
    build_optimization_engine_service,
    build_pem_model_service,
    build_project_service,
    build_traceability_service,
)
from app.domain.models.engineering_results import EngineeringResultIngestionRequest
from app.domain.models.optimization import OptimizationMode, OptimizationRequest
from app.infrastructure.repositories.postgres_analysis_repository import PostgresAnalysisRepository
from app.domain.models.analysis import AnalysisStatus, AnalysisRequest
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_multi_beam_geometry,
    sample_multi_beam_members,
    sample_sections,
    sample_mixed_discipline_members,
    sample_steel_load_cases,
    sample_steel_materials,
    sample_steel_members,
    sample_supports,
)


def _engineering_results(member_demands: dict[str, list[float]]) -> dict:
    return {
        "frame_forces": [
            {
                "source_identifier": member_id,
                "values": values,
                "load_case": "lc-dead",
            }
            for member_id, values in member_demands.items()
        ]
    }


def _build_pem(db_session, *, geometry=None, materials=None, sections=None, members=None, load_cases=None):
    project = build_project_service().create_project("Optimization Calc Project").project
    model = build_pem_model_service()
    model.update_geometry(project.id, geometry or sample_geometry(), summary="Geometry")
    model.update_materials(project.id, materials or sample_materials(), summary="Materials")
    model.update_sections(project.id, sections or sample_sections(), summary="Sections")
    model.update_members(project.id, members or sample_members(), summary="Members")
    model.update_supports(project.id, sample_supports(), summary="Supports")
    model.update_load_cases(project.id, load_cases or sample_load_cases(), summary="Loads")
    model.update_load_combinations(project.id, sample_load_combinations(), summary="Combos")
    pem, _, _ = model.get_current_model(project.id)
    return project.id, pem


def test_independent_multi_member_optimization_selects_lightest_sections(db_session) -> None:
    _, pem = _build_pem(
        db_session,
        geometry=sample_multi_beam_geometry(),
        members=sample_multi_beam_members(),
    )
    result = run_multi_member_optimization(
        pem=pem,
        engineering_results=_engineering_results({"mbr-1": [5.0], "mbr-2": [8.0]}),
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={
            "optimization_mode": OptimizationMode.INDEPENDENT.value,
            "member_ids": ["mbr-1", "mbr-2"],
        },
    )
    assert result["status"] == "PASS"
    assert result["optimization_mode"] == OptimizationMode.INDEPENDENT.value
    assert len(result["member_results"]) == 2
    assert result["member_results"][0]["selected_section_id"]
    assert result["member_results"][1]["selected_section_id"]


def test_shared_section_optimization_applies_common_section(db_session) -> None:
    _, pem = _build_pem(
        db_session,
        geometry=sample_multi_beam_geometry(),
        members=sample_multi_beam_members(),
    )
    result = run_multi_member_optimization(
        pem=pem,
        engineering_results=_engineering_results({"mbr-1": [5.0], "mbr-2": [7.0]}),
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={
            "optimization_mode": OptimizationMode.SHARED_SECTION.value,
            "member_ids": ["mbr-1", "mbr-2"],
        },
    )
    assert result["status"] == "PASS"
    assert len(result["shared_section_groups"]) == 1
    shared = result["shared_section_groups"][0]
    assert len(shared["member_ids"]) == 2
    assert shared["selected_section_id"]


def test_shared_section_rejects_incompatible_member_group(db_session) -> None:
    materials = sample_materials()
    materials.steel.extend(sample_steel_materials().steel)
    _, pem = _build_pem(
        db_session,
        geometry=sample_multi_beam_geometry(),
        materials=materials,
        members=sample_mixed_discipline_members(),
    )
    result = run_multi_member_optimization(
        pem=pem,
        engineering_results=_engineering_results({"mbr-1": [5.0], "steel-1": [5.0, 10.0]}),
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={
            "optimization_mode": OptimizationMode.SHARED_SECTION.value,
            "member_ids": ["steel-1", "mbr-1"],
        },
    )
    assert result["status"] == "REQUIRES_ENGINEER_REVIEW"
    assert "same type and material" in result["message"]


def test_steel_members_use_interaction_checks(db_session) -> None:
    materials = sample_steel_materials()
    _, pem = _build_pem(
        db_session,
        geometry=sample_multi_beam_geometry(),
        materials=materials,
        sections=sample_sections(),
        members=sample_steel_members(),
        load_cases=sample_steel_load_cases(),
    )
    result = run_multi_member_optimization(
        pem=pem,
        engineering_results=_engineering_results({"steel-1": [5.0, 12.0], "steel-2": [4.0, 10.0]}),
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={
            "member_ids": ["steel-1", "steel-2"],
        },
    )
    assert result["status"] == "PASS"
    all_checks = [
        check
        for member in result["member_results"]
        for candidate in member.get("candidates", [])
        for check in candidate.get("checks", [])
    ]
    assert any(item.get("check_id") == "STEEL_MEMBER_INTERACTION" for item in all_checks)


def test_no_valid_section_returns_engineer_review(db_session) -> None:
    _, pem = _build_pem(db_session)
    result = run_multi_member_optimization(
        pem=pem,
        engineering_results=_engineering_results({"mbr-1": [500.0]}),
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={"member_ids": ["mbr-1"]},
    )
    assert result["status"] == "REQUIRES_ENGINEER_REVIEW"


def test_optimization_is_deterministic(db_session) -> None:
    _, pem = _build_pem(
        db_session,
        geometry=sample_multi_beam_geometry(),
        members=sample_multi_beam_members(),
    )
    kwargs = dict(
        pem=pem,
        engineering_results=_engineering_results({"mbr-1": [5.0], "mbr-2": [8.0]}),
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={"member_ids": ["mbr-1", "mbr-2"]},
    )
    first = run_multi_member_optimization(**kwargs)
    second = run_multi_member_optimization(**kwargs)
    assert first["member_results"] == second["member_results"]


def _ingest_validated_results(project_id, analysis_run_id) -> None:
    model = build_pem_model_service()
    _, version, snapshot_id = model.get_current_model(project_id)
    build_engineering_result_service().ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results={
                "member_forces": [
                    {"id": "mbr-1", "values": [5.0, 0.0], "load_case": "lc-dead"},
                    {"id": "mbr-2", "values": [7.0, 0.0], "load_case": "lc-dead"},
                ],
                "joint_displacements": [
                    {"joint_name": "pt-1", "values": [0.001], "load_case": "lc-dead"}
                ],
            },
            provenance={"source_software": "ETABS", "execution_mode": "vendor"},
        )
    )


def test_optimization_engine_multi_member_with_validated_results(db_session) -> None:
    project_id, _ = _build_pem(
        db_session,
        geometry=sample_multi_beam_geometry(),
        members=sample_multi_beam_members(),
    )
    from app.application.service_factory import build_analysis_engine_service

    analysis_result = build_analysis_engine_service().run_analysis(
        AnalysisRequest(project_id=project_id, analysis_type="LINEAR_STATIC")
    )
    PostgresAnalysisRepository().update_run(
        project_id,
        analysis_result.id,
        status=AnalysisStatus.SUCCESS,
        capability_status="SUCCESS",
        message="Completed",
        outputs={"engineering_results_available": False},
    )
    _ingest_validated_results(project_id, analysis_result.id)

    optimization = build_optimization_engine_service().run_optimization(
        OptimizationRequest(
            project_id=project_id,
            optimization_type="WEIGHT",
            objective="Minimize structural weight",
            parameters={
                "member_ids": ["mbr-1", "mbr-2"],
                "optimization_mode": OptimizationMode.INDEPENDENT.value,
            },
        ),
        created_by="tester",
    )
    assert optimization.status.value == "PASS"
    assert optimization.outputs.get("member_results")
    links = build_traceability_service().get_links_by_target(
        project_id,
        target_type="optimization_result",
        target_id=optimization.id,
    )
    assert links


def test_backward_compatible_single_member_request(db_session) -> None:
    project_id, pem = _build_pem(db_session)
    result = run_multi_member_optimization(
        pem=pem,
        engineering_results=_engineering_results({"mbr-1": [5.0]}),
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={},
    )
    assert result["member_id"] == "mbr-1"
    assert result.get("selected_candidate")
