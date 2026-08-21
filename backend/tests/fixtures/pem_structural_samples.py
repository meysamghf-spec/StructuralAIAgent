"""Sample structural model fixtures for PEM tests."""

from __future__ import annotations

from app.domain.models.pem_structural import (
    AreaDefinition,
    BeamSection,
    ColumnSection,
    ConcreteMaterial,
    GeometryModel,
    GridDefinition,
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
    SlabSection,
    SteelMaterial,
    StructuralMember,
    SupportDefinition,
    SupportType,
)


def sample_geometry() -> GeometryModel:
    return GeometryModel(
        grids=[
            GridDefinition(id="grid-a", name="A", spacing_x=20.0, spacing_y=20.0),
        ],
        levels=[
            LevelDefinition(id="lvl-1", name="Level 1", elevation=0.0, sort_order=0),
            LevelDefinition(id="lvl-2", name="Level 2", elevation=12.0, sort_order=1),
        ],
        points=[
            PointDefinition(id="pt-1", x=0.0, y=0.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-2", x=20.0, y=0.0, z=0.0, level_id="lvl-1"),
        ],
        lines=[
            LineDefinition(id="ln-1", start_point_id="pt-1", end_point_id="pt-2"),
        ],
    )


def sample_materials() -> MaterialLibrary:
    return MaterialLibrary(
        concrete=[
            ConcreteMaterial(
                id="mat-conc-1",
                name="4000 psi Concrete",
                compressive_strength=4000.0,
                unit_weight=150.0,
            )
        ]
    )


def sample_sections() -> SectionLibrary:
    return SectionLibrary(
        beams=[
            BeamSection(id="sec-b1", name="W18x35", width=6.0, depth=17.7),
            BeamSection(id="sec-b2", name="W21x44", width=6.5, depth=20.8),
            BeamSection(id="sec-b3", name="W24x55", width=7.0, depth=23.6),
        ]
    )


def sample_multi_beam_geometry() -> GeometryModel:
    return GeometryModel(
        levels=[LevelDefinition(id="lvl-1", name="Level 1", elevation=0.0, sort_order=0)],
        points=[
            PointDefinition(id="pt-1", x=0.0, y=0.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-2", x=20.0, y=0.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-3", x=40.0, y=0.0, z=0.0, level_id="lvl-1"),
        ],
        lines=[
            LineDefinition(id="ln-1", start_point_id="pt-1", end_point_id="pt-2"),
            LineDefinition(id="ln-2", start_point_id="pt-2", end_point_id="pt-3"),
        ],
    )


def sample_multi_beam_members() -> MemberLibrary:
    return MemberLibrary(
        members=[
            StructuralMember(
                id="mbr-1",
                member_type=MemberType.BEAM,
                name="B1",
                section_id="sec-b1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-1",
                end_point_id="pt-2",
                line_id="ln-1",
            ),
            StructuralMember(
                id="mbr-2",
                member_type=MemberType.BEAM,
                name="B2",
                section_id="sec-b1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-2",
                end_point_id="pt-3",
                line_id="ln-2",
            ),
        ]
    )


def sample_steel_materials() -> MaterialLibrary:
    return MaterialLibrary(
        steel=[
            SteelMaterial(id="mat-steel-1", name="A992 Steel", yield_strength=50000.0),
        ]
    )


def sample_steel_load_cases() -> list[LoadCase]:
    return [
        LoadCase(
            id="lc-dead",
            name="Dead Load",
            category=LoadCategory.DEAD,
            loads=[
                LoadDefinition(
                    id="ld-steel-1",
                    name="Self weight",
                    load_case_id="lc-dead",
                    category=LoadCategory.DEAD,
                    distribution=LoadDistribution.MEMBER,
                    magnitude=1.0,
                    unit="kip",
                    member_id="steel-1",
                )
            ],
        )
    ]


def sample_mixed_discipline_members() -> MemberLibrary:
    return MemberLibrary(
        members=[
            StructuralMember(
                id="mbr-1",
                member_type=MemberType.BEAM,
                name="B1",
                section_id="sec-b1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-1",
                end_point_id="pt-2",
                line_id="ln-1",
            ),
            StructuralMember(
                id="steel-1",
                member_type=MemberType.BEAM,
                name="SB1",
                section_id="sec-b1",
                material_id="mat-steel-1",
                level_id="lvl-1",
                start_point_id="pt-2",
                end_point_id="pt-3",
                line_id="ln-2",
            ),
        ]
    )


def sample_steel_members() -> MemberLibrary:
    return MemberLibrary(
        members=[
            StructuralMember(
                id="steel-1",
                member_type=MemberType.BEAM,
                name="SB1",
                section_id="sec-b1",
                material_id="mat-steel-1",
                level_id="lvl-1",
                start_point_id="pt-1",
                end_point_id="pt-2",
                line_id="ln-1",
            ),
            StructuralMember(
                id="steel-2",
                member_type=MemberType.BEAM,
                name="SB2",
                section_id="sec-b1",
                material_id="mat-steel-1",
                level_id="lvl-1",
                start_point_id="pt-2",
                end_point_id="pt-3",
                line_id="ln-2",
            ),
        ]
    )


def sample_members() -> MemberLibrary:
    return MemberLibrary(
        members=[
            StructuralMember(
                id="mbr-1",
                member_type=MemberType.BEAM,
                name="B1",
                section_id="sec-b1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-1",
                end_point_id="pt-2",
                line_id="ln-1",
            )
        ]
    )


def sample_supports() -> list[SupportDefinition]:
    return [
        SupportDefinition(
            id="sup-1",
            point_id="pt-1",
            support_type=SupportType.FIXED,
        )
    ]


def sample_load_cases() -> list[LoadCase]:
    return [
        LoadCase(
            id="lc-dead",
            name="Dead Load",
            category=LoadCategory.DEAD,
            loads=[
                LoadDefinition(
                    id="ld-1",
                    name="Self weight",
                    load_case_id="lc-dead",
                    category=LoadCategory.DEAD,
                    distribution=LoadDistribution.MEMBER,
                    magnitude=1.0,
                    unit="kip",
                    member_id="mbr-1",
                )
            ],
        )
    ]


def sample_load_combinations() -> list[LoadCombination]:
    return [
        LoadCombination(
            id="combo-1",
            name="1.4D",
            combination_type="STRENGTH",
            terms=[LoadCombinationTerm(load_case_id="lc-dead", factor=1.4)],
            code_source="ASCE 7-22",
        )
    ]


def sample_column_plan_geometry() -> GeometryModel:
    return GeometryModel(
        grids=[GridDefinition(id="grid-a", name="A", spacing_x=20.0, spacing_y=20.0)],
        levels=[LevelDefinition(id="lvl-1", name="Level 1", elevation=0.0, sort_order=0)],
        points=[
            PointDefinition(id="pt-c1", x=0.0, y=0.0, z=0.0, level_id="lvl-1", grid_id="grid-a"),
            PointDefinition(id="pt-c2", x=20.0, y=0.0, z=0.0, level_id="lvl-1", grid_id="grid-a"),
        ],
        lines=[
            LineDefinition(id="ln-grid-1", start_point_id="pt-c1", end_point_id="pt-c2"),
        ],
    )


def sample_column_sections() -> SectionLibrary:
    return SectionLibrary(
        columns=[ColumnSection(id="sec-c1", name="18x18 Column", width=18.0, depth=18.0)]
    )


def sample_column_members() -> MemberLibrary:
    return MemberLibrary(
        members=[
            StructuralMember(
                id="col-1",
                member_type=MemberType.COLUMN,
                name="C1",
                section_id="sec-c1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-c1",
            ),
            StructuralMember(
                id="col-2",
                member_type=MemberType.COLUMN,
                name="C2",
                section_id="sec-c1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-c2",
            ),
        ]
    )


def sample_beam_plan_geometry() -> GeometryModel:
    return GeometryModel(
        levels=[LevelDefinition(id="lvl-1", name="Level 1", elevation=0.0, sort_order=0)],
        points=[
            PointDefinition(id="pt-b1", x=0.0, y=0.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-b2", x=24.0, y=0.0, z=0.0, level_id="lvl-1"),
        ],
        lines=[LineDefinition(id="ln-b1", start_point_id="pt-b1", end_point_id="pt-b2", member_id="beam-1")],
    )


def sample_beam_members() -> MemberLibrary:
    return MemberLibrary(
        members=[
            StructuralMember(
                id="beam-1",
                member_type=MemberType.BEAM,
                name="B1",
                section_id="sec-b1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-b1",
                end_point_id="pt-b2",
                line_id="ln-b1",
            )
        ]
    )


def sample_slab_plan_geometry() -> GeometryModel:
    return GeometryModel(
        levels=[LevelDefinition(id="lvl-1", name="Level 1", elevation=0.0, sort_order=0)],
        points=[
            PointDefinition(id="pt-s1", x=0.0, y=0.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-s2", x=30.0, y=0.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-s3", x=30.0, y=20.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-s4", x=0.0, y=20.0, z=0.0, level_id="lvl-1"),
            PointDefinition(id="pt-col", x=5.0, y=5.0, z=0.0, level_id="lvl-1"),
        ],
        areas=[
            AreaDefinition(
                id="area-s1",
                boundary_point_ids=["pt-s1", "pt-s2", "pt-s3", "pt-s4"],
                level_id="lvl-1",
                member_id="slab-1",
            )
        ],
    )


def sample_slab_sections() -> SectionLibrary:
    return SectionLibrary(
        beams=[BeamSection(id="sec-b1", name="W18x35", width=6.0, depth=17.7)],
        columns=[ColumnSection(id="sec-c1", name="16x16 Column", width=16.0, depth=16.0)],
        slabs=[SlabSection(id="sec-s1", name="8 in Slab", thickness=8.0)],
    )


def sample_slab_members() -> MemberLibrary:
    return MemberLibrary(
        members=[
            StructuralMember(
                id="slab-1",
                member_type=MemberType.SLAB,
                name="S1",
                section_id="sec-s1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                area_id="area-s1",
            ),
            StructuralMember(
                id="col-s1",
                member_type=MemberType.COLUMN,
                name="C1",
                section_id="sec-c1",
                material_id="mat-conc-1",
                level_id="lvl-1",
                start_point_id="pt-col",
            ),
        ]
    )
