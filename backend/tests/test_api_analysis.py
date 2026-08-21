"""API integration tests — analysis engine endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient

from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _create_project(api_client: TestClient, name: str = "Analysis API Project") -> str:
    response = api_client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def _populate_model(api_client: TestClient, project_id: str) -> None:
    headers = {"X-Actor-Id": "analysis-tester"}
    api_client.put(
        f"/api/v1/projects/{project_id}/model/geometry",
        json={"summary": "Geometry", "geometry": sample_geometry().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/materials",
        json={"summary": "Materials", "materials": sample_materials().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/sections",
        json={"summary": "Sections", "sections": sample_sections().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/members",
        json={"summary": "Members", "members": sample_members().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/supports",
        json={
            "summary": "Supports",
            "supports": [item.model_dump(mode="json") for item in sample_supports()],
        },
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/load-cases",
        json={
            "summary": "Loads",
            "load_cases": [item.model_dump(mode="json") for item in sample_load_cases()],
        },
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/load-combinations",
        json={
            "summary": "Combos",
            "load_combinations": [item.model_dump(mode="json") for item in sample_load_combinations()],
        },
        headers=headers,
    )


def test_api_run_analysis_empty_project_model_not_ready(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    response = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={"project_id": project_id, "analysis_type": "STATIC"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "MODEL_NOT_READY"
    assert body["id"] is not None


def test_api_run_analysis_configured_model_requires_solver(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    _populate_model(api_client, project_id)
    response = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={"project_id": project_id, "analysis_type": "STATIC"},
        headers={"X-Actor-Id": "api-tester"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "REQUIRES_SOLVER"
    assert body["capability_status"] == "REQUIRES_SOLVER"
    assert body["outputs"]["engineering_results_available"] is False


def test_api_list_and_get_analysis_runs(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    run = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={"project_id": project_id, "analysis_type": "MODAL"},
    ).json()

    listed = api_client.get(f"/api/v1/engineering/analysis/{project_id}/runs")
    assert listed.status_code == 200
    assert len(listed.json()["runs"]) == 1

    fetched = api_client.get(f"/api/v1/engineering/analysis/{project_id}/runs/{run['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["analysis_type"] == "MODAL"


def test_api_analysis_readiness(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    response = api_client.get(f"/api/v1/engineering/analysis/{project_id}/readiness")
    assert response.status_code == 200
    assert response.json()["ready_for_solver"] is False


def test_api_load_combinations_from_structural_model(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    _populate_model(api_client, project_id)
    response = api_client.get(f"/api/v1/engineering/analysis/{project_id}/load-combinations")
    assert response.status_code == 200
    body = response.json()
    assert body["load_combination_count"] == 1


def test_api_orchestration_analysis_run(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    response = api_client.post(
        "/api/v1/orchestration/execute",
        json={
            "task_type": "engineering.analysis.run",
            "project_id": project_id,
            "payload": {"analysis_type": "STATIC"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["route"] == "ENGINE"
    assert body["output"]["status"] == "MODEL_NOT_READY"


def test_api_analysis_unknown_project(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={"project_id": str(uuid4()), "analysis_type": "STATIC"},
    )
    assert response.status_code == 404
