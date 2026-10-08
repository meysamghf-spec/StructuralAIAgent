"""Normalize vendor-specific solver output into vendor-neutral engineering results."""

from __future__ import annotations

from typing import Any

from app.domain.models.engineering_results import NormalizedEngineeringResults

_VENDOR_TYPE_MAP = {
    "reactions": "joint_reactions",
    "joint_reactions": "joint_reactions",
    "member_forces": "frame_forces",
    "frame_force": "frame_forces",
    "frame_forces": "frame_forces",
    "joint_displacements": "joint_displacements",
    "joint_displ": "joint_displacements",
    "story_drifts": "story_drifts",
    "story_drift": "story_drifts",
    "modal_periods": "modal_periods",
    "modal_period": "modal_periods",
    "modal_frequencies": "modal_frequencies",
    "mass_participation": "mass_participation",
    "load_combination_results": "load_combination_results",
}


def normalize_vendor_results(raw_results: dict[str, Any]) -> NormalizedEngineeringResults:
    normalized = NormalizedEngineeringResults()

    for vendor_key, target_field in _VENDOR_TYPE_MAP.items():
        payload = raw_results.get(vendor_key)
        if payload in (None, {}, []):
            continue
        entries = _normalize_payload(vendor_key, payload)
        if entries:
            getattr(normalized, target_field).extend(entries)

    if raw_results.get("frame_moments"):
        normalized.frame_moments.extend(_normalize_payload("frame_moments", raw_results["frame_moments"]))
    if raw_results.get("frame_axial_forces"):
        normalized.frame_axial_forces.extend(
            _normalize_payload("frame_axial_forces", raw_results["frame_axial_forces"])
        )
    if raw_results.get("frame_shear"):
        normalized.frame_shear.extend(_normalize_payload("frame_shear", raw_results["frame_shear"]))
    if raw_results.get("modal_frequencies"):
        normalized.modal_frequencies.extend(
            _normalize_payload("modal_frequencies", raw_results["modal_frequencies"])
        )
    if raw_results.get("mass_participation"):
        normalized.mass_participation.extend(
            _normalize_payload("mass_participation", raw_results["mass_participation"])
        )
    if raw_results.get("shell_results"):
        normalized.shell_results.extend(_normalize_payload("shell_results", raw_results["shell_results"]))

    return normalized


def _normalize_payload(result_type: str, payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [_normalize_entry(result_type, item) for item in payload if item is not None]
    if isinstance(payload, dict):
        if "raw" in payload:
            return [
                {
                    "result_type": result_type,
                    "source_identifier": payload.get("frame_name")
                    or payload.get("joint_name")
                    or payload.get("story_name"),
                    "values": payload.get("raw"),
                    "units": payload.get("units"),
                }
            ]
        return [_normalize_entry(result_type, payload)]
    return []


def _normalize_entry(result_type: str, item: Any) -> dict[str, Any]:
    if isinstance(item, dict):
        identifier = (
            item.get("id")
            or item.get("frame_name")
            or item.get("member_name")
            or item.get("joint_name")
            or item.get("point_name")
            or item.get("story_name")
        )
        values = item.get("values", item.get("raw", item))
        if isinstance(values, dict) and "raw" in values:
            values = values["raw"]
        return {
            "result_type": result_type,
            "source_identifier": identifier,
            "values": values,
            "units": item.get("units"),
            "load_case": item.get("load_case") or item.get("case_name"),
            "load_combination": item.get("load_combination"),
            "axial_force": item.get("axial_force"),
            "shear_v2": item.get("shear_v2"),
            "shear_v3": item.get("shear_v3"),
            "moment_m2": item.get("moment_m2"),
            "moment_m3": item.get("moment_m3"),
            "station": item.get("station"),
            "step_type": item.get("step_type"),
            "step_number": item.get("step_number"),
            "source_units": item.get("source_units"),
        }
    return {"result_type": result_type, "values": item}
