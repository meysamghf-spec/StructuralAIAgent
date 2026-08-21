"""Application service — agent version lifecycle and immutability."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.exceptions import (
    AgentNotFoundError,
    AgentVersionImmutableError,
    AgentVersionNotFoundError,
    CapabilityNotFoundError,
    InvalidLifecycleTransitionError,
)
from app.domain.models.agent import (
    AgentCapability,
    AgentDefinitionStatus,
    AgentVersion,
    AgentVersionStatus,
)
from app.domain.repositories.agent_protocols import (
    AgentCapabilityRepository,
    AgentDefinitionRepository,
    AgentVersionRepository,
)


@dataclass
class AgentVersionDetail:
    version: AgentVersion
    capabilities: list[AgentCapability]


class AgentVersionService:
    def __init__(
        self,
        definition_repository: AgentDefinitionRepository,
        version_repository: AgentVersionRepository,
        capability_repository: AgentCapabilityRepository,
    ) -> None:
        self._definitions = definition_repository
        self._versions = version_repository
        self._capabilities = capability_repository

    def _require_definition(self, agent_id: UUID):
        definition = self._definitions.get_by_id(agent_id)
        if definition is None:
            raise AgentNotFoundError(agent_id)
        return definition

    def _require_version(self, agent_id: UUID, version: int) -> AgentVersion:
        self._require_definition(agent_id)
        agent_version = self._versions.get_by_definition_and_version(agent_id, version)
        if agent_version is None:
            raise AgentVersionNotFoundError(agent_id, version)
        return agent_version

    def create_version(
        self,
        agent_id: UUID,
        *,
        instructions: str | None = None,
        configuration_metadata: dict | None = None,
        capability_keys: list[str] | None = None,
        created_by: str | None = None,
    ) -> AgentVersionDetail:
        definition = self._require_definition(agent_id)
        if definition.status == AgentDefinitionStatus.ARCHIVED:
            raise InvalidLifecycleTransitionError(
                "Cannot create versions for an archived agent definition",
                details={"agent_id": str(agent_id)},
            )

        agent_version = self._versions.create(
            agent_id,
            instructions=instructions,
            configuration_metadata=configuration_metadata,
            created_by=created_by,
            status=AgentVersionStatus.DRAFT,
        )

        capabilities: list[AgentCapability] = []
        for key in capability_keys or []:
            capability = self._capabilities.get_by_key(key)
            if capability is None:
                raise CapabilityNotFoundError(key)
            self._capabilities.assign_to_version(agent_version.id, capability.id)
            capabilities.append(capability)

        return AgentVersionDetail(version=agent_version, capabilities=capabilities)

    def get_version(self, agent_id: UUID, version: int) -> AgentVersionDetail:
        agent_version = self._require_version(agent_id, version)
        capabilities = self._capabilities.list_for_version(agent_version.id)
        return AgentVersionDetail(version=agent_version, capabilities=capabilities)

    def list_versions(self, agent_id: UUID) -> list[AgentVersion]:
        self._require_definition(agent_id)
        return self._versions.list_for_definition(agent_id)

    def get_active_version(self, agent_id: UUID) -> AgentVersionDetail | None:
        self._require_definition(agent_id)
        active = self._versions.get_active_for_definition(agent_id)
        if active is None:
            return None
        capabilities = self._capabilities.list_for_version(active.id)
        return AgentVersionDetail(version=active, capabilities=capabilities)

    def activate_version(
        self, agent_id: UUID, version: int, *, created_by: str | None = None
    ) -> AgentVersionDetail:
        definition = self._require_definition(agent_id)
        if definition.status == AgentDefinitionStatus.ARCHIVED:
            raise InvalidLifecycleTransitionError(
                "Cannot activate versions for an archived agent definition",
                details={"agent_id": str(agent_id)},
            )

        agent_version = self._require_version(agent_id, version)
        if agent_version.status == AgentVersionStatus.ACTIVE:
            return self.get_version(agent_id, version)
        if agent_version.status == AgentVersionStatus.ARCHIVED:
            raise InvalidLifecycleTransitionError(
                "Archived agent versions cannot be reactivated",
                details={"agent_id": str(agent_id), "version": version},
            )

        self._versions.archive_active_for_definition(agent_id)
        updated = self._versions.update_status(agent_version.id, AgentVersionStatus.ACTIVE)
        assert updated is not None

        if definition.status == AgentDefinitionStatus.DRAFT:
            self._definitions.update_status(agent_id, AgentDefinitionStatus.ACTIVE)
        self._definitions.set_current_version(agent_id, version)

        return self.get_version(agent_id, version)

    def archive_version(self, agent_id: UUID, version: int) -> AgentVersionDetail:
        definition = self._require_definition(agent_id)
        agent_version = self._require_version(agent_id, version)

        if agent_version.status == AgentVersionStatus.ARCHIVED:
            return self.get_version(agent_id, version)
        if agent_version.status == AgentVersionStatus.ACTIVE:
            if definition.current_version == version:
                self._definitions.set_current_version(agent_id, None)
            updated = self._versions.update_status(
                agent_version.id, AgentVersionStatus.ARCHIVED
            )
            assert updated is not None
            return self.get_version(agent_id, version)

        updated = self._versions.update_status(agent_version.id, AgentVersionStatus.ARCHIVED)
        assert updated is not None
        return self.get_version(agent_id, version)

    def ensure_mutable(self, agent_id: UUID, version: int) -> None:
        agent_version = self._require_version(agent_id, version)
        if agent_version.status == AgentVersionStatus.ACTIVE:
            raise AgentVersionImmutableError(agent_id, version)

    def update_draft_version(
        self,
        agent_id: UUID,
        version: int,
        *,
        instructions: str | None = None,
        configuration_metadata: dict | None = None,
    ) -> AgentVersionDetail:
        agent_version = self._require_version(agent_id, version)
        if agent_version.status != AgentVersionStatus.DRAFT:
            raise AgentVersionImmutableError(agent_id, version)

        updated = self._versions.update_draft(
            agent_version.id,
            instructions=instructions,
            configuration_metadata=configuration_metadata,
        )
        if updated is None:
            raise AgentVersionImmutableError(agent_id, version)
        return self.get_version(agent_id, version)

    def replace_version_capabilities(
        self,
        agent_version_id: UUID,
        capability_ids: list[UUID],
    ) -> None:
        self._versions.replace_capabilities(agent_version_id, capability_ids)

    def deactivate_version(self, agent_id: UUID, version: int) -> AgentVersionDetail:
        definition = self._require_definition(agent_id)
        agent_version = self._require_version(agent_id, version)
        if agent_version.status != AgentVersionStatus.ACTIVE:
            raise InvalidLifecycleTransitionError(
                "Only active versions can be deactivated",
                details={"agent_id": str(agent_id), "version": version},
            )

        updated = self._versions.update_status(agent_version.id, AgentVersionStatus.INACTIVE)
        assert updated is not None
        if definition.current_version == version:
            self._definitions.set_current_version(agent_id, None)
        return self.get_version(agent_id, version)

    def rollback_to_version(
        self,
        agent_id: UUID,
        version: int,
        *,
        created_by: str | None = None,
    ) -> AgentVersionDetail:
        definition = self._require_definition(agent_id)
        agent_version = self._require_version(agent_id, version)
        if agent_version.status not in {
            AgentVersionStatus.ARCHIVED,
            AgentVersionStatus.INACTIVE,
        }:
            raise InvalidLifecycleTransitionError(
                "Rollback target must be an inactive or archived version",
                details={"agent_id": str(agent_id), "version": version},
            )

        self._versions.archive_active_for_definition(agent_id)
        updated = self._versions.update_status(agent_version.id, AgentVersionStatus.ACTIVE)
        assert updated is not None

        if definition.status != AgentDefinitionStatus.ACTIVE:
            self._definitions.update_status(agent_id, AgentDefinitionStatus.ACTIVE)
        self._definitions.set_current_version(agent_id, version)
        return self.get_version(agent_id, version)
