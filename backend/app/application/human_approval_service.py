"""Human Approval Gate application service."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.application.exceptions import (
    ApprovalInvalidStateError,
    ApprovalNotFoundError,
    ProjectNotFoundError,
)
from app.application.project_memory_service import ProjectMemoryService
from app.application.traceability_integration import (
    record_approval_to_model,
    record_decision_to_approval,
    record_source_to_memory,
)
from app.application.traceability_service import TraceabilityService
from app.domain.approval_policy import requires_approval_for_target
from app.domain.models.human_approval import (
    APPROVAL_MEMORY_SOURCE_TYPE,
    ApprovalEvent,
    ApprovalEventType,
    ApprovalRequest,
    ApprovalStatus,
    ApprovalTargetType,
    HumanApprovalRequest,
)
from app.domain.models.project_memory import MemoryType, ProjectMemory
from app.domain.repositories.protocols import (
    HumanApprovalRepository,
    ProjectRepository,
)


class HumanApprovalService:
    def __init__(
        self,
        *,
        project_repository: ProjectRepository,
        approval_repository: HumanApprovalRepository,
        memory_service: ProjectMemoryService,
        traceability_service: TraceabilityService | None = None,
    ) -> None:
        self._projects = project_repository
        self._approvals = approval_repository
        self._memory = memory_service
        self._traceability = traceability_service

    def requires_approval(
        self,
        target_type: ApprovalTargetType,
        target_action: str,
    ) -> bool:
        return requires_approval_for_target(target_type, target_action)

    def create_request(
        self,
        project_id: UUID,
        *,
        requester: str,
        target_type: ApprovalTargetType,
        target_action: str,
        summary: str,
        target_object_type: str | None = None,
        target_object_id: UUID | None = None,
        metadata: dict | None = None,
    ) -> HumanApprovalRequest:
        self._ensure_project_exists(project_id)

        request = self._approvals.create_request(
            project_id,
            requester=requester,
            target_type=target_type,
            target_action=target_action,
            summary=summary,
            target_object_type=target_object_type,
            target_object_id=target_object_id,
            metadata=metadata,
        )

        self._approvals.create_event(
            project_id,
            request.id,
            event_type=ApprovalEventType.CREATED,
            actor=requester,
            metadata={
                "target_type": target_type.value,
                "target_action": target_action,
                "target_object_type": target_object_type,
                "target_object_id": str(target_object_id) if target_object_id else None,
            },
        )
        return request

    def get_request(
        self,
        project_id: UUID,
        request_id: UUID,
    ) -> HumanApprovalRequest:
        self._ensure_project_exists(project_id)
        request = self._approvals.get_request(project_id, request_id)
        if request is None:
            raise ApprovalNotFoundError(project_id, request_id)
        return request

    def list_requests(
        self,
        project_id: UUID,
        *,
        status: ApprovalStatus | None = None,
    ) -> list[HumanApprovalRequest]:
        self._ensure_project_exists(project_id)
        if status == ApprovalStatus.NOT_REQUIRED:
            return []
        return self._approvals.list_requests(project_id, status=status)

    def list_pending(self, project_id: UUID) -> list[HumanApprovalRequest]:
        return self.list_requests(project_id, status=ApprovalStatus.PENDING)

    def approve_request(
        self,
        project_id: UUID,
        request_id: UUID,
        *,
        approver: str,
        decision_note: str | None = None,
    ) -> HumanApprovalRequest:
        request = self._get_pending_request(project_id, request_id)
        resolved_at = datetime.now(UTC)

        updated = self._approvals.update_request(
            project_id,
            request_id,
            status=ApprovalStatus.APPROVED,
            approver=approver,
            decision=ApprovalStatus.APPROVED,
            resolved_at=resolved_at,
        )
        assert updated is not None

        self._approvals.create_event(
            project_id,
            request_id,
            event_type=ApprovalEventType.APPROVED,
            actor=approver,
            reason=decision_note,
            metadata={"target_action": request.target_action},
        )

        self._record_memory_for_decision(
            project_id=project_id,
            request=updated,
            memory_type=MemoryType.DECISION,
            content=self._approval_memory_content(updated, decision_note),
            created_by=approver,
        )
        return updated

    def reject_request(
        self,
        project_id: UUID,
        request_id: UUID,
        *,
        approver: str,
        rejection_reason: str,
    ) -> HumanApprovalRequest:
        request = self._get_pending_request(project_id, request_id)
        resolved_at = datetime.now(UTC)

        updated = self._approvals.update_request(
            project_id,
            request_id,
            status=ApprovalStatus.REJECTED,
            approver=approver,
            decision=ApprovalStatus.REJECTED,
            rejection_reason=rejection_reason,
            resolved_at=resolved_at,
        )
        assert updated is not None

        self._approvals.create_event(
            project_id,
            request_id,
            event_type=ApprovalEventType.REJECTED,
            actor=approver,
            reason=rejection_reason,
            metadata={"target_action": request.target_action},
        )

        self._record_memory_for_decision(
            project_id=project_id,
            request=updated,
            memory_type=MemoryType.REJECTION,
            content=self._rejection_memory_content(updated, rejection_reason),
            created_by=approver,
        )
        return updated

    def cancel_request(
        self,
        project_id: UUID,
        request_id: UUID,
        *,
        actor: str,
        reason: str | None = None,
    ) -> HumanApprovalRequest:
        request = self._get_pending_request(project_id, request_id)
        resolved_at = datetime.now(UTC)

        updated = self._approvals.update_request(
            project_id,
            request_id,
            status=ApprovalStatus.CANCELLED,
            approver=actor,
            decision=ApprovalStatus.CANCELLED,
            rejection_reason=reason,
            resolved_at=resolved_at,
        )
        assert updated is not None

        self._approvals.create_event(
            project_id,
            request_id,
            event_type=ApprovalEventType.CANCELLED,
            actor=actor,
            reason=reason,
            metadata={"target_action": request.target_action},
        )
        return updated

    def get_history(
        self,
        project_id: UUID,
        *,
        approval_request_id: UUID | None = None,
    ) -> list[ApprovalEvent]:
        self._ensure_project_exists(project_id)
        return self._approvals.list_events(
            project_id,
            approval_request_id=approval_request_id,
        )

    def to_protocol_request(self, request: HumanApprovalRequest) -> ApprovalRequest:
        return ApprovalRequest(
            request_id=request.id,
            task_type=f"{request.target_type.value}:{request.target_action}",
            summary=request.summary,
            context={
                "project_id": str(request.project_id),
                "target_object_type": request.target_object_type,
                "target_object_id": str(request.target_object_id)
                if request.target_object_id
                else None,
                **request.metadata,
            },
            status=request.status,
            requested_at=request.requested_at,
            resolved_at=request.resolved_at,
            resolved_by=request.approver,
        )

    def _get_pending_request(
        self,
        project_id: UUID,
        request_id: UUID,
    ) -> HumanApprovalRequest:
        request = self.get_request(project_id, request_id)
        if request.status != ApprovalStatus.PENDING:
            raise ApprovalInvalidStateError(
                project_id,
                request_id,
                current_status=request.status.value,
            )
        return request

    def _record_memory_for_decision(
        self,
        *,
        project_id: UUID,
        request: HumanApprovalRequest,
        memory_type: MemoryType,
        content: str,
        created_by: str,
    ) -> ProjectMemory:
        memory = self._memory.create_memory(
            project_id,
            memory_type,
            content,
            source_type=APPROVAL_MEMORY_SOURCE_TYPE,
            source_id=request.id,
            metadata={
                "target_type": request.target_type.value,
                "target_action": request.target_action,
                "target_object_type": request.target_object_type,
                "target_object_id": str(request.target_object_id)
                if request.target_object_id
                else None,
                "decision": request.decision.value if request.decision else None,
                "rejection_reason": request.rejection_reason,
            },
            created_by=created_by,
        )
        if self._traceability is not None:
            record_decision_to_approval(
                self._traceability,
                project_id=project_id,
                memory_id=memory.id,
                approval_id=request.id,
                metadata={"memory_type": memory_type.value},
            )
            if (
                request.target_object_type == "pem_snapshot"
                and request.target_object_id is not None
                and request.decision == ApprovalStatus.APPROVED
            ):
                record_approval_to_model(
                    self._traceability,
                    project_id=project_id,
                    approval_id=request.id,
                    model_id=request.target_object_id,
                    metadata={"target_action": request.target_action},
                )
        return memory

    @staticmethod
    def _approval_memory_content(
        request: HumanApprovalRequest,
        decision_note: str | None,
    ) -> str:
        note = f" Note: {decision_note}" if decision_note else ""
        return (
            f"Approved {request.target_type.value} action '{request.target_action}' "
            f"for {request.summary}.{note}"
        )

    @staticmethod
    def _rejection_memory_content(
        request: HumanApprovalRequest,
        rejection_reason: str,
    ) -> str:
        return (
            f"Rejected {request.target_type.value} action '{request.target_action}' "
            f"for {request.summary}. Reason: {rejection_reason}"
        )

    def _ensure_project_exists(self, project_id: UUID) -> None:
        if self._projects.get_by_id(project_id) is None:
            raise ProjectNotFoundError(project_id)
