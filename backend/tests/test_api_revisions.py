"""API integration tests — revision endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_list_and_get_revisions(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/projects", json={"name": "Rev Project"}).json()
    project_id = created["project"]["id"]

    pem = api_client.get(f"/api/v1/projects/{project_id}/pem/current").json()["pem"]
    pem["metadata"]["description"] = "updated"
    api_client.put(
        f"/api/v1/projects/{project_id}/pem",
        json={"pem": pem, "change_type": "PEM_UPDATE", "summary": "second"},
    )

    list_response = api_client.get(f"/api/v1/projects/{project_id}/revisions")
    assert list_response.status_code == 200
    revisions = list_response.json()["revisions"]
    assert len(revisions) == 2
    assert revisions[0]["change_type"] == "INITIAL"
    assert revisions[1]["change_type"] == "PEM_UPDATE"
    assert revisions[1]["before_snapshot_id"] is not None
    assert revisions[1]["after_snapshot_id"] is not None

    get_response = api_client.get(f"/api/v1/projects/{project_id}/revisions/2")
    assert get_response.status_code == 200
    assert get_response.json()["revision_number"] == 2


def test_get_revision_404(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/projects", json={"name": "Rev404"}).json()
    project_id = created["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}/revisions/99")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REVISION_NOT_FOUND"


def test_list_revisions_404_unknown_project(api_client: TestClient) -> None:
    response = api_client.get(f"/api/v1/projects/{uuid4()}/revisions")
    assert response.status_code == 404
