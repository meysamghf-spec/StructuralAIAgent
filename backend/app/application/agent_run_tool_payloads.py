"""Safe, real tool payloads for agent_run.tool events and agent_run views.

Built only from attachment context and AgentResult fields that already exist.
Does not invent counts, page numbers, or engineering results.
"""

from __future__ import annotations

from typing import Any

from app.application.agent_capability_catalog import get_agent_capability_profile
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentResult

TOOL_TITLES: dict[str, str] = {
    EngineeringAgentType.ANALYSIS_AGENT.value: "Structural Analysis",
    EngineeringAgentType.CONCRETE_DESIGN_AGENT.value: "Concrete Design",
    EngineeringAgentType.STEEL_DESIGN_AGENT.value: "Steel Design",
    EngineeringAgentType.CAD_AGENT.value: "CAD Generation",
    EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT.value: "Document Analysis",
    EngineeringAgentType.REPORTING_AGENT.value: "Report Generation",
    EngineeringAgentType.VALIDATION_AGENT.value: "Result Validation",
    EngineeringAgentType.OPTIMIZATION_AGENT.value: "Optimization",
    EngineeringAgentType.STRUCTURAL_MODELING_AGENT.value: "Model Inspection",
    EngineeringAgentType.LOAD_ASSESSMENT_AGENT.value: "Load Assessment",
    EngineeringAgentType.SEISMIC_AGENT.value: "Seismic Review",
}

_DOCUMENT_OPERATION_ORDER = (
    "DOCUMENT_DISCOVERED",
    "DOCUMENT_INDEXED",
    "DOCUMENT_READ",
    "DOCUMENT_SEARCHED",
)

_DOCUMENT_DETAIL_PREFIXES: dict[str, tuple[str, ...]] = {
    "DOCUMENT_DISCOVERED": ("file:", "pages:"),
    "DOCUMENT_INDEXED": ("file:", "pages:", "indexed:"),
    "DOCUMENT_READ": ("file:", "pages:", "indexed:", "read:"),
    "DOCUMENT_SEARCHED": ("file:", "pages:", "indexed:", "read:", "search:"),
}

_SENSITIVE_KEYS = {
    "password",
    "secret",
    "token",
    "api_key",
    "authorization",
    "connection_string",
    "database_url",
    "file_path",
    "path",
    "storage_path",
    "absolute_path",
}

_SAFE_ARTIFACT_KEYS = {
    "id",
    "type",
    "artifact_type",
    "name",
    "description",
    "file_id",
    "report_id",
    "drawing_id",
    "drawing_type",
    "format",
    "report_type",
    "version",
}

_WORKSPACE_ACTIONS: dict[str, dict[str, str]] = {
    "DOCUMENT_READ": {"label": "View context", "href": "/workspace/files"},
    "ANALYSIS_AGENT": {"label": "View analysis", "href": "/workspace/analysis"},
    "CONCRETE_DESIGN_AGENT": {"label": "View design", "href": "/workspace/design"},
    "STEEL_DESIGN_AGENT": {"label": "View design", "href": "/workspace/design"},
    "CAD_AGENT": {"label": "View CAD", "href": "/workspace/cad"},
    "REPORTING_AGENT": {"label": "View report", "href": "/workspace/reports"},
    "VALIDATION_AGENT": {"label": "View validation", "href": "/workspace/validation"},
    "DOCUMENT_INTERPRETATION_AGENT": {"label": "View context", "href": "/workspace/files"},
}


