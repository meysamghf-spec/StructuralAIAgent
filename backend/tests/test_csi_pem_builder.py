"""Tests for CSI PEM vendor model builder."""

from __future__ import annotations

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
    def SetMaterial(self, name: str, mat_type: int, grade: float) -> int:
        return 0


class _FakePropFrame:
    def SetRectangle(self, name: str, material: str, height: float, width: float) -> int:
        return 0


class _FakePointObj:
    def __init__(self) -> None:
        self.restraints: dict[str, list[bool]] = {}

    def AddCartesian(self, x: float, y: float, z: float, name: str, user_name: str, csys: str):
        return 0, name

    def SetRestraint(self, point_name: str, restraint: list[bool]) -> int:
        self.restraints[point_name] = restraint
        return 0


class _FakeFrameObj:
    def __init__(self) -> None:
        self.frames: list[tuple[str, str, str]] = []

    def AddByPoint(self, start: str, end: str, name: str, section: str, rotation: float):
        self.frames.append((start, end, name))
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
    def Add(self, name: str, combo_type: int) -> int:
        return 0

    def SetCaseList(self, combo_name: str, index: int, case_name: str, factor: float) -> int:
        return 0


class _FakeSapModel:
    def __init__(self) -> None:
        self.PropMaterial = _FakePropMaterial()
        self.PropFrame = _FakePropFrame()
        self.PointObj = _FakePointObj()
        self.FrameObj = _FakeFrameObj()
        self.LoadPatterns = _FakeLoadPatterns()
        self.RespCombo = _FakeRespCombo()


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
                )
            ]
        ),
        sections=SectionLibrary(
            beams=[BeamSection(id="sec-b1", name="B1 Section", width=12.0, depth=18.0)]
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
                        unit="kip",
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
    report = build_vendor_model_from_export(_FakeSapModel(), export)
    assert report["vendor_build_status"] == "COMPLETE"
    assert len(report["stages"]) == 8
    assert all(stage["status"] == "COMPLETE" for stage in report["stages"])


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
    assert any(stage["status"] == "SKIPPED" for stage in report["stages"])
