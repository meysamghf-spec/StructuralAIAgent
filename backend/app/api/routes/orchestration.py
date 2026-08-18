"""Hybrid orchestration REST endpoints — /api/v1/orchestration."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.api.deps import get_hybrid_orchestration_service
from app.api.schemas.orchestration import OrchestrationResultResponse, OrchestrationTaskRequest
from app.application.hybrid_orchestration_service import HybridOrchestrationService

router = APIRouter(prefix="/orchestration", tags=["orchestration"])


@router.post("/execute", response_model=OrchestrationResultResponse)
def execute_orchestration_task(
    body: OrchestrationTaskRequest,
    orchestration_service: Annotated[
        HybridOrchestrationService, Depends(get_hybrid_orchestration_service)
    ],
) -> OrchestrationResultResponse:
    result = orchestration_service.execute(body.to_domain())
    return OrchestrationResultResponse.from_domain(result)
