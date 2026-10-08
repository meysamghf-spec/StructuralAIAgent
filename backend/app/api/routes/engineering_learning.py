"""Engineering learning REST endpoints."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_accessible_project,
    get_agent_runtime_service,
    get_current_account,
    get_engineering_learning_service,
)
from app.api.schemas.engineering_learning import (
    LearningCorrectionRequest,
    LearningCreateRequest,
    LearningDecisionRequest,
    LearningFeedbackRequest,
    LearningListResponse,
    LearningRecordResponse,
    LearningRetrievalResponse,
    LearningUseListResponse,
    LearningUseResponse,
)
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.engineering_learning_service import EngineeringLearningService
from app.domain.models.engineering_learning import LearningScope
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(
    prefix="/projects/{project_id}/learning",
    tags=["engineering-learning"],
    dependencies=[Depends(get_accessible_project)],
)


@router.post(
    "",
    response_model=LearningRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_candidate_learning(
    project_id: UUID,
    body: LearningCreateRequest,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> LearningRecordResponse:
    record = learning_service.create_candidate(
        owner_account_id=account.account_id,
        learning_scope=body.learning_scope,
        project_id=project_id,
        agent_id=body.agent_id,
        task_id=body.task_id,
        source_snapshot_id=body.source_snapshot_id,
        source_element_ids=body.source_element_ids,
        source_element_type=body.source_element_type,
        input_context=body.input_context,
        agent_output=body.agent_output,
        human_correction=body.human_correction,
        engineering_reason=body.engineering_reason,
        validation_result=body.validation_result,
        applicability=body.applicability,
        confidence=body.confidence,
        engineering_result_id=body.engineering_result_id,
    )
    return LearningRecordResponse.from_domain(record)


@router.post(
    "/corrections",
    response_model=LearningRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def capture_correction(
    project_id: UUID,
    body: LearningCorrectionRequest,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> LearningRecordResponse:
    record = learning_service.record_correction(
        project_id=project_id,
        owner_account_id=account.account_id,
        original_output=body.original_output,
        corrected_result=body.corrected_result,
        reason=body.reason,
        learning_scope=body.learning_scope,
        agent_id=body.agent_id,
        task_id=body.task_id,
        source_snapshot_id=body.source_snapshot_id,
        source_element_ids=body.source_element_ids,
        source_element_type=body.source_element_type,
        applicability=body.applicability,
        validation_result=body.validation_result,
        engineering_result_id=body.engineering_result_id,
        input_context=body.input_context,
    )
    return LearningRecordResponse.from_domain(record)


@router.post(
    "/feedback",
    response_model=LearningRecordResponse,
    status_code=status.HTTP_201_CREATED,
)
def capture_engineering_result_feedback(
    project_id: UUID,
    body: LearningFeedbackRequest,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    runtime: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> LearningRecordResponse:
    execution = runtime.get_execution(body.execution_id)
    record = learning_service.candidate_from_engineering_result(
        project_id=project_id,
        owner_account_id=account.account_id,
        execution=execution,
        corrected_result=body.corrected_result,
        reason=body.reason,
        learning_scope=body.learning_scope,
        source_element_ids=body.source_element_ids,
        source_element_type=body.source_element_type,
        applicability=body.applicability,
    )
    return LearningRecordResponse.from_domain(record)


@router.get("", response_model=LearningListResponse)
def list_learning(
    project_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> LearningListResponse:
    records = learning_service.list_visible(project_id=project_id, account_id=account.account_id)
    return LearningListResponse(records=[LearningRecordResponse.from_domain(item) for item in records])


@router.get("/retrieval", response_model=LearningRetrievalResponse)
def retrieve_approved_learning(
    project_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_id: str | None = Query(default=None),
    task_type: str | None = Query(default=None),
    element_type: str | None = Query(default=None),
    learning_scope: LearningScope | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=50),
) -> LearningRetrievalResponse:
    retrieval = learning_service.retrieve(
        project_id=project_id,
        account_id=account.account_id,
        agent_id=agent_id,
        task_type=task_type,
        element_type=element_type,
        learning_scope=learning_scope,
        limit=limit,
    )
    return LearningRetrievalResponse.from_domain(retrieval)


@router.get("/tasks/{task_id}", response_model=LearningUseListResponse)
def learning_used_by_task(
    project_id: UUID,
    task_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
) -> LearningUseListResponse:
    uses = learning_service.uses_for_task(project_id=project_id, task_id=task_id)
    return LearningUseListResponse(
        task_id=task_id,
        uses=[LearningUseResponse.model_validate(item) for item in uses],
    )


@router.get("/{record_id}", response_model=LearningRecordResponse)
def get_learning_record(
    project_id: UUID,
    record_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> LearningRecordResponse:
    record = learning_service.get(record_id, project_id=project_id, account_id=account.account_id)
    return LearningRecordResponse.from_domain(record)


@router.get("/{record_id}/provenance")
def get_learning_provenance(
    project_id: UUID,
    record_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> dict:
    return learning_service.provenance(record_id, project_id=project_id, account_id=account.account_id)


@router.post("/{record_id}/review", response_model=LearningRecordResponse)
def review_learning(
    project_id: UUID,
    record_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> LearningRecordResponse:
    record = learning_service.mark_review(
        record_id,
        project_id=project_id,
        account_id=account.account_id,
    )
    return LearningRecordResponse.from_domain(record)


@router.post("/{record_id}/approve", response_model=LearningRecordResponse)
def approve_learning(
    project_id: UUID,
    record_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    body: LearningDecisionRequest | None = None,
) -> LearningRecordResponse:
    record = learning_service.approve(
        record_id,
        project_id=project_id,
        account_id=account.account_id,
        note=body.note if body is not None else None,
    )
    return LearningRecordResponse.from_domain(record)


@router.post("/{record_id}/reject", response_model=LearningRecordResponse)
def reject_learning(
    project_id: UUID,
    record_id: UUID,
    learning_service: Annotated[EngineeringLearningService, Depends(get_engineering_learning_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    body: LearningDecisionRequest | None = None,
) -> LearningRecordResponse:
    record = learning_service.reject(
        record_id,
        project_id=project_id,
        account_id=account.account_id,
        reason=body.reason if body is not None else None,
    )
    return LearningRecordResponse.from_domain(record)
