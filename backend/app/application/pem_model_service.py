"""Application service — structured PEM model operations."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from app.application.exceptions import PemNotFoundError, PemValidationError, ProjectNotFoundError
from app.application.human_approval_service import HumanApprovalService
from app.application.pem_revision_service import PemRevisionService, PemUpdateResult
from app.application.project_service import PemService, ProjectService
from app.application.traceability_integration import record_approval_to_model
from app.application.traceability_service import TraceabilityService
from app.domain.approval_policy import requires_approval_for_target
from app.domain.models.human_approval import ApprovalTargetType
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import (
    AnalysisModelReference,
    DesignParameters,
    GeometryModel,
    LoadCombination,
    LoadCase,
    MaterialLibrary,
    MemberLibrary,
    SectionLibrary,
    StructuralModel,
    SupportDefinition,
)
from app.domain.models.revision import RevisionChangeType
from app.domain.models.validation import ValidationFinding, ValidationReport, ValidationStatus
from app.domain.pem_validation import validate_structural_model


MAJOR_CHANGE_TYPES = frozenset(
    {
        RevisionChangeType.GEOMETRY_UPDATE,
        RevisionChangeType.MATERIALS_UPDATE,
        RevisionChangeType.LOADS_UPDATE,
        RevisionChangeType.LOAD_COMBINATIONS_UPDATE,
        RevisionChangeType.MEMBERS_UPDATE,
    }
)


@dataclass
class PemModelUpdateResult:
    pem_version: int
    snapshot_id: UUID
    revision_number: int
    validation: ValidationReport
    approval_request_id: UUID | None = None


@dataclass
class PemModelSummary:
    project_id: UUID
    pem_version: int
    snapshot_id: UUID
    project_name: str
    grid_count: int
    level_count: int
    material_count: int
    section_count: int
    member_count: int
    support_count: int
    load_case_count: int
    load_combination_count: int
    analysis_status: str
    validation_status: str


class PemModelService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        pem_service: PemService,
        pem_revision_service: PemRevisionService,
        approval_service: HumanApprovalService | None = None,
        traceability_service: TraceabilityService | None = None,
    ) -> None:
        self._projects = project_service
        self._pem = pem_service
        self._revisions = pem_revision_service
        self._approval = approval_service
        self._traceability = traceability_service

    def get_current_model(self, project_id: UUID) -> tuple[ProjectEngineeringModel, int, UUID]:
        self._ensure_project(project_id)
        meta = self._pem.get_current_snapshot_meta(project_id)
        pem = self._pem.get_current_pem(project_id)
        if meta is None or pem is None:
            raise PemNotFoundError(project_id)
        return pem, meta.version, meta.id

    def get_model_summary(self, project_id: UUID) -> PemModelSummary:
        pem, version, snapshot_id = self.get_current_model(project_id)
        validation = self.validate_model(project_id)
        structural = pem.structural_model
        return PemModelSummary(
            project_id=project_id,
            pem_version=version,
            snapshot_id=snapshot_id,
            project_name=pem.metadata.name,
            grid_count=len(structural.geometry.grids),
            level_count=len(structural.geometry.levels),
            material_count=(
                len(structural.materials.concrete)
                + len(structural.materials.steel)
                + len(structural.materials.reinforcement)
            ),
            section_count=(
                len(structural.sections.beams)
                + len(structural.sections.columns)
                + len(structural.sections.walls)
                + len(structural.sections.slabs)
                + len(structural.sections.foundations)
            ),
            member_count=len(structural.members.members),
            support_count=len(structural.supports),
            load_case_count=len(structural.load_cases),
            load_combination_count=len(structural.load_combinations),
            analysis_status=structural.analysis_model.capability_status,
            validation_status=validation.overall_status.value,
        )

    def validate_model(self, project_id: UUID) -> ValidationReport:
        pem, _, _ = self.get_current_model(project_id)
        findings = validate_structural_model(pem)
        return self._build_report(project_id, findings)

    def update_geometry(
        self,
        project_id: UUID,
        geometry: GeometryModel,
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.GEOMETRY_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(update={"geometry": geometry}),
        )

    def update_materials(
        self,
        project_id: UUID,
        materials: MaterialLibrary,
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.MATERIALS_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(update={"materials": materials}),
        )

    def update_sections(
        self,
        project_id: UUID,
        sections: SectionLibrary,
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.SECTIONS_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(update={"sections": sections}),
        )

    def update_members(
        self,
        project_id: UUID,
        members: MemberLibrary,
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.MEMBERS_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(update={"members": members}),
        )

    def update_supports(
        self,
        project_id: UUID,
        supports: list[SupportDefinition],
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.SUPPORTS_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(update={"supports": supports}),
        )

    def update_load_cases(
        self,
        project_id: UUID,
        load_cases: list[LoadCase],
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.LOADS_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(update={"load_cases": load_cases}),
        )

    def update_load_combinations(
        self,
        project_id: UUID,
        load_combinations: list[LoadCombination],
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.LOAD_COMBINATIONS_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(
                update={"load_combinations": load_combinations}
            ),
        )

    def update_analysis_model(
        self,
        project_id: UUID,
        analysis_model: AnalysisModelReference,
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.ANALYSIS_MODEL_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(update={"analysis_model": analysis_model}),
        )

    def update_design_parameters(
        self,
        project_id: UUID,
        design_parameters: DesignParameters,
        *,
        summary: str,
        created_by: str | None = None,
        request_approval: bool = False,
    ) -> PemModelUpdateResult:
        return self._update_section(
            project_id,
            change_type=RevisionChangeType.DESIGN_PARAMETERS_UPDATE,
            summary=summary,
            created_by=created_by,
            request_approval=request_approval,
            apply=lambda structural: structural.model_copy(
                update={"design_parameters": design_parameters}
            ),
        )

    def _update_section(
        self,
        project_id: UUID,
        *,
        change_type: RevisionChangeType,
        summary: str,
        created_by: str | None,
        request_approval: bool,
        apply: Callable[[StructuralModel], StructuralModel],
    ) -> PemModelUpdateResult:
        pem, _, before_snapshot_id = self.get_current_model(project_id)
        updated_structural = apply(pem.structural_model)
        candidate = pem.model_copy(update={"structural_model": updated_structural})
        findings = validate_structural_model(candidate)
        validation = self._build_report(project_id, findings)
        if any(finding.status == ValidationStatus.ERROR for finding in findings):
            raise PemValidationError(project_id, validation)

        needs_approval = request_approval or (
            change_type in MAJOR_CHANGE_TYPES
            and requires_approval_for_target(
                ApprovalTargetType.MODEL_CHANGE,
                "pem.snapshot.publish",
            )
        )
        approval_request_id: UUID | None = None
        if needs_approval and self._approval is not None:
            approval = self._approval.create_request(
                project_id,
                requester=created_by or "system",
                target_type=ApprovalTargetType.MODEL_CHANGE,
                target_action="pem.snapshot.publish",
                summary=f"Approve PEM change: {summary}",
                target_object_type="pem_snapshot",
                target_object_id=before_snapshot_id,
                metadata={"change_type": change_type.value, "pending_snapshot": True},
            )
            approval_request_id = approval.id

        update_result = self._revisions.update_pem(
            project_id,
            candidate,
            change_type=change_type,
            summary=summary,
            created_by=created_by,
            metadata={
                "validation_status": validation.overall_status.value,
                "approval_request_id": str(approval_request_id) if approval_request_id else None,
            },
        )

        if approval_request_id and self._traceability is not None:
            record_approval_to_model(
                self._traceability,
                project_id=project_id,
                approval_id=approval_request_id,
                model_id=update_result.snapshot_id,
                metadata={"change_type": change_type.value},
            )

        return PemModelUpdateResult(
            pem_version=update_result.pem_version,
            snapshot_id=update_result.snapshot_id,
            revision_number=update_result.revision.revision_number,
            validation=validation,
            approval_request_id=approval_request_id,
        )

    def _ensure_project(self, project_id: UUID) -> None:
        if self._projects.get_project(project_id) is None:
            raise ProjectNotFoundError(project_id)

    @staticmethod
    def _build_report(project_id: UUID, findings: list[ValidationFinding]) -> ValidationReport:
        if not findings:
            overall = ValidationStatus.PASS
            summary = "Structural model validation passed"
        elif any(f.status == ValidationStatus.ERROR for f in findings):
            overall = ValidationStatus.ERROR
            summary = "Structural model validation failed"
        elif any(f.status == ValidationStatus.REQUIRES_ENGINEER_REVIEW for f in findings):
            overall = ValidationStatus.REQUIRES_ENGINEER_REVIEW
            summary = "Structural model requires engineer review"
        elif any(f.status == ValidationStatus.WARNING for f in findings):
            overall = ValidationStatus.WARNING
            summary = "Structural model validation completed with warnings"
        else:
            overall = ValidationStatus.PASS
            summary = "Structural model validation passed"

        return ValidationReport(
            project_id=project_id,
            overall_status=overall,
            findings=findings,
            summary=summary,
        )
