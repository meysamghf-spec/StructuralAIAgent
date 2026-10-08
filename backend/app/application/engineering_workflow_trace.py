"""Copy real calculation identifiers from an agent result onto the run record.

These values come from the existing analysis, design, and result services.
Missing identifiers stay absent. A capability status such as MODEL_NOT_READY
is recorded as that status and is not treated as a completed calculation.
"""

from __future__ import annotations

from typing import Any

_WORKFLOW_KEYS = (
    "analysis_run_id",
    "design_run_id",
    "optimization_run_id",
    "result_set_id",
    "result_validation_status",
    "capability_status",
    "engineering_results_available",
    "engineering_design_results_available",
    "code_edition",
)


def engineering_workflow_trace(output: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(output, dict):
        return {}
    traced: dict[str, Any] = {}
    for key in _WORKFLOW_KEYS:
        value = output.get(key)
        if value is None or value == "":
            continue
        traced[key] = value
    return traced
