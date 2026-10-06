"""Building brief → geometry → analysis → design → drawings vertical slice."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.application.building_brief_parser import BuildingBriefParser
from app.application.building_design_assembler import BuildingDesignAssembler
from app.application.building_view import serialize_building_view
from app.application.service_factory import (
    build_building_design_pipeline,
    build_code_engine_service,
    build_project_service,
)
from app.application.sheet_generation_service import SheetGenerationService
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.pem_architecture import FloorType, SpaceUsage
from app.domain.models.pem_structural import MemberType
from app.infrastructure.cad.dxf_renderer import render_plan_dxf
from app.infrastructure.reporting.pdf_sheet_renderer import render_pdf_sheet
from app.application.agent_intent_routing import resolve_primary_agent_type


PERSIAN_BRIEF = (
    "زمین ۱۲×۲۲ متر، بر ۱۲ متر، پیلوت با ۴ پارکینگ، ۳ طبقه مسکونی، هر طبقه یک واحد، هر واحد ۳ خوابه"
)
ENGLISH_BRIEF = (
    "Plot 12m × 22m, 12m frontage, pilot/parking floor, 4 parking spaces, "
    "3 residential floors, one apartment per floor, 3 bedrooms per apartment"
)


def test_parser_extracts_persian_12x22_brief() -> None:
    brief = BuildingBriefParser().parse(PERSIAN_BRIEF)
    assert {brief.plot_length_m, brief.plot_width_m} == {12.0, 22.0}
    assert brief.frontage_m == 12.0
    assert brief.has_piloti is True
    assert brief.parking_space_count == 4
    assert brief.residential_floor_count == 3
    assert brief.apartments_per_floor == 1
    assert brief.bedrooms_per_apartment == 3
    assert brief.missing_critical_inputs() == []


def test_parser_extracts_english_equivalent() -> None:
    brief = BuildingBriefParser().parse(ENGLISH_BRIEF)
    assert {brief.plot_length_m, brief.plot_width_m} == {12.0, 22.0}
    assert brief.parking_space_count == 4
    assert brief.residential_floor_count == 3
    assert brief.apartments_per_floor == 1
    assert brief.bedrooms_per_apartment == 3


def test_persian_design_request_routes_to_modeling_agent() -> None:
    agent_type, _ = resolve_primary_agent_type("این ساختمان را طراحی کن. " + PERSIAN_BRIEF)
    assert agent_type == EngineeringAgentType.STRUCTURAL_MODELING_AGENT


def test_assemble_12x22_building_has_real_geometry() -> None:
    assembled = BuildingDesignAssembler(code_engine=build_code_engine_service()).assemble_from_text(
        PERSIAN_BRIEF
    )
    building = assembled.pem.building_model
    structural = assembled.pem.structural_model

    assert assembled.status in {"GENERATED", "GENERATED_WITH_ERRORS"}
    assert building.site is not None
    assert {round(building.site.frontage_m, 3), round(building.site.depth_m, 3)} == {12.0, 22.0}
    assert building.site.boundary.area > 200
    assert any(plan.floor_type is FloorType.PILOTI for plan in building.floor_plans)
    assert sum(1 for plan in building.floor_plans if plan.floor_type is FloorType.RESIDENTIAL) == 3
    assert len(building.all_parking_spaces()) == 4
    assert any(space.usage is SpaceUsage.BEDROOM for space in building.all_spaces())
    assert any(space.usage is SpaceUsage.CORRIDOR for space in building.all_spaces())
    assert building.stairs
    assert assembled.structure.column_count >= 4
    assert assembled.structure.beam_count >= 4
    assert assembled.structure.slab_count >= 1
    assert any(member.member_type is MemberType.COLUMN for member in structural.members.members)
    assert any(member.member_type is MemberType.BEAM for member in structural.members.members)
    assert any(member.member_type is MemberType.SLAB for member in structural.members.members)
    assert {case.category.value for case in structural.load_cases} >= {"DEAD", "LIVE", "ROOF"}
    assert assembled.analysis.status == "SUCCESS"
    assert assembled.analysis.solver == "internal_direct_stiffness_3d"
    assert assembled.analysis.max_abs_displacement_m >= 0
    assert assembled.design.checks
    assert assembled.pem.structural_model.reinforcement
    assert assembled.qa.findings is not None
    wind_names = {case.name for case in structural.load_cases}
    assert {"WIND_X+", "EQ_X+", "DEAD", "LIVE"} <= wind_names
    assert structural.diaphragms
    assert structural.story_masses
    assert structural.story_drifts
    assert structural.footings
    assert any(item.origin.value == "ASSUMED" for item in structural.input_provenance)
    assert "qualified engineer" in (assembled.pem.engineering_report.get("disclaimer") or "")
    assert assembled.pem.code_compliance.get("ACI 318-25") == "PARTIAL_IMPLEMENTATION"
    assert assembled.qa.error_count == 0
    assert not any(
        finding.code == "PLACEMENT_CONFLICT" and "sits inside" in finding.message
        for finding in assembled.qa.findings
    )
    assert assembled.pem.lifecycle_status == "QA_PASSED"
    mass = next(
        item for item in structural.design_checks if item.check_kind == "IRREGULARITY_MASS"
    )
    assert mass.status.value != "FAIL"
    soft = next(
        item for item in structural.design_checks if item.check_kind == "IRREGULARITY_SOFT_STORY"
    )
    assert soft.status.value != "FAIL"

    site_plan = render_plan_dxf(assembled.pem, drawing_type="SITE_PLAN")
    parking_plan = render_plan_dxf(assembled.pem, drawing_type="PARKING_PLAN")
    floor_plan = render_plan_dxf(assembled.pem, drawing_type="ARCHITECTURAL_FLOOR_PLAN")
    column_plan = render_plan_dxf(assembled.pem, drawing_type="COLUMN_PLAN")
    assert site_plan.entity_count > 0
    assert parking_plan.entity_count > 0
    assert floor_plan.entity_count > 0
    assert column_plan.layer_summary.get("COLUMNS", 0) >= 1
    assert "LINE" in site_plan.content

    pdf = render_pdf_sheet(
        title="Site plan",
        project_name="Demo",
        sheet_number="A-101",
        scale="1:100",
        notes=["Preliminary"],
        lines=[(0, 0, 12, 0), (12, 0, 12, 22), (12, 22, 0, 22), (0, 22, 0, 0)],
        labels=[(6, 11, "PLOT")],
        model_width=12,
        model_height=22,
    )
    assert pdf.startswith(b"%PDF-1.4")
    assert b"startxref" in pdf

    view = serialize_building_view(assembled.pem)
    assert view["counts"]["parking"] == 4
    assert view["counts"]["columns"] >= 4
    assert view["site"]["frontage_m"] == 12.0


def test_pipeline_persists_model_traceability_and_sheets(db_session, tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FILE_STORAGE_ROOT", str(tmp_path))
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    project = build_project_service().create_project("12x22 Demo").project
    pipeline = build_building_design_pipeline()
    result = pipeline.generate_from_brief(
        project.id,
        PERSIAN_BRIEF,
        created_by="tester",
        generate_drawings=True,
    )
    assert result.pem_version is not None
    assert result.snapshot_id is not None
    assert result.assembled.pem.building_model.site is not None
    assert result.drawing_ids
    assert result.sheet_paths
    assert result.approval_request_id is not None
    assert result.trace_link_count >= 1
    assert Path(result.sheet_paths[0]).is_file()
    get_settings.cache_clear()


def test_api_generate_building_from_persian_brief(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/projects", json={"name": "API 12x22"})
    assert created.status_code == 201
    project_id = created.json()["project"]["id"]
    response = api_client.post(
        f"/api/v1/projects/{project_id}/building/generate",
        json={"brief": PERSIAN_BRIEF, "generate_drawings": False, "max_iterations": 2},
        headers={"X-Actor-Id": "building-tester"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in {"GENERATED", "GENERATED_WITH_ERRORS"}
    assert body["pem_version"] >= 2
    assert body["view"]["counts"]["parking"] == 4
    assert body["view"]["counts"]["stairs"] >= 1
    assert body["summary"]["analysis_status"] == "SUCCESS"

    fetched = api_client.get(f"/api/v1/projects/{project_id}/building")
    assert fetched.status_code == 200
    view = fetched.json()["view"]
    assert view["site"]["plot_area_m2"] == 264.0
    assert len(view["floors"]) >= 4


def test_sheet_generation_writes_pdfs(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FILE_STORAGE_ROOT", str(tmp_path))
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    assembled = BuildingDesignAssembler(code_engine=build_code_engine_service()).assemble_from_text(
        ENGLISH_BRIEF
    )
    from uuid import uuid4

    paths = SheetGenerationService().generate_project_sheets(
        uuid4(), assembled.pem, pem_version=1
    )
    assert paths
    assert Path(paths[0]).read_bytes().startswith(b"%PDF-1.4")
    get_settings.cache_clear()
