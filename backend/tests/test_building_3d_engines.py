"""Deterministic 3D / wind / seismic / drift / foundation / rebar tests."""

from __future__ import annotations

from app.application.engineering_report_service import EngineeringReportService
from app.application.load_combination_engine import LoadCombinationEngine
from app.application.reinforcement_selection import ReinforcementSelectionEngine
from app.application.seismic_elf_engine import SeismicElfEngine, SeismicEngineInputs
from app.application.wind_load_engine import WindEngineInputs, WindLoadEngine
from app.domain.models.pem_architecture import BuildingModel, SiteDefinition, Polygon2D, Point2D
from app.domain.models.pem_structural import (
    InputOrigin,
    LevelDefinition,
    LoadCase,
    LoadCategory,
    StoryMass,
    StructuralModel,
)


def _tiny_building() -> tuple[BuildingModel, StructuralModel]:
    site = SiteDefinition(
        id="SITE",
        name="Plot",
        frontage_m=12.0,
        depth_m=22.0,
        boundary=Polygon2D(points=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=22), Point2D(x=0, y=22)]),
    )
    building = BuildingModel(site=site)
    structural = StructuralModel()
    structural.geometry.levels = [
        LevelDefinition(id="L0", name="Base", elevation=0.0, sort_order=0),
        LevelDefinition(id="L1", name="Level 1", elevation=3.2, sort_order=1),
        LevelDefinition(id="L2", name="Level 2", elevation=6.4, sort_order=2),
        LevelDefinition(id="L3", name="Roof", elevation=9.6, sort_order=3),
    ]
    return building, structural


def test_wind_engine_emits_four_directional_cases() -> None:
    building, structural = _tiny_building()
    result = WindLoadEngine().generate(building, structural, inputs=WindEngineInputs())
    names = {case.name for case in result.load_cases}
    assert names == {"WIND_X+", "WIND_X-", "WIND_Y+", "WIND_Y-"}
    assert result.qh_kN_m2 > 0
    assert result.story_forces
    assert all(item.origin is not InputOrigin.USER_PROVIDED for item in result.provenance if item.field == "basic_wind_speed")
    assert "NOT" in result.warnings[0] or "not" in result.warnings[0].lower() or "simplified" in result.warnings[0].lower()


def test_seismic_elf_uses_assumed_site_parameters() -> None:
    building, structural = _tiny_building()
    masses = [
        StoryMass(level_id="L1", dead_weight_kN=800.0, seismic_weight_kN=800.0, mass_kg=80000.0),
        StoryMass(level_id="L2", dead_weight_kN=800.0, seismic_weight_kN=800.0, mass_kg=80000.0),
        StoryMass(level_id="L3", dead_weight_kN=600.0, seismic_weight_kN=600.0, mass_kg=60000.0),
    ]
    result = SeismicElfEngine().generate(
        building,
        structural,
        masses,
        inputs=SeismicEngineInputs(ss_origin=InputOrigin.ASSUMED, s1_origin=InputOrigin.ASSUMED),
    )
    assert result.cs > 0
    assert result.base_shear_kN > 0
    assert abs(result.base_shear_kN - result.cs * 2200.0) < 1.0
    assert {case.name for case in result.load_cases} == {"EQ_X+", "EQ_X-", "EQ_Y+", "EQ_Y-"}
    ss = next(item for item in result.provenance if item.field == "Ss")
    assert ss.origin is InputOrigin.ASSUMED
    assert result.seismic_design_category in {"A", "B", "C", "D"}


def test_combinations_expand_directional_wind_and_eq() -> None:
    cases = [
        LoadCase(id="LC-DEAD", name="DEAD", category=LoadCategory.DEAD),
        LoadCase(id="LC-LIVE", name="LIVE", category=LoadCategory.LIVE),
        LoadCase(id="LC-ROOF", name="ROOF", category=LoadCategory.ROOF),
        LoadCase(id="LC-WIND_X+", name="WIND_X+", category=LoadCategory.WIND),
        LoadCase(id="LC-WIND_Y+", name="WIND_Y+", category=LoadCategory.WIND),
        LoadCase(id="LC-EQ_X+", name="EQ_X+", category=LoadCategory.SEISMIC),
        LoadCase(id="LC-EQ_Y+", name="EQ_Y+", category=LoadCategory.SEISMIC),
    ]
    result = LoadCombinationEngine().generate(cases)
    names = {item.name for item in result.combinations}
    assert "1.2D + 1.6L + 0.5Lr" in names
    assert any("WIND_X+" in name for name in names)
    assert any("EQ_Y+" in name for name in names)
    gravity = LoadCombinationEngine.governing_gravity_combination(result.combinations)
    assert gravity is not None
    assert gravity.metadata.get("governing_gravity") is True


def test_reinforcement_selects_bars_meeting_required_area() -> None:
    selection = ReinforcementSelectionEngine().select_longitudinal(800.0, width_mm=300.0, depth_mm=500.0)
    assert selection.provided_mm2 + 1e-6 >= 800.0
    assert selection.bars.count >= 2
    stirrups = ReinforcementSelectionEngine().select_stirrups(
        vs_needed_kn=80.0, width_mm=300.0, d_mm=450.0, fy_mpa=400.0
    )
    assert 75.0 <= stirrups.spacing_mm <= 300.0


def test_engineering_report_separates_implementation_status() -> None:
    from app.domain.models.pem import create_initial_pem
    from uuid import UUID

    pem = create_initial_pem(UUID(int=1), "Report demo")
    pem.code_compliance = {"ACI 318-25": "PARTIAL_IMPLEMENTATION"}
    report = EngineeringReportService().generate(pem)
    assert "qualified engineer" in report["disclaimer"]
    assert report["classification"]["REQUIRES_ENGINEER_REVIEW"] is True
    assert "NOT_CHECKED" in report["classification"]
    assert report["code_compliance"]["ACI 318-25"] == "PARTIAL_IMPLEMENTATION"
