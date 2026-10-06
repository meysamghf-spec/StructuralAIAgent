"""User-friendly agent output helpers."""

from __future__ import annotations

from typing import Any


VALIDATION_LABELS = {
    "VALIDATED": "Results validated",
    "INVALID": "Results invalid",
    "INCOMPLETE": "Results incomplete",
    "PARTIALLY_VALIDATED": "Some results need engineering review",
    "REQUIRES_ENGINEER_REVIEW": "Engineering review required",
    "REQUIRES_LOCAL_SOFTWARE": "Local software required",
}

CAPABILITY_LABELS = {
    "REQUIRES_SOLVER": "Connect a structural solver to continue",
    "REQUIRES_ANALYSIS": "Run analysis before continuing",
    "REQUIRES_LOCAL_SOFTWARE": "Required software is not available on this computer",
    "MODEL_NOT_READY": "Complete the engineering model first",
    "NOT_IMPLEMENTED": "This capability is not available yet",
    "DEMO_COMPLETED": "Demo calculation completed",
    "PASS": "Completed successfully",
    "SUCCESS": "Completed successfully",
}


def validation_label(status: str | None) -> str:
    if not status:
        return "Validation status unavailable"
    return VALIDATION_LABELS.get(status, status.replace("_", " ").lower())


def capability_label(status: str | None) -> str:
    if not status:
        return "Status unavailable"
    return CAPABILITY_LABELS.get(status, status.replace("_", " ").lower())


def analysis_user_summary(
    *,
    capability_status: str,
    message: str,
    result_set_id: str | None,
    validation_status: str | None,
) -> str:
    if result_set_id and validation_status == "VALIDATED":
        return f"Analysis completed with validated engineering results. {message}"
    if capability_status in {"REQUIRES_LOCAL_SOFTWARE", "REQUIRES_SOLVER", "NOT_INSTALLED"}:
        return (
            "Analysis could not produce validated engineering results because the solver "
            "is not available on this computer."
        )
    return message


def design_user_summary(
    *,
    capability_status: str,
    message: str,
    result_set_id: str | None,
    design_available: bool,
) -> str:
    if design_available:
        return f"Design checks completed using validated analysis results. {message}"
    if not result_set_id:
        return "Design needs validated analysis results before code checks can run."
    return capability_label(capability_status)


def optimization_user_summary(*, capability_status: str, message: str, selected: dict | None) -> str:
    if selected:
        return (
            f"Optimization selected section '{selected.get('section_name')}' "
            f"with utilization {selected.get('utilization')}."
        )
    return capability_label(capability_status) if capability_status != "PASS" else message
