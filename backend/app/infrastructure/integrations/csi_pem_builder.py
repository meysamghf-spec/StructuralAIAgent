"""Push PEM structural data into CSI SapModel when the vendor COM API is available.

Database units for the vendor model are kN, m, and C (CSI eUnits = 6). PEM values
are converted only from units the PEM declares. A missing unit, material strength,
or geometry reference fails that stage. It is not replaced with a default.
"""

from __future__ import annotations

from typing import Any

from app.domain.models.integration import ExternalModelExport
from app.domain.models.pem_structural import SupportType


CSI_UNIT_SYSTEM_KN_M_C = 6

_LENGTH_TO_M = {
    "m": 1.0,
    "meter": 1.0,
    "meters": 1.0,
    "mm": 0.001,
    "cm": 0.01,
    "in": 0.0254,
    "inch": 0.0254,
    "inches": 0.0254,
    "ft": 0.3048,
    "foot": 0.3048,
    "feet": 0.3048,
}

_FORCE_TO_KN = {
    "kn": 1.0,
    "n": 0.001,
    "kip": 4.4482216153,
    "kips": 4.4482216153,
    "lbf": 0.0044482216153,
    "lb": 0.0044482216153,
}

_STRESS_TO_KPA = {
    "kpa": 1.0,
    "kn/m2": 1.0,
    "mpa": 1000.0,
    "n/mm2": 1000.0,
    "pa": 0.001,
    "n/m2": 0.001,
    "psi": 6.894757293,
    "ksi": 6894.757293,
    "psf": 0.04788025898,
    "ksf": 47.88025898,
    "kip/ft2": 47.88025898,
    "kip/in2": 6894.757293,
}

# Force per length → kN/m.
_LINE_LOAD_TO_KN_PER_M = {
    "kn/m": 1.0,
    "n/m": 0.001,
    "kip/ft": 4.4482216153 / 0.3048,
    "k/ft": 4.4482216153 / 0.3048,
    "kip/in": 4.4482216153 / 0.0254,
    "lb/ft": 0.0044482216153 / 0.3048,
    "lbf/ft": 0.0044482216153 / 0.3048,
    "plf": 0.0044482216153 / 0.3048,
}

# CSI eLoadPatternType.
_LOAD_PATTERN_TYPES = {
    "DEAD": 1,
    "PARTITION": 2,
    "LIVE": 3,
    "ROOF": 11,
    "WIND": 6,
    "SEISMIC": 5,
    "SNOW": 7,
    "OTHER": 8,
}


class _ApiUnavailable(RuntimeError):
    pass


class _NoData(RuntimeError):
    pass


def build_vendor_model_from_export(
    sap_model: Any,
    export: ExternalModelExport,
    *,
    length_unit: str = "m",
    force_unit: str = "kN",
) -> dict[str, Any]:
    """Attempt progressive PEM → CSI model construction. Never fabricates solver success."""
    structural = export.structural_model
    unit_config = {}
    if isinstance(export.metadata, dict):
        raw_units = export.metadata.get("unit_configuration") or {}
        if isinstance(raw_units, dict):
            unit_config = raw_units
    project_length = str(unit_config.get("length_unit") or length_unit or "m")
    assumptions: list[str] = []
    stages: list[dict[str, Any]] = []
    point_name_map: dict[str, str] = {}

    _run_stage(stages, "materials", lambda: _define_materials(sap_model, structural, assumptions))
    _run_stage(stages, "sections", lambda: _define_sections(sap_model, structural, project_length, assumptions))
    point_name_map = _run_stage(
        stages,
        "geometry",
        lambda: _define_points(sap_model, structural, project_length),
        default={},
    ) or {}
    _run_stage(stages, "members", lambda: _define_frames(sap_model, structural, point_name_map))
    _run_stage(stages, "areas", lambda: _define_areas(sap_model, structural, point_name_map))
    _run_stage(stages, "supports", lambda: _define_supports(sap_model, structural, point_name_map))
    _run_stage(stages, "load_patterns", lambda: _define_load_patterns(sap_model, structural))
    _run_stage(stages, "load_cases", lambda: _define_load_cases(sap_model, structural))
    _run_stage(
        stages,
        "loads",
        lambda: _define_loads(sap_model, structural, point_name_map),
    )
    _run_stage(stages, "load_combinations", lambda: _define_load_combinations(sap_model, structural))
    _run_stage(stages, "releases", lambda: _define_releases(sap_model, structural))
    _run_stage(stages, "diaphragms", lambda: _define_diaphragms(sap_model, structural, point_name_map))
    _run_stage(stages, "analysis_settings", lambda: _define_analysis_settings(sap_model, structural))

    completed = sum(1 for stage in stages if stage["status"] == "COMPLETE")
    failed = sum(1 for stage in stages if stage["status"] == "FAILED")
    skipped = sum(1 for stage in stages if stage["status"] == "SKIPPED")
    if failed > 0 and completed == 0:
        vendor_build_status = "FAILED"
    elif failed > 0 or skipped > 0:
        vendor_build_status = "PARTIAL"
    else:
        vendor_build_status = "COMPLETE"

    return {
        "vendor_build_status": vendor_build_status,
        "stages": stages,
        "assumptions": assumptions,
        "counts": {
            "materials": _count_items(structural, "materials"),
            "sections": _section_count(structural),
            "points": len(structural.get("geometry", {}).get("points", [])),
            "members": len(structural.get("members", {}).get("members", [])),
            "supports": len(structural.get("supports", [])),
            "load_cases": len(structural.get("load_cases", [])),
            "load_combinations": len(structural.get("load_combinations", [])),
        },
        "length_unit": project_length,
        "force_unit": force_unit,
        "csi_unit_system": CSI_UNIT_SYSTEM_KN_M_C,
        "target_units": {"length": "m", "force": "kN", "stress": "kN/m2", "temperature": "C"},
        "analysis_executed": False,
    }


