"""API integration tests — agent execution endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.domain.models.agent import EngineeringAgentType


def _create_project(api_client: TestClient) -> str:
    response = api_client.post("/api/v1/projects", json={"name": "Agent Execution Project"})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_create_agent_with_agent_type(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/agents",
        json={
            "key": "runtime-analysis",
            "name": "Runtime Analysis Agent",
            "agent_type": EngineeringAgentType.ANALYSIS_AGENT.value,
            "configuration": {"discipline": "analysis"},
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["agent_type"] == EngineeringAgentType.ANALYSIS_AGENT.value
    assert body["configuration"]["discipline"] == "analysis"


def test_create_and_get_agent_execution(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.VALIDATION_AGENT.value,
            "user_request": "Validate the current design assumptions",
            "requires_approval": False,
        },
        headers={"X-Actor-Id": "api-engineer"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["execution_status"] == "COMPLETED"
    assert body["created_by"] == "api-engineer"
    assert body["user_view"]["progress"] == "completed"
    assert body["context_snapshot"]["project_name"] == "Agent Execution Project"

    execution_id = body["id"]
    get_response = api_client.get(f"/api/v1/agent-executions/{execution_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == execution_id


def test_list_agent_executions_by_project(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.REPORTING_AGENT.value,
            "user_request": "Generate a project summary report",
            "requires_approval": False,
        },
    )
    response = api_client.get(f"/api/v1/agent-executions?project_id={project_id}")
    assert response.status_code == 200
    assert len(response.json()["executions"]) == 1


def test_agent_execution_not_found_404(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/agent-executions/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AGENT_EXECUTION_NOT_FOUND"
