"""Deterministic validation for normalized engineering results."""

from __future__ import annotations

import math
from typing import Any

from app.domain.models.engineering_results import (
    NormalizedEngineeringResults,
    ResultValidationStatus,
)
from app.domain.models.pem import ProjectEngineeringModel


def validate_engineering_results(
    *,
    normalized: NormalizedEngineeringResults,
    pem: ProjectEngineeringModel,
    analysis_type: str,
    software: str,
    software_version: str,
    provenance: dict[str, Any],
) -> tuple[ResultValidationStatus, dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    missing: list[str] = []

    if provenance.get("execution_mode") == "mock":
        findings.append(
            {
                "code": "MOCK_EXECUTION",
                "message": "Mock execution results cannot be validated as engineering outputs",
                "severity": "ERROR",
            }
        )
        return ResultValidationStatus.INVALID, _summary(findings, missing, normalized)

    if not software or not software_version:
        missing.append("Solver identity is required")
    if not provenance.get("source_software"):
        missing.append("Result provenance must identify source software")

    member_ids = {member.id for member in pem.structural_model.members.members}
    point_ids = {point.id for point in pem.structural_model.geometry.points}
    load_cases = {item.id for item in pem.structural_model.load_cases}

    present_types = normalized.present_types()
    if not present_types:
        missing.append("No supported engineering result types were normalized")

    for result_type in present_types:
        entries = getattr(normalized, result_type)
        for index, entry in enumerate(entries):
            _validate_entry_numbers(result_type, index, entry, findings)
            _validate_entry_references(
                result_type,
                entry,
                member_ids=member_ids,
                point_ids=point_ids,
                load_cases=load_cases,
                findings=findings,
            )

    if analysis_type.upper() in {"MODAL", "SEISMIC"} and not normalized.modal_periods:
        missing.append("Modal analysis requires modal period results")

    if findings:
        status = ResultValidationStatus.INVALID
    elif missing and present_types:
        status = ResultValidationStatus.INCOMPLETE
    elif missing:
        status = ResultValidationStatus.INVALID
    elif any(item["severity"] == "WARNING" for item in findings):
        status = ResultValidationStatus.PARTIALLY_VALIDATED
    else:
        status = ResultValidationStatus.VALIDATED

    return status, _summary(findings, missing, normalized, status=status)


def _validate_entry_numbers(result_type: str, index: int, entry: dict[str, Any], findings: list) -> None:
    values = entry.get("values")
    if values is None:
        findings.append(
            {
                "code": "MISSING_VALUES",
                "message": f"{result_type}[{index}] has no numeric values",
                "severity": "ERROR",
            }
        )
        return

    numbers = _flatten_numbers(values)
    if not numbers:
        findings.append(
            {
                "code": "EMPTY_VALUES",
                "message": f"{result_type}[{index}] contains no numeric values",
                "severity": "ERROR",
            }
        )
        return

    for value in numbers:
        if math.isnan(value) or math.isinf(value):
            findings.append(
                {
                    "code": "NON_FINITE_VALUE",
                    "message": f"{result_type}[{index}] contains non-finite numeric values",
                    "severity": "ERROR",
                }
            )
            break


def _validate_entry_references(
    result_type: str,
    entry: dict[str, Any],
    *,
    member_ids: set[str],
    point_ids: set[str],
    load_cases: set[str],
    findings: list,
) -> None:
    source_id = entry.get("source_identifier")
    if source_id and result_type.startswith("frame") and source_id not in member_ids:
        findings.append(
            {
                "code": "UNKNOWN_MEMBER",
                "message": f"Result references unknown member '{source_id}'",
                "severity": "WARNING",
            }
        )
    if source_id and result_type.startswith("joint") and source_id not in point_ids:
        findings.append(
            {
                "code": "UNKNOWN_JOINT",
                "message": f"Result references unknown joint '{source_id}'",
                "severity": "WARNING",
            }
        )
    load_case = entry.get("load_case")
    if load_case and load_case not in load_cases:
        findings.append(
            {
                "code": "UNKNOWN_LOAD_CASE",
                "message": f"Result references unknown load case '{load_case}'",
                "severity": "WARNING",
            }
        )


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


def _summary(
    findings: list[dict[str, Any]],
    missing: list[str],
    normalized: NormalizedEngineeringResults,
    *,
    status: ResultValidationStatus | None = None,
) -> dict[str, Any]:
    return {
        "validation_status": status.value if status else None,
        "findings": findings,
        "missing_requirements": missing,
        "result_types_present": normalized.present_types(),
        "result_entry_count": sum(len(getattr(normalized, key)) for key in normalized.present_types()),
    }
