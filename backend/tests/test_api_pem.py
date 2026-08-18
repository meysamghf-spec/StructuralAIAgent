"""API integration tests — PEM endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def _create_project(api_client: TestClient, name: str = "PEM Project") -> dict:
    response = api_client.post("/api/v1/projects", json={"name": name})
    assert response.status_code == 201
    return response.json()


def test_get_current_pem_returns_defaults(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}/pem/current")
    assert response.status_code == 200
    body = response.json()
    assert body["version"] == 1
    assert body["is_current"] is True
    assert body["pem"]["code_configuration"]["governing_building_code"]["edition"] == "IBC 2024"
    assert body["pem"]["unit_configuration"]["system"] == "US_CUSTOMARY"


def test_put_pem_increments_version_and_creates_revision(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    before_snapshot_id = created["snapshot_id"]

    current = api_client.get(f"/api/v1/projects/{project_id}/pem/current").json()
    pem = current["pem"]
    pem["metadata"]["description"] = "Updated via API"

    response = api_client.put(
        f"/api/v1/projects/{project_id}/pem",
        json={
            "pem": pem,
            "change_type": "PEM_UPDATE",
            "summary": "Updated project metadata",
        },
        headers={"X-Actor-Id": "api-tester"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["pem_version"] == 2
    assert body["before_snapshot_id"] == before_snapshot_id
    assert body["revision"]["change_type"] == "PEM_UPDATE"
    assert body["revision"]["created_by"] == "api-tester"
    assert body["revision"]["before_snapshot_id"] == before_snapshot_id
    assert body["revision"]["after_snapshot_id"] == body["snapshot_id"]


def test_historical_pem_version_immutable(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    original = api_client.get(f"/api/v1/projects/{project_id}/pem/current").json()

    pem = original["pem"]
    pem["metadata"]["description"] = "Version 2"
    api_client.put(
        f"/api/v1/projects/{project_id}/pem",
        json={
            "pem": pem,
            "change_type": "PEM_UPDATE",
            "summary": "v2",
        },
    )

    v1 = api_client.get(f"/api/v1/projects/{project_id}/pem/versions/1").json()
    assert v1["pem"]["metadata"]["description"] != "Version 2"
    assert v1["version"] == 1
    assert v1["is_current"] is False

    current = api_client.get(f"/api/v1/projects/{project_id}/pem/current").json()
    assert current["version"] == 2
    assert current["pem"]["metadata"]["description"] == "Version 2"


def test_list_pem_versions(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    pem = api_client.get(f"/api/v1/projects/{project_id}/pem/current").json()["pem"]
    pem["metadata"]["description"] = "v2"
    api_client.put(
        f"/api/v1/projects/{project_id}/pem",
        json={"pem": pem, "change_type": "PEM_UPDATE", "summary": "v2"},
    )
    response = api_client.get(f"/api/v1/projects/{project_id}/pem/versions")
    assert response.status_code == 200
    assert response.json()["versions"] == [1, 2]


def test_get_pem_version_404(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}/pem/versions/99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PEM_VERSION_NOT_FOUND"


def test_get_current_pem_404_unknown_project(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/projects/{uuid4()}/pem/current")
    assert response.status_code == 404


def test_put_pem_project_mismatch_400(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    pem = api_client.get(f"/api/v1/projects/{project_id}/pem/current").json()["pem"]
    pem["project_id"] = str(uuid4())
    response = api_client.put(
        f"/api/v1/projects/{project_id}/pem",
        json={"pem": pem, "change_type": "PEM_UPDATE", "summary": "bad"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PEM_PROJECT_MISMATCH"


def test_put_pem_initial_change_type_400(api_client: TestClient) -> None:
    created = _create_project(api_client)
    project_id = created["project"]["id"]
    pem = api_client.get(f"/api/v1/projects/{project_id}/pem/current").json()["pem"]
    response = api_client.put(
        f"/api/v1/projects/{project_id}/pem",
        json={"pem": pem, "change_type": "INITIAL", "summary": "bad"},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_CHANGE_TYPE"
