"""Tests for CSI PEM vendor model builder."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from app.application.external_model_conversion import build_external_model_export
from app.domain.models.integration import IntegrationSoftware
from app.domain.models.pem import (
    ProjectEngineeringModel,
    ProjectMetadata,
    create_software_default_code_configuration,
    create_us_customary_unit_configuration,
)
from app.domain.models.pem_structural import (
    BeamSection,
    ConcreteMaterial,
    GeometryModel,
    LevelDefinition,
    LineDefinition,
    LoadCase,
    LoadCategory,
    LoadCombination,
    LoadCombinationTerm,
    LoadDefinition,
    LoadDistribution,
    MaterialLibrary,
    MemberLibrary,
    MemberType,
    PointDefinition,
    SectionLibrary,
    StructuralMember,
    StructuralModel,
    SupportDefinition,
    SupportType,
)
from app.infrastructure.integrations.csi_pem_builder import build_vendor_model_from_export


class _FakePropMaterial:
    def __init__(self) -> None:
        self.concrete: list[tuple[Any, ...]] = []

    def SetMaterial(self, name: str, mat_type: int) -> int:
        return 0

    def SetOConcrete_1(self, name: str, fc: float, *args: Any) -> int:
        self.concrete.append((name, fc, args))
        return 0


class _FakePropFrame:
    def __init__(self) -> None:
        self.rectangles: list[tuple[Any, ...]] = []

    def SetRectangle(self, name: str, material: str, depth: float, width: float) -> int:
        self.rectangles.append((name, material, depth, width))
        return 0


class _FakePointObj:
    def __init__(self) -> None:
        self.restraints: dict[str, list[bool]] = {}
        self.points: list[tuple[float, float, float, str]] = []

    def AddCartesian(self, x: float, y: float, z: float, name: str, user_name: str, csys: str):
        self.points.append((x, y, z, name))
        return 0, name

    def SetRestraint(self, point_name: str, restraint: list[bool]) -> int:
        self.restraints[point_name] = restraint
        return 0


class _FakeFrameObj:
    def __init__(self) -> None:
        self.frames: list[tuple[str, str, str]] = []

    def AddByPoint(self, start: str, end: str, name: str, section: str, user_name: str, csys: str):
        self.frames.append((start, end, name, section))
        return 0, name

    def SetLoadDistributed(
        self,
        name: str,
        pattern: str,
        my_type: int,
        direction: int,
        dist1: float,
        dist2: float,
        val1: float,
        val2: float,
    ) -> int:
        return 0


class _FakeLoadPatterns:
    def Add(self, name: str, load_type: int, self_weight: float, add_case: bool) -> int:
        return 0


class _FakeRespCombo:
    def __init__(self) -> None:
        self.cases: list[tuple[str, int, str, float]] = []

    def Add(self, name: str, combo_type: int) -> int:
        return 0

    def SetCaseList(self, combo_name: str, case_type: int, case_name: str, factor: float) -> int:
        self.cases.append((combo_name, case_type, case_name, factor))
        return 0


class _FakeAnalyze:
    def __init__(self) -> None:
        self.flags: list[tuple[str, bool, int]] = []

    def SetRunCaseFlag(self, name: str, run: bool, run_type: int) -> int:
        self.flags.append((name, run, run_type))
        return 0


class _FakeSapModel:
    def __init__(self) -> None:
        self.PropMaterial = _FakePropMaterial()
        self.PropFrame = _FakePropFrame()
        self.PointObj = _FakePointObj()
        self.FrameObj = _FakeFrameObj()
        self.LoadPatterns = _FakeLoadPatterns()
        self.RespCombo = _FakeRespCombo()
        self.Analyze = _FakeAnalyze()


def _sample_pem() -> ProjectEngineeringModel:
    return ProjectEngineeringModel(
        project_id=uuid4(),
        metadata=ProjectMetadata(name="CSI Builder Test"),
        code_configuration=create_software_default_code_configuration(),
        unit_configuration=create_us_customary_unit_configuration(),
        structural_model=_sample_structural(),
    )


def _sample_structural() -> StructuralModel:
    return StructuralModel(
        geometry=GeometryModel(
            levels=[LevelDefinition(id="lvl-1", name="Level 1", elevation=0.0)],
            points=[
                PointDefinition(id="pt-1", x=0.0, y=0.0, z=0.0),
                PointDefinition(id="pt-2", x=20.0, y=0.0, z=0.0),
            ],
            lines=[LineDefinition(id="ln-1", start_point_id="pt-1", end_point_id="pt-2")],
        ),
        materials=MaterialLibrary(
            concrete=[
                ConcreteMaterial(
                    id="mat-conc-1",
                    name="4000 psi Concrete",
                    compressive_strength=4000.0,
                    metadata={"units": {"strength": "psi"}},
                )
            ]
        ),
        sections=SectionLibrary(
            beams=[
                BeamSection(
                    id="sec-b1",
                    name="B1 Section",
                    width=12.0,
                    depth=18.0,
                    metadata={"units": "in"},
                )
            ]
        ),
        members=MemberLibrary(
            members=[
                StructuralMember(
                    id="mbr-1",
                    member_type=MemberType.BEAM,
                    name="B1",
                    section_id="sec-b1",
                    material_id="mat-conc-1",
                    start_point_id="pt-1",
                    end_point_id="pt-2",
                    line_id="ln-1",
                )
            ]
        ),
        supports=[
            SupportDefinition(id="sup-1", point_id="pt-1", support_type=SupportType.FIXED),
        ],
        load_cases=[
            LoadCase(
                id="lc-dead",
                name="Dead Load",
                category=LoadCategory.DEAD,
                loads=[
                    LoadDefinition(
                        id="ld-1",
                        name="Member load",
                        load_case_id="lc-dead",
                        category=LoadCategory.DEAD,
                        distribution=LoadDistribution.MEMBER,
                        magnitude=1.0,
                        unit="kip/ft",
                        member_id="mbr-1",
                    )
                ],
            )
        ],
        load_combinations=[
            LoadCombination(
                id="combo-1",
                name="1.4D",
                combination_type="STRENGTH",
                terms=[LoadCombinationTerm(load_case_id="lc-dead", factor=1.4)],
            )
        ],
    )


def test_build_vendor_model_from_export_completes_with_mock_sap_model() -> None:
    pem = _sample_pem()
    export = build_external_model_export(
        project_id=pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        software=IntegrationSoftware.ETABS,
        software_version="23.0.0",
    )
    sap_model = _FakeSapModel()
    report = build_vendor_model_from_export(sap_model, export)
    assert report["vendor_build_status"] == "COMPLETE"
    assert report["analysis_executed"] is False
    assert report["csi_unit_system"] == 6
    assert [stage["stage"] for stage in report["stages"]] == [
        "materials",
        "sections",
        "geometry",
        "members",
        "areas",
        "supports",
        "load_patterns",
        "load_cases",
        "loads",
        "load_combinations",
        "releases",
        "diaphragms",
        "analysis_settings",
    ]
    assert all(stage["status"] in {"COMPLETE", "SKIPPED_EMPTY"} for stage in report["stages"])
    assert sap_model.RespCombo.cases == [("combo-1", 0, "lc-dead", 1.4)]
    assert sap_model.Analyze.flags == [("lc-dead", True, 0)]
    # 12 in x 18 in converted to metres. Depth is T3.
    _name, material, depth_m, width_m = sap_model.PropFrame.rectangles[0]
    assert material == "mat-conc-1"
    assert abs(width_m - 12.0 * 0.0254) < 1e-9
    assert abs(depth_m - 18.0 * 0.0254) < 1e-9
    # 4000 psi → kN/m². The strength is not passed as the SetMaterial color argument.
    assert abs(sap_model.PropMaterial.concrete[0][1] - 4000.0 * 6.894757293) < 1e-6


def test_build_vendor_model_skips_missing_api_gracefully() -> None:
    pem = _sample_pem()
    export = build_external_model_export(
        project_id=pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        software=IntegrationSoftware.SAP2000,
        software_version="27.0.0",
    )

    class _MinimalSapModel:
        pass

    report = build_vendor_model_from_export(_MinimalSapModel(), export)
    assert report["vendor_build_status"] in {"PARTIAL", "FAILED"}
    assert report["analysis_executed"] is False
    assert any(stage["status"] == "SKIPPED" for stage in report["stages"])


def test_missing_strength_unit_fails_the_material_stage() -> None:
    pem = _sample_pem()
    pem.structural_model.materials.concrete[0].metadata = {}
    export = build_external_model_export(
        project_id=pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        software=IntegrationSoftware.ETABS,
        software_version="23.0.0",
    )
    report = build_vendor_model_from_export(_FakeSapModel(), export)
    material_stage = next(stage for stage in report["stages"] if stage["stage"] == "materials")
    assert material_stage["status"] == "FAILED"
    assert "strength unit" in material_stage["detail"]
    assert report["vendor_build_status"] != "COMPLETE"
    assert report["analysis_executed"] is False


def test_si_section_metres_are_not_converted_as_inches() -> None:
    pem = _sample_pem()
    pem.unit_configuration.length_unit = "m"
    pem.unit_configuration.force_unit = "kN"
    pem.unit_configuration.stress_unit = "MPa"
    pem.structural_model.materials.concrete[0].compressive_strength = 30.0
    pem.structural_model.materials.concrete[0].metadata = {"units": {"strength": "MPa"}}
    pem.structural_model.sections.beams[0].width = 0.3
    pem.structural_model.sections.beams[0].depth = 0.5
    pem.structural_model.sections.beams[0].metadata = {"units": "m"}
    pem.structural_model.geometry.points[1].x = 6.0
    export = build_external_model_export(
        project_id=pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        software=IntegrationSoftware.ETABS,
        software_version="23.0.0",
    )
    sap_model = _FakeSapModel()
    report = build_vendor_model_from_export(sap_model, export)
    assert report["vendor_build_status"] == "COMPLETE"
    _name, _material, depth_m, width_m = sap_model.PropFrame.rectangles[0]
    assert abs(width_m - 0.3) < 1e-9
    assert abs(depth_m - 0.5) < 1e-9
    assert abs(sap_model.PointObj.points[1][0] - 6.0) < 1e-9


def test_nonzero_vendor_code_fails_the_stage() -> None:
    pem = _sample_pem()
    export = build_external_model_export(
        project_id=pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        software=IntegrationSoftware.ETABS,
        software_version="23.0.0",
    )

    class _RejectingPoints(_FakeSapModel):
        def __init__(self) -> None:
            super().__init__()

            def _reject(*_args: Any) -> int:
                return 7

            self.PointObj.SetRestraint = _reject  # type: ignore[method-assign]

    report = build_vendor_model_from_export(_RejectingPoints(), export)
    support_stage = next(stage for stage in report["stages"] if stage["stage"] == "supports")
    assert support_stage["status"] == "FAILED"
    assert "vendor code 7" in support_stage["detail"]
    assert report["vendor_build_status"] != "COMPLETE"
