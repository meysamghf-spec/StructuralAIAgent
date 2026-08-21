"""Analysis and design REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import (
    get_actor_id,
    get_analysis_engine_service,
    get_design_engine_service,
    get_optimization_engine_service,
)
from app.api.schemas.engineering import (
    AnalysisReadinessResponse,
    AnalysisRequestBody,
    AnalysisResultResponse,
    AnalysisRunListResponse,
    AnalysisRunResponse,
    DesignReadinessResponse,
    DesignRequestBody,
    DesignResultResponse,
    DesignRunListResponse,
    DesignRunResponse,
    OptimizationReadinessResponse,
    OptimizationRequestBody,
    OptimizationResultResponse,
    OptimizationRunListResponse,
    OptimizationRunResponse,
)
from app.application.analysis_engine_service import AnalysisEngineService
from app.application.design_engine_service import DesignEngineService
from app.application.optimization_engine_service import OptimizationEngineService

router = APIRouter(prefix="/engineering", tags=["engineering"])


@router.post("/analysis/run", response_model=AnalysisResultResponse)
def run_analysis(
    body: AnalysisRequestBody,
    analysis_service: Annotated[AnalysisEngineService, Depends(get_analysis_engine_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> AnalysisResultResponse:
    result = analysis_service.run_analysis(body.to_domain(), created_by=actor_id)
    return AnalysisResultResponse.from_domain(result)


@router.get("/analysis/{project_id}/readiness", response_model=AnalysisReadinessResponse)
def get_analysis_readiness(
    project_id: UUID,
    analysis_service: Annotated[AnalysisEngineService, Depends(get_analysis_engine_service)],
    pem_version: int | None = None,
) -> AnalysisReadinessResponse:
    return AnalysisReadinessResponse.from_domain(
        analysis_service.get_readiness(project_id, pem_version=pem_version)
    )


@router.get("/analysis/{project_id}/runs", response_model=AnalysisRunListResponse)
def list_analysis_runs(
    project_id: UUID,
    analysis_service: Annotated[AnalysisEngineService, Depends(get_analysis_engine_service)],
) -> AnalysisRunListResponse:
    runs = analysis_service.list_runs(project_id)
    return AnalysisRunListResponse(
        project_id=project_id,
        runs=[AnalysisRunResponse.from_domain(run) for run in runs],
    )


@router.get("/analysis/{project_id}/runs/{run_id}", response_model=AnalysisRunResponse)
def get_analysis_run(
    project_id: UUID,
    run_id: UUID,
    analysis_service: Annotated[AnalysisEngineService, Depends(get_analysis_engine_service)],
) -> AnalysisRunResponse:
    return AnalysisRunResponse.from_domain(analysis_service.get_run(project_id, run_id))


@router.get("/analysis/{project_id}/load-combinations")
def get_load_combinations(
    project_id: UUID,
    analysis_service: Annotated[AnalysisEngineService, Depends(get_analysis_engine_service)],
) -> dict:
    return analysis_service.summarize_load_combinations(project_id)


@router.post("/design/run", response_model=DesignResultResponse)
def run_design(
    body: DesignRequestBody,
    design_service: Annotated[DesignEngineService, Depends(get_design_engine_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> DesignResultResponse:
    result = design_service.run_design(body.to_domain(), created_by=actor_id)
    return DesignResultResponse.from_domain(result)


@router.get("/design/{project_id}/readiness", response_model=DesignReadinessResponse)
def get_design_readiness(
    project_id: UUID,
    design_service: Annotated[DesignEngineService, Depends(get_design_engine_service)],
    pem_version: int | None = None,
) -> DesignReadinessResponse:
    return DesignReadinessResponse.from_domain(
        design_service.get_readiness(project_id, pem_version=pem_version)
    )


@router.get("/design/{project_id}/runs", response_model=DesignRunListResponse)
def list_design_runs(
    project_id: UUID,
    design_service: Annotated[DesignEngineService, Depends(get_design_engine_service)],
) -> DesignRunListResponse:
    runs = design_service.list_runs(project_id)
    return DesignRunListResponse(
        project_id=project_id,
        runs=[DesignRunResponse.from_domain(run) for run in runs],
    )


@router.get("/design/{project_id}/runs/{run_id}", response_model=DesignRunResponse)
def get_design_run(
    project_id: UUID,
    run_id: UUID,
    design_service: Annotated[DesignEngineService, Depends(get_design_engine_service)],
) -> DesignRunResponse:
    return DesignRunResponse.from_domain(design_service.get_run(project_id, run_id))


@router.get("/design/{project_id}/analysis-runs")
def list_design_analysis_runs(
    project_id: UUID,
    design_service: Annotated[DesignEngineService, Depends(get_design_engine_service)],
) -> dict:
    return {
        "project_id": str(project_id),
        "analysis_runs": design_service.list_available_analysis_runs(project_id),
    }


@router.post("/optimization/run", response_model=OptimizationResultResponse)
def run_optimization(
    body: OptimizationRequestBody,
    optimization_service: Annotated[
        OptimizationEngineService, Depends(get_optimization_engine_service)
    ],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> OptimizationResultResponse:
    result = optimization_service.run_optimization(body.to_domain(), created_by=actor_id)
    return OptimizationResultResponse.from_domain(result)


@router.get("/optimization/{project_id}/readiness", response_model=OptimizationReadinessResponse)
def get_optimization_readiness(
    project_id: UUID,
    optimization_service: Annotated[
        OptimizationEngineService, Depends(get_optimization_engine_service)
    ],
    pem_version: int | None = None,
) -> OptimizationReadinessResponse:
    return OptimizationReadinessResponse.from_domain(
        optimization_service.get_readiness(project_id, pem_version=pem_version)
    )


@router.get("/optimization/{project_id}/runs", response_model=OptimizationRunListResponse)
def list_optimization_runs(
    project_id: UUID,
    optimization_service: Annotated[
        OptimizationEngineService, Depends(get_optimization_engine_service)
    ],
) -> OptimizationRunListResponse:
    runs = optimization_service.list_runs(project_id)
    return OptimizationRunListResponse(
        project_id=project_id,
        runs=[OptimizationRunResponse.from_domain(run) for run in runs],
    )


@router.get("/optimization/{project_id}/runs/{run_id}", response_model=OptimizationRunResponse)
def get_optimization_run(
    project_id: UUID,
    run_id: UUID,
    optimization_service: Annotated[
        OptimizationEngineService, Depends(get_optimization_engine_service)
    ],
) -> OptimizationRunResponse:
    return OptimizationRunResponse.from_domain(optimization_service.get_run(project_id, run_id))


@router.get("/optimization/{project_id}/analysis-runs")
def list_optimization_analysis_runs(
    project_id: UUID,
    optimization_service: Annotated[
        OptimizationEngineService, Depends(get_optimization_engine_service)
    ],
) -> dict:
    return {
        "project_id": str(project_id),
        "analysis_runs": optimization_service.list_available_analysis_runs(project_id),
    }


@router.get("/optimization/{project_id}/design-runs")
def list_optimization_design_runs(
    project_id: UUID,
    optimization_service: Annotated[
        OptimizationEngineService, Depends(get_optimization_engine_service)
    ],
) -> dict:
    return {
        "project_id": str(project_id),
        "design_runs": optimization_service.list_available_design_runs(project_id),
    }
