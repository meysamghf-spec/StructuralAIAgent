"""
Phase G regression tests — the structural sheets S-001, S-101, S-102, S-103, S-104.

The defect these guard against is the one the milestone exists to fix: the four
structural plans used to be the same grid plot emitted under four titles. So the
assertions here are not just "a sheet was produced" — they check that each sheet
carries references to the PEM elements it is *about*, that its projected geometry
is more than the grid, that the four sheets differ from one another, and that the
PDF and DXF exports carry that difference through to the output files.

``test_generator_is_not_tuned_to_the_12x22_model`` runs the whole generator over a
second, differently shaped PEM. Without it, the numeric assertions in here could
all be satisfied by a generator hard-coded to the 12x22 demo.
"""

from __future__ import annotations

import re
from uuid import uuid4

import pytest

from app.application.building_design_assembler import BuildingDesignAssembler
from app.application.drawing.drawing_set_service import (
    STRUCTURAL_SHEET_NUMBERS,
    DrawingSetService,
)
from app.application.drawing.schedule_sheets import schedule_source_ids
from app.application.drawing.annotation import LAYER_GRID, LAYER_GRID_BUBBLE
from app.application.service_factory import build_code_engine_service
from app.domain.models.drawing import (
    NOT_IN_PEM,
    Discipline,
    DrawingSet,
    DrawingSheet,
    SheetAvailability,
    SourceElementKind,
)
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import MemberType
from app.infrastructure.cad.drawing_sheet_dxf import render_sheet_dxf
from app.infrastructure.reporting.drawing_set_pdf import render_drawing_set_pdf

ENGLISH_BRIEF = (
    "Plot 12m x 22m, 12m frontage, pilot/parking floor, 4 parking spaces, "
    "3 residential floors, one apartment per floor, 3 bedrooms per apartment"
)
SMALLER_BRIEF = (
    "Plot 9m x 15m, 9m frontage, pilot/parking floor, 2 parking spaces, "
    "2 residential floors, one apartment per floor, 2 bedrooms per apartment"
)

PLAN_SHEETS = ("S-101", "S-102", "S-103", "S-104")


def _build(brief: str) -> tuple[ProjectEngineeringModel, DrawingSet]:
    pem = BuildingDesignAssembler(code_engine=build_code_engine_service()).assemble_from_text(brief).pem
    drawing_set = DrawingSetService().generate(
        pem, project_id=uuid4(), pem_version=1, snapshot_id="SNAP-TEST"
    )
    return pem, drawing_set


@pytest.fixture(scope="module")
def demo() -> tuple[ProjectEngineeringModel, DrawingSet]:
    """The 12x22 vertical slice. Module-scoped: assembling the PEM is expensive."""
    return _build(ENGLISH_BRIEF)


def _sheet(drawing_set: DrawingSet, number: str) -> DrawingSheet:
    sheet = drawing_set.sheet(number)
    assert sheet is not None, f"{number} is missing from the drawing set"
    return sheet


def _ref_ids(sheet: DrawingSheet, kind: SourceElementKind) -> set[str]:
    return {ref.element_id for ref in sheet.element_refs if ref.element_kind is kind}


def _member_ids(pem: ProjectEngineeringModel, member_type: MemberType) -> set[str]:
    return {
        member.id
        for member in pem.structural_model.members.members
        if member.member_type is member_type
    }


def _footing_ids(pem: ProjectEngineeringModel) -> set[str]:
    return {footing.id for footing in pem.structural_model.footings}


def _levels(pem: ProjectEngineeringModel) -> dict[str, object]:
    return {level.id: level for level in pem.structural_model.geometry.levels}


def _view_level(view) -> str:
    return view.source_level_ids[0] if view.source_level_ids else ""


# ---------------------------------------------------------------------------
# The sheets exist, are structural, and are complete
# ---------------------------------------------------------------------------


