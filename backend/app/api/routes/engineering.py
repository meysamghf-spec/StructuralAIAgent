"""Analysis and design REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_analysis_engine_service, get_design_engine_service
from app.api.schemas.engineering import (
    AnalysisRequestBody,
    AnalysisResultResponse,
    DesignRequestBody,
    DesignResultResponse,
)
from app.application.analysis_engine_service import AnalysisEngineService
from app.application.design_engine_service import DesignEngineService

router = APIRouter(prefix="/engineering", tags=["engineering"])


@router.post("/analysis/run", response_model=AnalysisResultResponse)
def run_analysis(
    body: AnalysisRequestBody,
    analysis_service: Annotated[AnalysisEngineService, Depends(get_analysis_engine_service)],
) -> AnalysisResultResponse:
    result = analysis_service.run_analysis(body.to_domain())
    return AnalysisResultResponse.from_domain(result)


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
) -> DesignResultResponse:
    result = design_service.run_design(body.to_domain())
    return DesignResultResponse.from_domain(result)
