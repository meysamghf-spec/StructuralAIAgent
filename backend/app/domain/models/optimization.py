"""Optimization engine domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class OptimizationStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    REQUIRES_SOLVER = "REQUIRES_SOLVER"
    REQUIRES_ANALYSIS = "REQUIRES_ANALYSIS"
    REQUIRES_DESIGN = "REQUIRES_DESIGN"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"


SUPPORTED_OPTIMIZATION_TYPES = frozenset(
    {
        "WEIGHT",
        "MATERIAL_EFFICIENCY",
        "ESTIMATED_COST",
        "MEMBER_SIZE",
        "CONSTRUCTABILITY",
        "CODE_COMPLIANCE",
        "PERFORMANCE",
        "MULTI_OBJECTIVE",
    }
)


class OptimizationMode(StrEnum):
    INDEPENDENT = "INDEPENDENT"
    SHARED_SECTION = "SHARED_SECTION"


SUPPORTED_OPTIMIZATION_MODES = frozenset(item.value for item in OptimizationMode)


class OptimizationRequest(BaseModel):
    project_id: UUID
    optimization_type: str
    objective: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    pem_version: int | None = None
    analysis_run_id: UUID | None = None
    design_run_id: UUID | None = None


class OptimizationRun(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    analysis_run_id: UUID | None = None
    design_run_id: UUID | None = None
    optimization_type: str
    objective: str
    status: OptimizationStatus
    capability_status: str
    message: str
    code_edition: str | None = None
    constraints: dict[str, Any] = Field(default_factory=dict)
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class OptimizationResult(BaseModel):
    id: UUID | None = None
    project_id: UUID
    optimization_type: str
    objective: str
    status: OptimizationStatus
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
    def from_run(cls, run: OptimizationRun) -> OptimizationResult:
        return cls(
            id=run.id,
            project_id=run.project_id,
            optimization_type=run.optimization_type,
            objective=run.objective,
            status=run.status,
            capability_status=run.capability_status,
            message=run.message,
            code_edition=run.code_edition,
            pem_snapshot_id=run.pem_snapshot_id,
            pem_version=run.pem_version,
            analysis_run_id=run.analysis_run_id,
            design_run_id=run.design_run_id,
            constraints=run.constraints,
            inputs=run.inputs,
            outputs=run.outputs,
            model_summary=run.model_summary,
            validation_summary=run.validation_summary,
            created_at=run.created_at,
        )


class OptimizationReadinessReport(BaseModel):
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
