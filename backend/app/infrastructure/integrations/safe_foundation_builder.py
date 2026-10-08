"""Build an isolated spread-footing model in SAFE from a validated specification.

The specification must already contain explicit geometry, concrete strength, a
user-provided subgrade modulus, supports, and column point loads. This module
does not invent any of those values.
"""

from __future__ import annotations

from typing import Any

from app.infrastructure.integrations.csi_pem_builder import (
    CSI_UNIT_SYSTEM_KN_M_C,
    _STRESS_TO_KPA,
    _call,
    _require_api,
    _unit_token,
)


def build_safe_foundation_model(sap_model: Any, spec: dict[str, Any]) -> dict[str, Any]:
    if not spec.get("ready"):
        missing = spec.get("missing") or ["A validated SAFE foundation specification is required"]
        return {
            "vendor_build_status": "FAILED",
            "failure_class": "MISSING_INPUTS",
            "missing": missing,
            "stages": [{"stage": "specification", "status": "FAILED", "detail": "; ".join(missing)}],
            "analysis_executed": False,
            "csi_unit_system": CSI_UNIT_SYSTEM_KN_M_C,
            "result_authority": "NONE",
        }
    stages: list[dict[str, Any]] = []
    try:
        _stage(stages, "materials", lambda: _materials(sap_model, spec))
        _stage(stages, "footing_properties", lambda: _properties(sap_model, spec))
        _stage(stages, "geometry_and_soil", lambda: _geometry(sap_model, spec))
        _stage(stages, "loads", lambda: _loads(sap_model, spec))
        _stage(stages, "load_combinations", lambda: _combinations(sap_model, spec))
        _stage(stages, "analysis_settings", lambda: _analysis_settings(sap_model, spec))
    except Exception as exc:  # noqa: BLE001
        stages.append({"stage": "safe_foundation", "status": "FAILED", "detail": str(exc)})
    failed = any(item["status"] == "FAILED" for item in stages)
    return {
        "vendor_build_status": "FAILED" if failed else "COMPLETE",
        "failure_class": "MODEL_BUILD_FAILURE" if failed else None,
        "stages": stages,
        "supported_type": spec.get("supported_type"),
        "analysis_executed": False,
        "csi_unit_system": CSI_UNIT_SYSTEM_KN_M_C,
        "result_authority": "SAFE" if not failed else "NONE",
        "preliminary_internal_footing_ids": spec.get("preliminary_internal_footing_ids") or [],
        "notes": spec.get("notes") or [],
    }


def _stage(stages: list[dict[str, Any]], name: str, action: Any) -> None:
    try:
        detail = action()
        stages.append({"stage": name, "status": "COMPLETE", "detail": str(detail)})
    except Exception as exc:  # noqa: BLE001
        stages.append({"stage": name, "status": "FAILED", "detail": str(exc)})
        raise


def _materials(sap_model: Any, spec: dict[str, Any]) -> str:
    concrete = spec["concrete"]
    set_material = _require_api(sap_model, "PropMaterial", "SetMaterial")
    set_concrete = _require_api(sap_model, "PropMaterial", "SetOConcrete_1")
    name = str(concrete["id"])
    factor = _STRESS_TO_KPA.get(_unit_token(str(concrete["fc_unit"])))
    if factor is None:
        raise RuntimeError(f"Concrete strength unit '{concrete['fc_unit']}' cannot be converted")
    fc_kpa = float(concrete["fc"]) * factor
    _call(set_material, name, 2, label=f"PropMaterial.SetMaterial {name}")
    _call(set_concrete, name, fc_kpa, False, 0, 1, 2, 0, 0, 0, 0, 0, label=f"PropMaterial.SetOConcrete_1 {name}")
    return f"fc_kN_m2={fc_kpa:.3f}"


def _properties(sap_model: Any, spec: dict[str, Any]) -> str:
    set_slab = _require_api(sap_model, "PropArea", "SetSlab")
    material = str(spec["concrete"]["id"])
    for footing in spec["footings"]:
        # SlabType 6 = footing, ShellType 2 = thick shell. Thickness is metres.
        _call(
            set_slab,
            f"FND-{footing['id']}",
            6,
            2,
            material,
            float(footing["thickness_m"]),
            label=f"PropArea.SetSlab {footing['id']}",
        )
    return f"footings={len(spec['footings'])}"