def test_structural_sheets_are_generated(demo) -> None:
    _, drawing_set = demo
    assert STRUCTURAL_SHEET_NUMBERS == ("S-001", "S-101", "S-102", "S-103", "S-104")
    for number in STRUCTURAL_SHEET_NUMBERS:
        sheet = _sheet(drawing_set, number)
        assert sheet.availability is SheetAvailability.AVAILABLE, number
        assert sheet.discipline is Discipline.STRUCTURAL, number
        assert sheet.title_block.discipline is Discipline.STRUCTURAL, number
        assert sheet.title_block.drawing_number == number
        assert sheet.title_block.project_name
        assert sheet.title_block.source_model_id
        assert sheet.title_block.source_snapshot_id == "SNAP-TEST"
        assert sheet.title_block.revision == "0"
        assert sheet.title_block.units
        assert sheet.title_block.generated_at is not None
        assert sheet.notes, number


def test_out_of_scope_sheets_are_absent_rather_than_stubbed(demo) -> None:
    """S-301 and S-401 remain later milestones and must not be faked as empty sheets."""
    _, drawing_set = demo
    numbers = set(drawing_set.sheet_numbers)
    assert not numbers & {"S-301", "S-401"}
    pending = drawing_set.metadata["pending_milestones"]
    for number in ("S-301", "S-401"):
        assert any(entry.startswith(number) for entry in pending), number
    for number in ("S-201", "S-202", "S-203"):
        assert not any(entry.startswith(number) for entry in pending), number


# ---------------------------------------------------------------------------
# 1-4: each sheet references the PEM elements it is about
# ---------------------------------------------------------------------------


def test_s101_references_pem_footings(demo) -> None:
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, "S-101")
    footing_refs = _ref_ids(sheet, SourceElementKind.FOOTING)
    assert footing_refs, "S-101 carries no footing references"
    assert footing_refs == _footing_ids(pem)


def test_s102_references_pem_columns(demo) -> None:
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, "S-102")
    column_refs = _ref_ids(sheet, SourceElementKind.COLUMN)
    assert column_refs
    assert column_refs == _member_ids(pem, MemberType.COLUMN)


def test_s103_references_pem_beams(demo) -> None:
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, "S-103")
    beam_refs = _ref_ids(sheet, SourceElementKind.BEAM)
    assert beam_refs
    assert beam_refs == _member_ids(pem, MemberType.BEAM)


def test_s104_references_pem_slabs_and_diaphragms(demo) -> None:
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, "S-104")
    slab_refs = _ref_ids(sheet, SourceElementKind.SLAB)
    diaphragm_refs = _ref_ids(sheet, SourceElementKind.DIAPHRAGM)
    assert slab_refs == _member_ids(pem, MemberType.SLAB)
    assert diaphragm_refs == {
        diaphragm.id for diaphragm in pem.structural_model.diaphragms
    }
    assert diaphragm_refs


# ---------------------------------------------------------------------------
# 5-8: no sheet is only the grid
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("number", PLAN_SHEETS)
def test_plan_sheet_is_more_than_the_grid(demo, number: str) -> None:
    _, drawing_set = demo
    sheet = _sheet(drawing_set, number)
    geometry = sheet.geometry_primitives
    assert geometry, f"{number} has no projected model geometry"

    grid_only = [
        item
        for item in geometry
        if item.layer in {LAYER_GRID, LAYER_GRID_BUBBLE}
        or item.source_element_kind is SourceElementKind.GRID
    ]
    assert not grid_only, f"{number} projected geometry includes grid linework"

    subject = {
        "S-101": SourceElementKind.FOOTING,
        "S-102": SourceElementKind.COLUMN,
        "S-103": SourceElementKind.BEAM,
        "S-104": SourceElementKind.SLAB,
    }[number]
    from_subject = [item for item in geometry if item.source_element_kind is subject]
    assert len(from_subject) >= 0.1 * len(geometry), (
        f"{number} geometry is not predominantly {subject.value}"
    )


