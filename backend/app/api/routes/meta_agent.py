"""Meta-Agent API routes — capability discovery and new-agent proposal workflow."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import get_actor_id, get_current_account, get_meta_agent_service
from app.api.schemas.meta_agent import (
    AgentBuildResultResponse,
    AgentProposalRegistrationResponse,
    MetaAgentDecideRequest,
    MetaAgentDecisionResponse,
    MetaAgentSpecificationSubmissionResponse,
    SubmitAgentSpecificationRequest,
)
from app.application.meta_agent_service import MetaAgentService
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/meta-agent", tags=["meta-agent"])


@router.post("/decide", response_model=MetaAgentDecisionResponse)
def decide_meta_agent_route(
    body: MetaAgentDecideRequest,
    service: Annotated[MetaAgentService, Depends(get_meta_agent_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
) -> MetaAgentDecisionResponse:
    decision = service.decide(
        body.user_request,
        account,
        project_id=body.project_id,
    )
    return MetaAgentDecisionResponse.from_domain(decision)


@router.post(
    "/specifications/submit",
    status_code=status.HTTP_201_CREATED,
    response_model=MetaAgentSpecificationSubmissionResponse,
)
def submit_agent_specification_route(
    body: SubmitAgentSpecificationRequest,
    service: Annotated[MetaAgentService, Depends(get_meta_agent_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> MetaAgentSpecificationSubmissionResponse:
    submission = service.submit_specification_for_approval(
        body.specification,
        project_id=body.project_id,
        account=account,
        actor_id=actor_id,
        conversation_id=body.conversation_id,
    )
    return MetaAgentSpecificationSubmissionResponse.from_domain(submission)


@router.post(
    "/specifications/{approval_request_id}/register",
    response_model=AgentProposalRegistrationResponse,
)
def register_approved_proposal_route(
    approval_request_id: UUID,
    project_id: UUID,
    service: Annotated[MetaAgentService, Depends(get_meta_agent_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> AgentProposalRegistrationResponse:
    result = service.register_approved_proposal(
        project_id=project_id,
        approval_request_id=approval_request_id,
        account=account,
        actor_id=actor_id,
    )
    return AgentProposalRegistrationResponse.from_domain(result)


@router.post(
    "/specifications/{approval_request_id}/build",
    response_model=AgentBuildResultResponse,
)
def request_agent_build_route(
    approval_request_id: UUID,
    project_id: UUID,
    service: Annotated[MetaAgentService, Depends(get_meta_agent_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> AgentBuildResultResponse:
    result = service.request_build_after_approval(
        project_id=project_id,
        approval_request_id=approval_request_id,
        account=account,
        actor_id=actor_id,
    )
    return AgentBuildResultResponse.from_domain(result)
