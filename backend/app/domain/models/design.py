"""Design engine domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class DesignStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    REQUIRES_SOLVER = "REQUIRES_SOLVER"
    REQUIRES_ANALYSIS = "REQUIRES_ANALYSIS"
    MODEL_NOT_READY = "MODEL_NOT_READY"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"


SUPPORTED_DESIGN_TYPES = frozenset(
    {
        "CONCRETE_BEAM",
        "CONCRETE_COLUMN",
        "CONCRETE_MEMBER",
        "CONCRETE_SLAB",
        "CONCRETE_WALL",
        "CONCRETE_FOUNDATION",
        "STEEL_BEAM",
        "STEEL_COLUMN",
        "STEEL_MEMBER",
        "STEEL_BRACE",
        "FOUNDATION",
        "SLAB",
        "WALL",
    }
)

CONCRETE_DESIGN_TYPES = frozenset(
    {
        "CONCRETE_BEAM",
        "CONCRETE_COLUMN",
        "CONCRETE_MEMBER",
        "CONCRETE_SLAB",
        "CONCRETE_WALL",
        "CONCRETE_FOUNDATION",
    }
)

STEEL_DESIGN_TYPES = frozenset(
    {
        "STEEL_BEAM",
        "STEEL_COLUMN",
        "STEEL_MEMBER",
        "STEEL_BRACE",
    }
)


class DesignRequest(BaseModel):
    project_id: UUID
    design_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    pem_version: int | None = None
    analysis_run_id: UUID | None = None


class DesignRun(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    analysis_run_id: UUID | None = None
    design_type: str
    status: DesignStatus
    capability_status: str
    message: str
    code_edition: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class DesignResult(BaseModel):
    id: UUID | None = None
    project_id: UUID
    design_type: str
    status: DesignStatus
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
    def from_run(cls, run: DesignRun) -> DesignResult:
        return cls(
            id=run.id,
            project_id=run.project_id,
            design_type=run.design_type,
            status=run.status,
            capability_status=run.capability_status,
            message=run.message,
            code_edition=run.code_edition,
            pem_snapshot_id=run.pem_snapshot_id,
            pem_version=run.pem_version,
            analysis_run_id=run.analysis_run_id,
            inputs=run.inputs,
            outputs=run.outputs,
            model_summary=run.model_summary,
            validation_summary=run.validation_summary,
            created_at=run.created_at,
        )


class DesignReadinessReport(BaseModel):
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
