"""Agent definition access control for global and project-scoped agents."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import AgentNotFoundError, AgentAuthorizationError
from app.application.project_access_service import ProjectAccessService
from app.domain.models.agent import AgentDefinition
from app.domain.models.user import AuthenticatedAccount
from app.domain.repositories.agent_protocols import AgentDefinitionRepository
from app.infrastructure.config import get_settings


class AgentAccessService:
    def __init__(
        self,
        definition_repository: AgentDefinitionRepository,
        project_access_service: ProjectAccessService,
    ) -> None:
        self._definitions = definition_repository
        self._project_access = project_access_service

    def require_agent(
        self,
        agent_id: UUID,
        account: AuthenticatedAccount,
    ) -> AgentDefinition:
        definition = self._definitions.get_by_id(agent_id)
        if definition is None:
            raise AgentNotFoundError(agent_id)
        self._ensure_accessible(definition, account)
        return definition

    def require_agent_mutation(
        self,
        agent_id: UUID,
        account: AuthenticatedAccount,
    ) -> AgentDefinition:
        definition = self._definitions.get_by_id(agent_id)
        if definition is None:
            raise AgentNotFoundError(agent_id)
        if definition.project_id is None and self._project_access.enforcement_enabled:
            raise AgentAuthorizationError(
                agent_id,
                message="Global agents are read-only when project access enforcement is enabled",
            )
        self._ensure_accessible(definition, account)
        return definition

    def list_accessible_agents(
        self,
        account: AuthenticatedAccount,
        *,
        project_id: UUID | None = None,
    ) -> list[AgentDefinition]:
        if project_id is not None:
            self._project_access.require_project(project_id, account)
            project_agents = self._definitions.list_for_project(project_id)
            global_agents = self._definitions.list_global()
            return sorted(
                {agent.id: agent for agent in [*global_agents, *project_agents]}.values(),
                key=lambda item: item.created_at,
            )

        if self._project_access.enforcement_enabled:
            return self._definitions.list_global()
        return self._definitions.list_all()

    def _ensure_accessible(
        self,
        definition: AgentDefinition,
        account: AuthenticatedAccount,
    ) -> None:
        if definition.project_id is None:
            return
        self._project_access.require_project(definition.project_id, account)
