"""Coordinate architecture, structure, drawings, and external software.

ETABS, SAFE, and AutoCAD are asked to run through the existing adapters.
When those applications are not installed, the result is an explicit
unavailable execution. Internal analysis and the existing design checks stay
labeled as internal results.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.application.coordination_service import CoordinationService
from app.application.engineering_brief_mapping import normalize_engineering_brief
from app.domain.models.building_brief import BriefLanguage, BuildingBrief, OccupancyKind
from app.domain.models.integration import IntegrationSoftware
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_architecture import StructuralSystem

ARCHITECTURAL_FIELDS: tuple[tuple[str, str], ...] = (
    ("project_type", "Project type"),
    ("location", "Location"),
    ("plot_length_m", "Plot length"),
    ("plot_width_m", "Plot width"),
    ("frontage_m", "Frontage"),
    ("setback_front_m", "Front setback"),
    ("setback_rear_m", "Rear setback"),
    ("setback_side_m", "Side setback"),
    ("number_of_floors", "Number of floors"),
    ("story_heights", "Floor heights"),
    ("required_rooms", "Required rooms"),
    ("room_areas", "Room areas"),
    ("circulation", "Circulation"),
    ("parking_space_count", "Parking"),
    ("stairs", "Stairs"),
    ("elevator", "Elevator"),
    ("shafts", "Shafts"),
    ("entrances", "Entrances"),
    ("accessibility", "Accessibility"),
    ("architectural_preferences", "Architectural preferences"),
    ("facade", "Facade"),
    ("engineer_notes", "Engineer notes"),
    ("units", "Units"),
    ("has_piloti", "Piloti"),
    ("apartments_per_floor", "Apartments per floor"),
    ("bedrooms_per_apartment", "Bedrooms"),
    ("structural_system", "Structural system"),
)

_DETAIL_SHEETS = (
    ("foundation details", "Foundation detail geometry is not stored on the PEM."),
    ("beam details", "Beam detail geometry is not stored on the PEM."),
    ("column details", "Column detail geometry is not stored on the PEM."),
    ("slab details", "Slab detail geometry is not stored on the PEM."),
    ("stair structural details", "Stair structural detailing is not stored on the PEM."),
    ("shear wall details", "Shear wall detail geometry is not stored on the PEM."),
    ("typical sections", "S-301 section geometry is not stored on the PEM."),
    ("reinforcement details", "S-401 reinforcement detailing is not stored on the PEM."),
    ("construction notes", "Construction-note sheets are not stored separately from S-001."),
)


def execute_production_workflow(
    *,
    services: Any,
    project_id: UUID,
    user_request: str,
    parameters: dict[str, Any] | None,
    actor_id: str | None,
    context: dict[str, Any] | None,
) -> dict[str, Any]:
    from app.application.service_factory import (
        build_pem_service,
        build_structural_solver_integration_service,
    )
    from app.application.structural_engineering_workflow import (
        _drawings,
        _execute_design,
        _learning_context,
        _run_analysis,
        assess_structural_readiness,
    )
    from app.application.drawing_set_query_service import DrawingSetQueryService

    params = parameters if isinstance(parameters, dict) else {}
    brief = normalize_engineering_brief(
        {"engineering_brief": params.get("architectural_brief") or params.get("engineering_brief")},
        ARCHITECTURAL_FIELDS,
    )
    model_brief, brief_notes = building_brief_from_record(brief)
    pem_service = build_pem_service()
    pem = pem_service.get_current_pem(project_id)
    meta = pem_service.get_current_snapshot_meta(project_id)
    if pem is None or meta is None:
        raise ValueError(f"Project {project_id} has no current PEM")

    change = _apply_architecture(
        services,
        project_id=project_id,
        pem=pem,
        model_brief=model_brief,
        requested=params.get("apply_to_pem") is True,
        actor_id=actor_id,
    )
    pem = pem_service.get_current_pem(project_id) or pem
    meta = pem_service.get_current_snapshot_meta(project_id) or meta
    readiness = assess_structural_readiness(pem)
    internal = _run_analysis(
        services,
        project_id=project_id,
        pem=pem,
        readiness=readiness,
        requested_solver=None,
        actor_id=actor_id,
    )
    internal["label"] = "INTERNAL PRELIMINARY ANALYSIS"
    internal["external_software_result"] = False
    design_checks = _execute_design(
        services,
        project_id=project_id,
        pem=pem,
        readiness=readiness,
        analysis=internal,
        actor_id=actor_id,
    )
    pem = pem_service.get_current_pem(project_id) or pem
    meta = pem_service.get_current_snapshot_meta(project_id) or meta
    coordination = _coordination_record(pem)
    solver = build_structural_solver_integration_service()
    external = [
        _solver_execution(solver, project_id, IntegrationSoftware.ETABS, pem_version=meta.version, actor_id=actor_id),
        _solver_execution(solver, project_id, IntegrationSoftware.SAFE, pem_version=meta.version, actor_id=actor_id),
        _autocad_execution(project_id, snapshot_id=str(meta.id)),
    ]
    drawings = _drawings(DrawingSetQueryService(pem_service), project_id)
    drawings["detail_sheets"] = detail_sheet_status()
    drawings["autocad_execution"] = False
    learning = _learning_context(context)
    gates = production_qa_gates(
        pem=pem,
        coordination=coordination,
        internal_analysis=internal,
        design_checks=design_checks,
        drawings=drawings,
        external=external,
        snapshot_id=str(meta.id),
    )
    qa = summarize_production_qa(gates)
    report = _production_report(
        pem=pem,
        meta_version=meta.version,
        snapshot_id=str(meta.id),
        brief=brief,
        brief_notes=brief_notes,
        user_request=user_request,
        coordination=coordination,
        internal_analysis=internal,
        design_checks=design_checks,
        drawings=drawings,
        external=external,
        qa=qa,
        learning=learning,
        change=change,
    )
    external_failed = [item["software"] for item in external if item["executed"] is not True]
    return {
        "operation": "production",
        "agent": "Structural Engineering Agent",
        "responsibility": (
            "Coordinate the architectural brief, PEM, drawings, and external software. "
            "ETABS, SAFE, and AutoCAD results are recorded only when those applications run."
        ),
        "engineering_brief": brief,
        "architectural_brief": brief,
        "architectural_notes": brief_notes,
        "model_readiness": readiness,
        "coordination": coordination,
        "analysis": _external_analysis_view(external),
        "internal_analysis": internal,
        "design_checks": design_checks,
        "external_executions": external,
        "qa": qa,
        "drawings": drawings,
        "engineering_report": report,
        "pem": {"version": meta.version, "snapshot_id": str(meta.id), "change": change},
        "unavailable_capabilities": external_failed,
        "final_engineering_approval": False,
        "engineer_message": _engineer_message(change, qa, external_failed),
        "learning_context": learning,
        "authoritative_engineering_input": {
            "heading": "AUTHORITATIVE ENGINEERING INPUT",
            "source": "current PEM snapshot",
            "pem_version": meta.version,
            "pem_snapshot_id": str(meta.id),
        },
    }


def building_brief_from_record(brief: dict[str, Any]) -> tuple[BuildingBrief, list[dict[str, Any]]]:
    """Copy provided architectural values. Blank fields stay off the model brief."""
    fields = {item["field"]: item for item in brief.get("fields", [])}
    notes: list[dict[str, Any]] = []

    def take(name: str) -> Any:
        item = fields.get(name)
        if item is None or item.get("origin") == "UNAVAILABLE" or item.get("value") in (None, ""):
            notes.append({"field": name, "origin": "UNAVAILABLE", "value": None})
            return None
        notes.append({"field": name, "origin": item.get("origin"), "value": item.get("value")})
        return item.get("value")

    plot_length = _as_float(take("plot_length_m"))
    plot_width = _as_float(take("plot_width_m"))
    frontage = _as_float(take("frontage_m"))
    setback_front = _as_float(take("setback_front_m"))
    setback_rear = _as_float(take("setback_rear_m"))
    setback_side = _as_float(take("setback_side_m"))
    stories = _integer(take("number_of_floors"))
    piloti = _truthy(take("has_piloti"))
    residential = stories
    if stories is not None and piloti and stories > 1:
        residential = stories - 1
        notes.append(
            {
                "field": "residential_floor_count",
                "origin": "DERIVED",
                "value": residential,
                "note": "Piloti is one of the stated floors, so residential floors are the remainder.",
            }
        )
    heights = _numbers(take("story_heights"))
    storey_height = heights[0] if heights else None
    if len(heights) > 1 and len(set(heights)) > 1:
        notes.append(
            {
                "field": "story_heights",
                "origin": "ASSUMED",
                "value": storey_height,
                "note": "The layout uses the first stated floor height. The full list is retained.",
            }
        )
    parking = _integer(take("parking_space_count"))
    apartments = _integer(take("apartments_per_floor"))
    bedrooms = _integer(take("bedrooms_per_apartment"))
    stairs = _truthy(take("stairs"))
    elevator = _truthy(take("elevator"))
    system_text = take("structural_system")
    system = _structural_system(system_text)
    if system_text and system is not StructuralSystem.UNDETERMINED and "moment" not in str(system_text).lower():
        notes.append(
            {
                "field": "structural_system",
                "origin": "ASSUMED",
                "value": system.value,
                "note": "A concrete or steel description was mapped to a moment frame for layout.",
            }
        )
    project_type = take("project_type")
    occupancy = OccupancyKind.UNKNOWN
    if isinstance(project_type, str) and "resid" in project_type.lower():
        occupancy = OccupancyKind.RESIDENTIAL
    text_only = {
        name: value
        for name in (
            "location",
            "required_rooms",
            "room_areas",
            "circulation",
            "shafts",
            "entrances",
            "accessibility",
            "architectural_preferences",
            "facade",
            "engineer_notes",
            "units",
        )
        if (value := take(name)) is not None
    }
    model = BuildingBrief(
        raw_text=_raw_text(fields),
        language=BriefLanguage.EN,
        plot_length_m=plot_length,
        plot_width_m=plot_width,
        frontage_m=frontage,
        setback_front_m=setback_front,
        setback_rear_m=setback_rear,
        setback_side_m=setback_side,
        has_piloti=piloti,
        parking_space_count=parking,
        residential_floor_count=residential,
        apartments_per_floor=apartments,
        bedrooms_per_apartment=bedrooms,
        requires_stair=stairs,
        requires_elevator=elevator,
        storey_height_m=storey_height,
        occupancy=occupancy,
        structural_system=system,
        metadata={
            "source": "architectural_brief",
            "field_provenance": notes,
            "story_heights": heights,
            "text_only": text_only,
        },
    )
    return model, notes


def production_qa_gates(
    *,
    pem: ProjectEngineeringModel,
    coordination: dict[str, Any],
    internal_analysis: dict[str, Any],
    design_checks: list[dict[str, Any]],
    drawings: dict[str, Any],
    external: list[dict[str, Any]],
    snapshot_id: str,
) -> list[dict[str, Any]]:
    building = pem.building_model
    architecture = "PASS" if building.floor_plans and building.site is not None else "FAIL"
    members = pem.structural_model.members.members
    structure = "PASS" if members else "FAIL"
    coordination_status = "FAIL" if coordination.get("hard_count") else "PASS"
    loads = "PASS" if pem.structural_model.load_cases else "UNAVAILABLE"
    analysis_status = "PASS" if internal_analysis.get("executed") is True else "NOT_RUN"
    recognized = [item for item in design_checks if item.get("recognized") is True]
    if any(item.get("status") == "FAIL" for item in recognized):
        design_status = "FAIL"
    elif recognized:
        design_status = "PASS"
    else:
        design_status = "NOT_APPLICABLE"
    sheet_numbers = set(drawings.get("sheet_numbers") or [])
    drawing_status = "PASS" if {"A-001", "S-001", "S-201", "S-202", "S-203"} <= sheet_numbers else "NOT_RUN"
    trace = "PASS" if snapshot_id else "FAIL"
    gates = [
        {"name": "architectural_completeness", "status": architecture, "authority": "PEM"},
        {"name": "structural_model_completeness", "status": structure, "authority": "PEM"},
        {"name": "architecture_structure_coordination", "status": coordination_status, "authority": "PEM"},
        {"name": "load_completeness", "status": loads, "authority": "PEM"},
        {"name": "internal_analysis_execution", "status": analysis_status, "authority": "INTERNAL"},
        {"name": "internal_design_execution", "status": design_status, "authority": "INTERNAL"},
        {"name": "drawing_completeness", "status": drawing_status, "authority": "PEM"},
        {"name": "pem_traceability", "status": trace, "authority": "PEM"},
    ]
    for item in external:
        gates.append(
            {
                "name": f"{item['software'].lower()}_execution",
                "status": item["status"] if item["executed"] else "REQUIRES_LOCAL_SOFTWARE",
                "authority": "EXTERNAL SOFTWARE RESULT",
                "executed": item["executed"],
            }
        )
    return gates


def summarize_production_qa(gates: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = {item["status"] for item in gates}
    external = [item for item in gates if item.get("authority") == "EXTERNAL SOFTWARE RESULT"]
    if "FAIL" in statuses:
        status = "FAIL"
        reason = "A required model, coordination, or design check failed."
    elif any(item.get("executed") is not True for item in external):
        status = "UNAVAILABLE"
        reason = (
            "ETABS, SAFE, or AutoCAD did not execute. "
            "A missing external execution is not a QA pass."
        )
    elif statuses <= {"PASS", "NOT_APPLICABLE"}:
        status = "PASS"
        reason = "Required checks passed and every requested external application executed."
    else:
        status = "NOT_RUN"
        reason = "QA is waiting for model or analysis information."
    return {"status": status, "reason": reason, "gates": gates, "final_engineering_approval": False}


def detail_sheet_status() -> list[dict[str, str]]:
    return [
        {"sheet": name, "status": "NOT_AVAILABLE_IN_PEM", "reason": reason}
        for name, reason in _DETAIL_SHEETS
    ]


def execution_contract(
    *,
    software: str,
    version: str | None,
    execution_id: str,
    executed: bool,
    status: str,
    model_reference: str | None,
    input_snapshot_id: str | None,
    output_reference: str | None,
    warnings: list[str],
    errors: list[str],
    provenance: dict[str, Any],
) -> dict[str, Any]:
    return {
        "software": software,
        "version": version,
        "execution_id": execution_id,
        "executed": executed,
        "status": status,
        "model_reference": model_reference,
        "input_snapshot_id": input_snapshot_id,
        "output_reference": output_reference,
        "warnings": warnings,
        "errors": errors,
        "provenance": provenance,
    }


def _apply_architecture(
    services: Any,
    *,
    project_id: UUID,
    pem: ProjectEngineeringModel,
    model_brief: BuildingBrief,
    requested: bool,
    actor_id: str | None,
) -> dict[str, Any]:
    if not requested:
        return {
            "applied": False,
            "source": "not_applied",
            "approval_state": "NOT_REQUESTED",
            "reason": "The architectural brief was not written. A chat message does not change the PEM.",
        }
    if pem.structural_model.members.members:
        return {
            "applied": False,
            "source": "refused",
            "approval_state": "NOT_REQUESTED",
            "reason": "The current PEM already has structural members. Architecture was not written over it.",
        }
    missing = model_brief.missing_critical_inputs()
    pipeline = getattr(services, "building_design_pipeline", None)
    if missing or pipeline is None:
        return {
            "applied": False,
            "source": "not_applied",
            "approval_state": "NOT_REQUESTED",
            "reason": "Plot dimensions and floor count are required before architecture can be generated.",
            "missing": missing,
        }
    result = pipeline.generate_from_structured_brief(
        project_id,
        model_brief,
        created_by=actor_id,
        generate_drawings=False,
    )
    if result.snapshot_id is None:
        return {
            "applied": False,
            "source": "BuildingDesignPipeline",
            "approval_state": "NOT_REQUESTED",
            "reason": "The model builder did not change the PEM.",
            "missing": result.assembled.missing_inputs,
        }
    return {
        "applied": True,
        "source": "architectural_brief",
        "approval_state": "PENDING" if result.approval_request_id else "NOT_REQUESTED",
        "approval_request_id": str(result.approval_request_id) if result.approval_request_id else None,
        "snapshot_id": str(result.snapshot_id),
        "pem_version": result.pem_version,
        "reason": "Architecture and the derived structural proposal were saved as a PEM revision.",
    }


def _solver_execution(solver: Any, project_id: UUID, software: IntegrationSoftware, *, pem_version: int, actor_id: str | None) -> dict[str, Any]:
    outcome = solver.run_solver_analysis(
        project_id,
        software,
        analysis_type="STATIC",
        pem_version=pem_version,
        created_by=actor_id,
    )
    status = str(outcome.get("status") or outcome.get("solver_status") or "REQUIRES_LOCAL_SOFTWARE")
    executed = status == "SUCCESS" and outcome.get("engineering_results_available") is True
    errors = [] if executed else [str(outcome.get("message") or "The local application did not execute.")]
    return execution_contract(
        software=software.value,
        version=str(outcome.get("solver_status") or ""),
        execution_id=str(outcome.get("integration_execution_id") or uuid4()),
        executed=executed,
        status="SUCCESS" if executed else "REQUIRES_LOCAL_SOFTWARE",
        model_reference=None,
        input_snapshot_id=None,
        output_reference=None,
        warnings=[],
        errors=errors,
        provenance={
            "pem_version": pem_version,
            "project_id": str(project_id),
            "capability_status": outcome.get("capability_status") or outcome.get("solver_status"),
            "engineering_results_available": False if not executed else True,
            "source": "existing_csi_adapter",
        },
    )


def _autocad_execution(project_id: UUID, *, snapshot_id: str) -> dict[str, Any]:
    from app.infrastructure.integrations.autocad_adapter import AutocadAdapter

    result = AutocadAdapter().generate_drawing(project_id, parameters={"source": "pem", "snapshot_id": snapshot_id})
    executed = result.status.value == "SUCCESS"
    return execution_contract(
        software="AUTOCAD",
        version=result.metadata.get("detected_version") or result.metadata.get("version"),
        execution_id=str(uuid4()),
        executed=executed,
        status="SUCCESS" if executed else "REQUIRES_LOCAL_SOFTWARE",
        model_reference=None,
        input_snapshot_id=snapshot_id,
        output_reference=None,
        warnings=["A platform DXF or PDF sheet is not an AutoCAD execution."],
        errors=[] if executed else [result.message],
        provenance={
            "project_id": str(project_id),
            "pem_snapshot_id": snapshot_id,
            "adapter_status": result.status.value,
            "source": "autocad_adapter",
        },
    )


def _coordination_record(pem: ProjectEngineeringModel) -> dict[str, Any]:
    result = CoordinationService().check(pem.building_model, pem.structural_model)
    return {
        "hard_count": result.hard_count,
        "soft_count": result.soft_count,
        "requires_review": result.requires_review,
        "conflicts": [
            {
                "severity": item.severity,
                "code": item.code,
                "message": item.message,
                "element_ids": item.element_ids,
            }
            for item in result.conflicts
        ],
    }


def _external_analysis_view(external: list[dict[str, Any]]) -> dict[str, Any]:
    etabs = next(item for item in external if item["software"] == "ETABS")
    return {
        "solver": "ETABS",
        "requested": True,
        "available": etabs["executed"],
        "executed": etabs["executed"],
        "status": etabs["status"],
        "solver_status": etabs["status"],
        "reason": etabs["errors"][0] if etabs["errors"] else None,
        "engineer_message": etabs["errors"][0] if etabs["errors"] else "ETABS analysis completed.",
        "analysis_run_id": None,
        "integration_execution_id": etabs["execution_id"],
        "external_software_result": etabs["executed"],
    }


def _production_report(**kwargs: Any) -> dict[str, Any]:
    pem: ProjectEngineeringModel = kwargs["pem"]
    learning = kwargs["learning"]
    return {
        "1_project_information": {"name": pem.metadata.name, "request": kwargs["user_request"]},
        "2_architectural_brief": kwargs["brief"],
        "3_architectural_assumptions": [
            item for item in kwargs["brief_notes"] if item.get("origin") in {"ASSUMED", "DERIVED"}
        ],
        "4_structural_system": pem.structural_system,
        "5_materials": [item.name for item in pem.structural_model.materials.concrete + pem.structural_model.materials.steel],
        "6_geometry": {
            "floors": len(pem.building_model.floor_plans),
            "members": len(pem.structural_model.members.members),
        },
        "7_loads": [item.name for item in pem.structural_model.load_cases],
        "8_load_combinations": [item.name for item in pem.structural_model.load_combinations],
        "9_analysis_software": "internal preliminary analysis; ETABS is recorded separately",
        "10_analysis_execution_status": kwargs["internal_analysis"].get("status"),
        "11_design_software": "existing internal design engine; ETABS and SAFE design are recorded separately",
        "12_design_execution_status": kwargs["qa"]["status"],
        "13_design_checks": kwargs["design_checks"],
        "14_qa": kwargs["qa"],
        "15_learning_context": learning,
        "16_pem_provenance": {
            "heading": "AUTHORITATIVE ENGINEERING INPUT",
            "pem_version": kwargs["meta_version"],
            "pem_snapshot_id": kwargs["snapshot_id"],
            "change": kwargs["change"],
        },
        "17_drawing_package": kwargs["drawings"],
        "18_external_software_execution_records": kwargs["external"],
        "19_warnings": kwargs["coordination"]["conflicts"],
        "20_final_engineering_readiness": {
            "status": kwargs["qa"]["status"],
            "final_engineering_approval": False,
            "statement": "Learning context did not approve this package.",
        },
        "authority": {
            "AUTHORITATIVE ENGINEERING INPUT": "current PEM snapshot",
            "DERIVED": "values marked DERIVED in the architectural notes",
            "ASSUMED": "values marked ASSUMED in the architectural notes",
            "LEARNING CONTEXT": learning,
            "EXTERNAL SOFTWARE RESULT": kwargs["external"],
        },
    }


def _engineer_message(change: dict[str, Any], qa: dict[str, Any], missing_software: list[str]) -> str:
    software = ", ".join(missing_software) if missing_software else "none"
    return (
        f"Architecture write: {change.get('reason')} "
        f"QA status is {qa['status']}. "
        f"External applications not executed: {software}."
    )


def _provided(fields: dict[str, Any], name: str) -> bool:
    item = fields.get(name)
    return bool(item) and item.get("origin") != "UNAVAILABLE" and item.get("value") not in (None, "")


def _number(fields: dict[str, Any], name: str) -> float | None:
    if not _provided(fields, name):
        return None
    return _as_float(fields[name].get("value"))


def _numbers(value: Any) -> list[float]:
    if value is None:
        return []
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return [float(value)]
    parts = str(value).replace(";", ",").split(",")
    numbers: list[float] = []
    for part in parts:
        parsed = _as_float(part.strip())
        if parsed is not None:
            numbers.append(parsed)
    return numbers


def _integer(value: Any) -> int | None:
    number = _as_float(value)
    if number is None:
        return None
    return int(number)


def _as_float(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower().replace("m", "")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "required", "y"}


def _structural_system(value: Any) -> StructuralSystem:
    text = str(value or "").lower()
    if "shear" in text:
        return StructuralSystem.RC_FRAME_WITH_SHEAR_WALLS
    if "steel" in text:
        return StructuralSystem.STEEL_MOMENT_FRAME
    if any(token in text for token in ("rc", "concrete", "reinforced")):
        return StructuralSystem.RC_MOMENT_FRAME
    return StructuralSystem.UNDETERMINED


def _raw_text(fields: dict[str, Any]) -> str:
    parts = []
    for name, item in fields.items():
        if item.get("origin") == "UNAVAILABLE" or item.get("value") in (None, ""):
            continue
        parts.append(f"{name}={item.get('value')}")
    return "; ".join(parts)