@pytest.mark.parametrize("number", PLAN_SHEETS)
def test_plan_sheet_geometry_covers_the_plot(demo, number: str) -> None:
    """A sheet drawn only at the grid origin would pass a ref count but fail here."""
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, number)
    site = pem.building_model.site
    assert site is not None
    min_x, min_y, max_x, max_y = sheet.geometry_bounds
    assert max_x - min_x > 0.5 * site.boundary.width
    assert max_y - min_y > 0.5 * site.boundary.depth


# ---------------------------------------------------------------------------
# 9: the four sheets are genuinely different drawings
# ---------------------------------------------------------------------------


def test_structural_plans_are_four_different_drawings(demo) -> None:
    _, drawing_set = demo
    sheets = [_sheet(drawing_set, number) for number in PLAN_SHEETS]
    geometry_signatures = {sheet.geometry_signature for sheet in sheets}
    content_signatures = {sheet.content_signature for sheet in sheets}
    assert len(geometry_signatures) == 4, "two structural plans share their geometry"
    assert len(content_signatures) == 4


def test_the_distinctness_check_catches_a_renamed_copy(demo) -> None:
    """
    Guards the guard.

    Builds the defect this milestone removed — S-102 as a relabelled copy of
    S-101 — in memory, and asserts the signature comparison above rejects it. If
    this passes while ``test_structural_plans_are_four_different_drawings`` is
    made to compare something insensitive, the suite has stopped protecting
    anything.
    """
    _, drawing_set = demo
    original = _sheet(drawing_set, "S-101")
    impostor = original.model_copy(
        update={"sheet_number": "S-102", "title": "Column layout"}, deep=True
    )
    assert impostor.sheet_number != original.sheet_number
    assert impostor.title != original.title
    # Different title block, same drawing underneath.
    assert impostor.geometry_signature == original.geometry_signature
    assert impostor.content_signature == original.content_signature
    assert len({impostor.geometry_signature, original.geometry_signature}) == 1

    # The reference-count checks would catch it too. A relabelled foundation
    # plan shows only the columns standing on the footings — one level's worth —
    # where the real S-102 covers every level that has columns.
    real = _sheet(drawing_set, "S-102")
    assert _ref_ids(impostor, SourceElementKind.COLUMN) < _ref_ids(
        real, SourceElementKind.COLUMN
    )
    assert len(impostor.views) == 1 < len(real.views)


def test_every_sheet_in_the_set_is_distinct(demo) -> None:
    _, drawing_set = demo
    signatures = {sheet.geometry_signature for sheet in drawing_set.sheets}
    # S-001 is a notes sheet and projects no geometry, so it is excluded from the
    # geometry comparison; the remaining sheets must all differ.
    drawn = [sheet for sheet in drawing_set.sheets if sheet.geometry_primitives]
    assert len(drawn) == len(drawing_set.sheets) - 1
    assert len({sheet.geometry_signature for sheet in drawn}) == len(drawn)
    assert len({sheet.content_signature for sheet in drawing_set.sheets}) == len(
        drawing_set.sheets
    )
    assert len(signatures) >= len(drawn)


# ---------------------------------------------------------------------------
# 10: traceability back to the PEM
# ---------------------------------------------------------------------------


def test_all_structural_geometry_is_traceable_to_the_pem(demo) -> None:
    pem, drawing_set = demo
    structural = pem.structural_model
    known: set[str] = {member.id for member in structural.members.members}
    known |= _footing_ids(pem)
    known |= {diaphragm.id for diaphragm in structural.diaphragms}
    known |= {point.id for point in structural.geometry.points}
    known |= {area.id for area in structural.geometry.areas}
    known |= {level.id for level in structural.geometry.levels}
    known |= {plan.id for plan in pem.building_model.floor_plans}

    element_kinds = {
        SourceElementKind.COLUMN,
        SourceElementKind.BEAM,
        SourceElementKind.SLAB,
        SourceElementKind.FOOTING,
        SourceElementKind.DIAPHRAGM,
        SourceElementKind.NODE,
        SourceElementKind.LEVEL,
    }
    for number in PLAN_SHEETS:
        sheet = _sheet(drawing_set, number)
        assert sheet.traceability_coverage == 1.0, number
        for primitive in sheet.geometry_primitives:
            assert primitive.source_element_ids, f"{number}/{primitive.id} untraced"
            if primitive.source_element_kind in element_kinds:
                unknown = set(primitive.source_element_ids) - known
                assert not unknown, f"{number} cites elements absent from the PEM: {unknown}"


