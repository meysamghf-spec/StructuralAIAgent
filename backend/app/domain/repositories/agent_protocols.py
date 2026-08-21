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
    EngineeringAgentType,
)
from app.domain.models.agent_runtime import AgentExecutionRecord, AgentExecutionStatus
from app.domain.models.agent_builder import AgentBuilderPublicationRecord, AgentVersionTestRecord
from app.domain.models.prompt_template import PromptTemplate, PromptTemplateStatus


class AgentDefinitionRepository(Protocol):
    def create(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        agent_type: EngineeringAgentType | None = None,
        configuration: dict | None = None,
        project_id: UUID | None = None,
    ) -> AgentDefinition: ...

    def update(
        self,
        agent_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        agent_type: EngineeringAgentType | None = None,
        configuration: dict | None = None,
    ) -> AgentDefinition | None: ...

    def list_for_project(self, project_id: UUID) -> list[AgentDefinition]: ...

    def list_global(self) -> list[AgentDefinition]: ...

    def get_by_id(self, agent_id: UUID) -> AgentDefinition | None: ...

    def get_by_key(self, key: str) -> AgentDefinition | None: ...

    def get_by_agent_type(self, agent_type: EngineeringAgentType) -> AgentDefinition | None: ...

    def list_all(self) -> list[AgentDefinition]: ...

    def list_by_agent_type(self, agent_type: EngineeringAgentType) -> list[AgentDefinition]: ...

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

    def update_draft(
        self,
        version_id: UUID,
        *,
        instructions: str | None = None,
        configuration_metadata: dict | None = None,
    ) -> AgentVersion | None: ...

    def replace_capabilities(self, agent_version_id: UUID, capability_ids: list[UUID]) -> None: ...


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


class AgentExecutionRepository(Protocol):
    def create(
        self,
        *,
        project_id: UUID,
        agent_definition_id: UUID,
        agent_version: int,
        input_request: dict,
        context_snapshot: dict,
        created_by: str | None = None,
    ) -> AgentExecutionRecord: ...

    def get_by_id(self, execution_id: UUID) -> AgentExecutionRecord | None: ...

    def update(self, record: AgentExecutionRecord) -> AgentExecutionRecord: ...

    def list_for_project(
        self,
        project_id: UUID,
        *,
        limit: int = 100,
    ) -> list[AgentExecutionRecord]: ...

    def get_by_approval_request_id(
        self,
        approval_request_id: UUID,
    ) -> AgentExecutionRecord | None: ...


class AgentVersionTestRepository(Protocol):
    def create(
        self,
        *,
        agent_definition_id: UUID,
        agent_version: int,
        project_id: UUID,
        test_input: dict,
        result: dict,
        validation_status: str | None = None,
        errors: list[str] | None = None,
        execution_metadata: dict | None = None,
        created_by: str | None = None,
    ) -> AgentVersionTestRecord: ...

    def list_for_version(
        self,
        agent_definition_id: UUID,
        agent_version: int,
        *,
        limit: int = 50,
    ) -> list[AgentVersionTestRecord]: ...


class AgentBuilderPublicationRepository(Protocol):
    def create(
        self,
        *,
        agent_definition_id: UUID,
        agent_version: int,
        action: str,
        status: str,
        project_id: UUID | None = None,
        approval_request_id: UUID | None = None,
        metadata: dict | None = None,
        created_by: str | None = None,
    ) -> AgentBuilderPublicationRecord: ...

    def update_status(
        self,
        publication_id: UUID,
        *,
        status: str,
        metadata: dict | None = None,
    ) -> AgentBuilderPublicationRecord | None: ...

    def get_by_approval_request_id(
        self,
        approval_request_id: UUID,
    ) -> AgentBuilderPublicationRecord | None: ...

    def list_for_definition(
        self,
        agent_definition_id: UUID,
        *,
        limit: int = 50,
    ) -> list[AgentBuilderPublicationRecord]: ...
