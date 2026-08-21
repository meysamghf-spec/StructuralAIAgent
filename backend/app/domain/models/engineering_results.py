"""Vendor-neutral engineering result domain models."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class EngineeringResultType(StrEnum):
    JOINT_DISPLACEMENTS = "joint_displacements"
    JOINT_REACTIONS = "joint_reactions"
    FRAME_FORCES = "frame_forces"
    FRAME_MOMENTS = "frame_moments"
    FRAME_AXIAL_FORCES = "frame_axial_forces"
    FRAME_SHEAR = "frame_shear"
    SHELL_RESULTS = "shell_results"
    STORY_DRIFTS = "story_drifts"
    MODAL_PERIODS = "modal_periods"
    MODAL_FREQUENCIES = "modal_frequencies"
    MASS_PARTICIPATION = "mass_participation"
    LOAD_COMBINATION_RESULTS = "load_combination_results"


class ResultValidationStatus(StrEnum):
    VALIDATED = "VALIDATED"
    INVALID = "INVALID"
    INCOMPLETE = "INCOMPLETE"
    PARTIALLY_VALIDATED = "PARTIALLY_VALIDATED"
    REQUIRES_ENGINEER_REVIEW = "REQUIRES_ENGINEER_REVIEW"
    REQUIRES_LOCAL_SOFTWARE = "REQUIRES_LOCAL_SOFTWARE"


SUPPORTED_ENGINEERING_RESULT_TYPES = frozenset(item.value for item in EngineeringResultType)


class NormalizedEngineeringResults(BaseModel):
    joint_displacements: list[dict[str, Any]] = Field(default_factory=list)
    joint_reactions: list[dict[str, Any]] = Field(default_factory=list)
    frame_forces: list[dict[str, Any]] = Field(default_factory=list)
    frame_moments: list[dict[str, Any]] = Field(default_factory=list)
    frame_axial_forces: list[dict[str, Any]] = Field(default_factory=list)
    frame_shear: list[dict[str, Any]] = Field(default_factory=list)
    shell_results: list[dict[str, Any]] = Field(default_factory=list)
    story_drifts: list[dict[str, Any]] = Field(default_factory=list)
    modal_periods: list[dict[str, Any]] = Field(default_factory=list)
    modal_frequencies: list[dict[str, Any]] = Field(default_factory=list)
    mass_participation: list[dict[str, Any]] = Field(default_factory=list)
    load_combination_results: list[dict[str, Any]] = Field(default_factory=list)

    def present_types(self) -> list[str]:
        mapping = {
            "joint_displacements": self.joint_displacements,
            "joint_reactions": self.joint_reactions,
            "frame_forces": self.frame_forces,
            "frame_moments": self.frame_moments,
            "frame_axial_forces": self.frame_axial_forces,
            "frame_shear": self.frame_shear,
            "shell_results": self.shell_results,
            "story_drifts": self.story_drifts,
            "modal_periods": self.modal_periods,
            "modal_frequencies": self.modal_frequencies,
            "mass_participation": self.mass_participation,
            "load_combination_results": self.load_combination_results,
        }
        return [key for key, values in mapping.items() if values]


class EngineeringResultSet(BaseModel):
    id: UUID
    project_id: UUID
    analysis_run_id: UUID | None = None
    integration_execution_id: UUID | None = None
    pem_snapshot_id: UUID
    pem_version: int
    software: str
    software_version: str
    analysis_type: str
    validation_status: ResultValidationStatus
    engineering_results_available: bool
    result_types: list[str] = Field(default_factory=list)
    results: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    validation_summary: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_by: str | None = None
    created_at: datetime


class EngineeringResultIngestionRequest(BaseModel):
    project_id: UUID
    analysis_run_id: UUID | None = None
    integration_execution_id: UUID | None = None
    pem_snapshot_id: UUID
    pem_version: int
    software: str
    software_version: str
    analysis_type: str
    raw_results: dict[str, Any] = Field(default_factory=dict)
    provenance: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
