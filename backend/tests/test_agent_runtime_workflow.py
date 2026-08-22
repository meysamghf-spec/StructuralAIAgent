"""End-to-end agent runtime workflow tests."""

from fastapi.testclient import TestClient

from app.domain.models.agent import EngineeringAgentType


def _create_project(api_client: TestClient) -> str:
    response = api_client.post("/api/v1/projects", json={"name": "Workflow Project"})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_api_workflow_approve_agent_execution(api_client: TestClient) -> None:
    project_id = _create_project(api_client)

    execution_response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.STRUCTURAL_MODELING_AGENT.value,
            "user_request": "Publish updated model geometry",
        },
        headers={"X-Actor-Id": "engineer-1"},
    )
    assert execution_response.status_code == 201
    execution = execution_response.json()
    assert execution["user_view"]["progress"] == "awaiting_approval"
    assert execution["execution_status"] in {"WAITING_APPROVAL", "REQUIRES_HUMAN_APPROVAL"}

    approval_id = execution["approval_request_id"]
    approve_response = api_client.post(
        f"/api/v1/approvals/{approval_id}/approve",
        params={"project_id": project_id},
        json={"approver": "reviewer-1", "decision_note": "Approved"},
    )
    assert approve_response.status_code == 200

    final_response = api_client.get(f"/api/v1/agent-executions/{execution['id']}")
    assert final_response.status_code == 200
    final = final_response.json()
    assert final["execution_status"] == "COMPLETED"
    assert final["user_view"]["progress"] == "completed"
    assert final["traceability_metadata"].get("report_id") is not None


def test_api_workflow_reject_agent_execution(api_client: TestClient) -> None:
    project_id = _create_project(api_client)

    execution_response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.SEISMIC_AGENT.value,
            "user_request": "Apply revised seismic parameters",
        },
        headers={"X-Actor-Id": "engineer-1"},
    )
    execution = execution_response.json()
    approval_id = execution["approval_request_id"]

    reject_response = api_client.post(
        f"/api/v1/approvals/{approval_id}/reject",
        params={"project_id": project_id},
        json={
            "approver": "reviewer-1",
            "rejection_reason": "Needs peer review first",
        },
    )
    assert reject_response.status_code == 200

    final_response = api_client.get(f"/api/v1/agent-executions/{execution['id']}")
    final = final_response.json()
    assert final["execution_status"] == "CANCELLED"
    assert final["user_view"]["progress"] == "rejected"
    assert "peer review" in final["user_view"]["final_result"]
