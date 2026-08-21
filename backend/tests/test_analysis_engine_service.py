"""Application service tests — AnalysisEngineService."""

from uuid import uuid4

import pytest

from app.application.exceptions import AnalysisRunNotFoundError, ProjectNotFoundError
from app.application.service_factory import (
    build_analysis_engine_service,
    build_pem_model_service,
    build_project_service,
    build_traceability_service,
)
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _create_project(name: str = "Analysis Service Project"):
    return build_project_service().create_project(name).project


def _populate_model(project_id):
    service = build_pem_model_service()
    service.update_geometry(project_id, sample_geometry(), summary="Geometry")
    service.update_materials(project_id, sample_materials(), summary="Materials")
    service.update_sections(project_id, sample_sections(), summary="Sections")
    service.update_members(project_id, sample_members(), summary="Members")
    service.update_supports(project_id, sample_supports(), summary="Supports")
    service.update_load_cases(project_id, sample_load_cases(), summary="Loads")
    service.update_load_combinations(project_id, sample_load_combinations(), summary="Combos")


def test_readiness_reports_model_not_ready_for_empty_project(db_session) -> None:
    project = _create_project()
    service = build_analysis_engine_service()
    readiness = service.get_readiness(project.id)
    assert readiness.ready_for_solver is False
    assert readiness.readiness_status == "MODEL_NOT_READY"
    assert "structural members" in readiness.summary.lower()


def test_run_analysis_persists_run_and_traceability(db_session) -> None:
    project = _create_project()
    _populate_model(project.id)
    service = build_analysis_engine_service()
    from app.domain.models.analysis import AnalysisRequest

    result = service.run_analysis(
        AnalysisRequest(project_id=project.id, analysis_type="STATIC"),
        created_by="tester",
    )
    assert result.id is not None
    assert result.status.value == "REQUIRES_SOLVER"
    assert result.capability_status == "REQUIRES_SOLVER"
    assert result.outputs.get("engineering_results_available") is False
    assert result.pem_version > 1

    stored = service.get_run(project.id, result.id)
    assert stored.analysis_type == "STATIC"

    links = build_traceability_service().get_links_by_target(
        project.id,
        target_type="analysis_result",
        target_id=result.id,
    )
    assert len(links) == 1
    assert links[0].relationship_type.value == "MODEL_TO_ANALYSIS"


def test_run_analysis_empty_project_returns_model_not_ready(db_session) -> None:
    project = _create_project()
    service = build_analysis_engine_service()
    from app.domain.models.analysis import AnalysisRequest

    result = service.run_analysis(
        AnalysisRequest(project_id=project.id, analysis_type="STATIC"),
    )
    assert result.status.value == "MODEL_NOT_READY"
    assert result.outputs.get("engineering_results_available") is False


def test_summarize_load_combinations_uses_structural_model(db_session) -> None:
    project = _create_project()
    _populate_model(project.id)
    service = build_analysis_engine_service()
    summary = service.summarize_load_combinations(project.id)
    assert summary["load_combination_count"] == 1
    assert summary["load_case_count"] == 1
    assert len(summary["load_combinations"]) == 1


def test_list_runs_returns_history(db_session) -> None:
    project = _create_project()
    service = build_analysis_engine_service()
    from app.domain.models.analysis import AnalysisRequest

    service.run_analysis(AnalysisRequest(project_id=project.id, analysis_type="STATIC"))
    runs = service.list_runs(project.id)
    assert len(runs) == 1


def test_get_run_unknown_raises(db_session) -> None:
    project = _create_project()
    service = build_analysis_engine_service()
    with pytest.raises(AnalysisRunNotFoundError):
        service.get_run(project.id, uuid4())


def test_run_analysis_unknown_project_raises(db_session) -> None:
    service = build_analysis_engine_service()
    from app.domain.models.analysis import AnalysisRequest

    with pytest.raises(ProjectNotFoundError):
        service.run_analysis(AnalysisRequest(project_id=uuid4(), analysis_type="STATIC"))
