"""Scoped project context assembly for AI and orchestration."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.pem import CodeConfiguration, UnitConfiguration
from app.domain.models.project_memory import ProjectMemory


class ProjectFileSummary(BaseModel):
    id: UUID
    filename: str
    file_type: str
    parsing_status: str
    extraction_status: str


class EngineeringResultSummary(BaseModel):
    id: UUID
    analysis_run_id: UUID | None = None
    software: str
    validation_status: str
    engineering_results_available: bool
    result_types: list[str] = Field(default_factory=list)


class CadDrawingSummary(BaseModel):
    id: UUID
    drawing_type: str
    output_format: str
    status: str
    validation_status: str
    message: str


class ProjectContextAssembly(BaseModel):
    project_id: UUID
    project_name: str
    pem_version: int | None = None
    pem_snapshot_id: UUID | None = None
    code_configuration: CodeConfiguration | None = None
    unit_configuration: UnitConfiguration | None = None
    memory_total_count: int
    memory_counts_by_type: dict[str, int] = Field(default_factory=dict)
    memories: list[ProjectMemory] = Field(default_factory=list)
    files: list[ProjectFileSummary] = Field(default_factory=list)
    validated_engineering_results: list[EngineeringResultSummary] = Field(default_factory=list)
    recent_analysis_runs: list[dict[str, Any]] = Field(default_factory=list)
    recent_cad_drawings: list[CadDrawingSummary] = Field(default_factory=list)
