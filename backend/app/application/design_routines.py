"""Design calculation routine extension points — deterministic routines only."""

from __future__ import annotations

from typing import Any

from app.application.code_engine_service import CodeEngineService
from app.application.design_calculations import (
    run_concrete_beam_design,
    run_concrete_column_design,
    run_steel_member_design,
    select_target_member,
)
from app.domain.models.design import (
    CONCRETE_DESIGN_TYPES,
    STEEL_DESIGN_TYPES,
    DesignStatus,
)
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import MemberType


class DesignRoutineResult:
    def __init__(
        self,
        *,
        status: DesignStatus,
        capability_status: str,
        message: str,
        outputs: dict[str, Any] | None = None,
    ) -> None:
        self.status = status
        self.capability_status = capability_status
        self.message = message
        self.outputs = outputs or {}


def run_design_routine(
    *,
    design_type: str,
    pem: ProjectEngineeringModel,
    analysis_outputs: dict[str, Any],
    engineering_results: dict[str, Any] | None,
    code_engine: CodeEngineService | None,
    parameters: dict[str, Any],
) -> DesignRoutineResult:
    normalized = design_type.strip().upper()

    base_outputs = {
        "routine_connected": True,
        "engineering_design_results_available": False,
        "design_type": normalized,
        "analysis_run_id": analysis_outputs.get("result_set_id"),
        "result_validation_status": analysis_outputs.get("result_validation_status"),
    }

    if engineering_results is None or code_engine is None:
        return DesignRoutineResult(
            status=DesignStatus.REQUIRES_ANALYSIS,
            capability_status=DesignStatus.REQUIRES_ANALYSIS.value,
            message="Validated engineering results are required before deterministic design checks can run.",
            outputs={**base_outputs, "routine_connected": False},
        )

    if normalized in CONCRETE_DESIGN_TYPES:
        if normalized == "CONCRETE_COLUMN":
            member = select_target_member(
                pem,
                parameters,
                member_types={MemberType.COLUMN},
            )
            if member is None:
                return DesignRoutineResult(
                    status=DesignStatus.MODEL_NOT_READY,
                    capability_status=DesignStatus.MODEL_NOT_READY.value,
                    message="No concrete column is available in the engineering model for design checks.",
                    outputs=base_outputs,
                )
            result = run_concrete_column_design(
                pem=pem,
                member=member,
                engineering_results=engineering_results,
                code_engine=code_engine,
                parameters=parameters,
            )
        else:
            member = select_target_member(
                pem,
                parameters,
                member_types={MemberType.BEAM, MemberType.COLUMN},
            )
            if member is None:
                return DesignRoutineResult(
                    status=DesignStatus.MODEL_NOT_READY,
                    capability_status=DesignStatus.MODEL_NOT_READY.value,
                    message="No concrete member is available in the engineering model for design checks.",
                    outputs=base_outputs,
                )
            if member.member_type == MemberType.COLUMN and normalized == "CONCRETE_MEMBER":
                result = run_concrete_column_design(
                    pem=pem,
                    member=member,
                    engineering_results=engineering_results,
                    code_engine=code_engine,
                    parameters=parameters,
                )
            else:
                result = run_concrete_beam_design(
                    pem=pem,
                    member=member,
                    engineering_results=engineering_results,
                    code_engine=code_engine,
                    parameters=parameters,
                )
        status = DesignStatus(result["status"])
        available = status == DesignStatus.PASS
        return DesignRoutineResult(
            status=status,
            capability_status=status.value,
            message=result["message"],
            outputs={
                **base_outputs,
                "engineering_design_results_available": available,
                "discipline": "CONCRETE",
                "code_reference": pem.code_configuration.concrete_edition,
                "member_results": [result],
                "governing_utilization": result.get("governing_utilization"),
                "checks": result.get("checks", []),
            },
        )

    if normalized in STEEL_DESIGN_TYPES:
        member = select_target_member(
            pem,
            parameters,
            member_types={MemberType.BEAM, MemberType.COLUMN, MemberType.BRACE},
        )
        if member is None:
            return DesignRoutineResult(
                status=DesignStatus.MODEL_NOT_READY,
                capability_status=DesignStatus.MODEL_NOT_READY.value,
                message="No steel member is available in the engineering model for design checks.",
                outputs=base_outputs,
            )

        result = run_steel_member_design(
            pem=pem,
            member=member,
            engineering_results=engineering_results,
            code_engine=code_engine,
            parameters=parameters,
        )
        status = DesignStatus(result["status"])
        available = status == DesignStatus.PASS
        return DesignRoutineResult(
            status=status,
            capability_status=status.value,
            message=result["message"],
            outputs={
                **base_outputs,
                "engineering_design_results_available": available,
                "discipline": "STEEL",
                "code_reference": pem.code_configuration.steel_edition,
                "member_results": [result],
                "governing_utilization": result.get("governing_utilization"),
                "checks": result.get("checks", []),
            },
        )

    if normalized in {"FOUNDATION", "SLAB", "WALL"}:
        return DesignRoutineResult(
            status=DesignStatus.NOT_IMPLEMENTED,
            capability_status=DesignStatus.NOT_IMPLEMENTED.value,
            message=f"Design routine for '{normalized}' is not implemented yet.",
            outputs={**base_outputs, "routine_connected": False, "discipline": normalized},
        )

    return DesignRoutineResult(
        status=DesignStatus.NOT_IMPLEMENTED,
        capability_status=DesignStatus.NOT_IMPLEMENTED.value,
        message=f"Unsupported design type '{normalized}'.",
        outputs={**base_outputs, "routine_connected": False},
    )
