"""Orchestrate external solver workflows with PEM export/import and persistence."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any
from uuid import UUID

from app.application.exceptions import IntegrationAdapterNotFoundError, ProjectNotFoundError
from app.application.external_model_conversion import validate_imported_results
from app.application.engineering_result_service import EngineeringResultService
from app.application.integration_service import IntegrationService
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.traceability_integration import (
    record_external_model_to_analysis,
    record_model_to_external_model,
)
from app.application.traceability_service import TraceabilityService
from app.domain.models.engineering_results import EngineeringResultIngestionRequest
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.integration import (
    IntegrationExecution,
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)
from app.domain.models.project_memory import MemoryType
from app.infrastructure.repositories.postgres_integration_execution_repository import (
    PostgresIntegrationExecutionRepository,
)


SOLVER_SOFTWARE = {
    IntegrationSoftware.ETABS,
    IntegrationSoftware.SAP2000,
    IntegrationSoftware.SAFE,
}


class StructuralSolverIntegrationService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        integration_service: IntegrationService,
        execution_repository: PostgresIntegrationExecutionRepository,
        traceability_service: TraceabilityService | None = None,
        memory_service: ProjectMemoryService | None = None,
        engineering_result_service: EngineeringResultService | None = None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._integration = integration_service
        self._executions = execution_repository
        self._traceability = traceability_service
        self._memory = memory_service
        self._engineering_results = engineering_result_service

    def list_capabilities(self) -> list[SoftwareCapabilityReport]:
        reports: list[SoftwareCapabilityReport] = []
        for software in SOLVER_SOFTWARE:
            reports.append(self.get_capability(software))
        return reports

    def get_capability(self, software: IntegrationSoftware) -> SoftwareCapabilityReport:
        adapter = self._integration.get_adapter(software)
        if hasattr(adapter, "detect_capability"):
            return adapter.detect_capability()
        status = adapter.get_status()
        availability = SoftwareAvailabilityStatus.REQUIRES_LOCAL_SOFTWARE
        if status.metadata.get("availability"):
            availability = SoftwareAvailabilityStatus(status.metadata["availability"])
        return SoftwareCapabilityReport(
            software=software,
            expected_version=status.metadata.get("expected_version", adapter.software_version),
            detected_version=status.metadata.get("detected_version"),
            install_path=status.metadata.get("install_path"),
            availability=availability,
            message=status.message,
            metadata=status.metadata,
        )

    def list_executions(
        self,
        project_id: UUID,
        *,
        software: IntegrationSoftware | None = None,
        limit: int = 50,
    ) -> list[IntegrationExecution]:
        self._ensure_project(project_id)
        return self._executions.list_executions(project_id, software=software, limit=limit)

    def get_execution(self, project_id: UUID, execution_id: UUID) -> IntegrationExecution | None:
        self._ensure_project(project_id)
        return self._executions.get_execution(project_id, execution_id)

    def connect(self, project_id: UUID, software: IntegrationSoftware, *, created_by: str | None = None):
        return self._execute_simple(project_id, software, IntegrationOperation.CONNECT, created_by=created_by)

    def disconnect(self, project_id: UUID, software: IntegrationSoftware, *, created_by: str | None = None):
        return self._execute_simple(
            project_id, software, IntegrationOperation.DISCONNECT, created_by=created_by
        )

    def export_model(
        self,
        project_id: UUID,
        software: IntegrationSoftware,
        *,
        pem_version: int | None = None,
        created_by: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> IntegrationExecution:
        pem, snapshot_id, version = self._resolve_pem(project_id, pem_version)
        execution = self._executions.create_execution(
            project_id,
            software=software,
            operation=IntegrationOperation.EXPORT_MODEL,
            status=IntegrationOperationStatus.NOT_AVAILABLE,
            message="Export started",
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            inputs={"pem_version": version},
            created_by=created_by,
        )

        adapter = self._integration.get_adapter(software)
        with tempfile.TemporaryDirectory(prefix="pem-export-") as tmpdir:
            destination = str(Path(tmpdir) / f"{software.value.lower()}_export.json")
            if hasattr(adapter, "export_model_from_pem"):
                result = adapter.export_model_from_pem(
                    project_id,
                    pem=pem,
                    pem_snapshot_id=snapshot_id,
                    pem_version=version,
                    destination_path=destination,
                    foundation_spec=(parameters or {}).get("foundation_spec"),
                )
            else:
                result = self._integration.execute(
                    self._integration.build_request(
                        project_id,
                        software,
                        IntegrationOperation.EXPORT_MODEL,
                        {"destination_path": destination},
                    )
                )

        completed = self._executions.update_execution(
            project_id,
            execution.id,
            status=result.status,
            message=result.message,
            outputs={"integration_result": result.model_dump(mode="json")},
            metadata=result.metadata,
        )
        assert completed is not None
        self._record_memory(project_id, completed, created_by)
        return completed

    def record_unavailable_analysis(
        self,
        project_id: UUID,
        software: IntegrationSoftware,
        *,
        analysis_type: str,
        pem_version: int | None = None,
        analysis_run_id: UUID | None = None,
        parameters: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> IntegrationExecution:
        """Persist that a named solver was requested and not executed."""
        _pem, snapshot_id, version = self._resolve_pem(project_id, pem_version)
        capability = self.get_capability(software)
        return self._executions.create_execution(
            project_id,
            software=software,
            operation=IntegrationOperation.RUN_ANALYSIS,
            status=IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
            message=capability.message,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            analysis_run_id=analysis_run_id,
            inputs={
                "analysis_type": analysis_type,
                "parameters": parameters or {},
                "engineering_results_available": False,
            },
            outputs={
                "engineering_results_available": False,
                "solver": software.value,
                "solver_status": capability.availability.value,
                "executed": False,
            },
            metadata={"availability": capability.availability.value},
            created_by=created_by,
        )

    def run_solver_analysis(
        self,
        project_id: UUID,
        software: IntegrationSoftware,
        *,
        analysis_type: str,
        pem_version: int | None = None,
        analysis_run_id: UUID | None = None,
        parameters: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        pem, snapshot_id, version = self._resolve_pem(project_id, pem_version)
        capability = self.get_capability(software)
        if capability.availability != SoftwareAvailabilityStatus.AVAILABLE:
            recorded = self.record_unavailable_analysis(
                project_id,
                software,
                analysis_type=analysis_type,
                pem_version=version,
                analysis_run_id=analysis_run_id,
                parameters=parameters,
                created_by=created_by,
            )
            unavailable_status = {
                SoftwareAvailabilityStatus.NOT_INSTALLED: IntegrationOperationStatus.NOT_INSTALLED,
                SoftwareAvailabilityStatus.VERSION_MISMATCH: IntegrationOperationStatus.VERSION_MISMATCH,
                SoftwareAvailabilityStatus.NOT_ACCESSIBLE: IntegrationOperationStatus.NOT_ACCESSIBLE,
            }.get(capability.availability, IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE)
            failure_class = (
                "LICENSING_FAILURE"
                if unavailable_status == IntegrationOperationStatus.NOT_ACCESSIBLE
                and "license" in capability.message.lower()
                else "APPLICATION_UNAVAILABLE"
            )
            return {
                "status": unavailable_status.value,
                "capability_status": capability.availability.value,
                "failure_class": failure_class,
                "message": capability.message,
                "engineering_results_available": False,
                "analysis_executed": False,
                "integration_execution_id": str(recorded.id),
                "solver": software.value,
                "solver_status": capability.availability.value,
                "software_version": capability.detected_version,
            }

        export_execution = self.export_model(
            project_id,
            software,
            pem_version=version,
            created_by=created_by,
            parameters=parameters,
        )
        export_meta = export_execution.metadata if isinstance(export_execution.metadata, dict) else {}
        export_outputs = export_execution.outputs if isinstance(export_execution.outputs, dict) else {}
        integration_result = (export_outputs.get("integration_result") or {}) if isinstance(export_outputs, dict) else {}
        if isinstance(integration_result, dict):
            export_meta = {**export_meta, **(integration_result.get("metadata") or {})}
        vendor_status = export_meta.get("vendor_export_status")
        if (
            export_execution.status != IntegrationOperationStatus.SUCCESS
            or vendor_status != "VENDOR_MODEL_BUILT"
        ):
            return {
                "status": export_execution.status.value,
                "capability_status": export_execution.status.value,
                "failure_class": export_meta.get("failure_class") or "MODEL_BUILD_FAILURE",
                "message": export_execution.message,
                "engineering_results_available": False,
                "analysis_executed": False,
                "integration_execution_id": str(export_execution.id),
                "solver": software.value,
                "vendor_export_status": vendor_status,
                "software_version": export_meta.get("software_version"),
            }
        external_model_identity = export_execution.metadata.get("external_model_identity")
        if external_model_identity is None:
            outputs = export_execution.outputs.get("integration_result", {})
            external_model_identity = outputs.get("metadata", {}).get("external_model_identity")

        run_execution = self._executions.create_execution(
            project_id,
            software=software,
            operation=IntegrationOperation.RUN_ANALYSIS,
            status=IntegrationOperationStatus.NOT_AVAILABLE,
            message="External analysis started",
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            analysis_run_id=analysis_run_id,
            inputs={
                "analysis_type": analysis_type,
                "parameters": parameters or {},
                "external_model_identity": external_model_identity,
            },
            created_by=created_by,
        )
        run_result = self._integration.execute(
            self._integration.build_request(
                project_id,
                software,
                IntegrationOperation.RUN_ANALYSIS,
                {"analysis_type": analysis_type, **(parameters or {})},
            )
        )
        run_completed = self._executions.update_execution(
            project_id,
            run_execution.id,
            status=run_result.status,
            message=run_result.message,
            outputs={"integration_result": run_result.model_dump(mode="json")},
            metadata=run_result.metadata,
            analysis_run_id=analysis_run_id,
        )
        assert run_completed is not None

        if run_result.status != IntegrationOperationStatus.SUCCESS:
            return {
                "status": run_result.status.value,
                "capability_status": run_result.status.value,
                "failure_class": run_result.metadata.get("failure_class") or "ANALYSIS_FAILURE",
                "message": run_result.message,
                "engineering_results_available": False,
                "analysis_executed": False,
                "integration_execution_id": str(run_completed.id),
                "solver": software.value,
            }

        extract_execution = self._executions.create_execution(
            project_id,
            software=software,
            operation=IntegrationOperation.EXTRACT_RESULTS,
            status=IntegrationOperationStatus.NOT_AVAILABLE,
            message="Result extraction started",
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            analysis_run_id=analysis_run_id,
            inputs={
                "pem_snapshot_id": str(snapshot_id),
                "pem_version": version,
                "analysis_run_id": str(analysis_run_id) if analysis_run_id else None,
                "external_model_identity": external_model_identity,
            },
            created_by=created_by,
        )
        extract_result = self._integration.execute(
            self._integration.build_request(
                project_id,
                software,
                IntegrationOperation.EXTRACT_RESULTS,
                self._build_extract_parameters(
                    pem=pem,
                    snapshot_id=snapshot_id,
                    version=version,
                    analysis_run_id=analysis_run_id,
                    external_model_identity=external_model_identity,
                    parameters=parameters,
                ),
            )
        )
        extract_completed = self._executions.update_execution(
            project_id,
            extract_execution.id,
            status=extract_result.status,
            message=extract_result.message,
            outputs={"integration_result": extract_result.model_dump(mode="json")},
            metadata=extract_result.metadata,
            analysis_run_id=analysis_run_id,
        )
        assert extract_completed is not None

        parsed = extract_result.metadata.get("parsed_results")
        engineering_results_available = False
        result_set_id = None
        validation_status = None

        if parsed is not None and self._engineering_results is not None:
            provenance = {
                "source_software": software.value,
                "integration_execution_id": str(extract_completed.id),
                "external_model_identity": external_model_identity,
                "execution_mode": extract_result.metadata.get("execution_mode", "vendor"),
            }
            raw_for_ingest = parsed.get("results", parsed) if isinstance(parsed, dict) else parsed
            if isinstance(raw_for_ingest, dict):
                raw_for_ingest = dict(raw_for_ingest)
                raw_for_ingest.setdefault("execution_mode", "vendor")
                if external_model_identity is not None:
                    raw_for_ingest.setdefault("external_model_identity", external_model_identity)
            result_set = self._engineering_results.ingest_results(
                EngineeringResultIngestionRequest(
                    project_id=project_id,
                    analysis_run_id=analysis_run_id,
                    integration_execution_id=extract_completed.id,
                    pem_snapshot_id=snapshot_id,
                    pem_version=version,
                    software=software.value,
                    software_version=capability.detected_version or capability.expected_version,
                    analysis_type=analysis_type,
                    raw_results=raw_for_ingest if isinstance(raw_for_ingest, dict) else {"raw": raw_for_ingest},
                    provenance=provenance,
                    metadata={
                        "export_execution_id": str(export_execution.id),
                        "extraction_status": extract_result.metadata.get("extraction_status"),
                        "extraction_summary": extract_result.metadata.get("extraction_summary"),
                    },
                ),
                created_by=created_by,
            )
            engineering_results_available = result_set.engineering_results_available
            result_set_id = str(result_set.id)
            validation_status = result_set.validation_status.value
        elif parsed is not None:
            from app.domain.models.integration import ExternalAnalysisResults

            valid, _ = validate_imported_results(ExternalAnalysisResults.model_validate(parsed))
            engineering_results_available = (
                valid and extract_result.status == IntegrationOperationStatus.SUCCESS
            )

        if analysis_run_id is not None and external_model_identity is not None:
            self._record_external_traceability(
                project_id,
                snapshot_id,
                UUID(str(external_model_identity)),
                analysis_run_id,
                software,
            )

        self._record_memory(project_id, extract_completed, created_by)

        extracted = (
            extract_result.status == IntegrationOperationStatus.SUCCESS and engineering_results_available
        )
        return {
            "status": extract_result.status.value if extracted else IntegrationOperationStatus.FAILED.value,
            "capability_status": extract_result.status.value,
            "failure_class": None if extracted else (extract_result.metadata.get("failure_class") or "EXTRACTION_FAILURE"),
            "message": extract_result.message,
            "engineering_results_available": engineering_results_available,
            "analysis_executed": True,
            "integration_execution_id": str(extract_completed.id),
            "result_types_present": extract_result.metadata.get("result_types_present", []),
            "parsed_results": parsed,
            "software": software.value,
            "software_version": capability.detected_version or capability.expected_version,
            "result_set_id": result_set_id,
            "validation_status": validation_status,
            "extraction_status": extract_result.metadata.get("extraction_status"),
            "extraction_summary": extract_result.metadata.get("extraction_summary"),
            "external_model_identity": external_model_identity,
        }

    def extract_solver_results(
        self,
        project_id: UUID,
        software: IntegrationSoftware,
        *,
        pem_version: int | None = None,
        analysis_run_id: UUID | None = None,
        external_model_identity: str | None = None,
        parameters: dict[str, Any] | None = None,
        created_by: str | None = None,
    ) -> dict[str, Any]:
        pem, snapshot_id, version = self._resolve_pem(project_id, pem_version)
        capability = self.get_capability(software)
        if capability.availability != SoftwareAvailabilityStatus.AVAILABLE:
            return {
                "status": IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE.value,
                "extraction_status": "NOT_CONNECTED",
                "message": capability.message,
                "engineering_results_available": False,
            }

        extract_execution = self._executions.create_execution(
            project_id,
            software=software,
            operation=IntegrationOperation.EXTRACT_RESULTS,
            status=IntegrationOperationStatus.NOT_AVAILABLE,
            message="Result extraction started",
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            analysis_run_id=analysis_run_id,
            inputs={
                "pem_snapshot_id": str(snapshot_id),
                "pem_version": version,
                "analysis_run_id": str(analysis_run_id) if analysis_run_id else None,
                "external_model_identity": external_model_identity,
            },
            created_by=created_by,
        )
        extract_result = self._integration.execute(
            self._integration.build_request(
                project_id,
                software,
                IntegrationOperation.EXTRACT_RESULTS,
                self._build_extract_parameters(
                    pem=pem,
                    snapshot_id=snapshot_id,
                    version=version,
                    analysis_run_id=analysis_run_id,
                    external_model_identity=external_model_identity,
                    parameters=parameters,
                ),
            )
        )
        extract_completed = self._executions.update_execution(
            project_id,
            extract_execution.id,
            status=extract_result.status,
            message=extract_result.message,
            outputs={"integration_result": extract_result.model_dump(mode="json")},
            metadata=extract_result.metadata,
            analysis_run_id=analysis_run_id,
        )
        assert extract_completed is not None

        parsed = extract_result.metadata.get("parsed_results")
        engineering_results_available = False
        result_set_id = None
        validation_status = None

        if parsed is not None and self._engineering_results is not None:
            raw_for_ingest = parsed.get("results", parsed) if isinstance(parsed, dict) else parsed
            if isinstance(raw_for_ingest, dict):
                raw_for_ingest = dict(raw_for_ingest)
                raw_for_ingest.setdefault("execution_mode", "vendor")
            result_set = self._engineering_results.ingest_results(
                EngineeringResultIngestionRequest(
                    project_id=project_id,
                    analysis_run_id=analysis_run_id,
                    integration_execution_id=extract_completed.id,
                    pem_snapshot_id=snapshot_id,
                    pem_version=version,
                    software=software.value,
                    software_version=capability.detected_version or capability.expected_version,
                    analysis_type=str((parameters or {}).get("analysis_type", "STATIC")),
                    raw_results=raw_for_ingest if isinstance(raw_for_ingest, dict) else {"raw": raw_for_ingest},
                    provenance={
                        "source_software": software.value,
                        "integration_execution_id": str(extract_completed.id),
                        "external_model_identity": external_model_identity,
                        "execution_mode": "vendor",
                    },
                    metadata={
                        "extraction_status": extract_result.metadata.get("extraction_status"),
                        "extraction_summary": extract_result.metadata.get("extraction_summary"),
                    },
                ),
                created_by=created_by,
            )
            engineering_results_available = result_set.engineering_results_available
            result_set_id = str(result_set.id)
            validation_status = result_set.validation_status.value

        self._record_memory(project_id, extract_completed, created_by)

        return {
            "status": extract_result.status.value,
            "extraction_status": extract_result.metadata.get("extraction_status"),
            "extraction_summary": extract_result.metadata.get("extraction_summary"),
            "message": extract_result.message,
            "engineering_results_available": engineering_results_available,
            "integration_execution_id": str(extract_completed.id),
            "result_types_present": extract_result.metadata.get("result_types_present", []),
            "result_set_id": result_set_id,
            "validation_status": validation_status,
        }

    def _build_extract_parameters(
        self,
        *,
        pem: ProjectEngineeringModel,
        snapshot_id: UUID,
        version: int,
        analysis_run_id: UUID | None,
        external_model_identity: str | None,
        parameters: dict[str, Any] | None,
    ) -> dict[str, Any]:
        structural = pem.structural_model
        units = pem.unit_configuration
        payload: dict[str, Any] = {
            "pem_snapshot_id": str(snapshot_id),
            "pem_version": version,
            "analysis_run_id": str(analysis_run_id) if analysis_run_id else None,
            "external_model_identity": external_model_identity,
            "member_ids": [member.id for member in structural.members.members],
            "joint_ids": [point.id for point in structural.geometry.points],
            "load_case_ids": [item.id for item in structural.load_cases],
            "load_combination_ids": [item.id for item in structural.load_combinations],
            "target_force_unit": units.force_unit,
            "target_moment_unit": units.moment_unit,
            "target_length_unit": units.length_unit,
        }
        if parameters:
            payload.update(parameters)
        return payload

    def _execute_simple(
        self,
        project_id: UUID,
        software: IntegrationSoftware,
        operation: IntegrationOperation,
        *,
        created_by: str | None = None,
    ) -> IntegrationExecution:
        self._ensure_project(project_id)
        execution = self._executions.create_execution(
            project_id,
            software=software,
            operation=operation,
            status=IntegrationOperationStatus.NOT_AVAILABLE,
            message=f"{operation.value} started",
            created_by=created_by,
        )
        result = self._integration.execute(
            self._integration.build_request(project_id, software, operation, {})
        )
        completed = self._executions.update_execution(
            project_id,
            execution.id,
            status=result.status,
            message=result.message,
            outputs={"integration_result": result.model_dump(mode="json")},
            metadata=result.metadata,
        )
        assert completed is not None
        return completed

    def _record_external_traceability(
        self,
        project_id: UUID,
        pem_snapshot_id: UUID,
        external_model_id: UUID,
        analysis_run_id: UUID,
        software: IntegrationSoftware,
    ) -> None:
        if self._traceability is None:
            return
        record_model_to_external_model(
            self._traceability,
            project_id=project_id,
            model_id=pem_snapshot_id,
            external_model_id=external_model_id,
            metadata={"software": software.value},
        )
        record_external_model_to_analysis(
            self._traceability,
            project_id=project_id,
            external_model_id=external_model_id,
            analysis_id=analysis_run_id,
            metadata={"software": software.value},
        )

    def _record_memory(
        self,
        project_id: UUID,
        execution: IntegrationExecution,
        created_by: str | None,
    ) -> None:
        if self._memory is None:
            return
        if execution.status not in {
            IntegrationOperationStatus.SUCCESS,
            IntegrationOperationStatus.FAILED,
            IntegrationOperationStatus.NOT_ACCESSIBLE,
            IntegrationOperationStatus.NOT_INSTALLED,
            IntegrationOperationStatus.VERSION_MISMATCH,
            IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
        }:
            return
        self._memory.create_memory(
            project_id,
            MemoryType.EXTRACTED_INFORMATION,
            content=(
                f"{execution.software.value} {execution.operation.value}: {execution.message}"
            ),
            source_type="integration_execution",
            source_id=execution.id,
            metadata={
                "software": execution.software.value,
                "operation": execution.operation.value,
                "status": execution.status.value,
                "pem_version": execution.pem_version,
                "analysis_run_id": str(execution.analysis_run_id)
                if execution.analysis_run_id
                else None,
            },
            created_by=created_by,
        )

    def _resolve_pem(self, project_id: UUID, pem_version: int | None):
        self._ensure_project(project_id)
        if pem_version is None:
            meta = self._pem.get_current_snapshot_meta(project_id)
            pem = self._pem.get_current_pem(project_id)
        else:
            meta = self._pem.get_snapshot_meta_by_version(project_id, pem_version)
            pem = self._pem.get_pem_version(project_id, pem_version)
        if meta is None or pem is None:
            from app.application.exceptions import PemNotFoundError

            raise PemNotFoundError(project_id)
        return pem, meta.id, meta.version

    def _ensure_project(self, project_id: UUID) -> None:
        if self._projects.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)
