"""Agent registry repository interfaces — domain layer only."""

from __future__ import annotations

from typing import Protocol
from uuid import UUID

from app.domain.models.agent import (
    AgentCapability,
    AgentDefinition,
    AgentDefinitionStatus,
    AgentVersion,
    AgentVersionStatus,
)
from app.domain.models.prompt_template import PromptTemplate, PromptTemplateStatus


class AgentDefinitionRepository(Protocol):
    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
    ) -> AgentDefinition: ...

    def get_by_id(self, agent_id: UUID) -> AgentDefinition | None: ...

    def get_by_key(self, key: str) -> AgentDefinition | None: ...

    def list_all(self) -> list[AgentDefinition]: ...

    def update_status(
        self, agent_id: UUID, status: AgentDefinitionStatus
    ) -> AgentDefinition | None: ...

    def set_current_version(
        self, agent_id: UUID, version: int | None
    ) -> AgentDefinition | None: ...


class AgentVersionRepository(Protocol):
    def create(
        self,
        agent_definition_id: UUID,
        *,
        version: int | None = None,
        instructions: str | None = None,
        configuration_metadata: dict | None = None,
        created_by: str | None = None,
        status: AgentVersionStatus = AgentVersionStatus.DRAFT,
    ) -> AgentVersion: ...

    def get_by_id(self, version_id: UUID) -> AgentVersion | None: ...

    def get_by_definition_and_version(
        self, agent_definition_id: UUID, version: int
    ) -> AgentVersion | None: ...

    def list_for_definition(self, agent_definition_id: UUID) -> list[AgentVersion]: ...

    def get_active_for_definition(
        self, agent_definition_id: UUID
    ) -> AgentVersion | None: ...

    def update_status(
        self, version_id: UUID, status: AgentVersionStatus
    ) -> AgentVersion | None: ...

    def archive_active_for_definition(self, agent_definition_id: UUID) -> None: ...


class AgentCapabilityRepository(Protocol):
    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        metadata: dict | None = None,
    ) -> AgentCapability: ...

    def get_by_key(self, key: str) -> AgentCapability | None: ...

    def get_by_id(self, capability_id: UUID) -> AgentCapability | None: ...

    def list_all(self) -> list[AgentCapability]: ...

    def assign_to_version(self, agent_version_id: UUID, capability_id: UUID) -> None: ...

    def list_for_version(self, agent_version_id: UUID) -> list[AgentCapability]: ...


class PromptTemplateRepository(Protocol):
    def create(
        self,
        agent_version_id: UUID,
        *,
        name: str,
        template: str,
        version: int | None = None,
        variables_schema: dict | None = None,
        created_by: str | None = None,
        status: PromptTemplateStatus = PromptTemplateStatus.DRAFT,
    ) -> PromptTemplate: ...

    def get_by_version_and_number(
        self, agent_version_id: UUID, version: int
    ) -> PromptTemplate | None: ...

    def list_for_version(self, agent_version_id: UUID) -> list[PromptTemplate]: ...

    def get_latest_for_version(self, agent_version_id: UUID) -> PromptTemplate | None: ...
