"""Analysis engine domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class AnalysisStatus(StrEnum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    WARNING = "WARNING"
    FAILED = "FAILED"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    REQUIRES_SOLVER = "REQUIRES_SOLVER"
    REQUIRES_LOCAL_SOFTWARE = "REQUIRES_LOCAL_SOFTWARE"
    MODEL_NOT_READY = "MODEL_NOT_READY"


TERMINAL_ANALYSIS_STATUSES = frozenset(
    {
        AnalysisStatus.SUCCESS,
        AnalysisStatus.WARNING,
        AnalysisStatus.FAILED,
        AnalysisStatus.NOT_IMPLEMENTED,
        AnalysisStatus.REQUIRES_SOLVER,
        AnalysisStatus.REQUIRES_LOCAL_SOFTWARE,
        AnalysisStatus.MODEL_NOT_READY,
    }
)

SUPPORTED_ANALYSIS_TYPES = frozenset(
    {
        "STATIC",
        "LINEAR_STATIC",
        "MODAL",
        "DRIFT",
        "LATERAL_DRIFT",
        "SEISMIC",
    }
)


class AnalysisRequest(BaseModel):
    project_id: UUID
    analysis_type: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    pem_version: int | None = None


class AnalysisRun(BaseModel):
    id: UUID
    project_id: UUID
    pem_snapshot_id: UUID
    pem_version: int
    analysis_type: str
    status: AnalysisStatus
    capability_status: str
    message: str
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    model_summary: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime
    completed_at: datetime | None = None


class AnalysisResult(BaseModel):
    id: UUID | None = None
    project_id: UUID
    analysis_type: str
    status: AnalysisStatus
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
    def from_run(cls, run: AnalysisRun) -> AnalysisResult:
        return cls(
            id=run.id,
            project_id=run.project_id,
            analysis_type=run.analysis_type,
            status=run.status,
            capability_status=run.capability_status,
            message=run.message,
            pem_snapshot_id=run.pem_snapshot_id,
            pem_version=run.pem_version,
            model_version_id=run.pem_snapshot_id,
            inputs=run.inputs,
            outputs=run.outputs,
            model_summary=run.model_summary,
            validation_summary=run.validation_summary,
            created_at=run.created_at,
        )


class AnalysisReadinessReport(BaseModel):
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
