"""Project engineering model API schemas."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.pem_model_service import PemModelSummary, PemModelUpdateResult
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
from app.domain.models.validation import ValidationReport


class ModelEnvelopeResponse(BaseModel):
    project_id: UUID
    pem_version: int
    snapshot_id: UUID
    structural_model: StructuralModel
    code_configuration: dict[str, Any]
    unit_configuration: dict[str, Any]


class ModelSummaryResponse(BaseModel):
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

    @classmethod
    def from_domain(cls, summary: PemModelSummary) -> ModelSummaryResponse:
        return cls.model_validate(summary.__dict__)


class ModelUpdateRequest(BaseModel):
    summary: str = Field(..., min_length=1)
    request_approval: bool = False


class GeometryUpdateRequest(ModelUpdateRequest):
    geometry: GeometryModel


class MaterialsUpdateRequest(ModelUpdateRequest):
    materials: MaterialLibrary


class SectionsUpdateRequest(ModelUpdateRequest):
    sections: SectionLibrary


class MembersUpdateRequest(ModelUpdateRequest):
    members: MemberLibrary


class SupportsUpdateRequest(ModelUpdateRequest):
    supports: list[SupportDefinition]


class LoadCasesUpdateRequest(ModelUpdateRequest):
    load_cases: list[LoadCase]


class LoadCombinationsUpdateRequest(ModelUpdateRequest):
    load_combinations: list[LoadCombination]


class AnalysisModelUpdateRequest(ModelUpdateRequest):
    analysis_model: AnalysisModelReference


class DesignParametersUpdateRequest(ModelUpdateRequest):
    design_parameters: DesignParameters


class ModelValidationResponse(BaseModel):
    project_id: UUID
    overall_status: str
    summary: str
    findings: list[dict[str, Any]] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, report: ValidationReport) -> ModelValidationResponse:
        return cls(
            project_id=report.project_id,
            overall_status=report.overall_status.value,
            summary=report.summary,
            findings=[finding.model_dump(mode="json") for finding in report.findings],
        )


class ModelUpdateResponse(BaseModel):
    pem_version: int
    snapshot_id: UUID
    revision_number: int
    validation: ModelValidationResponse
    approval_request_id: UUID | None = None

    @classmethod
    def from_domain(cls, result: PemModelUpdateResult) -> ModelUpdateResponse:
        return cls(
            pem_version=result.pem_version,
            snapshot_id=result.snapshot_id,
            revision_number=result.revision_number,
            validation=ModelValidationResponse.from_domain(result.validation),
            approval_request_id=result.approval_request_id,
        )
