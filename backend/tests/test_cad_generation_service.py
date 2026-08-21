"""Tests for DXF rendering and CAD generation."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.application.service_factory import build_cad_generation_service, build_pem_model_service, build_project_service
from app.domain.models.cad import CadDrawingRequest, CadDrawingType, CadOutputFormat, SUPPORTED_CAD_DRAWING_TYPES
from app.infrastructure.cad.dxf_renderer import (
    render_beam_plan_dxf,
    render_column_plan_dxf,
    render_framing_plan_dxf,
    render_plan_dxf,
    render_slab_plan_dxf,
)
from tests.fixtures.pem_structural_samples import (
    sample_beam_members,
    sample_beam_plan_geometry,
    sample_column_members,
    sample_column_plan_geometry,
    sample_column_sections,
    sample_geometry,
    sample_materials,
    sample_members,
    sample_sections,
    sample_slab_members,
    sample_slab_plan_geometry,
    sample_slab_sections,
)


def _build_pem(db_session):
    project = build_project_service().create_project("CAD Project").project
    model = build_pem_model_service()
    model.update_geometry(project.id, sample_geometry(), summary="Geometry")
    model.update_materials(project.id, sample_materials(), summary="Materials")
    model.update_sections(project.id, sample_sections(), summary="Sections")
    model.update_members(project.id, sample_members(), summary="Members")
    pem, _, _ = model.get_current_model(project.id)
    return project.id, pem


def _build_pem_with(db_session, *, geometry, sections, members):
    project = build_project_service().create_project("CAD Typed Project").project
    model = build_pem_model_service()
    model.update_geometry(project.id, geometry, summary="Geometry")
    model.update_materials(project.id, sample_materials(), summary="Materials")
    model.update_sections(project.id, sections, summary="Sections")
    model.update_members(project.id, members, summary="Members")
    pem, _, _ = model.get_current_model(project.id)
    return project.id, pem


def test_supported_cad_drawing_types_include_new_plans() -> None:
    assert CadDrawingType.COLUMN_PLAN.value in SUPPORTED_CAD_DRAWING_TYPES
    assert CadDrawingType.BEAM_PLAN.value in SUPPORTED_CAD_DRAWING_TYPES
    assert CadDrawingType.SLAB_PLAN.value in SUPPORTED_CAD_DRAWING_TYPES
    assert CadDrawingType.FRAMING_PLAN.value in SUPPORTED_CAD_DRAWING_TYPES


def test_render_framing_plan_dxf_from_pem_geometry(db_session) -> None:
    _, pem = _build_pem(db_session)
    render = render_framing_plan_dxf(pem, drawing_type="FRAMING_PLAN")
    assert "SECTION" in render.content
    assert render.entity_count > 0
    assert render.layer_summary["MEMBERS"] >= 1
    assert render.metadata["capability_status"] == "COMPLETE"


def test_render_column_plan_dxf_draws_columns(db_session) -> None:
    _, pem = _build_pem_with(
        db_session,
        geometry=sample_column_plan_geometry(),
        sections=sample_column_sections(),
        members=sample_column_members(),
    )
    render = render_column_plan_dxf(pem, drawing_type="COLUMN_PLAN")
    assert render.layer_summary["COLUMNS"] == 2
    assert render.metadata["capability_status"] == "COMPLETE"
    assert "C1" in render.content


def test_render_beam_plan_dxf_draws_beams(db_session) -> None:
    _, pem = _build_pem_with(
        db_session,
        geometry=sample_beam_plan_geometry(),
        sections=sample_sections(),
        members=sample_beam_members(),
    )
    render = render_beam_plan_dxf(pem, drawing_type="BEAM_PLAN")
    assert render.layer_summary["BEAMS"] == 1
    assert render.metadata["capability_status"] == "COMPLETE"
    assert "B1" in render.content


def test_render_slab_plan_dxf_draws_slab_boundary(db_session) -> None:
    _, pem = _build_pem_with(
        db_session,
        geometry=sample_slab_plan_geometry(),
        sections=sample_slab_sections(),
        members=sample_slab_members(),
    )
    render = render_slab_plan_dxf(pem, drawing_type="SLAB_PLAN")
    assert render.layer_summary["SLABS"] == 1
    assert render.metadata["capability_status"] == "COMPLETE"
    assert "S1" in render.content


def test_render_slab_plan_reports_missing_data(db_session) -> None:
    _, pem = _build_pem(db_session)
    render = render_plan_dxf(pem, drawing_type="SLAB_PLAN")
    assert render.layer_summary.get("SLABS", 0) == 0
    assert render.metadata["capability_status"] == "INCOMPLETE"
    assert render.metadata["missing_data"]


def test_plan_renderers_are_deterministic(db_session) -> None:
    _, pem = _build_pem_with(
        db_session,
        geometry=sample_column_plan_geometry(),
        sections=sample_column_sections(),
        members=sample_column_members(),
    )
    first = render_column_plan_dxf(pem, drawing_type="COLUMN_PLAN")
    second = render_column_plan_dxf(pem, drawing_type="COLUMN_PLAN")
    assert first.content == second.content
    assert first.layer_summary == second.layer_summary


def test_cad_generation_service_produces_validated_dxf(db_session, file_storage_root) -> None:
    project_id, _ = _build_pem(db_session)
    service = build_cad_generation_service()
    drawing = service.generate_drawing(
        CadDrawingRequest(
            project_id=project_id,
            drawing_type="FRAMING_PLAN",
            output_format=CadOutputFormat.DXF,
        )
    )
    assert drawing.status.value == "SUCCESS"
    assert drawing.validation_status.value == "VALIDATED"
    assert drawing.file_path is not None


def test_cad_generation_service_column_plan(db_session, file_storage_root) -> None:
    project_id, _ = _build_pem_with(
        db_session,
        geometry=sample_column_plan_geometry(),
        sections=sample_column_sections(),
        members=sample_column_members(),
    )
    service = build_cad_generation_service()
    drawing = service.generate_drawing(
        CadDrawingRequest(
            project_id=project_id,
            drawing_type="COLUMN_PLAN",
            output_format=CadOutputFormat.DXF,
        )
    )
    assert drawing.status.value == "SUCCESS"
    assert drawing.validation_status.value == "VALIDATED"
    assert drawing.layer_summary.get("COLUMNS", 0) == 2


def test_cad_generation_service_slab_plan_incomplete_without_geometry(db_session, file_storage_root) -> None:
    project_id, _ = _build_pem(db_session)
    service = build_cad_generation_service()
    drawing = service.generate_drawing(
        CadDrawingRequest(
            project_id=project_id,
            drawing_type="SLAB_PLAN",
            output_format=CadOutputFormat.DXF,
        )
    )
    assert drawing.status.value == "SUCCESS"
    assert drawing.validation_status.value == "INCOMPLETE"


from tests.test_api_design import _populate_model


def test_api_cad_endpoints(api_client: TestClient, file_storage_root) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "CAD API Project"}).json()[
        "project"
    ]["id"]
    _populate_model(api_client, project_id)

    capability = api_client.get("/api/v1/cad/capabilities/autocad")
    assert capability.status_code == 200
    assert capability.json()["software"] == "AUTOCAD"

    generated = api_client.post(
        "/api/v1/cad/generate",
        json={
            "project_id": project_id,
            "drawing_type": "FRAMING_PLAN",
            "output_format": "DXF",
        },
        headers={"X-Actor-Id": "cad-tester"},
    )
    assert generated.status_code == 200
    assert generated.json()["validation_status"] == "VALIDATED"

    for drawing_type in ("COLUMN_PLAN", "BEAM_PLAN", "SLAB_PLAN"):
        response = api_client.post(
            "/api/v1/cad/generate",
            json={
                "project_id": project_id,
                "drawing_type": drawing_type,
                "output_format": "DXF",
            },
            headers={"X-Actor-Id": "cad-tester"},
        )
        assert response.status_code == 200
        assert response.json()["drawing_type"] == drawing_type

    listed = api_client.get(f"/api/v1/cad/{project_id}/drawings")
    assert listed.status_code == 200
    assert len(listed.json()["drawings"]) == 4
