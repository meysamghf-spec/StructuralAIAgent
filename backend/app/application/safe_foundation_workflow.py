"""Decide whether a PEM can be sent to SAFE for isolated spread footings.

Preliminary internal footing sizes and reactions are reported and are not used as
SAFE loads or as a substitute for a user-provided subgrade modulus.
"""

from __future__ import annotations

from typing import Any

from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import InputOrigin, MemberType


_SUPPORTED_TYPES = {"isolated", "spread", "spread footing", "isolated spread footing"}
_ACCEPTED_ORIGINS = {InputOrigin.USER_PROVIDED.value, "USER_PROVIDED"}


def assess_safe_foundation_inputs(pem: ProjectEngineeringModel) -> dict[str, Any]:
    structural = pem.structural_model
    missing: list[str] = []
    notes: list[str] = []
    preliminary_ids = [
        item.id
        for item in structural.footings
        if str((item.metadata or {}).get("origin") or "") not in _ACCEPTED_ORIGINS
    ]
    if preliminary_ids:
        notes.append(
            "PEM footing records "
            + ", ".join(preliminary_ids)
            + " come from the internal preliminary footing calculation. They are not SAFE results and are not used as SAFE loads."
        )

    footings = _explicit_footings(pem, missing)
    if footings:
        notes.append(
            "Rigid vertical restraint is not sent to SAFE. Vertical stiffness is only the user-provided subgrade modulus. "
            "Each explicit column force is divided equally among the four footing corners so the area defined by those corners receives the full PEM force."
        )
    concrete = _concrete_material(structural, missing)
    subgrade = _subgrade(structural, missing)
    load_cases, combinations = _loads(structural, footings, missing)

    ready = not missing and bool(footings) and concrete is not None and subgrade is not None
    spec = {
        "ready": ready,
        "supported_type": "ISOLATED_SPREAD_FOOTING",
        "units": {"length": "m", "force": "kN", "subgrade": "kN/m3", "stress": "kN/m2"},
        "concrete": concrete,
        "subgrade_modulus_kN_m3": subgrade["value"] if subgrade else None,
        "subgrade_origin": subgrade["origin"] if subgrade else None,
        "footings": footings,
        "load_cases": load_cases,
        "combinations": combinations,
        "missing": missing,
        "preliminary_internal_footing_ids": preliminary_ids,
        "notes": notes,
        "source": "PEM",
    }
    return {
        "ready": ready,
        "missing": missing,
        "notes": notes,
        "preliminary_internal_footing_ids": preliminary_ids,
        "supported_type": "ISOLATED_SPREAD_FOOTING" if ready else None,
        "spec": spec,
    }


def _explicit_footings(pem: ProjectEngineeringModel, missing: list[str]) -> list[dict[str, Any]]:
    structural = pem.structural_model
    points = {point.id: point for point in structural.geometry.points}
    columns = {
        member.id: member
        for member in structural.members.members
        if member.member_type is MemberType.COLUMN
    }
    found: list[dict[str, Any]] = []
    for section in structural.sections.foundations:
        kind = section.foundation_type.strip().lower()
        if kind not in _SUPPORTED_TYPES:
            missing.append(
                f"Foundation section {section.id} type '{section.foundation_type}' is not an isolated spread footing"
            )
            continue
        if section.width is None or section.length is None or section.depth is None:
            missing.append(f"Foundation section {section.id} is missing width, length, or thickness")
            continue
        metadata = section.metadata or {}
        point_id = metadata.get("point_id")
        column_id = metadata.get("column_member_id")
        if column_id and not point_id:
            column = columns.get(str(column_id))
            point_id = column.start_point_id if column is not None else None
        point = points.get(str(point_id or ""))
        if point is None:
            missing.append(f"Foundation section {section.id} has no column point assignment")
            continue
        support = _support_at(structural, point.id)
        if support is None:
            missing.append(f"Foundation section {section.id} has no support definition at {point.id}")
            continue
        found.append(
            {
                "id": section.id,
                "point_id": point.id,
                "column_member_id": column_id,
                "x_m": point.x,
                "y_m": point.y,
                "z_m": point.z,
                "length_m": section.length,
                "width_m": section.width,
                "thickness_m": section.depth,
                "restraint": _horizontal_restraint(support),
                "geometry_source": "FOUNDATION_SECTION",
            }
        )
    for footing in structural.footings:
        origin = str((footing.metadata or {}).get("origin") or "")
        if origin not in _ACCEPTED_ORIGINS:
            continue
        point = points.get(footing.point_id)
        if point is None:
            missing.append(f"User footing {footing.id} point {footing.point_id} is not in the geometry")
            continue
        support = _support_at(structural, point.id)
        if support is None:
            missing.append(f"User footing {footing.id} has no support definition at {point.id}")
            continue
        found.append(
            {
                "id": footing.id,
                "point_id": point.id,
                "column_member_id": footing.column_member_id,
                "x_m": point.x,
                "y_m": point.y,
                "z_m": point.z,
                "length_m": footing.length_m,
                "width_m": footing.width_m,
                "thickness_m": footing.thickness_m,
                "restraint": _horizontal_restraint(support),
                "geometry_source": "USER_PROVIDED_FOOTING",
            }
        )
    if not found and not any(item.startswith("Foundation section") or item.startswith("User footing") for item in missing):
        missing.append(
            "No isolated spread footing with declared width, length, thickness, column point, and support is in the PEM"
        )
    return found


