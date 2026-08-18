"""Project context assembly API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.models.pem import CodeConfiguration, UnitConfiguration
from app.domain.models.project_context import ProjectContextAssembly
from app.domain.models.project_memory import MemoryType


class ProjectFileSummaryResponse(BaseModel):
    id: UUID
    filename: str
    file_type: str
    parsing_status: str
    extraction_status: str


class ProjectMemorySummaryResponse(BaseModel):
    id: UUID
    memory_type: MemoryType
    content: str
    source_type: str | None = None
    source_id: UUID | None = None
    confidence: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class CodeConfigurationSummaryResponse(BaseModel):
    jurisdiction: str
    profile_type: str
    governing_building_code: str
    loading_standard: str
    concrete_standard: str
    steel_standard: str
    compatibility_status: str
    status: str

    @classmethod
    def from_domain(cls, config: CodeConfiguration) -> CodeConfigurationSummaryResponse:
        return cls(
            jurisdiction=config.jurisdiction.value,
            profile_type=config.profile_type.value,
            governing_building_code=config.governing_building_code.edition,
            loading_standard=config.loading_standard.edition,
            concrete_standard=config.concrete_standard.edition,
            steel_standard=config.steel_standard.edition,
            compatibility_status=config.compatibility_status.value,
            status=config.status.value,
        )


class UnitConfigurationResponse(BaseModel):
    system: str
    length_unit: str
    force_unit: str
    moment_unit: str
    stress_unit: str
    area_unit: str
    volume_unit: str

    @classmethod
    def from_domain(cls, config: UnitConfiguration) -> UnitConfigurationResponse:
        return cls(
            system=config.system.value,
            length_unit=config.length_unit,
            force_unit=config.force_unit,
            moment_unit=config.moment_unit,
            stress_unit=config.stress_unit,
            area_unit=config.area_unit,
            volume_unit=config.volume_unit,
        )


class ProjectContextAssemblyResponse(BaseModel):
    project_id: UUID
    project_name: str
    pem_version: int | None = None
    code_configuration: CodeConfigurationSummaryResponse | None = None
    unit_configuration: UnitConfigurationResponse | None = None
    memory_total_count: int
    memory_counts_by_type: dict[str, int] = Field(default_factory=dict)
    memories: list[ProjectMemorySummaryResponse]
    files: list[ProjectFileSummaryResponse]

    @classmethod
    def from_domain(cls, context: ProjectContextAssembly) -> ProjectContextAssemblyResponse:
        return cls(
            project_id=context.project_id,
            project_name=context.project_name,
            pem_version=context.pem_version,
            code_configuration=(
                CodeConfigurationSummaryResponse.from_domain(context.code_configuration)
                if context.code_configuration is not None
                else None
            ),
            unit_configuration=(
                UnitConfigurationResponse.from_domain(context.unit_configuration)
                if context.unit_configuration is not None
                else None
            ),
            memory_total_count=context.memory_total_count,
            memory_counts_by_type=context.memory_counts_by_type,
            memories=[
                ProjectMemorySummaryResponse.model_validate(memory.model_dump())
                for memory in context.memories
            ],
            files=[ProjectFileSummaryResponse.model_validate(f.model_dump()) for f in context.files],
        )
