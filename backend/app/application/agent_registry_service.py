"""Application service — platform agent registry."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import (
    AgentKeyConflictError,
    AgentNotFoundError,
    InvalidLifecycleTransitionError,
)
from app.domain.models.agent import AgentDefinition, AgentDefinitionStatus, EngineeringAgentType
from app.domain.repositories.agent_protocols import AgentDefinitionRepository


class AgentRegistryService:
    def __init__(self, definition_repository: AgentDefinitionRepository) -> None:
        self._definitions = definition_repository

    def create_agent(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        agent_type: EngineeringAgentType | None = None,
        configuration: dict | None = None,
        project_id: UUID | None = None,
    ) -> AgentDefinition:
        if self._definitions.get_by_key(key) is not None and project_id is None:
            raise AgentKeyConflictError(key)
        if project_id is not None:
            existing = self._definitions.list_for_project(project_id)
            if any(agent.key == key for agent in existing):
                raise AgentKeyConflictError(key)
        return self._definitions.create(
            key=key,
            name=name,
            description=description,
            agent_type=agent_type,
            configuration=configuration,
            project_id=project_id,
        )

    def get_agent(self, agent_id: UUID) -> AgentDefinition:
        definition = self._definitions.get_by_id(agent_id)
        if definition is None:
            raise AgentNotFoundError(agent_id)
        return definition

    def list_agents(self) -> list[AgentDefinition]:
        return self._definitions.list_all()

    def list_agents_for_project(self, project_id: UUID) -> list[AgentDefinition]:
        return self._definitions.list_for_project(project_id)

    def archive_agent(self, agent_id: UUID) -> AgentDefinition:
        definition = self.get_agent(agent_id)
        if definition.status == AgentDefinitionStatus.ARCHIVED:
            raise InvalidLifecycleTransitionError(
                "Agent definition is already archived",
                details={"agent_id": str(agent_id)},
            )
        archived = self._definitions.update_status(agent_id, AgentDefinitionStatus.ARCHIVED)
        assert archived is not None
        return archived
