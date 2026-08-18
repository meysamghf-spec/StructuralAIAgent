"""API integration tests — project endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_create_project_returns_201_with_initial_revision(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/projects",
        json={"name": "Tower A", "description": "Test tower"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["project"]["name"] == "Tower A"
    assert body["project"]["description"] == "Test tower"
    assert body["pem_version"] == 1
    assert body["revision"]["revision_number"] == 1
    assert body["revision"]["change_type"] == "INITIAL"
    assert body["revision"]["after_snapshot_id"] == body["snapshot_id"]


def test_create_project_with_x_actor_id(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/projects",
        json={"name": "Actor Project"},
        headers={"X-Actor-Id": "engineer-1"},
    )
    assert response.status_code == 201
    assert response.json()["revision"]["created_by"] == "engineer-1"


def test_list_projects(api_client: TestClient) -> None:
    api_client.post("/api/v1/projects", json={"name": "P1"})
    api_client.post("/api/v1/projects", json={"name": "P2"})
    response = api_client.get("/api/v1/projects")
    assert response.status_code == 200
    names = {p["name"] for p in response.json()["projects"]}
    assert names == {"P1", "P2"}


def test_get_project_by_id(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/projects", json={"name": "Lookup"}).json()
    project_id = created["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}")
    assert response.status_code == 200
    assert response.json()["name"] == "Lookup"


def test_get_project_404(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/projects/{uuid4()}")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "PROJECT_NOT_FOUND"


def test_create_project_422_empty_name(api_client: TestClient) -> None:
    response = api_client.post("/api/v1/projects", json={"name": ""})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"