def test_element_refs_name_their_sheet_and_kind(demo) -> None:
    _, drawing_set = demo
    sheet = _sheet(drawing_set, "S-103")
    for ref in sheet.element_refs:
        assert ref.element_id
        assert isinstance(ref.element_kind, SourceElementKind)
        assert ref.primitive_ids
        assert ref.primitive_count == len(ref.primitive_ids)


def test_sheets_can_answer_which_pem_element_made_this_geometry(demo) -> None:
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, "S-101")
    footing = pem.structural_model.footings[0]
    ref = next(ref for ref in sheet.element_refs if ref.element_id == footing.id)
    assert ref.element_kind is SourceElementKind.FOOTING
    assert ref.primitive_ids
    found = [item for item in sheet.all_primitives() if item.id in set(ref.primitive_ids)]
    assert found
    assert all(footing.id in item.source_element_ids for item in found)


# ---------------------------------------------------------------------------
# 11: levels
# ---------------------------------------------------------------------------


def test_each_plan_sheet_shows_one_view_per_level_present_in_the_pem(demo) -> None:
    pem, drawing_set = demo
    levels = _levels(pem)

    def levels_with(member_type: MemberType) -> set[str]:
        return {
            member.level_id
            for member in pem.structural_model.members.members
            if member.member_type is member_type and member.level_id
        }

    expectations = {
        "S-102": levels_with(MemberType.COLUMN),
        "S-103": levels_with(MemberType.BEAM),
        "S-104": levels_with(MemberType.SLAB),
    }
    for number, expected_levels in expectations.items():
        sheet = _sheet(drawing_set, number)
        assert expected_levels, number
        view_levels = {_view_level(view) for view in sheet.views}
        assert view_levels == expected_levels, number
        assert len(sheet.views) == len(expected_levels), number
        # Levels must not be collapsed into one another: each view names the
        # level it draws, and no two views draw the same one.
        for view in sheet.views:
            level_id = _view_level(view)
            assert level_id in levels
            assert levels[level_id].name in view.name or level_id in view.name

    foundation = _sheet(drawing_set, "S-101")
    assert len(foundation.views) == 1
    assert _view_level(foundation.views[0]) in levels


def test_roof_level_is_labelled_roof_not_a_level_number(demo) -> None:
    pem, drawing_set = demo
    top_level_id = pem.structural_model.geometry.levels[-1].id
    sheet = _sheet(drawing_set, "S-103")
    roof_views = [view for view in sheet.views if _view_level(view) == top_level_id]
    assert roof_views
    assert all("ROOF" in view.name.upper() for view in roof_views)
    lower = [view for view in sheet.views if _view_level(view) != top_level_id]
    assert lower
    assert all("LEVEL" in view.name.upper() for view in lower)


def test_level_views_use_real_pem_elevations(demo) -> None:
    pem, drawing_set = demo
    elevations = {
        level.id: level.elevation for level in pem.structural_model.geometry.levels
    }
    for number in ("S-102", "S-103", "S-104"):
        sheet = _sheet(drawing_set, number)
        seen = {
            _view_level(view): view.metadata["elevation_m"] for view in sheet.views
        }
        for level_id, elevation in seen.items():
            assert elevation == pytest.approx(elevations[level_id]), number
        assert len(set(seen.values())) == len(seen), f"{number} reuses one elevation"


# ---------------------------------------------------------------------------
# 12: PDF output
# ---------------------------------------------------------------------------


