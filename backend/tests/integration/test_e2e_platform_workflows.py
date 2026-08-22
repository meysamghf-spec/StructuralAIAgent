"""End-to-end platform workflow integration tests (Scenarios A–E)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.application.csi_result_normalization import normalize_csi_raw_results
from app.application.design_calculations import extract_member_force_demand
from app.application.engineering_result_normalization import normalize_vendor_results
from app.application.optimization_calculations import run_multi_member_optimization
from app.application.service_factory import (
    build_analysis_engine_service,
    build_cad_generation_service,
    build_code_engine_service,
    build_design_engine_service,
    build_engineering_result_service,
    build_optimization_engine_service,
    build_traceability_service,
)
from app.domain.models.analysis import AnalysisRequest, AnalysisStatus
from app.domain.models.cad import CadDrawingRequest, CadDrawingType, CadOutputFormat
from app.domain.models.design import DesignRequest
from app.domain.models.integration import IntegrationOperationStatus
from app.domain.models.optimization import OptimizationMode, OptimizationRequest
from app.infrastructure.cad.dxf_renderer import render_plan_dxf
from app.infrastructure.integrations.csi_result_extractor import extract_csi_results
from app.domain.models.integration import IntegrationSoftware
from app.infrastructure.repositories.postgres_analysis_repository import PostgresAnalysisRepository
from tests.fixtures.pem_structural_samples import (
    sample_beam_members,
    sample_beam_plan_geometry,
    sample_column_members,
    sample_column_plan_geometry,
    sample_column_sections,
    sample_geometry,
    sample_materials,
    sample_members,
    sample_mixed_discipline_members,
    sample_sections,
    sample_slab_members,
    sample_slab_plan_geometry,
    sample_slab_sections,
    sample_steel_materials,
)
from tests.integration.helpers import (
    build_mock_csi_adapter,
    create_project,
    ingest_vendor_frame_results,
    populate_multi_beam_pem,
    populate_standard_pem,
)
from tests.test_csi_result_extractor import _MockSapModel


def test_scenario_a_deterministic_design_without_csi(db_session) -> None:
    """Project → PEM → validated results → CodeEngine → design."""
    project = create_project("Scenario A")
    version, snapshot_id = populate_standard_pem(project.id)

    analysis = build_analysis_engine_service().run_analysis(
        AnalysisRequest(project_id=project.id, analysis_type="LINEAR_STATIC"),
    )
    PostgresAnalysisRepository().update_run(
        project.id,
        analysis.id,
        status=AnalysisStatus.SUCCESS,
        capability_status="SUCCESS",
        message="Deterministic analysis context",
        outputs={"engineering_results_available": False},
    )
    result_set_id = ingest_vendor_frame_results(
        project.id,
        pem_version=version,
        pem_snapshot_id=snapshot_id,
        analysis_run_id=analysis.id,
    )

    design = build_design_engine_service().run_design(
        DesignRequest(project_id=project.id, design_type="CONCRETE_BEAM", analysis_run_id=analysis.id),
    )
    assert design.status.value in {"PASS", "WARNING", "FAIL"}
    assert design.outputs.get("routine_connected") is True
    assert design.outputs.get("result_set_id") == str(result_set_id)

    lineage = build_traceability_service().get_links_by_target(
        project.id,
        target_type="engineering_result",
        target_id=result_set_id,
    )
    assert isinstance(lineage, list)


def test_scenario_b_multi_member_independent_optimization(db_session) -> None:
    """Multiple members optimized independently through CodeEngine."""
    project = create_project("Scenario B")
    version, snapshot_id = populate_multi_beam_pem(project.id)

    analysis = build_analysis_engine_service().run_analysis(
        AnalysisRequest(project_id=project.id, analysis_type="LINEAR_STATIC"),
    )
    PostgresAnalysisRepository().update_run(
        project.id,
        analysis.id,
        status=AnalysisStatus.SUCCESS,
        capability_status="SUCCESS",
        message="Completed",
        outputs={"engineering_results_available": False},
    )
    ingest_vendor_frame_results(
        project.id,
        pem_version=version,
        pem_snapshot_id=snapshot_id,
        analysis_run_id=analysis.id,
        member_forces=[
            {"id": "mbr-1", "values": [5.0, 0.0], "load_case": "lc-dead"},
            {"id": "mbr-2", "values": [7.0, 0.0], "load_case": "lc-dead"},
        ],
    )

    result = build_optimization_engine_service().run_optimization(
        OptimizationRequest(
            project_id=project.id,
            optimization_type="WEIGHT",
            objective="Minimize weight",
            analysis_run_id=analysis.id,
            parameters={
                "optimization_mode": OptimizationMode.INDEPENDENT.value,
                "member_ids": ["mbr-1", "mbr-2"],
            },
        )
    )
    assert result.status.value == "PASS"
    assert len(result.outputs.get("member_results", [])) == 2
    assert result.outputs.get("optimization_mode") == OptimizationMode.INDEPENDENT.value


def test_scenario_c_shared_section_optimization(db_session) -> None:
    """Compatible members share a governing section."""
    project = create_project("Scenario C")
    version, snapshot_id = populate_multi_beam_pem(project.id)

    analysis = build_analysis_engine_service().run_analysis(
        AnalysisRequest(project_id=project.id, analysis_type="LINEAR_STATIC"),
    )
    PostgresAnalysisRepository().update_run(
        project.id,
        analysis.id,
        status=AnalysisStatus.SUCCESS,
        capability_status="SUCCESS",
        message="Completed",
        outputs={"engineering_results_available": False},
    )
    ingest_vendor_frame_results(
        project.id,
        pem_version=version,
        pem_snapshot_id=snapshot_id,
        analysis_run_id=analysis.id,
        member_forces=[
            {"id": "mbr-1", "values": [5.0, 0.0], "load_case": "lc-dead"},
            {"id": "mbr-2", "values": [7.0, 0.0], "load_case": "lc-dead"},
        ],
    )

    result = build_optimization_engine_service().run_optimization(
        OptimizationRequest(
            project_id=project.id,
            optimization_type="WEIGHT",
            objective="Shared section",
            analysis_run_id=analysis.id,
            parameters={
                "optimization_mode": OptimizationMode.SHARED_SECTION.value,
                "member_ids": ["mbr-1", "mbr-2"],
            },
        )
    )
    assert result.status.value == "PASS"
    shared = result.outputs.get("shared_section_groups") or []
    assert shared
    assert shared[0]["selected_section_id"]


def test_scenario_c_rejects_incompatible_shared_section_group(db_session) -> None:
    project = create_project("Scenario C incompatible")
    model = __import__(
        "app.application.service_factory", fromlist=["build_pem_model_service"]
    ).build_pem_model_service()
    from tests.fixtures.pem_structural_samples import sample_multi_beam_geometry

    materials = sample_materials()
    materials.steel.extend(sample_steel_materials().steel)
    model.update_geometry(project.id, sample_multi_beam_geometry(), summary="Geometry")
    model.update_materials(project.id, materials, summary="Materials")
    model.update_sections(project.id, sample_sections(), summary="Sections")
    model.update_members(project.id, sample_mixed_discipline_members(), summary="Members")
    pem, _, _ = model.get_current_model(project.id)

    calc = run_multi_member_optimization(
        pem=pem,
        engineering_results={
            "frame_forces": [
                {"source_identifier": "mbr-1", "values": [5.0], "load_case": "lc-dead"},
                {"source_identifier": "steel-1", "values": [5.0, 10.0], "load_case": "lc-dead"},
            ]
        },
        constraints={"max_utilization": 1.0},
        code_engine=build_code_engine_service(),
        parameters={
            "optimization_mode": OptimizationMode.SHARED_SECTION.value,
            "member_ids": ["steel-1", "mbr-1"],
        },
    )
    assert calc["status"] == "REQUIRES_ENGINEER_REVIEW"
    assert "same type and material" in calc["message"]


def test_scenario_d_cad_plan_types_and_capability_states(db_session) -> None:
    """COLUMN/BEAM/SLAB plans with explicit capability metadata."""
    column_project = create_project("Scenario D column")
    column_render = render_plan_dxf(
        _pem_for_cad(
            column_project.id,
            sample_column_plan_geometry(),
            sample_column_sections(),
            sample_column_members(),
        ),
        drawing_type=CadDrawingType.COLUMN_PLAN.value,
    )
    beam_project = create_project("Scenario D beam")
    beam_render = render_plan_dxf(
        _pem_for_cad(
            beam_project.id,
            sample_beam_plan_geometry(),
            sample_sections(),
            sample_beam_members(),
        ),
        drawing_type=CadDrawingType.BEAM_PLAN.value,
    )
    slab_project = create_project("Scenario D slab")
    slab_render = render_plan_dxf(
        _pem_for_cad(
            slab_project.id,
            sample_slab_plan_geometry(),
            sample_slab_sections(),
            sample_slab_members(),
        ),
        drawing_type=CadDrawingType.SLAB_PLAN.value,
    )

    assert column_render.metadata["capability_status"] == "COMPLETE"
    assert beam_render.metadata["capability_status"] == "COMPLETE"
    assert slab_render.metadata["capability_status"] in {"COMPLETE", "PARTIAL", "INCOMPLETE"}
    assert "SECTION" in column_render.content
    assert "SECTION" in beam_render.content

    framing_project = create_project("Scenario D framing")
    populate_standard_pem(framing_project.id)
    service = build_cad_generation_service()
    _, version, _ = __import__(
        "app.application.service_factory", fromlist=["build_pem_model_service"]
    ).build_pem_model_service().get_current_model(framing_project.id)
    drawing = service.generate_drawing(
        CadDrawingRequest(
            project_id=framing_project.id,
            drawing_type=CadDrawingType.FRAMING_PLAN,
            output_format=CadOutputFormat.DXF,
            pem_version=version,
        )
    )
    assert drawing.validation_status.value in {"VALIDATED", "PARTIALLY_VALIDATED"}
    assert drawing.pem_version == version


def _pem_for_cad(project_id, geometry, sections, members):
    model = __import__(
        "app.application.service_factory", fromlist=["build_pem_model_service"]
    ).build_pem_model_service()
    from tests.fixtures.pem_structural_samples import sample_materials

    model.update_geometry(project_id, geometry, summary="Geometry")
    model.update_materials(project_id, sample_materials(), summary="Materials")
    model.update_sections(project_id, sections, summary="Sections")
    model.update_members(project_id, members, summary="Members")
    pem, _, _ = model.get_current_model(project_id)
    return pem


def test_scenario_d_slab_plan_without_boundaries_is_not_complete(db_session) -> None:
    project = create_project("Scenario D slab incomplete")
    pem = _pem_for_cad(
        project.id,
        sample_geometry(),
        sample_sections(),
        sample_members(),
    )
    render = render_plan_dxf(pem, drawing_type=CadDrawingType.SLAB_PLAN.value)
    assert render.metadata["capability_status"] != "COMPLETE"


def test_scenario_e_csi_mock_extract_to_design(db_session) -> None:
    """Mock CSI extraction → normalization → ingest → design demand."""
    project = create_project("Scenario E")
    version, snapshot_id = populate_standard_pem(project.id)
    adapter = build_mock_csi_adapter()

    extract = adapter.extract_results(
        project.id,
        parameters={
            "pem_snapshot_id": str(snapshot_id),
            "pem_version": version,
            "member_ids": ["mbr-1"],
            "joint_ids": ["pt-1", "pt-2"],
            "load_case_ids": ["lc-dead"],
        },
    )
    assert extract.status == IntegrationOperationStatus.SUCCESS
    assert extract.metadata.get("extraction_status") in {"COMPLETE", "PARTIAL"}

    parsed = extract.metadata["parsed_results"]["results"]
    member_forces = [row for row in parsed.get("member_forces", []) if row.get("id") == "mbr-1"]
    ingest_payload = {**parsed, "member_forces": member_forces, "execution_mode": "vendor"}
    result_set = build_engineering_result_service().ingest_results(
        __import__(
            "app.domain.models.engineering_results", fromlist=["EngineeringResultIngestionRequest"]
        ).EngineeringResultIngestionRequest(
            project_id=project.id,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results=ingest_payload,
            provenance={"source_software": "ETABS", "execution_mode": "vendor"},
            metadata={"extraction_status": extract.metadata.get("extraction_status")},
        )
    )
    assert result_set.engineering_results_available is True
    demand = extract_member_force_demand(result_set.results, "mbr-1", component="moment")
    assert demand is not None and demand > 0

    design = build_design_engine_service().run_design(
        DesignRequest(project_id=project.id, design_type="CONCRETE_BEAM"),
    )
    assert design.status.value in {"PASS", "WARNING", "FAIL", "REQUIRES_ANALYSIS"}
    if design.status.value in {"PASS", "WARNING", "FAIL"}:
        assert design.outputs.get("routine_connected") is True


def test_scenario_e_csi_normalization_is_deterministic(db_session) -> None:
    raw, _ = extract_csi_results(_MockSapModel(), software=IntegrationSoftware.ETABS)
    normalized_once = normalize_csi_raw_results(raw)
    normalized_twice = normalize_csi_raw_results(raw)
    assert normalized_once["member_forces"] == normalized_twice["member_forces"]

    vendor_once = normalize_vendor_results({"member_forces": normalized_once["member_forces"]})
    vendor_twice = normalize_vendor_results({"member_forces": normalized_twice["member_forces"]})
    assert vendor_once.model_dump(mode="json") == vendor_twice.model_dump(mode="json")


def test_api_contract_design_requires_validated_results(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Contract Design"}).json()["project"]["id"]
    from tests.test_api_design import _populate_model

    _populate_model(api_client, project_id)
    response = api_client.post(
        "/api/v1/engineering/design/run",
        json={"project_id": project_id, "design_type": "CONCRETE_BEAM"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REQUIRES_ANALYSIS"


def test_api_contract_engineering_result_scoped_to_project(api_client: TestClient) -> None:
    project_a = api_client.post("/api/v1/projects", json={"name": "Project A"}).json()["project"]["id"]
    project_b = api_client.post("/api/v1/projects", json={"name": "Project B"}).json()["project"]["id"]
    from tests.test_api_engineering_results import _ingest_sample_result

    _ingest_sample_result(project_a)
    result_id = api_client.get(f"/api/v1/engineering/results/{project_a}").json()["results"][0]["id"]
    cross = api_client.get(f"/api/v1/engineering/results/{project_b}/{result_id}")
    assert cross.status_code == 404


def test_scenario_f_report_workflow_from_persisted_data(api_client: TestClient) -> None:
    """Project → PEM → report with explicit missing-data markers."""
    project_id = api_client.post("/api/v1/projects", json={"name": "Report Workflow"}).json()["project"]["id"]
    populate_standard_pem(UUID(project_id))

    report = api_client.post(
        "/api/v1/reports",
        json={
            "project_id": project_id,
            "report_type": "STRUCTURAL_DESIGN",
            "title": "Workflow Report",
        },
    )
    assert report.status_code == 201
    report_id = report.json()["id"]

    generated = api_client.post(
        f"/api/v1/reports/{report_id}/generate",
        params={"project_id": project_id},
        json={"report_type": "STRUCTURAL_DESIGN"},
    )
    assert generated.status_code == 200
    content = generated.json()["content"]
    section_keys = [section["key"] for section in content["sections"]]
    assert "analysis_results" in section_keys
    assert "cad_outputs" in section_keys
    assert generated.json()["traceability_metadata"].get("missing_data")
