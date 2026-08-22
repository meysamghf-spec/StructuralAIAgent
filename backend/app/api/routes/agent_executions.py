"""Agent execution REST endpoints — /api/v1/agent-executions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_accessible_project_from_query,
    get_actor_id,
    get_agent_runtime_service,
    get_current_account,
    get_project_access_service,
)
from app.api.schemas.agent_execution import (
    AgentExecutionListResponse,
    AgentExecutionResponse,
    CreateAgentExecutionRequest,
)
from app.api.schemas.prompt_generation import PlanAgentExecutionRequest, PromptGenerationResponse
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.project_access_service import ProjectAccessService
from app.domain.models.agent_runtime import AgentExecutionRequest
from app.domain.models.project import Project
from app.domain.models.user import AuthenticatedAccount

router = APIRouter(prefix="/agent-executions", tags=["agent-executions"])


@router.post("/plan", response_model=PromptGenerationResponse)
def plan_agent_execution(
    body: PlanAgentExecutionRequest,
    runtime_service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> PromptGenerationResponse:
    access.require_project(body.project_id, account)
    result = runtime_service.plan_request(
        project_id=body.project_id,
        user_request=body.user_request,
    )
    return PromptGenerationResponse.from_domain(result)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgentExecutionResponse)
def create_agent_execution(
    body: CreateAgentExecutionRequest,
    runtime_service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> AgentExecutionResponse:
    access.require_project(body.project_id, account)
    record = runtime_service.execute(
        AgentExecutionRequest(
            project_id=body.project_id,
            agent_definition_id=body.agent_definition_id,
            agent_type=body.agent_type,
            user_request=body.user_request,
            parameters=body.parameters,
            requested_by=body.requested_by,
            requires_approval=body.requires_approval,
        ),
        actor_id=actor_id,
        account_id=account.account_id,
    )
    return AgentExecutionResponse.from_domain(record)


@router.get("/{execution_id}", response_model=AgentExecutionResponse)
def get_agent_execution(
    execution_id: UUID,
    runtime_service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> AgentExecutionResponse:
    record = runtime_service.get_execution(execution_id)
    access.require_project(record.project_id, account)
    return AgentExecutionResponse.from_domain(record)


@router.get("", response_model=AgentExecutionListResponse)
def list_agent_executions(
    _: Annotated[Project, Depends(get_accessible_project_from_query)],
    runtime_service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AgentExecutionListResponse:
    records = runtime_service.list_executions(_.id, limit=limit)
    return AgentExecutionListResponse(
        executions=[AgentExecutionResponse.from_domain(record) for record in records]
    )
