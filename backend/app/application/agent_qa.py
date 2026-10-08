"""Decide the QA status recorded on an agent run.

A run is PASS only when a real check passed. Missing software, a model that is
not ready, a design that is waiting on analysis, and an unfinished workflow are
not checks, so they stay NOT_RUN. Confidence and a completed chat turn do not
create a pass.
"""

from __future__ import annotations

from typing import Any

from app.domain.models.agent_runtime import AgentValidationStatus

_NO_CHECK_CAPABILITIES = frozenset(
    {
        "MODEL_NOT_READY",
        "REQUIRES_SOLVER",
        "REQUIRES_ANALYSIS",
        "REQUIRES_LOCAL_SOFTWARE",
        "REQUIRES_EXTERNAL_SOLVER",
        "NOT_IMPLEMENTED",
        "NOT_AVAILABLE",
        "UNAVAILABLE",
        "PARTIALLY_COMPLETED",
        "BLOCKED",
        "WAITING_FOR_INPUT",
        "WAITING_FOR_APPROVAL",
        "NOT_CHECKED",
        "NOT_RUN",
    }
)


def resolve_agent_qa_status(
    *,
    validation_information: dict[str, Any] | None,
    structured_output: dict[str, Any] | None,
    confidence: float | None,
) -> AgentValidationStatus:
    info = validation_information if isinstance(validation_information, dict) else {}
    output = structured_output if isinstance(structured_output, dict) else {}

    if info.get("fabricated_results"):
        return AgentValidationStatus.ERROR

    orchestration_status = _upper(info.get("orchestration_status"))
    if orchestration_status in {"ERROR", "FAIL", "FAILED"}:
        return AgentValidationStatus.ERROR
    if orchestration_status in {"WARNING", "WARN"}:
        return AgentValidationStatus.WARNING

    validation_status = _upper(info.get("validation_status") or output.get("validation_status"))
    if validation_status in {"ERROR", "FAIL", "FAILED"}:
        return AgentValidationStatus.ERROR
    if validation_status in {"WARNING", "WARN", "REQUIRES_ENGINEER_REVIEW"}:
        return AgentValidationStatus.WARNING
    if validation_status == "PASS" and not _results_explicitly_unavailable(output):
        return AgentValidationStatus.PASS

    capability_status = _upper(info.get("capability_status") or output.get("capability_status"))
    if capability_status in {"ERROR", "FAIL", "FAILED"}:
        return AgentValidationStatus.ERROR
    if capability_status in {
        "WARNING",
        "WARN",
        "MISSING_REQUIRED_INPUT",
        "INVALID_INPUT",
        "UNSUPPORTED_CODE",
    }:
        return AgentValidationStatus.WARNING
    if capability_status in _NO_CHECK_CAPABILITIES or _results_explicitly_unavailable(output):
        return AgentValidationStatus.NOT_RUN
    if capability_status == "PASS" and _checked_results_available(output):
        return AgentValidationStatus.PASS

    if info.get("stub"):
        return AgentValidationStatus.REQUIRES_ENGINEER_REVIEW
    if confidence is not None and confidence < 0.5:
        return AgentValidationStatus.WARNING
    return AgentValidationStatus.NOT_RUN


def _results_explicitly_unavailable(output: dict[str, Any]) -> bool:
    analysis = output.get("engineering_results_available")
    design = output.get("engineering_design_results_available")
    if analysis is True or design is True:
        return False
    return analysis is False or design is False


def _checked_results_available(output: dict[str, Any]) -> bool:
    return (
        output.get("engineering_results_available") is True
        or output.get("engineering_design_results_available") is True
    )


def _upper(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip().upper()
