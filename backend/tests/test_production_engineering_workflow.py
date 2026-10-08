"""Production workflow: real PEM coordination, honest external-software states."""

from __future__ import annotations

from uuid import UUID

from fastapi.testclient import TestClient

from app.application.coordination_service import CoordinationService
from app.application.production_engineering_workflow import (
    building_brief_from_record,
    detail_sheet_status,
    execution_contract,
    summarize_production_qa,
)
from app.application.service_factory import build_pem_service
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.pem import create_initial_pem
from app.domain.models.pem_architecture import (
    FloorPlanDefinition,
    FloorType,
    Point2D,
    Polygon2D,
    SpaceDefinition,
    SpaceUsage,
)
from app.domain.models.pem_structural import MemberType, PointDefinition, StructuralMember
from app.application.engineering_brief_mapping import normalize_engineering_brief
from app.application.production_engineering_workflow import ARCHITECTURAL_FIELDS


ARCH_BRIEF = {
    "project_type": {"value": "residential", "origin": "USER_PROVIDED"},
    "location": {"value": "test site", "origin": "USER_PROVIDED"},
    "plot_length_m": {"value": 22, "origin": "USER_PROVIDED"},
    "plot_width_m": {"value": 12, "origin": "USER_PROVIDED"},
    "frontage_m": {"value": 12, "origin": "USER_PROVIDED"},
    "setback_front_m": {"value": 2, "origin": "USER_PROVIDED"},
    "setback_rear_m": {"value": 2, "origin": "USER_PROVIDED"},
    "setback_side_m": {"value": 1, "origin": "USER_PROVIDED"},
    "number_of_floors": {"value": 3, "origin": "USER_PROVIDED"},
    "story_heights": {"value": "3, 3.2", "origin": "USER_PROVIDED"},
    "parking_space_count": {"value": 4, "origin": "USER_PROVIDED"},
    "has_piloti": {"value": "yes", "origin": "USER_PROVIDED"},
    "apartments_per_floor": {"value": 1, "origin": "USER_PROVIDED"},
    "bedrooms_per_apartment": {"value": 3, "origin": "USER_PROVIDED"},
    "stairs": {"value": "required", "origin": "USER_PROVIDED"},
    "elevator": {"value": "required", "origin": "USER_PROVIDED"},
    "structural_system": {"value": "reinforced concrete", "origin": "USER_PROVIDED"},
    "units": {"value": "SI", "origin": "USER_PROVIDED"},
    "engineer_notes": {"value": "Production package test.", "origin": "USER_PROVIDED"},
    "accessibility": {"value": None, "origin": "UNAVAILABLE"},
}


def test_architectural_brief_keeps_provenance_and_does_not_invent_blanks() -> None:
    recorded = normalize_engineering_brief({"engineering_brief": ARCH_BRIEF}, ARCHITECTURAL_FIELDS)
    model, notes = building_brief_from_record(recorded)
    assert model.plot_length_m == 22
    assert model.plot_width_m == 12
    assert model.residential_floor_count == 2
    assert model.requires_stair is True
    assert model.requires_elevator is True
    assert model.metadata["text_only"]["units"] == "SI"
    derived = next(item for item in notes if item["field"] == "residential_floor_count")
    assert derived["origin"] == "DERIVED"
    assumed = next(item for item in notes if item["field"] == "structural_system" and item["origin"] == "ASSUMED")
    assert assumed["value"] == "RC_MOMENT_FRAME"
    assert any(item["field"] == "accessibility" and item["origin"] == "UNAVAILABLE" for item in notes)
    assert model.metadata["story_heights"] == [3.0, 3.2]


def test_beam_through_stair_opening_is_a_hard_conflict() -> None:
    pem = create_initial_pem(UUID(int=9), "beam-opening")
    stair = SpaceDefinition(
        id="ST",
        name="Stair",
        usage=SpaceUsage.STAIR,
        boundary=Polygon2D(
            points=[
                Point2D(x=4, y=4),
                Point2D(x=8, y=4),
                Point2D(x=8, y=8),
                Point2D(x=4, y=8),
            ]
        ),
        level_id="L1",
    )
    pem.building_model.floor_plans.append(
        FloorPlanDefinition(
            id="F1",
            name="Level 1",
            level_id="L1",
            floor_type=FloorType.RESIDENTIAL,
            elevation_m=3.0,
            storey_height_m=3.0,
            boundary=Polygon2D(
                points=[Point2D(x=0, y=0), Point2D(x=12, y=0), Point2D(x=12, y=12), Point2D(x=0, y=12)]
            ),
            spaces=[stair],
        )
    )
    pem.structural_model.geometry.points.extend(
        [
            PointDefinition(id="A", x=0, y=6, z=3, level_id="L1"),
            PointDefinition(id="B", x=12, y=6, z=3, level_id="L1"),
        ]
    )
    pem.structural_model.members.members.append(
        StructuralMember(
            id="BM-1",
            member_type=MemberType.BEAM,
            name="Beam",
            section_id="B1",
            material_id="C",
            level_id="L1",
            start_point_id="A",
            end_point_id="B",
        )
    )
    result = CoordinationService().check(pem.building_model, pem.structural_model)
    assert any(item.code == "BEAM_THROUGH_OPENING" and item.severity == "WARNING" for item in result.conflicts)


