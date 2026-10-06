"""Analysis engine — deterministic model preparation and persisted run orchestration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.analysis_model_readiness import assess_analysis_readiness, build_model_summary
from app.application.exceptions import AnalysisRunNotFoundError, PemNotFoundError, ProjectNotFoundError
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.traceability_integration import record_model_to_analysis
from app.application.traceability_service import TraceabilityService
from app.domain.models.integration import IntegrationSoftware, SoftwareAvailabilityStatus
from app.domain.models.analysis import (
    SUPPORTED_ANALYSIS_TYPES,
    AnalysisReadinessReport,
    AnalysisRequest,
    AnalysisResult,
    AnalysisRun,
    AnalysisStatus,
)
from app.domain.models.project_memory import MemoryType
from app.domain.models.validation import ValidationStatus
from app.domain.pem_validation import validate_structural_model
from app.infrastructure.repositories.postgres_analysis_repository import PostgresAnalysisRepository


def _normalize_solver(raw: object | None) -> IntegrationSoftware | None:
    if raw is None:
        return None
    normalized = str(raw).strip().upper()
    mapping = {
        "ETABS": IntegrationSoftware.ETABS,
        "SAP2000": IntegrationSoftware.SAP2000,
        "SAFE": IntegrationSoftware.SAFE,
    }
    return mapping.get(normalized)


_INTERNAL_SOLVER_NAMES = frozenset(
    {"internal", "internal_direct_stiffness_2d", "internal_direct_stiffness_3d"}
)
_INTERNAL_ANALYSIS_TYPES = frozenset({"STATIC", "LINEAR_STATIC", "DRIFT"})


def _uses_internal_solver(pem, requested_solver: object | None) -> bool:
    if requested_solver is not None:
        return str(requested_solver).strip().lower() in _INTERNAL_SOLVER_NAMES
    configuration = pem.structural_model.analysis_model.configuration or {}
    return str(configuration.get("solver", "")).strip().lower() in _INTERNAL_SOLVER_NAMES


class AnalysisEngineService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        analysis_repository: PostgresAnalysisRepository,
        traceability_service: TraceabilityService | None = None,
        memory_service: ProjectMemoryService | None = None,
        solver_integration_service=None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._runs = analysis_repository
        self._traceability = traceability_service
        self._memory = memory_service
        self._solver_integration = solver_integration_service

    def get_readiness(self, project_id: UUID, *, pem_version: int | None = None) -> AnalysisReadinessReport:
        pem, snapshot_id, version = self._resolve_pem(project_id, pem_version)
        return assess_analysis_readiness(
            project_id=project_id,
            pem=pem,
            pem_version=version,
            pem_snapshot_id=snapshot_id,
        )

    def run_analysis(
        self,
        request: AnalysisRequest,
        *,
        created_by: str | None = None,
    ) -> AnalysisResult:
        pem, snapshot_id, pem_version = self._resolve_pem(request.project_id, request.pem_version)
        readiness = assess_analysis_readiness(
            project_id=request.project_id,
            pem=pem,
            pem_version=pem_version,
            pem_snapshot_id=snapshot_id,
        )

        normalized_type = request.analysis_type.strip().upper()
        inputs = self._build_inputs(pem, request, readiness)

        run = self._runs.create_run(
            request.project_id,
            pem_snapshot_id=snapshot_id,
            pem_version=pem_version,
            analysis_type=normalized_type,
            status=AnalysisStatus.RUNNING,
            capability_status=AnalysisStatus.RUNNING.value,
            message="Analysis run started",
            inputs=inputs,
            model_summary=readiness.model_summary,
            validation_summary={
                "validation_status": readiness.validation_status,
                "findings": readiness.findings,
                "missing_requirements": readiness.missing_requirements,
            },
            created_by=created_by,
        )

        status, capability_status, message, outputs = self._determine_outcome(
            pem=pem,
            normalized_type=normalized_type,
            readiness=readiness,
            request=request,
            pem_snapshot_id=snapshot_id,
            pem_version=pem_version,
            analysis_run_id=run.id,
            created_by=created_by,
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
            },
            metadata={"requested_parameters": request.parameters},
        )
        assert completed is not None

        self._record_traceability(request.project_id, snapshot_id, completed)
        self._record_memory(request.project_id, completed, created_by)

        return AnalysisResult.from_run(completed)

    def get_run(self, project_id: UUID, run_id: UUID) -> AnalysisRun:
        run = self._runs.get_run(project_id, run_id)
        if run is None:
            raise AnalysisRunNotFoundError(project_id, run_id)
        return run

    def list_runs(self, project_id: UUID, *, limit: int = 50) -> list[AnalysisRun]:
        self._ensure_project(project_id)
        return self._runs.list_runs(project_id, limit=limit)

    def summarize_load_combinations(self, project_id: UUID) -> dict[str, Any]:
        pem, snapshot_id, pem_version = self._resolve_pem(project_id, None)
        structural = pem.structural_model
        combinations = [
            combination.model_dump(mode="json")
            for combination in structural.load_combinations
        ]
        load_cases = [
            load_case.model_dump(mode="json") for load_case in structural.load_cases
        ]
        return {
            "project_id": str(project_id),
            "pem_snapshot_id": str(snapshot_id),
            "pem_version": pem_version,
            "load_combination_count": len(combinations),
            "load_case_count": len(load_cases),
            "load_combinations": combinations,
            "load_cases": load_cases,
            "analysis_model_status": structural.analysis_model.capability_status,
        }

    def _determine_outcome(
        self,
        *,
        pem,
        normalized_type: str,
        readiness: AnalysisReadinessReport,
        request: AnalysisRequest,
        pem_snapshot_id: UUID,
        pem_version: int,
        analysis_run_id: UUID,
        created_by: str | None,
    ) -> tuple[AnalysisStatus, str, str, dict[str, Any]]:
        outputs: dict[str, Any] = {
            "solver_connected": False,
            "solver_status": "NOT_CONNECTED",
            "analysis_type_requested": normalized_type,
            "supported_analysis_types": sorted(SUPPORTED_ANALYSIS_TYPES),
            "engineering_results_available": False,
        }

        if normalized_type not in SUPPORTED_ANALYSIS_TYPES:
            return (
                AnalysisStatus.NOT_IMPLEMENTED,
                AnalysisStatus.NOT_IMPLEMENTED.value,
                f"Analysis type '{normalized_type}' is not supported by the current analysis engine",
                {
                    **outputs,
                    "reason": "UNSUPPORTED_ANALYSIS_TYPE",
                },
            )

        if readiness.readiness_status == AnalysisStatus.MODEL_NOT_READY.value:
            return (
                AnalysisStatus.MODEL_NOT_READY,
                AnalysisStatus.MODEL_NOT_READY.value,
                readiness.summary,
                {
                    **outputs,
                    "reason": "MODEL_NOT_READY",
                    "missing_requirements": readiness.missing_requirements,
                },
            )

        requested_solver = request.parameters.get("solver") or request.parameters.get("software")
        if _uses_internal_solver(pem, requested_solver):
            return self._determine_internal_solver_outcome(
                pem=pem,
                normalized_type=normalized_type,
                readiness=readiness,
                outputs=outputs,
            )

        solver = _normalize_solver(requested_solver)
        if solver is not None:
            return self._determine_solver_outcome(
                normalized_type=normalized_type,
                readiness=readiness,
                request=request,
                solver=solver,
                pem_snapshot_id=pem_snapshot_id,
                pem_version=pem_version,
                analysis_run_id=analysis_run_id,
                outputs=outputs,
                created_by=created_by,
            )

        outputs.update(
            {
                "solver_status": "REQUIRES_EXTERNAL_SOLVER",
                "reason": "SOLVER_NOT_CONNECTED",
                "model_prepared": True,
                "prepared_model_summary": readiness.model_summary,
            }
        )

        if readiness.missing_requirements:
            return (
                AnalysisStatus.WARNING,
                AnalysisStatus.REQUIRES_SOLVER.value,
                (
                    "Model inputs were prepared, but recommended configuration items remain. "
                    "An external structural solver (ETABS, SAP2000, SAFE, or equivalent) is required "
                    "to produce engineering analysis results."
                ),
                outputs,
            )

        return (
            AnalysisStatus.REQUIRES_SOLVER,
            AnalysisStatus.REQUIRES_SOLVER.value,
            (
                "Model inputs were prepared successfully. An external structural solver "
                "(ETABS, SAP2000, SAFE, or equivalent) is required to execute analysis and "
                "return forces, displacements, or modal results."
            ),
            outputs,
        )

    def _determine_internal_solver_outcome(
        self,
        *,
        pem,
        normalized_type: str,
        readiness: AnalysisReadinessReport,
        outputs: dict[str, Any],
    ) -> tuple[AnalysisStatus, str, str, dict[str, Any]]:
        if normalized_type not in _INTERNAL_ANALYSIS_TYPES:
            outputs.update(
                {
                    "solver_status": "INTERNAL_LINEAR_STATIC_ONLY",
                    "reason": "INTERNAL_SOLVER_SCOPE",
                    "model_prepared": True,
                    "prepared_model_summary": readiness.model_summary,
                }
            )
            return (
                AnalysisStatus.NOT_IMPLEMENTED,
                AnalysisStatus.NOT_IMPLEMENTED.value,
                (
                    f"The in-repository solver supports linear-static (including gravity, "
                    f"simplified wind/ELF and elastic drift) analysis only. "
                    f"'{normalized_type}' is not implemented internally; use ETABS/SAP2000 "
                    "or treat the request as not checked."
                ),
                outputs,
            )

        from app.application.building_analysis_service import BuildingAnalysisService

        analysis = BuildingAnalysisService().analyze(pem)
        outputs.update(
            {
                "solver_connected": True,
                "solver_status": analysis.status,
                "solver": analysis.solver,
                "model_prepared": True,
                "prepared_model_summary": readiness.model_summary,
                "engineering_results_available": analysis.status == "SUCCESS",
                "engineering_results": analysis.engineering_results,
                "max_abs_displacement_m": analysis.max_abs_displacement_m,
                "reactions_kN": analysis.reactions_kN,
                "assumptions": analysis.assumptions,
                "warnings": analysis.warnings,
                "fidelity": "INTERNAL_3D_LINEAR_STATIC"
                if analysis.solver == "internal_direct_stiffness_3d"
                else "INTERNAL_2D_LINEAR_STATIC",
            }
        )
        if analysis.status == "SUCCESS":
            return (
                AnalysisStatus.SUCCESS,
                AnalysisStatus.SUCCESS.value,
                analysis.message,
                outputs,
            )
        if analysis.status == "MODEL_NOT_READY":
            return (
                AnalysisStatus.MODEL_NOT_READY,
                AnalysisStatus.MODEL_NOT_READY.value,
                analysis.message,
                outputs,
            )
        return (
            AnalysisStatus.FAILED,
            AnalysisStatus.FAILED.value,
            analysis.message,
            outputs,
        )

    def _determine_solver_outcome(
        self,
        *,
        normalized_type: str,
        readiness: AnalysisReadinessReport,
        request: AnalysisRequest,
        solver: IntegrationSoftware,
        pem_snapshot_id: UUID,
        pem_version: int,
        analysis_run_id: UUID,
        outputs: dict[str, Any],
        created_by: str | None,
    ) -> tuple[AnalysisStatus, str, str, dict[str, Any]]:
        outputs.update(
            {
                "solver": solver.value,
                "model_prepared": True,
                "prepared_model_summary": readiness.model_summary,
            }
        )

        if self._solver_integration is None:
            return (
                AnalysisStatus.REQUIRES_LOCAL_SOFTWARE,
                AnalysisStatus.REQUIRES_LOCAL_SOFTWARE.value,
                f"{solver.value} integration is not configured on this platform.",
                {
                    **outputs,
                    "reason": "SOLVER_INTEGRATION_NOT_CONFIGURED",
                },
            )

        capability = self._solver_integration.get_capability(solver)
        outputs["solver_status"] = capability.availability.value
        outputs["solver_capability"] = capability.model_dump(mode="json")

        if capability.availability != SoftwareAvailabilityStatus.AVAILABLE:
            status = AnalysisStatus.REQUIRES_LOCAL_SOFTWARE
            if capability.availability == SoftwareAvailabilityStatus.VERSION_MISMATCH:
                message = capability.message
            elif capability.availability == SoftwareAvailabilityStatus.NOT_ACCESSIBLE:
                message = (
                    f"{solver.value} could not be connected. Check that the application is "
                    "installed and accessible."
                )
            elif capability.availability == SoftwareAvailabilityStatus.NOT_INSTALLED:
                message = (
                    f"{solver.value} {capability.expected_version} is not available on this computer. "
                    f"Install/connect {solver.value} {capability.expected_version} to run analysis."
                )
            else:
                message = capability.message
            return (
                status,
                AnalysisStatus.REQUIRES_LOCAL_SOFTWARE.value,
                message,
                {
                    **outputs,
                    "reason": capability.availability.value,
                },
            )

        solver_result = self._solver_integration.run_solver_analysis(
            request.project_id,
            solver,
            analysis_type=normalized_type,
            pem_version=pem_version,
            analysis_run_id=analysis_run_id,
            parameters=request.parameters,
            created_by=created_by,
        )
        outputs.update(
            {
                "solver_connected": True,
                "solver_status": solver_result.get("status"),
                "integration_execution_id": solver_result.get("integration_execution_id"),
                "result_types_present": solver_result.get("result_types_present", []),
                "parsed_results": solver_result.get("parsed_results"),
                "software_version": solver_result.get("software_version"),
                "result_set_id": solver_result.get("result_set_id"),
                "result_validation_status": solver_result.get("validation_status"),
            }
        )

        if solver_result.get("engineering_results_available"):
            outputs["engineering_results_available"] = True
            return (
                AnalysisStatus.SUCCESS,
                AnalysisStatus.SUCCESS.value,
                solver_result.get(
                    "message",
                    f"{solver.value} analysis completed with validated engineering outputs.",
                ),
                outputs,
            )

        failure_status = str(solver_result.get("status", "FAILED")).upper()
        analysis_status = AnalysisStatus.FAILED
        capability_status = failure_status
        if failure_status in {
            AnalysisStatus.REQUIRES_LOCAL_SOFTWARE.value,
            "REQUIRES_LOCAL_SOFTWARE",
            "NOT_INSTALLED",
            "NOT_ACCESSIBLE",
            "VERSION_MISMATCH",
        }:
            analysis_status = AnalysisStatus.REQUIRES_LOCAL_SOFTWARE
            capability_status = AnalysisStatus.REQUIRES_LOCAL_SOFTWARE.value

        return (
            analysis_status,
            capability_status,
            solver_result.get("message", f"{solver.value} analysis did not produce validated results."),
            {
                **outputs,
                "reason": failure_status,
            },
        )

    def _build_inputs(
        self,
        pem,
        request: AnalysisRequest,
        readiness: AnalysisReadinessReport,
    ) -> dict[str, Any]:
        structural = pem.structural_model
        findings = validate_structural_model(pem)
        return {
            "analysis_type": request.analysis_type.strip().upper(),
            "parameters": request.parameters,
            "pem_version": readiness.pem_version,
            "code_configuration": pem.code_configuration.model_dump(mode="json"),
            "unit_configuration": pem.unit_configuration.model_dump(mode="json"),
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
            "validation_finding_count": len(findings),
            "validation_error_count": sum(
                1 for finding in findings if finding.status == ValidationStatus.ERROR
            ),
            "readiness": readiness.model_dump(mode="json"),
        }

    def _record_traceability(
        self,
        project_id: UUID,
        snapshot_id: UUID,
        run: AnalysisRun,
    ) -> None:
        if self._traceability is None:
            return
        record_model_to_analysis(
            self._traceability,
            project_id=project_id,
            model_id=snapshot_id,
            analysis_id=run.id,
            metadata={
                "analysis_type": run.analysis_type,
                "status": run.status.value,
                "capability_status": run.capability_status,
            },
        )

    def _record_memory(
        self,
        project_id: UUID,
        run: AnalysisRun,
        created_by: str | None,
    ) -> None:
        if self._memory is None:
            return
        self._memory.create_memory(
            project_id,
            MemoryType.EXTRACTED_INFORMATION,
            content=(
                f"Analysis run '{run.analysis_type}' on model v{run.pem_version}: "
                f"{run.message}"
            ),
            source_type="analysis_run",
            source_id=run.id,
            metadata={
                "analysis_type": run.analysis_type,
                "status": run.status.value,
                "capability_status": run.capability_status,
                "pem_version": run.pem_version,
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