def document_tool_payload(
    attachments: list[dict[str, Any]],
    *,
    status: str,
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    details: list[dict[str, str]] = []
    operations: list[str] = []
    relevant_sections = 0
    failed = False

    for item in attachments:
        if not isinstance(item, dict) or not item.get("filename"):
            continue
        filename = str(item["filename"])
        availability = str(item.get("availability") or "stored_only")
        file_failed = availability == "failed"
        failed = failed or file_failed
        state = "error" if file_failed else "complete"
        page_count = _page_count(item)
        file_entry: dict[str, Any] = {
            "filename": filename,
            "file_type": item.get("file_type") if isinstance(item.get("file_type"), str) else None,
            "availability": availability,
            "page_count": page_count,
        }
        file_id = item.get("file_id")
        if isinstance(file_id, str) and file_id and "/" not in file_id and "\\" not in file_id:
            file_entry["file_id"] = file_id
        files.append(file_entry)
        operations.append("DOCUMENT_DISCOVERED")
        details.append({"key": f"file:{filename}", "label": filename, "state": state})
        if page_count is not None:
            details.append(
                {
                    "key": f"pages:{filename}",
                    "label": f"{page_count} page{'s' if page_count != 1 else ''}",
                    "state": state,
                }
            )
        if availability == "indexed":
            operations.append("DOCUMENT_INDEXED")
            details.append({"key": f"indexed:{filename}", "label": "Indexed", "state": "complete"})
        if _was_read(item):
            operations.append("DOCUMENT_READ")
            details.append({"key": f"read:{filename}", "label": "Content extracted", "state": "complete"})
        section_count = _relevant_section_count(item)
        if section_count:
            operations.append("DOCUMENT_SEARCHED")
            relevant_sections += section_count
            details.append(
                {
                    "key": f"search:{filename}",
                    "label": f"{section_count} relevant section{'s' if section_count != 1 else ''} found",
                    "state": "complete",
                }
            )

    operations = list(dict.fromkeys(operations))
    payload: dict[str, Any] = {
        "id": "document_analysis",
        "name": "Document Analysis",
        "capability": "DOCUMENT_READ",
        "status": "error" if failed else status,
        "operation": operations[-1] if operations else "DOCUMENT_DISCOVERED",
        "operations": operations,
        "details": details,
        "files": files,
        "counts": {"files": len(files), "relevant_sections": relevant_sections},
        "actions": [_WORKSPACE_ACTIONS["DOCUMENT_READ"]],
    }
    return payload


def document_tool_stage_payload(
    attachments: list[dict[str, Any]],
    *,
    operation: str,
    status: str,
) -> dict[str, Any] | None:
    full = document_tool_payload(attachments, status=status)
    known = set(full.get("operations") or [])
    if operation not in known:
        return None
    prefixes = _DOCUMENT_DETAIL_PREFIXES.get(operation, ("file:",))
    details = [
        detail
        for detail in full.get("details") or []
        if isinstance(detail, dict) and str(detail.get("key", "")).startswith(prefixes)
    ]
    allowed_ops = [
        item
        for item in _DOCUMENT_OPERATION_ORDER
        if item in known and _DOCUMENT_OPERATION_ORDER.index(item) <= _DOCUMENT_OPERATION_ORDER.index(operation)
    ]
    return {
        **full,
        "status": "error" if full["status"] == "error" else status,
        "operation": operation,
        "operations": allowed_ops,
        "details": details,
    }


def iter_document_tool_events(attachments: list[dict[str, Any]]) -> list[dict[str, Any]]:
    full = document_tool_payload(attachments, status="complete")
    operations = [op for op in _DOCUMENT_OPERATION_ORDER if op in set(full.get("operations") or [])]
    if not operations:
        return [full]
    events: list[dict[str, Any]] = []
    for index, operation in enumerate(operations):
        stage = document_tool_stage_payload(
            attachments,
            operation=operation,
            status="complete" if index == len(operations) - 1 else "current",
        )
        if stage is not None:
            events.append(stage)
    return events


def capability_tool_payload(
    *,
    agent_type: str,
    status: str,
    agent_result: AgentResult | None = None,
    validation_status: str | None = None,
    error_message: str | None = None,
) -> dict[str, Any]:
    name = TOOL_TITLES.get(agent_type, capability_label(agent_type) or "Engineering capability")
    details: list[dict[str, str]] = []
    artifacts: list[dict[str, Any]] = []
    counts: dict[str, int] = {}
    operations = ["CAPABILITY_SELECTED"]

    try:
        profile = get_agent_capability_profile(EngineeringAgentType(agent_type))
        if profile.available_tools:
            details.append(
                {
                    "key": "authorized_tools",
                    "label": f"Authorized tools: {', '.join(profile.available_tools[:3])}",
                    "state": "complete" if status in {"complete", "current"} else status,
                }
            )
    except ValueError:
        pass

    output = agent_result.structured_output if agent_result else {}
    if not isinstance(output, dict):
        output = {}

    if output.get("demo_rc_beam"):
        operations.append("ENGINEERING_ANALYSIS")
        details.append(
            {
                "key": "demo_analysis",
                "label": "Deterministic beam analysis completed",
                "state": "complete",
            }
        )
    aci = output.get("aci_rc_beam")
    if isinstance(aci, dict):
        operations.append("ENGINEERING_CODE_CHECK")
        aci_status = str(aci.get("status") or "")
        if aci_status == "MISSING_REQUIRED_INPUT":
            label = "ACI 318 RC beam check waiting for required inputs"
            state = "current" if status == "current" else "complete"
        elif aci_status == "INVALID_INPUT":
            label = "ACI 318 RC beam check rejected invalid inputs"
            state = "error"
        elif aci_status == "UNSUPPORTED_CODE":
            label = "ACI 318 RC beam check unsupported for the configured code"
            state = "error"
        elif aci_status == "FAIL":
            label = "ACI 318 RC beam design check failed"
            state = "error"
        elif aci_status == "PASS":
            label = "ACI 318 RC beam flexure and shear check completed"
            state = "complete"
        else:
            label = "ACI 318 RC beam check"
            state = "complete" if status == "complete" else status
        details.append({"key": "aci_rc_beam", "label": label, "state": state})
        results = aci.get("results") if isinstance(aci.get("results"), dict) else {}
        flexure = results.get("flexure_outcome")
        shear = results.get("shear_outcome")
        if flexure in {"PASS", "FAIL"}:
            details.append(
                {
                    "key": "aci_flexure",
                    "label": f"Flexure {flexure}",
                    "state": "complete" if flexure == "PASS" else "error",
                }
            )
        if shear in {"PASS", "FAIL"}:
            details.append(
                {
                    "key": "aci_shear",
                    "label": f"Shear {shear}",
                    "state": "complete" if shear == "PASS" else "error",
                }
            )
    if output.get("analysis_type"):
        operations.append("ENGINEERING_ANALYSIS")
        details.append(
            {
                "key": "analysis_type",
                "label": f"Analysis type: {str(output['analysis_type']).replace('_', ' ').title()}",
                "state": "complete" if status == "complete" else status,
            }
        )
    if output.get("capability_label"):
        details.append(
            {
                "key": "capability_label",
                "label": str(output["capability_label"]),
                "state": "complete" if status == "complete" else status,
            }
        )

    model_summary = output.get("model_summary")
    if isinstance(model_summary, dict):
        if _positive_int(model_summary.get("member_count")) is not None:
            counts["members"] = int(model_summary["member_count"])
            details.append(
                {
                    "key": "members",
                    "label": f"{counts['members']} member{'s' if counts['members'] != 1 else ''} in model",
                    "state": "complete",
                }
            )
        if _positive_int(model_summary.get("load_combination_count")) is not None:
            counts["load_combinations"] = int(model_summary["load_combination_count"])
            details.append(
                {
                    "key": "load_combinations",
                    "label": f"{counts['load_combinations']} load combination{'s' if counts['load_combinations'] != 1 else ''} found",
                    "state": "complete",
                }
            )
        if counts:
            details.append({"key": "model_loaded", "label": "Model loaded", "state": "complete"})

    load_summary = output.get("load_combinations")
    if isinstance(load_summary, dict) and _positive_int(load_summary.get("count")) is not None:
        counts["load_combinations"] = int(load_summary["count"])
        details.append(
            {
                "key": "load_combinations",
                "label": f"{counts['load_combinations']} load combination{'s' if counts['load_combinations'] != 1 else ''} found",
                "state": "complete",
            }
        )
    elif isinstance(load_summary, list) and load_summary:
        counts["load_combinations"] = len(load_summary)
        details.append(
            {
                "key": "load_combinations",
                "label": f"{len(load_summary)} load combination{'s' if len(load_summary) != 1 else ''} found",
                "state": "complete",
            }
        )

    if output.get("engineering_results_available") is True:
        details.append(
            {
                "key": "engineering_results",
                "label": "Engineering results available",
                "state": "complete",
            }
        )
    if output.get("drawing_type"):
        operations.append("CAD_GENERATION")
        details.append(
            {
                "key": "drawing_type",
                "label": f"Drawing: {str(output['drawing_type']).replace('_', ' ').title()}",
                "state": "complete" if status == "complete" else status,
            }
        )
    if output.get("report_id"):
        operations.append("REPORT_GENERATION")
        details.append({"key": "report", "label": "Engineering report generated", "state": "complete"})

    if agent_result and agent_result.generated_artifacts:
        for index, raw in enumerate(agent_result.generated_artifacts[:10]):
            sanitized = _safe_artifact(raw, index)
            if sanitized:
                artifacts.append(sanitized)
        if artifacts:
            details.append(
                {
                    "key": "artifacts",
                    "label": f"{len(artifacts)} artifact{'s' if len(artifacts) != 1 else ''} produced",
                    "state": "complete" if status == "complete" else status,
                }
            )

    if validation_status:
        operations.append("RESULT_VALIDATION")
        details.append(
            {
                "key": "validation",
                "label": f"Validation: {validation_status.replace('_', ' ').title()}",
                "state": "complete" if status == "complete" else status,
            }
        )

    error = None
    if status == "error":
        reason = error_message or "Capability execution failed"
        error = {"title": "Tool execution failed", "reason": _safe_reason(reason)}
        details.append({"key": "error", "label": error["reason"], "state": "error"})

    payload: dict[str, Any] = {
        "id": f"capability_{agent_type.lower()}",
        "name": name,
        "capability": agent_type,
        "status": status,
        "operation": operations[-1] if operations else None,
        "operations": operations,
        "details": details,
        "artifacts": artifacts,
        "counts": counts,
    }
    action = _WORKSPACE_ACTIONS.get(agent_type)
    if action:
        payload["actions"] = [action]
    if error:
        payload["error"] = error
    return payload


def _page_count(item: dict[str, Any]) -> int | None:
    metadata = item.get("extraction_metadata")
    if isinstance(metadata, dict):
        for key in ("page_count", "pages"):
            value = metadata.get(key)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                return value
    preview = item.get("structured_preview")
    if isinstance(preview, dict):
        value = preview.get("page_count")
        if isinstance(value, int) and value >= 0:
            return value
        pages = preview.get("pages")
        if isinstance(pages, list) and pages:
            return len(pages)
    return None


def _was_read(item: dict[str, Any]) -> bool:
    extraction = str(item.get("extraction_status") or "")
    if extraction.upper() in {"COMPLETE", "COMPLETED"}:
        return True
    return bool(item.get("text_preview") or item.get("structured_preview"))


def _relevant_section_count(item: dict[str, Any]) -> int:
    memories = item.get("indexed_memory_content")
    if isinstance(memories, list) and memories:
        return len([entry for entry in memories if isinstance(entry, str) and entry.strip()])
    memory_ids = item.get("indexed_memory_ids")
    if isinstance(memory_ids, list) and memory_ids:
        return len(memory_ids)
    return 0


def _positive_int(value: Any) -> int | None:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _safe_artifact(raw: Any, index: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    sanitized: dict[str, Any] = {}
    for key, value in raw.items():
        if key.lower() in _SENSITIVE_KEYS or key.lower().endswith("_path"):
            continue
        if key not in _SAFE_ARTIFACT_KEYS:
            continue
        if isinstance(value, (str, int, float, bool)) or value is None:
            sanitized[key] = value
    artifact_type = str(sanitized.get("type") or sanitized.get("artifact_type") or "artifact")
    name = str(sanitized.get("name") or f"{artifact_type.replace('_', ' ').title()} {index + 1}")
    return {
        "id": str(sanitized.get("id") or sanitized.get("file_id") or sanitized.get("report_id") or sanitized.get("drawing_id") or f"artifact-{index}"),
        "name": name,
        "artifact_type": artifact_type,
    }


def capability_label(agent_type: str | None) -> str | None:
    if not agent_type:
        return None
    try:
        profile = get_agent_capability_profile(EngineeringAgentType(agent_type))
        return profile.name
    except ValueError:
        return agent_type.replace("_", " ").title()


def _safe_reason(reason: str) -> str:
    cleaned = " ".join(reason.split())
    lowered = cleaned.lower()
    if any(token in lowered for token in ("traceback", "password", "secret", "token", "c:\\", "/home/", "database")):
        return "The tool could not complete this engineering step."
    return cleaned[:400]
