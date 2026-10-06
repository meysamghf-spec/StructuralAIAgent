"""Mass, footing, coordination and irregularity unit tests."""

from __future__ import annotations

from uuid import UUID

from app.application.building_analysis_service import BuildingAnalysisResult
from app.application.coordination_service import CoordinationService
from app.application.foundation_design_service import FoundationDesignService
from app.application.irregularity_qa_service import IrregularityQAService
from app.application.mass_model_service import MassModelService
from app.domain.models.pem import create_initial_pem
from app.domain.models.pem_architecture import (
    BuildingModel,
    FloorPlanDefinition,
    FloorType,
    Point2D,
    Polygon2D,
    SiteDefinition,
    SpaceDefinition,
    SpaceUsage,
)
from app.domain.models.pem_structural import (
    ColumnSection,
    ConcreteMaterial,
    DesignCheckStatus,
    LevelDefinition,
    LoadCase,
    LoadCategory,
    LoadDefinition,
    LoadDistribution,
    MemberType,
    PointDefinition,
    ReinforcementMaterial,
    StoryDriftRecord,
    StoryMass,
    StructuralMember,
    SupportDefinition,
    SupportType,
)


def test_mass_model_uses_zero_live_factor_for_residential() -> None:
    pem = create_initial_pem(UUID(int=2), "mass")
    pem.structural_model.geometry.levels = [LevelDefinition(id="L1", name="L1", elevation=3.2)]
    pem.structural_model.members.members.append(
        StructuralMember(
            id="SLAB-L1-Z01",
            member_type=MemberType.SLAB,
            name="S1",
            section_id="SLAB",
            material_id="C",
            level_id="L1",
            area_id="A1",
        )
    )
    pem.structural_model.load_cases = [
        LoadCase(
            id="LC-DEAD",
            name="DEAD",
            category=LoadCategory.DEAD,
            loads=[
                LoadDefinition(
                    id="LD1",
                    name="d",
                    load_case_id="LC-DEAD",
                    category=LoadCategory.DEAD,
                    distribution=LoadDistribution.AREA,
                    magnitude=4.0,
                    unit="kN/m2",
                    area_id="A1",
                    member_id="SLAB-L1-Z01",
                    metadata={"area_m2": 50.0, "resultant_kN": 200.0, "level_id": "L1"},
                )
            ],
        ),
        LoadCase(
            id="LC-LIVE",
            name="LIVE",
            category=LoadCategory.LIVE,
            loads=[
                LoadDefinition(
                    id="LD2",
                    name="l",
                    load_case_id="LC-LIVE",
                    category=LoadCategory.LIVE,
                    distribution=LoadDistribution.AREA,
                    magnitude=1.92,
                    unit="kN/m2",
                    area_id="A1",
                    member_id="SLAB-L1-Z01",
                    metadata={"area_m2": 50.0, "resultant_kN": 96.0, "level_id": "L1"},
                )
            ],
        ),
    ]
    result = MassModelService().generate(pem.structural_model)
    storey = next(item for item in result.story_masses if item.level_id == "L1")
    assert abs(storey.dead_weight_kN - 200.0) < 1e-6
    assert abs(storey.live_weight_kN - 96.0) < 1e-6
    assert abs(storey.seismic_weight_kN - 200.0) < 1e-6
    assert result.live_mass_factor == 0.0


def test_isolated_footing_uses_assumed_bearing() -> None:
    pem = create_initial_pem(UUID(int=3), "footing")
    pem.structural_model.materials.concrete.append(
        ConcreteMaterial(id="C", name="C25", compressive_strength=25.0, unit_weight=25.0)
    )
    pem.structural_model.materials.reinforcement.append(
        ReinforcementMaterial(id="R", name="S400", yield_strength=400.0)
    )
    pem.structural_model.sections.columns.append(ColumnSection(id="C1", name="C400", width=0.4, depth=0.4))
    pem.structural_model.geometry.points.append(PointDefinition(id="PT", x=0.0, y=0.0, z=0.0, level_id="L0"))
    pem.structural_model.members.members.append(
        StructuralMember(
            id="COL-L0-A1",
            member_type=MemberType.COLUMN,
            name="C",
            section_id="C1",
            material_id="C",
            start_point_id="PT",
            end_point_id="PT",
        )
    )
    pem.structural_model.supports.append(
        SupportDefinition(id="SUP", point_id="PT", support_type=SupportType.FIXED)
    )
    analysis = BuildingAnalysisResult(status="SUCCESS", message="ok", reactions_kN={"PT": 400.0})
    result = FoundationDesignService().design(pem, analysis)
    assert result.footings
    assert result.footings[0].width_m >= 0.8
    assert any(item.origin.value == "ASSUMED" for item in result.provenance)
    assert any("PRELIMINARY_ASSUMPTION" in item.note for item in result.provenance)


def test_irregularity_weak_storey_is_not_checked() -> None:
    pem = create_initial_pem(UUID(int=4), "irr")
    pem.building_model = BuildingModel(
        site=SiteDefinition(
            frontage_m=12,
            depth_m=22,
            boundary=Polygon2D(
                points=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=22), Point2D(x=0, y=22)]
            ),
        )
    )
    pem.structural_model.story_masses = [
        StoryMass(level_id="L1", mass_kg=10000),
        StoryMass(level_id="L2", mass_kg=10000),
    ]
    result = IrregularityQAService().evaluate(pem.building_model, pem.structural_model)
    weak = next(item for item in result.checks if item.check_kind == "IRREGULARITY_WEAK_STORY")
    assert weak.status is DesignCheckStatus.NOT_CHECKED
    torsion = next(item for item in result.checks if item.check_kind == "IRREGULARITY_TORSION")
    assert torsion.status is DesignCheckStatus.NOT_CHECKED


