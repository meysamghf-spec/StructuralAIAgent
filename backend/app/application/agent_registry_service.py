"""Application service — platform agent registry."""

from __future__ import annotations

from uuid import UUID

from app.application.exceptions import (
    AgentKeyConflictError,
    AgentNotFoundError,
    InvalidLifecycleTransitionError,
)
from app.domain.models.agent import AgentDefinition, AgentDefinitionStatus
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
    ) -> AgentDefinition:
        if self._definitions.get_by_key(key) is not None:
            raise AgentKeyConflictError(key)
        return self._definitions.create(key=key, name=name, description=description)

    def get_agent(self, agent_id: UUID) -> AgentDefinition:
        definition = self._definitions.get_by_id(agent_id)
        if definition is None:
            raise AgentNotFoundError(agent_id)
        return definition

    def list_agents(self) -> list[AgentDefinition]:
        return self._definitions.list_all()

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
