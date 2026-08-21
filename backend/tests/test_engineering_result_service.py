"""Persistence and service tests for validated engineering results."""

from __future__ import annotations

from uuid import UUID

from app.application.service_factory import (
    build_analysis_engine_service,
    build_design_engine_service,
    build_engineering_result_service,
    build_pem_model_service,
    build_project_service,
)
from app.domain.models.analysis import AnalysisRequest, AnalysisStatus
from app.domain.models.design import DesignRequest
from app.domain.models.engineering_results import EngineeringResultIngestionRequest
from app.infrastructure.repositories.postgres_analysis_repository import PostgresAnalysisRepository
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _populate_project(project_id):
    model = build_pem_model_service()
    model.update_geometry(project_id, sample_geometry(), summary="Geometry")
    model.update_materials(project_id, sample_materials(), summary="Materials")
    model.update_sections(project_id, sample_sections(), summary="Sections")
    model.update_members(project_id, sample_members(), summary="Members")
    model.update_supports(project_id, sample_supports(), summary="Supports")
    model.update_load_cases(project_id, sample_load_cases(), summary="Loads")
    model.update_load_combinations(project_id, sample_load_combinations(), summary="Combos")
    _, version, snapshot_id = model.get_current_model(project_id)
    return version, snapshot_id


def _vendor_raw_results():
    return {
        "member_forces": [
            {
                "id": "mbr-1",
                "values": [10.0, 0.0, -4.0],
                "units": "kip",
                "load_case": "lc-dead",
            }
        ],
        "joint_displacements": [
            {
                "joint_name": "pt-1",
                "values": [0.001, 0.0, 0.0],
                "units": "in",
                "load_case": "lc-dead",
            }
        ],
    }


def test_ingest_and_unlock_design_with_validated_results(db_session) -> None:
    project = build_project_service().create_project("Result Service Project").project
    version, snapshot_id = _populate_project(project.id)

    analysis = build_analysis_engine_service()
    analysis_result = analysis.run_analysis(
        AnalysisRequest(project_id=project.id, analysis_type="LINEAR_STATIC"),
        created_by="tester",
    )
    assert analysis_result.id is not None

    PostgresAnalysisRepository().update_run(
        project.id,
        analysis_result.id,
        status=AnalysisStatus.SUCCESS,
        capability_status=AnalysisStatus.SUCCESS.value,
        message="Test analysis completed",
        outputs={"engineering_results_available": False},
    )

    result_service = build_engineering_result_service()
    result_set = result_service.ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project.id,
            analysis_run_id=analysis_result.id,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results=_vendor_raw_results(),
            provenance={"source_software": "ETABS", "execution_mode": "vendor"},
        ),
        created_by="tester",
    )
    assert result_set.engineering_results_available is True
    assert result_set.validation_status.value == "VALIDATED"

    design = build_design_engine_service()
    readiness = design.get_readiness(project.id)
    assert readiness.usable_analysis_runs >= 1

    design_result = design.run_design(
        DesignRequest(project_id=project.id, design_type="STEEL_BEAM"),
        created_by="tester",
    )
    assert design_result.status.value in {"REQUIRES_SOLVER", "NOT_IMPLEMENTED", "PASS", "WARNING"}


def test_list_and_fetch_result_sets(db_session) -> None:
    project = build_project_service().create_project("Result List Project").project
    version, snapshot_id = _populate_project(project.id)

    result_service = build_engineering_result_service()
    created = result_service.ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project.id,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="SAP2000",
            software_version="27",
            analysis_type="LINEAR_STATIC",
            raw_results=_vendor_raw_results(),
            provenance={"source_software": "SAP2000", "execution_mode": "vendor"},
        )
    )
    listed = result_service.list_result_sets(project.id)
    assert len(listed) == 1
    fetched = result_service.get_result_set(project.id, created.id)
    assert fetched.id == created.id
