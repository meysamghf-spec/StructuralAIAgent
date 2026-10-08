"""Completes agent builder publications when linked approvals resolve."""

from __future__ import annotations

from uuid import UUID

from app.application.agent_registry_service import AgentRegistryService
from app.application.agent_version_service import AgentVersionService
from app.application.traceability_integration import record_approval_to_agent_version
from app.application.traceability_service import TraceabilityService
from app.domain.models.agent import AgentDefinitionStatus
from app.domain.models.agent_builder import AgentBuilderAction, AgentBuilderPublicationStatus
from app.domain.models.human_approval import ApprovalStatus, HumanApprovalRequest
from app.domain.repositories.agent_protocols import AgentBuilderPublicationRepository


class AgentBuilderApprovalCompletionService:
    def __init__(
        self,
        *,
        publication_repository: AgentBuilderPublicationRepository,
        version_service: AgentVersionService,
        traceability_service: TraceabilityService,
        registry_service: AgentRegistryService | None = None,
        definition_repository=None,
    ) -> None:
        self._publications = publication_repository
        self._versions = version_service
        self._traceability = traceability_service
        self._registry = registry_service
        self._definitions = definition_repository

    def handle_approval_resolved(
        self,
        project_id: UUID,
        request: HumanApprovalRequest,
    ) -> None:
        if request.target_object_type != "agent_version":
            return

        publication = self._publications.get_by_approval_request_id(request.id)
        if publication is None:
            return

        if request.status == ApprovalStatus.APPROVED:
            self._complete_publication(project_id, publication, request)
            return

        status = (
            AgentBuilderPublicationStatus.REJECTED.value
            if request.status == ApprovalStatus.REJECTED
            else AgentBuilderPublicationStatus.CANCELLED.value
        )
        self._publications.update_status(
            publication.id,
            status=status,
            metadata={"decision": request.status.value, "reason": request.rejection_reason},
        )

    def _complete_publication(
        self,
        project_id: UUID,
        publication,
        request: HumanApprovalRequest,
    ) -> None:
        agent_id = publication.agent_definition_id
        version = publication.agent_version

        if publication.action == AgentBuilderAction.PUBLISH.value:
            self._versions.record_publish_approval(
                agent_id,
                version,
                approval_request_id=request.id,
                approver=request.approver,
            )
            detail = self._versions.activate_version(agent_id, version)
            self._mark_enabled(agent_id)
            record_approval_to_agent_version(
                self._traceability,
                project_id=project_id,
                approval_id=request.id,
                version_id=detail.version.id,
                metadata={"action": "publish", "decision": "APPROVED"},
            )
        elif publication.action in {
            AgentBuilderAction.ROLLBACK.value,
            AgentBuilderAction.ENABLE.value,
        }:
            detail = self._versions.rollback_to_version(agent_id, version)
            self._mark_enabled(agent_id)
            record_approval_to_agent_version(
                self._traceability,
                project_id=project_id,
                approval_id=request.id,
                version_id=detail.version.id,
                metadata={"action": publication.action, "decision": "APPROVED"},
            )

        self._publications.update_status(
            publication.id,
            status=AgentBuilderPublicationStatus.COMPLETED.value,
            metadata={"decision": ApprovalStatus.APPROVED.value},
        )

    def _mark_enabled(self, agent_id: UUID) -> None:
        if self._registry is None or self._definitions is None:
            return
        definition = self._registry.get_agent(agent_id)
        configuration = dict(definition.configuration)
        configuration["enabled"] = True
        self._definitions.update(agent_id, configuration=configuration)
        if definition.status == AgentDefinitionStatus.DISABLED:
            self._definitions.update_status(agent_id, AgentDefinitionStatus.ACTIVE)