def _run_stage(
    stages: list[dict[str, Any]],
    name: str,
    action: Any,
    *,
    default: Any = None,
) -> Any:
    try:
        result = action()
        status = "COMPLETE"
        if isinstance(result, dict) and result.get("status") == "SKIPPED_EMPTY":
            status = "SKIPPED_EMPTY"
        stages.append({"stage": name, "status": status, "detail": _stage_detail(result)})
        return default if result is None else result
    except _NoData as exc:
        stages.append({"stage": name, "status": "SKIPPED_EMPTY", "detail": str(exc)})
        return default
    except _ApiUnavailable as exc:
        stages.append({"stage": name, "status": "SKIPPED", "detail": str(exc)})
        return default
    except Exception as exc:  # noqa: BLE001
        stages.append({"stage": name, "status": "FAILED", "detail": str(exc)})
        return default


def _stage_detail(result: Any) -> str:
    if isinstance(result, dict):
        return ", ".join(f"{key}={value}" for key, value in result.items() if key != "status")
    if isinstance(result, int):
        return f"count={result}"
    return "ok"


def _require_api(obj: Any, *path: str) -> Any:
    current = obj
    for segment in path:
        current = getattr(current, segment, None)
        if current is None:
            raise _ApiUnavailable(f"Vendor API missing: {'.'.join(path)}")
    if not callable(current):
        raise _ApiUnavailable(f"Vendor API not callable: {'.'.join(path)}")
    return current


def _call(api: Any, *args: Any, label: str) -> Any:
    result = api(*args)
    code = result[0] if isinstance(result, tuple) else result
    if code not in (0, None):
        raise RuntimeError(f"{label} failed with vendor code {code}")
    return result


def _unit_token(value: str) -> str:
    return value.strip().lower().replace(" ", "")


def _length_m(value: float, unit: str, *, label: str) -> float:
    factor = _LENGTH_TO_M.get(_unit_token(unit))
    if factor is None:
        raise RuntimeError(f"{label} length unit '{unit}' is not a supported conversion")
    return float(value) * factor


def _project_length_unit(structural: dict[str, Any], project_length: str) -> str:
    token = _unit_token(project_length)
    if token not in _LENGTH_TO_M:
        raise RuntimeError(
            f"PEM length unit '{project_length}' is not declared as m, mm, cm, in, or ft"
        )
    return project_length


def _section_length_unit(item: dict[str, Any], project_length: str) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    units = metadata.get("units")
    if isinstance(units, str) and units.strip():
        return units
    if isinstance(units, dict) and units.get("length"):
        return str(units["length"])
    if _unit_token(project_length) == "m":
        return "m"
    raise RuntimeError(
        f"Section {item.get('id')} width/depth unit is not declared. "
        "Set section metadata.units to the length unit (for example 'm' or 'in')."
    )


