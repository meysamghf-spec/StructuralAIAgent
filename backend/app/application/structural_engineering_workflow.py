"""One structural workflow over the current PEM.

The agent records a structured brief, checks whether the model can be analyzed,
and calls the existing internal analysis, preliminary design results, drawing
set, and report. It does not invent missing brief values or external-solver
results. Writing a brief into the PEM happens only when the caller sets
``apply_to_pem``.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.analysis_model_readiness import build_model_summary
from app.application.drawing_set_query_service import DrawingSetQueryService
from app.application.engineering_agent_services import EngineeringAgentServices
from app.domain.models.analysis import AnalysisRequest
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import DesignCheckStatus, LoadCategory

_BRIEF_FIELDS: tuple[tuple[str, str], ...] = (
    ("project_type", "Project type"),
    ("location", "Location"),
    ("number_of_stories", "Number of stories"),
    ("story_heights", "Story heights"),
    ("grid", "Grid"),
    ("spans", "Spans"),
    ("structural_system", "Structural system"),
    ("material", "Material"),
    ("member_assumptions", "Member assumptions"),
    ("loads", "Loads"),
    ("design_code", "Design code"),
    ("units", "Units"),
    ("foundation_assumptions", "Foundation assumptions"),
    ("seismic_assumptions", "Seismic assumptions"),
    ("wind_assumptions", "Wind assumptions"),
    ("engineer_notes", "Engineer notes"),
    ("plot_length_m", "Plot length"),
    ("plot_width_m", "Plot width"),
    ("frontage_m", "Frontage"),
    ("residential_floor_count", "Residential floors"),
    ("parking_space_count", "Parking spaces"),
    ("apartments_per_floor", "Apartments per floor"),
    ("bedrooms_per_apartment", "Bedrooms per apartment"),
    ("has_piloti", "Parking storey"),
)

_REQUIRED_FOR_ANALYSIS = (
    "geometry",
    "levels",
    "grids",
    "members",
    "materials",
    "sections",
    "supports",
    "loads",
    "load_cases",
    "load_combinations",
)

_OPTIONAL_GAPS = ("code", "seismic_parameters", "wind_parameters", "foundation")

_MISSING_LABELS = {
    "geometry": "geometry",
    "levels": "story levels",
    "grids": "grids",
    "members": "structural members",
    "materials": "materials",
    "sections": "member sections",
    "supports": "support conditions",
    "loads": "loads",
    "load_cases": "load case definitions",
    "load_combinations": "load combinations",
    "code": "applicable code inputs",
    "analysis_settings": "analysis settings",
    "seismic_parameters": "seismic parameters",
    "wind_parameters": "wind parameters",
    "foundation": "foundation assumptions",
}

_NAMED_SOLVERS = frozenset({"ETABS", "SAP2000", "SAFE"})
_RECOGNIZED_CHECKS = frozenset({"BEAM_FLEXURE", "BEAM_SHEAR"})
_SIMPLIFIED_CHECKS = frozenset(
    {"BEAM_FLEXURE", "BEAM_SHEAR", "COLUMN_COMBINED", "SLAB_FLEXURE_ONE_WAY"}
)


def normalize_engineering_brief(parameters: dict[str, Any] | None) -> dict[str, Any]:
    """Classify each brief field. Absent values stay unavailable."""
    raw = parameters.get("engineering_brief") if isinstance(parameters, dict) else None
    source = raw if isinstance(raw, dict) else {}
    fields: list[dict[str, Any]] = []
    for key, label in _BRIEF_FIELDS:
        value = source.get(key)
        if _blank(value):
            fields.append(
                {"field": key, "label": label, "value": None, "origin": "UNAVAILABLE"}
            )
            continue
        fields.append(
            {"field": key, "label": label, "value": value, "origin": "USER_PROVIDED"}
        )
    unavailable = [item["label"] for item in fields if item["origin"] == "UNAVAILABLE"]
    return {
        "fields": fields,
        "values": {item["field"]: item["value"] for item in fields if item["origin"] == "USER_PROVIDED"},
        "unavailable": unavailable,
    }


def assess_structural_readiness(pem: ProjectEngineeringModel) -> dict[str, Any]:
    """READY, PARTIAL, or NOT_READY, with the exact missing items."""
    structural = pem.structural_model
    summary = build_model_summary(pem)
    present = {
        "geometry": summary["point_count"] > 0 or summary["member_count"] > 0,
        "levels": summary["level_count"] > 0,
        "grids": summary["grid_count"] > 0,
        "members": summary["member_count"] > 0,
        "materials": summary["material_count"] > 0,
        "sections": summary["section_count"] > 0,
        "supports": summary["support_count"] > 0,
        "load_cases": summary["load_case_count"] > 0,
        "load_combinations": summary["load_combination_count"] > 0,
        "loads": any(case.loads for case in structural.load_cases),
        "code": pem.code_configuration is not None,
        "analysis_settings": structural.analysis_model is not None,
        "seismic_parameters": any(
            case.category is LoadCategory.SEISMIC for case in structural.load_cases
        ),
        "wind_parameters": any(case.category is LoadCategory.WIND for case in structural.load_cases),
        "foundation": len(structural.footings) > 0 or len(structural.sections.foundations) > 0,
    }
    required_missing = [key for key in _REQUIRED_FOR_ANALYSIS if not present[key]]
    optional_missing = [key for key in _OPTIONAL_GAPS if not present[key]]
    if required_missing:
        status = "NOT_READY"
    elif optional_missing:
        status = "PARTIAL"
    else:
        status = "READY"
    missing = required_missing + optional_missing
    return {
        "status": status,
        "missing": [_MISSING_LABELS[key] for key in missing],
        "missing_codes": missing,
        "model_summary": summary,
        "engineer_message": readiness_message(status, [_MISSING_LABELS[key] for key in missing]),
    }


def readiness_message(status: str, missing: list[str]) -> str:
    if status == "READY":
        return "The structural model has the information required to start analysis."
    if not missing:
        return "The structural model is not ready for analysis."
    lines = "\n".join(f"- {item}" for item in missing)
    if status == "NOT_READY":
        return (
            "Analysis cannot start because the following required information is missing:\n"
            f"{lines}"
        )
    return (
        "The model can be reviewed, but the following information is still missing:\n"
        f"{lines}"
    )


def resolve_workflow_qa(
    *,
    analysis_executed: bool,
    analysis_status: str | None,
    design_checks: list[dict[str, Any]],
) -> dict[str, Any]:
    """PASS only when analysis ran and a recognized check passed without a failure."""
    recognized = [item for item in design_checks if item.get("recognized") is True]
    if not analysis_executed:
        return {
            "status": "NOT_RUN",
            "reason": "Analysis was not completed, so QA has nothing to accept.",
        }
    if str(analysis_status or "").upper() != "SUCCESS":
        return {
            "status": "NOT_RUN",
            "reason": "Analysis did not finish successfully, so QA was not run.",
        }
    if not recognized:
        return {
            "status": "NOT_APPLICABLE",
            "reason": "No ACI 318-25 beam flexure or shear check was produced for this model.",
        }
    statuses = {str(item.get("status") or "").upper() for item in recognized}
    if "FAIL" in statuses:
        return {
            "status": "FAIL",
            "reason": "At least one completed beam design check failed.",
        }
    if "PASS" in statuses:
        return {
            "status": "PASS",
            "reason": (
                "Completed beam checks passed. This is not a stamped engineering approval."
            ),
        }
    return {
        "status": "NOT_APPLICABLE",
        "reason": "Beam checks were recorded without a pass or fail result.",
    }


def execute_structural_workflow(
    *,
    services: EngineeringAgentServices,
    project_id: UUID,
    user_request: str,
    parameters: dict[str, Any] | None,
    actor_id: str | None,
) -> dict[str, Any]:
    params = parameters if isinstance(parameters, dict) else {}
    operation = str(params.get("operation") or "workflow").strip().lower()
    brief = normalize_engineering_brief(params)
    from app.application.service_factory import build_pem_service

    pem_service = build_pem_service()
    pem = pem_service.get_current_pem(project_id)
    meta = pem_service.get_current_snapshot_meta(project_id)
    if pem is None or meta is None:
        raise ValueError(f"Project {project_id} has no current PEM")

    apply_requested = params.get("apply_to_pem") is True
    stages = _stages_for(operation)
    change = {
        "applied": False,
        "source": "not_applied",
        "approval_state": "NOT_REQUESTED",
        "approval_request_id": None,
        "changed_entities": [],
    }
    if "prepare" in stages and apply_requested:
        change = _apply_brief(
            services,
            project_id=project_id,
            pem=pem,
            brief=brief,
            actor_id=actor_id,
        )
        pem = pem_service.get_current_pem(project_id) or pem
        meta = pem_service.get_current_snapshot_meta(project_id) or meta

    readiness = assess_structural_readiness(pem)
    analysis = _empty_analysis(params.get("solver"))
    if "analyze" in stages:
        analysis = _run_analysis(
            services,
            project_id=project_id,
            pem=pem,
            readiness=readiness,
            requested_solver=params.get("solver"),
            actor_id=actor_id,
        )
    elif _pem_has_internal_results(pem):
        analysis = _analysis_from_pem(pem)

    design_checks = _design_checks(pem) if "design" in stages or "qa" in stages or "outputs" in stages else []
    qa = (
        resolve_workflow_qa(
            analysis_executed=bool(analysis.get("executed")),
            analysis_status=str(analysis.get("status") or ""),
            design_checks=design_checks,
        )
        if "qa" in stages or operation == "workflow"
        else {"status": "NOT_RUN", "reason": "QA was not requested for this action."}
    )
    drawings = (
        _drawings(DrawingSetQueryService(pem_service), project_id) if "outputs" in stages else None
    )
    report = None
    if "outputs" in stages:
        report = _report(
            pem=pem,
            meta_version=meta.version,
            snapshot_id=str(meta.id),
            brief=brief,
            readiness=readiness,
            analysis=analysis,
            design_checks=design_checks,
            qa=qa,
            drawings=drawings or {},
            change=change,
            user_request=user_request,
        )

    unavailable = _unavailable(brief, readiness, analysis, design_checks)
    engineer_message = _engineer_message(operation, readiness, analysis, qa, change)
    package = {
        "operation": operation,
        "agent": "Structural Engineering Agent",
        "responsibility": (
            "Inspect the current PEM, record the engineering brief, and run the "
            "analysis, design checks, drawings, and report that are actually implemented."
        ),
        "engineering_brief": brief,
        "model_readiness": readiness,
        "analysis": analysis,
        "design_checks": design_checks,
        "qa": qa,
        "drawings": drawings,
        "engineering_report": report,
        "pem": {
            "version": meta.version,
            "snapshot_id": str(meta.id),
            "change": change,
        },
        "unavailable_capabilities": unavailable,
        "final_engineering_approval": False,
        "engineer_message": engineer_message,
        "calculated": _calculated(analysis, design_checks),
        "assumed": _assumed(pem),
        "not_calculated": unavailable,
        "external_software": _external_software(analysis),
    }
    return package


def _stages_for(operation: str) -> set[str]:
    if operation == "prepare":
        return {"prepare"}
    if operation == "validate":
        return {"validate"}
    if operation == "analyze":
        return {"analyze"}
    if operation == "design":
        return {"design"}
    if operation == "qa":
        return {"qa"}
    if operation == "outputs":
        return {"outputs", "qa", "design"}
    return {"prepare", "validate", "analyze", "design", "qa", "outputs"}


def _apply_brief(
    services: EngineeringAgentServices,
    *,
    project_id: UUID,
    pem: ProjectEngineeringModel,
    brief: dict[str, Any],
    actor_id: str | None,
) -> dict[str, Any]:
    if build_model_summary(pem)["member_count"] > 0:
        return {
            "applied": False,
            "source": "refused",
            "approval_state": "NOT_REQUESTED",
            "approval_request_id": None,
            "changed_entities": [],
            "reason": "The current PEM already has structural members. The brief was not written over it.",
        }
    text = _generation_text(brief["values"])
    pipeline = services.building_design_pipeline
    if text is None or pipeline is None:
        missing = brief["unavailable"]
        return {
            "applied": False,
            "source": "not_applied",
            "approval_state": "NOT_REQUESTED",
            "approval_request_id": None,
            "changed_entities": [],
            "reason": (
                "The brief does not include the plot size and story count required "
                "to build a model. Nothing was written to the PEM."
            ),
            "missing": missing,
        }
    result = pipeline.generate_from_brief(
        project_id,
        text,
        created_by=actor_id,
        generate_drawings=False,
    )
    if result.pem_version is None:
        return {
            "applied": False,
            "source": "BuildingDesignPipeline",
            "approval_state": "NOT_REQUESTED",
            "approval_request_id": None,
            "changed_entities": [],
            "reason": "The existing model builder is waiting for inputs and did not change the PEM.",
        }
    assembled = result.assembled
    return {
        "applied": True,
        "source": "BuildingDesignPipeline",
        "approval_state": "PENDING" if result.approval_request_id else "NOT_REQUESTED",
        "approval_request_id": str(result.approval_request_id) if result.approval_request_id else None,
        "pem_version": result.pem_version,
        "snapshot_id": str(result.snapshot_id) if result.snapshot_id else None,
        "changed_entities": [
            {"entity": "structural_members", "count": assembled.structure.beam_count + assembled.structure.column_count},
            {"entity": "beams", "count": assembled.structure.beam_count},
            {"entity": "columns", "count": assembled.structure.column_count},
            {"entity": "slabs", "count": assembled.structure.slab_count},
        ],
        "reason": "The brief was written to a new PEM snapshot and is waiting for engineer approval.",
    }


def _generation_text(values: dict[str, Any]) -> str | None:
    length = _number(values.get("plot_length_m"))
    width = _number(values.get("plot_width_m"))
    floors = _number(values.get("residential_floor_count"))
    if floors is None:
        floors = _number(values.get("number_of_stories"))
    if length is None or width is None or floors is None:
        return None
    parts = [f"Plot {width:g}m × {length:g}m"]
    frontage = _number(values.get("frontage_m"))
    if frontage is not None:
        parts.append(f"{frontage:g}m frontage")
    if values.get("has_piloti") is True:
        parking = _number(values.get("parking_space_count"))
        if parking is None:
            return None
        parts.append(f"pilot/parking floor, {int(parking)} parking spaces")
    parts.append(f"{int(floors)} residential floors")
    apartments = _number(values.get("apartments_per_floor"))
    bedrooms = _number(values.get("bedrooms_per_apartment"))
    if apartments is not None:
        noun = "apartment" if int(apartments) == 1 else "apartments"
        parts.append(f"{int(apartments)} {noun} per floor")
    if bedrooms is not None:
        parts.append(f"{int(bedrooms)} bedrooms per apartment")
    return ", ".join(parts)


def _run_analysis(
    services: EngineeringAgentServices,
    *,
    project_id: UUID,
    pem: ProjectEngineeringModel,
    readiness: dict[str, Any],
    requested_solver: Any,
    actor_id: str | None,
) -> dict[str, Any]:
    solver_name = _solver_name(requested_solver)
    if readiness["status"] == "NOT_READY":
        record = _empty_analysis(solver_name)
        record["requested"] = solver_name is not None
        record["status"] = "NOT_RUN"
        record["solver_status"] = "NOT_RUN"
        record["reason"] = "MODEL_NOT_READY"
        record["engineer_message"] = readiness["engineer_message"]
        return record

    named = solver_name in _NAMED_SOLVERS
    solver_argument = solver_name if named else _internal_solver_name(pem, solver_name)
    result = services.analysis_engine.run_analysis(
        AnalysisRequest(
            project_id=project_id,
            analysis_type="STATIC",
            parameters={"solver": solver_argument} if solver_argument else {},
        ),
        created_by=actor_id,
    )
    outputs = result.outputs if isinstance(result.outputs, dict) else {}
    executed = bool(outputs.get("engineering_results_available")) and not named
    status = result.status.value if hasattr(result.status, "value") else str(result.status)
    if named:
        executed = False
    available = (not named) and status == "SUCCESS"
    return {
        "solver": outputs.get("solver") or solver_argument or "internal",
        "requested": True,
        "available": available,
        "executed": executed and status == "SUCCESS",
        "status": "REQUIRES_LOCAL_SOFTWARE" if named else status,
        "solver_status": outputs.get("solver_status") or status,
        "reason": outputs.get("reason"),
        "engineer_message": _analysis_message(named, status, result.message, readiness),
        "analysis_run_id": str(result.id) if result.id else None,
        "pem_version": result.pem_version,
        "pem_snapshot_id": str(result.pem_snapshot_id) if result.pem_snapshot_id else None,
        "integration_execution_id": outputs.get("integration_execution_id"),
        "assumptions": outputs.get("assumptions") or [],
        "warnings": outputs.get("warnings") or [],
        "max_abs_displacement_m": outputs.get("max_abs_displacement_m"),
        "engineering_results_available": executed and status == "SUCCESS",
    }


def _analysis_message(named: bool, status: str, message: str, readiness: dict[str, Any]) -> str:
    if named:
        return (
            "The requested external solver is not available on this computer. "
            "No forces or displacements were calculated. "
            f"{message}"
        )
    if status == "SUCCESS":
        return message
    if readiness["status"] != "READY":
        return readiness["engineer_message"]
    return message or "Analysis did not produce a result."


def _analysis_from_pem(pem: ProjectEngineeringModel) -> dict[str, Any]:
    configuration = pem.structural_model.analysis_model.configuration or {}
    status = str(configuration.get("last_analysis_status") or "")
    executed = status.upper() == "SUCCESS" or bool(pem.structural_model.story_drifts)
    return {
        "solver": configuration.get("solver") or "internal",
        "requested": False,
        "available": executed,
        "executed": executed,
        "status": "SUCCESS" if executed else "NOT_RUN",
        "solver_status": status or ("SUCCESS" if executed else "NOT_RUN"),
        "reason": None,
        "engineer_message": "Using the analysis already stored on the current PEM.",
        "analysis_run_id": None,
        "assumptions": [],
        "warnings": [],
        "engineering_results_available": executed,
    }


def _pem_has_internal_results(pem: ProjectEngineeringModel) -> bool:
    structural = pem.structural_model
    return bool(structural.story_drifts or structural.design_checks)


def _design_checks(pem: ProjectEngineeringModel) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    for item in pem.structural_model.design_checks:
        kind = item.check_kind
        recognized = kind in _RECOGNIZED_CHECKS
        simplified = kind in _SIMPLIFIED_CHECKS or "simplified" in item.code_reference.lower()
        checks.append(
            {
                "member_id": item.member_id,
                "member_name": item.member_name,
                "code": _code_for(item.code_reference),
                "check_type": kind,
                "inputs": {
                    "governing_combination": item.governing_combination,
                    "demand": item.demand,
                    "demand_unit": item.demand_unit,
                },
                "result": item.status.value,
                "utilization": item.utilization,
                "capacity": item.capacity,
                "status": item.status.value,
                "assumptions": list(item.assumptions),
                "provenance": item.code_reference,
                "recognized": recognized,
                "simplified": simplified,
                "label": (
                    "Simplified ACI 318-25 beam check"
                    if recognized
                    else "Preliminary check stored on the PEM"
                ),
            }
        )
    return checks


def _code_for(reference: str) -> str:
    if "ACI" in reference:
        return "ACI 318-25"
    if "AISC" in reference:
        return "AISC 360-22"
    return reference or "UNAVAILABLE"


def _drawings(service: DrawingSetQueryService, project_id: UUID) -> dict[str, Any]:
    drawing_set = service.current_drawing_set(project_id)
    numbers = list(drawing_set.sheet_numbers)
    pending = []
    metadata = drawing_set.metadata if isinstance(drawing_set.metadata, dict) else {}
    for item in metadata.get("pending_milestones") or []:
        if isinstance(item, str):
            pending.append(item)
    return {
        "pem_version": drawing_set.pem_version,
        "pem_snapshot_id": drawing_set.source_snapshot_id,
        "sheet_numbers": numbers,
        "includes_schedules": {"S-201", "S-202", "S-203"} <= set(numbers),
        "pending": pending,
        "s301_generated": any(number.startswith("S-301") for number in numbers),
        "s401_generated": any(number.startswith("S-401") for number in numbers),
    }


def _report(
    *,
    pem: ProjectEngineeringModel,
    meta_version: int,
    snapshot_id: str,
    brief: dict[str, Any],
    readiness: dict[str, Any],
    analysis: dict[str, Any],
    design_checks: list[dict[str, Any]],
    qa: dict[str, Any],
    drawings: dict[str, Any],
    change: dict[str, Any],
    user_request: str,
) -> dict[str, Any]:
    structural = pem.structural_model
    materials = [item.name for item in structural.materials.concrete]
    materials.extend(item.name for item in structural.materials.steel)
    return {
        "title": "Structural Engineering Agent v1 — project report",
        "disclaimer": (
            "Generated from the current PEM and this run. "
            "It is not a signed engineering approval and does not name an engineer of record."
        ),
        "1_project_information": {
            "name": pem.metadata.name,
            "project_id": str(pem.project_id),
            "request": user_request,
        },
        "2_engineering_brief": brief,
        "3_pem": {"version": meta_version, "snapshot_id": snapshot_id, "change": change},
        "4_structural_system": pem.structural_system,
        "5_materials": materials,
        "6_loads": [case.name for case in structural.load_cases],
        "7_analysis_method": {
            "solver": analysis.get("solver"),
            "executed": analysis.get("executed"),
            "status": analysis.get("status"),
        },
        "8_analysis_status": analysis.get("engineer_message"),
        "9_design_checks": [
            {
                "check_type": item["check_type"],
                "code": item["code"],
                "status": item["status"],
                "utilization": item["utilization"],
                "simplified": item["simplified"],
            }
            for item in design_checks[:40]
        ],
        "10_qa_status": qa,
        "11_drawings": drawings,
        "12_assumptions": _assumed(pem),
        "13_limitations": [
            "External solvers ETABS, SAP2000, and SAFE are not executed on this computer.",
            "Sheets S-301 and S-401 are not generated.",
            "Simplified beam checks are not a complete building-code design.",
            "No engineer credentials or signature are included.",
        ],
        "14_external_software": _external_software(analysis),
        "15_traceability": {
            "pem_version": meta_version,
            "pem_snapshot_id": snapshot_id,
            "analysis_run_id": analysis.get("analysis_run_id"),
            "model_readiness": readiness["status"],
        },
        "16_approval_status": {
            "final_engineering_approval": False,
            "model_change": change.get("approval_state"),
            "approval_request_id": change.get("approval_request_id"),
        },
    }


def _assumed(pem: ProjectEngineeringModel) -> list[dict[str, Any]]:
    assumed = []
    for item in pem.structural_model.input_provenance:
        if item.origin.value in {"ASSUMED", "DEFAULT"}:
            assumed.append(
                {
                    "field": item.field,
                    "value": item.value,
                    "origin": item.origin.value,
                    "note": item.note,
                }
            )
    return assumed


def _calculated(analysis: dict[str, Any], design_checks: list[dict[str, Any]]) -> list[str]:
    items = []
    if analysis.get("executed"):
        items.append("Internal linear-static analysis")
    if any(item.get("recognized") and item.get("status") == DesignCheckStatus.PASS.value for item in design_checks):
        items.append("Simplified ACI 318-25 beam flexure and shear checks stored on the PEM")
    return items


def _external_software(analysis: dict[str, Any]) -> list[str]:
    solver = str(analysis.get("solver") or "")
    if solver.upper() in _NAMED_SOLVERS or analysis.get("status") == "REQUIRES_LOCAL_SOFTWARE":
        return [f"{solver or 'Named solver'} was requested and was not executed."]
    return ["ETABS, SAP2000, and SAFE were not used."]


def _unavailable(
    brief: dict[str, Any],
    readiness: dict[str, Any],
    analysis: dict[str, Any],
    design_checks: list[dict[str, Any]],
) -> list[str]:
    items = [f"{label} was not provided." for label in brief["unavailable"]]
    if readiness["status"] == "NOT_READY":
        items.append(readiness["engineer_message"])
    if analysis.get("executed") is False and analysis.get("requested"):
        items.append(str(analysis.get("engineer_message") or "Analysis was not executed."))
    if not any(item.get("recognized") for item in design_checks):
        items.append("No recognized ACI beam check is available for this model.")
    items.append("ETABS, SAP2000, and SAFE results were not simulated.")
    items.append("Sheets S-301 and S-401 were not generated.")
    return items


def _engineer_message(
    operation: str,
    readiness: dict[str, Any],
    analysis: dict[str, Any],
    qa: dict[str, Any],
    change: dict[str, Any],
) -> str:
    if operation == "validate" or readiness["status"] == "NOT_READY" and operation in {"analyze", "workflow"}:
        if readiness["status"] == "NOT_READY":
            return readiness["engineer_message"]
    if change.get("applied") is False and change.get("reason") and operation in {"prepare", "workflow"}:
        if "already has structural members" in str(change.get("reason")):
            return str(change["reason"])
    if analysis.get("requested") and analysis.get("executed") is False and analysis.get("engineer_message"):
        if operation in {"analyze", "workflow"}:
            return str(analysis["engineer_message"])
    if qa.get("status") == "FAIL":
        return str(qa["reason"])
    if qa.get("status") == "PASS":
        return str(qa["reason"])
    if readiness["status"] == "NOT_READY":
        return readiness["engineer_message"]
    return str(analysis.get("engineer_message") or readiness["engineer_message"])


def _empty_analysis(solver: Any) -> dict[str, Any]:
    name = _solver_name(solver)
    return {
        "solver": name,
        "requested": False,
        "available": False,
        "executed": False,
        "status": "NOT_RUN",
        "solver_status": "NOT_RUN",
        "reason": None,
        "engineer_message": "Analysis was not requested.",
        "analysis_run_id": None,
        "engineering_results_available": False,
        "assumptions": [],
        "warnings": [],
    }


def _solver_name(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    upper = text.upper().replace(" ", "")
    if upper in {"ETABS", "SAP2000", "SAFE"}:
        return upper
    return text


def _internal_solver_name(pem: ProjectEngineeringModel, requested: str | None) -> str:
    if requested and requested.upper() not in _NAMED_SOLVERS:
        return requested
    configured = str((pem.structural_model.analysis_model.configuration or {}).get("solver") or "")
    if configured.strip().lower() in {"internal", "internal_direct_stiffness_2d", "internal_direct_stiffness_3d"}:
        return configured
    return "internal"


def _blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    return False


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None
