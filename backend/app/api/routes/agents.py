"""Agent registry REST endpoints — /api/v1/agents."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.api.deps import (
    get_actor_id,
    get_agent_registry_service,
    get_agent_version_service,
    get_prompt_template_service,
)
from app.api.schemas.agent import (
    AgentDefinitionResponse,
    AgentListResponse,
    AgentVersionListResponse,
    AgentVersionResponse,
    CreateAgentRequest,
    CreateAgentVersionRequest,
)
from app.api.schemas.prompt import (
    CreatePromptTemplateRequest,
    PromptTemplateListResponse,
    PromptTemplateResponse,
)
from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_version_service import AgentVersionService
from app.application.prompt_template_service import PromptTemplateService

router = APIRouter(prefix="/agents", tags=["agents"])


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgentDefinitionResponse)
def create_agent(
    body: CreateAgentRequest,
    registry_service: Annotated[AgentRegistryService, Depends(get_agent_registry_service)],
) -> AgentDefinitionResponse:
    definition = registry_service.create_agent(
        key=body.key,
        name=body.name,
        description=body.description,
    )
    return AgentDefinitionResponse.from_domain(definition)


@router.get("", response_model=AgentListResponse)
def list_agents(
    registry_service: Annotated[AgentRegistryService, Depends(get_agent_registry_service)],
) -> AgentListResponse:
    agents = registry_service.list_agents()
    return AgentListResponse(
        agents=[AgentDefinitionResponse.from_domain(agent) for agent in agents]
    )


@router.get("/{agent_id}", response_model=AgentDefinitionResponse)
def get_agent(
    agent_id: UUID,
    registry_service: Annotated[AgentRegistryService, Depends(get_agent_registry_service)],
) -> AgentDefinitionResponse:
    definition = registry_service.get_agent(agent_id)
    return AgentDefinitionResponse.from_domain(definition)


@router.post(
    "/{agent_id}/versions",
    status_code=status.HTTP_201_CREATED,
    response_model=AgentVersionResponse,
)
def create_agent_version(
    agent_id: UUID,
    body: CreateAgentVersionRequest,
    version_service: Annotated[AgentVersionService, Depends(get_agent_version_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> AgentVersionResponse:
    detail = version_service.create_version(
        agent_id,
        instructions=body.instructions,
        configuration_metadata=body.configuration_metadata,
        capability_keys=body.capability_keys,
        created_by=actor_id,
    )
    return AgentVersionResponse.from_detail(detail.version, detail.capabilities)


@router.get("/{agent_id}/versions", response_model=AgentVersionListResponse)
def list_agent_versions(
    agent_id: UUID,
    version_service: Annotated[AgentVersionService, Depends(get_agent_version_service)],
) -> AgentVersionListResponse:
    versions = version_service.list_versions(agent_id)
    return AgentVersionListResponse(
        versions=[
            AgentVersionResponse.from_detail(version, [])
            for version in versions
        ]
    )


@router.get("/{agent_id}/versions/{version}", response_model=AgentVersionResponse)
def get_agent_version(
    agent_id: UUID,
    version: int,
    version_service: Annotated[AgentVersionService, Depends(get_agent_version_service)],
) -> AgentVersionResponse:
    detail = version_service.get_version(agent_id, version)
    return AgentVersionResponse.from_detail(detail.version, detail.capabilities)


@router.post("/{agent_id}/versions/{version}/activate", response_model=AgentVersionResponse)
def activate_agent_version(
    agent_id: UUID,
    version: int,
    version_service: Annotated[AgentVersionService, Depends(get_agent_version_service)],
) -> AgentVersionResponse:
    detail = version_service.activate_version(agent_id, version)
    return AgentVersionResponse.from_detail(detail.version, detail.capabilities)


@router.post("/{agent_id}/versions/{version}/archive", response_model=AgentVersionResponse)
def archive_agent_version(
    agent_id: UUID,
    version: int,
    version_service: Annotated[AgentVersionService, Depends(get_agent_version_service)],
) -> AgentVersionResponse:
    detail = version_service.archive_version(agent_id, version)
    return AgentVersionResponse.from_detail(detail.version, detail.capabilities)


@router.post(
    "/{agent_id}/versions/{version}/prompts",
    status_code=status.HTTP_201_CREATED,
    response_model=PromptTemplateResponse,
)
def create_prompt_template(
    agent_id: UUID,
    version: int,
    body: CreatePromptTemplateRequest,
    prompt_service: Annotated[PromptTemplateService, Depends(get_prompt_template_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
) -> PromptTemplateResponse:
    prompt = prompt_service.create_prompt(
        agent_id,
        version,
        name=body.name,
        template=body.template,
        variables_schema=body.variables_schema,
        created_by=actor_id,
    )
    return PromptTemplateResponse.from_domain(prompt)


@router.get("/{agent_id}/versions/{version}/prompts", response_model=PromptTemplateListResponse)
def list_prompt_templates(
    agent_id: UUID,
    version: int,
    prompt_service: Annotated[PromptTemplateService, Depends(get_prompt_template_service)],
) -> PromptTemplateListResponse:
    prompts = prompt_service.list_prompts(agent_id, version)
    return PromptTemplateListResponse(
        prompts=[PromptTemplateResponse.from_domain(prompt) for prompt in prompts]
    )
