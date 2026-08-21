"""Integration service — dispatches operations to structural and CAD adapters."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.exceptions import IntegrationAdapterNotFoundError, IntegrationOperationNotSupportedError
from app.domain.models.integration import (
    IntegrationOperation,
    IntegrationRequest,
    IntegrationResult,
    IntegrationSoftware,
)


class IntegrationService:
    def __init__(self, *, adapters: dict[str, object]) -> None:
        self._adapters = adapters

    def list_adapters(self) -> list[IntegrationResult]:
        return [adapter.get_status() for adapter in self._adapters.values()]

    def detect_capabilities(self) -> list:
        reports = []
        for adapter in self._adapters.values():
            if hasattr(adapter, "detect_capability"):
                reports.append(adapter.detect_capability())
            else:
                status = adapter.get_status()
                reports.append(status)
        return reports

    def get_adapter(self, software: IntegrationSoftware) -> Any:
        return self._get_adapter(software)

    @staticmethod
    def build_request(
        project_id: UUID,
        software: IntegrationSoftware,
        operation: IntegrationOperation,
        parameters: dict[str, Any],
    ) -> IntegrationRequest:
        return IntegrationRequest(
            project_id=project_id,
            software=software,
            operation=operation,
            parameters=parameters,
        )

    def execute(self, request: IntegrationRequest) -> IntegrationResult:
        adapter = self._get_adapter(request.software)
        if not adapter.supports_operation(request.operation):
            raise IntegrationOperationNotSupportedError(
                software=request.software.value,
                operation=request.operation.value,
            )

        project_id = request.project_id
        params = request.parameters

        if request.operation == IntegrationOperation.STATUS:
            return adapter.get_status()
        if request.operation == IntegrationOperation.DETECT:
            if hasattr(adapter, "detect_capability"):
                report = adapter.detect_capability()
                from app.domain.models.integration import IntegrationOperationStatus

                status = IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE
                if report.availability.value == "AVAILABLE":
                    status = IntegrationOperationStatus.SUCCESS
                elif report.availability.value == "NOT_INSTALLED":
                    status = IntegrationOperationStatus.NOT_INSTALLED
                elif report.availability.value == "VERSION_MISMATCH":
                    status = IntegrationOperationStatus.VERSION_MISMATCH
                elif report.availability.value == "NOT_ACCESSIBLE":
                    status = IntegrationOperationStatus.NOT_ACCESSIBLE
                return IntegrationResult(
                    software=request.software,
                    operation=request.operation,
                    status=status,
                    message=report.message,
                    metadata=report.model_dump(mode="json"),
                )
            return adapter.get_status()
        if request.operation == IntegrationOperation.CONNECT:
            return adapter.connect(project_id)
        if request.operation == IntegrationOperation.DISCONNECT:
            return adapter.disconnect(project_id)
        if request.operation == IntegrationOperation.IMPORT_MODEL:
            return adapter.import_model(project_id, source_path=params.get("source_path", ""))
        if request.operation == IntegrationOperation.EXPORT_MODEL:
            return adapter.export_model(
                project_id,
                destination_path=params.get("destination_path", ""),
            )
        if request.operation == IntegrationOperation.RUN_ANALYSIS:
            return adapter.run_analysis(project_id, parameters=params)
        if request.operation == IntegrationOperation.EXTRACT_RESULTS:
            return adapter.extract_results(project_id, parameters=params)
        if request.operation == IntegrationOperation.GENERATE_DRAWING:
            return adapter.generate_drawing(project_id, parameters=params)
        if request.operation == IntegrationOperation.EXPORT_DXF:
            return adapter.export_dxf(
                project_id,
                destination_path=params.get("destination_path", ""),
            )
        if request.operation == IntegrationOperation.EXPORT_DWG:
            return adapter.export_dwg(
                project_id,
                destination_path=params.get("destination_path", ""),
            )

        raise IntegrationOperationNotSupportedError(
            software=request.software.value,
            operation=request.operation.value,
        )

    def _get_adapter(self, software: IntegrationSoftware) -> Any:
        adapter = self._adapters.get(software.value)
        if adapter is None:
            raise IntegrationAdapterNotFoundError(software=software.value)
        return adapter
