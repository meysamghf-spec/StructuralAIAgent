"""Structured architectural concept derived from engineering requests."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ArchitecturalSpace(BaseModel):
    name: str
    space_type: str
    count: int = 1
    approximate_area_m2: float | None = None
    notes: str | None = None


class ArchitecturalConcept(BaseModel):
    story_count: int | None = None
    plan_length_m: float | None = None
    plan_width_m: float | None = None
    total_plan_area_m2: float | None = None
    spaces: list[ArchitecturalSpace] = Field(default_factory=list)
    circulation: list[str] = Field(default_factory=list)
    functional_zones: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
