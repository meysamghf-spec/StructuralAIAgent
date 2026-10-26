"""Analysis and design API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.analysis import (
    AnalysisReadinessReport,
    AnalysisRequest,
    AnalysisResult,
    AnalysisRun,
)


class AnalysisRequestBody(BaseModel):
    project_id: UUID
    analysis_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    pem_version: int | None = None

    def to_domain(self) -> AnalysisRequest:
        return AnalysisRequest(
            project_id=self.project_id,
            analysis_type=self.analysis_type,
            parameters=self.parameters,
            pem_version=self.pem_version,
        )


class AnalysisResultResponse(BaseModel):
    id: UUID | None = None
    project_id: UUID
    analysis_type: str
    status: str
    capability_status: str
    message: str
    pem_snapshot_id: UUID | None = None
    pem_version: int | None = None
    model_version_id: UUID | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, result: AnalysisResult) -> AnalysisResultResponse:
        return cls.model_validate(result.model_dump(mode="json"))


class AnalysisRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    analysis_type: str
    status: str
    capability_status: str
    message: str
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_domain(cls, run: AnalysisRun) -> AnalysisRunResponse:
        payload = run.model_dump(mode="json")
        payload["status"] = run.status.value
        return cls.model_validate(payload)


class AnalysisRunListResponse(BaseModel):
    project_id: UUID
    runs: list[AnalysisRunResponse]


class AnalysisReadinessResponse(BaseModel):
    project_id: UUID
    pem_version: int
    pem_snapshot_id: UUID
    ready_for_solver: bool
    readiness_status: str
    summary: str
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_status: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)

    @classmethod
    def from_domain(cls, report: AnalysisReadinessReport) -> AnalysisReadinessResponse:
        return cls.model_validate(report.model_dump(mode="json"))


class DesignRequestBody(BaseModel):
    project_id: UUID
    design_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    pem_version: int | None = None
    analysis_run_id: UUID | None = None

    def to_domain(self):
        from app.domain.models.design import DesignRequest

        return DesignRequest(
            project_id=self.project_id,
            design_type=self.design_type,
            parameters=self.parameters,
            pem_version=self.pem_version,
            analysis_run_id=self.analysis_run_id,
        )


class DesignResultResponse(BaseModel):
    id: UUID | None = None
    project_id: UUID
    design_type: str
    status: str
    capability_status: str
    message: str
    code_edition: str | None = None
    pem_snapshot_id: UUID | None = None
    pem_version: int | None = None
    analysis_run_id: UUID | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, result) -> DesignResultResponse:
        payload = result.model_dump(mode="json")
        payload["status"] = result.status.value
        return cls.model_validate(payload)


class DesignRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    analysis_run_id: UUID | None = None
    design_type: str
    status: str
    capability_status: str
    message: str
    code_edition: str | None = None
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_domain(cls, run) -> DesignRunResponse:
        payload = run.model_dump(mode="json")
        payload["status"] = run.status.value
        return cls.model_validate(payload)


class DesignRunListResponse(BaseModel):
    project_id: UUID
    runs: list[DesignRunResponse]


class DesignReadinessResponse(BaseModel):
    project_id: UUID
    pem_version: int
    pem_snapshot_id: UUID
    ready_for_design: bool
    readiness_status: str
    summary: str
    code_edition: str | None = None
    code_configuration_valid: bool = True
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_status: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    available_analysis_runs: int = 0
    usable_analysis_runs: int = 0

    @classmethod
    def from_domain(cls, report) -> DesignReadinessResponse:
        return cls.model_validate(report.model_dump(mode="json"))


class OptimizationRequestBody(BaseModel):
    project_id: UUID
    optimization_type: str
    objective: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    pem_version: int | None = None
    analysis_run_id: UUID | None = None
    design_run_id: UUID | None = None

    def to_domain(self):
        from app.domain.models.optimization import OptimizationRequest

        return OptimizationRequest(
            project_id=self.project_id,
            optimization_type=self.optimization_type,
            objective=self.objective,
            constraints=self.constraints,
            parameters=self.parameters,
            pem_version=self.pem_version,
            analysis_run_id=self.analysis_run_id,
            design_run_id=self.design_run_id,
        )


class OptimizationResultResponse(BaseModel):
    id: UUID | None = None
    project_id: UUID
    optimization_type: str
    objective: str
    status: str
    capability_status: str
    message: str
    code_edition: str | None = None
    pem_snapshot_id: UUID | None = None
    pem_version: int | None = None
    analysis_run_id: UUID | None = None
    design_run_id: UUID | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None

    @classmethod
    def from_domain(cls, result) -> OptimizationResultResponse:
        payload = result.model_dump(mode="json")
        payload["status"] = result.status.value
        return cls.model_validate(payload)


class OptimizationRunResponse(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    analysis_run_id: UUID | None = None
    design_run_id: UUID | None = None
    optimization_type: str
    objective: str
    status: str
    capability_status: str
    message: str
    code_edition: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None

    @classmethod
    def from_domain(cls, run) -> OptimizationRunResponse:
        payload = run.model_dump(mode="json")
        payload["status"] = run.status.value
        return cls.model_validate(payload)


class OptimizationRunListResponse(BaseModel):
    project_id: UUID
    runs: list[OptimizationRunResponse]


class OptimizationReadinessResponse(BaseModel):
    project_id: UUID
    pem_version: int
    pem_snapshot_id: UUID
    ready_for_optimization: bool
    readiness_status: str
    summary: str
    code_edition: str | None = None
    code_configuration_valid: bool = True
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_status: str
    findings: list[dict[str, Any]] = Field(default_factory=list)
    missing_requirements: list[str] = Field(default_factory=list)
    available_analysis_runs: int = 0
    usable_analysis_runs: int = 0
    available_design_runs: int = 0
    usable_design_runs: int = 0
    checklist: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_domain(cls, report) -> OptimizationReadinessResponse:
        from app.application.optimization_checklist import checklist_for_readiness

        data = report.model_dump(mode="json")
        data["checklist"] = checklist_for_readiness(data, str(data.get("project_id")))
        return cls.model_validate(data)
