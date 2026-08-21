"""Application service tests — OptimizationEngineService."""

from uuid import uuid4

import pytest

from app.application.exceptions import OptimizationRunNotFoundError, ProjectNotFoundError
from app.application.service_factory import (
    build_analysis_engine_service,
    build_design_engine_service,
    build_optimization_engine_service,
    build_pem_model_service,
    build_project_service,
    build_traceability_service,
)
from app.domain.models.analysis import AnalysisRequest
from app.domain.models.design import DesignRequest
from app.domain.models.optimization import OptimizationRequest
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _create_project(name: str = "Optimization Service Project"):
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
    readiness = build_optimization_engine_service().get_readiness(project.id)
    assert readiness.ready_for_optimization is False
    assert readiness.readiness_status == "MODEL_NOT_READY"


def test_run_optimization_empty_project_returns_model_not_ready(db_session) -> None:
    project = _create_project()
    result = build_optimization_engine_service().run_optimization(
        OptimizationRequest(
            project_id=project.id,
            optimization_type="WEIGHT",
            objective="Minimize structural weight",
        )
    )
    assert result.status.value == "MODEL_NOT_READY"
    assert result.outputs.get("engineering_optimization_results_available") is False


def test_run_optimization_configured_model_requires_analysis(db_session) -> None:
    project = _create_project()
    _populate_model(project.id)
    result = build_optimization_engine_service().run_optimization(
        OptimizationRequest(
            project_id=project.id,
            optimization_type="WEIGHT",
            objective="Minimize structural weight",
        ),
        created_by="tester",
    )
    assert result.status.value == "REQUIRES_ANALYSIS"
    assert result.id is not None


def test_run_optimization_with_design_run_links_traceability(db_session) -> None:
    project = _create_project()
    _populate_model(project.id)
    analysis = build_analysis_engine_service().run_analysis(
        AnalysisRequest(project_id=project.id, analysis_type="STATIC")
    )
    design = build_design_engine_service().run_design(
        DesignRequest(
            project_id=project.id,
            design_type="CONCRETE_BEAM",
            analysis_run_id=analysis.id,
        )
    )
    optimization = build_optimization_engine_service().run_optimization(
        OptimizationRequest(
            project_id=project.id,
            optimization_type="WEIGHT",
            objective="Minimize structural weight",
            design_run_id=design.id,
        )
    )
    assert optimization.design_run_id == design.id
    links = build_traceability_service().get_links_by_target(
        project.id,
        target_type="optimization_result",
        target_id=optimization.id,
    )
    relationship_types = {link.relationship_type.value for link in links}
    assert "DESIGN_TO_OPTIMIZATION" in relationship_types
    assert "MODEL_TO_OPTIMIZATION" in relationship_types


def test_list_optimization_runs_returns_history(db_session) -> None:
    project = _create_project()
    service = build_optimization_engine_service()
    service.run_optimization(
        OptimizationRequest(
            project_id=project.id,
            optimization_type="WEIGHT",
            objective="Minimize structural weight",
        )
    )
    assert len(service.list_runs(project.id)) == 1


def test_get_optimization_run_unknown_raises(db_session) -> None:
    project = _create_project()
    with pytest.raises(OptimizationRunNotFoundError):
        build_optimization_engine_service().get_run(project.id, uuid4())


def test_run_optimization_unknown_project_raises(db_session) -> None:
    with pytest.raises(ProjectNotFoundError):
        build_optimization_engine_service().run_optimization(
            OptimizationRequest(
                project_id=uuid4(),
                optimization_type="WEIGHT",
                objective="Minimize structural weight",
            )
        )
