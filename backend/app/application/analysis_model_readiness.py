"""Deterministic analysis model readiness assessment."""

from __future__ import annotations

from uuid import UUID

from app.domain.models.analysis import AnalysisReadinessReport, AnalysisStatus
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.validation import ValidationStatus
from app.domain.pem_validation import validate_structural_model


def build_model_summary(pem: ProjectEngineeringModel) -> dict:
    structural = pem.structural_model
    return {
        "grid_count": len(structural.geometry.grids),
        "level_count": len(structural.geometry.levels),
        "point_count": len(structural.geometry.points),
        "member_count": len(structural.members.members),
        "support_count": len(structural.supports),
        "load_case_count": len(structural.load_cases),
        "load_combination_count": len(structural.load_combinations),
        "analysis_model_status": structural.analysis_model.capability_status,
        "material_count": (
            len(structural.materials.concrete)
            + len(structural.materials.steel)
            + len(structural.materials.reinforcement)
        ),
        "section_count": (
            len(structural.sections.beams)
            + len(structural.sections.columns)
            + len(structural.sections.walls)
            + len(structural.sections.slabs)
            + len(structural.sections.foundations)
        ),
    }


def assess_analysis_readiness(
    *,
    project_id: UUID,
    pem: ProjectEngineeringModel,
    pem_version: int,
    pem_snapshot_id: UUID,
) -> AnalysisReadinessReport:
    findings = validate_structural_model(pem)
    model_summary = build_model_summary(pem)
    missing: list[str] = []

    has_errors = any(f.status == ValidationStatus.ERROR for f in findings)
    if has_errors:
        missing.append("Resolve structural model validation errors")

    if model_summary["member_count"] == 0:
        missing.append("Define at least one structural member")

    if model_summary["support_count"] == 0:
        missing.append("Define support conditions")

    if model_summary["load_case_count"] == 0:
        missing.append("Define load cases")

    if model_summary["load_combination_count"] == 0:
        missing.append("Define load combinations")

    validation_status = (
        ValidationStatus.ERROR.value
        if has_errors
        else ValidationStatus.WARNING.value
        if missing
        else ValidationStatus.PASS.value
    )

    ready_for_solver = not has_errors and model_summary["member_count"] > 0

    if has_errors:
        readiness_status = AnalysisStatus.MODEL_NOT_READY.value
        summary = "Structural model failed validation and is not ready for analysis"
    elif model_summary["member_count"] == 0:
        readiness_status = AnalysisStatus.MODEL_NOT_READY.value
        summary = "Engineering model has no structural members configured"
    elif missing:
        readiness_status = AnalysisStatus.WARNING.value
        summary = "Model partially configured; additional inputs recommended before solver execution"
        ready_for_solver = True
    else:
        readiness_status = AnalysisStatus.SUCCESS.value
        summary = "Model is configured and ready for external solver execution"

    return AnalysisReadinessReport(
        project_id=project_id,
        pem_version=pem_version,
        pem_snapshot_id=pem_snapshot_id,
        ready_for_solver=ready_for_solver,
        readiness_status=readiness_status,
        summary=summary,
        model_summary=model_summary,
        validation_status=validation_status,
        findings=[finding.model_dump(mode="json") for finding in findings],
        missing_requirements=missing,
    )
