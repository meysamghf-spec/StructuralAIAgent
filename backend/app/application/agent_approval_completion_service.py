"""Completes agent executions when linked human approvals are resolved."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from app.application.exceptions import AgentExecutionNotFoundError
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.project_memory_service import ProjectMemoryService
from app.application.traceability_integration import (
    record_agent_result_to_report,
    record_approval_to_agent_result,
)
from app.application.traceability_service import TraceabilityService
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionStatus,
    AgentValidationStatus,
    is_awaiting_human_approval,
)
from app.domain.models.agent_runtime_view import AGENT_EXECUTION_MEMORY_SOURCE_TYPE
from app.domain.models.human_approval import ApprovalStatus, HumanApprovalRequest
from app.domain.models.orchestration import OrchestrationTask
from app.domain.models.project_memory import MemoryType
from app.domain.models.reporting import ReportType
from app.domain.repositories.agent_protocols import AgentExecutionRepository
from app.infrastructure.repositories.postgres_report_repository import PostgresReportRepository


class AgentApprovalCompletionService:
    def __init__(
        self,
        *,
        execution_repository: AgentExecutionRepository,
        orchestration_service: HybridOrchestrationService,
        memory_service: ProjectMemoryService,
        traceability_service: TraceabilityService,
        report_repository: PostgresReportRepository | None = None,
    ) -> None:
        self._executions = execution_repository
        self._orchestration = orchestration_service
        self._memory = memory_service
        self._traceability = traceability_service
        self._reports = report_repository or PostgresReportRepository()

    def handle_approval_resolved(
        self,
        project_id: UUID,
        request: HumanApprovalRequest,
    ) -> AgentExecutionRecord | None:
        if request.target_object_type != "agent_execution":
            return None

        execution = self._resolve_execution(request)
        if execution is None:
            return None

        if request.status == ApprovalStatus.APPROVED:
            return self._complete_after_approval(project_id, execution, request)
        if request.status == ApprovalStatus.REJECTED:
            return self._complete_after_rejection(
                project_id,
                execution,
                request,
                rejection_reason=request.rejection_reason or "Rejected by approver",
            )
        if request.status == ApprovalStatus.CANCELLED:
            return self._complete_after_cancellation(
                project_id,
                execution,
                request,
                reason=request.rejection_reason or "Approval cancelled",
            )
        return execution

    def _complete_after_approval(
        self,
        project_id: UUID,
        execution: AgentExecutionRecord,
        request: HumanApprovalRequest,
    ) -> AgentExecutionRecord:
        if not is_awaiting_human_approval(execution.execution_status):
            return execution

        orchestration_output = self._run_post_approval_orchestration(project_id)
        result_trace_id = self._result_trace_id(execution)

        if orchestration_output is not None:
            execution.traceability_metadata["orchestration"] = orchestration_output
            execution.validation_status = self._map_orchestration_validation(orchestration_output)

        if result_trace_id is not None:
            record_approval_to_agent_result(
                self._traceability,
                project_id=project_id,
                approval_id=request.id,
                result_id=result_trace_id,
                metadata={"decision": ApprovalStatus.APPROVED.value},
            )

        report = self._reports.create_report(
            project_id,
            report_type=ReportType.DECISION_HISTORY,
            title="Agent Execution Decision History",
            metadata={
                "agent_execution_id": str(execution.id),
                "approval_request_id": str(request.id),
                "integration_point": True,
            },
            created_by=request.approver,
        )
        execution.traceability_metadata["report_id"] = str(report.id)

        if result_trace_id is not None:
            record_agent_result_to_report(
                self._traceability,
                project_id=project_id,
                result_id=result_trace_id,
                report_id=report.id,
                metadata={"report_type": ReportType.DECISION_HISTORY.value},
            )

        self._memory.create_memory(
            project_id,
            MemoryType.DECISION,
            self._approved_result_memory_content(execution, request),
            source_type=AGENT_EXECUTION_MEMORY_SOURCE_TYPE,
            source_id=execution.id,
            metadata={
                "approval_request_id": str(request.id),
                "agent_execution_id": str(execution.id),
                "report_id": str(report.id),
            },
            created_by=request.approver or request.requester,
        )

        execution.execution_status = AgentExecutionStatus.COMPLETED
        execution.completed_at = datetime.now(UTC)
        execution.error_metadata = {}
        return self._executions.update(execution)

    def _complete_after_rejection(
        self,
        project_id: UUID,
        execution: AgentExecutionRecord,
        request: HumanApprovalRequest,
        *,
        rejection_reason: str,
    ) -> AgentExecutionRecord:
        if not is_awaiting_human_approval(execution.execution_status):
            return execution

        result_trace_id = self._result_trace_id(execution)
        if result_trace_id is not None:
            record_approval_to_agent_result(
                self._traceability,
                project_id=project_id,
                approval_id=request.id,
                result_id=result_trace_id,
                metadata={
                    "decision": ApprovalStatus.REJECTED.value,
                    "rejection_reason": rejection_reason,
                },
            )

        self._memory.create_memory(
            project_id,
            MemoryType.REJECTION,
            self._rejected_result_memory_content(execution, rejection_reason),
            source_type=AGENT_EXECUTION_MEMORY_SOURCE_TYPE,
            source_id=execution.id,
            metadata={
                "approval_request_id": str(request.id),
                "agent_execution_id": str(execution.id),
                "rejection_reason": rejection_reason,
            },
            created_by=request.approver or request.requester,
        )

        execution.execution_status = AgentExecutionStatus.CANCELLED
        execution.completed_at = datetime.now(UTC)
        execution.error_metadata = {
            "approval_decision": "REJECTED",
            "rejection_reason": rejection_reason,
            "approval_request_id": str(request.id),
        }
        return self._executions.update(execution)

    def _complete_after_cancellation(
        self,
        project_id: UUID,
        execution: AgentExecutionRecord,
        request: HumanApprovalRequest,
        *,
        reason: str,
    ) -> AgentExecutionRecord:
        if not is_awaiting_human_approval(execution.execution_status):
            return execution

        execution.execution_status = AgentExecutionStatus.CANCELLED
        execution.completed_at = datetime.now(UTC)
        execution.error_metadata = {
            "approval_decision": "CANCELLED",
            "message": reason,
            "approval_request_id": str(request.id),
        }
        return self._executions.update(execution)

    def _resolve_execution(self, request: HumanApprovalRequest) -> AgentExecutionRecord | None:
        execution = self._executions.get_by_approval_request_id(request.id)
        if execution is not None:
            return execution
        if request.target_object_id is None:
            return None
        execution = self._executions.get_by_id(request.target_object_id)
        if execution is None:
            raise AgentExecutionNotFoundError(request.target_object_id)
        return execution

    def _run_post_approval_orchestration(self, project_id: UUID) -> dict | None:
        result = self._orchestration.execute(
            OrchestrationTask(
                task_type="project.validate",
                project_id=project_id,
                payload={},
            )
        )
        return result.model_dump(mode="json")

    @staticmethod
    def _map_orchestration_validation(orchestration_output: dict) -> AgentValidationStatus:
        status = str(orchestration_output.get("status", "")).upper()
        if status in {"PASS", "SUCCESS", "OK"}:
            return AgentValidationStatus.PASS
        if status in {"WARNING", "WARN"}:
            return AgentValidationStatus.WARNING
        if status in {"ERROR", "FAIL", "FAILED"}:
            return AgentValidationStatus.ERROR
        return AgentValidationStatus.REQUIRES_ENGINEER_REVIEW

    @staticmethod
    def _result_trace_id(execution: AgentExecutionRecord) -> UUID | None:
        raw = execution.traceability_metadata.get("result_trace_id")
        if raw is None:
            return None
        return UUID(str(raw))

    @staticmethod
    def _approved_result_memory_content(
        execution: AgentExecutionRecord,
        request: HumanApprovalRequest,
    ) -> str:
        user_request = execution.input_request.get("user_request", "Agent task")
        note = f" Approver note: {request.metadata.get('decision_note')}" if request.metadata else ""
        return f"Agent execution approved and finalized for '{user_request}'.{note}"

    @staticmethod
    def _rejected_result_memory_content(
        execution: AgentExecutionRecord,
        rejection_reason: str,
    ) -> str:
        user_request = execution.input_request.get("user_request", "Agent task")
        return (
            f"Agent execution rejected for '{user_request}'. "
            f"Reason: {rejection_reason}"
        )
