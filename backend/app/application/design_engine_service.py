"""Design engine — deterministic orchestration and persisted design runs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.code_engine_service import CodeEngineService
from app.application.engineering_result_readiness import analysis_run_has_validated_results
from app.application.engineering_result_service import EngineeringResultService
from app.application.design_routines import run_design_routine
from app.application.exceptions import (
    AnalysisRunNotFoundError,
    DesignRunNotFoundError,
    PemNotFoundError,
    ProjectNotFoundError,
)
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.design_model_readiness import assess_design_readiness
from app.application.traceability_integration import record_analysis_to_design, record_result_to_design
from app.application.traceability_service import TraceabilityService
from app.domain.models.analysis import AnalysisRun, AnalysisStatus
from app.domain.models.design import (
    SUPPORTED_DESIGN_TYPES,
    DesignReadinessReport,
    DesignRequest,
    DesignResult,
    DesignRun,
    DesignStatus,
)
from app.domain.models.project_memory import MemoryType
from app.domain.models.validation import ValidationStatus
from app.domain.pem_validation import validate_structural_model
from app.infrastructure.repositories.postgres_analysis_repository import PostgresAnalysisRepository
from app.infrastructure.repositories.postgres_design_repository import PostgresDesignRepository


def _analysis_outputs_usable(
    run: AnalysisRun,
    *,
    validated_run_ids: set[UUID] | None = None,
) -> bool:
    return analysis_run_has_validated_results(run, validated_run_ids=validated_run_ids)


class DesignEngineService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        design_repository: PostgresDesignRepository,
        analysis_repository: PostgresAnalysisRepository,
        code_engine_service: CodeEngineService,
        traceability_service: TraceabilityService | None = None,
        memory_service: ProjectMemoryService | None = None,
        engineering_result_service: EngineeringResultService | None = None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._runs = design_repository
        self._analysis = analysis_repository
        self._code_engine = code_engine_service
        self._traceability = traceability_service
        self._memory = memory_service
        self._engineering_results = engineering_result_service

    def get_readiness(
        self,
        project_id: UUID,
        *,
        pem_version: int | None = None,
    ) -> DesignReadinessReport:
        pem, snapshot_id, version = self._resolve_pem(project_id, pem_version)
        analysis_runs = self._analysis.list_runs(project_id, limit=100)
        validated_run_ids = self._validated_run_ids(project_id, analysis_runs)
        return assess_design_readiness(
            project_id=project_id,
            pem=pem,
            pem_version=version,
            pem_snapshot_id=snapshot_id,
            code_engine=self._code_engine,
            analysis_runs=analysis_runs,
            validated_run_ids=validated_run_ids,
        )

    def run_design(
        self,
        request: DesignRequest,
        *,
        created_by: str | None = None,
    ) -> DesignResult:
        pem, snapshot_id, pem_version = self._resolve_pem(request.project_id, request.pem_version)
        analysis_runs = self._analysis.list_runs(request.project_id, limit=100)
        validated_run_ids = self._validated_run_ids(request.project_id, analysis_runs)
        readiness = assess_design_readiness(
            project_id=request.project_id,
            pem=pem,
            pem_version=pem_version,
            pem_snapshot_id=snapshot_id,
            code_engine=self._code_engine,
            analysis_runs=analysis_runs,
            validated_run_ids=validated_run_ids,
        )

        normalized_type = request.design_type.strip().upper()
        analysis_run = self._resolve_analysis_run(
            request.project_id,
            pem_version=pem_version,
            requested_run_id=request.analysis_run_id or self._analysis_run_id_from_parameters(request),
            analysis_runs=analysis_runs,
        )

        inputs = self._build_inputs(pem, request, readiness, analysis_run)
        code_edition = pem.code_configuration.steel_edition

        run = self._runs.create_run(
            request.project_id,
            pem_snapshot_id=snapshot_id,
            pem_version=pem_version,
            analysis_run_id=analysis_run.id if analysis_run else None,
            design_type=normalized_type,
            status=DesignStatus.RUNNING,
            capability_status=DesignStatus.RUNNING.value,
            message="Design run started",
            code_edition=code_edition,
            inputs=inputs,
            model_summary=readiness.model_summary,
            validation_summary={
                "validation_status": readiness.validation_status,
                "findings": readiness.findings,
                "missing_requirements": readiness.missing_requirements,
                "code_configuration_valid": readiness.code_configuration_valid,
            },
            created_by=created_by,
        )

        status, capability_status, message, outputs = self._determine_outcome(
            normalized_type=normalized_type,
            readiness=readiness,
            pem=pem,
            analysis_run=analysis_run,
            validated_run_ids=validated_run_ids,
            parameters=request.parameters,
        )

        completed = self._runs.update_run(
            request.project_id,
            run.id,
            status=status,
            capability_status=capability_status,
            message=message,
            outputs=outputs,
            validation_summary={
                "validation_status": readiness.validation_status,
                "findings": readiness.findings,
                "missing_requirements": readiness.missing_requirements,
                "readiness_status": readiness.readiness_status,
                "code_configuration_valid": readiness.code_configuration_valid,
            },
            metadata={"requested_parameters": request.parameters},
        )
        assert completed is not None

        if analysis_run is not None:
            self._record_traceability(request.project_id, analysis_run.id, completed)
        self._record_memory(request.project_id, completed, created_by)

        return DesignResult.from_run(completed)

    def get_run(self, project_id: UUID, run_id: UUID) -> DesignRun:
        run = self._runs.get_run(project_id, run_id)
        if run is None:
            raise DesignRunNotFoundError(project_id, run_id)
        return run

    def list_runs(self, project_id: UUID, *, limit: int = 50) -> list[DesignRun]:
        self._ensure_project(project_id)
        return self._runs.list_runs(project_id, limit=limit)

    def list_available_analysis_runs(self, project_id: UUID) -> list[dict[str, Any]]:
        self._ensure_project(project_id)
        runs = self._analysis.list_runs(project_id, limit=50)
        return [
            {
                "id": str(run.id),
                "analysis_type": run.analysis_type,
                "status": run.status.value,
                "capability_status": run.capability_status,
                "pem_version": run.pem_version,
                "engineering_results_available": bool(
                    run.outputs.get("engineering_results_available")
                ),
                "created_at": run.created_at.isoformat(),
                "message": run.message,
            }
            for run in runs
        ]

    def _determine_outcome(
        self,
        *,
        normalized_type: str,
        readiness: DesignReadinessReport,
        pem,
        analysis_run: AnalysisRun | None,
        validated_run_ids: set[UUID] | None = None,
        parameters: dict[str, Any],
    ) -> tuple[DesignStatus, str, str, dict[str, Any]]:
        outputs: dict[str, Any] = {
            "routine_connected": False,
            "engineering_design_results_available": False,
            "design_type_requested": normalized_type,
            "supported_design_types": sorted(SUPPORTED_DESIGN_TYPES),
        }

        if normalized_type not in SUPPORTED_DESIGN_TYPES:
            return (
                DesignStatus.NOT_IMPLEMENTED,
                DesignStatus.NOT_IMPLEMENTED.value,
                f"Design type '{normalized_type}' is not supported by the current design engine",
                {**outputs, "reason": "UNSUPPORTED_DESIGN_TYPE"},
            )

        if readiness.readiness_status == DesignStatus.MODEL_NOT_READY.value:
            return (
                DesignStatus.MODEL_NOT_READY,
                DesignStatus.MODEL_NOT_READY.value,
                readiness.summary,
                {
                    **outputs,
                    "reason": "MODEL_NOT_READY",
                    "missing_requirements": readiness.missing_requirements,
                },
            )

        if not readiness.code_configuration_valid:
            return (
                DesignStatus.REQUIRES_ENGINEER_REVIEW,
                DesignStatus.REQUIRES_ENGINEER_REVIEW.value,
                readiness.summary,
                {**outputs, "reason": "CODE_CONFIGURATION_REVIEW"},
            )

        if analysis_run is None or not _analysis_outputs_usable(
            analysis_run,
            validated_run_ids=validated_run_ids,
        ):
            return (
                DesignStatus.REQUIRES_ANALYSIS,
                DesignStatus.REQUIRES_ANALYSIS.value,
                (
                    "Design requires completed analysis results with engineering force, stress, "
                    "or displacement outputs. Run analysis with a connected solver first."
                ),
                {
                    **outputs,
                    "reason": "REQUIRES_ANALYSIS",
                    "linked_analysis_run_id": str(analysis_run.id) if analysis_run else None,
                    "analysis_status": analysis_run.status.value if analysis_run else None,
                },
            )

        engineering_results = None
        result_set_id = None
        validation_status = None
        if analysis_run is not None and self._engineering_results is not None:
            result_set = self._engineering_results.get_validated_result_for_analysis(
                analysis_run.project_id,
                analysis_run.id,
            )
            if result_set is not None:
                engineering_results = result_set.results
                result_set_id = str(result_set.id)
                validation_status = result_set.validation_status.value

        routine = run_design_routine(
            design_type=normalized_type,
            pem=pem,
            analysis_outputs={
                **analysis_run.outputs,
                "result_set_id": result_set_id,
                "result_validation_status": validation_status,
            },
            engineering_results=engineering_results,
            code_engine=self._code_engine,
            parameters=parameters,
        )
        return (
            routine.status,
            routine.capability_status,
            routine.message,
            {
                **outputs,
                **routine.outputs,
                "result_set_id": result_set_id,
                "result_validation_status": validation_status,
            },
        )

    def _build_inputs(
        self,
        pem,
        request: DesignRequest,
        readiness: DesignReadinessReport,
        analysis_run: AnalysisRun | None,
    ) -> dict[str, Any]:
        structural = pem.structural_model
        findings = validate_structural_model(pem)
        code_validation = self._code_engine.validate_configuration(pem.code_configuration)
        memories = []
        if self._memory is not None:
            memories = [
                item.model_dump(mode="json")
                for item in self._memory.list_memories_by_type(
                    request.project_id, MemoryType.ASSUMPTION
                )[:10]
            ]

        return {
            "design_type": request.design_type.strip().upper(),
            "parameters": request.parameters,
            "pem_version": readiness.pem_version,
            "code_configuration": pem.code_configuration.model_dump(mode="json"),
            "unit_configuration": pem.unit_configuration.model_dump(mode="json"),
            "code_validation": code_validation.model_dump(mode="json"),
            "structural_model_reference": {
                "geometry": structural.geometry.model_dump(mode="json"),
                "materials": structural.materials.model_dump(mode="json"),
                "sections": structural.sections.model_dump(mode="json"),
                "members": structural.members.model_dump(mode="json"),
                "supports": [item.model_dump(mode="json") for item in structural.supports],
                "load_cases": [item.model_dump(mode="json") for item in structural.load_cases],
                "load_combinations": [
                    item.model_dump(mode="json") for item in structural.load_combinations
                ],
                "analysis_model": structural.analysis_model.model_dump(mode="json"),
                "design_parameters": structural.design_parameters.model_dump(mode="json"),
            },
            "analysis_run_reference": (
                {
                    "id": str(analysis_run.id),
                    "analysis_type": analysis_run.analysis_type,
                    "status": analysis_run.status.value,
                    "outputs": analysis_run.outputs,
                }
                if analysis_run
                else None
            ),
            "approved_assumptions": memories,
            "validation_finding_count": len(findings),
            "validation_error_count": sum(
                1 for finding in findings if finding.status == ValidationStatus.ERROR
            ),
            "readiness": readiness.model_dump(mode="json"),
        }

    def _resolve_analysis_run(
        self,
        project_id: UUID,
        *,
        pem_version: int,
        requested_run_id: UUID | None,
        analysis_runs: list[AnalysisRun],
    ) -> AnalysisRun | None:
        if requested_run_id is not None:
            run = self._analysis.get_run(project_id, requested_run_id)
            if run is None:
                raise AnalysisRunNotFoundError(project_id, requested_run_id)
            return run

        version_runs = [run for run in analysis_runs if run.pem_version == pem_version]
        if not version_runs:
            return None
        return version_runs[0]

    @staticmethod
    def _analysis_run_id_from_parameters(request: DesignRequest) -> UUID | None:
        raw = request.parameters.get("analysis_run_id")
        if raw is None:
            return None
        return UUID(str(raw))

    def _validated_run_ids(self, project_id: UUID, analysis_runs: list[AnalysisRun]) -> set[UUID]:
        if self._engineering_results is None:
            return set()
        validated: set[UUID] = set()
        for run in analysis_runs:
            if self._engineering_results.analysis_has_validated_results(project_id, run.id):
                validated.add(run.id)
        return validated

    def _record_traceability(
        self,
        project_id: UUID,
        analysis_run_id: UUID,
        run: DesignRun,
    ) -> None:
        if self._traceability is None:
            return
        record_analysis_to_design(
            self._traceability,
            project_id=project_id,
            analysis_id=analysis_run_id,
            design_id=run.id,
            metadata={
                "design_type": run.design_type,
                "status": run.status.value,
                "capability_status": run.capability_status,
            },
        )
        if self._engineering_results is not None:
            result_set = self._engineering_results.get_validated_result_for_analysis(
                project_id,
                analysis_run_id,
            )
            if result_set is not None:
                record_result_to_design(
                    self._traceability,
                    project_id=project_id,
                    result_id=result_set.id,
                    design_id=run.id,
                    metadata={"validation_status": result_set.validation_status.value},
                )

    def _record_memory(
        self,
        project_id: UUID,
        run: DesignRun,
        created_by: str | None,
    ) -> None:
        if self._memory is None:
            return
        self._memory.create_memory(
            project_id,
            MemoryType.EXTRACTED_INFORMATION,
            content=(
                f"Design run '{run.design_type}' on model v{run.pem_version}: "
                f"{run.message}"
            ),
            source_type="design_run",
            source_id=run.id,
            metadata={
                "design_type": run.design_type,
                "status": run.status.value,
                "capability_status": run.capability_status,
                "pem_version": run.pem_version,
                "analysis_run_id": str(run.analysis_run_id) if run.analysis_run_id else None,
            },
            created_by=created_by,
        )

    def _resolve_pem(
        self,
        project_id: UUID,
        pem_version: int | None,
    ) -> tuple[Any, UUID, int]:
        self._ensure_project(project_id)
        if pem_version is None:
            meta = self._pem.get_current_snapshot_meta(project_id)
            pem = self._pem.get_current_pem(project_id)
        else:
            meta = self._pem.get_snapshot_meta_by_version(project_id, pem_version)
            pem = self._pem.get_pem_version(project_id, pem_version)
        if meta is None or pem is None:
            raise PemNotFoundError(project_id)
        return pem, meta.id, meta.version

    def _ensure_project(self, project_id: UUID) -> None:
        if self._projects.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)