def _support_at(structural: Any, point_id: str) -> Any:
    return next((item for item in structural.supports if item.point_id == point_id), None)


def _horizontal_restraint(support: Any) -> list[bool]:
    """PEM horizontal and rotational restraints. Vertical translation stays free for the soil spring."""
    kind = support.support_type.value
    if kind == "CUSTOM":
        flags = [
            bool(support.restraint_tx),
            bool(support.restraint_ty),
            False,
            bool(support.restraint_rx),
            bool(support.restraint_ry),
            bool(support.restraint_rz),
        ]
    elif kind == "PINNED":
        flags = [True, True, False, False, False, False]
    elif kind == "ROLLER":
        flags = [False, True, False, False, False, False]
    elif kind == "FIXED":
        flags = [True, True, False, True, True, True]
    else:
        flags = [False, False, False, False, False, False]
    return flags


def _concrete_material(structural: Any, missing: list[str]) -> dict[str, Any] | None:
    concrete = structural.materials.concrete
    if not concrete:
        missing.append("SAFE foundation design needs a concrete material")
        return None
    material = concrete[0]
    units = material.metadata.get("units") if isinstance(material.metadata, dict) else None
    strength_unit = units.get("strength") if isinstance(units, dict) else None
    if not strength_unit:
        missing.append(f"Concrete material {material.id} strength unit is not declared")
        return None
    if material.compressive_strength is None:
        missing.append(f"Concrete material {material.id} compressive strength is missing")
        return None
    return {
        "id": material.id,
        "name": material.name,
        "fc": float(material.compressive_strength),
        "fc_unit": str(strength_unit),
        "poisson_ratio": material.poisson_ratio,
        "modulus_of_elasticity": material.modulus_of_elasticity,
        "modulus_unit": units.get("modulus") if isinstance(units, dict) else None,
    }


def _subgrade(structural: Any, missing: list[str]) -> dict[str, Any] | None:
    parameters = structural.design_parameters.load_parameters or {}
    value = parameters.get("subgrade_modulus_kN_m3")
    origin = str(parameters.get("subgrade_modulus_origin") or "")
    provenance_origin = ""
    for item in structural.input_provenance:
        if item.field == "subgrade_modulus_kN_m3":
            provenance_origin = item.origin.value
            break
    accepted = origin in _ACCEPTED_ORIGINS or provenance_origin in _ACCEPTED_ORIGINS
    if value in (None, ""):
        missing.append("subgrade_modulus_kN_m3 is required for SAFE area springs and was not provided")
        return None
    if not accepted:
        missing.append(
            "subgrade_modulus_kN_m3 is present but its origin is not USER_PROVIDED. "
            "A preliminary or unlabeled soil stiffness is not sent to SAFE."
        )
        return None
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        missing.append("subgrade_modulus_kN_m3 is not a number")
        return None
    if numeric <= 0:
        missing.append("subgrade_modulus_kN_m3 must be greater than zero")
        return None
    return {"value": numeric, "origin": origin or provenance_origin}


def _loads(
    structural: Any,
    footings: list[dict[str, Any]],
    missing: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    point_ids = {item["point_id"] for item in footings}
    cases: list[dict[str, Any]] = []
    if not structural.load_cases:
        missing.append("SAFE foundation design needs at least one load case with explicit column-point forces")
        return [], []
    for case in structural.load_cases:
        loads = []
        for load in case.loads:
            if load.point_id not in point_ids:
                continue
            if load.distribution.value not in {"POINT", "NODAL"}:
                continue
            converted = _force_kN(load.magnitude, load.unit)
            if converted is None:
                missing.append(f"Load {load.id} unit '{load.unit}' cannot be converted to kN")
                continue
            direction = _signed_components(load, converted)
            loads.append(
                {
                    "id": load.id,
                    "point_id": load.point_id,
                    "fx_kN": direction[0],
                    "fy_kN": direction[1],
                    "fz_kN": direction[2],
                    "origin": "PEM_LOAD_CASE",
                }
            )
        if loads:
            cases.append({"id": case.id, "category": case.category.value, "loads": loads})
    if footings and not cases:
        missing.append(
            "Column loads are not defined as point loads on the footing points. "
            "Preliminary internal footing reactions are not sent to SAFE."
        )
    combinations = []
    known = {item["id"] for item in cases}
    for combo in structural.load_combinations:
        terms = []
        for term in combo.terms:
            if term.load_case_id not in known and term.load_case_id not in {case.id for case in structural.load_cases}:
                missing.append(f"Combination {combo.id} references unknown load case {term.load_case_id}")
                continue
            terms.append({"load_case_id": term.load_case_id, "factor": term.factor})
        if terms:
            combinations.append({"id": combo.id, "terms": terms})
    return cases, combinations


def _force_kN(magnitude: float, unit: str) -> float | None:
    token = unit.strip().lower().replace(" ", "")
    factors = {"kn": 1.0, "n": 0.001, "kip": 4.4482216153, "kips": 4.4482216153, "lb": 0.0044482216153, "lbf": 0.0044482216153}
    factor = factors.get(token)
    if factor is None:
        return None
    return float(magnitude) * factor


def _signed_components(load: Any, force_kN: float) -> tuple[float, float, float]:
    dx = float(load.direction_x or 0.0)
    dy = float(load.direction_y or 0.0)
    dz = float(load.direction_z if load.direction_z is not None else -1.0)
    scale = max(abs(dx), abs(dy), abs(dz), 1e-9)
    return (force_kN * dx / scale, force_kN * dy / scale, force_kN * dz / scale)
