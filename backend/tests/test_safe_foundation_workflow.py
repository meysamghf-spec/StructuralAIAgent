"""SAFE foundation inputs are explicit. Preliminary footing reactions are not SAFE loads."""

from __future__ import annotations

from uuid import uuid4

from app.application.safe_foundation_workflow import assess_safe_foundation_inputs
from app.domain.models.integration import IntegrationSoftware
from app.domain.models.pem import ProjectEngineeringModel, ProjectMetadata, create_software_default_code_configuration
from app.domain.models.pem import create_us_customary_unit_configuration
from app.domain.models.pem_structural import (
    ConcreteMaterial,
    FoundationSection,
    GeometryModel,
    LoadCase,
    LoadCategory,
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
from app.infrastructure.integrations.safe_foundation_builder import build_safe_foundation_model


def _pem() -> ProjectEngineeringModel:
    return ProjectEngineeringModel(
        project_id=uuid4(),
        metadata=ProjectMetadata(name="SAFE footing"),
        code_configuration=create_software_default_code_configuration(),
        unit_configuration=create_us_customary_unit_configuration(),
        structural_model=StructuralModel(
            geometry=GeometryModel(
                points=[PointDefinition(id="pt-1", x=1.0, y=2.0, z=0.0)]
            ),
            materials=MaterialLibrary(
                concrete=[
                    ConcreteMaterial(
                        id="conc",
                        name="C25",
                        compressive_strength=25.0,
                        metadata={"units": {"strength": "MPa"}},
                    )
                ]
            ),
            sections=SectionLibrary(
                foundations=[
                    FoundationSection(
                        id="fnd-1",
                        name="F1",
                        foundation_type="spread footing",
                        width=1.5,
                        length=1.5,
                        depth=0.45,
                        metadata={"point_id": "pt-1", "column_member_id": "col-1"},
                    )
                ]
            ),
            members=MemberLibrary(
                members=[
                    StructuralMember(
                        id="col-1",
                        member_type=MemberType.COLUMN,
                        name="C1",
                        section_id="col-sec",
                        material_id="conc",
                        start_point_id="pt-1",
                        end_point_id="pt-1",
                    )
                ]
            ),
            supports=[SupportDefinition(id="sup-1", point_id="pt-1", support_type=SupportType.PINNED)],
            load_cases=[
                LoadCase(
                    id="lc-dead",
                    name="Dead",
                    category=LoadCategory.DEAD,
                    loads=[
                        LoadDefinition(
                            id="ld-1",
                            name="Column",
                            load_case_id="lc-dead",
                            category=LoadCategory.DEAD,
                            distribution=LoadDistribution.POINT,
                            magnitude=100.0,
                            unit="kN",
                            point_id="pt-1",
                            direction_z=-1.0,
                        )
                    ],
                )
            ],
        ),
    )


def test_missing_soil_and_loads_stop_before_safe() -> None:
    pem = _pem()
    pem.structural_model.load_cases = []
    assessment = assess_safe_foundation_inputs(pem)
    assert assessment["ready"] is False
    assert any("subgrade_modulus_kN_m3" in item for item in assessment["missing"])
    assert any("load case" in item for item in assessment["missing"])
    report = build_safe_foundation_model(object(), assessment["spec"])
    assert report["vendor_build_status"] == "FAILED"
    assert report["failure_class"] == "MISSING_INPUTS"
    assert report["analysis_executed"] is False
    assert report["result_authority"] == "NONE"


def test_unlabeled_subgrade_is_not_sent() -> None:
    pem = _pem()
    pem.structural_model.design_parameters.load_parameters = {"subgrade_modulus_kN_m3": 15000}
    assessment = assess_safe_foundation_inputs(pem)
    assert assessment["ready"] is False
    assert any("origin is not USER_PROVIDED" in item for item in assessment["missing"])


def test_ready_spec_maps_user_soil_and_column_load_without_inventing_results() -> None:
    pem = _pem()
    pem.structural_model.design_parameters.load_parameters = {
        "subgrade_modulus_kN_m3": 20000,
        "subgrade_modulus_origin": "USER_PROVIDED",
    }
    assessment = assess_safe_foundation_inputs(pem)
    assert assessment["ready"] is True
    assert assessment["spec"]["subgrade_modulus_kN_m3"] == 20000

    class _PropMaterial:
        def SetMaterial(self, name: str, mat_type: int) -> int:
            return 0

        def SetOConcrete_1(self, *args: object) -> int:
            return 0

    class _PropArea:
        def __init__(self) -> None:
            self.slabs: list[tuple[object, ...]] = []

        def SetSlab(self, *args: object) -> int:
            self.slabs.append(args)
            return 0

    class _Point:
        def __init__(self) -> None:
            self.springs: list[tuple[str, list[float]]] = []
            self.forces: list[tuple[str, list[float]]] = []

        def AddCartesian(self, x: float, y: float, z: float, name: str, user: str, csys: str):
            return 0, name

        def SetSpring(self, name: str, stiffness: list[float]) -> int:
            self.springs.append((name, stiffness))
            return 0

        def SetRestraint(self, name: str, restraint: list[bool]) -> int:
            assert restraint[2] is False
            return 0

        def SetLoadForce(self, name: str, pattern: str, vector: list[float]) -> int:
            self.forces.append((name, vector))
            return 0

    class _Area:
        def AddByPoint(self, count: int, points: list[str], name: str, prop: str) -> int:
            assert count == 4
            return 0

    class _Patterns:
        def Add(self, name: str, load_type: int, self_weight: float, add_case: bool) -> int:
            assert self_weight == 0.0
            return 0

    class _Combo:
        def Add(self, name: str, combo_type: int) -> int:
            return 0

        def SetCaseList(self, name: str, case_type: int, case_name: str, factor: float) -> int:
            return 0

    class _Analyze:
        def SetRunCaseFlag(self, name: str, run: bool, run_type: int) -> int:
            return 0

    class _Sap:
        def __init__(self) -> None:
            self.PropMaterial = _PropMaterial()
            self.PropArea = _PropArea()
            self.PointObj = _Point()
            self.AreaObj = _Area()
            self.LoadPatterns = _Patterns()
            self.RespCombo = _Combo()
            self.Analyze = _Analyze()

    sap = _Sap()
    report = build_safe_foundation_model(sap, assessment["spec"])
    assert report["vendor_build_status"] == "COMPLETE"
    assert report["analysis_executed"] is False
    assert report["result_authority"] == "SAFE"
    assert sap.PropArea.slabs[0][1] == 6
    # 100 kN downward is split across four corners, preserving the total.
    vertical = [item[1][2] for item in sap.PointObj.forces]
    assert len(vertical) == 4
    assert abs(sum(vertical) - (-100.0)) < 1e-9
    assert abs(sap.PointObj.springs[0][1][2] - 20000.0 * 1.5 * 1.5 / 4.0) < 1e-6
    assert IntegrationSoftware.SAFE.value == "SAFE"


def test_nonzero_safe_api_code_fails_the_build() -> None:
    pem = _pem()
    pem.structural_model.design_parameters.load_parameters = {
        "subgrade_modulus_kN_m3": 10000,
        "subgrade_modulus_origin": "USER_PROVIDED",
    }
    assessment = assess_safe_foundation_inputs(pem)

    class _PropMaterial:
        def SetMaterial(self, name: str, mat_type: int) -> int:
            return 4

        def SetOConcrete_1(self, *args: object) -> int:
            return 0

    class _Sap:
        PropMaterial = _PropMaterial()

    report = build_safe_foundation_model(_Sap(), assessment["spec"])
    assert report["vendor_build_status"] == "FAILED"
    assert report["failure_class"] == "MODEL_BUILD_FAILURE"
    assert "vendor code 4" in report["stages"][0]["detail"]
