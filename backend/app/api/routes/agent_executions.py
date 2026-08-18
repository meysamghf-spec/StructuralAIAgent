"""Agent execution REST endpoints — /api/v1/agent-executions."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import get_actor_id, get_agent_runtime_service
from app.api.schemas.agent_execution import (
    AgentExecutionListResponse,
    AgentExecutionResponse,
    CreateAgentExecutionRequest,
)
from app.application.agent_runtime_service import AgentRuntimeService
from app.domain.models.agent_runtime import AgentExecutionRequest

router = APIRouter(prefix="/agent-executions", tags=["agent-executions"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgentExecutionResponse)
def create_agent_execution(
    body: CreateAgentExecutionRequest,
    runtime_service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> AgentExecutionResponse:
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
    )
    return AgentExecutionResponse.from_domain(record)


@router.get("/{execution_id}", response_model=AgentExecutionResponse)
def get_agent_execution(
    execution_id: UUID,
    runtime_service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
) -> AgentExecutionResponse:
    record = runtime_service.get_execution(execution_id)
    return AgentExecutionResponse.from_domain(record)


@router.get("", response_model=AgentExecutionListResponse)
def list_agent_executions(
    project_id: Annotated[UUID, Query()],
    runtime_service: Annotated[AgentRuntimeService, Depends(get_agent_runtime_service)],
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AgentExecutionListResponse:
    records = runtime_service.list_executions(project_id, limit=limit)
    return AgentExecutionListResponse(
        executions=[AgentExecutionResponse.from_domain(record) for record in records]
    )
