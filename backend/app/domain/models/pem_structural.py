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
    ROOF = "ROOF"
    PARTITION = "PARTITION"
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


class DesignCheckStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    NOT_CHECKED = "NOT_CHECKED"


class InputOrigin(StrEnum):
    USER_PROVIDED = "USER_PROVIDED"
    DEFAULT = "DEFAULT"
    ASSUMED = "ASSUMED"
    CALCULATED = "CALCULATED"
    EXTERNAL_REQUIRED = "EXTERNAL_REQUIRED"


class DiaphragmKind(StrEnum):
    RIGID = "RIGID"
    SEMI_RIGID = "SEMI_RIGID"
    FLEXIBLE = "FLEXIBLE"


class InputProvenance(BaseModel):
    field: str
    value: str
    origin: InputOrigin
    note: str = ""
    unit: str | None = None


class DiaphragmDefinition(BaseModel):
    id: str
    level_id: str
    kind: DiaphragmKind = DiaphragmKind.RIGID
    center_of_mass_x: float = 0.0
    center_of_mass_y: float = 0.0
    center_of_rigidity_x: float | None = None
    center_of_rigidity_y: float | None = None
    mass_kg: float = 0.0
    weight_kN: float = 0.0
    node_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoryMass(BaseModel):
    level_id: str
    dead_weight_kN: float = 0.0
    live_weight_kN: float = 0.0
    seismic_weight_kN: float = 0.0
    mass_kg: float = 0.0
    assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoryForce(BaseModel):
    level_id: str
    case_id: str
    fx_kN: float = 0.0
    fy_kN: float = 0.0
    mz_kNm: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class StoryDriftRecord(BaseModel):
    level_id: str
    story_name: str
    height_m: float
    displacement_x_m: float = 0.0
    displacement_y_m: float = 0.0
    drift_x_m: float = 0.0
    drift_y_m: float = 0.0
    drift_ratio_x: float = 0.0
    drift_ratio_y: float = 0.0
    limit: float | None = None
    status: DesignCheckStatus = DesignCheckStatus.NOT_CHECKED
    code_reference: str = ""
    assumptions: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ReinforcementBarSet(BaseModel):
    """A group of identical bars. Areas are millimetres squared."""

    designation: str
    diameter_mm: float
    count: int = 1
    area_each_mm2: float
    spacing_mm: float | None = None
    layer: str = "LONGITUDINAL"
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def total_area_mm2(self) -> float:
        return self.count * self.area_each_mm2


class StirrupLayout(BaseModel):
    designation: str
    diameter_mm: float
    legs: int = 2
    spacing_mm: float
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemberReinforcement(BaseModel):
    """Structured reinforcement assigned to one structural member."""

    member_id: str
    longitudinal: list[ReinforcementBarSet] = Field(default_factory=list)
    stirrups: StirrupLayout | None = None
    slab_bottom: list[ReinforcementBarSet] = Field(default_factory=list)
    slab_top: list[ReinforcementBarSet] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    status: DesignCheckStatus = DesignCheckStatus.WARNING
    metadata: dict[str, Any] = Field(default_factory=dict)


class MemberDesignCheck(BaseModel):
    member_id: str
    member_name: str
    check_kind: str
    governing_combination: str
    demand: float
    capacity: float
    utilization: float
    demand_unit: str
    code_reference: str
    assumptions: list[str] = Field(default_factory=list)
    status: DesignCheckStatus
    metadata: dict[str, Any] = Field(default_factory=dict)


class FoundationFooting(BaseModel):
    id: str
    column_member_id: str
    point_id: str
    length_m: float
    width_m: float
    thickness_m: float
    axial_kN: float = 0.0
    moment_x_kNm: float = 0.0
    moment_y_kNm: float = 0.0
    bearing_demand_kPa: float = 0.0
    bearing_capacity_kPa: float = 0.0
    utilization: float = 0.0
    status: DesignCheckStatus = DesignCheckStatus.NOT_CHECKED
    assumptions: list[str] = Field(default_factory=list)
    checks: list[MemberDesignCheck] = Field(default_factory=list)
    reinforcement: MemberReinforcement | None = None
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
    reinforcement: list[MemberReinforcement] = Field(default_factory=list)
    design_checks: list[MemberDesignCheck] = Field(default_factory=list)
    diaphragms: list[DiaphragmDefinition] = Field(default_factory=list)
    story_masses: list[StoryMass] = Field(default_factory=list)
    story_forces: list[StoryForce] = Field(default_factory=list)
    story_drifts: list[StoryDriftRecord] = Field(default_factory=list)
    footings: list[FoundationFooting] = Field(default_factory=list)
    input_provenance: list[InputProvenance] = Field(default_factory=list)
    irregularity_checks: list[MemberDesignCheck] = Field(default_factory=list)


def create_empty_structural_model() -> StructuralModel:
    return StructuralModel()