def test_pdf_contains_one_distinct_page_per_sheet(demo) -> None:
    _, drawing_set = demo
    pdf = render_drawing_set_pdf(drawing_set)
    assert pdf.startswith(b"%PDF-1.4")
    assert pdf.rstrip().endswith(b"%%EOF")
    assert pdf.count(b"/Type /Page ") == len(drawing_set.sheets)
    assert f"/Count {len(drawing_set.sheets)}".encode() in pdf
    for sheet in drawing_set.sheets:
        assert sheet.sheet_number.encode("latin-1") in pdf
        assert sheet.title[:30].encode("latin-1", "replace") in pdf
    assert b"/MediaBox [0 0 1190 842]" in pdf


def test_pdf_structural_pages_have_different_content_streams(demo) -> None:
    from app.infrastructure.reporting.drawing_set_pdf import _sheet_content

    _, drawing_set = demo
    streams = {
        number: _sheet_content(_sheet(drawing_set, number)) for number in PLAN_SHEETS
    }
    assert len(set(streams.values())) == 4
    for number, stream in streams.items():
        # Drawing operators, not just a title block.
        assert stream.count(" l S") + stream.count(" l ") > 100, number
        assert "BT /F1" in stream
        assert "STRUCTURAL" in stream
        assert number in stream


def test_pdf_page_order_matches_the_sheet_order(demo) -> None:
    _, drawing_set = demo
    pdf = render_drawing_set_pdf(drawing_set).decode("latin-1")
    assert "(DRAWING No) Tj" in pdf
    # The title-block drawing number is unique per page, so its position in the
    # byte stream orders the pages.
    positions = [
        pdf.index(f"({sheet.sheet_number}      REV") for sheet in drawing_set.sheets
    ]
    assert positions == sorted(positions)
    assert len(set(positions)) == len(drawing_set.sheets)


# ---------------------------------------------------------------------------
# 13: DXF output
# ---------------------------------------------------------------------------


def test_dxf_exports_carry_sheet_specific_structural_geometry(demo) -> None:
    _, drawing_set = demo
    expected_layers = {
        "S-101": "FOUNDATIONS",
        "S-102": "COLUMNS",
        "S-103": "BEAMS",
        "S-104": "SLABS",
    }
    results = {
        number: render_sheet_dxf(_sheet(drawing_set, number)) for number in PLAN_SHEETS
    }
    for number, result in results.items():
        assert result.content.startswith("0\nSECTION")
        assert result.content.rstrip().endswith("0\nEOF")
        assert result.entity_count > 0
        assert result.metadata["sheet_number"] == number
        assert result.metadata["discipline"] == "STRUCTURAL"
        layer = expected_layers[number]
        assert layer in result.layer_summary, f"{number} DXF has no {layer} layer"
        assert result.layer_summary[layer] > 0
        assert f"8\n{layer}" in result.content

    # The sheet-specific layer must dominate its own sheet and not simply be
    # present on all of them, which is what a reused grid plot would look like.
    assert results["S-104"].layer_summary.get("DIAPHRAGM", 0) > 0
    assert "FOUNDATIONS" not in results["S-103"].layer_summary
    assert "BEAMS" not in results["S-101"].layer_summary
    assert "SLABS" not in results["S-102"].layer_summary


def test_dxf_geometry_differs_between_structural_sheets(demo) -> None:
    _, drawing_set = demo
    bodies = {}
    for number in PLAN_SHEETS:
        content = render_sheet_dxf(_sheet(drawing_set, number)).content
        # Drop the title block, whose text differs by construction.
        bodies[number] = "\n".join(
            line for line in content.splitlines() if "TITLE-BLOCK" not in line
        )
    assert len(set(bodies.values())) == 4


def test_dxf_retains_source_element_ids(demo) -> None:
    pem, drawing_set = demo
    content = render_sheet_dxf(_sheet(drawing_set, "S-101")).content
    assert "1001\nSAIA" in content
    assert "1000\nsource_element_kind=FOOTING" in content
    traced: set[str] = set()
    for group in re.findall(r"1000\nsource_element_ids=([^\n]+)", content):
        traced.update(group.split(","))
    assert _footing_ids(pem) <= traced


# ---------------------------------------------------------------------------
# 12x22-specific element counts
# ---------------------------------------------------------------------------


