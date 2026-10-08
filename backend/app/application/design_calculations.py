"""Deterministic design calculations using CodeEngine plugins and validated analysis demands."""

from __future__ import annotations

import math
from typing import Any

from app.application.code_engine_service import CodeEngineService
from app.domain.models.code_engine import CheckOutcome
from app.domain.models.design import DesignStatus
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import BeamSection, ColumnSection, ConcreteMaterial, MemberType, StructuralMember


def extract_member_force_demand(
    engineering_results: dict[str, Any],
    member_id: str,
    *,
    component: str = "moment",
) -> float | None:
    """Extract governing demand from normalized frame force results."""
    entries = engineering_results.get("frame_forces") or engineering_results.get("frame_moments") or []
    demands: list[float] = []
    for entry in entries:
        if entry.get("source_identifier") != member_id and entry.get("id") != member_id:
            continue
        component_values = _component_values(entry, component)
        if component_values:
            demands.append(max(abs(value) for value in component_values))
            continue
        values = entry.get("values")
        numbers = _flatten_numbers(values)
        if not numbers:
            continue
        if component == "moment":
            demands.append(max(abs(value) for value in numbers))
        elif component == "shear":
            demands.append(max(abs(value) for value in numbers))
        elif component == "axial":
            demands.append(max(abs(value) for value in numbers))
    if not demands:
        return None
    return max(demands)


def _component_values(entry: dict[str, Any], component: str) -> list[float]:
    if component == "axial":
        value = entry.get("axial_force")
        return [float(value)] if isinstance(value, (int, float)) else []
    if component == "shear":
        values = [entry.get("shear_v2"), entry.get("shear_v3")]
        return [float(item) for item in values if isinstance(item, (int, float))]
    if component == "moment":
        values = [entry.get("moment_m2"), entry.get("moment_m3")]
        return [float(item) for item in values if isinstance(item, (int, float))]
    return []


