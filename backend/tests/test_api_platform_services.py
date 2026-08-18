"""API tests — integrations, AI, orchestration, engineering."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_api_list_integration_adapters(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/integrations/adapters")
    assert response.status_code == 200
    assert len(response.json()) == 4


def test_api_ai_complete(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/ai/complete",
        json={
            "model": "stub-default",
            "messages": [{"role": "user", "content": "Check drift"}],
        },
    )
    assert response.status_code == 200
    assert response.json()["provider"] == "STUB"


def test_api_orchestration_validate(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Orch Project"}).json()
    project_id = project["project"]["id"]
    response = api_client.post(
        "/api/v1/orchestration/execute",
        json={"task_type": "project.validate", "project_id": project_id},
    )
    assert response.status_code == 200
    assert response.json()["route"] == "VALIDATION"


def test_api_run_analysis(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Analysis Project"}).json()
    project_id = project["project"]["id"]
    response = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={"project_id": project_id, "analysis_type": "linear_static"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "NOT_IMPLEMENTED"


def test_api_run_design(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Design Project"}).json()
    project_id = project["project"]["id"]
    response = api_client.post(
        "/api/v1/engineering/design/run",
        json={"project_id": project_id, "design_type": "steel_member"},
    )
    assert response.status_code == 200
    assert response.json()["code_edition"] == "AISC 360-22"


def test_api_integration_execute(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "ETABS Project"}).json()
    project_id = project["project"]["id"]
    response = api_client.post(
        "/api/v1/integrations/execute",
        json={
            "project_id": project_id,
            "software": "ETABS",
            "operation": "STATUS",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REQUIRES_LOCAL_SOFTWARE"


def test_api_analysis_unknown_project(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={"project_id": str(uuid4()), "analysis_type": "linear_static"},
    )
    assert response.status_code == 404
