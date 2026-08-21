"""Normalize CSI extraction payloads into platform unit system."""

from __future__ import annotations

from typing import Any

from app.application.unit_conversion_service import UnitConversionService
from app.domain.models.csi_extraction import CsiExtractionSummary
from app.domain.models.units import EngineeringQuantityType


def normalize_csi_raw_results(
    raw_results: dict[str, Any],
    *,
    extraction_summary: CsiExtractionSummary | None = None,
    target_force_unit: str = "kip",
    target_moment_unit: str = "kip-ft",
    target_length_unit: str = "ft",
    unit_service: UnitConversionService | None = None,
) -> dict[str, Any]:
    """Convert CSI vendor rows to platform units while preserving traceability metadata."""
    service = unit_service or UnitConversionService()
    normalized = dict(raw_results)
    source_units = (extraction_summary.source_units if extraction_summary else {}) or {
        "force": "kN",
        "moment": "kN-m",
        "length": "m",
    }

    if normalized.get("member_forces"):
        normalized["member_forces"] = [
            _normalize_frame_row(row, service, source_units, target_force_unit, target_moment_unit)
            for row in sorted(normalized["member_forces"], key=_frame_row_sort_key)
        ]

    if normalized.get("joint_displacements"):
        normalized["joint_displacements"] = [
            _normalize_joint_displacement_row(row, service, source_units, target_length_unit)
            for row in sorted(normalized["joint_displacements"], key=_joint_row_sort_key)
        ]

    if normalized.get("reactions"):
        normalized["reactions"] = [
            _normalize_reaction_row(row, service, source_units, target_force_unit, target_moment_unit)
            for row in sorted(normalized["reactions"], key=_joint_row_sort_key)
        ]

    if normalized.get("shell_results"):
        normalized["shell_results"] = sorted(
            normalized["shell_results"],
            key=lambda item: (
                str(item.get("object_name") or ""),
                str(item.get("load_case") or ""),
            ),
        )

    if extraction_summary is not None:
        normalized["extraction_summary"] = extraction_summary.model_dump(mode="json")
        extraction_summary.target_units = {
            "force": target_force_unit,
            "moment": target_moment_unit,
            "length": target_length_unit,
        }
        extraction_summary.source_units = source_units

    normalized["target_units"] = {
        "force": target_force_unit,
        "moment": target_moment_unit,
        "length": target_length_unit,
    }
    return normalized


def _normalize_frame_row(
    row: dict[str, Any],
    service: UnitConversionService,
    source_units: dict[str, str],
    target_force_unit: str,
    target_moment_unit: str,
) -> dict[str, Any]:
    item = dict(row)
    row_source = item.get("source_units") or source_units
    force_from = row_source.get("force", "kN")
    moment_from = row_source.get("moment", "kN-m")

    for key in ("axial_force", "shear_v2", "shear_v3", "torsion"):
        if isinstance(item.get(key), (int, float)):
            item[key] = service.convert(
                float(item[key]),
                from_unit=force_from,
                to_unit=target_force_unit,
                quantity_type=EngineeringQuantityType.FORCE,
            ).value

    for key in ("moment_m2", "moment_m3"):
        if isinstance(item.get(key), (int, float)):
            item[key] = service.convert(
                float(item[key]),
                from_unit=moment_from,
                to_unit=target_moment_unit,
                quantity_type=EngineeringQuantityType.MOMENT,
            ).value

    values = [
        item.get("axial_force"),
        item.get("shear_v2"),
        item.get("shear_v3"),
        item.get("torsion"),
        item.get("moment_m2"),
        item.get("moment_m3"),
    ]
    item["values"] = values
    item["units"] = {"force": target_force_unit, "moment": target_moment_unit}
    item["source_units"] = row_source
    return item


def _normalize_joint_displacement_row(
    row: dict[str, Any],
    service: UnitConversionService,
    source_units: dict[str, str],
    target_length_unit: str,
) -> dict[str, Any]:
    item = dict(row)
    row_source = item.get("source_units") or source_units
    length_from = row_source.get("length", "m")

    for key in ("displacement_ux", "displacement_uy", "displacement_uz"):
        source_key = {"displacement_ux": "U1", "displacement_uy": "U2", "displacement_uz": "U3"}[key]
        value = item.get(key, item.get(source_key))
        if isinstance(value, (int, float)):
            converted = service.convert(
                float(value),
                from_unit=length_from,
                to_unit=target_length_unit,
                quantity_type=EngineeringQuantityType.LENGTH,
            ).value
            item[key] = converted
            item[source_key] = converted

    item["values"] = [
        item.get("displacement_ux", item.get("U1")),
        item.get("displacement_uy", item.get("U2")),
        item.get("displacement_uz", item.get("U3")),
        item.get("rotation_rx", item.get("R1")),
        item.get("rotation_ry", item.get("R2")),
        item.get("rotation_rz", item.get("R3")),
    ]
    item["units"] = {"length": target_length_unit, "rotation": "rad"}
    item["source_units"] = row_source
    return item


def _normalize_reaction_row(
    row: dict[str, Any],
    service: UnitConversionService,
    source_units: dict[str, str],
    target_force_unit: str,
    target_moment_unit: str,
) -> dict[str, Any]:
    item = dict(row)
    row_source = item.get("source_units") or source_units
    force_from = row_source.get("force", "kN")
    moment_from = row_source.get("moment", "kN-m")

    for key, source_key in (
        ("force_fx", "F1"),
        ("force_fy", "F2"),
        ("force_fz", "F3"),
    ):
        value = item.get(key, item.get(source_key))
        if isinstance(value, (int, float)):
            converted = service.convert(
                float(value),
                from_unit=force_from,
                to_unit=target_force_unit,
                quantity_type=EngineeringQuantityType.FORCE,
            ).value
            item[key] = converted
            item[source_key] = converted

    for key, source_key in (
        ("moment_mx", "M1"),
        ("moment_my", "M2"),
        ("moment_mz", "M3"),
    ):
        value = item.get(key, item.get(source_key))
        if isinstance(value, (int, float)):
            converted = service.convert(
                float(value),
                from_unit=moment_from,
                to_unit=target_moment_unit,
                quantity_type=EngineeringQuantityType.MOMENT,
            ).value
            item[key] = converted
            item[source_key] = converted

    item["values"] = [
        item.get("force_fx", item.get("F1")),
        item.get("force_fy", item.get("F2")),
        item.get("force_fz", item.get("F3")),
        item.get("moment_mx", item.get("M1")),
        item.get("moment_my", item.get("M2")),
        item.get("moment_mz", item.get("M3")),
    ]
    item["units"] = {"force": target_force_unit, "moment": target_moment_unit}
    item["source_units"] = row_source
    return item


def _frame_row_sort_key(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(row.get("id") or row.get("frame_name") or ""),
        str(row.get("load_case") or row.get("load_combination") or ""),
        str(row.get("step_type") or ""),
        str(row.get("station") or ""),
    )


def _joint_row_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("joint_name") or row.get("id") or ""),
        str(row.get("load_case") or row.get("load_combination") or ""),
        str(row.get("step_type") or ""),
    )