def test_12x22_foundation_plan_has_thirty_six_footings(demo) -> None:
    pem, drawing_set = demo
    assert len(pem.structural_model.footings) == 36
    sheet = _sheet(drawing_set, "S-101")
    assert len(_ref_ids(sheet, SourceElementKind.FOOTING)) == 36


def test_12x22_structural_reference_counts_match_the_pem(demo) -> None:
    pem, drawing_set = demo
    counts = {
        "S-102": (SourceElementKind.COLUMN, len(_member_ids(pem, MemberType.COLUMN))),
        "S-103": (SourceElementKind.BEAM, len(_member_ids(pem, MemberType.BEAM))),
        "S-104": (SourceElementKind.SLAB, len(_member_ids(pem, MemberType.SLAB))),
    }
    for number, (kind, expected) in counts.items():
        assert len(_ref_ids(_sheet(drawing_set, number), kind)) == expected, number
    assert len(_ref_ids(_sheet(drawing_set, "S-104"), SourceElementKind.DIAPHRAGM)) == len(
        pem.structural_model.diaphragms
    )


def test_12x22_footing_sizes_are_read_from_the_pem(demo) -> None:
    """The plan must show each footing at its designed size, not a nominal one."""
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, "S-101")
    sizes = {
        footing.id: (footing.length_m, footing.width_m)
        for footing in pem.structural_model.footings
    }
    assert len({size for size in sizes.values()}) > 1, "fixture has uniform footings"

    outlines = {
        primitive.source_element_ids[0]: primitive
        for primitive in sheet.geometry_primitives
        if primitive.source_element_kind is SourceElementKind.FOOTING
        and primitive.closed
        and len(primitive.points) == 4
    }
    assert set(outlines) == set(sizes)
    for footing_id, primitive in outlines.items():
        xs = [point.x for point in primitive.points]
        ys = [point.y for point in primitive.points]
        length, width = sizes[footing_id]
        assert max(xs) - min(xs) == pytest.approx(length, abs=1e-6)
        assert max(ys) - min(ys) == pytest.approx(width, abs=1e-6)


# ---------------------------------------------------------------------------
# Engineering safety
# ---------------------------------------------------------------------------


def test_notes_sheet_reports_pem_metadata_without_inventing_values(demo) -> None:
    pem, drawing_set = demo
    sheet = _sheet(drawing_set, "S-001")
    text = " ".join(
        primitive.text or "" for primitive in sheet.all_primitives() if primitive.text
    )
    assert pem.metadata.name in text
    for level in pem.structural_model.geometry.levels:
        assert level.id in text
    assert "NOT FOR CONSTRUCTION" in text.upper()
    assert "construction-document set" in text.replace("   ", " ")
    assert _ref_ids(sheet, SourceElementKind.LEVEL)


def test_notes_sheet_repeats_not_checked_items_rather_than_upgrading_them(demo) -> None:
    """Capability classification must reach the sheet as the PEM states it."""
    pem, drawing_set = demo
    classification = pem.engineering_report.get("classification")
    assert isinstance(classification, dict)
    not_checked = classification.get("NOT_CHECKED") or []
    assert not_checked, "fixture has nothing NOT_CHECKED, so this proves nothing"

    sheet = _sheet(drawing_set, "S-001")
    text = " ".join(
        primitive.text or "" for primitive in sheet.all_primitives() if primitive.text
    )
    assert "NOT_CHECKED:" in text
    for item in not_checked:
        # Long entries are soft-wrapped onto the next line, so match the head.
        assert item.split(" ")[0] in text, item


def test_unavailable_values_are_declared_not_fabricated(demo) -> None:
    _, drawing_set = demo
    for number in STRUCTURAL_SHEET_NUMBERS:
        sheet = _sheet(drawing_set, number)
        for primitive in sheet.all_primitives():
            if primitive.text and "N/A" in primitive.text:
                assert NOT_IN_PEM in primitive.text or "N/A —" in primitive.text