def _strength_unit(item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    units = metadata.get("units")
    if isinstance(units, dict) and units.get("strength"):
        return str(units["strength"])
    if isinstance(units, str) and _unit_token(units) in _STRESS_TO_KPA:
        return units
    raise RuntimeError(
        f"Material {item.get('id')} strength unit is not declared. "
        "Set metadata.units.strength (for example 'MPa' or 'psi')."
    )


def _stress_kpa(value: float, unit: str, *, label: str) -> float:
    factor = _STRESS_TO_KPA.get(_unit_token(unit))
    if factor is None:
        raise RuntimeError(f"{label} stress unit '{unit}' is not a supported conversion")
    return float(value) * factor


def _define_materials(
    sap_model: Any,
    structural: dict[str, Any],
    assumptions: list[str],
) -> dict[str, Any]:
    set_material = _require_api(sap_model, "PropMaterial", "SetMaterial")
    prop_material = sap_model.PropMaterial
    materials = structural.get("materials", {})
    concrete = list(materials.get("concrete") or [])
    steel = list(materials.get("steel") or [])
    reinforcement = list(materials.get("reinforcement") or [])
    if not concrete and not steel and not reinforcement:
        raise _NoData("No materials defined in PEM export")

    defined = 0
    for item in concrete:
        name = str(item["id"])
        unit = _strength_unit(item)
        fc_kpa = _stress_kpa(float(item["compressive_strength"]), unit, label=name)
        _call(set_material, name, 2, label=f"PropMaterial.SetMaterial {name}")
        _set_concrete_strength(prop_material, name, fc_kpa, assumptions)
        _set_isotropic(prop_material, item, name, assumptions)
        _set_weight(prop_material, item, name, assumptions)
        defined += 1
    for item in steel:
        name = str(item["id"])
        unit = _strength_unit(item)
        fy_kpa = _stress_kpa(float(item["yield_strength"]), unit, label=name)
        if item.get("ultimate_strength") in (None, ""):
            raise RuntimeError(f"Steel material {name} is missing ultimate_strength")
        fu_kpa = _stress_kpa(float(item["ultimate_strength"]), unit, label=name)
        _call(set_material, name, 1, label=f"PropMaterial.SetMaterial {name}")
        set_steel = getattr(prop_material, "SetOSteel_1", None)
        if not callable(set_steel):
            raise _ApiUnavailable("Vendor API missing: PropMaterial.SetOSteel_1")
        _call(
            set_steel,
            name,
            fy_kpa,
            fu_kpa,
            fy_kpa,
            fu_kpa,
            1,
            2,
            0,
            0,
            0,
            0,
            label=f"PropMaterial.SetOSteel_1 {name}",
        )
        assumptions.append(
            f"Steel {name} stress-strain curve ordinates were not in the PEM. "
            "SetOSteel_1 received Fy and Fu only; the remaining curve arguments are 0 "
            "so the vendor applies its own defaults."
        )
        _set_isotropic(prop_material, item, name, assumptions)
        _set_weight(prop_material, item, name, assumptions)
        defined += 1
    rebar_defined = 0
    for item in reinforcement:
        name = str(item["id"])
        unit = _strength_unit(item)
        fy_kpa = _stress_kpa(float(item["yield_strength"]), unit, label=name)
        _call(set_material, name, 6, label=f"PropMaterial.SetMaterial {name}")
        set_rebar = getattr(prop_material, "SetORebar_1", None)
        if callable(set_rebar):
            _call(set_rebar, name, fy_kpa, fy_kpa, 0, 0, 1, 2, 0, 0, 0, label=f"PropMaterial.SetORebar_1 {name}")
            rebar_defined += 1
        else:
            assumptions.append(f"Reinforcement {name} was created without SetORebar_1 because that API is absent.")
        defined += 1
    return {"defined": defined, "rebar_design_properties": rebar_defined}


def _set_concrete_strength(prop_material: Any, name: str, fc_kpa: float, assumptions: list[str]) -> None:
    set_concrete = getattr(prop_material, "SetOConcrete_1", None)
    if not callable(set_concrete):
        raise _ApiUnavailable("Vendor API missing: PropMaterial.SetOConcrete_1")
    _call(
        set_concrete,
        name,
        fc_kpa,
        False,
        0,
        1,
        2,
        0,
        0,
        0,
        0,
        0,
        label=f"PropMaterial.SetOConcrete_1 {name}",
    )
    assumptions.append(
        f"Concrete {name} stress-strain curve was not in the PEM. "
        f"SetOConcrete_1 received f'c = {fc_kpa:.3f} kN/m2 and zero curve arguments "
        "so ETABS can apply its own defaults. Those defaults are not project test data."
    )


def _set_isotropic(prop_material: Any, item: dict[str, Any], name: str, assumptions: list[str]) -> None:
    modulus = item.get("modulus_of_elasticity")
    poisson = item.get("poisson_ratio")
    if modulus in (None, "") and poisson in (None, ""):
        assumptions.append(f"Material {name} modulus and Poisson's ratio were not sent because the PEM does not contain them.")
        return
    if modulus in (None, "") or poisson in (None, ""):
        assumptions.append(
            f"Material {name} elastic constants were not sent. Modulus and Poisson's ratio must both be present."
        )
        return
    set_mp = getattr(prop_material, "SetMPIsotropic", None)
    if not callable(set_mp):
        raise _ApiUnavailable("Vendor API missing: PropMaterial.SetMPIsotropic")
    unit = "MPa"
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    units = metadata.get("units")
    if isinstance(units, dict) and units.get("modulus"):
        unit = str(units["modulus"])
    modulus_kpa = _stress_kpa(float(modulus), unit, label=f"{name} modulus")
    _call(set_mp, name, modulus_kpa, float(poisson), 0, label=f"PropMaterial.SetMPIsotropic {name}")


def _set_weight(prop_material: Any, item: dict[str, Any], name: str, assumptions: list[str]) -> None:
    weight = item.get("unit_weight")
    if weight in (None, ""):
        assumptions.append(
            f"Material {name} unit weight was not in the PEM. The vendor material default is left unchanged."
        )
        return
    set_weight = getattr(prop_material, "SetWeightAndMass", None)
    if not callable(set_weight):
        raise _ApiUnavailable("Vendor API missing: PropMaterial.SetWeightAndMass")
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    units = metadata.get("units")
    unit = "kN/m3"
    if isinstance(units, dict) and units.get("unit_weight"):
        unit = str(units["unit_weight"])
    token = _unit_token(unit)
    if token not in {"kn/m3", "kn/m^3"}:
        raise RuntimeError(f"Material {name} unit weight unit '{unit}' is not kN/m3")
    _call(set_weight, name, 1, float(weight), label=f"PropMaterial.SetWeightAndMass {name}")


def _material_for_section(structural: dict[str, Any], section_id: str) -> str:
    members = [
        item
        for item in structural.get("members", {}).get("members", [])
        if str(item.get("section_id")) == section_id and item.get("material_id")
    ]
    material_ids = {str(item["material_id"]) for item in members}
    if len(material_ids) > 1:
        raise RuntimeError(f"Section {section_id} is used with more than one material: {sorted(material_ids)}")
    if len(material_ids) == 1:
        return next(iter(material_ids))
    concrete = structural.get("materials", {}).get("concrete") or []
    if len(concrete) == 1:
        return str(concrete[0]["id"])
    raise RuntimeError(f"Section {section_id} has no material assignment")


def _define_sections(
    sap_model: Any,
    structural: dict[str, Any],
    project_length: str,
    assumptions: list[str],
) -> dict[str, Any]:
    set_rectangle = _require_api(sap_model, "PropFrame", "SetRectangle")
    sections = structural.get("sections", {})
    defined = 0
    for bucket in ("beams", "columns"):
        for item in sections.get(bucket) or []:
            unit = _section_length_unit(item, project_length)
            if "units" not in (item.get("metadata") or {}) and _unit_token(project_length) == "m":
                assumptions.append(
                    f"Section {item.get('id')} dimensions use the project length unit {project_length}."
                )
            width_m = _length_m(float(item["width"]), unit, label=str(item.get("id")))
            depth_m = _length_m(float(item["depth"]), unit, label=str(item.get("id")))
            material_name = _material_for_section(structural, str(item["id"]))
            # T3 is depth, T2 is width, in the current database length unit (m).
            _call(
                set_rectangle,
                str(item["id"]),
                material_name,
                depth_m,
                width_m,
                label=f"PropFrame.SetRectangle {item.get('id')}",
            )
            defined += 1
    slab_defined = _define_area_properties(sap_model, structural, sections, project_length)
    if defined == 0 and slab_defined == 0:
        raise _NoData("No frame or area sections defined in PEM export")
    return {"frame_sections": defined, "area_sections": slab_defined}


def _define_area_properties(
    sap_model: Any,
    structural: dict[str, Any],
    sections: dict[str, Any],
    project_length: str,
) -> int:
    slabs = list(sections.get("slabs") or [])
    walls = list(sections.get("walls") or [])
    if not slabs and not walls:
        return 0
    prop_area = getattr(sap_model, "PropArea", None)
    if prop_area is None:
        raise RuntimeError("Vendor API missing: PropArea. Slab or wall sections were not created.")
    defined = 0
    set_slab = getattr(prop_area, "SetSlab", None)
    if slabs:
        if not callable(set_slab):
            raise RuntimeError("Vendor API missing: PropArea.SetSlab")
        for item in slabs:
            unit = _section_length_unit(item, project_length)
            thickness_m = _length_m(float(item["thickness"]), unit, label=str(item.get("id")))
            # SlabType 0 = slab, ShellType 1 = thin shell. Thickness is in metres.
            _call(
                set_slab,
                str(item["id"]),
                0,
                1,
                _area_material_name(structural, item),
                thickness_m,
                label=f"PropArea.SetSlab {item.get('id')}",
            )
            defined += 1
    set_wall = getattr(prop_area, "SetWall", None)
    if walls:
        if not callable(set_wall):
            raise RuntimeError("Vendor API missing: PropArea.SetWall")
        for item in walls:
            unit = _section_length_unit(item, project_length)
            thickness_m = _length_m(float(item["thickness"]), unit, label=str(item.get("id")))
            _call(
                set_wall,
                str(item["id"]),
                1,
                1,
                _area_material_name(structural, item),
                thickness_m,
                label=f"PropArea.SetWall {item.get('id')}",
            )
            defined += 1
    return defined


def _area_material_name(structural: dict[str, Any], item: dict[str, Any]) -> str:
    metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
    if metadata.get("material_id"):
        return str(metadata["material_id"])
    concrete = (structural.get("materials") or {}).get("concrete") or []
    if len(concrete) == 1:
        return str(concrete[0]["id"])
    raise RuntimeError(f"Area section {item.get('id')} has no material_id and the PEM does not have one concrete material")


def _define_points(sap_model: Any, structural: dict[str, Any], project_length: str) -> dict[str, str]:
    add_point = _require_api(sap_model, "PointObj", "AddCartesian")
    points = structural.get("geometry", {}).get("points", [])
    if not points:
        raise _NoData("No geometry points defined in PEM export")
    length_unit = _project_length_unit(structural, project_length)
    mapping: dict[str, str] = {}
    for item in points:
        point_id = str(item["id"])
        x = _length_m(float(item["x"]), length_unit, label=point_id)
        y = _length_m(float(item["y"]), length_unit, label=point_id)
        z = _length_m(float(item["z"]), length_unit, label=point_id)
        result = _call(add_point, x, y, z, point_id, point_id, "Global", label=f"PointObj.AddCartesian {point_id}")
        name = point_id
        if isinstance(result, tuple) and len(result) > 1 and result[1]:
            name = str(result[1])
        mapping[point_id] = name
    return mapping


def _define_frames(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
) -> dict[str, int]:
    add_frame = _require_api(sap_model, "FrameObj", "AddByPoint")
    members = [
        item
        for item in structural.get("members", {}).get("members", [])
        if str(item.get("member_type", "")).upper() in {"BEAM", "COLUMN", "BRACE"}
    ]
    if not members:
        raise _NoData("No frame members defined in PEM export")
    missing: list[str] = []
    count = 0
    for item in members:
        member_name = str(item["id"])
        start_id = item.get("start_point_id")
        end_id = item.get("end_point_id")
        if not start_id or not end_id:
            missing.append(f"{member_name} has no start or end point")
            continue
        start_name = point_name_map.get(str(start_id))
        end_name = point_name_map.get(str(end_id))
        if not start_name or not end_name:
            missing.append(f"{member_name} points are not in the geometry")
            continue
        if not item.get("section_id"):
            missing.append(f"{member_name} has no section_id")
            continue
        _call(
            add_frame,
            start_name,
            end_name,
            member_name,
            str(item["section_id"]),
            member_name,
            "Global",
            label=f"FrameObj.AddByPoint {member_name}",
        )
        count += 1
    if missing:
        raise RuntimeError("Frame members could not be mapped: " + "; ".join(missing))
    return {"defined": count}


def _define_areas(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
) -> dict[str, Any]:
    areas = {str(item["id"]): item for item in structural.get("geometry", {}).get("areas", [])}
    area_members = [
        item
        for item in structural.get("members", {}).get("members", [])
        if str(item.get("member_type", "")).upper() in {"SLAB", "WALL"}
    ]
    if not area_members:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    add_area = _require_api(sap_model, "AreaObj", "AddByPoint")
    count = 0
    for item in area_members:
        area = areas.get(str(item.get("area_id") or ""))
        if area is None:
            raise RuntimeError(f"Area member {item.get('id')} has no geometry area")
        boundary = [str(point_id) for point_id in area.get("boundary_point_ids") or []]
        if len(boundary) < 3:
            raise RuntimeError(f"Area member {item.get('id')} needs at least three boundary points")
        names = []
        for point_id in boundary:
            mapped = point_name_map.get(point_id)
            if not mapped:
                raise RuntimeError(f"Area member {item.get('id')} point {point_id} is not in the geometry")
            names.append(mapped)
        _call(
            add_area,
            len(names),
            names,
            str(item["id"]),
            str(item.get("section_id") or ""),
            label=f"AreaObj.AddByPoint {item.get('id')}",
        )
        count += 1
    return {"defined": count}


def _define_supports(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
) -> dict[str, Any]:
    supports = structural.get("supports") or []
    if not supports:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    set_restraint = _require_api(sap_model, "PointObj", "SetRestraint")
    count = 0
    notes: list[str] = []
    for item in supports:
        point_name = point_name_map.get(str(item.get("point_id")))
        if not point_name:
            raise RuntimeError(f"Support {item.get('id')} point {item.get('point_id')} is not in the geometry")
        support_type = str(item.get("support_type") or "")
        if not support_type:
            raise RuntimeError(f"Support {item.get('id')} has no support_type")
        restraint = _support_restraint(item)
        if support_type == SupportType.ROLLER.value:
            notes.append(f"Support {item.get('id')} ROLLER releases global X and all rotations")
        _call(set_restraint, point_name, restraint, label=f"PointObj.SetRestraint {point_name}")
        count += 1
    return {"defined": count, "notes": "; ".join(notes)}


def _support_restraint(item: dict[str, Any]) -> list[bool]:
    support_type = str(item.get("support_type") or "")
    if support_type == SupportType.CUSTOM.value:
        return [
            bool(item.get("restraint_tx")),
            bool(item.get("restraint_ty")),
            bool(item.get("restraint_tz")),
            bool(item.get("restraint_rx")),
            bool(item.get("restraint_ry")),
            bool(item.get("restraint_rz")),
        ]
    if support_type == SupportType.PINNED.value:
        return [True, True, True, False, False, False]
    if support_type == SupportType.ROLLER.value:
        return [False, True, True, False, False, False]
    if support_type == SupportType.FIXED.value:
        return [True, True, True, True, True, True]
    raise RuntimeError(f"Support type '{support_type}' is not FIXED, PINNED, ROLLER, or CUSTOM")


def _define_load_patterns(sap_model: Any, structural: dict[str, Any]) -> dict[str, Any]:
    load_cases = structural.get("load_cases") or []
    if not load_cases:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    add_pattern = _require_api(sap_model, "LoadPatterns", "Add")
    count = 0
    for item in load_cases:
        name = str(item["id"])
        load_type = _load_pattern_type(str(item.get("category") or "OTHER"))
        metadata = item.get("metadata") if isinstance(item.get("metadata"), dict) else {}
        if "self_weight_multiplier" in metadata:
            self_weight = float(metadata["self_weight_multiplier"])
        else:
            self_weight = 0.0
        _call(add_pattern, name, load_type, self_weight, True, label=f"LoadPatterns.Add {name}")
        count += 1
    return {"defined": count, "self_weight": "metadata self_weight_multiplier, otherwise 0"}


def _load_pattern_type(category: str) -> int:
    return _LOAD_PATTERN_TYPES.get(category.upper(), 8)


def _define_load_cases(sap_model: Any, structural: dict[str, Any]) -> dict[str, Any]:
    load_cases = structural.get("load_cases") or []
    if not load_cases:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    static_linear = getattr(getattr(sap_model, "LoadCases", None), "StaticLinear", None)
    set_case = getattr(static_linear, "SetCase", None)
    if not callable(set_case):
        return {
            "defined": len(load_cases),
            "method": "LoadPatterns.Add created the linear static case because AddLoadCase was true",
        }
    for item in load_cases:
        _call(set_case, str(item["id"]), label=f"LoadCases.StaticLinear.SetCase {item.get('id')}")
    return {"defined": len(load_cases), "method": "LoadCases.StaticLinear.SetCase"}


def _define_loads(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
) -> dict[str, Any]:
    loads = [
        (str(case["id"]), load)
        for case in structural.get("load_cases") or []
        for load in case.get("loads") or []
    ]
    if not loads:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    set_distributed = _require_api(sap_model, "FrameObj", "SetLoadDistributed")
    set_point = getattr(getattr(sap_model, "PointObj", None), "SetLoadForce", None)
    set_area = getattr(getattr(sap_model, "AreaObj", None), "SetLoadUniform", None)
    count = 0
    for pattern_name, load in loads:
        distribution = str(load.get("distribution") or "").upper()
        unit = str(load.get("unit") or "")
        if not unit:
            raise RuntimeError(f"Load {load.get('id')} has no unit")
        magnitude = float(load.get("magnitude"))
        direction = _load_direction(load)
        if distribution in {"MEMBER", "LINE"}:
            scale = _LINE_LOAD_TO_KN_PER_M.get(_unit_token(unit))
            if scale is None:
                raise RuntimeError(
                    f"Distributed load {load.get('id')} unit '{unit}' is not force per length"
                )
            member_name = str(load.get("member_id") or "")
            if not member_name:
                raise RuntimeError(f"Distributed load {load.get('id')} has no member_id")
            value = magnitude * scale
            _call(
                set_distributed,
                member_name,
                pattern_name,
                1,
                direction,
                0.0,
                1.0,
                value,
                value,
                label=f"FrameObj.SetLoadDistributed {member_name}",
            )
            count += 1
        elif distribution in {"POINT", "NODAL"}:
            if not callable(set_point):
                raise _ApiUnavailable("Vendor API missing: PointObj.SetLoadForce")
            scale = _FORCE_TO_KN.get(_unit_token(unit))
            if scale is None:
                raise RuntimeError(f"Point load {load.get('id')} unit '{unit}' is not a force unit")
            point_name = point_name_map.get(str(load.get("point_id") or ""))
            if not point_name:
                raise RuntimeError(f"Point load {load.get('id')} point is not in the geometry")
            force = magnitude * scale
            vector = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
            vector[_force_index(load)] = force if direction != 10 else -abs(force)
            _call(set_point, point_name, pattern_name, vector, label=f"PointObj.SetLoadForce {point_name}")
            count += 1
        elif distribution in {"AREA", "SURFACE"}:
            if not callable(set_area):
                raise _ApiUnavailable("Vendor API missing: AreaObj.SetLoadUniform")
            scale = _STRESS_TO_KPA.get(_unit_token(unit))
            if scale is None:
                raise RuntimeError(f"Area load {load.get('id')} unit '{unit}' is not a pressure unit")
            area_name = str(load.get("member_id") or load.get("area_id") or "")
            if not area_name:
                raise RuntimeError(f"Area load {load.get('id')} has no area or member id")
            _call(
                set_area,
                area_name,
                pattern_name,
                magnitude * scale,
                direction,
                label=f"AreaObj.SetLoadUniform {area_name}",
            )
            count += 1
        else:
            raise RuntimeError(f"Load {load.get('id')} distribution '{distribution}' is not supported")
    return {"defined": count}


def _load_direction(load: dict[str, Any]) -> int:
    dx = float(load.get("direction_x") or 0.0)
    dy = float(load.get("direction_y") or 0.0)
    dz = float(load.get("direction_z") if load.get("direction_z") is not None else -1.0)
    if abs(dz) >= abs(dx) and abs(dz) >= abs(dy) and dz < 0:
        return 10  # gravity, positive downward in the CSI load direction enum
    if abs(dx) >= abs(dy) and abs(dx) >= abs(dz):
        return 4
    if abs(dy) >= abs(dx) and abs(dy) >= abs(dz):
        return 5
    return 6


def _force_index(load: dict[str, Any]) -> int:
    dx = abs(float(load.get("direction_x") or 0.0))
    dy = abs(float(load.get("direction_y") or 0.0))
    dz = abs(float(load.get("direction_z") if load.get("direction_z") is not None else -1.0))
    if dx >= dy and dx >= dz:
        return 0
    if dy >= dx and dy >= dz:
        return 1
    return 2


def _define_load_combinations(sap_model: Any, structural: dict[str, Any]) -> dict[str, Any]:
    combinations = structural.get("load_combinations") or []
    if not combinations:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    add_combo = _require_api(sap_model, "RespCombo", "Add")
    set_case_list = _require_api(sap_model, "RespCombo", "SetCaseList")
    known_cases = {str(item["id"]) for item in structural.get("load_cases") or []}
    count = 0
    for combo in combinations:
        combo_name = str(combo["id"])
        _call(add_combo, combo_name, 0, label=f"RespCombo.Add {combo_name}")
        terms = combo.get("terms") or []
        if not terms:
            raise RuntimeError(f"Load combination {combo_name} has no terms")
        for term in terms:
            case_name = str(term.get("load_case_id") or "")
            if case_name not in known_cases:
                raise RuntimeError(f"Load combination {combo_name} references unknown load case {case_name}")
            factor = float(term.get("factor"))
            # CNameType 0 = load case. The case name is the PEM load case id.
            _call(
                set_case_list,
                combo_name,
                0,
                case_name,
                factor,
                label=f"RespCombo.SetCaseList {combo_name}/{case_name}",
            )
        count += 1
    return {"defined": count}


def _define_releases(sap_model: Any, structural: dict[str, Any]) -> dict[str, Any]:
    elements = (structural.get("analysis_model") or {}).get("elements") or []
    released = [
        item
        for item in elements
        if item.get("start_release") or item.get("end_release")
    ]
    if not released:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    set_releases = _require_api(sap_model, "FrameObj", "SetReleases")
    count = 0
    for item in released:
        member_id = str(item.get("member_id") or item.get("id") or "")
        if not member_id:
            raise RuntimeError("An analysis element release has no member id")
        start = _release_flags(item.get("start_release") or {})
        end = _release_flags(item.get("end_release") or {})
        _call(set_releases, member_id, start, end, label=f"FrameObj.SetReleases {member_id}")
        count += 1
    return {"defined": count}


def _release_flags(raw: dict[str, Any]) -> list[bool]:
    return [
        bool(raw.get("ux") or raw.get("u1")),
        bool(raw.get("uy") or raw.get("u2")),
        bool(raw.get("uz") or raw.get("u3")),
        bool(raw.get("rx") or raw.get("r1")),
        bool(raw.get("ry") or raw.get("r2")),
        bool(raw.get("rz") or raw.get("r3")),
    ]


def _define_diaphragms(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
) -> dict[str, Any]:
    diaphragms = structural.get("diaphragms") or []
    if not diaphragms:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    set_diaphragm = _require_api(sap_model, "PointObj", "SetDiaphragm")
    count = 0
    for item in diaphragms:
        nodes = [str(node) for node in item.get("node_ids") or []]
        if not nodes:
            raise RuntimeError(f"Diaphragm {item.get('id')} has no node_ids")
        for node_id in nodes:
            point_name = point_name_map.get(node_id)
            if not point_name:
                raise RuntimeError(f"Diaphragm {item.get('id')} node {node_id} is not in the geometry")
            _call(set_diaphragm, point_name, str(item["id"]), label=f"PointObj.SetDiaphragm {point_name}")
            count += 1
    return {"defined": count}


def _define_analysis_settings(sap_model: Any, structural: dict[str, Any]) -> dict[str, Any]:
    load_cases = structural.get("load_cases") or []
    if not load_cases:
        return {"status": "SKIPPED_EMPTY", "defined": 0}
    set_flag = _require_api(sap_model, "Analyze", "SetRunCaseFlag")
    count = 0
    for item in load_cases:
        _call(set_flag, str(item["id"]), True, 0, label=f"Analyze.SetRunCaseFlag {item.get('id')}")
        count += 1
    return {"cases_marked_to_run": count}


def _count_items(structural: dict[str, Any], key: str) -> int:
    materials = structural.get(key, {})
    return (
        len(materials.get("concrete", []))
        + len(materials.get("steel", []))
        + len(materials.get("reinforcement", []))
    )


def _section_count(structural: dict[str, Any]) -> int:
    sections = structural.get("sections", {})
    return (
        len(sections.get("beams", []))
        + len(sections.get("columns", []))
        + len(sections.get("slabs", []))
        + len(sections.get("walls", []))
    )
