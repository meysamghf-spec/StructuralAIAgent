"""Deterministic optimization using validated design and analysis outputs."""

from __future__ import annotations

from typing import Any

from app.application.code_engine_service import CodeEngineService
from app.application.design_calculations import evaluate_member_section_design
from app.domain.models.design import DesignStatus
from app.domain.models.optimization import OptimizationMode, OptimizationStatus
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import MemberType, StructuralMember


def run_weight_optimization(
    *,
    pem: ProjectEngineeringModel,
    engineering_results: dict[str, Any],
    design_outputs: dict[str, Any] | None,
    constraints: dict[str, Any],
    code_engine: CodeEngineService | None = None,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backward-compatible entry point; delegates to multi-member optimization."""
    return run_multi_member_optimization(
        pem=pem,
        engineering_results=engineering_results,
        constraints=constraints,
        code_engine=code_engine,
        parameters=parameters or {},
        objective=str((parameters or {}).get("objective") or constraints.get("objective") or "minimize_weight_proxy"),
    )


def run_multi_member_optimization(
    *,
    pem: ProjectEngineeringModel,
    engineering_results: dict[str, Any],
    constraints: dict[str, Any],
    code_engine: CodeEngineService | None = None,
    parameters: dict[str, Any],
    objective: str = "minimize_weight_proxy",
) -> dict[str, Any]:
    if code_engine is None:
        return {
            "status": OptimizationStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "Code engine is required for deterministic section optimization.",
            "candidates": [],
        }

    mode = _resolve_optimization_mode(parameters)
    members = _resolve_target_members(pem, parameters)
    if not members:
        return {
            "status": OptimizationStatus.MODEL_NOT_READY.value,
            "message": "No optimizable members were selected in the engineering model.",
            "candidates": [],
        }

    max_utilization = float(constraints.get("max_utilization", 1.0))
    if mode == OptimizationMode.SHARED_SECTION:
        return _run_shared_section_optimization(
            pem=pem,
            members=members,
            engineering_results=engineering_results,
            code_engine=code_engine,
            parameters=parameters,
            constraints=constraints,
            objective=objective,
            max_utilization=max_utilization,
        )

    return _run_independent_optimization(
        pem=pem,
        members=members,
        engineering_results=engineering_results,
        code_engine=code_engine,
        parameters=parameters,
        objective=objective,
        max_utilization=max_utilization,
    )


def _run_independent_optimization(
    *,
    pem: ProjectEngineeringModel,
    members: list[StructuralMember],
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    parameters: dict[str, Any],
    objective: str,
    max_utilization: float,
) -> dict[str, Any]:
    member_results: list[dict[str, Any]] = []
    all_candidates: list[dict[str, Any]] = []
    total_evaluated = 0

    for member in members:
        member_result = _optimize_single_member(
            pem=pem,
            member=member,
            engineering_results=engineering_results,
            code_engine=code_engine,
            parameters=parameters,
            objective=objective,
            max_utilization=max_utilization,
        )
        member_results.append(member_result)
        all_candidates.extend(member_result.get("candidates", []))
        total_evaluated += int(member_result.get("evaluated_candidate_count", 0))

    successful = [item for item in member_results if item.get("selected_section_id")]
    if not successful:
        first_failure = member_results[0] if member_results else {}
        return {
            "status": first_failure.get("status", OptimizationStatus.REQUIRES_ENGINEER_REVIEW.value),
            "message": _independent_failure_message(member_results),
            "optimization_mode": OptimizationMode.INDEPENDENT.value,
            "objective": objective,
            "member_results": member_results,
            "candidates": all_candidates,
            "candidate_count": len(all_candidates),
            "evaluated_candidate_count": total_evaluated,
        }

    first_selected = successful[0]
    return {
        "status": OptimizationStatus.PASS.value,
        "message": (
            f"Independent section optimization completed for {len(successful)} member(s) "
            f"using objective '{objective}'."
        ),
        "optimization_mode": OptimizationMode.INDEPENDENT.value,
        "objective": objective,
        "member_results": member_results,
        "shared_section_groups": [],
        "selected_candidate": first_selected.get("selected_candidate"),
        "member_id": first_selected.get("member_id"),
        "candidates": all_candidates,
        "candidate_count": len(all_candidates),
        "evaluated_candidate_count": total_evaluated,
    }


def _run_shared_section_optimization(
    *,
    pem: ProjectEngineeringModel,
    members: list[StructuralMember],
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    parameters: dict[str, Any],
    constraints: dict[str, Any],
    objective: str,
    max_utilization: float,
) -> dict[str, Any]:
    compatibility = {_member_compatibility_key(pem, member) for member in members}
    if len(compatibility) != 1:
        return {
            "status": OptimizationStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "Shared-section optimization requires members of the same type and material discipline.",
            "optimization_mode": OptimizationMode.SHARED_SECTION.value,
            "member_results": [],
        }

    candidate_sections = _shared_candidate_sections(pem, members[0], parameters)
    if not candidate_sections:
        return {
            "status": OptimizationStatus.MODEL_NOT_READY.value,
            "message": "No candidate sections are available for shared-section optimization.",
            "optimization_mode": OptimizationMode.SHARED_SECTION.value,
        }

    evaluated: list[dict[str, Any]] = []
    feasible: list[dict[str, Any]] = []
    member_evaluations: list[dict[str, Any]] = []

    for section in candidate_sections:
        section_evaluations: list[dict[str, Any]] = []
        rejected_reasons: list[str] = []
        max_member_utilization = 0.0
        all_pass = True

        for member in members:
            evaluation = _evaluate_candidate(
                pem=pem,
                member=member,
                section=section,
                engineering_results=engineering_results,
                code_engine=code_engine,
                parameters=parameters,
                max_utilization=max_utilization,
            )
            section_evaluations.append(evaluation)
            if not evaluation["feasible"]:
                all_pass = False
                rejected_reasons.append(
                    f"{member.name}: {evaluation.get('rejection_reason', 'failed checks')}"
                )
            max_member_utilization = max(
                max_member_utilization,
                float(evaluation.get("governing_utilization") or 0.0),
            )

        record = {
            **section,
            "feasible": all_pass,
            "governing_utilization": round(max_member_utilization, 4),
            "objective_value": _objective_value(section, objective),
            "member_evaluations": section_evaluations,
            "rejection_reasons": rejected_reasons,
        }
        evaluated.append(record)
        if all_pass:
            feasible.append(record)

    member_results = [
        {
            "member_id": member.id,
            "member_name": member.name,
            "member_type": member.member_type.value,
            "status": OptimizationStatus.PASS.value if feasible else OptimizationStatus.REQUIRES_ENGINEER_REVIEW.value,
        }
        for member in members
    ]

    if not feasible:
        return {
            "status": OptimizationStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "No shared section satisfies all members in the selected group.",
            "optimization_mode": OptimizationMode.SHARED_SECTION.value,
            "objective": objective,
            "member_results": member_results,
            "shared_section_groups": [],
            "candidates": evaluated,
            "candidate_count": len(candidate_sections),
            "evaluated_candidate_count": len(evaluated),
        }

    selected = _select_best_candidate(feasible, objective)
    shared_group = {
        "member_ids": [member.id for member in members],
        "member_names": [member.name for member in members],
        "selected_section_id": selected["section_id"],
        "selected_section_name": selected["section_name"],
        "governing_utilization": selected["governing_utilization"],
        "objective_value": selected["objective_value"],
    }

    for item in member_results:
        item["selected_section_id"] = selected["section_id"]
        item["selected_section_name"] = selected["section_name"]
        item["governing_utilization"] = selected["governing_utilization"]
        item["selected_candidate"] = {
            "section_id": selected["section_id"],
            "section_name": selected["section_name"],
            "utilization": selected["governing_utilization"],
            "weight_proxy": selected["objective_value"],
            "feasible": True,
        }

    return {
        "status": OptimizationStatus.PASS.value,
        "message": (
            f"Shared section '{selected['section_name']}' selected for "
            f"{len(members)} compatible member(s)."
        ),
        "optimization_mode": OptimizationMode.SHARED_SECTION.value,
        "objective": objective,
        "member_results": member_results,
        "shared_section_groups": [shared_group],
        "selected_candidate": shared_group,
        "member_id": members[0].id,
        "candidates": evaluated,
        "candidate_count": len(candidate_sections),
        "evaluated_candidate_count": len(evaluated),
    }


def _optimize_single_member(
    *,
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    parameters: dict[str, Any],
    objective: str,
    max_utilization: float,
) -> dict[str, Any]:
    candidate_sections = _member_candidate_sections(pem, member, parameters)
    if not candidate_sections:
        return {
            "member_id": member.id,
            "member_name": member.name,
            "member_type": member.member_type.value,
            "status": OptimizationStatus.MODEL_NOT_READY.value,
            "message": f"No candidate sections are defined for member '{member.name}'.",
            "candidates": [],
            "candidate_count": 0,
            "evaluated_candidate_count": 0,
        }

    evaluated: list[dict[str, Any]] = []
    for section in candidate_sections:
        evaluated.append(
            _evaluate_candidate(
                pem=pem,
                member=member,
                section=section,
                engineering_results=engineering_results,
                code_engine=code_engine,
                parameters=parameters,
                max_utilization=max_utilization,
            )
        )

    feasible = [item for item in evaluated if item["feasible"]]
    if not feasible:
        return {
            "member_id": member.id,
            "member_name": member.name,
            "member_type": member.member_type.value,
            "status": OptimizationStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": f"No valid section satisfies constraints for member '{member.name}'.",
            "candidates": evaluated,
            "rejected_candidates": [item for item in evaluated if not item["feasible"]],
            "candidate_count": len(candidate_sections),
            "evaluated_candidate_count": len(evaluated),
        }

    selected = _select_best_candidate(feasible, objective)
    return {
        "member_id": member.id,
        "member_name": member.name,
        "member_type": member.member_type.value,
        "status": OptimizationStatus.PASS.value,
        "selected_section_id": selected["section_id"],
        "selected_section_name": selected["section_name"],
        "governing_utilization": selected["governing_utilization"],
        "selected_candidate": selected,
        "candidates": evaluated,
        "rejected_candidates": [item for item in evaluated if not item["feasible"]],
        "candidate_count": len(candidate_sections),
        "evaluated_candidate_count": len(evaluated),
    }


def _evaluate_candidate(
    *,
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    section: dict[str, Any],
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    parameters: dict[str, Any],
    max_utilization: float,
) -> dict[str, Any]:
    design = evaluate_member_section_design(
        pem=pem,
        member=member,
        engineering_results=engineering_results,
        code_engine=code_engine,
        section_id=section["section_id"],
        section_name=section["section_name"],
        width=float(section["width"]),
        depth=float(section["depth"]),
        parameters=parameters,
    )
    utilization = float(design.get("governing_utilization") or 0.0)
    status = design.get("status")
    feasible = status == DesignStatus.PASS.value and utilization <= max_utilization
    rejection_reason = None
    if status == DesignStatus.REQUIRES_ANALYSIS.value:
        rejection_reason = "missing analysis demand"
    elif status != DesignStatus.PASS.value:
        rejection_reason = design.get("message", "design checks failed")
    elif utilization > max_utilization:
        rejection_reason = f"utilization {utilization:.3f} exceeds limit {max_utilization:.3f}"

    return {
        "section_id": section["section_id"],
        "section_name": section["section_name"],
        "width": section["width"],
        "depth": section["depth"],
        "utilization": round(utilization, 4),
        "governing_utilization": round(utilization, 4),
        "objective_value": _objective_value(section, parameters.get("objective") or "minimize_weight_proxy"),
        "weight_proxy": _objective_value(section, "minimize_weight_proxy"),
        "feasible": feasible,
        "design_status": status,
        "rejection_reason": rejection_reason,
        "checks": design.get("checks", []),
    }


def _select_best_candidate(candidates: list[dict[str, Any]], objective: str) -> dict[str, Any]:
    normalized = objective.strip().lower()

    def sort_key(item: dict[str, Any]) -> tuple[float, str, float, str]:
        objective_value = float(item.get("objective_value", item.get("weight_proxy", 0.0)))
        utilization = float(item.get("governing_utilization", item.get("utilization", 0.0)))
        return (
            objective_value,
            str(item.get("section_id", "")),
            utilization,
            str(item.get("section_name", "")),
        )

    if normalized in {"minimize_area", "minimize_section_area", "material_efficiency"}:
        return min(
            candidates,
            key=lambda item: (
                float(item.get("width", 0.0)) * float(item.get("depth", 0.0)),
                str(item.get("section_id", "")),
                str(item.get("section_name", "")),
            ),
        )

    return min(candidates, key=sort_key)


def _objective_value(section: dict[str, Any], objective: str) -> float:
    normalized = objective.strip().lower()
    width = float(section.get("width", 0.0))
    depth = float(section.get("depth", 0.0))
    area = width * depth
    if normalized in {"minimize_area", "minimize_section_area"}:
        return round(area, 4)
    if normalized in {"estimated_cost", "minimize_cost", "minimize_cost_proxy"}:
        return round(area * 1.05, 4)
    return round(area, 4)


def _resolve_optimization_mode(parameters: dict[str, Any]) -> OptimizationMode:
    raw = str(parameters.get("optimization_mode", OptimizationMode.INDEPENDENT.value)).upper()
    if raw == OptimizationMode.SHARED_SECTION.value:
        return OptimizationMode.SHARED_SECTION
    return OptimizationMode.INDEPENDENT


def _resolve_target_members(
    pem: ProjectEngineeringModel,
    parameters: dict[str, Any],
) -> list[StructuralMember]:
    member_ids = parameters.get("member_ids")
    if member_ids:
        id_set = {str(item) for item in member_ids}
        selected = [
            member
            for member in pem.structural_model.members.members
            if member.id in id_set
        ]
        return sorted(selected, key=lambda item: item.id)

    member_id = parameters.get("member_id")
    if member_id:
        for member in pem.structural_model.members.members:
            if member.id == member_id:
                return [member]

    optimizable_types = {
        MemberType.BEAM,
        MemberType.COLUMN,
        MemberType.BRACE,
    }
    selected = [
        member
        for member in pem.structural_model.members.members
        if member.member_type in optimizable_types
    ]
    if selected:
        return [sorted(selected, key=lambda item: item.id)[0]]
    return []


def _member_candidate_sections(
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    explicit_ids = parameters.get("candidate_section_ids")
    sections = _sections_for_member(pem, member)
    if explicit_ids:
        allowed = {str(item) for item in explicit_ids}
        sections = [item for item in sections if item["section_id"] in allowed]
    return sorted(sections, key=lambda item: item["section_id"])


def _shared_candidate_sections(
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    parameters: dict[str, Any],
) -> list[dict[str, Any]]:
    return _member_candidate_sections(pem, member, parameters)


def _sections_for_member(pem: ProjectEngineeringModel, member: StructuralMember) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    if member.member_type == MemberType.COLUMN:
        for section in pem.structural_model.sections.columns:
            sections.append(
                {
                    "section_id": section.id,
                    "section_name": section.name,
                    "width": float(section.width),
                    "depth": float(section.depth),
                }
            )
        for section in pem.structural_model.sections.beams:
            sections.append(
                {
                    "section_id": section.id,
                    "section_name": section.name,
                    "width": float(section.width),
                    "depth": float(section.depth),
                }
            )
    else:
        for section in pem.structural_model.sections.beams:
            sections.append(
                {
                    "section_id": section.id,
                    "section_name": section.name,
                    "width": float(section.width),
                    "depth": float(section.depth),
                }
            )
    return sections


def _member_compatibility_key(pem: ProjectEngineeringModel, member: StructuralMember) -> str:
    if _find_concrete_material(pem, member.material_id):
        discipline = "CONCRETE"
    elif any(item.id == member.material_id for item in pem.structural_model.materials.steel):
        discipline = "STEEL"
    else:
        discipline = "UNKNOWN"
    return f"{discipline}:{member.member_type.value}"


def _find_concrete_material(pem: ProjectEngineeringModel, material_id: str) -> bool:
    return any(item.id == material_id for item in pem.structural_model.materials.concrete)


def _independent_failure_message(member_results: list[dict[str, Any]]) -> str:
    messages = [str(item.get("message")) for item in member_results if item.get("message")]
    if messages:
        return messages[0]
    return "No valid section could be selected for the requested members."
