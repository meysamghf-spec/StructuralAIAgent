"""API integration tests — agent foundation endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)


def _seed_capabilities() -> None:
    repo = PostgresAgentCapabilityRepository()
    if repo.get_by_key("routing") is None:
        repo.create(key="routing", name="Routing")
    if repo.get_by_key("planning") is None:
        repo.create(key="planning", name="Planning")


def test_create_and_get_agent(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/agents",
        json={"key": "api-agent", "name": "API Agent", "description": "via API"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["key"] == "api-agent"
    assert body["status"] == "DRAFT"

    agent_id = body["id"]
    get_response = api_client.get(f"/api/v1/agents/{agent_id}")
    assert get_response.status_code == 200
    assert get_response.json()["name"] == "API Agent"


def test_list_agents(api_client: TestClient) -> None:
    api_client.post("/api/v1/agents", json={"key": "a1", "name": "A1"})
    api_client.post("/api/v1/agents", json={"key": "a2", "name": "A2"})
    response = api_client.get("/api/v1/agents")
    assert response.status_code == 200
    keys = {item["key"] for item in response.json()["agents"]}
    assert {"a1", "a2"}.issubset(keys)


def test_create_version_activate_and_prompts(api_client: TestClient) -> None:
    _seed_capabilities()
    agent = api_client.post(
        "/api/v1/agents",
        json={"key": "prompt-api-agent", "name": "Prompt API Agent"},
    ).json()
    agent_id = agent["id"]

    version_response = api_client.post(
        f"/api/v1/agents/{agent_id}/versions",
        json={
            "instructions": "System instructions",
            "capability_keys": ["routing"],
        },
        headers={"X-Actor-Id": "prompt-engineer"},
    )
    assert version_response.status_code == 201
    version_body = version_response.json()
    assert version_body["version"] == 1
    assert version_body["created_by"] == "prompt-engineer"
    assert len(version_body["capabilities"]) == 1

    prompt_response = api_client.post(
        f"/api/v1/agents/{agent_id}/versions/1/prompts",
        json={
            "name": "system",
            "template": "You are {{role}}",
            "variables_schema": {"role": "string"},
        },
        headers={"X-Actor-Id": "prompt-engineer"},
    )
    assert prompt_response.status_code == 201
    assert prompt_response.json()["version"] == 1

    prompt_v2 = api_client.post(
        f"/api/v1/agents/{agent_id}/versions/1/prompts",
        json={"name": "system", "template": "You are {{role}} v2"},
    )
    assert prompt_v2.status_code == 201
    assert prompt_v2.json()["version"] == 2

    list_prompts = api_client.get(f"/api/v1/agents/{agent_id}/versions/1/prompts")
    assert list_prompts.status_code == 200
    templates = list_prompts.json()["prompts"]
    assert len(templates) == 2
    assert templates[0]["template"] == "You are {{role}}"

    activate = api_client.post(f"/api/v1/agents/{agent_id}/versions/1/activate")
    assert activate.status_code == 200
    assert activate.json()["status"] == "ACTIVE"

    agent_after = api_client.get(f"/api/v1/agents/{agent_id}").json()
    assert agent_after["status"] == "ACTIVE"
    assert agent_after["current_version"] == 1


def test_only_one_active_version_via_api(api_client: TestClient) -> None:
    agent = api_client.post(
        "/api/v1/agents",
        json={"key": "dual-active", "name": "Dual Active"},
    ).json()
    agent_id = agent["id"]
    api_client.post(f"/api/v1/agents/{agent_id}/versions", json={"instructions": "v1"})
    api_client.post(f"/api/v1/agents/{agent_id}/versions", json={"instructions": "v2"})
    api_client.post(f"/api/v1/agents/{agent_id}/versions/1/activate")
    api_client.post(f"/api/v1/agents/{agent_id}/versions/2/activate")

    v1 = api_client.get(f"/api/v1/agents/{agent_id}/versions/1").json()
    v2 = api_client.get(f"/api/v1/agents/{agent_id}/versions/2").json()
    assert v1["status"] == "ARCHIVED"
    assert v2["status"] == "ACTIVE"


def test_agent_not_found_404(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/agents/{uuid4()}")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "AGENT_NOT_FOUND"


def test_duplicate_agent_key_409(api_client: TestClient) -> None:
    api_client.post("/api/v1/agents", json={"key": "dup", "name": "One"})
    response = api_client.post("/api/v1/agents", json={"key": "dup", "name": "Two"})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "AGENT_KEY_CONFLICT"


def test_create_agent_422_empty_key(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/agents", json={"key": "", "name": "Bad"})
    assert response.status_code == 422


def test_prompt_on_active_version_400(api_client: TestClient) -> None:
    agent = api_client.post(
        "/api/v1/agents",
        json={"key": "active-prompt-block", "name": "Active Prompt Block"},
    ).json()
    agent_id = agent["id"]
    api_client.post(f"/api/v1/agents/{agent_id}/versions", json={"instructions": "v1"})
    api_client.post(f"/api/v1/agents/{agent_id}/versions/1/activate")

    response = api_client.post(
        f"/api/v1/agents/{agent_id}/versions/1/prompts",
        json={"name": "system", "template": "blocked"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "AGENT_VERSION_IMMUTABLE"
