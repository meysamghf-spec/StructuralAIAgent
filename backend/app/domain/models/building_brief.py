"""Structured building requirements extracted from a natural-language brief."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, Field, computed_field

from app.domain.models.pem_architecture import StructuralSystem


class BriefLanguage(StrEnum):
    EN = "EN"
    FA = "FA"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class OccupancyKind(StrEnum):
    RESIDENTIAL = "RESIDENTIAL"
    PARKING = "PARKING"
    MIXED_USE = "MIXED_USE"
    UNKNOWN = "UNKNOWN"


class ParsedField(BaseModel):
    """One extracted requirement plus the literal text it came from."""

    field: str
    value: str
    matched_text: str
    unit: str | None = None


class BuildingBrief(BaseModel):
    """
    Normalised building requirements. All lengths are metres regardless of how the
    brief expressed them.

    ``None`` means "not stated in the brief". Defaults are never silently invented
    here — :class:`BuildingLayoutGenerator` applies defaults and records them as
    explicit assumptions.
    """

    raw_text: str = ""
    language: BriefLanguage = BriefLanguage.UNKNOWN

    plot_length_m: float | None = None
    plot_width_m: float | None = None
    frontage_m: float | None = None

    setback_front_m: float | None = None
    setback_rear_m: float | None = None
    setback_side_m: float | None = None

    has_piloti: bool = False
    parking_space_count: int | None = None

    residential_floor_count: int | None = None
    apartments_per_floor: int | None = None
    bedrooms_per_apartment: int | None = None
    bathrooms_per_apartment: int | None = None
    has_living_room: bool = False
    has_kitchen: bool = False

    requires_stair: bool = False
    requires_elevator: bool = False

    storey_height_m: float | None = None
    occupancy: OccupancyKind = OccupancyKind.UNKNOWN
    structural_system: StructuralSystem = StructuralSystem.UNDETERMINED

    parsed_fields: list[ParsedField] = Field(default_factory=list)
    unresolved_terms: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def plot_area_m2(self) -> float | None:
        if self.plot_length_m is None or self.plot_width_m is None:
            return None
        return round(self.plot_length_m * self.plot_width_m, 4)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_floor_count(self) -> int | None:
        """Piloti/parking storey plus residential storeys."""
        if self.residential_floor_count is None:
            return None
        return self.residential_floor_count + (1 if self.has_piloti else 0)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def total_apartment_count(self) -> int | None:
        if self.residential_floor_count is None or self.apartments_per_floor is None:
            return None
        return self.residential_floor_count * self.apartments_per_floor

    @property
    def has_plot_geometry(self) -> bool:
        return self.plot_length_m is not None and self.plot_width_m is not None

    def missing_critical_inputs(self) -> list[str]:
        """Inputs without which no layout can be generated at all."""
        missing: list[str] = []
        if self.plot_length_m is None or self.plot_width_m is None:
            missing.append("Plot dimensions (length x width in metres)")
        if self.residential_floor_count is None and not self.has_piloti:
            missing.append("Number of floors")
        return missing

    def field_value(self, field: str) -> ParsedField | None:
        for parsed in self.parsed_fields:
            if parsed.field == field:
                return parsed
        return None


BriefConfidence = Literal["HIGH", "MEDIUM", "LOW"]
