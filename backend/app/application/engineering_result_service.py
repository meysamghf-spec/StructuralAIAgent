"""Persist and validate normalized engineering results from external solvers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.engineering_result_normalization import normalize_vendor_results
from app.application.engineering_result_validation import validate_engineering_results
from app.application.exceptions import EngineeringResultNotFoundError, ProjectNotFoundError
from app.application.project_memory_service import ProjectMemoryService
from app.application.project_service import PemService, ProjectService
from app.application.traceability_integration import (
    record_analysis_to_engineering_result,
    record_external_model_to_engineering_result,
    record_integration_execution_to_engineering_result,
)
from app.application.traceability_service import TraceabilityService
from app.domain.models.engineering_results import (
    EngineeringResultIngestionRequest,
    EngineeringResultSet,
    NormalizedEngineeringResults,
    ResultValidationStatus,
)
from app.domain.models.project_memory import MemoryType
from app.infrastructure.repositories.postgres_engineering_result_repository import (
    PostgresEngineeringResultRepository,
)


class EngineeringResultService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        result_repository: PostgresEngineeringResultRepository,
        traceability_service: TraceabilityService | None = None,
        memory_service: ProjectMemoryService | None = None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._results = result_repository
        self._traceability = traceability_service
        self._memory = memory_service

    def ingest_results(
        self,
        request: EngineeringResultIngestionRequest,
        *,
        created_by: str | None = None,
    ) -> EngineeringResultSet:
        pem = self._pem.get_pem_version(request.project_id, request.pem_version)
        if pem is None:
            pem = self._pem.get_current_pem(request.project_id)
        if pem is None:
            from app.application.exceptions import PemNotFoundError

            raise PemNotFoundError(request.project_id)

        normalized = normalize_vendor_results(_unwrap_raw_results(request.raw_results))
        validation_status, validation_summary = validate_engineering_results(
            normalized=normalized,
            pem=pem,
            analysis_type=request.analysis_type,
            software=request.software,
            software_version=request.software_version,
            provenance=request.provenance,
        )
        engineering_results_available = validation_status == ResultValidationStatus.VALIDATED

        result_set = self._results.create_result_set(
            request.project_id,
            analysis_run_id=request.analysis_run_id,
            integration_execution_id=request.integration_execution_id,
            pem_snapshot_id=request.pem_snapshot_id,
            pem_version=request.pem_version,
            software=request.software,
            software_version=request.software_version,
            analysis_type=request.analysis_type,
            validation_status=validation_status,
            engineering_results_available=engineering_results_available,
            result_types=normalized.present_types(),
            results=normalized.model_dump(mode="json"),
            provenance=request.provenance,
            validation_summary=validation_summary,
            metadata=request.metadata,
            created_by=created_by,
        )

        self._record_traceability(request, result_set)
        self._record_memory(request.project_id, result_set, created_by)
        return result_set

    def get_result_set(self, project_id: UUID, result_set_id: UUID) -> EngineeringResultSet:
        result = self._results.get_result_set(project_id, result_set_id)
        if result is None:
            raise EngineeringResultNotFoundError(project_id, result_set_id)
        return result

    def list_result_sets(
        self,
        project_id: UUID,
        *,
        analysis_run_id: UUID | None = None,
        limit: int = 50,
    ) -> list[EngineeringResultSet]:
        self._ensure_project(project_id)
        return self._results.list_result_sets(
            project_id,
            analysis_run_id=analysis_run_id,
            limit=limit,
        )

    def analysis_has_validated_results(self, project_id: UUID, analysis_run_id: UUID) -> bool:
        return self._results.get_validated_result_for_analysis(project_id, analysis_run_id) is not None

    def get_validated_result_for_analysis(
        self,
        project_id: UUID,
        analysis_run_id: UUID,
    ) -> EngineeringResultSet | None:
        return self._results.get_validated_result_for_analysis(project_id, analysis_run_id)

    def build_validation_report(self, result_set: EngineeringResultSet) -> dict[str, Any]:
        return {
            "result_set_id": str(result_set.id),
            "validation_status": result_set.validation_status.value,
            "engineering_results_available": result_set.engineering_results_available,
            "result_types": result_set.result_types,
            "validation_summary": result_set.validation_summary,
            "provenance": result_set.provenance,
            "extraction_summary": result_set.metadata.get("extraction_summary"),
            "extraction_status": result_set.metadata.get("extraction_status"),
        }

    def filter_results(
        self,
        result_set: EngineeringResultSet,
        *,
        member_id: str | None = None,
        joint_id: str | None = None,
        load_case: str | None = None,
        load_combination: str | None = None,
        result_category: str | None = None,
    ) -> dict[str, Any]:
        filtered: dict[str, Any] = {}
        for category, entries in result_set.results.items():
            if result_category and category != result_category:
                continue
            if not isinstance(entries, list):
                continue
            kept: list[dict[str, Any]] = []
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                source = entry.get("source_identifier")
                if member_id and category.startswith("frame") and source != member_id:
                    continue
                if joint_id and category.startswith("joint") and source != joint_id:
                    continue
                if load_case and entry.get("load_case") != load_case:
                    continue
                if load_combination and entry.get("load_combination") != load_combination:
                    continue
                kept.append(entry)
            if kept:
                filtered[category] = kept
        return filtered

    def _record_traceability(
        self,
        request: EngineeringResultIngestionRequest,
        result_set: EngineeringResultSet,
    ) -> None:
        if self._traceability is None:
            return
        if request.analysis_run_id is not None:
            record_analysis_to_engineering_result(
                self._traceability,
                project_id=request.project_id,
                analysis_id=request.analysis_run_id,
                result_id=result_set.id,
                metadata={
                    "validation_status": result_set.validation_status.value,
                    "software": result_set.software,
                },
            )
        if request.integration_execution_id is not None:
            record_integration_execution_to_engineering_result(
                self._traceability,
                project_id=request.project_id,
                execution_id=request.integration_execution_id,
                result_id=result_set.id,
                metadata={"validation_status": result_set.validation_status.value},
            )
        external_model_id = request.provenance.get("external_model_identity")
        if external_model_id:
            record_external_model_to_engineering_result(
                self._traceability,
                project_id=request.project_id,
                external_model_id=UUID(str(external_model_id)),
                result_id=result_set.id,
                metadata={"software": result_set.software},
            )

    def _record_memory(
        self,
        project_id: UUID,
        result_set: EngineeringResultSet,
        created_by: str | None,
    ) -> None:
        if self._memory is None:
            return
        memory_type = (
            MemoryType.EXTRACTED_INFORMATION
            if result_set.validation_status != ResultValidationStatus.VALIDATED
            else MemoryType.EXTRACTED_INFORMATION
        )
        self._memory.create_memory(
            project_id,
            memory_type,
            content=(
                f"Engineering results from {result_set.software} {result_set.software_version} "
                f"for analysis '{result_set.analysis_type}': {result_set.validation_status.value}"
            ),
            source_type="engineering_result_set",
            source_id=result_set.id,
            metadata={
                "validation_status": result_set.validation_status.value,
                "engineering_results_available": result_set.engineering_results_available,
                "software": result_set.software,
                "analysis_run_id": str(result_set.analysis_run_id) if result_set.analysis_run_id else None,
                "integration_execution_id": str(result_set.integration_execution_id)
                if result_set.integration_execution_id
                else None,
            },
            created_by=created_by,
        )

    def _ensure_project(self, project_id: UUID) -> None:
        if self._projects.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)


def _unwrap_raw_results(raw_results: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(raw_results, dict):
        return {"raw": raw_results}
    nested = raw_results.get("results")
    if isinstance(nested, dict):
        payload = dict(nested)
        for key in (
            "execution_mode",
            "external_model_identity",
            "extraction_summary",
            "target_units",
        ):
            if key in raw_results:
                payload[key] = raw_results[key]
        provenance = raw_results.get("provenance")
        if isinstance(provenance, dict):
            if "execution_mode" in provenance and "execution_mode" not in payload:
                payload["execution_mode"] = provenance["execution_mode"]
            if "external_model_identity" in provenance and "external_model_identity" not in payload:
                payload["external_model_identity"] = provenance["external_model_identity"]
        return payload
    return raw_results
