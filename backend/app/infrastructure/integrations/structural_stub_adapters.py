"""Stub structural software adapters — local CSI software not available in CI."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.models.integration import (
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationResult,
    IntegrationSoftware,
)


class _StubStructuralAdapter:
    def __init__(self, software: IntegrationSoftware, version: str) -> None:
        self._software = software
        self._version = version

    @property
    def software_name(self) -> str:
        return self._software.value

    @property
    def software_version(self) -> str:
        return self._version

    def get_status(self) -> IntegrationResult:
        return IntegrationResult(
            software=self._software,
            operation=IntegrationOperation.STATUS,
            status=IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
            message=f"{self._software.value} {self._version} adapter loaded; local software not connected",
            metadata={"adapter": "stub", "version": self._version},
        )

    def import_model(self, project_id: UUID, *, source_path: str) -> IntegrationResult:
        return self._unavailable(IntegrationOperation.IMPORT_MODEL, project_id, source_path=source_path)

    def export_model(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        return self._unavailable(
            IntegrationOperation.EXPORT_MODEL,
            project_id,
            destination_path=destination_path,
        )

    def run_analysis(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult:
        return self._unavailable(IntegrationOperation.RUN_ANALYSIS, project_id, parameters=parameters)

    def extract_results(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult:
        return self._unavailable(
            IntegrationOperation.EXTRACT_RESULTS,
            project_id,
            parameters=parameters,
        )

    def supports_operation(self, operation: IntegrationOperation) -> bool:
        return operation in {
            IntegrationOperation.IMPORT_MODEL,
            IntegrationOperation.EXPORT_MODEL,
            IntegrationOperation.RUN_ANALYSIS,
            IntegrationOperation.EXTRACT_RESULTS,
            IntegrationOperation.STATUS,
        }

    def _unavailable(
        self,
        operation: IntegrationOperation,
        project_id: UUID,
        **metadata: Any,
    ) -> IntegrationResult:
        return IntegrationResult(
            software=self._software,
            operation=operation,
            status=IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
            message=(
                f"{self._software.value} {operation.value} requires local "
                f"{self._software.value} {self._version} installation"
            ),
            metadata={"project_id": str(project_id), **metadata},
        )


class EtabsStubAdapter(_StubStructuralAdapter):
    def __init__(self) -> None:
        super().__init__(IntegrationSoftware.ETABS, "23")


class Sap2000StubAdapter(_StubStructuralAdapter):
    def __init__(self) -> None:
        super().__init__(IntegrationSoftware.SAP2000, "27")


class SafeStubAdapter(_StubStructuralAdapter):
    def __init__(self) -> None:
        super().__init__(IntegrationSoftware.SAFE, "23")