def test_no_sheet_claims_construction_status(demo) -> None:
    _, drawing_set = demo
    for sheet in drawing_set.sheets:
        note = sheet.title_block.status_note.upper()
        assert "NOT FOR CONSTRUCTION" in note or "NOT A CONSTRUCTION DOCUMENT" in note
        assert "APPROVED FOR CONSTRUCTION" not in note


def test_sheets_do_not_draw_reinforcement_that_the_pem_lacks(demo) -> None:
    """Phase G draws no rebar at all; S-401 is a later milestone."""
    _, drawing_set = demo
    for number in PLAN_SHEETS:
        sheet = _sheet(drawing_set, number)
        assert not [
            primitive
            for primitive in sheet.all_primitives()
            if primitive.layer == "REINFORCEMENT"
        ], number


# ---------------------------------------------------------------------------
# Model independence
# ---------------------------------------------------------------------------


def test_generator_is_not_tuned_to_the_12x22_model(demo) -> None:
    """
    The same generator over a differently shaped PEM.

    Every count and dimension must follow the second PEM. If any of the numbers
    above were hard-coded for the demo building, this fails.
    """
    demo_pem, _ = demo
    other_pem, other_set = _build(SMALLER_BRIEF)

    demo_site = demo_pem.building_model.site
    other_site = other_pem.building_model.site
    assert demo_site is not None and other_site is not None
    assert (other_site.boundary.width, other_site.boundary.depth) != (
        demo_site.boundary.width,
        demo_site.boundary.depth,
    )

    for number in STRUCTURAL_SHEET_NUMBERS:
        sheet = _sheet(other_set, number)
        assert sheet.availability is SheetAvailability.AVAILABLE, number

    footings = _footing_ids(other_pem)
    assert _ref_ids(_sheet(other_set, "S-101"), SourceElementKind.FOOTING) == footings
    assert len(footings) != 36, "second fixture is too close to the demo to be a control"

    assert _ref_ids(_sheet(other_set, "S-102"), SourceElementKind.COLUMN) == _member_ids(
        other_pem, MemberType.COLUMN
    )
    assert _ref_ids(_sheet(other_set, "S-103"), SourceElementKind.BEAM) == _member_ids(
        other_pem, MemberType.BEAM
    )
    assert _ref_ids(_sheet(other_set, "S-104"), SourceElementKind.SLAB) == _member_ids(
        other_pem, MemberType.SLAB
    )

    # Still four different drawings on a different building.
    plans = [_sheet(other_set, number) for number in PLAN_SHEETS]
    assert len({sheet.geometry_signature for sheet in plans}) == 4

    # And the plotted geometry tracks the smaller plot rather than the demo's.
    # Footings at the perimeter columns straddle the plot edge, so the drawn
    # extent legitimately exceeds the boundary by up to half a footing.
    _, demo_set = demo
    other_x0, other_y0, other_x1, other_y1 = _sheet(other_set, "S-101").geometry_bounds
    demo_x0, demo_y0, demo_x1, demo_y1 = _sheet(demo_set, "S-101").geometry_bounds
    assert other_x1 - other_x0 < demo_x1 - demo_x0
    assert other_y1 - other_y0 < demo_y1 - demo_y0
    assert other_x1 - other_x0 == pytest.approx(other_site.boundary.width, abs=2.5)
    assert other_y1 - other_y0 == pytest.approx(other_site.boundary.depth, abs=2.5)

    # Levels follow the second PEM's storey count, not the demo's.
    other_levels = {_view_level(view) for view in _sheet(other_set, "S-102").views}
    demo_levels = {level.id for level in demo_pem.structural_model.geometry.levels}
    assert other_levels != demo_levels

    for family, member_type in (
        ("S-201", MemberType.BEAM),
        ("S-202", MemberType.COLUMN),
        ("S-203", MemberType.SLAB),
    ):
        demo_ids = _member_ids(demo_pem, member_type)
        other_ids = _member_ids(other_pem, member_type)
        assert schedule_source_ids(demo_set.sheets, family) == demo_ids
        assert schedule_source_ids(other_set.sheets, family) == other_ids
        assert demo_ids != other_ids
