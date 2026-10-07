"""Phase H schedule engine: PEM identity, pagination, and anti-fabrication."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.drawing.pem_solids import PemDrawingContext
from app.application.drawing.schedule_sheets import (
    build_schedule_sheets,
    schedule_source_ids,
)
from app.application.drawing.sheet_builder import SheetBuildContext
from app.domain.models.drawing import (
    NOT_IN_PEM,
    Discipline,
    PrimitiveKind,
    SheetAvailability,
    SourceElementKind,
)
from app.domain.models.pem import create_initial_pem
from app.domain.models.pem_structural import (
    BeamSection,
    ColumnSection,
    DesignCheckStatus,
    LevelDefinition,
    MemberDesignCheck,
    MemberReinforcement,
    MemberType,
    ReinforcementBarSet,
    SlabSection,
    StirrupLayout,
    StructuralMember,
)
from app.infrastructure.cad.drawing_sheet_dxf import render_sheet_dxf
from app.infrastructure.reporting.drawing_set_pdf import render_sheet_pdf

_FORBIDDEN = ("Ø16", "Ø20", "Ø25", "8Ø16", "10Ø20", "Ø8@100", "Ø10@150")
_STATUS_VALUES = {"PASS", "FAIL", "WARNING", "NOT_CHECKED"}


def _context(pem) -> SheetBuildContext:
    return SheetBuildContext(
        pem=PemDrawingContext(pem),
        project_name=pem.metadata.name,
        source_model_id=str(pem.id),
        generated_at=datetime(2026, 10, 7, tzinfo=UTC),
        source_snapshot_id="SNAP-SCHEDULE",
        pem_version=3,
        revision="B",
        units="m",
    )


def _pem():
    pem = create_initial_pem(uuid4(), "Schedule fixture", "synthetic, not the 12x22 demo")
    structural = pem.structural_model
    structural.geometry.levels.append(LevelDefinition(id="L1", name="First floor", elevation=3.2))
    structural.sections.beams.extend(
        [
            BeamSection(id="SB-A", name="B300x500", width=0.30, depth=0.50),
            BeamSection(id="SB-B", name="B200x400", width=0.20, depth=0.40),
        ]
    )
    structural.sections.columns.append(
        ColumnSection(id="SC-A", name="C400x400", width=0.40, depth=0.40)
    )
    structural.sections.slabs.append(SlabSection(id="SS-A", name="S150", thickness=0.15))
    structural.members.members.extend(
        [
            StructuralMember(
                id="BM-1",
                member_type=MemberType.BEAM,
                name="Beam A1",
                section_id="SB-A",
                material_id="CONC",
                level_id="L1",
            ),
            StructuralMember(
                id="BM-2",
                member_type=MemberType.BEAM,
                name="Beam A2",
                section_id="SB-A",
                material_id="CONC",
                level_id="L1",
            ),
            StructuralMember(
                id="BM-3",
                member_type=MemberType.BEAM,
                name="Beam B",
                section_id="SB-B",
                material_id="CONC",
                level_id="L1",
            ),
            StructuralMember(
                id="COL-1",
                member_type=MemberType.COLUMN,
                name="Column 1",
                section_id="SC-A",
                material_id="CONC",
                level_id="L1",
            ),
            StructuralMember(
                id="SL-1",
                member_type=MemberType.SLAB,
                name="Slab 1",
                section_id="SS-A",
                material_id="CONC",
                level_id="L1",
            ),
        ]
    )
    return pem


def _family(sheets, family: str):
    return [sheet for sheet in sheets if sheet.metadata.get("schedule_family") == family]


def _cells(sheets) -> str:
    chunks: list[str] = []
    for sheet in sheets:
        if sheet.schedule is None:
            continue
        for row in sheet.schedule.rows:
            chunks.extend(row.cells)
        for primitive in sheet.all_primitives():
            if primitive.text:
                chunks.append(primitive.text)
    return "\n".join(chunks)


def test_schedules_keep_every_pem_id_when_rows_are_grouped() -> None:
    sheets = build_schedule_sheets(_context(_pem()))
    beams = _family(sheets, "S-201")
    assert len(beams) == 1
    assert schedule_source_ids(sheets, "S-201") == {"BM-1", "BM-2", "BM-3"}
    grouped = [
        row
        for row in beams[0].schedule.rows
        if set(row.source_element_ids) == {"BM-1", "BM-2"}
    ]
    assert len(grouped) == 1
    assert grouped[0].cells[1] == "2"
    assert grouped[0].metadata["source_element_type"] == "BEAM"
    assert "BM-3" not in grouped[0].source_element_ids
    assert schedule_source_ids(sheets, "S-202") == {"COL-1"}
    assert schedule_source_ids(sheets, "S-203") == {"SL-1"}


def test_missing_reinforcement_is_declared_and_not_invented() -> None:
    sheets = build_schedule_sheets(_context(_pem()))
    text = _cells(sheets)
    assert NOT_IN_PEM in text
    for token in _FORBIDDEN:
        assert token not in text
    for sheet in sheets:
        assert sheet.schedule is not None
        for row in sheet.schedule.rows:
            status = row.cells[-1]
            if status in _STATUS_VALUES:
                assert status == "NOT_CHECKED"
            assert status != "PASS"


def test_explicit_pem_reinforcement_is_copied_and_not_checked_stays_not_checked() -> None:
    pem = _pem()
    pem.structural_model.reinforcement.append(
        MemberReinforcement(
            member_id="BM-1",
            longitudinal=[
                ReinforcementBarSet(
                    designation="16M",
                    diameter_mm=16.0,
                    count=8,
                    area_each_mm2=201.0,
                )
            ],
            stirrups=StirrupLayout(
                designation="10M",
                diameter_mm=10.0,
                legs=2,
                spacing_mm=150.0,
            ),
            status=DesignCheckStatus.NOT_CHECKED,
        )
    )
    pem.structural_model.design_checks.append(
        MemberDesignCheck(
            member_id="BM-1",
            member_name="Beam A1",
            check_kind="BEAM_FLEXURE",
            governing_combination="1.2D+1.6L",
            demand=90.0,
            capacity=0.0,
            utilization=0.0,
            demand_unit="kN·m",
            code_reference="ACI 318",
            status=DesignCheckStatus.NOT_CHECKED,
        )
    )
    sheets = build_schedule_sheets(_context(pem))
    beam_rows = [row for sheet in _family(sheets, "S-201") for row in sheet.schedule.rows]
    furnished = next(row for row in beam_rows if "BM-1" in row.source_element_ids)
    bare = next(row for row in beam_rows if row.source_element_ids == ["BM-3"])
    assert "16M" in furnished.cells[4]
    assert "16 mm" in furnished.cells[4]
    assert "8 x" in furnished.cells[4]
    assert "10M" in furnished.cells[5]
    assert "150 mm" in furnished.cells[5]
    assert furnished.cells[-1] == "NOT_CHECKED"
    assert bare.cells[4] == NOT_IN_PEM
    assert bare.cells[5] == NOT_IN_PEM
    text = _cells(sheets)
    for token in _FORBIDDEN:
        assert token not in text
    assert "Ø20" not in text
    assert "20 mm" not in furnished.cells[4]


def test_not_checked_is_not_promoted_when_another_check_passes() -> None:
    pem = _pem()
    pem.structural_model.design_checks.extend(
        [
            MemberDesignCheck(
                member_id="COL-1",
                member_name="Column 1",
                check_kind="COLUMN_AXIAL",
                governing_combination="1.2D+1.6L",
                demand=100.0,
                capacity=200.0,
                utilization=0.5,
                demand_unit="kN",
                code_reference="ACI 318",
                status=DesignCheckStatus.PASS,
            ),
            MemberDesignCheck(
                member_id="COL-1",
                member_name="Column 1",
                check_kind="COLUMN_SLENDERNESS",
                governing_combination="1.2D+1.6L",
                demand=0.0,
                capacity=0.0,
                utilization=0.0,
                demand_unit="kN",
                code_reference="ACI 318",
                status=DesignCheckStatus.NOT_CHECKED,
            ),
        ]
    )
    sheets = build_schedule_sheets(_context(pem))
    row = _family(sheets, "S-202")[0].schedule.rows[0]
    assert row.source_element_ids == ["COL-1"]
    assert row.cells[-1] == "NOT_CHECKED"


def test_pass_is_reported_only_when_every_check_passed() -> None:
    pem = _pem()
    pem.structural_model.design_checks.append(
        MemberDesignCheck(
            member_id="SL-1",
            member_name="Slab 1",
            check_kind="SLAB_FLEXURE_ONE_WAY",
            governing_combination="1.2D+1.6L",
            demand=8.0,
            capacity=12.0,
            utilization=0.67,
            demand_unit="kN·m/m",
            code_reference="ACI 318",
            status=DesignCheckStatus.PASS,
        )
    )
    pem.structural_model.reinforcement.append(
        MemberReinforcement(
            member_id="SL-1",
            slab_bottom=[
                ReinforcementBarSet(
                    designation="12M",
                    diameter_mm=12.0,
                    count=1,
                    area_each_mm2=113.0,
                    spacing_mm=200.0,
                    layer="SLAB_BOTTOM",
                )
            ],
        )
    )
    sheets = build_schedule_sheets(_context(pem))
    row = _family(sheets, "S-203")[0].schedule.rows[0]
    assert row.cells[-1] == "PASS"
    assert row.cells[3] == "0.150"
    assert "12M" in row.cells[4]
    assert row.cells[5] == NOT_IN_PEM
    assert "Ø12" not in row.cells[4]


def test_pagination_retains_ids_across_continuation_sheets() -> None:
    sheets = build_schedule_sheets(_context(_pem()), page_rows=1)
    beams = _family(sheets, "S-201")
    assert [sheet.sheet_number for sheet in beams] == ["S-201", "S-201.2"]
    assert beams[0].metadata["page_count"] == 2
    assert beams[1].title.startswith("Beam schedule (2 of 2)")
    seen: list[str] = []
    for sheet in beams:
        assert sheet.schedule is not None
        assert len(sheet.schedule.rows) == 1
        seen.extend(sheet.schedule.rows[0].source_element_ids)
    assert seen.count("BM-1") == 1
    assert seen.count("BM-2") == 1
    assert seen.count("BM-3") == 1
    assert set(seen) == {"BM-1", "BM-2", "BM-3"}


def test_schedule_sheet_carries_title_block_table_geometry_pdf_and_dxf() -> None:
    sheet = _family(build_schedule_sheets(_context(_pem())), "S-201")[0]
    block = sheet.title_block
    assert block.drawing_number == "S-201"
    assert block.project_name == "Schedule fixture"
    assert block.revision == "B"
    assert block.units == "m"
    assert block.source_snapshot_id == "SNAP-SCHEDULE"
    assert block.discipline is Discipline.STRUCTURAL
    assert "NOT FOR CONSTRUCTION" in block.status_note.upper()
    assert sheet.scale == "NTS"
    assert any("PRELIMINARY" in note for note in sheet.notes)
    assert any("NOT_CHECKED" in note for note in sheet.notes)
    view = sheet.views[0]
    assert view.projection.value == "SCHEDULE"
    rules = [
        item
        for item in view.primitives
        if item.kind in {PrimitiveKind.LINE, PrimitiveKind.POLYLINE} and item.layer == "SCHEDULE"
    ]
    assert len(rules) >= 3
    row_rule = next(item for item in rules if "BM-1" in item.source_element_ids)
    assert row_rule.source_element_kind is SourceElementKind.BEAM
    assert "BM-2" in row_rule.source_element_ids

    pdf = render_sheet_pdf(sheet)
    assert pdf.startswith(b"%PDF-1.4")
    decoded = pdf.decode("latin-1", "replace")
    assert "S-201" in decoded
    assert "Beam schedule" in decoded
    assert "SNAP-SCHEDULE" in decoded
    assert "REV B" in decoded
    assert "B300x500" in decoded
    assert " l S" in decoded or " re S" in decoded

    dxf = render_sheet_dxf(sheet)
    assert dxf.metadata["sheet_number"] == "S-201"
    assert dxf.metadata["source_snapshot_id"] == "SNAP-SCHEDULE"
    assert dxf.layer_summary.get("SCHEDULE", 0) > 0
    assert "1000\nsource_element_kind=BEAM" in dxf.content
    traced: set[str] = set()
    for group in re.findall(r"1000\nsource_element_ids=([^\n]+)", dxf.content):
        traced.update(part for part in group.split(",") if part)
    assert {"BM-1", "BM-2", "BM-3"} <= traced


def test_empty_member_type_is_not_available_rather_than_a_blank_pass() -> None:
    pem = _pem()
    pem.structural_model.members.members = [
        member
        for member in pem.structural_model.members.members
        if member.member_type is not MemberType.SLAB
    ]
    sheets = build_schedule_sheets(_context(pem))
    slab = _family(sheets, "S-203")[0]
    assert slab.availability is SheetAvailability.NOT_AVAILABLE
    assert schedule_source_ids(sheets, "S-203") == set()
    assert slab.schedule.rows[0].cells[0] == NOT_IN_PEM
    assert slab.schedule.rows[0].cells[-1] == NOT_IN_PEM


def test_section_size_follows_the_pem_and_not_a_demo_constant() -> None:
    sheets = build_schedule_sheets(_context(_pem()))
    beam_text = " ".join(
        cell
        for sheet in _family(sheets, "S-201")
        for row in sheet.schedule.rows
        for cell in row.cells
    )
    assert "0.300 x 0.500" in beam_text
    assert "0.200 x 0.400" in beam_text
    assert "0.400 x 0.400" in " ".join(
        cell
        for sheet in _family(sheets, "S-202")
        for row in sheet.schedule.rows
        for cell in row.cells
    )
    assert "12.000 x 22.000" not in beam_text


@pytest.mark.parametrize("page_rows", [0, -1])
def test_page_rows_must_be_positive(page_rows: int) -> None:
    with pytest.raises(ValueError):
        build_schedule_sheets(_context(_pem()), page_rows=page_rows)
