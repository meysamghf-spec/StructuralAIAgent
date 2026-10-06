"""Completes agent executions when linked human approvals are resolved."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING
from uuid import UUID

from app.application.exceptions import AgentExecutionNotFoundError
from app.application.hybrid_orchestration_service import HybridOrchestrationService
from app.application.project_context_assembly_service import ProjectContextAssemblyService
from app.application.project_memory_service import ProjectMemoryService
from app.application.traceability_integration import (
    record_agent_result_to_approval,
    record_agent_result_to_report,
    record_approval_to_agent_result,
)
from app.application.traceability_service import TraceabilityService
from app.domain.models.agent import AgentDefinition
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionStatus,
    AgentValidationStatus,
    is_awaiting_human_approval,
)
from app.domain.models.agent_runtime_view import AGENT_EXECUTION_MEMORY_SOURCE_TYPE
from app.domain.models.engineering_task import EngineeringTask, EngineeringTaskStatus, EngineeringTaskStep
from app.domain.models.human_approval import (
    ApprovalStatus,
    ApprovalTargetType,
    HumanApprovalRequest,
)
from app.domain.models.orchestration import OrchestrationTask
from app.domain.models.project_memory import MemoryType
from app.domain.models.reporting import ReportType
from app.domain.repositories.agent_protocols import AgentDefinitionRepository, AgentExecutionRepository
from app.infrastructure.repositories.postgres_report_repository import PostgresReportRepository

if TYPE_CHECKING:
    from app.application.engineering_task_execution_service import WorkflowExecutionOutcome


class AgentApprovalCompletionService:
    def __init__(
        self,
        *,
        execution_repository: AgentExecutionRepository,
        orchestration_service: HybridOrchestrationService,
        memory_service: ProjectMemoryService,
        traceability_service: TraceabilityService,
        report_repository: PostgresReportRepository | None = None,
        definition_repository: AgentDefinitionRepository | None = None,
        context_service: ProjectContextAssemblyService | None = None,
    ) -> None:
        self._executions = execution_repository
        self._orchestration = orchestration_service
        self._memory = memory_service
        self._traceability = traceability_service
        self._reports = report_repository or PostgresReportRepository()
        self._definitions = definition_repository
        self._context = context_service

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

        engineering_task = self._load_engineering_task(execution)
        if (
            engineering_task is not None
            and engineering_task.status == EngineeringTaskStatus.WAITING_FOR_APPROVAL
            and engineering_task.paused_step_id is not None
            and self._definitions is not None
            and self._context is not None
        ):
            from app.application.service_factory import build_engineering_task_execution_service

            task_execution = build_engineering_task_execution_service()
            agent_definition = self._definitions.get_by_id(execution.agent_definition_id)
            if agent_definition is not None:
                context_snapshot = execution.context_snapshot
                if not isinstance(context_snapshot, dict):
                    context_snapshot = {}
                outcome = task_execution.resume_after_approval(
                    task=engineering_task,
                    project_id=project_id,
                    user_request=str(execution.input_request.get("user_request", "")),
                    context_snapshot=context_snapshot,
                    parameters=dict(execution.input_request.get("parameters") or {}),
                    agent_definition=agent_definition,
                    actor_id=request.approver or request.requester or execution.created_by,
                    execution_id=execution.id,
                )
                execution.agent_result = outcome.agent_result
                execution.output = outcome.agent_result.structured_output
                execution.traceability_metadata = {
                    **execution.traceability_metadata,
                    "engineering_task": outcome.task.model_dump(mode="json"),
                }
                if outcome.requires_approval:
                    execution.execution_status = AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
                    follow_up = self._ensure_follow_up_approval_request(
                        project_id=project_id,
                        execution=execution,
                        resolved_request=request,
                        outcome=outcome,
                        agent_definition=agent_definition,
                    )
                    execution.approval_request_id = follow_up.id
                    gate_history = list(
                        execution.traceability_metadata.get("approval_gate_history") or []
                    )
                    resolved_id = str(request.id)
                    if resolved_id not in gate_history:
                        gate_history.append(resolved_id)
                    follow_up_id = str(follow_up.id)
                    if follow_up_id not in gate_history:
                        gate_history.append(follow_up_id)
                    execution.traceability_metadata = {
                        **execution.traceability_metadata,
                        "approval_gate_history": gate_history,
                        "workflow_approval_step_id": outcome.approval_step_id,
                    }
                    return self._persist_and_notify_conversation(
                        execution,
                        reason="approval_follow_up",
                    )
                execution.execution_status = outcome.execution_status
                return self._finalize_approved_execution(project_id, execution, request)

        return self._finalize_approved_execution(project_id, execution, request)

    def _finalize_approved_execution(
        self,
        project_id: UUID,
        execution: AgentExecutionRecord,
        request: HumanApprovalRequest,
    ) -> AgentExecutionRecord:
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

        if execution.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL:
            execution.execution_status = AgentExecutionStatus.COMPLETED
        if execution.completed_at is None and execution.execution_status == AgentExecutionStatus.COMPLETED:
            execution.completed_at = datetime.now(UTC)
        execution.error_metadata = {}
        return self._persist_and_notify_conversation(execution, reason="approval_finalized")

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
        return self._persist_and_notify_conversation(execution, reason="approval_rejected")

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
        return self._persist_and_notify_conversation(execution, reason="approval_cancelled")

    def _persist_and_notify_conversation(
        self,
        execution: AgentExecutionRecord,
        *,
        reason: str,
    ) -> AgentExecutionRecord:
        updated = self._executions.update(execution)
        from app.application.conversation_service import append_execution_follow_up

        append_execution_follow_up(updated, reason=reason)
        return updated

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
    def _load_engineering_task(execution: AgentExecutionRecord) -> EngineeringTask | None:
        raw = execution.traceability_metadata.get("engineering_task")
        if not isinstance(raw, dict):
            return None
        return EngineeringTask.model_validate(raw)

    def _ensure_follow_up_approval_request(
        self,
        *,
        project_id: UUID,
        execution: AgentExecutionRecord,
        resolved_request: HumanApprovalRequest,
        outcome: WorkflowExecutionOutcome,
        agent_definition: AgentDefinition,
    ) -> HumanApprovalRequest:
        from app.application.service_factory import build_human_approval_service

        approval_service = build_human_approval_service()
        step_id = outcome.approval_step_id
        paused_step = self._find_workflow_step(outcome.task, step_id) if step_id else None
        step_title = paused_step.title if paused_step is not None else step_id or "workflow step"

        existing = self._find_pending_workflow_approval(
            approval_service=approval_service,
            project_id=project_id,
            execution_id=execution.id,
            workflow_step_id=step_id,
        )
        if existing is not None:
            return existing

        requester = (
            resolved_request.approver
            or resolved_request.requester
            or execution.created_by
            or "system"
        )
        approval = approval_service.create_request(
            project_id,
            requester=requester,
            target_type=ApprovalTargetType.AGENT_ACTION,
            target_action="agent.execute",
            summary=f"Approve workflow step: {step_title}",
            target_object_type="agent_execution",
            target_object_id=execution.id,
            metadata={
                "agent_definition_id": str(agent_definition.id),
                "agent_type": (
                    agent_definition.agent_type.value if agent_definition.agent_type else None
                ),
                "user_request": str(execution.input_request.get("user_request", "")),
                "workflow_step_id": step_id,
                "workflow_task_id": str(outcome.task.id),
                "prior_approval_request_id": str(resolved_request.id),
                "approval_gate": "multi_step_workflow",
            },
        )

        result_trace_id = self._result_trace_id(execution)
        if result_trace_id is not None:
            record_agent_result_to_approval(
                self._traceability,
                project_id=project_id,
                result_id=result_trace_id,
                approval_id=approval.id,
                metadata={
                    "workflow_step_id": step_id,
                    "approval_gate": "multi_step_workflow",
                },
            )
        return approval

    def _find_pending_workflow_approval(
        self,
        *,
        approval_service,
        project_id: UUID,
        execution_id: UUID,
        workflow_step_id: str | None,
    ) -> HumanApprovalRequest | None:
        if workflow_step_id is None:
            return None
        pending = approval_service.list_requests(project_id, status=ApprovalStatus.PENDING)
        for request in pending:
            if (
                request.target_object_type == "agent_execution"
                and request.target_object_id == execution_id
                and request.metadata.get("workflow_step_id") == workflow_step_id
            ):
                return request
        return None

    @staticmethod
    def _find_workflow_step(task: EngineeringTask, step_id: str | None) -> EngineeringTaskStep | None:
        if step_id is None:
            return None
        for step in task.steps:
            if step.step_id == step_id:
                return step
        return None

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
