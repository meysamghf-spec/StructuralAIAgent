"""Optimization routine extension points — deterministic routines only."""

from __future__ import annotations

from typing import Any

from app.application.code_engine_service import CodeEngineService
from app.application.optimization_calculations import run_multi_member_optimization
from app.domain.models.optimization import OptimizationStatus
from app.domain.models.pem import ProjectEngineeringModel


class OptimizationRoutineResult:
    def __init__(
        self,
        *,
        status: OptimizationStatus,
        capability_status: str,
        message: str,
        outputs: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.capability_status = capability_status
        self.message = message
        self.outputs = outputs or {}


def run_optimization_routine(
    *,
    optimization_type: str,
    objective: str,
    pem: ProjectEngineeringModel,
    constraints: dict[str, Any],
    analysis_outputs: dict[str, Any] | None,
    design_outputs: dict[str, Any] | None,
    engineering_results: dict[str, Any] | None,
    parameters: dict[str, Any],
    code_engine: CodeEngineService | None = None,
) -> OptimizationRoutineResult:
    normalized = optimization_type.strip().upper()
    base_outputs = {
        "routine_connected": True,
        "engineering_optimization_results_available": False,
        "optimization_type": normalized,
        "objective": objective,
    }

    if engineering_results is None:
        return OptimizationRoutineResult(
            status=OptimizationStatus.REQUIRES_ANALYSIS,
            capability_status=OptimizationStatus.REQUIRES_ANALYSIS.value,
            message="Validated analysis results are required before optimization can run.",
            outputs={**base_outputs, "routine_connected": False},
        )

    if normalized in {"WEIGHT", "MEMBER_SIZE", "MATERIAL_EFFICIENCY", "ESTIMATED_COST"}:
        result = run_multi_member_optimization(
            pem=pem,
            engineering_results=engineering_results,
            constraints=constraints,
            code_engine=code_engine,
            parameters={**parameters, "objective": _objective_key(objective, normalized)},
            objective=_objective_key(objective, normalized),
        )
        status = OptimizationStatus(result["status"])
        available = status == OptimizationStatus.PASS
        return OptimizationRoutineResult(
            status=status,
            capability_status=status.value,
            message=result["message"],
            outputs={
                **base_outputs,
                "engineering_optimization_results_available": available,
                "optimization_mode": result.get("optimization_mode"),
                "member_results": result.get("member_results", []),
                "shared_section_groups": result.get("shared_section_groups", []),
                "candidates": result.get("candidates", []),
                "selected_candidate": result.get("selected_candidate"),
                "member_id": result.get("member_id"),
                "candidate_count": result.get("candidate_count", 0),
                "evaluated_candidate_count": result.get("evaluated_candidate_count", 0),
                "code_reference": pem.code_configuration.governing_building_code.edition,
            },
        )

    return OptimizationRoutineResult(
        status=OptimizationStatus.NOT_IMPLEMENTED,
        capability_status=OptimizationStatus.NOT_IMPLEMENTED.value,
        message=f"Optimization type '{normalized}' is not implemented yet.",
        outputs={**base_outputs, "routine_connected": False},
    )


def _objective_key(objective: str, optimization_type: str) -> str:
    normalized = objective.strip().lower()
    if normalized:
        if "cost" in normalized:
            return "minimize_cost_proxy"
        if "area" in normalized or "material" in normalized:
            return "minimize_area"
        if "weight" in normalized:
            return "minimize_weight_proxy"
        return normalized.replace(" ", "_")
    mapping = {
        "WEIGHT": "minimize_weight_proxy",
        "MEMBER_SIZE": "minimize_weight_proxy",
        "MATERIAL_EFFICIENCY": "minimize_area",
        "ESTIMATED_COST": "minimize_cost_proxy",
    }
    return mapping.get(optimization_type.upper(), "minimize_weight_proxy")
