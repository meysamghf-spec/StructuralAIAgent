"""Structured structural engineering entities for ProjectEngineeringModel."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


def new_structural_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:12]}"


class SupportType(StrEnum):
    FIXED = "FIXED"
    PINNED = "PINNED"
    ROLLER = "ROLLER"
    CUSTOM = "CUSTOM"


class MemberType(StrEnum):
    BEAM = "BEAM"
    COLUMN = "COLUMN"
    BRACE = "BRACE"
    WALL = "WALL"
    SLAB = "SLAB"
    FOUNDATION = "FOUNDATION"


class LoadCategory(StrEnum):
    DEAD = "DEAD"
    LIVE = "LIVE"
    WIND = "WIND"
    SEISMIC = "SEISMIC"
    SNOW = "SNOW"
    OTHER = "OTHER"


class LoadDistribution(StrEnum):
    POINT = "POINT"
    LINE = "LINE"
    AREA = "AREA"
    NODAL = "NODAL"
    MEMBER = "MEMBER"
    SURFACE = "SURFACE"


class SectionKind(StrEnum):
    BEAM = "BEAM"
    COLUMN = "COLUMN"
    WALL = "WALL"
    SLAB = "SLAB"
    FOUNDATION = "FOUNDATION"


class MaterialKind(StrEnum):
    CONCRETE = "CONCRETE"
    STEEL = "STEEL"
    REINFORCEMENT = "REINFORCEMENT"


class GridDefinition(BaseModel):
    id: str
    name: str
    spacing_x: float | None = None
    spacing_y: float | None = None
    origin_x: float = 0.0
    origin_y: float = 0.0
    orientation_deg: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class LevelDefinition(BaseModel):
    id: str
    name: str
    elevation: float
    sort_order: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class PointDefinition(BaseModel):
    id: str
    x: float
    y: float
    z: float
    level_id: str | None = None
    grid_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LineDefinition(BaseModel):
    id: str
    start_point_id: str
    end_point_id: str
    member_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AreaDefinition(BaseModel):
    id: str
    boundary_point_ids: list[str] = Field(default_factory=list)
    level_id: str | None = None
    member_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_boundary(self) -> AreaDefinition:
        if len(self.boundary_point_ids) > 0 and len(self.boundary_point_ids) < 3:
            raise ValueError("Area boundary requires at least three points")
        return self


class GeometryModel(BaseModel):
    grids: list[GridDefinition] = Field(default_factory=list)
    levels: list[LevelDefinition] = Field(default_factory=list)
    points: list[PointDefinition] = Field(default_factory=list)
    lines: list[LineDefinition] = Field(default_factory=list)
    areas: list[AreaDefinition] = Field(default_factory=list)


class ConcreteMaterial(BaseModel):
    id: str
    name: str
    compressive_strength: float
    modulus_of_elasticity: float | None = None
    unit_weight: float | None = None
    poisson_ratio: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SteelMaterial(BaseModel):
    id: str
    name: str
    yield_strength: float
    ultimate_strength: float | None = None
    modulus_of_elasticity: float | None = None
    unit_weight: float | None = None
    poisson_ratio: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReinforcementMaterial(BaseModel):
    id: str
    name: str
    yield_strength: float
    modulus_of_elasticity: float | None = None
    unit_weight: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaterialLibrary(BaseModel):
    concrete: list[ConcreteMaterial] = Field(default_factory=list)
    steel: list[SteelMaterial] = Field(default_factory=list)
    reinforcement: list[ReinforcementMaterial] = Field(default_factory=list)


class BeamSection(BaseModel):
    id: str
    name: str
    width: float
    depth: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class ColumnSection(BaseModel):
    id: str
    name: str
    width: float
    depth: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class WallSection(BaseModel):
    id: str
    name: str
    thickness: float
    length: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SlabSection(BaseModel):
    id: str
    name: str
    thickness: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class FoundationSection(BaseModel):
    id: str
    name: str
    foundation_type: str
    width: float | None = None
    length: float | None = None
    depth: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SectionLibrary(BaseModel):
    beams: list[BeamSection] = Field(default_factory=list)
    columns: list[ColumnSection] = Field(default_factory=list)
    walls: list[WallSection] = Field(default_factory=list)
    slabs: list[SlabSection] = Field(default_factory=list)
    foundations: list[FoundationSection] = Field(default_factory=list)


class StructuralMember(BaseModel):
    id: str
    member_type: MemberType
    name: str
    section_id: str
    material_id: str
    level_id: str | None = None
    start_point_id: str | None = None
    end_point_id: str | None = None
    line_id: str | None = None
    area_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemberLibrary(BaseModel):
    members: list[StructuralMember] = Field(default_factory=list)


class SupportDefinition(BaseModel):
    id: str
    point_id: str
    support_type: SupportType
    restraint_tx: bool = True
    restraint_ty: bool = True
    restraint_tz: bool = True
    restraint_rx: bool = False
    restraint_ry: bool = False
    restraint_rz: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoadDefinition(BaseModel):
    id: str
    name: str
    load_case_id: str
    category: LoadCategory
    distribution: LoadDistribution
    magnitude: float
    direction_x: float = 0.0
    direction_y: float = 0.0
    direction_z: float = -1.0
    unit: str
    point_id: str | None = None
    line_id: str | None = None
    area_id: str | None = None
    member_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoadCase(BaseModel):
    id: str
    name: str
    category: LoadCategory
    description: str | None = None
    code_reference: str | None = None
    loads: list[LoadDefinition] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class LoadCombinationTerm(BaseModel):
    load_case_id: str
    factor: float


class LoadCombination(BaseModel):
    id: str
    name: str
    combination_type: str
    terms: list[LoadCombinationTerm] = Field(default_factory=list)
    code_source: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AnalysisNodeReference(BaseModel):
    id: str
    point_id: str


class AnalysisElementReference(BaseModel):
    id: str
    member_id: str | None = None
    line_id: str | None = None
    start_release: dict[str, bool] = Field(default_factory=dict)
    end_release: dict[str, bool] = Field(default_factory=dict)


class AnalysisModelReference(BaseModel):
    nodes: list[AnalysisNodeReference] = Field(default_factory=list)
    elements: list[AnalysisElementReference] = Field(default_factory=list)
    load_case_ids: list[str] = Field(default_factory=list)
    load_combination_ids: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    capability_status: Literal[
        "NOT_CONFIGURED",
        "PARTIAL",
        "READY_FOR_ANALYSIS_ENGINE",
    ] = "NOT_CONFIGURED"


class DesignParameters(BaseModel):
    material_overrides: dict[str, Any] = Field(default_factory=dict)
    member_design_parameters: dict[str, Any] = Field(default_factory=dict)
    seismic_parameters: dict[str, Any] = Field(default_factory=dict)
    load_parameters: dict[str, Any] = Field(default_factory=dict)
    detailing_parameters: dict[str, Any] = Field(default_factory=dict)
    code_configuration_ref: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class StructuralModel(BaseModel):
    geometry: GeometryModel = Field(default_factory=GeometryModel)
    materials: MaterialLibrary = Field(default_factory=MaterialLibrary)
    sections: SectionLibrary = Field(default_factory=SectionLibrary)
    members: MemberLibrary = Field(default_factory=MemberLibrary)
    supports: list[SupportDefinition] = Field(default_factory=list)
    load_cases: list[LoadCase] = Field(default_factory=list)
    load_combinations: list[LoadCombination] = Field(default_factory=list)
    analysis_model: AnalysisModelReference = Field(default_factory=AnalysisModelReference)
    design_parameters: DesignParameters = Field(default_factory=DesignParameters)


def create_empty_structural_model() -> StructuralModel:
    return StructuralModel()
