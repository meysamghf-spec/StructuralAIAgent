"""Domain tests — PEM structural validation."""

from uuid import uuid4

from app.domain.models.pem import create_initial_pem
from app.domain.models.pem_structural import (
    AreaDefinition,
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
    PointDefinition,
    StructuralMember,
    MemberLibrary,
    MemberType,
    SupportDefinition,
    SupportType,
)
from app.domain.models.validation import ValidationStatus
from app.domain.pem_validation import validate_structural_model
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _pem_with(**updates):
    pem = create_initial_pem(uuid4(), "Validation Project")
    structural = pem.structural_model.model_copy(update=updates)
    return pem.model_copy(update={"structural_model": structural})


def test_empty_structural_model_passes_validation() -> None:
    pem = create_initial_pem(uuid4(), "Empty")
    findings = validate_structural_model(pem)
    assert not any(f.status == ValidationStatus.ERROR for f in findings)


def test_valid_sample_model_passes_validation() -> None:
    pem = _pem_with(
        geometry=sample_geometry(),
        materials=sample_materials(),
        sections=sample_sections(),
        members=sample_members(),
        supports=sample_supports(),
        load_cases=sample_load_cases(),
        load_combinations=sample_load_combinations(),
    )
    findings = validate_structural_model(pem)
    assert not any(f.status == ValidationStatus.ERROR for f in findings)


def test_duplicate_point_ids_detected() -> None:
    geometry = GeometryModel(
        points=[
            PointDefinition(id="pt-dup", x=0, y=0, z=0),
            PointDefinition(id="pt-dup", x=1, y=1, z=0),
        ]
    )
    findings = validate_structural_model(_pem_with(geometry=geometry))
    assert any(f.code == "DUPLICATE_POINT_ID" for f in findings)


def test_invalid_line_point_reference_detected() -> None:
    geometry = GeometryModel(
        lines=[LineDefinition(id="ln-bad", start_point_id="missing-a", end_point_id="missing-b")]
    )
    findings = validate_structural_model(_pem_with(geometry=geometry))
    assert any(f.code == "INVALID_LINE_POINT_REFERENCE" for f in findings)


def test_invalid_area_boundary_detected() -> None:
    geometry = GeometryModel(
        points=[
            PointDefinition(id="pt-1", x=0, y=0, z=0),
            PointDefinition(id="pt-2", x=1, y=0, z=0),
            PointDefinition(id="pt-3", x=0, y=1, z=0),
        ],
        areas=[
            AreaDefinition(
                id="area-1",
                boundary_point_ids=["pt-1", "pt-2", "pt-missing"],
                level_id=None,
            )
        ],
    )
    findings = validate_structural_model(_pem_with(geometry=geometry))
    assert any(f.code == "INVALID_AREA_BOUNDARY" for f in findings)


def test_invalid_concrete_strength_detected() -> None:
    from app.domain.models.pem_structural import MaterialLibrary

    materials = MaterialLibrary(
        concrete=[
            ConcreteMaterial(id="mat-bad", name="Bad", compressive_strength=0.0),
        ]
    )
    findings = validate_structural_model(_pem_with(materials=materials))
    assert any(f.code == "INVALID_CONCRETE_STRENGTH" for f in findings)


def test_member_missing_section_detected() -> None:
    members = MemberLibrary(
        members=[
            StructuralMember(
                id="mbr-bad",
                member_type=MemberType.BEAM,
                name="B?",
                section_id="missing-sec",
                material_id="mat-conc-1",
            )
        ]
    )
    pem = _pem_with(materials=sample_materials(), members=members)
    findings = validate_structural_model(pem)
    assert any(f.code == "MISSING_MEMBER_SECTION" for f in findings)


def test_support_missing_point_detected() -> None:
    supports = [
        SupportDefinition(id="sup-bad", point_id="pt-missing", support_type=SupportType.PINNED)
    ]
    findings = validate_structural_model(_pem_with(supports=supports))
    assert any(f.code == "INVALID_SUPPORT_POINT" for f in findings)


def test_load_case_mismatch_detected() -> None:
    load_cases = [
        LoadCase(
            id="lc-1",
            name="Dead",
            category=LoadCategory.DEAD,
            loads=[
                LoadDefinition(
                    id="ld-1",
                    name="Load",
                    load_case_id="other-case",
                    category=LoadCategory.DEAD,
                    distribution=LoadDistribution.POINT,
                    magnitude=10.0,
                    unit="kip",
                )
            ],
        )
    ]
    findings = validate_structural_model(_pem_with(load_cases=load_cases))
    assert any(f.code == "LOAD_CASE_MISMATCH" for f in findings)


def test_invalid_combination_load_case_detected() -> None:
    combinations = [
        LoadCombination(
            id="combo-bad",
            name="Bad",
            combination_type="STRENGTH",
            terms=[LoadCombinationTerm(load_case_id="missing", factor=1.0)],
        )
    ]
    findings = validate_structural_model(_pem_with(load_combinations=combinations))
    assert any(f.code == "INVALID_COMBINATION_LOAD_CASE" for f in findings)


def test_level_reference_on_point_detected() -> None:
    geometry = GeometryModel(
        levels=[LevelDefinition(id="lvl-1", name="L1", elevation=0.0)],
        points=[PointDefinition(id="pt-1", x=0, y=0, z=0, level_id="lvl-missing")],
    )
    findings = validate_structural_model(_pem_with(geometry=geometry))
    assert any(f.code == "INVALID_POINT_LEVEL_REFERENCE" for f in findings)
