"""API tests — ValidationEngine endpoint."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_api_validate_project(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Validate Me"}).json()
    project_id = project["project"]["id"]

    response = api_client.post(f"/api/v1/projects/{project_id}/validate")
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == project_id
    assert body["overall_status"] == "REQUIRES_ENGINEER_REVIEW"


def test_api_validate_project_404(api_client: TestClient) -> None:
    response = api_client.post(f"/api/v1/projects/{uuid4()}/validate")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_NOT_FOUND"
