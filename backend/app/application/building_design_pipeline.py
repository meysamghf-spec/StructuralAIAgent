"""Persist a generated building, emit drawings, and record traceability + approval."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from app.application.building_design_assembler import AssembledBuilding, BuildingDesignAssembler
from app.application.cad_generation_service import CadGenerationService
from app.application.code_engine_service import CodeEngineService
from app.application.human_approval_service import HumanApprovalService
from app.application.pem_revision_service import PemRevisionService
from app.application.project_service import PemService, ProjectService
from app.application.sheet_generation_service import SheetGenerationService
from app.application.traceability_integration import record_model_to_drawing
from app.application.traceability_service import TraceabilityService
from app.domain.models.cad import CadDrawingRequest, CadDrawingType, CadOutputFormat
from app.domain.models.human_approval import ApprovalTargetType
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.revision import RevisionChangeType
from app.domain.models.traceability import TraceObjectType, TraceabilityRelationshipType
from app.application.exceptions import ProjectNotFoundError


BUILDING_DRAWING_TYPES = (
    CadDrawingType.FRAMING_PLAN.value,
    CadDrawingType.COLUMN_PLAN.value,
    CadDrawingType.BEAM_PLAN.value,
    CadDrawingType.SLAB_PLAN.value,
    "SITE_PLAN",
    "PARKING_PLAN",
    "ARCHITECTURAL_FLOOR_PLAN",
    "ROOF_PLAN",
    "ELEVATION",
    "SECTION",
    "GRID_PLAN",
    "FOUNDATION_LAYOUT",
    "COLUMN_SCHEDULE",
    "BEAM_SCHEDULE",
    "SLAB_SCHEDULE",
)


@dataclass
class BuildingPipelineResult:
    assembled: AssembledBuilding
    pem_version: int | None
    snapshot_id: UUID | None
    drawing_ids: list[str]
    sheet_paths: list[str]
    approval_request_id: UUID | None
    trace_link_count: int
    summary: dict[str, Any]


class BuildingDesignPipeline:
    def __init__(
        self,
        *,
        code_engine: CodeEngineService,
        project_service: ProjectService,
        pem_service: PemService,
        pem_revision_service: PemRevisionService,
        cad_generation_service: CadGenerationService,
        sheet_generation_service: SheetGenerationService,
        traceability_service: TraceabilityService | None = None,
        approval_service: HumanApprovalService | None = None,
    ) -> None:
        self._assembler = BuildingDesignAssembler(code_engine=code_engine)
        self._projects = project_service
        self._pem = pem_service
        self._revisions = pem_revision_service
        self._cad = cad_generation_service
        self._sheets = sheet_generation_service
        self._traceability = traceability_service
        self._approval = approval_service

    def generate_from_brief(
        self,
        project_id: UUID,
        brief_text: str,
        *,
        created_by: str | None = None,
        max_iterations: int = 5,
        generate_drawings: bool = True,
    ) -> BuildingPipelineResult:
        project = self._projects.get_project(project_id)
        if project is None:
            raise ProjectNotFoundError(project_id)
        assembled = self._assembler.assemble_from_text(
            brief_text,
            project_id=project_id,
            project_name=project.name,
            max_iterations=max_iterations,
        )
        if assembled.status == "WAITING_FOR_INPUT":
            return BuildingPipelineResult(
                assembled=assembled,
                pem_version=None,
                snapshot_id=None,
                drawing_ids=[],
                sheet_paths=[],
                approval_request_id=None,
                trace_link_count=0,
                summary=self._summary(assembled, None, [], []),
            )

        assembled.pem.project_id = project_id
        update = self._revisions.update_pem(
            project_id,
            assembled.pem,
            change_type=RevisionChangeType.PEM_UPDATE,
            summary="Automated building generation from natural-language brief",
            created_by=created_by,
            metadata={
                "pipeline": "BuildingDesignPipeline",
                "brief_language": assembled.brief.language.value,
                "status": assembled.status,
            },
        )
        assembled.pem.id = assembled.pem.id

        drawing_ids: list[str] = []
        sheet_paths: list[str] = []
        if generate_drawings:
            drawing_ids, sheet_paths = self._emit_drawings(
                project_id,
                assembled.pem,
                pem_version=update.pem_version,
                created_by=created_by,
            )

        approval_id = None
        if self._approval is not None:
            request = self._approval.create_request(
                project_id,
                requester=created_by or "building-pipeline",
                target_type=ApprovalTargetType.MODEL_CHANGE,
                target_action="pem.snapshot.publish",
                summary="Review automatically generated building model, analysis and drawings",
                target_object_type="pem_snapshot",
                target_object_id=update.snapshot_id,
                metadata={"pipeline": "BuildingDesignPipeline", "pem_version": update.pem_version},
            )
            approval_id = request.id

        link_count = self._record_traceability(
            project_id,
            brief_text=brief_text,
            snapshot_id=update.snapshot_id,
            drawing_ids=drawing_ids,
            created_by=created_by,
        )
        return BuildingPipelineResult(
            assembled=assembled,
            pem_version=update.pem_version,
            snapshot_id=update.snapshot_id,
            drawing_ids=drawing_ids,
            sheet_paths=sheet_paths,
            approval_request_id=approval_id,
            trace_link_count=link_count,
            summary=self._summary(assembled, update.pem_version, drawing_ids, sheet_paths),
        )

    def _emit_drawings(
        self,
        project_id: UUID,
        pem: ProjectEngineeringModel,
        *,
        pem_version: int,
        created_by: str | None,
    ) -> tuple[list[str], list[str]]:
        drawing_ids: list[str] = []
        for drawing_type in BUILDING_DRAWING_TYPES:
            try:
                drawing = self._cad.generate_drawing(
                    CadDrawingRequest(
                        project_id=project_id,
                        drawing_type=drawing_type,
                        output_format=CadOutputFormat.DXF,
                        pem_version=pem_version,
                    ),
                    created_by=created_by,
                )
                drawing_ids.append(str(drawing.id))
            except Exception:
                continue
        sheet_paths = self._sheets.generate_project_sheets(project_id, pem, pem_version=pem_version)
        return drawing_ids, sheet_paths

    def _record_traceability(
        self,
        project_id: UUID,
        *,
        brief_text: str,
        snapshot_id: UUID,
        drawing_ids: list[str],
        created_by: str | None,
    ) -> int:
        if self._traceability is None:
            return 0
        request_id = uuid4()
        self._traceability.create_link(
            project_id,
            source_type=TraceObjectType.USER_REQUEST.value,
            source_id=request_id,
            target_type=TraceObjectType.PEM_SNAPSHOT.value,
            target_id=snapshot_id,
            relationship_type=TraceabilityRelationshipType.REQUIREMENT_TO_SOURCE,
            metadata={"brief": brief_text[:240], "created_by": created_by},
        )
        count = 1
        for drawing_id in drawing_ids:
            try:
                record_model_to_drawing(
                    self._traceability,
                    project_id=project_id,
                    model_id=snapshot_id,
                    drawing_id=UUID(drawing_id),
                    metadata={"pipeline": "BuildingDesignPipeline"},
                )
                count += 1
            except Exception:
                continue
        return count

    @staticmethod
    def _summary(
        assembled: AssembledBuilding,
        pem_version: int | None,
        drawing_ids: list[str],
        sheet_paths: list[str],
    ) -> dict[str, Any]:
        building = assembled.pem.building_model
        structural = assembled.pem.structural_model
        return {
            "status": assembled.status,
            "missing_inputs": assembled.missing_inputs,
            "pem_version": pem_version,
            "plot_area_m2": building.site.plot_area_m2 if building.site else None,
            "floor_count": building.floor_count,
            "space_count": len(building.all_spaces()),
            "parking_count": len(building.all_parking_spaces()),
            "stair_count": len(building.stairs),
            "column_count": assembled.structure.column_count,
            "beam_count": assembled.structure.beam_count,
            "slab_count": assembled.structure.slab_count,
            "load_case_count": len(structural.load_cases),
            "analysis_status": assembled.analysis.status,
            "design_governing_utilization": assembled.design.governing_utilization,
            "qa_status": assembled.qa.overall_status,
            "failed_members": assembled.design.failed_member_ids,
            "drawing_count": len(drawing_ids),
            "sheet_count": len(sheet_paths),
            "assumptions": assembled.assumptions,
            "warnings": assembled.warnings,
            "fidelity": {
                "architecture": "PRELIMINARY_DETERMINISTIC",
                "structure": "PRELIMINARY_RC_FRAME",
                "gravity_loads": "PRELIMINARY",
                "live_load_tables": "ASCE_7_22_TABLE",
                "wind": "PRELIMINARY_NOT_CODE",
                "seismic": "PRELIMINARY_NOT_CODE",
                "analysis": "INTERNAL_2D_LINEAR_STATIC",
                "design": "ACI_318_25_SIMPLIFIED",
            },
        }
