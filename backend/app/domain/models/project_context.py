"""Scoped project context assembly for AI and orchestration."""

from __future__ import annotations

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


class ProjectContextAssembly(BaseModel):
    project_id: UUID
    project_name: str
    pem_version: int | None = None
    code_configuration: CodeConfiguration | None = None
    unit_configuration: UnitConfiguration | None = None
    memory_total_count: int
    memory_counts_by_type: dict[str, int] = Field(default_factory=dict)
    memories: list[ProjectMemory] = Field(default_factory=list)
    files: list[ProjectFileSummary] = Field(default_factory=list)
