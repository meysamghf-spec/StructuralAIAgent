"""Human Approval Gate REST endpoints — /api/v1/approvals."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_accessible_project_from_query,
    get_current_account,
    get_human_approval_service,
    get_project_access_service,
)
from app.api.schemas.human_approval import (
    ApprovalCancelRequest,
    ApprovalCreateRequest,
    ApprovalDecisionRequest,
    ApprovalEventResponse,
    ApprovalHistoryResponse,
    ApprovalListResponse,
    ApprovalRejectRequest,
    HumanApprovalResponse,
)
from app.application import revision_workflow
from app.application.human_approval_service import HumanApprovalService
from app.application.project_access_service import ProjectAccessService
from app.domain.models.human_approval import ApprovalStatus
from app.domain.models.project import Project
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/approvals", tags=["approvals"])


@router.post("", response_model=HumanApprovalResponse, status_code=status.HTTP_201_CREATED)
def create_approval_request(
    body: ApprovalCreateRequest,
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> HumanApprovalResponse:
    access.require_project(body.project_id, account)
    request = approval_service.create_request(
        body.project_id,
        requester=account.account_id,
        target_type=body.target_type,
        target_action=body.target_action,
        summary=body.summary,
        target_object_type=body.target_object_type,
        target_object_id=body.target_object_id,
        metadata=body.metadata,
    )
    return HumanApprovalResponse.from_domain(request)


@router.get("", response_model=ApprovalListResponse)
def list_approval_requests(
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    status_filter: ApprovalStatus | None = Query(default=None, alias="status"),
) -> ApprovalListResponse:
    requests = approval_service.list_requests(project.id, status=status_filter)
    return ApprovalListResponse(
        requests=[HumanApprovalResponse.from_domain(item) for item in requests]
    )


@router.get("/pending", response_model=ApprovalListResponse)
def list_pending_approvals(
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
) -> ApprovalListResponse:
    requests = approval_service.list_pending(project.id)
    return ApprovalListResponse(
        requests=[HumanApprovalResponse.from_domain(item) for item in requests]
    )


@router.get("/history", response_model=ApprovalHistoryResponse)
def get_approval_history(
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    approval_request_id: UUID | None = Query(default=None),
) -> ApprovalHistoryResponse:
    events = approval_service.get_history(
        project.id,
        approval_request_id=approval_request_id,
    )
    return ApprovalHistoryResponse(
        events=[ApprovalEventResponse.from_domain(event) for event in events]
    )


@router.get("/{request_id}", response_model=HumanApprovalResponse)
def get_approval_request(
    request_id: UUID,
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
) -> HumanApprovalResponse:
    request = approval_service.get_request(project.id, request_id)
    return HumanApprovalResponse.from_domain(request)


@router.post("/{request_id}/approve", response_model=HumanApprovalResponse)
def approve_request(
    request_id: UUID,
    body: ApprovalDecisionRequest,
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> HumanApprovalResponse:
    request = approval_service.approve_request(
        project.id,
        request_id,
        approver=account.account_id,
        decision_note=body.decision_note,
    )
    return HumanApprovalResponse.from_domain(request)


@router.post("/{request_id}/reject", response_model=HumanApprovalResponse)
def reject_request(
    request_id: UUID,
    body: ApprovalRejectRequest,
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> HumanApprovalResponse:
    request = approval_service.reject_request(
        project.id,
        request_id,
        approver=account.account_id,
        rejection_reason=body.rejection_reason,
    )
    response = HumanApprovalResponse.from_domain(request)
    outcome = revision_workflow.handle_rejection(approval_service, project.id, request, body.rejection_reason, account.account_id)
    if outcome["outcome"] == "revised":
        changes = "; ".join(f"{c['key']}: {c['old']} → {c['new']}" for c in outcome["changes"])
        response.revision_outcome, response.next_approval_id = "revised", outcome["approval"].id
        response.revision_message = f"Re-ran and created revision {outcome['approval'].metadata.get('revision')}: {changes}"
    elif outcome["outcome"] == "clarify":
        response.revision_outcome, response.revision_message = "clarify", outcome["message"]
        _post_chat_message((request.metadata or {}).get("conversation_id"), outcome["message"])
    return response


def _post_chat_message(conversation_id: str | None, text: str) -> None:
    """Ask for clarification in the conversation that produced the run (best effort)."""
    if not conversation_id:
        return
    try:
        from app.domain.models.conversation import MessageRole
        from app.infrastructure.repositories.postgres_conversation_repository import PostgresConversationRepository

        PostgresConversationRepository().create_message(conversation_id=UUID(conversation_id), role=MessageRole.ASSISTANT,
                                                         content=text, metadata={"kind": "approval_clarification"})
    except Exception:  # noqa: BLE001 - never fail the rejection because the chat note could not be written
        pass


@router.post("/{request_id}/cancel", response_model=HumanApprovalResponse)
def cancel_request(
    request_id: UUID,
    body: ApprovalCancelRequest,
    approval_service: Annotated[HumanApprovalService, Depends(get_human_approval_service)],
    project: Annotated[Project, Depends(get_accessible_project_from_query)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> HumanApprovalResponse:
    request = approval_service.cancel_request(
        project.id,
        request_id,
        actor=account.account_id,
        reason=body.reason,
    )
    return HumanApprovalResponse.from_domain(request)
