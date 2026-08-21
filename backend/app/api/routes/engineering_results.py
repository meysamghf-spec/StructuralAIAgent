"""Engineering result REST endpoints."""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends

from app.api.deps import get_actor_id, get_engineering_result_service
from app.api.schemas.engineering_results import (
    EngineeringResultListResponse,
    EngineeringResultSetResponse,
    EngineeringResultValidationResponse,
)
from app.application.engineering_result_service import EngineeringResultService

router = APIRouter(prefix="/engineering/results", tags=["engineering-results"])


@router.get("/{project_id}", response_model=EngineeringResultListResponse)
def list_engineering_results(
    project_id: UUID,
    result_service: Annotated[EngineeringResultService, Depends(get_engineering_result_service)],
    analysis_run_id: UUID | None = None,
) -> EngineeringResultListResponse:
    results = result_service.list_result_sets(
        project_id,
        analysis_run_id=analysis_run_id,
    )
    return EngineeringResultListResponse(
        project_id=project_id,
        results=[EngineeringResultSetResponse.from_domain(item) for item in results],
    )


@router.get("/{project_id}/{result_set_id}", response_model=EngineeringResultSetResponse)
def get_engineering_result(
    project_id: UUID,
    result_set_id: UUID,
    result_service: Annotated[EngineeringResultService, Depends(get_engineering_result_service)],
) -> EngineeringResultSetResponse:
    result = result_service.get_result_set(project_id, result_set_id)
    return EngineeringResultSetResponse.from_domain(result)


@router.get("/{project_id}/{result_set_id}/filter")
def filter_engineering_results(
    project_id: UUID,
    result_set_id: UUID,
    result_service: Annotated[EngineeringResultService, Depends(get_engineering_result_service)],
    member_id: str | None = None,
    joint_id: str | None = None,
    load_case: str | None = None,
    load_combination: str | None = None,
    result_category: str | None = None,
) -> dict[str, Any]:
    result = result_service.get_result_set(project_id, result_set_id)
    return result_service.filter_results(
        result,
        member_id=member_id,
        joint_id=joint_id,
        load_case=load_case,
        load_combination=load_combination,
        result_category=result_category,
    )


@router.get(
    "/{project_id}/{result_set_id}/validation",
    response_model=EngineeringResultValidationResponse,
)
def get_engineering_result_validation(
    project_id: UUID,
    result_set_id: UUID,
    result_service: Annotated[EngineeringResultService, Depends(get_engineering_result_service)],
) -> EngineeringResultValidationResponse:
    result = result_service.get_result_set(project_id, result_set_id)
    report = result_service.build_validation_report(result)
    return EngineeringResultValidationResponse(
        result_set_id=result.id,
        validation_status=report["validation_status"],
        engineering_results_available=report["engineering_results_available"],
        result_types=report["result_types"],
        validation_summary=report["validation_summary"],
    )