def test_coordination_flags_column_in_stair_as_hard_conflict() -> None:
    pem = create_initial_pem(UUID(int=5), "coord")
    stair = SpaceDefinition(
        id="ST",
        name="Stair",
        usage=SpaceUsage.STAIR,
        boundary=Polygon2D(points=[Point2D(x=0, y=0), Point2D(x=3, y=0), Point2D(x=3, y=3), Point2D(x=0, y=3)]),
        level_id="L1",
    )
    pem.building_model.floor_plans.append(
        FloorPlanDefinition(
            id="F1",
            name="L1",
            level_id="L1",
            floor_type=FloorType.RESIDENTIAL,
            elevation_m=3.2,
            storey_height_m=3.2,
            boundary=Polygon2D(
                points=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=22), Point2D(x=0, y=22)]
            ),
            spaces=[stair],
        )
    )
    pem.structural_model.geometry.points.append(PointDefinition(id="P", x=1.5, y=1.5, z=0.0, level_id="L1"))
    pem.structural_model.members.members.append(
        StructuralMember(
            id="COL-1",
            member_type=MemberType.COLUMN,
            name="C",
            section_id="C1",
            material_id="C",
            start_point_id="P",
            end_point_id="P",
        )
    )
    result = CoordinationService().check(pem.building_model, pem.structural_model)
    assert result.hard_count >= 1
    assert any(item.code == "COLUMN_IN_CORE" for item in result.conflicts)


def test_coordination_treats_stair_wall_column_as_warning_not_hard() -> None:
    pem = create_initial_pem(UUID(int=6), "coord-wall")
    stair = SpaceDefinition(
        id="ST",
        name="Stair",
        usage=SpaceUsage.STAIR,
        boundary=Polygon2D(points=[Point2D(x=4.7, y=17.4), Point2D(x=7.3, y=17.4), Point2D(x=7.3, y=22.0), Point2D(x=4.7, y=22.0)]),
        level_id="L0",
    )
    pem.building_model.floor_plans.append(
        FloorPlanDefinition(
            id="F0",
            name="L0",
            level_id="L0",
            floor_type=FloorType.PILOTI,
            elevation_m=0.0,
            storey_height_m=3.0,
            boundary=Polygon2D(
                points=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=22), Point2D(x=0, y=22)]
            ),
            spaces=[stair],
        )
    )
    pem.structural_model.sections.columns.append(ColumnSection(id="C1", name="C400", width=0.4, depth=0.4))
    pem.structural_model.geometry.points.append(PointDefinition(id="P", x=5.0, y=17.4, z=0.0, level_id="L0"))
    pem.structural_model.members.members.append(
        StructuralMember(
            id="COL-L0-C5",
            member_type=MemberType.COLUMN,
            name="C5",
            section_id="C1",
            material_id="C",
            level_id="L0",
            start_point_id="P",
            end_point_id="P",
        )
    )
    result = CoordinationService().check(pem.building_model, pem.structural_model)
    assert result.hard_count == 0
    assert not any(item.code == "COLUMN_IN_CORE" for item in result.conflicts)
    assert any(item.code == "COLUMN_ON_CORE_WALL" for item in result.conflicts)


def test_mass_discontinuity_skips_foundation_level() -> None:
    check = IrregularityQAService._mass_discontinuity(
        [
            StoryMass(level_id="L0", mass_kg=432.0, seismic_weight_kN=4.2, live_weight_kN=0.0),
            StoryMass(level_id="L1", mass_kg=2847.0, seismic_weight_kN=27.9, live_weight_kN=96.0),
            StoryMass(level_id="L2", mass_kg=2847.0, seismic_weight_kN=27.9, live_weight_kN=96.0),
            StoryMass(level_id="L3", mass_kg=1887.0, seismic_weight_kN=18.5, live_weight_kN=0.0),
        ]
    )
    assert check.status is DesignCheckStatus.PASS
    assert check.demand <= 1.5


def test_soft_story_does_not_fail_from_smaller_roof_drift() -> None:
    drifts = [
        StoryDriftRecord(level_id="L0", story_name="base", height_m=3.0, drift_ratio_x=0.0, drift_ratio_y=0.0),
        StoryDriftRecord(level_id="L1", story_name="L1", height_m=3.0, drift_ratio_x=0.002, drift_ratio_y=0.002),
        StoryDriftRecord(level_id="L2", story_name="L2", height_m=3.0, drift_ratio_x=0.002, drift_ratio_y=0.002),
        StoryDriftRecord(level_id="L3", story_name="L3", height_m=3.0, drift_ratio_x=0.002, drift_ratio_y=0.002),
        StoryDriftRecord(level_id="L4", story_name="roof", height_m=3.0, drift_ratio_x=0.001, drift_ratio_y=0.001),
    ]
    check = IrregularityQAService._soft_story(drifts)
    assert check.status is not DesignCheckStatus.FAIL
