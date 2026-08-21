"""Deterministic validation for generated CAD drawings."""

from __future__ import annotations

from typing import Any

from app.domain.models.cad import CadValidationStatus, SUPPORTED_CAD_DRAWING_TYPES
from app.domain.models.pem import ProjectEngineeringModel


def validate_cad_drawing(
    *,
    pem: ProjectEngineeringModel,
    pem_version: int,
    drawing_type: str,
    layer_summary: dict[str, Any],
    drawing_metadata: dict[str, Any],
    entity_count: int,
) -> tuple[CadValidationStatus, dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    missing: list[str] = []
    normalized = drawing_type.upper()

    if normalized not in SUPPORTED_CAD_DRAWING_TYPES:
        missing.append(f"Drawing type '{normalized}' is not supported")

    member_count = len(pem.structural_model.members.members)
    if member_count == 0 and normalized not in {"SLAB_PLAN", "GRID_PLAN"}:
        missing.append("Structural model has no members to draw")

    if entity_count <= 0:
        missing.append("Drawing contains no geometry entities")

    if not layer_summary:
        missing.append("Drawing layer summary is empty")

    if drawing_metadata.get("pem_version") != pem_version:
        findings.append(
            {
                "code": "PEM_VERSION_MISMATCH",
                "message": "Drawing metadata PEM version does not match source PEM",
                "severity": "ERROR",
            }
        )

    capability_status = str(drawing_metadata.get("capability_status", "COMPLETE"))
    metadata_missing = drawing_metadata.get("missing_data") or []
    if isinstance(metadata_missing, list):
        missing.extend(str(item) for item in metadata_missing)

    if normalized in {"FRAMING_PLAN", "BEAM_LAYOUT", "BEAM_PLAN"}:
        primary_count = layer_summary.get("MEMBERS", 0) + layer_summary.get("BEAMS", 0)
        if primary_count == 0:
            missing.append("Beam/framing plan requires beam member geometry")

    if normalized in {"COLUMN_PLAN", "COLUMN_LAYOUT"}:
        if layer_summary.get("COLUMNS", 0) == 0:
            missing.append("Column plan requires column members with plan locations")

    if normalized == "SLAB_PLAN":
        if layer_summary.get("SLABS", 0) == 0:
            missing.append("Slab plan requires slab boundary geometry in the engineering model")

    if findings:
        status = CadValidationStatus.INVALID
    elif capability_status == "INCOMPLETE" or (missing and entity_count <= 0):
        status = CadValidationStatus.INCOMPLETE
    elif missing or capability_status == "PARTIAL":
        status = CadValidationStatus.REQUIRES_ENGINEER_REVIEW
    else:
        status = CadValidationStatus.VALIDATED

    return status, {
        "validation_status": status.value,
        "findings": findings,
        "missing_requirements": missing,
        "entity_count": entity_count,
        "drawing_type": drawing_type,
        "capability_status": capability_status,
    }
