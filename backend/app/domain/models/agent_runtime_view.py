"""User-facing agent execution view — hides runtime internals."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel

from app.domain.models.agent_runtime import AgentExecutionRecord, AgentExecutionStatus

AGENT_EXECUTION_MEMORY_SOURCE_TYPE = "agent_execution"


class AgentExecutionUserView(BaseModel):
    progress: str
    requires_approval: bool
    approval_request_id: UUID | None = None
    final_result: str | None = None
    summary: str | None = None


def build_agent_execution_user_view(record: AgentExecutionRecord) -> AgentExecutionUserView:
    progress = _resolve_progress(record)
    requires_approval = record.execution_status == AgentExecutionStatus.WAITING_APPROVAL
    final_result = _resolve_final_result(record)
    summary = _resolve_summary(record)

    return AgentExecutionUserView(
        progress=progress,
        requires_approval=requires_approval,
        approval_request_id=record.approval_request_id,
        final_result=final_result,
        summary=summary,
    )


def _resolve_progress(record: AgentExecutionRecord) -> str:
    if record.execution_status == AgentExecutionStatus.CREATED:
        return "starting"
    if record.execution_status == AgentExecutionStatus.RUNNING:
        return "in_progress"
    if record.execution_status == AgentExecutionStatus.WAITING_APPROVAL:
        return "awaiting_approval"
    if record.execution_status == AgentExecutionStatus.COMPLETED:
        return "completed"
    if record.execution_status == AgentExecutionStatus.FAILED:
        return "failed"
    if record.execution_status == AgentExecutionStatus.CANCELLED:
        if record.error_metadata.get("approval_decision") == "REJECTED":
            return "rejected"
        return "cancelled"
    return "in_progress"


def _resolve_final_result(record: AgentExecutionRecord) -> str | None:
    if record.execution_status == AgentExecutionStatus.WAITING_APPROVAL:
        return "Awaiting engineer approval before results are finalized."
    if record.execution_status == AgentExecutionStatus.CANCELLED:
        reason = record.error_metadata.get("rejection_reason")
        if reason:
            return f"Rejected: {reason}"
        return record.error_metadata.get("message")
    if record.execution_status == AgentExecutionStatus.FAILED:
        return record.error_metadata.get("message", "Execution failed.")
    if record.execution_status != AgentExecutionStatus.COMPLETED:
        return None

    if record.agent_result and record.agent_result.recommendations:
        return record.agent_result.recommendations[0]
    if record.output and record.output.get("status"):
        return f"Completed with status {record.output['status']}."
    return "Completed successfully."


def _resolve_summary(record: AgentExecutionRecord) -> str | None:
    user_request = record.input_request.get("user_request")
    if isinstance(user_request, str) and user_request.strip():
        return user_request.strip()
    return None
