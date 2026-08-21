"""CAD drawing generation from validated PEM geometry."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from app.application.cad_validation import validate_cad_drawing
from app.application.exceptions import CadDrawingNotFoundError, PemNotFoundError, ProjectNotFoundError
from app.application.integration_service import IntegrationService
from app.application.project_service import PemService, ProjectService
from app.application.traceability_integration import record_model_to_drawing
from app.application.traceability_service import TraceabilityService
from app.domain.models.cad import (
    CadDrawing,
    CadDrawingRequest,
    CadDrawingStatus,
    CadOutputFormat,
    CadValidationStatus,
)
from app.domain.models.integration import IntegrationOperation, IntegrationSoftware
from app.infrastructure.cad.dxf_renderer import render_plan_dxf
from app.infrastructure.config import get_settings
from app.infrastructure.repositories.postgres_cad_drawing_repository import PostgresCadDrawingRepository


class CadGenerationService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        drawing_repository: PostgresCadDrawingRepository,
        integration_service: IntegrationService | None = None,
        traceability_service: TraceabilityService | None = None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._drawings = drawing_repository
        self._integration = integration_service
        self._traceability = traceability_service

    def get_autocad_capability(self) -> dict[str, Any]:
        if self._integration is None:
            return {
                "software": IntegrationSoftware.AUTOCAD.value,
                "availability": "REQUIRES_LOCAL_SOFTWARE",
                "message": "AutoCAD integration is not configured.",
            }
        adapter = self._integration.get_adapter(IntegrationSoftware.AUTOCAD)
        if hasattr(adapter, "detect_capability"):
            report = adapter.detect_capability()
            return report.model_dump(mode="json")
        status = adapter.get_status()
        return {
            "software": IntegrationSoftware.AUTOCAD.value,
            "availability": status.metadata.get("availability", status.status.value),
            "message": status.message,
            "metadata": status.metadata,
        }

    def generate_drawing(
        self,
        request: CadDrawingRequest,
        *,
        created_by: str | None = None,
    ) -> CadDrawing:
        pem, snapshot_id, version = self._resolve_pem(request.project_id, request.pem_version)
        drawing_type = request.drawing_type.strip().upper()
        drawing = self._drawings.create_drawing(
            request.project_id,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            drawing_type=drawing_type,
            output_format=request.output_format,
            status=CadDrawingStatus.RUNNING,
            validation_status=CadValidationStatus.INCOMPLETE,
            message="Drawing generation started",
            provenance={
                "pem_version": version,
                "drawing_type": drawing_type,
                "output_format": request.output_format.value,
            },
            created_by=created_by,
        )

        if request.output_format == CadOutputFormat.DXF:
            return self._generate_dxf(
                request.project_id,
                drawing,
                pem=pem,
                snapshot_id=snapshot_id,
                version=version,
                drawing_type=drawing_type,
                parameters=request.parameters,
            )

        return self._generate_dwg(
            request.project_id,
            drawing,
            pem=pem,
            snapshot_id=snapshot_id,
            version=version,
            drawing_type=drawing_type,
            parameters=request.parameters,
        )

    def get_drawing(self, project_id: UUID, drawing_id: UUID) -> CadDrawing:
        drawing = self._drawings.get_drawing(project_id, drawing_id)
        if drawing is None:
            raise CadDrawingNotFoundError(project_id, drawing_id)
        return drawing

    def list_drawings(self, project_id: UUID, *, limit: int = 50) -> list[CadDrawing]:
        self._ensure_project(project_id)
        return self._drawings.list_drawings(project_id, limit=limit)

    def build_validation_report(self, drawing: CadDrawing) -> dict[str, Any]:
        return {
            "drawing_id": str(drawing.id),
            "validation_status": drawing.validation_status.value,
            "status": drawing.status.value,
            "validation_summary": drawing.validation_summary,
            "layer_summary": drawing.layer_summary,
            "provenance": drawing.provenance,
        }

    def _generate_dxf(
        self,
        project_id: UUID,
        drawing: CadDrawing,
        *,
        pem,
        snapshot_id: UUID,
        version: int,
        drawing_type: str,
        parameters: dict[str, Any],
    ) -> CadDrawing:
        units = "METERS"
        if pem.unit_configuration is not None:
            units = pem.unit_configuration.length_unit
        render = render_plan_dxf(pem, drawing_type=drawing_type, units=units)
        output_dir = Path(get_settings().resolved_file_storage_root) / "cad" / str(project_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        file_path = output_dir / f"{drawing.id}.dxf"
        file_path.write_text(render.content, encoding="utf-8")

        validation_status, validation_summary = validate_cad_drawing(
            pem=pem,
            pem_version=version,
            drawing_type=drawing_type,
            layer_summary=render.layer_summary,
            drawing_metadata={**render.metadata, "pem_version": version},
            entity_count=render.entity_count,
        )
        status = CadDrawingStatus.SUCCESS
        completed = self._drawings.update_drawing(
            project_id,
            drawing.id,
            status=status,
            validation_status=validation_status,
            message="DXF drawing generated from engineering model geometry.",
            file_path=str(file_path),
            layer_summary=render.layer_summary,
            drawing_metadata={**render.metadata, "pem_version": version, **parameters},
            validation_summary=validation_summary,
            provenance={
                "source": "pem_geometry",
                "pem_version": version,
                "output_format": CadOutputFormat.DXF.value,
                "generation_method": "deterministic_dxf_renderer",
            },
            completed_at=datetime.now(UTC),
        )
        assert completed is not None
        self._record_traceability(project_id, snapshot_id, completed.id, drawing_type)
        return completed

    def _generate_dwg(
        self,
        project_id: UUID,
        drawing: CadDrawing,
        *,
        pem,
        snapshot_id: UUID,
        version: int,
        drawing_type: str,
        parameters: dict[str, Any],
    ) -> CadDrawing:
        capability = self.get_autocad_capability()
        if capability.get("availability") != "AVAILABLE":
            completed = self._drawings.update_drawing(
                project_id,
                drawing.id,
                status=CadDrawingStatus.REQUIRES_LOCAL_SOFTWARE,
                validation_status=CadValidationStatus.INCOMPLETE,
                message=capability.get(
                    "message",
                    "AutoCAD 2027 is not available on this computer.",
                ),
                drawing_metadata={"pem_version": version, **parameters},
                validation_summary={"reason": "REQUIRES_LOCAL_SOFTWARE"},
                provenance={"output_format": CadOutputFormat.DWG.value},
                completed_at=datetime.now(UTC),
            )
            assert completed is not None
            return completed

        if self._integration is None:
            raise ProjectNotFoundError(project_id)

        output_dir = Path(get_settings().resolved_file_storage_root) / "cad" / str(project_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        destination = str(output_dir / f"{drawing.id}.dwg")
        adapter = self._integration.get_adapter(IntegrationSoftware.AUTOCAD)
        result = adapter.export_dwg(project_id, destination_path=destination)
        status = CadDrawingStatus.REQUIRES_LOCAL_SOFTWARE
        validation_status = CadValidationStatus.INCOMPLETE
        if result.status.value == "SUCCESS":
            status = CadDrawingStatus.SUCCESS
            validation_status = CadValidationStatus.VALIDATED
        elif result.status.value == "NOT_IMPLEMENTED":
            status = CadDrawingStatus.REQUIRES_LOCAL_SOFTWARE

        completed = self._drawings.update_drawing(
            project_id,
            drawing.id,
            status=status,
            validation_status=validation_status,
            message=result.message,
            file_path=destination if status == CadDrawingStatus.SUCCESS else None,
            drawing_metadata={"pem_version": version, **parameters},
            validation_summary={"integration_status": result.status.value},
            provenance={
                "output_format": CadOutputFormat.DWG.value,
                "software": IntegrationSoftware.AUTOCAD.value,
                "operation": IntegrationOperation.EXPORT_DWG.value,
            },
            completed_at=datetime.now(UTC),
        )
        assert completed is not None
        if status == CadDrawingStatus.SUCCESS:
            self._record_traceability(project_id, snapshot_id, completed.id, drawing_type)
        return completed

    def _record_traceability(
        self,
        project_id: UUID,
        snapshot_id: UUID,
        drawing_id: UUID,
        drawing_type: str,
    ) -> None:
        if self._traceability is None:
            return
        record_model_to_drawing(
            self._traceability,
            project_id=project_id,
            model_id=snapshot_id,
            drawing_id=drawing_id,
            metadata={"drawing_type": drawing_type},
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
            raise PemNotFoundError(project_id)
        return pem, meta.id, meta.version

    def _ensure_project(self, project_id: UUID) -> None:
        if self._projects.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)
