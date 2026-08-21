"""API integration tests — project engineering model endpoints."""

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


def _create_project(api_client: TestClient, name: str = "Model API Project") -> dict:
    response = api_client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_get_current_model_returns_structural_model(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}/model")
    assert response.status_code == 200
    body = response.json()
    assert body["pem_version"] == 1
    assert "structural_model" in body
    assert body["structural_model"]["geometry"]["levels"] == []


def test_get_model_summary(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}/model/summary")
    assert response.status_code == 200
    body = response.json()
    assert body["level_count"] == 0
    assert body["validation_status"] == "PASS"


def test_validate_model_endpoint(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    response = api_client.post(f"/api/v1/projects/{project_id}/model/validate")
    assert response.status_code == 200
    assert response.json()["overall_status"] == "PASS"


def test_update_geometry_creates_revision(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    response = api_client.put(
        f"/api/v1/projects/{project_id}/model/geometry",
        json={
            "summary": "Initial geometry",
            "geometry": sample_geometry().model_dump(mode="json"),
        },
        headers={"X-Actor-Id": "api-tester"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pem_version"] == 2
    assert body["revision_number"] == 2
    assert body["validation"]["overall_status"] == "PASS"


def test_update_geometry_rejects_invalid_references(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    response = api_client.put(
        f"/api/v1/projects/{project_id}/model/geometry",
        json={
            "summary": "Bad geometry",
            "geometry": {
                "grids": [],
                "levels": [],
                "points": [],
                "lines": [
                    {
                        "id": "ln-bad",
                        "start_point_id": "missing",
                        "end_point_id": "also-missing",
                    }
                ],
                "areas": [],
            },
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PEM_VALIDATION_FAILED"


def test_full_model_crud_flow(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    headers = {"X-Actor-Id": "api-tester"}

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
        json={"summary": "Supports", "supports": [s.model_dump(mode="json") for s in sample_supports()]},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/load-cases",
        json={
            "summary": "Load cases",
            "load_cases": [c.model_dump(mode="json") for c in sample_load_cases()],
        },
        headers=headers,
    )
    response = api_client.put(
        f"/api/v1/projects/{project_id}/model/load-combinations",
        json={
            "summary": "Combinations",
            "load_combinations": [c.model_dump(mode="json") for c in sample_load_combinations()],
        },
        headers=headers,
    )
    assert response.status_code == 200

    summary = api_client.get(f"/api/v1/projects/{project_id}/model/summary").json()
    assert summary["member_count"] == 1
    assert summary["load_combination_count"] == 1


def test_model_endpoints_require_existing_project(api_client: TestClient) -> None:
    missing = uuid4()
    assert api_client.get(f"/api/v1/projects/{missing}/model").status_code == 404
