"""AutoCAD 2027 integration adapter boundary."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import UUID

from app.domain.models.integration import (
    IntegrationOperation,
    IntegrationOperationStatus,
    IntegrationResult,
    IntegrationSoftware,
    SoftwareCapabilityReport,
)
from app.infrastructure.integrations.autocad_detection import detect_autocad_capability


class AutocadAdapter:
    @property
    def software_name(self) -> str:
        return IntegrationSoftware.AUTOCAD.value

    @property
    def software_version(self) -> str:
        return "2027"

    def detect_capability(self) -> SoftwareCapabilityReport:
        return detect_autocad_capability()

    def get_status(self) -> IntegrationResult:
        capability = self.detect_capability()
        status = IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE
        if capability.availability.value == "AVAILABLE":
            status = IntegrationOperationStatus.SUCCESS
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.STATUS,
            status=status,
            message=capability.message,
            metadata={
                "availability": capability.availability.value,
                "detected_version": capability.detected_version,
                "install_path": capability.install_path,
                "adapter": "autocad",
                "version": self.software_version,
            },
        )

    def generate_drawing(self, project_id: UUID, *, parameters: dict[str, Any]) -> IntegrationResult:
        capability = self.detect_capability()
        if capability.availability.value != "AVAILABLE":
            return self._requires_local(IntegrationOperation.GENERATE_DRAWING, project_id, capability.message)
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.GENERATE_DRAWING,
            status=IntegrationOperationStatus.NOT_IMPLEMENTED,
            message="AutoCAD drawing generation via COM is not configured in this environment.",
            metadata={"project_id": str(project_id), **parameters},
        )

    def export_dxf(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.EXPORT_DXF,
            status=IntegrationOperationStatus.NOT_IMPLEMENTED,
            message="Use platform DXF generation; AutoCAD is not required for DXF export.",
            metadata={"project_id": str(project_id), "destination_path": destination_path},
        )

    def export_dwg(self, project_id: UUID, *, destination_path: str) -> IntegrationResult:
        capability = self.detect_capability()
        if capability.availability.value != "AVAILABLE":
            return self._requires_local(IntegrationOperation.EXPORT_DWG, project_id, capability.message)
        path = Path(destination_path)
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import win32com.client  # type: ignore[import-untyped]

            app = win32com.client.Dispatch("AutoCAD.Application")
            doc = app.Documents.Add()
            doc.SaveAs(str(path))
            doc.Close(False)
            if path.is_file() and path.stat().st_size > 0:
                return IntegrationResult(
                    software=IntegrationSoftware.AUTOCAD,
                    operation=IntegrationOperation.EXPORT_DWG,
                    status=IntegrationOperationStatus.SUCCESS,
                    message="DWG drawing exported through AutoCAD.",
                    metadata={
                        "project_id": str(project_id),
                        "destination_path": destination_path,
                        "install_path": capability.install_path,
                    },
                )
        except ImportError:
            return IntegrationResult(
                software=IntegrationSoftware.AUTOCAD,
                operation=IntegrationOperation.EXPORT_DWG,
                status=IntegrationOperationStatus.NOT_IMPLEMENTED,
                message="AutoCAD COM automation requires pywin32 on this computer.",
                metadata={"project_id": str(project_id), "destination_path": destination_path},
            )
        except Exception as exc:  # noqa: BLE001
            return IntegrationResult(
                software=IntegrationSoftware.AUTOCAD,
                operation=IntegrationOperation.EXPORT_DWG,
                status=IntegrationOperationStatus.FAILED,
                message=f"AutoCAD DWG export failed: {exc}",
                metadata={"project_id": str(project_id), "destination_path": destination_path},
            )

        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=IntegrationOperation.EXPORT_DWG,
            status=IntegrationOperationStatus.FAILED,
            message="AutoCAD did not produce a valid DWG file.",
            metadata={"project_id": str(project_id), "destination_path": destination_path},
        )

    def supports_operation(self, operation: IntegrationOperation) -> bool:
        return operation in {
            IntegrationOperation.GENERATE_DRAWING,
            IntegrationOperation.EXPORT_DXF,
            IntegrationOperation.EXPORT_DWG,
            IntegrationOperation.STATUS,
        }

    def _requires_local(
        self,
        operation: IntegrationOperation,
        project_id: UUID,
        message: str,
    ) -> IntegrationResult:
        return IntegrationResult(
            software=IntegrationSoftware.AUTOCAD,
            operation=operation,
            status=IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE,
            message=message,
            metadata={"project_id": str(project_id)},
        )
