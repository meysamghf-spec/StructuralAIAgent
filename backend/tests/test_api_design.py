"""API integration tests — design engine endpoints."""

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


def _create_project(api_client: TestClient, name: str = "Design API Project") -> str:
    response = api_client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()["project"]["id"]


def _populate_model(api_client: TestClient, project_id: str) -> None:
    headers = {"X-Actor-Id": "design-tester"}
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


def test_api_run_design_empty_project_model_not_ready(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    response = api_client.post(
        "/api/v1/engineering/design/run",
        json={"project_id": project_id, "design_type": "steel_member"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "MODEL_NOT_READY"
    assert body["code_edition"] == "AISC 360-22"
    assert body["id"] is not None


def test_api_run_design_configured_model_requires_analysis(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    _populate_model(api_client, project_id)
    response = api_client.post(
        "/api/v1/engineering/design/run",
        json={"project_id": project_id, "design_type": "CONCRETE_BEAM"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "REQUIRES_ANALYSIS"


def test_api_design_readiness_and_runs(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    run = api_client.post(
        "/api/v1/engineering/design/run",
        json={"project_id": project_id, "design_type": "STEEL_BEAM"},
    ).json()

    readiness = api_client.get(f"/api/v1/engineering/design/{project_id}/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["ready_for_design"] is False

    listed = api_client.get(f"/api/v1/engineering/design/{project_id}/runs")
    assert listed.status_code == 200
    assert len(listed.json()["runs"]) == 1

    fetched = api_client.get(f"/api/v1/engineering/design/{project_id}/runs/{run['id']}")
    assert fetched.status_code == 200


def test_api_orchestration_design_run(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    response = api_client.post(
        "/api/v1/orchestration/execute",
        json={
            "task_type": "engineering.design.run",
            "project_id": project_id,
            "payload": {"design_type": "CONCRETE_BEAM"},
        },
    )
    assert response.status_code == 200
    assert response.json()["route"] == "ENGINE"
    assert response.json()["output"]["status"] == "MODEL_NOT_READY"


def test_api_design_unknown_project(api_client: TestClient) -> None:
    response = api_client.post(
        "/api/v1/engineering/design/run",
        json={"project_id": str(uuid4()), "design_type": "CONCRETE_BEAM"},
    )
    assert response.status_code == 404
