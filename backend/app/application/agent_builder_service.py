"""Agent Builder — create, configure, test, publish, and rollback assistants."""

from __future__ import annotations

import copy
from dataclasses import dataclass
from uuid import UUID, uuid4

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
    AgentProductLifecycle,
    AgentVersionTestRecord,
    resolve_product_lifecycle,
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
    lifecycle: AgentProductLifecycle = AgentProductLifecycle.DRAFT


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
        purpose: str | None = None,
        engineering_domain: str | None = None,
        task_types: list[str] | None = None,
        element_types: list[str] | None = None,
        supported_codes: list[str] | None = None,
        input_contract: dict | None = None,
        output_contract: dict | None = None,
        allowed_tools: list[str] | None = None,
        change_summary: str | None = None,
    ) -> AgentBuilderVersionDetail:
        identity = dict(configuration or {})
        identity.setdefault("enabled", True)
        if purpose is not None:
            identity["purpose"] = purpose
        if engineering_domain is not None:
            identity["engineering_domain"] = engineering_domain
        elif agent_type is not None:
            identity.setdefault("engineering_domain", agent_type.value)
        definition = self._registry.create_agent(
            key=key,
            name=name,
            description=description,
            agent_type=agent_type,
            configuration=identity,
            project_id=project_id,
        )
        version_detail = self._versions.create_version(
            definition.id,
            instructions=instructions,
            configuration_metadata={
                "allowed_tools": list(allowed_tools or []),
                "model_configuration": {},
                "task_types": list(task_types or []),
                "element_types": list(element_types or []),
                "supported_codes": list(supported_codes or []),
                "input_contract": dict(input_contract or {}),
                "output_contract": dict(output_contract or {}),
                "change_summary": change_summary or "Initial draft",
            },
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
        purpose: str | None = None,
        engineering_domain: str | None = None,
    ) -> AgentDefinition:
        definition = self._registry.get_agent(agent_id)
        if definition.status == AgentDefinitionStatus.ARCHIVED:
            raise InvalidLifecycleTransitionError(
                "Archived assistants cannot be configured.",
                details={"agent_id": str(agent_id)},
            )
        merged = dict(definition.configuration)
        if configuration is not None:
            merged.update(configuration)
        if purpose is not None:
            merged["purpose"] = purpose
        if engineering_domain is not None:
            merged["engineering_domain"] = engineering_domain
        updated = self._definitions.update(
            agent_id,
            name=name,
            description=description,
            agent_type=agent_type,
            configuration=merged,
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
        self._reject_archived(definition)
        agent_version = self._versions.get_version(agent_id, version)
        if agent_version.version.status != AgentVersionStatus.DRAFT:
            raise AgentVersionImmutableError(agent_id, version)

        if configuration_metadata is not None:
            merged_metadata = dict(agent_version.version.configuration_metadata)
            merged_metadata.update(copy.deepcopy(configuration_metadata))
            configuration_metadata = merged_metadata

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
        self._reject_archived(definition)
        self._reject_disabled(definition)
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
            account_id=actor_id,
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
        self._reject_archived(definition)
        self._reject_disabled(definition)
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

        if not requires_approval_for_target(
            ApprovalTargetType.AGENT_ACTION,
            "agent.version.publish",
        ):
            raise AgentBuilderInvalidStateError(
                "Publishing an assistant requires the approval workflow.",
                details={"agent_id": str(agent_id), "version": version},
            )

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
        self._reject_archived(definition)
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

    def create_successor_version(
        self,
        agent_id: UUID,
        source_version: int,
        *,
        change_summary: str,
        created_by: str | None = None,
        instructions: str | None = None,
    ) -> AgentBuilderVersionDetail:
        definition = self._registry.get_agent(agent_id)
        self._reject_archived(definition)
        if not change_summary.strip():
            raise AgentBuilderInvalidStateError(
                "A change summary is required for a new assistant version.",
                details={"agent_id": str(agent_id)},
            )
        source = self._versions.get_version(agent_id, source_version)
        metadata = copy.deepcopy(source.version.configuration_metadata)
        metadata.pop("approval", None)
        metadata["change_summary"] = change_summary.strip()
        capability_keys = [capability.key for capability in source.capabilities]
        created = self._versions.create_version(
            agent_id,
            instructions=instructions if instructions is not None else source.version.instructions,
            configuration_metadata=metadata,
            capability_keys=capability_keys,
            created_by=created_by,
        )
        return self._build_detail(definition, created)

    def duplicate_agent(
        self,
        agent_id: UUID,
        *,
        project_id: UUID,
        actor_id: str,
        name: str | None = None,
        key: str | None = None,
    ) -> AgentBuilderVersionDetail:
        definition = self._registry.get_agent(agent_id)
        self._ensure_project_scope(definition, project_id)
        source_version_number = definition.current_version or 1
        source = self._versions.get_version(agent_id, source_version_number)
        identity = copy.deepcopy(definition.configuration)
        identity["enabled"] = True
        identity.pop("approval", None)
        identity["duplicated_from_agent_id"] = str(definition.id)
        metadata = copy.deepcopy(source.version.configuration_metadata)
        metadata.pop("approval", None)
        metadata["change_summary"] = f"Duplicated from {definition.name} version {source_version_number}"
        duplicate_key = (key or f"{definition.key}-copy-{uuid4().hex[:8]}")[:128]
        duplicate_name = name or f"{definition.name} copy"
        created = self.create_agent(
            key=duplicate_key,
            name=duplicate_name,
            description=definition.description,
            agent_type=definition.agent_type,
            configuration=identity,
            project_id=definition.project_id or project_id,
            instructions=source.version.instructions,
            capability_keys=[capability.key for capability in source.capabilities],
            created_by=actor_id,
            purpose=identity.get("purpose") if isinstance(identity.get("purpose"), str) else None,
            engineering_domain=(
                identity.get("engineering_domain")
                if isinstance(identity.get("engineering_domain"), str)
                else None
            ),
            task_types=_string_list(metadata.get("task_types")),
            element_types=_string_list(metadata.get("element_types")),
            supported_codes=_string_list(metadata.get("supported_codes")),
            input_contract=metadata.get("input_contract") if isinstance(metadata.get("input_contract"), dict) else {},
            output_contract=metadata.get("output_contract") if isinstance(metadata.get("output_contract"), dict) else {},
            allowed_tools=_string_list(metadata.get("allowed_tools")),
            change_summary=str(metadata.get("change_summary") or "Duplicated draft"),
        )
        return created

    def disable_agent(
        self,
        agent_id: UUID,
        *,
        project_id: UUID,
        actor_id: str,
    ) -> AgentDefinition:
        definition = self._registry.get_agent(agent_id)
        self._ensure_project_scope(definition, project_id)
        self._reject_archived(definition)
        active = self._versions.get_active_version(agent_id)
        disabled_version = active.version.version if active is not None else (definition.current_version or 1)
        if active is not None:
            self._versions.deactivate_version(agent_id, active.version.version)
        self._set_enabled(agent_id, enabled=False, status=AgentDefinitionStatus.DISABLED)
        self._publications.create(
            agent_definition_id=agent_id,
            agent_version=disabled_version,
            project_id=project_id,
            action=AgentBuilderAction.DISABLE.value,
            status=AgentBuilderPublicationStatus.COMPLETED.value,
            metadata={"historical_runs_retained": True},
            created_by=actor_id,
        )
        return self._registry.get_agent(agent_id)

    def request_enable(
        self,
        agent_id: UUID,
        *,
        target_version: int,
        project_id: UUID,
        actor_id: str,
    ) -> AgentBuilderPublicationRecord:
        definition = self._registry.get_agent(agent_id)
        self._ensure_project_scope(definition, project_id)
        self._reject_archived(definition)
        detail = self._versions.get_version(agent_id, target_version)
        if detail.version.status not in {AgentVersionStatus.INACTIVE, AgentVersionStatus.ARCHIVED}:
            raise AgentBuilderInvalidStateError(
                "Enable must restore a previously approved version.",
                details={"agent_id": str(agent_id), "target_version": target_version},
            )
        approval = self._approval.create_request(
            project_id,
            requester=actor_id,
            target_type=ApprovalTargetType.AGENT_ACTION,
            target_action="agent.rollback",
            summary=f"Enable assistant '{definition.name}' at version {target_version}",
            target_object_type="agent_version",
            target_object_id=detail.version.id,
            metadata={
                "agent_definition_id": str(agent_id),
                "target_version": target_version,
            },
        )
        return self._publications.create(
            agent_definition_id=agent_id,
            agent_version=target_version,
            project_id=project_id,
            action=AgentBuilderAction.ENABLE.value,
            status=AgentBuilderPublicationStatus.PENDING_APPROVAL.value,
            approval_request_id=approval.id,
            created_by=actor_id,
        )

    def archive_agent(self, agent_id: UUID) -> AgentDefinition:
        return self._registry.archive_agent(agent_id)

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
        publications = self._publications.list_for_definition(definition.id)
        publication_status = None
        for publication in publications:
            if (
                publication.agent_version == version_detail.version.version
                and publication.action == AgentBuilderAction.PUBLISH.value
            ):
                publication_status = publication.status
                break
        approval = (version_detail.version.configuration_metadata or {}).get("approval") or {}
        approval_status = approval.get("status") if isinstance(approval, dict) else None
        lifecycle = resolve_product_lifecycle(
            version_detail.version.status.value,
            publication_status=publication_status,
            approval_status=approval_status if isinstance(approval_status, str) else None,
        )
        return AgentBuilderVersionDetail(
            definition=definition,
            version=version_detail,
            validation=validation,
            lifecycle=lifecycle,
        )

    def _set_enabled(
        self,
        agent_id: UUID,
        *,
        enabled: bool,
        status: AgentDefinitionStatus,
    ) -> None:
        definition = self._registry.get_agent(agent_id)
        configuration = dict(definition.configuration)
        configuration["enabled"] = enabled
        self._definitions.update(agent_id, configuration=configuration)
        self._definitions.update_status(agent_id, status)

    @staticmethod
    def _reject_archived(definition: AgentDefinition) -> None:
        if definition.status == AgentDefinitionStatus.ARCHIVED:
            raise InvalidLifecycleTransitionError(
                "Archived assistants cannot be changed.",
                details={"agent_id": str(definition.id)},
            )

    @staticmethod
    def _reject_disabled(definition: AgentDefinition) -> None:
        if definition.status == AgentDefinitionStatus.DISABLED or definition.configuration.get("enabled") is False:
            raise AgentBuilderInvalidStateError(
                "This assistant is disabled and cannot start new work.",
                details={"agent_id": str(definition.id)},
            )

    @staticmethod
    def _ensure_project_scope(definition: AgentDefinition, project_id: UUID) -> None:
        if definition.project_id is not None and definition.project_id != project_id:
            raise ProjectAgentScopeError(definition.id, project_id)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str)]
