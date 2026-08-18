"""API integration tests — project memory endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(api_client: TestClient, name: str = "Memory API Project") -> str:
    response = api_client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_api_create_list_get_by_type_and_delete_memory(api_client: TestClient) -> None:
    project_id = _create_project(api_client)

    create_response = api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={
            "memory_type": "DECISION",
            "content": "Adopt AISC 360-16 for steel design.",
            "source_type": "conversation",
            "confidence": 0.9,
            "metadata": {"code": "AISC"},
            "created_by": "lead-engineer",
        },
    )
    assert create_response.status_code == 201
    body = create_response.json()
    assert body["memory_type"] == "DECISION"
    assert body["created_by"] == "lead-engineer"
    memory_id = body["id"]

    api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={
            "memory_type": "ASSUMPTION",
            "content": "Soil bearing capacity 4000 psf.",
        },
    )

    list_response = api_client.get(f"/api/v1/projects/{project_id}/memory")
    assert list_response.status_code == 200
    assert len(list_response.json()["memories"]) == 2

    type_response = api_client.get(
        f"/api/v1/projects/{project_id}/memory/type/DECISION",
    )
    assert type_response.status_code == 200
    assert len(type_response.json()["memories"]) == 1
    assert type_response.json()["memories"][0]["id"] == memory_id

    get_response = api_client.get(
        f"/api/v1/projects/{project_id}/memory/{memory_id}",
    )
    assert get_response.status_code == 200
    assert get_response.json()["content"] == "Adopt AISC 360-16 for steel design."

    delete_response = api_client.delete(
        f"/api/v1/projects/{project_id}/memory/{memory_id}",
    )
    assert delete_response.status_code == 204

    missing_response = api_client.get(
        f"/api/v1/projects/{project_id}/memory/{memory_id}",
    )
    assert missing_response.status_code == 404
    assert missing_response.json()["error"]["code"] == "PROJECT_MEMORY_NOT_FOUND"


def test_api_project_memory_isolation(api_client: TestClient) -> None:
    project_a = _create_project(api_client, "Memory Iso A")
    project_b = _create_project(api_client, "Memory Iso B")

    created = api_client.post(
        f"/api/v1/projects/{project_a}/memory",
        json={"memory_type": "REQUIREMENT", "content": "Project A only"},
    ).json()
    memory_id = created["id"]

    assert api_client.get(f"/api/v1/projects/{project_b}/memory").json()["memories"] == []
    assert api_client.get(f"/api/v1/projects/{project_b}/memory/{memory_id}").status_code == 404
    assert (
        api_client.delete(f"/api/v1/projects/{project_b}/memory/{memory_id}").status_code
        == 404
    )


def test_api_unknown_project_memory(api_client: TestClient) -> None:
    missing_project = uuid4()
    response = api_client.get(f"/api/v1/projects/{missing_project}/memory")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"


def test_api_memory_type_route_not_captured_by_memory_id(api_client: TestClient) -> None:
    project_id = _create_project(api_client, "Route Order Project")

    response = api_client.get(f"/api/v1/projects/{project_id}/memory/type/ASSUMPTION")
    assert response.status_code == 200
    assert response.json()["memories"] == []


def test_api_filter_memories_by_source_and_type(api_client: TestClient) -> None:
    project_id = _create_project(api_client, "Filter Memory Project")
    source_id = str(uuid4())

    api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={
            "memory_type": "DECISION",
            "content": "Linked to file",
            "source_type": "file",
            "source_id": source_id,
        },
    )
    api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={
            "memory_type": "ASSUMPTION",
            "content": "Also linked to file",
            "source_type": "file",
            "source_id": source_id,
        },
    )
    api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={
            "memory_type": "DECISION",
            "content": "Unlinked decision",
            "source_type": "conversation",
        },
    )

    filtered = api_client.get(
        f"/api/v1/projects/{project_id}/memory",
        params={
            "source_type": "file",
            "source_id": source_id,
            "memory_type": "DECISION",
        },
    )
    assert filtered.status_code == 200
    memories = filtered.json()["memories"]
    assert len(memories) == 1
    assert memories[0]["content"] == "Linked to file"


def test_api_get_project_memory_context(api_client: TestClient) -> None:
    project_id = _create_project(api_client, "Context API Project")

    api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={"memory_type": "REQUIREMENT", "content": "Req 1"},
    )
    api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={"memory_type": "DESIGN_CHOICE", "content": "Choice 1"},
    )

    response = api_client.get(f"/api/v1/projects/{project_id}/memory/context")
    assert response.status_code == 200
    body = response.json()
    assert body["total_count"] == 2
    assert body["counts_by_type"] == {"REQUIREMENT": 1, "DESIGN_CHOICE": 1}
    assert len(body["memories"]) == 2


def test_api_context_route_not_captured_by_memory_id(api_client: TestClient) -> None:
    project_id = _create_project(api_client, "Context Route Project")
    response = api_client.get(f"/api/v1/projects/{project_id}/memory/context")
    assert response.status_code == 200
    assert response.json()["total_count"] == 0


def test_api_source_filter_project_isolation(api_client: TestClient) -> None:
    project_a = _create_project(api_client, "Source Iso A")
    project_b = _create_project(api_client, "Source Iso B")
    source_id = str(uuid4())

    api_client.post(
        f"/api/v1/projects/{project_a}/memory",
        json={
            "memory_type": "DECISION",
            "content": "Project A source memory",
            "source_type": "file",
            "source_id": source_id,
        },
    )

    response = api_client.get(
        f"/api/v1/projects/{project_b}/memory",
        params={"source_type": "file", "source_id": source_id},
    )
    assert response.status_code == 200
    assert response.json()["memories"] == []
