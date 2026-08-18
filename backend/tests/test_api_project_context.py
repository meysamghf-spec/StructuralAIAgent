"""API tests — project context assembly endpoint."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_api_get_project_context(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "API Context Project"}).json()
    project_id = project["project"]["id"]

    api_client.post(
        f"/api/v1/projects/{project_id}/memory",
        json={"memory_type": "ASSUMPTION", "content": "Wind speed 120 mph"},
    )

    response = api_client.get(f"/api/v1/projects/{project_id}/context")
    assert response.status_code == 200
    body = response.json()
    assert body["project_name"] == "API Context Project"
    assert body["pem_version"] == 1
    assert body["memory_total_count"] == 1
    assert body["memory_counts_by_type"]["ASSUMPTION"] == 1


def test_api_project_context_404(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/projects/{uuid4()}/context")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
