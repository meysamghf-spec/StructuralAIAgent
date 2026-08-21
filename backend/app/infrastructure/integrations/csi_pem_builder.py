"""Push PEM structural data into CSI SapModel when the vendor COM API is available."""

from __future__ import annotations

from typing import Any

from app.domain.models.integration import ExternalModelExport
from app.domain.models.pem_structural import SupportType


LENGTH_TO_METERS = {
    "ft": 0.3048,
    "m": 1.0,
    "in": 0.0254,
    "mm": 0.001,
}

FORCE_TO_KN = {
    "kip": 4.4482216153,
    "kN": 1.0,
    "N": 0.001,
    "lbf": 0.0044482216153,
}


def build_vendor_model_from_export(
    sap_model: Any,
    export: ExternalModelExport,
    *,
    length_unit: str = "ft",
    force_unit: str = "kip",
) -> dict[str, Any]:
    """Attempt progressive PEM → CSI model construction. Never fabricates solver success."""
    length_scale = LENGTH_TO_METERS.get(length_unit.lower(), 0.3048)
    force_scale = FORCE_TO_KN.get(force_unit.lower(), 4.4482216153)
    stages: list[dict[str, Any]] = []
    structural = export.structural_model
    point_name_map: dict[str, str] = {}

    _run_stage(stages, "materials", lambda: _define_materials(sap_model, structural))
    _run_stage(stages, "sections", lambda: _define_sections(sap_model, structural, length_scale))
    point_name_map = _run_stage(
        stages,
        "geometry",
        lambda: _define_points(sap_model, structural, length_scale),
        default={},
    )
    _run_stage(
        stages,
        "members",
        lambda: _define_frames(sap_model, structural, point_name_map),
    )
    _run_stage(
        stages,
        "supports",
        lambda: _define_supports(sap_model, structural, point_name_map),
    )
    _run_stage(stages, "load_cases", lambda: _define_load_patterns(sap_model, structural))
    _run_stage(
        stages,
        "loads",
        lambda: _define_member_loads(sap_model, structural, point_name_map, force_scale),
    )
    _run_stage(stages, "load_combinations", lambda: _define_load_combinations(sap_model, structural))

    completed = sum(1 for stage in stages if stage["status"] == "COMPLETE")
    failed = sum(1 for stage in stages if stage["status"] == "FAILED")
    skipped = sum(1 for stage in stages if stage["status"] == "SKIPPED")

    if failed > 0 and completed == 0:
        vendor_build_status = "FAILED"
    elif failed > 0 or skipped > 0:
        vendor_build_status = "PARTIAL"
    elif completed == len(stages):
        vendor_build_status = "COMPLETE"
    else:
        vendor_build_status = "PARTIAL"

    return {
        "vendor_build_status": vendor_build_status,
        "stages": stages,
        "counts": {
            "materials": _count_items(structural, "materials"),
            "sections": _section_count(structural),
            "points": len(structural.get("geometry", {}).get("points", [])),
            "members": len(structural.get("members", {}).get("members", [])),
            "supports": len(structural.get("supports", [])),
            "load_cases": len(structural.get("load_cases", [])),
            "load_combinations": len(structural.get("load_combinations", [])),
        },
        "length_unit": length_unit,
        "force_unit": force_unit,
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
        stages.append({"stage": name, "status": "COMPLETE", "detail": _stage_detail(result)})
        return default if result is None else result
    except _ApiUnavailable as exc:
        stages.append({"stage": name, "status": "SKIPPED", "detail": str(exc)})
        return default
    except Exception as exc:  # noqa: BLE001
        stages.append({"stage": name, "status": "FAILED", "detail": str(exc)})
        return default


def _stage_detail(result: Any) -> str:
    if isinstance(result, dict):
        return ", ".join(f"{key}={value}" for key, value in result.items())
    if isinstance(result, int):
        return f"count={result}"
    return "ok"


class _ApiUnavailable(RuntimeError):
    pass


def _require_api(obj: Any, *path: str) -> Any:
    current = obj
    for segment in path:
        current = getattr(current, segment, None)
        if current is None:
            raise _ApiUnavailable(f"Vendor API missing: {'.'.join(path)}")
    if not callable(current):
        raise _ApiUnavailable(f"Vendor API not callable: {'.'.join(path)}")
    return current


def _define_materials(sap_model: Any, structural: dict[str, Any]) -> dict[str, int]:
    set_material = _require_api(sap_model, "PropMaterial", "SetMaterial")
    materials = structural.get("materials", {})
    count = 0
    for item in materials.get("concrete", []):
        name = str(item["id"])
        fc_mpa = float(item.get("compressive_strength", 4000.0)) * 0.00689475728
        set_material(name, 2, fc_mpa)
        count += 1
    for item in materials.get("steel", []):
        name = str(item["id"])
        fy_mpa = float(item.get("yield_strength", 50000.0)) * 0.00689475728
        set_material(name, 1, fy_mpa)
        count += 1
    if count == 0:
        raise _ApiUnavailable("No materials defined in PEM export")
    return {"defined": count}


def _define_sections(sap_model: Any, structural: dict[str, Any], length_scale: float) -> dict[str, int]:
    set_rectangle = _require_api(sap_model, "PropFrame", "SetRectangle")
    sections = structural.get("sections", {})
    count = 0
    for bucket in ("beams", "columns"):
        for item in sections.get(bucket, []):
            name = str(item["id"])
            width_m = float(item.get("width", 12.0)) * 0.0254
            depth_m = float(item.get("depth", 18.0)) * 0.0254
            material_name = _default_material_name(structural)
            set_rectangle(name, material_name, depth_m, width_m)
            count += 1
    if count == 0:
        raise _ApiUnavailable("No frame sections defined in PEM export")
    return {"defined": count}


def _default_material_name(structural: dict[str, Any]) -> str:
    materials = structural.get("materials", {})
    if materials.get("concrete"):
        return str(materials["concrete"][0]["id"])
    if materials.get("steel"):
        return str(materials["steel"][0]["id"])
    raise _ApiUnavailable("No material available for section assignment")


def _define_points(
    sap_model: Any,
    structural: dict[str, Any],
    length_scale: float,
) -> dict[str, str]:
    add_point = _require_api(sap_model, "PointObj", "AddCartesian")
    points = structural.get("geometry", {}).get("points", [])
    if not points:
        raise _ApiUnavailable("No geometry points defined in PEM export")
    mapping: dict[str, str] = {}
    for item in points:
        point_id = str(item["id"])
        x = float(item["x"]) * length_scale
        y = float(item["y"]) * length_scale
        z = float(item["z"]) * length_scale
        ret, name, *_rest = add_point(x, y, z, point_id, point_id, "Global")
        if ret not in (0, None):
            raise RuntimeError(f"PointObj.AddCartesian failed for {point_id} with code {ret}")
        mapping[point_id] = str(name or point_id)
    return mapping


def _define_frames(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
) -> dict[str, int]:
    add_frame = _require_api(sap_model, "FrameObj", "AddByPoint")
    members = structural.get("members", {}).get("members", [])
    if not members:
        raise _ApiUnavailable("No members defined in PEM export")
    count = 0
    for item in members:
        start_id = item.get("start_point_id")
        end_id = item.get("end_point_id")
        if not start_id or not end_id:
            continue
        start_name = point_name_map.get(str(start_id))
        end_name = point_name_map.get(str(end_id))
        if not start_name or not end_name:
            continue
        member_name = str(item["id"])
        section_name = str(item.get("section_id") or _first_section_name(structural))
        ret, name = add_frame(start_name, end_name, member_name, section_name, 0.0)
        if ret not in (0, None):
            raise RuntimeError(f"FrameObj.AddByPoint failed for {member_name} with code {ret}")
        count += 1
    if count == 0:
        raise RuntimeError("No frame members could be mapped to geometry points")
    return {"defined": count}


def _first_section_name(structural: dict[str, Any]) -> str:
    sections = structural.get("sections", {})
    for bucket in ("beams", "columns"):
        items = sections.get(bucket, [])
        if items:
            return str(items[0]["id"])
    raise _ApiUnavailable("No section available for member assignment")


def _define_supports(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
) -> dict[str, int]:
    set_restraint = _require_api(sap_model, "PointObj", "SetRestraint")
    supports = structural.get("supports", [])
    count = 0
    for item in supports:
        point_name = point_name_map.get(str(item.get("point_id")))
        if not point_name:
            continue
        restraint = _support_restraint(str(item.get("support_type", SupportType.FIXED.value)))
        ret = set_restraint(point_name, restraint)
        if ret not in (0, None):
            raise RuntimeError(f"PointObj.SetRestraint failed for {point_name} with code {ret}")
        count += 1
    return {"defined": count}


def _support_restraint(support_type: str) -> list[bool]:
    if support_type == SupportType.PINNED.value:
        return [True, True, True, False, False, False]
    if support_type == SupportType.ROLLER.value:
        return [False, True, True, False, False, False]
    return [True, True, True, True, True, True]


def _define_load_patterns(sap_model: Any, structural: dict[str, Any]) -> dict[str, int]:
    add_pattern = _require_api(sap_model, "LoadPatterns", "Add")
    load_cases = structural.get("load_cases", [])
    count = 0
    for item in load_cases:
        name = str(item["id"])
        load_type = _load_pattern_type(str(item.get("category", "OTHER")))
        ret = add_pattern(name, load_type, 1.0, True)
        if ret not in (0, None):
            raise RuntimeError(f"LoadPatterns.Add failed for {name} with code {ret}")
        count += 1
    return {"defined": count}


def _load_pattern_type(category: str) -> int:
    mapping = {
        "DEAD": 1,
        "LIVE": 3,
        "WIND": 6,
        "SEISMIC": 5,
        "SNOW": 8,
    }
    return mapping.get(category.upper(), 8)


def _define_member_loads(
    sap_model: Any,
    structural: dict[str, Any],
    point_name_map: dict[str, str],
    force_scale: float,
) -> dict[str, int]:
    set_load = _require_api(sap_model, "FrameObj", "SetLoadDistributed")
    count = 0
    for load_case in structural.get("load_cases", []):
        pattern_name = str(load_case["id"])
        for load in load_case.get("loads", []):
            if str(load.get("distribution", "")).upper() != "MEMBER":
                continue
            member_name = str(load.get("member_id") or "")
            if not member_name:
                continue
            magnitude_kn_per_m = float(load.get("magnitude", 0.0)) * force_scale
            ret = set_load(member_name, pattern_name, 1, 10, 0.0, 1.0, magnitude_kn_per_m, magnitude_kn_per_m)
            if ret not in (0, None):
                raise RuntimeError(
                    f"FrameObj.SetLoadDistributed failed for {member_name} with code {ret}"
                )
            count += 1
    return {"defined": count}


def _define_load_combinations(sap_model: Any, structural: dict[str, Any]) -> dict[str, int]:
    add_combo = _require_api(sap_model, "RespCombo", "Add")
    set_case_list = _require_api(sap_model, "RespCombo", "SetCaseList")
    combinations = structural.get("load_combinations", [])
    count = 0
    for combo in combinations:
        combo_name = str(combo["id"])
        ret = add_combo(combo_name, 0)
        if ret not in (0, None):
            raise RuntimeError(f"RespCombo.Add failed for {combo_name} with code {ret}")
        for index, term in enumerate(combo.get("terms", []), start=1):
            case_name = str(term.get("load_case_id"))
            factor = float(term.get("factor", 1.0))
            ret = set_case_list(combo_name, index, case_name, factor)
            if ret not in (0, None):
                raise RuntimeError(
                    f"RespCombo.SetCaseList failed for {combo_name}/{case_name} with code {ret}"
                )
        count += 1
    return {"defined": count}


def _count_items(structural: dict[str, Any], key: str) -> int:
    materials = structural.get(key, {})
    return len(materials.get("concrete", [])) + len(materials.get("steel", []))


def _section_count(structural: dict[str, Any]) -> int:
    sections = structural.get("sections", {})
    return len(sections.get("beams", [])) + len(sections.get("columns", []))
