"""API integration tests for Agent Builder endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)


def _seed_capabilities() -> None:
    repo = PostgresAgentCapabilityRepository()
    if repo.get_by_key("routing") is None:
        repo.create(key="routing", name="Routing")


def _create_project(api_client: TestClient) -> str:
    response = api_client.post("/api/v1/projects", json={"name": "Builder API Project"})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_builder_create_validate_test_flow(api_client: TestClient) -> None:
    _seed_capabilities()
    project_id = _create_project(api_client)

    create_response = api_client.post(
        "/api/v1/agents/builder",
        json={
            "key": "api-builder-agent",
            "name": "API Builder Assistant",
            "agent_type": "VALIDATION_AGENT",
            "project_id": project_id,
            "instructions": "Validate project readiness.",
            "capability_keys": ["routing"],
        },
        headers={"X-Actor-Id": "builder-engineer"},
    )
    assert create_response.status_code == 201
    body = create_response.json()
    agent_id = body["agent"]["id"]
    version = body["version"]["version"]
    assert body["version"]["status"] == "DRAFT"

    validate_response = api_client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/validate",
    )
    assert validate_response.status_code == 200
    assert validate_response.json()["valid"] is True

    test_response = api_client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/test",
        json={
            "project_id": project_id,
            "user_request": "Validate this project",
        },
        headers={"X-Actor-Id": "builder-engineer"},
    )
    assert test_response.status_code == 200
    assert test_response.json()["result"]["execution_status"] == "COMPLETED"

    publish_response = api_client.post(
        f"/api/v1/agents/{agent_id}/versions/{version}/publish",
        json={"project_id": project_id},
        headers={"X-Actor-Id": "builder-engineer"},
    )
    assert publish_response.status_code == 200
    approval_id = publish_response.json()["approval_request_id"]
    assert approval_id is not None

    approve_response = api_client.post(
        f"/api/v1/approvals/{approval_id}/approve?project_id={project_id}",
        json={"approver": "lead-engineer"},
    )
    assert approve_response.status_code == 200

    agent_response = api_client.get(f"/api/v1/agents/{agent_id}")
    assert agent_response.status_code == 200
    assert agent_response.json()["current_version"] == version
    assert agent_response.json()["status"] == "ACTIVE"


def test_list_capabilities(api_client: TestClient) -> None:
    _seed_capabilities()
    response = api_client.get("/api/v1/agents/capabilities")
    assert response.status_code == 200
    assert len(response.json()) >= 1


def test_builder_agent_not_found(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/agents/{uuid4()}/builder?version=1")
    assert response.status_code == 404
