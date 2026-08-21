"""Agent Builder — create, configure, test, publish, and rollback assistants."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.agent_builder_validation import validate_agent_configuration
from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_runtime_service import AgentRuntimeService
from app.application.agent_version_service import AgentVersionDetail, AgentVersionService
from app.application.exceptions import (
    AgentBuilderInvalidStateError,
    AgentBuilderValidationFailedError,
    AgentNotFoundError,
    AgentVersionImmutableError,
    AgentVersionNotFoundError,
    InvalidLifecycleTransitionError,
    ProjectAgentScopeError,
)
from app.application.human_approval_service import HumanApprovalService
from app.application.traceability_integration import (
    record_agent_to_agent_version,
    record_agent_version_to_approval,
    record_agent_version_to_test,
    record_approval_to_agent_version,
)
from app.application.traceability_service import TraceabilityService
from app.domain.approval_policy import requires_approval_for_target
from app.domain.models.agent import AgentDefinition, AgentDefinitionStatus, AgentVersionStatus, EngineeringAgentType
from app.domain.models.agent_builder import (
    AgentBuilderAction,
    AgentBuilderPublicationRecord,
    AgentBuilderPublicationStatus,
    AgentBuilderValidationResult,
    AgentVersionTestRecord,
)
from app.domain.models.agent_runtime import AgentExecutionRecord, AgentExecutionRequest
from app.domain.models.human_approval import ApprovalTargetType
from app.domain.repositories.agent_protocols import (
    AgentBuilderPublicationRepository,
    AgentCapabilityRepository,
    AgentDefinitionRepository,
    AgentVersionTestRepository,
)


@dataclass
class AgentBuilderVersionDetail:
    definition: AgentDefinition
    version: AgentVersionDetail
    validation: AgentBuilderValidationResult | None = None


class AgentBuilderService:
    def __init__(
        self,
        *,
        definition_repository: AgentDefinitionRepository,
        registry_service: AgentRegistryService,
        version_service: AgentVersionService,
        capability_repository: AgentCapabilityRepository,
        test_repository: AgentVersionTestRepository,
        publication_repository: AgentBuilderPublicationRepository,
        runtime_service: AgentRuntimeService,
        approval_service: HumanApprovalService,
        traceability_service: TraceabilityService,
    ) -> None:
        self._definitions = definition_repository
        self._registry = registry_service
        self._versions = version_service
        self._capabilities = capability_repository
        self._tests = test_repository
        self._publications = publication_repository
        self._runtime = runtime_service
        self._approval = approval_service
        self._traceability = traceability_service

    def create_agent(
        self,
        *,
        key: str,
        name: str,
        description: str | None = None,
        agent_type: EngineeringAgentType | None = None,
        configuration: dict | None = None,
        project_id: UUID | None = None,
        instructions: str | None = None,
        capability_keys: list[str] | None = None,
        created_by: str | None = None,
    ) -> AgentBuilderVersionDetail:
        definition = self._registry.create_agent(
            key=key,
            name=name,
            description=description,
            agent_type=agent_type,
            configuration=configuration,
            project_id=project_id,
        )
        version_detail = self._versions.create_version(
            definition.id,
            instructions=instructions,
            configuration_metadata={"allowed_tools": [], "model_configuration": {}},
            capability_keys=capability_keys or [],
            created_by=created_by,
        )
        if project_id is not None:
            record_agent_to_agent_version(
                self._traceability,
                project_id=project_id,
                agent_id=definition.id,
                version_id=version_detail.version.id,
                metadata={"version_number": version_detail.version.version},
            )
        return self._build_detail(definition, version_detail)

    def configure_agent(
        self,
        agent_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        agent_type: EngineeringAgentType | None = None,
        configuration: dict | None = None,
    ) -> AgentDefinition:
        definition = self._registry.get_agent(agent_id)
        if definition.status == AgentDefinitionStatus.ARCHIVED:
            raise InvalidLifecycleTransitionError(
                "Archived assistants cannot be configured.",
                details={"agent_id": str(agent_id)},
            )
        updated = self._definitions.update(
            agent_id,
            name=name,
            description=description,
            agent_type=agent_type,
            configuration=configuration,
        )
        assert updated is not None
        return updated

    def update_draft_version(
        self,
        agent_id: UUID,
        version: int,
        *,
        instructions: str | None = None,
        configuration_metadata: dict | None = None,
        capability_keys: list[str] | None = None,
    ) -> AgentBuilderVersionDetail:
        definition = self._registry.get_agent(agent_id)
        agent_version = self._versions.get_version(agent_id, version)
        if agent_version.version.status != AgentVersionStatus.DRAFT:
            raise AgentVersionImmutableError(agent_id, version)

        updated_version = self._versions.update_draft_version(
            agent_id,
            version,
            instructions=instructions,
            configuration_metadata=configuration_metadata,
        )
        if capability_keys is not None:
            capability_ids = []
            for key in capability_keys:
                capability = self._capabilities.get_by_key(key)
                if capability is None:
                    from app.application.exceptions import CapabilityNotFoundError

                    raise CapabilityNotFoundError(key)
                capability_ids.append(capability.id)
            self._versions.replace_version_capabilities(updated_version.version.id, capability_ids)
            updated_version = self._versions.get_version(agent_id, version)

        return self._build_detail(definition, updated_version)

    def validate_version(self, agent_id: UUID, version: int) -> AgentBuilderValidationResult:
        definition = self._registry.get_agent(agent_id)
        detail = self._versions.get_version(agent_id, version)
        capability_keys = [capability.key for capability in detail.capabilities]
        return validate_agent_configuration(
            definition=definition,
            version=detail.version,
            capability_keys=capability_keys,
        )

    def test_version(
        self,
        agent_id: UUID,
        version: int,
        *,
        project_id: UUID,
        user_request: str,
        actor_id: str,
    ) -> AgentVersionTestRecord:
        definition = self._registry.get_agent(agent_id)
        self._ensure_project_scope(definition, project_id)
        detail = self._versions.get_version(agent_id, version)
        if detail.version.status not in {AgentVersionStatus.DRAFT, AgentVersionStatus.INACTIVE}:
            raise AgentBuilderInvalidStateError(
                "Only draft or inactive versions can be tested without replacing the active version.",
                details={"agent_id": str(agent_id), "version": version},
            )

        execution = self._runtime.execute(
            AgentExecutionRequest(
                project_id=project_id,
                agent_definition_id=agent_id,
                user_request=user_request,
                parameters={
                    "builder_test_mode": True,
                    "agent_version_override": version,
                },
                requires_approval=False,
            ),
            actor_id=actor_id,
        )

        errors: list[str] = []
        if execution.error_metadata:
            message = execution.error_metadata.get("message")
            if isinstance(message, str):
                errors.append(message)

        test_record = self._tests.create(
            agent_definition_id=agent_id,
            agent_version=version,
            project_id=project_id,
            test_input={"user_request": user_request},
            result={
                "execution_id": str(execution.id),
                "execution_status": execution.execution_status.value,
                "output": execution.output,
                "validation_status": (
                    execution.validation_status.value if execution.validation_status else None
                ),
            },
            validation_status=(
                execution.validation_status.value if execution.validation_status else None
            ),
            errors=errors,
            execution_metadata={
                "prompt_generation": execution.prompt_generation,
                "traceability_metadata": execution.traceability_metadata,
            },
            created_by=actor_id,
        )

        record_agent_version_to_test(
            self._traceability,
            project_id=project_id,
            version_id=detail.version.id,
            test_id=test_record.id,
            metadata={"agent_version": version},
        )
        return test_record

    def request_publish(
        self,
        agent_id: UUID,
        version: int,
        *,
        project_id: UUID,
        actor_id: str,
    ) -> AgentBuilderPublicationRecord:
        definition = self._registry.get_agent(agent_id)
        self._ensure_project_scope(definition, project_id)
        detail = self._versions.get_version(agent_id, version)
        validation = self.validate_version(agent_id, version)
        if not validation.valid:
            raise AgentBuilderValidationFailedError(agent_id, version, validation)

        if detail.version.status != AgentVersionStatus.DRAFT:
            raise AgentBuilderInvalidStateError(
                "Only draft versions can be published.",
                details={"agent_id": str(agent_id), "version": version},
            )

        requires_approval = requires_approval_for_target(
            ApprovalTargetType.AGENT_ACTION,
            "agent.version.publish",
        )
        if not requires_approval:
            self._versions.activate_version(agent_id, version, created_by=actor_id)
            publication = self._publications.create(
                agent_definition_id=agent_id,
                agent_version=version,
                project_id=project_id,
                action=AgentBuilderAction.PUBLISH.value,
                status=AgentBuilderPublicationStatus.COMPLETED.value,
                metadata={"auto_activated": True},
                created_by=actor_id,
            )
            record_approval_to_agent_version(
                self._traceability,
                project_id=project_id,
                approval_id=publication.id,
                version_id=detail.version.id,
                metadata={"action": "publish", "auto_activated": True},
            )
            return publication

        approval = self._approval.create_request(
            project_id,
            requester=actor_id,
            target_type=ApprovalTargetType.AGENT_ACTION,
            target_action="agent.version.publish",
            summary=f"Publish assistant '{definition.name}' version {version}",
            target_object_type="agent_version",
            target_object_id=detail.version.id,
            metadata={
                "agent_definition_id": str(agent_id),
                "agent_version": version,
                "agent_name": definition.name,
            },
        )
        publication = self._publications.create(
            agent_definition_id=agent_id,
            agent_version=version,
            project_id=project_id,
            action=AgentBuilderAction.PUBLISH.value,
            status=AgentBuilderPublicationStatus.PENDING_APPROVAL.value,
            approval_request_id=approval.id,
            metadata={"validation": validation.model_dump(mode="json")},
            created_by=actor_id,
        )
        record_agent_version_to_approval(
            self._traceability,
            project_id=project_id,
            version_id=detail.version.id,
            approval_id=approval.id,
            metadata={"action": "publish"},
        )
        return publication

    def request_rollback(
        self,
        agent_id: UUID,
        *,
        target_version: int,
        project_id: UUID,
        actor_id: str,
    ) -> AgentBuilderPublicationRecord:
        definition = self._registry.get_agent(agent_id)
        self._ensure_project_scope(definition, project_id)
        detail = self._versions.get_version(agent_id, target_version)
        if detail.version.status not in {
            AgentVersionStatus.ARCHIVED,
            AgentVersionStatus.INACTIVE,
        }:
            raise AgentBuilderInvalidStateError(
                "Rollback target must be a previous inactive or archived version.",
                details={"agent_id": str(agent_id), "target_version": target_version},
            )

        approval = self._approval.create_request(
            project_id,
            requester=actor_id,
            target_type=ApprovalTargetType.AGENT_ACTION,
            target_action="agent.rollback",
            summary=f"Rollback assistant '{definition.name}' to version {target_version}",
            target_object_type="agent_version",
            target_object_id=detail.version.id,
            metadata={
                "agent_definition_id": str(agent_id),
                "target_version": target_version,
                "current_version": definition.current_version,
            },
        )
        return self._publications.create(
            agent_definition_id=agent_id,
            agent_version=target_version,
            project_id=project_id,
            action=AgentBuilderAction.ROLLBACK.value,
            status=AgentBuilderPublicationStatus.PENDING_APPROVAL.value,
            approval_request_id=approval.id,
            metadata={"current_version": definition.current_version},
            created_by=actor_id,
        )

    def deactivate_active_version(
        self,
        agent_id: UUID,
        *,
        project_id: UUID,
        actor_id: str,
    ) -> AgentDefinition:
        definition = self._registry.get_agent(agent_id)
        self._ensure_project_scope(definition, project_id)
        active = self._versions.get_active_version(agent_id)
        if active is None:
            raise AgentBuilderInvalidStateError(
                "Assistant has no active version to deactivate.",
                details={"agent_id": str(agent_id)},
            )

        self._versions.deactivate_version(agent_id, active.version.version)
        self._publications.create(
            agent_definition_id=agent_id,
            agent_version=active.version.version,
            project_id=project_id,
            action=AgentBuilderAction.DEACTIVATE.value,
            status=AgentBuilderPublicationStatus.COMPLETED.value,
            created_by=actor_id,
        )
        return self._registry.get_agent(agent_id)

    def list_publications(self, agent_id: UUID) -> list[AgentBuilderPublicationRecord]:
        self._registry.get_agent(agent_id)
        return self._publications.list_for_definition(agent_id)

    def list_tests(self, agent_id: UUID, version: int) -> list[AgentVersionTestRecord]:
        self._versions.get_version(agent_id, version)
        return self._tests.list_for_version(agent_id, version)

    def get_builder_detail(self, agent_id: UUID, version: int) -> AgentBuilderVersionDetail:
        definition = self._registry.get_agent(agent_id)
        detail = self._versions.get_version(agent_id, version)
        validation = self.validate_version(agent_id, version)
        return self._build_detail(definition, detail, validation)

    def _build_detail(
        self,
        definition: AgentDefinition,
        version_detail: AgentVersionDetail,
        validation: AgentBuilderValidationResult | None = None,
    ) -> AgentBuilderVersionDetail:
        if validation is None:
            validation = self.validate_version(definition.id, version_detail.version.version)
        return AgentBuilderVersionDetail(
            definition=definition,
            version=version_detail,
            validation=validation,
        )

    @staticmethod
    def _ensure_project_scope(definition: AgentDefinition, project_id: UUID) -> None:
        if definition.project_id is not None and definition.project_id != project_id:
            raise ProjectAgentScopeError(definition.id, project_id)
