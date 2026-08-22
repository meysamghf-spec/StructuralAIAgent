"""Agent registry REST endpoints — /api/v1/agents."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from app.api.deps import (
    get_actor_id,
    get_agent_access_service,
    get_agent_builder_service,
    get_agent_registry_service,
    get_agent_version_service,
    get_current_account,
    get_optional_accessible_project_from_query,
    get_project_access_service,
    get_prompt_template_service,
)
from app.api.schemas.agent import (
    AgentCapabilityResponse,
    AgentDefinitionResponse,
    AgentListResponse,
    AgentVersionListResponse,
    AgentVersionResponse,
    CreateAgentRequest,
    CreateAgentVersionRequest,
)
from app.api.schemas.agent_builder import (
    AgentBuilderDetailResponse,
    AgentBuilderPublicationListResponse,
    AgentBuilderPublicationResponse,
    AgentBuilderValidationResponse,
    ConfigureAgentRequest,
    CreateBuilderAgentRequest,
    DeactivateAgentRequest,
    PublishAgentVersionRequest,
    RollbackAgentRequest,
    TestAgentVersionRequest,
    UpdateDraftVersionRequest,
    AgentVersionTestListResponse,
    AgentVersionTestResponse,
)
from app.api.schemas.prompt import (
    CreatePromptTemplateRequest,
    PromptTemplateListResponse,
    PromptTemplateResponse,
)
from app.application.agent_access_service import AgentAccessService
from app.application.agent_builder_service import AgentBuilderService
from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_version_service import AgentVersionService
from app.application.project_access_service import ProjectAccessService
from app.application.prompt_template_service import PromptTemplateService
from app.domain.models.project import Project
from app.domain.models.user import AuthenticatedAccount
from app.domain.models.agent import EngineeringAgentType
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)

router = APIRouter(prefix="/agents", tags=["agents"])


def _require_agent_access(
    agent_id: UUID,
    account: AuthenticatedAccount,
    agent_access: AgentAccessService,
) -> None:
    agent_access.require_agent(agent_id, account)


def _require_agent_mutation(
    agent_id: UUID,
    account: AuthenticatedAccount,
    agent_access: AgentAccessService,
) -> None:
    agent_access.require_agent_mutation(agent_id, account)


@router.post("/builder", status_code=status.HTTP_201_CREATED, response_model=AgentBuilderDetailResponse)
def create_builder_agent(
    body: CreateBuilderAgentRequest,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> AgentBuilderDetailResponse:
    if body.project_id is not None:
        access.require_project(body.project_id, account)
    agent_type = EngineeringAgentType(body.agent_type) if body.agent_type else None
    detail = builder_service.create_agent(
        key=body.key,
        name=body.name,
        description=body.description,
        agent_type=agent_type,
        configuration=body.configuration,
        project_id=body.project_id,
        instructions=body.instructions,
        capability_keys=body.capability_keys,
        created_by=actor_id,
    )
    return AgentBuilderDetailResponse.from_domain(detail)


@router.get("/capabilities", response_model=list[AgentCapabilityResponse])
def list_agent_capabilities() -> list[AgentCapabilityResponse]:
    capabilities = PostgresAgentCapabilityRepository().list_all()
    return [AgentCapabilityResponse.from_domain(capability) for capability in capabilities]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=AgentDefinitionResponse)
def create_agent(
    body: CreateAgentRequest,
    registry_service: Annotated[AgentRegistryService, Depends(get_agent_registry_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
) -> AgentDefinitionResponse:
    if body.project_id is not None:
        access.require_project(body.project_id, account)
    definition = registry_service.create_agent(
        key=body.key,
        name=body.name,
        description=body.description,
        agent_type=body.agent_type,
        configuration=body.configuration,
        project_id=body.project_id,
    )
    return AgentDefinitionResponse.from_domain(definition)


@router.get("", response_model=AgentListResponse)
def list_agents(
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
    project: Annotated[Project | None, Depends(get_optional_accessible_project_from_query)],
) -> AgentListResponse:
    agents = agent_access.list_accessible_agents(
        account,
        project_id=project.id if project is not None else None,
    )
    return AgentListResponse(
        agents=[AgentDefinitionResponse.from_domain(agent) for agent in agents]
    )


@router.get("/{agent_id}", response_model=AgentDefinitionResponse)
def get_agent(
    agent_id: UUID,
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentDefinitionResponse:
    definition = agent_access.require_agent(agent_id, account)
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
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentVersionResponse:
    _require_agent_mutation(agent_id, account, agent_access)
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
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentVersionListResponse:
    _require_agent_access(agent_id, account, agent_access)
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
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentVersionResponse:
    _require_agent_access(agent_id, account, agent_access)
    detail = version_service.get_version(agent_id, version)
    return AgentVersionResponse.from_detail(detail.version, detail.capabilities)


@router.post("/{agent_id}/versions/{version}/activate", response_model=AgentVersionResponse)
def activate_agent_version(
    agent_id: UUID,
    version: int,
    version_service: Annotated[AgentVersionService, Depends(get_agent_version_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentVersionResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    detail = version_service.activate_version(agent_id, version)
    return AgentVersionResponse.from_detail(detail.version, detail.capabilities)


@router.post("/{agent_id}/versions/{version}/archive", response_model=AgentVersionResponse)
def archive_agent_version(
    agent_id: UUID,
    version: int,
    version_service: Annotated[AgentVersionService, Depends(get_agent_version_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentVersionResponse:
    _require_agent_mutation(agent_id, account, agent_access)
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
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> PromptTemplateResponse:
    _require_agent_mutation(agent_id, account, agent_access)
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
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> PromptTemplateListResponse:
    _require_agent_access(agent_id, account, agent_access)
    prompts = prompt_service.list_prompts(agent_id, version)
    return PromptTemplateListResponse(
        prompts=[PromptTemplateResponse.from_domain(prompt) for prompt in prompts]
    )


@router.patch("/{agent_id}/configure", response_model=AgentDefinitionResponse)
def configure_agent(
    agent_id: UUID,
    body: ConfigureAgentRequest,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentDefinitionResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    agent_type = EngineeringAgentType(body.agent_type) if body.agent_type else None
    definition = builder_service.configure_agent(
        agent_id,
        name=body.name,
        description=body.description,
        agent_type=agent_type,
        configuration=body.configuration,
    )
    return AgentDefinitionResponse.from_domain(definition)


@router.put("/{agent_id}/versions/{version}/draft", response_model=AgentBuilderDetailResponse)
def update_draft_version(
    agent_id: UUID,
    version: int,
    body: UpdateDraftVersionRequest,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentBuilderDetailResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    detail = builder_service.update_draft_version(
        agent_id,
        version,
        instructions=body.instructions,
        configuration_metadata=body.configuration_metadata,
        capability_keys=body.capability_keys,
    )
    return AgentBuilderDetailResponse.from_domain(detail)


@router.post("/{agent_id}/versions/{version}/validate", response_model=AgentBuilderValidationResponse)
def validate_agent_version(
    agent_id: UUID,
    version: int,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentBuilderValidationResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    result = builder_service.validate_version(agent_id, version)
    return AgentBuilderValidationResponse.from_domain(result)


@router.post("/{agent_id}/versions/{version}/test", response_model=AgentVersionTestResponse)
def test_agent_version(
    agent_id: UUID,
    version: int,
    body: TestAgentVersionRequest,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentVersionTestResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    access.require_project(body.project_id, account)
    record = builder_service.test_version(
        agent_id,
        version,
        project_id=body.project_id,
        user_request=body.user_request,
        actor_id=actor_id,
    )
    return AgentVersionTestResponse.from_domain(record)


@router.post("/{agent_id}/versions/{version}/publish", response_model=AgentBuilderPublicationResponse)
def publish_agent_version(
    agent_id: UUID,
    version: int,
    body: PublishAgentVersionRequest,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentBuilderPublicationResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    access.require_project(body.project_id, account)
    publication = builder_service.request_publish(
        agent_id,
        version,
        project_id=body.project_id,
        actor_id=actor_id,
    )
    return AgentBuilderPublicationResponse.from_domain(publication)


@router.post("/{agent_id}/rollback", response_model=AgentBuilderPublicationResponse)
def rollback_agent_version(
    agent_id: UUID,
    body: RollbackAgentRequest,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentBuilderPublicationResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    access.require_project(body.project_id, account)
    publication = builder_service.request_rollback(
        agent_id,
        target_version=body.target_version,
        project_id=body.project_id,
        actor_id=actor_id,
    )
    return AgentBuilderPublicationResponse.from_domain(publication)


@router.post("/{agent_id}/deactivate", response_model=AgentDefinitionResponse)
def deactivate_agent(
    agent_id: UUID,
    body: DeactivateAgentRequest,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    actor_id: Annotated[str, Depends(get_actor_id)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    access: Annotated[ProjectAccessService, Depends(get_project_access_service)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentDefinitionResponse:
    _require_agent_mutation(agent_id, account, agent_access)
    access.require_project(body.project_id, account)
    definition = builder_service.deactivate_active_version(
        agent_id,
        project_id=body.project_id,
        actor_id=actor_id,
    )
    return AgentDefinitionResponse.from_domain(definition)


@router.get("/{agent_id}/builder", response_model=AgentBuilderDetailResponse)
def get_builder_detail(
    agent_id: UUID,
    version: Annotated[int, Query(ge=1)],
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentBuilderDetailResponse:
    _require_agent_access(agent_id, account, agent_access)
    detail = builder_service.get_builder_detail(agent_id, version)
    return AgentBuilderDetailResponse.from_domain(detail)


@router.get("/{agent_id}/publications", response_model=AgentBuilderPublicationListResponse)
def list_agent_publications(
    agent_id: UUID,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentBuilderPublicationListResponse:
    _require_agent_access(agent_id, account, agent_access)
    publications = builder_service.list_publications(agent_id)
    return AgentBuilderPublicationListResponse(
        publications=[AgentBuilderPublicationResponse.from_domain(item) for item in publications]
    )


@router.get("/{agent_id}/versions/{version}/tests", response_model=AgentVersionTestListResponse)
def list_agent_version_tests(
    agent_id: UUID,
    version: int,
    builder_service: Annotated[AgentBuilderService, Depends(get_agent_builder_service)],
    account: Annotated[AuthenticatedAccount, Depends(get_current_account)],
    agent_access: Annotated[AgentAccessService, Depends(get_agent_access_service)],
) -> AgentVersionTestListResponse:
    _require_agent_access(agent_id, account, agent_access)
    tests = builder_service.list_tests(agent_id, version)
    return AgentVersionTestListResponse(
        tests=[AgentVersionTestResponse.from_domain(item) for item in tests]
    )
