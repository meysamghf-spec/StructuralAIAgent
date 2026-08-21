"""Deterministic optimization readiness assessment."""

from __future__ import annotations

from uuid import UUID

from app.application.analysis_model_readiness import build_model_summary
from app.application.code_engine_service import CodeEngineService
from app.application.engineering_result_readiness import analysis_run_has_validated_results
from app.domain.models.analysis import AnalysisRun
from app.domain.models.design import DesignRun, DesignStatus
from app.domain.models.optimization import OptimizationReadinessReport, OptimizationStatus
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.validation import ValidationStatus
from app.domain.pem_validation import validate_structural_model


def _analysis_outputs_usable(run: AnalysisRun) -> bool:
    return analysis_run_has_validated_results(run)


def _design_outputs_usable(run: DesignRun) -> bool:
    if run.status != DesignStatus.PASS:
        return False
    return bool(run.outputs.get("engineering_design_results_available"))


def assess_optimization_readiness(
    *,
    project_id: UUID,
    pem: ProjectEngineeringModel,
    pem_version: int,
    pem_snapshot_id: UUID,
    code_engine: CodeEngineService,
    analysis_runs: list[AnalysisRun],
    design_runs: list[DesignRun],
    validated_run_ids: set[UUID] | None = None,
) -> OptimizationReadinessReport:
    findings = validate_structural_model(pem)
    model_summary = build_model_summary(pem)
    missing: list[str] = []

    has_errors = any(f.status == ValidationStatus.ERROR for f in findings)
    if has_errors:
        missing.append("Resolve structural model validation errors")
    if model_summary["member_count"] == 0:
        missing.append("Define at least one structural member")

    code_validation = code_engine.validate_configuration(pem.code_configuration)
    if not code_validation.is_valid:
        missing.append("Resolve code configuration conflicts")

    version_analysis = [run for run in analysis_runs if run.pem_version == pem_version]
    version_design = [run for run in design_runs if run.pem_version == pem_version]
    usable_analysis = [
        run
        for run in version_analysis
        if analysis_run_has_validated_results(run, validated_run_ids=validated_run_ids)
    ]
    usable_design = [run for run in version_design if _design_outputs_usable(run)]

    validation_status = (
        ValidationStatus.ERROR.value
        if has_errors or not code_validation.is_valid
        else ValidationStatus.WARNING.value
        if missing or (not usable_analysis and not usable_design)
        else ValidationStatus.PASS.value
    )

    ready = (
        not has_errors
        and code_validation.is_valid
        and model_summary["member_count"] > 0
    )

    if has_errors or model_summary["member_count"] == 0:
        readiness_status = OptimizationStatus.MODEL_NOT_READY.value
        summary = "Engineering model is not ready for optimization"
    elif not code_validation.is_valid:
        readiness_status = OptimizationStatus.REQUIRES_ENGINEER_REVIEW.value
        summary = "Code configuration requires engineer review before optimization"
    elif not usable_analysis and not usable_design:
        readiness_status = OptimizationStatus.REQUIRES_ANALYSIS.value
        summary = "Optimization requires completed analysis or design results with engineering outputs"
    elif missing:
        readiness_status = OptimizationStatus.WARNING.value
        summary = "Model partially configured; review inputs before optimization"
    else:
        readiness_status = OptimizationStatus.PASS.value
        summary = "Model and upstream engineering runs are ready for optimization orchestration"

    return OptimizationReadinessReport(
        project_id=project_id,
        pem_version=pem_version,
        pem_snapshot_id=pem_snapshot_id,
        ready_for_optimization=ready,
        readiness_status=readiness_status,
        summary=summary,
        code_edition=pem.code_configuration.governing_building_code.edition,
        code_configuration_valid=code_validation.is_valid,
        model_summary=model_summary,
        validation_status=validation_status,
        findings=[finding.model_dump(mode="json") for finding in findings],
        missing_requirements=missing,
        available_analysis_runs=len(version_analysis),
        usable_analysis_runs=len(usable_analysis),
        available_design_runs=len(version_design),
        usable_design_runs=len(usable_design),
    )
