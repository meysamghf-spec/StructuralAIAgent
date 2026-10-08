"""Phase T: one project keeps the PEM, QA, and drawing set on the same snapshot.

This does not claim that ETABS ran or that S-301 and S-401 exist.
"""

from fastapi.testclient import TestClient

from app.domain.models.agent import EngineeringAgentType


def test_project_acceptance_keeps_authority_on_the_current_pem(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "MVP acceptance"}).json()["project"]["id"]
    current = api_client.get(f"/api/v1/projects/{project_id}/pem/current")
    assert current.status_code == 200
    pem = current.json()

    analysis = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.ANALYSIS_AGENT.value,
            "user_request": "Run lateral drift analysis",
            "requires_approval": False,
            "parameters": {
                "analysis_type": "LATERAL_DRIFT",
                "pem_version": 99,
                "allow_missing_inputs": True,
            },
        },
    )
    assert analysis.status_code == 201, analysis.text
    analysis_trace = analysis.json()["traceability_metadata"]
    assert analysis_trace["pem_snapshot_id"] == pem["snapshot_id"]
    assert analysis_trace["pem_version"] == pem["version"]
    assert analysis_trace["pem_version"] != 99
    assert analysis.json()["validation_status"] == "NOT_RUN"
    assert analysis_trace["qa_status"] == "NOT_RUN"
    assert analysis_trace["engineering_results_available"] is False
    assert analysis.json()["output"].get("learning_overrides_pem") is not True
    assert analysis.json()["output"].get("outputs", {}).get("engineering_results") is None

    design = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.CONCRETE_DESIGN_AGENT.value,
            "user_request": "Run concrete member design",
            "requires_approval": False,
            "parameters": {"design_type": "CONCRETE_MEMBER", "allow_missing_inputs": True},
        },
    )
    assert design.status_code == 201, design.text
    design_body = design.json()
    design_trace = design_body["traceability_metadata"]
    assert design_body["validation_status"] == "NOT_RUN"
    assert design_trace["qa_status"] == "NOT_RUN"
    assert design_trace["pem_snapshot_id"] == pem["snapshot_id"]
    assert design_trace["engineering_design_results_available"] is False
    assert design_body["output"].get("learning_overrides_pem") is not True

    drawing = api_client.get(f"/api/v1/projects/{project_id}/drawing-set")
    assert drawing.status_code == 200, drawing.text
    drawing_body = drawing.json()
    assert drawing_body["project_id"] == project_id
    assert drawing_body["pem_snapshot_id"] == pem["snapshot_id"]
    assert drawing_body["pem_version"] == pem["version"]
    numbers = {sheet["sheet_number"] for sheet in drawing_body["sheets"]}
    assert {"S-201", "S-202", "S-203"} <= numbers
    assert numbers.isdisjoint({"S-301", "S-401"})
    pending = {sheet["sheet_number"] for sheet in drawing_body["pending_sheets"]}
    assert {"S-301", "S-401"} <= pending

    pdf = api_client.get(f"/api/v1/projects/{project_id}/drawing-set/pdf")
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")
    assert project_id in pdf.headers["content-disposition"]