def run_concrete_beam_design(
    *,
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    section = _find_beam_section(pem, member.section_id)
    material = _find_concrete_material(pem, member.material_id)
    if material is None:
        return {
            "status": DesignStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "Member section or material could not be resolved from the engineering model.",
            "checks": [],
        }
    if section is None and parameters.get("width_in") is None:
        return {
            "status": DesignStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "Member section or material could not be resolved from the engineering model.",
            "checks": [],
        }

    mu = extract_member_force_demand(engineering_results, member.id, component="moment")
    vu = extract_member_force_demand(engineering_results, member.id, component="shear")
    if mu is None and vu is None:
        return {
            "status": DesignStatus.REQUIRES_ANALYSIS.value,
            "message": (
                f"No validated frame forces found for member '{member.name}'. "
                "Run analysis with a connected solver first."
            ),
            "checks": [],
        }

    assumptions: list[str] = []
    width_in = _dimension_inches(parameters, section, "width_in", "width", 12.0, assumptions, "width")
    depth_in = _dimension_inches(parameters, section, "depth_in", "depth", 18.0, assumptions, "depth")
    fc_psi = _concrete_fc_psi(material, assumptions)
    fy_psi, fy_note = _rebar_fy_psi(pem, parameters)
    if fy_note:
        assumptions.append(fy_note)
    unit_note = engineering_results.get("design_unit_assumption")
    if isinstance(unit_note, str) and unit_note:
        assumptions.append(unit_note)

    checks: list[dict[str, Any]] = []
    governing_utilization = 0.0
    all_pass = True

    if mu is not None:
        flexure = code_engine.run_check(
            "ACI318-25",
            "CONCRETE_BEAM_FLEXURE",
            {
                "Mu_kipft": mu,
                "fc_psi": fc_psi,
                "fy_psi": fy_psi,
                "width_in": width_in,
                "depth_in": depth_in,
            },
            code_configuration=pem.code_configuration,
        )
        checks.append(flexure.model_dump(mode="json"))
        utilization = flexure.metadata.get("utilization", 0.0)
        governing_utilization = max(governing_utilization, float(utilization or 0.0))
        if flexure.outcome == CheckOutcome.FAIL:
            all_pass = False

    if vu is not None:
        shear = code_engine.run_check(
            "ACI318-25",
            "CONCRETE_BEAM_SHEAR",
            {
                "Vu_kip": vu,
                "fc_psi": fc_psi,
                "width_in": width_in,
                "depth_in": depth_in,
            },
            code_configuration=pem.code_configuration,
        )
        checks.append(shear.model_dump(mode="json"))
        utilization = shear.metadata.get("utilization", 0.0)
        governing_utilization = max(governing_utilization, float(utilization or 0.0))
        if shear.outcome == CheckOutcome.FAIL:
            all_pass = False

    status = DesignStatus.PASS if all_pass else DesignStatus.FAIL
    return {
        "status": status.value,
        "message": (
            f"Concrete beam checks completed for '{member.name}' using {pem.code_configuration.concrete_edition}."
        ),
        "member_id": member.id,
        "member_name": member.name,
        "code_edition": pem.code_configuration.concrete_edition,
        "checks": checks,
        "governing_utilization": round(governing_utilization, 4),
        "calculation_method": "deterministic_code_engine",
        "assumptions": assumptions,
    }


def run_concrete_column_design(
    *,
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    section = _find_column_section(pem, member.section_id) or _find_beam_section(pem, member.section_id)
    material = _find_concrete_material(pem, member.material_id)
    if material is None:
        return {
            "status": DesignStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "Column section or material could not be resolved from the engineering model.",
            "checks": [],
        }
    if section is None and parameters.get("width_in") is None:
        return {
            "status": DesignStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "Column section or material could not be resolved from the engineering model.",
            "checks": [],
        }

    mu = extract_member_force_demand(engineering_results, member.id, component="moment")
    pu = extract_member_force_demand(engineering_results, member.id, component="axial")
    if mu is None and pu is None:
        return {
            "status": DesignStatus.REQUIRES_ANALYSIS.value,
            "message": (
                f"No validated frame forces found for column '{member.name}'. "
                "Run analysis with a connected solver first."
            ),
            "checks": [],
        }

    width_in = float(parameters.get("width_in") or getattr(section, "width", None) or 16.0)
    depth_in = float(parameters.get("depth_in") or getattr(section, "depth", None) or 16.0)
    fc_psi = float(material.compressive_strength or 4000.0)
    fy_psi = float(parameters.get("rebar_fy_psi", 60000.0))

    checks: list[dict[str, Any]] = []
    governing_utilization = 0.0
    all_pass = True

    if mu is not None and pu is not None:
        combined = code_engine.run_check(
            "ACI318-25",
            "CONCRETE_COLUMN_COMBINED",
            {
                "Pu_kip": pu,
                "Mu_kipft": mu,
                "fc_psi": fc_psi,
                "fy_psi": fy_psi,
                "width_in": width_in,
                "depth_in": depth_in,
            },
            code_configuration=pem.code_configuration,
        )
        checks.append(combined.model_dump(mode="json"))
        utilization = combined.metadata.get("utilization", 0.0)
        governing_utilization = max(governing_utilization, float(utilization or 0.0))
        if combined.outcome == CheckOutcome.FAIL:
            all_pass = False
    else:
        if mu is not None:
            flexure = code_engine.run_check(
                "ACI318-25",
                "CONCRETE_COLUMN_FLEXURE",
                {
                    "Mu_kipft": mu,
                    "fc_psi": fc_psi,
                    "fy_psi": fy_psi,
                    "width_in": width_in,
                    "depth_in": depth_in,
                },
                code_configuration=pem.code_configuration,
            )
            checks.append(flexure.model_dump(mode="json"))
            utilization = flexure.metadata.get("utilization", 0.0)
            governing_utilization = max(governing_utilization, float(utilization or 0.0))
            if flexure.outcome == CheckOutcome.FAIL:
                all_pass = False

        if pu is not None:
            axial = code_engine.run_check(
                "ACI318-25",
                "CONCRETE_COLUMN_AXIAL",
                {
                    "Pu_kip": pu,
                    "fc_psi": fc_psi,
                    "width_in": width_in,
                    "depth_in": depth_in,
                },
                code_configuration=pem.code_configuration,
            )
            checks.append(axial.model_dump(mode="json"))
            utilization = axial.metadata.get("utilization", 0.0)
            governing_utilization = max(governing_utilization, float(utilization or 0.0))
            if axial.outcome == CheckOutcome.FAIL:
                all_pass = False

    status = DesignStatus.PASS if all_pass else DesignStatus.FAIL
    return {
        "status": status.value,
        "message": (
            f"Concrete column checks completed for '{member.name}' using {pem.code_configuration.concrete_edition}."
        ),
        "member_id": member.id,
        "member_name": member.name,
        "code_edition": pem.code_configuration.concrete_edition,
        "checks": checks,
        "governing_utilization": round(governing_utilization, 4),
        "calculation_method": "deterministic_code_engine",
    }


def run_steel_member_design(
    *,
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    parameters: dict[str, Any],
) -> dict[str, Any]:
    section = _find_beam_section(pem, member.section_id)
    width = float(parameters.get("width_in") or (section.width if section else 6.0))
    depth = float(parameters.get("depth_in") or (section.depth if section else 12.0))
    if section is None and parameters.get("width_in") is None:
        return {
            "status": DesignStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": "Steel member section could not be resolved from the engineering model.",
            "checks": [],
        }

    mu = extract_member_force_demand(engineering_results, member.id, component="moment")
    pu = extract_member_force_demand(engineering_results, member.id, component="axial")
    if mu is None and pu is None:
        return {
            "status": DesignStatus.REQUIRES_ANALYSIS.value,
            "message": (
                f"No validated frame forces found for member '{member.name}'. "
                "Run analysis with a connected solver first."
            ),
            "checks": [],
        }

    fy_ksi = float(parameters.get("fy_ksi", 50.0))
    zx_in3 = float(parameters.get("zx_in3") or _estimate_plastic_modulus_from_dims(width, depth))
    ag_in2 = float(parameters.get("ag_in2") or width * depth)

    checks: list[dict[str, Any]] = []
    governing_utilization = 0.0
    all_pass = True

    if mu is not None and pu is not None:
        interaction = code_engine.run_check(
            "AISC360-22",
            "STEEL_MEMBER_INTERACTION",
            {"Mu_kipft": mu, "Pu_kip": pu, "Fy_ksi": fy_ksi, "Zx_in3": zx_in3, "Ag_in2": ag_in2},
            code_configuration=pem.code_configuration,
        )
        checks.append(interaction.model_dump(mode="json"))
        utilization = interaction.metadata.get("utilization", 0.0)
        governing_utilization = max(governing_utilization, float(utilization or 0.0))
        if interaction.outcome == CheckOutcome.FAIL:
            all_pass = False
    else:
        if mu is not None:
            flexure = code_engine.run_check(
                "AISC360-22",
                "STEEL_BEAM_FLEXURE",
                {"Mu_kipft": mu, "Fy_ksi": fy_ksi, "Zx_in3": zx_in3},
                code_configuration=pem.code_configuration,
            )
            checks.append(flexure.model_dump(mode="json"))
            utilization = flexure.metadata.get("utilization", 0.0)
            governing_utilization = max(governing_utilization, float(utilization or 0.0))
            if flexure.outcome == CheckOutcome.FAIL:
                all_pass = False

        if pu is not None:
            axial = code_engine.run_check(
                "AISC360-22",
                "STEEL_MEMBER_AXIAL",
                {"Pu_kip": pu, "Fy_ksi": fy_ksi, "Ag_in2": ag_in2},
                code_configuration=pem.code_configuration,
            )
            checks.append(axial.model_dump(mode="json"))
            utilization = axial.metadata.get("utilization", 0.0)
            governing_utilization = max(governing_utilization, float(utilization or 0.0))
            if axial.outcome == CheckOutcome.FAIL:
                all_pass = False

    status = DesignStatus.PASS if all_pass else DesignStatus.FAIL
    return {
        "status": status.value,
        "message": (
            f"Steel member checks completed for '{member.name}' using {pem.code_configuration.steel_edition}."
        ),
        "member_id": member.id,
        "member_name": member.name,
        "code_edition": pem.code_configuration.steel_edition,
        "checks": checks,
        "governing_utilization": round(governing_utilization, 4),
        "calculation_method": "deterministic_code_engine",
    }


def evaluate_member_section_design(
    *,
    pem: ProjectEngineeringModel,
    member: StructuralMember,
    engineering_results: dict[str, Any],
    code_engine: CodeEngineService,
    section_id: str,
    section_name: str,
    width: float,
    depth: float,
    parameters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate deterministic design checks for a member using explicit section dimensions."""
    params = {
        **(parameters or {}),
        "width_in": width,
        "depth_in": depth,
        "zx_in3": width * depth * depth / 4.0,
        "ag_in2": width * depth,
    }
    if _find_concrete_material(pem, member.material_id) is not None:
        if member.member_type == MemberType.COLUMN:
            result = run_concrete_column_design(
                pem=pem,
                member=member,
                engineering_results=engineering_results,
                code_engine=code_engine,
                parameters=params,
            )
        else:
            result = run_concrete_beam_design(
                pem=pem,
                member=member,
                engineering_results=engineering_results,
                code_engine=code_engine,
                parameters=params,
            )
    elif any(item.id == member.material_id for item in pem.structural_model.materials.steel):
        result = run_steel_member_design(
            pem=pem,
            member=member,
            engineering_results=engineering_results,
            code_engine=code_engine,
            parameters=params,
        )
    else:
        return {
            "status": DesignStatus.REQUIRES_ENGINEER_REVIEW.value,
            "message": f"Material for member '{member.name}' is not supported for section optimization.",
            "checks": [],
            "member_id": member.id,
            "section_id": section_id,
        }

    result["section_id"] = section_id
    result["section_name"] = section_name
    return result


def select_target_member(
    pem: ProjectEngineeringModel,
    parameters: dict[str, Any],
    *,
    member_types: set[MemberType],
) -> StructuralMember | None:
    member_id = parameters.get("member_id")
    if member_id:
        for member in pem.structural_model.members.members:
            if member.id == member_id:
                return member
    for member in pem.structural_model.members.members:
        if member.member_type in member_types:
            return member
    return None


def _dimension_inches(
    parameters: dict[str, Any],
    section: BeamSection | ColumnSection | None,
    parameter_name: str,
    axis: str,
    default: float,
    assumptions: list[str],
    label: str,
) -> float:
    explicit = parameters.get(parameter_name)
    if isinstance(explicit, (int, float)) and not isinstance(explicit, bool):
        return float(explicit)
    converted = _section_inches(section, axis)
    if converted is not None:
        if section is not None and section.metadata.get("units") == "m":
            assumptions.append(f"Beam {label} was converted from metres to inches.")
        return converted
    assumptions.append(f"Beam {label} was assumed as {default:g} in because the section has no {label}.")
    return default


def _concrete_fc_psi(material: ConcreteMaterial, assumptions: list[str]) -> float:
    units = material.metadata.get("units") if isinstance(material.metadata, dict) else None
    strength_unit = units.get("strength") if isinstance(units, dict) else None
    if material.compressive_strength is None:
        assumptions.append("Concrete f'c was assumed as 4000 psi because the material has no strength.")
        return 4000.0
    if strength_unit == "MPa":
        psi = float(material.compressive_strength) * 145.0377377
        assumptions.append(
            f"Concrete f'c was converted from {material.compressive_strength} MPa to {psi:.1f} psi."
        )
        return psi
    return float(material.compressive_strength)


def _rebar_fy_psi(pem: ProjectEngineeringModel, parameters: dict[str, Any]) -> tuple[float, str | None]:
    explicit = parameters.get("rebar_fy_psi")
    if isinstance(explicit, (int, float)) and not isinstance(explicit, bool):
        return float(explicit), None
    bars = pem.structural_model.materials.reinforcement
    if not bars or bars[0].yield_strength is None:
        return 60000.0, (
            "Reinforcement fy was assumed as 60000 psi because the PEM has no reinforcement yield strength."
        )
    bar = bars[0]
    units = bar.metadata.get("units") if isinstance(bar.metadata, dict) else None
    strength_unit = units.get("strength") if isinstance(units, dict) else None
    if strength_unit == "MPa" and bar.yield_strength is not None:
        psi = float(bar.yield_strength) * 145.0377377
        return psi, (
            f"Reinforcement fy was converted from {bar.yield_strength} MPa on {bar.id} to {psi:.1f} psi."
        )
    return float(bar.yield_strength or 60000.0), None


def _section_inches(section: BeamSection | ColumnSection | None, axis: str) -> float | None:
    if section is None:
        return None
    raw = getattr(section, axis, None)
    if raw is None:
        return None
    if section.metadata.get("units") == "m":
        return float(raw) * 39.3700787
    return float(raw)


def _stress_psi(value: float | None, metadata: dict[str, Any], *, default: float) -> float:
    if value is None:
        return default
    units = metadata.get("units") if isinstance(metadata, dict) else None
    if isinstance(units, dict) and units.get("strength") == "MPa":
        return float(value) * 145.0377377
    return float(value)


def _find_beam_section(pem: ProjectEngineeringModel, section_id: str) -> BeamSection | None:
    for section in pem.structural_model.sections.beams:
        if section.id == section_id:
            return section
    return None


def _find_column_section(pem: ProjectEngineeringModel, section_id: str) -> ColumnSection | None:
    for section in pem.structural_model.sections.columns:
        if section.id == section_id:
            return section
    return None


def _find_concrete_material(pem: ProjectEngineeringModel, material_id: str) -> ConcreteMaterial | None:
    for material in pem.structural_model.materials.concrete:
        if material.id == material_id:
            return material
    return None


def _estimate_plastic_modulus(section: BeamSection) -> float:
    width = section.width or 6.0
    depth = section.depth or 12.0
    return _estimate_plastic_modulus_from_dims(width, depth)


def _estimate_plastic_modulus_from_dims(width: float, depth: float) -> float:
    return width * depth * depth / 4.0


def _flatten_numbers(value: Any) -> list[float]:
    if isinstance(value, bool):
        return []
    if isinstance(value, (int, float)):
        return [float(value)]
    if isinstance(value, (list, tuple)):
        numbers: list[float] = []
        for item in value:
            numbers.extend(_flatten_numbers(item))
        return numbers
    if isinstance(value, dict):
        numbers: list[float] = []
        for item in value.values():
            numbers.extend(_flatten_numbers(item))
        return numbers
    return []