def _geometry(sap_model: Any, spec: dict[str, Any]) -> str:
    add_point = _require_api(sap_model, "PointObj", "AddCartesian")
    add_area = _require_api(sap_model, "AreaObj", "AddByPoint")
    set_spring = _require_api(sap_model, "PointObj", "SetSpring")
    set_restraint = _require_api(sap_model, "PointObj", "SetRestraint")
    ks = float(spec["subgrade_modulus_kN_m3"])
    for footing in spec["footings"]:
        cx = float(footing["x_m"])
        cy = float(footing["y_m"])
        cz = float(footing["z_m"])
        half_l = float(footing["length_m"]) / 2.0
        half_w = float(footing["width_m"]) / 2.0
        corners = [
            (cx - half_l, cy - half_w),
            (cx + half_l, cy - half_w),
            (cx + half_l, cy + half_w),
            (cx - half_l, cy + half_w),
        ]
        names: list[str] = []
        area = float(footing["length_m"]) * float(footing["width_m"])
        kz = ks * area / 4.0
        for index, (x, y) in enumerate(corners, start=1):
            name = f"{footing['id']}-C{index}"
            _call(add_point, x, y, cz, name, name, "Global", label=f"PointObj.AddCartesian {name}")
            # Vertical stiffness only. Horizontal restraints come from the PEM support.
            _call(set_spring, name, [0.0, 0.0, kz, 0.0, 0.0, 0.0], label=f"PointObj.SetSpring {name}")
            _call(
                set_restraint,
                name,
                list(footing.get("restraint") or [False, False, False, False, False, False]),
                label=f"PointObj.SetRestraint {name}",
            )
            names.append(name)
        _call(
            add_area,
            4,
            names,
            str(footing["id"]),
            f"FND-{footing['id']}",
            label=f"AreaObj.AddByPoint {footing['id']}",
        )
    return f"subgrade_kN_m3={ks}"


def _loads(sap_model: Any, spec: dict[str, Any]) -> str:
    add_pattern = _require_api(sap_model, "LoadPatterns", "Add")
    set_force = _require_api(sap_model, "PointObj", "SetLoadForce")
    corner_names = {
        item["point_id"]: [f"{item['id']}-C{index}" for index in range(1, 5)]
        for item in spec["footings"]
    }
    count = 0
    for case in spec["load_cases"]:
        _call(add_pattern, str(case["id"]), 8, 0.0, True, label=f"LoadPatterns.Add {case['id']}")
        for load in case["loads"]:
            names = corner_names.get(load["point_id"])
            if not names:
                raise RuntimeError(f"Load {load.get('id')} point is not a SAFE footing")
            vector = [
                float(load["fx_kN"]) / 4.0,
                float(load["fy_kN"]) / 4.0,
                float(load["fz_kN"]) / 4.0,
                0.0,
                0.0,
                0.0,
            ]
            for point_name in names:
                _call(set_force, point_name, str(case["id"]), vector, label=f"PointObj.SetLoadForce {point_name}")
                count += 1
    if count == 0:
        raise RuntimeError("SAFE specification contains no column point loads")
    return f"point_loads={count}"


def _combinations(sap_model: Any, spec: dict[str, Any]) -> str:
    combinations = spec.get("combinations") or []
    if not combinations:
        return "no combinations in the specification"
    add_combo = _require_api(sap_model, "RespCombo", "Add")
    set_case_list = _require_api(sap_model, "RespCombo", "SetCaseList")
    for combo in combinations:
        _call(add_combo, str(combo["id"]), 0, label=f"RespCombo.Add {combo['id']}")
        for term in combo["terms"]:
            _call(
                set_case_list,
                str(combo["id"]),
                0,
                str(term["load_case_id"]),
                float(term["factor"]),
                label=f"RespCombo.SetCaseList {combo['id']}",
            )
    return f"combinations={len(combinations)}"


def _analysis_settings(sap_model: Any, spec: dict[str, Any]) -> str:
    set_flag = _require_api(sap_model, "Analyze", "SetRunCaseFlag")
    for case in spec["load_cases"]:
        _call(set_flag, str(case["id"]), True, 0, label=f"Analyze.SetRunCaseFlag {case['id']}")
    return f"cases={len(spec['load_cases'])}"
