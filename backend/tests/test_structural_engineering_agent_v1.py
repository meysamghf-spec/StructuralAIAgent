"""Structural Engineering Agent v1: one project workflow, without invented results."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.application.exceptions import AgentNotExecutableError
from app.application.service_factory import (
    build_agent_builder_service,
    build_agent_runtime_service,
    build_file_ingestion_service,
    build_pem_service,
)
from app.application.structural_engineering_workflow import (
    normalize_engineering_brief,
    resolve_workflow_qa,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)

DEMO_BRIEF = {
    "project_type": "residential",
    "location": "demonstration site",
    "number_of_stories": 3,
    "structural_system": "reinforced concrete",
    "material": "concrete",
    "design_code": "ACI 318-25",
    "units": "SI",
    "plot_length_m": 22,
    "plot_width_m": 12,
    "frontage_m": 12,
    "residential_floor_count": 3,
    "parking_space_count": 4,
    "apartments_per_floor": 1,
    "bedrooms_per_apartment": 3,
    "has_piloti": True,
    "engineer_notes": "Canonical Structural Engineering Agent v1 demonstration.",
}


def test_brief_leaves_missing_values_unavailable() -> None:
    brief = normalize_engineering_brief({"engineering_brief": {"project_type": "residential"}})
    by_field = {item["field"]: item for item in brief["fields"]}
    assert by_field["project_type"]["origin"] == "USER_PROVIDED"
    assert by_field["loads"]["origin"] == "UNAVAILABLE"
    assert by_field["seismic_assumptions"]["value"] is None
    assert "Loads" in brief["unavailable"]


def test_qa_fails_a_completed_beam_check_and_does_not_pass_without_analysis() -> None:
    skipped = resolve_workflow_qa(analysis_executed=False, analysis_status=None, design_checks=[])
    assert skipped["status"] == "NOT_RUN"
    failed = resolve_workflow_qa(
        analysis_executed=True,
        analysis_status="SUCCESS",
        design_checks=[{"recognized": True, "status": "FAIL", "check_type": "BEAM_FLEXURE"}],
    )
    assert failed["status"] == "FAIL"
    missing_check = resolve_workflow_qa(
        analysis_executed=True,
        analysis_status="SUCCESS",
        design_checks=[],
    )
    assert missing_check["status"] == "NOT_APPLICABLE"


def test_incomplete_model_does_not_analyze(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Empty frame"}).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Run the structural workflow",
            "requires_approval": False,
            "parameters": {"operation": "analyze", "solver": "ETABS"},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    workflow = body["output"]["structural_workflow"]
    assert workflow["model_readiness"]["status"] == "NOT_READY"
    assert "support conditions" in workflow["engineer_message"]
    assert workflow["analysis"]["executed"] is False
    assert workflow["analysis"]["solver"] == "ETABS"
    assert workflow["analysis"]["status"] == "NOT_RUN"
    assert workflow["qa"]["status"] == "NOT_RUN"
    assert body["validation_status"] == "NOT_RUN"
    assert body["output"]["engineering_results_available"] is False
    assert "engineering_results" not in body["output"]
    assert workflow["final_engineering_approval"] is False


def test_named_solver_is_recorded_and_not_executed(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Named solver"}).json()["project"]["id"]
    _populate(project_id)
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Analyze in ETABS",
            "requires_approval": False,
            "parameters": {"operation": "analyze", "solver": "ETABS"},
        },
    )
    assert response.status_code == 201, response.text
    workflow = response.json()["output"]["structural_workflow"]
    analysis = workflow["analysis"]
    assert analysis["solver"] == "ETABS"
    assert analysis["requested"] is True
    assert analysis["available"] is False
    assert analysis["executed"] is False
    assert analysis["status"] == "REQUIRES_LOCAL_SOFTWARE"
    assert analysis["integration_execution_id"]
    assert workflow["qa"]["status"] == "NOT_RUN"
    assert "engineering_results" not in response.json()["output"]


def test_brief_without_apply_does_not_mutate_the_pem(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Read only brief"}).json()["project"]["id"]
    before = build_pem_service().get_current_pem(UUID(project_id))
    assert before is not None
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Plot 12m × 22m, 3 residential floors",
            "requires_approval": False,
            "parameters": {
                "operation": "prepare",
                "apply_to_pem": False,
                "engineering_brief": DEMO_BRIEF,
            },
        },
    )
    assert response.status_code == 201, response.text
    after = build_pem_service().get_current_pem(UUID(project_id))
    assert after is not None
    assert len(after.structural_model.members.members) == len(before.structural_model.members.members)
    assert response.json()["output"]["structural_workflow"]["pem"]["change"]["applied"] is False


def test_other_project_file_and_learning_do_not_enter_the_run(api_client: TestClient) -> None:
    project_a = api_client.post("/api/v1/projects", json={"name": "Workflow A"}).json()["project"]["id"]
    project_b = api_client.post("/api/v1/projects", json={"name": "Workflow B"}).json()["project"]["id"]
    uploaded = build_file_ingestion_service().ingest_upload(
        UUID(project_b),
        filename="other-project.txt",
        content=b"belongs to project b",
        content_type="text/plain",
        created_by="engineer",
    )
    rejected = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_a,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Validate the model",
            "requires_approval": False,
            "parameters": {
                "operation": "validate",
                "attachment_file_ids": [str(uploaded.id)],
            },
        },
    )
    assert rejected.status_code == 404

    created = api_client.post(
        f"/api/v1/projects/{project_b}/learning",
        json={
            "learning_scope": "PROJECT",
            "agent_id": "STRUCTURAL_ENGINEERING_AGENT",
            "engineering_reason": "Use 400 mm beams on every project.",
            "applicability": {"task_type": "structural_workflow"},
        },
    )
    assert created.status_code == 201, created.text
    record_id = created.json()["id"]
    approved = api_client.post(f"/api/v1/projects/{project_b}/learning/{record_id}/approve", json={})
    assert approved.status_code == 200, approved.text

    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_a,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Validate the model",
            "requires_approval": False,
            "parameters": {"operation": "validate"},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert record_id not in str(body["output"].get("learning_record_ids"))
    assert body["output"].get("learning_overrides_pem") is not True
    trace_ids = body["traceability_metadata"].get("learning_record_ids") or []
    assert record_id not in trace_ids


def test_other_account_cannot_run_the_workflow(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    owner = {"X-Actor-Id": "workflow-owner"}
    other = {"X-Actor-Id": "workflow-other"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Private workflow"},
        headers=owner,
    ).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Validate the model",
            "requires_approval": False,
            "parameters": {"operation": "validate"},
        },
        headers=other,
    )
    assert response.status_code in {403, 404}


def test_draft_structural_agent_cannot_execute(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Draft agent"}).json()["project"]["id"]
    repo = PostgresAgentCapabilityRepository()
    if repo.get_by_key("routing") is None:
        repo.create(key="routing", name="Routing", description="Route tasks")
    builder = build_agent_builder_service()
    detail = builder.create_agent(
        key=f"v1-draft-{project_id[:8]}",
        name="Draft structural agent",
        description="Not published",
        agent_type=EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT,
        project_id=UUID(project_id),
        instructions="Use the current PEM.",
        capability_keys=["routing"],
        created_by="v1-engineer",
        purpose="Structural workflow",
        engineering_domain="STRUCTURAL",
        task_types=["structural_workflow"],
        change_summary="Initial draft",
    )
    with pytest.raises(AgentNotExecutableError):
        build_agent_runtime_service().execute(
            AgentExecutionRequest(
                project_id=UUID(project_id),
                agent_definition_id=detail.definition.id,
                user_request="Run the structural workflow",
            ),
            actor_id="v1-engineer",
            account_id="v1-engineer",
        )


def test_canonical_demonstration_workflow(api_client: TestClient) -> None:
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Structural Engineering Agent v1 demo"},
    ).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_ENGINEERING_AGENT.value,
            "user_request": "Run structural engineering agent",
            "requires_approval": False,
            "parameters": {
                "operation": "workflow",
                "apply_to_pem": True,
                "engineering_brief": DEMO_BRIEF,
            },
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    workflow = body["output"]["structural_workflow"]
    trace = body["traceability_metadata"]
    pem = build_pem_service().get_current_pem(UUID(project_id))
    assert pem is not None
    assert pem.structural_model.members.members
    assert workflow["pem"]["change"]["applied"] is True
    assert workflow["pem"]["change"]["source"] == "BuildingDesignPipeline"
    assert workflow["pem"]["change"]["approval_state"] == "PENDING"
    assert workflow["final_engineering_approval"] is False
    assert trace["pem_snapshot_id"] == workflow["pem"]["snapshot_id"]
    assert trace["pem_version"] == workflow["pem"]["version"]
    assert workflow["model_readiness"]["status"] in {"READY", "PARTIAL"}
    assert workflow["analysis"]["executed"] is True
    assert workflow["analysis"]["status"] == "SUCCESS"
    assert workflow["analysis"]["solver"]
    assert "ETABS" not in str(workflow["analysis"]["solver"]).upper()
    recognized = [item for item in workflow["design_checks"] if item["recognized"]]
    assert recognized
    assert all(item["simplified"] is True for item in recognized)
    assert all(item["code"] == "ACI 318-25" for item in recognized)
    assert workflow["qa"]["status"] == "PASS"
    assert "stamped" in workflow["qa"]["reason"]
    drawings = workflow["drawings"]
    assert {"S-201", "S-202", "S-203"} <= set(drawings["sheet_numbers"])
    assert drawings["s301_generated"] is False
    assert drawings["s401_generated"] is False
    report = workflow["engineering_report"]
    for key in (
        "1_project_information",
        "2_engineering_brief",
        "3_pem",
        "7_analysis_method",
        "10_qa_status",
        "11_drawings",
        "12_assumptions",
        "13_limitations",
        "14_external_software",
        "15_traceability",
        "16_approval_status",
    ):
        assert key in report
    assert report["16_approval_status"]["final_engineering_approval"] is False
    assert any(item["origin"] == "ASSUMED" for item in report["12_assumptions"])
    assert body["output"]["learning_overrides_pem"] is False
    loads = next(item for item in workflow["engineering_brief"]["fields"] if item["field"] == "loads")
    assert loads["origin"] == "UNAVAILABLE"


def _populate(project_id: str) -> None:
    from app.application.service_factory import build_pem_model_service

    service = build_pem_model_service()
    project = UUID(project_id)
    service.update_geometry(project, sample_geometry(), summary="Geometry")
    service.update_materials(project, sample_materials(), summary="Materials")
    service.update_sections(project, sample_sections(), summary="Sections")
    service.update_members(project, sample_members(), summary="Members")
    service.update_supports(project, sample_supports(), summary="Supports")
    service.update_load_cases(project, sample_load_cases(), summary="Loads")
    service.update_load_combinations(project, sample_load_combinations(), summary="Combos")
