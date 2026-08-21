"""Deterministic design model readiness assessment."""

from __future__ import annotations

from uuid import UUID

from app.application.analysis_model_readiness import build_model_summary
from app.application.code_engine_service import CodeEngineService
from app.application.engineering_result_readiness import analysis_run_has_validated_results
from app.domain.models.analysis import AnalysisRun
from app.domain.models.design import DesignReadinessReport, DesignStatus
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.validation import ValidationStatus
from app.domain.pem_validation import validate_structural_model


def assess_design_readiness(
    *,
    project_id: UUID,
    pem: ProjectEngineeringModel,
    pem_version: int,
    pem_snapshot_id: UUID,
    code_engine: CodeEngineService,
    analysis_runs: list[AnalysisRun],
    validated_run_ids: set[UUID] | None = None,
) -> DesignReadinessReport:
    findings = validate_structural_model(pem)
    model_summary = build_model_summary(pem)
    missing: list[str] = []

    has_errors = any(f.status == ValidationStatus.ERROR for f in findings)
    if has_errors:
        missing.append("Resolve structural model validation errors")

    if model_summary["member_count"] == 0:
        missing.append("Define at least one structural member")

    if model_summary["material_count"] == 0:
        missing.append("Define material properties")

    if model_summary["section_count"] == 0:
        missing.append("Define member sections")

    code_validation = code_engine.validate_configuration(pem.code_configuration)
    code_edition = pem.code_configuration.steel_edition
    if not code_validation.is_valid:
        missing.append("Resolve code configuration conflicts")

    usable_runs = [
        run
        for run in analysis_runs
        if analysis_run_has_validated_results(run, validated_run_ids=validated_run_ids)
    ]
    matching_runs = [run for run in analysis_runs if run.pem_version == pem_version]

    validation_status = (
        ValidationStatus.ERROR.value
        if has_errors or not code_validation.is_valid
        else ValidationStatus.WARNING.value
        if missing or not usable_runs
        else ValidationStatus.PASS.value
    )

    ready_for_design = (
        not has_errors
        and code_validation.is_valid
        and model_summary["member_count"] > 0
    )

    if has_errors or model_summary["member_count"] == 0:
        readiness_status = DesignStatus.MODEL_NOT_READY.value
        summary = "Engineering model is not ready for design checks"
    elif not code_validation.is_valid:
        readiness_status = DesignStatus.REQUIRES_ENGINEER_REVIEW.value
        summary = "Code configuration requires engineer review before design"
    elif not usable_runs:
        readiness_status = DesignStatus.REQUIRES_ANALYSIS.value
        summary = "Design requires completed analysis results with engineering outputs"
    elif missing:
        readiness_status = DesignStatus.WARNING.value
        summary = "Model partially configured; additional inputs recommended before design execution"
    else:
        readiness_status = DesignStatus.PASS.value
        summary = "Model and analysis inputs are ready for design routine execution"

    return DesignReadinessReport(
        project_id=project_id,
        pem_version=pem_version,
        pem_snapshot_id=pem_snapshot_id,
        ready_for_design=ready_for_design,
        readiness_status=readiness_status,
        summary=summary,
        code_edition=code_edition,
        code_configuration_valid=code_validation.is_valid,
        model_summary=model_summary,
        validation_status=validation_status,
        findings=[finding.model_dump(mode="json") for finding in findings],
        missing_requirements=missing,
        available_analysis_runs=len(matching_runs),
        usable_analysis_runs=len(usable_runs),
    )
