"""Structured agent-run view derived from existing execution records.

This is not a competing persistence model. It maps AgentExecutionRecord,
attachment context, and AgentCapabilityCatalog data into chat-facing
lifecycle, progress, tool, and context metadata.
"""

from __future__ import annotations

from typing import Any

from app.application.agent_run_tool_payloads import (
    capability_label,
    capability_tool_payload,
    document_tool_payload,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRecord, AgentExecutionStatus
from app.domain.models.agent_runtime_view import build_agent_execution_user_view

AgentRunStepState = str
AgentRunLifecycle = str

_PROGRESS_TO_LIFECYCLE: dict[str, AgentRunLifecycle] = {
    "queued": "planning",
    "in_progress": "executing",
    "awaiting_approval": "waiting_for_approval",
    "blocked": "blocked",
    "completed": "completed",
    "failed": "failed",
    "rejected": "failed",
    "cancelled": "failed",
}

_EXECUTE_LABELS: dict[str, str] = {
    EngineeringAgentType.ANALYSIS_AGENT.value: "Running structural analysis",
    EngineeringAgentType.CONCRETE_DESIGN_AGENT.value: "Running concrete design",
    EngineeringAgentType.STEEL_DESIGN_AGENT.value: "Running steel design",
    EngineeringAgentType.CAD_AGENT.value: "Generating CAD deliverables",
    EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT.value: "Reading engineering documents",
    EngineeringAgentType.REPORTING_AGENT.value: "Preparing engineering report",
    EngineeringAgentType.VALIDATION_AGENT.value: "Checking code compliance",
    EngineeringAgentType.OPTIMIZATION_AGENT.value: "Running optimization",
    EngineeringAgentType.STRUCTURAL_MODELING_AGENT.value: "Inspecting structural model",
    EngineeringAgentType.LOAD_ASSESSMENT_AGENT.value: "Reviewing project loads",
    EngineeringAgentType.SEISMIC_AGENT.value: "Evaluating seismic parameters",
}

def build_agent_run_view(record: AgentExecutionRecord) -> dict[str, Any]:
    view = build_agent_execution_user_view(record)
    progress = view.progress
    lifecycle = _PROGRESS_TO_LIFECYCLE.get(progress, "executing")
    agent_type = _selected_agent_type(record)
    attachments = _attachment_entries(record)
    conversation_id = _conversation_id(record)
    steps = _build_steps(record, progress, agent_type, attachments)
    current_step = next(
        (step["key"] for step in steps if step["state"] in {"current", "error"}),
        steps[-1]["key"] if steps else "understand",
    )
    tools = _build_tools(record, progress, agent_type, attachments)
    context = {
        "conversation": conversation_id is not None,
        "project": record.project_id is not None,
        "project_id": str(record.project_id) if record.project_id else None,
        "conversation_id": conversation_id,
        "capability": capability_label(agent_type),
        "files": [
            {
                "filename": item["filename"],
                "file_type": item.get("file_type"),
                "availability": item.get("availability"),
            }
            for item in attachments
        ],
        "indexed_document_count": sum(
            1 for item in attachments if item.get("availability") == "indexed"
        ),
    }
    error = _safe_error(record, progress)
    return {
        "lifecycle": lifecycle,
        "current_step": current_step,
        "progress": progress,
        "selected_capability": capability_label(agent_type),
        "requires_approval": view.requires_approval,
        "steps": steps,
        "tools": tools,
        "context": context,
        "validation_status": record.validation_status.value if record.validation_status else None,
        "error": error,
    }


def chat_mode_to_agent_type(mode: str | None) -> EngineeringAgentType | None:
    """Map a lightweight composer mode to a catalog agent type.

    Design stays None so existing intent routing can choose concrete vs steel.
    Auto also stays None.
    """
    mapping = {
        "analyze": EngineeringAgentType.ANALYSIS_AGENT,
        "cad": EngineeringAgentType.CAD_AGENT,
        "documents": EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
        "reports": EngineeringAgentType.REPORTING_AGENT,
    }
    if not mode:
        return None
    return mapping.get(mode.strip().lower())


def _selected_agent_type(record: AgentExecutionRecord) -> str | None:
    if record.prompt_generation and isinstance(record.prompt_generation, dict):
        raw = record.prompt_generation.get("selected_agent_type")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    if isinstance(record.input_request, dict):
        raw = record.input_request.get("agent_type")
        if isinstance(raw, str) and raw.strip():
            return raw.strip()
    return None


def _conversation_id(record: AgentExecutionRecord) -> str | None:
    parameters = record.input_request.get("parameters") if isinstance(record.input_request, dict) else None
    if isinstance(parameters, dict):
        raw = parameters.get("conversation_id")
        if raw:
            return str(raw)
    return None


def _attachment_entries(record: AgentExecutionRecord) -> list[dict[str, Any]]:
    parameters = record.input_request.get("parameters") if isinstance(record.input_request, dict) else None
    bundle = None
    if isinstance(parameters, dict):
        bundle = parameters.get("attachment_context")
    if not isinstance(bundle, dict):
        bundle = record.context_snapshot.get("chat_attachments") if isinstance(record.context_snapshot, dict) else None
    if not isinstance(bundle, dict):
        return []
    raw_entries = bundle.get("attachments")
    if not isinstance(raw_entries, list):
        return []
    entries: list[dict[str, Any]] = []
    for item in raw_entries:
        if isinstance(item, dict) and item.get("filename"):
            entries.append(item)
    return entries


def _build_steps(
    record: AgentExecutionRecord,
    progress: str,
    agent_type: str | None,
    attachments: list[dict[str, Any]],
) -> list[dict[str, str]]:
    failed = progress in {"failed", "rejected", "cancelled"}
    completed = progress == "completed"
    awaiting = progress == "awaiting_approval"
    running = progress == "in_progress"
    queued = progress == "queued"
    blocked = progress == "blocked"

    steps: list[dict[str, str]] = [
        {"key": "understand", "label": "Understanding request", "state": "complete"},
        {
            "key": "project_context",
            "label": "Loading project context",
            "state": "complete" if record.project_id else "skipped",
        },
    ]
    if attachments:
        steps.append(
            {
                "key": "documents",
                "label": "Reading documents",
                "state": "error" if _attachments_failed(attachments) and failed else "complete",
            }
        )

    execute_state: AgentRunStepState = "pending"
    if queued:
        execute_state = "pending"
    elif running:
        execute_state = "current"
    elif awaiting or completed:
        execute_state = "complete"
    elif failed or blocked:
        execute_state = "error"
    steps.append(
        {
            "key": "execute",
            "label": _EXECUTE_LABELS.get(agent_type or "", "Running engineering workflow"),
            "state": execute_state,
        }
    )

    validate_state: AgentRunStepState = "pending"
    if completed or awaiting:
        validate_state = "complete"
    elif running:
        validate_state = "pending"
    elif failed or blocked:
        validate_state = "error"
    steps.append({"key": "validate", "label": "Validating results", "state": validate_state})

    if awaiting or record.approval_request_id is not None:
        approval_state: AgentRunStepState = "pending"
        if awaiting:
            approval_state = "current"
        elif completed:
            approval_state = "complete"
        elif failed:
            approval_state = "error"
        steps.append(
            {
                "key": "approval",
                "label": "Waiting for approval",
                "state": approval_state,
            }
        )

    response_state: AgentRunStepState = "pending"
    if completed:
        response_state = "complete"
    elif failed:
        response_state = "error"
    elif awaiting:
        response_state = "pending"
    steps.append({"key": "respond", "label": "Final response", "state": response_state})
    return [step for step in steps if step["state"] != "skipped"]


def _attachments_failed(attachments: list[dict[str, Any]]) -> bool:
    return any(item.get("availability") == "failed" for item in attachments)


def _build_tools(
    record: AgentExecutionRecord,
    progress: str,
    agent_type: str | None,
    attachments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    tools: list[dict[str, Any]] = []
    if attachments:
        document_status = "error" if _attachments_failed(attachments) else "complete"
        if progress == "in_progress" and document_status != "error":
            document_status = "current"
        tools.append(document_tool_payload(attachments, status=document_status))

    if agent_type:
        tool_status = "pending"
        if progress == "in_progress":
            tool_status = "current"
        elif progress in {"completed", "awaiting_approval"}:
            tool_status = "complete"
        elif progress in {"failed", "rejected", "cancelled", "blocked"}:
            tool_status = "error"
        error_message = None
        if tool_status == "error" and isinstance(record.error_metadata, dict):
            raw = record.error_metadata.get("message")
            if isinstance(raw, str) and raw.strip():
                error_message = raw
        tools.append(
            capability_tool_payload(
                agent_type=agent_type,
                status=tool_status,
                agent_result=record.agent_result,
                validation_status=record.validation_status.value if record.validation_status else None,
                error_message=error_message,
            )
        )
    return tools


def _safe_error(record: AgentExecutionRecord, progress: str) -> dict[str, str] | None:
    if progress not in {"failed", "rejected", "cancelled", "blocked"}:
        return None
    message = None
    if isinstance(record.error_metadata, dict):
        message = record.error_metadata.get("message") or record.error_metadata.get("rejection_reason")
    title = {
        "failed": "Engineering workflow failed",
        "rejected": "Request was rejected",
        "cancelled": "Request was cancelled",
        "blocked": "Additional input is required",
    }.get(progress, "Engineering workflow failed")
    reason = (
        str(message).strip()
        if isinstance(message, str) and message.strip()
        else "The agent could not complete this engineering step."
    )
    return {"title": title, "reason": reason}