def test_external_contract_and_qa_do_not_pass_without_software() -> None:
    contract = execution_contract(
        software="ETABS",
        version=None,
        execution_id="exec-1",
        executed=False,
        status="REQUIRES_LOCAL_SOFTWARE",
        model_reference=None,
        input_snapshot_id="snap",
        output_reference=None,
        warnings=[],
        errors=["ETABS automation requires a local Windows installation."],
        provenance={"source": "existing_csi_adapter"},
    )
    assert contract["executed"] is False
    qa = summarize_production_qa(
        [
            {"name": "architectural_completeness", "status": "PASS", "authority": "PEM"},
            {"name": "etabs_execution", "status": "REQUIRES_LOCAL_SOFTWARE", "authority": "EXTERNAL SOFTWARE RESULT", "executed": False},
        ]
    )
    assert qa["status"] == "UNAVAILABLE"
    assert qa["final_engineering_approval"] is False
    assert all(item["status"] == "NOT_AVAILABLE_IN_PEM" for item in detail_sheet_status())


def test_production_package_does_not_claim_external_success(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Production package"}).json()["project"]["id"]
    other_id = api_client.post("/api/v1/projects", json={"name": "Other project"}).json()["project"]["id"]
    before = build_pem_service().get_current_pem(UUID(other_id))
    assert before is not None
    untouched = before.model_dump(mode="json")
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Run the production package",
            "requires_approval": False,
            "parameters": {
                "operation": "production",
                "apply_to_pem": True,
                "architectural_brief": ARCH_BRIEF,
            },
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    workflow = body["output"]["structural_workflow"]
    assert workflow["pem"]["change"]["applied"] is True
    assert workflow["pem"]["change"]["approval_state"] == "PENDING"
    assert workflow["final_engineering_approval"] is False
    assert workflow["analysis"]["executed"] is False
    assert workflow["analysis"]["status"] == "REQUIRES_LOCAL_SOFTWARE"
    assert workflow["analysis"]["solver"] == "ETABS"
    assert {item["software"] for item in workflow["external_executions"]} == {"ETABS", "SAFE", "AUTOCAD"}
    assert all(item["executed"] is False for item in workflow["external_executions"])
    assert all(item["status"] == "REQUIRES_LOCAL_SOFTWARE" for item in workflow["external_executions"])
    assert workflow["qa"]["status"] != "PASS"
    assert workflow["qa"]["final_engineering_approval"] is False
    pem = build_pem_service().get_current_pem(UUID(project_id))
    assert pem is not None
    assert pem.building_model.floor_plans
    assert pem.structural_model.members.members
    assert {"A-001", "S-001", "S-101", "S-201", "S-202", "S-203"} <= set(workflow["drawings"]["sheet_numbers"])
    assert workflow["drawings"]["autocad_execution"] is False
    report = workflow["engineering_report"]
    assert report["15_learning_context"]["record_ids"] == []
    assert report["15_learning_context"]["produced_engineering_result"] is False
    assert report["16_pem_provenance"]["heading"] == "AUTHORITATIVE ENGINEERING INPUT"
    assert report["18_external_software_execution_records"]
    assert report["20_final_engineering_readiness"]["final_engineering_approval"] is False
    assert body["output"]["learning_overrides_pem"] is False
    assert body["output"]["learning_overrides_qa"] is False
    other = build_pem_service().get_current_pem(UUID(other_id))
    assert other is not None
    assert other.model_dump(mode="json") == untouched


def test_production_without_apply_does_not_mutate_the_pem(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "No write"}).json()["project"]["id"]
    before = build_pem_service().get_current_snapshot_meta(UUID(project_id))
    assert before is not None
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Describe the building",
            "requires_approval": False,
            "parameters": {
                "operation": "production",
                "apply_to_pem": False,
                "architectural_brief": ARCH_BRIEF,
            },
        },
    )
    assert response.status_code == 201, response.text
    workflow = response.json()["output"]["structural_workflow"]
    assert workflow["pem"]["change"]["applied"] is False
    assert workflow["qa"]["status"] != "PASS"
    after = build_pem_service().get_current_snapshot_meta(UUID(project_id))
    assert after is not None
    assert after.version == before.version
    assert str(after.id) == str(before.id)
