"""Stub AutoCAD adapter — local AutoCAD 2027 not available in CI."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.domain.models.integration import (
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationResult,
    IntegrationSoftware,
)


class AutocadStubAdapter:
    @property
    def software_name(self) -> str:
        return IntegrationSoftware.AUTOCAD.value

    @property
    def software_version(self) -> str:
        return "2027"

    def get_status(self) -> IntegrationResult:
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.STATUS,
            status=IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
            message="AutoCAD 2027 adapter loaded; local software not connected",
            metadata={"adapter": "stub", "version": self.software_version},
        )

    def generate_drawing(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult:
        return self._unavailable(IntegrationOperation.GENERATE_DRAWING, project_id, parameters=parameters)

    def export_dxf(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        return self._unavailable(
            IntegrationOperation.EXPORT_DXF,
            project_id,
            destination_path=destination_path,
        )

    def export_dwg(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        return self._unavailable(
            IntegrationOperation.EXPORT_DWG,
            project_id,
            destination_path=destination_path,
        )

    def supports_operation(self, operation: IntegrationOperation) -> bool:
        return operation in {
            IntegrationOperation.GENERATE_DRAWING,
            IntegrationOperation.EXPORT_DXF,
            IntegrationOperation.EXPORT_DWG,
            IntegrationOperation.STATUS,
        }

    def _unavailable(
        self,
        operation: IntegrationOperation,
        project_id: UUID,
        **metadata: Any,
    ) -> IntegrationResult:
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=operation,
            status=IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
            message=f"AutoCAD {operation.value} requires local AutoCAD 2027 installation",
            metadata={"project_id": str(project_id), **metadata},
        )
