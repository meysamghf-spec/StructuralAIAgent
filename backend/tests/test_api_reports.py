"""API tests — engineering reporting endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_api_create_generate_and_get_report(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Report API Project"}).json()
    project_id = project["project"]["id"]

    create_response = api_client.post(
        "/api/v1/reports",
        json={
            "project_id": project_id,
            "report_type": "PROJECT_SUMMARY",
            "created_by": "engineer-1",
        },
    )
    assert create_response.status_code == 201
    report_id = create_response.json()["id"]

    generate_response = api_client.post(
        f"/api/v1/reports/{report_id}/generate",
        params={"project_id": project_id},
        json={"report_type": "PROJECT_SUMMARY", "requested_by": "engineer-1"},
    )
    assert generate_response.status_code == 200
    assert generate_response.json()["version"] == 1

    get_response = api_client.get(
        f"/api/v1/reports/{report_id}",
        params={"project_id": project_id},
    )
    assert get_response.status_code == 200
    assert get_response.json()["current_version"] == 1


def test_api_list_reports(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Report List Project"}).json()
    project_id = project["project"]["id"]

    api_client.post(
        "/api/v1/reports",
        json={"project_id": project_id, "report_type": "VALIDATION"},
    )

    list_response = api_client.get(
        "/api/v1/reports",
        params={"project_id": project_id},
    )
    assert list_response.status_code == 200
    assert len(list_response.json()["reports"]) == 1


def test_api_report_traceability(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Report Trace API"}).json()
    project_id = project["project"]["id"]

    report_id = api_client.post(
        "/api/v1/reports",
        json={"project_id": project_id, "report_type": "PROJECT_SUMMARY"},
    ).json()["id"]

    api_client.post(
        f"/api/v1/reports/{report_id}/generate",
        params={"project_id": project_id},
        json={"report_type": "PROJECT_SUMMARY"},
    )

    trace_response = api_client.get(
        f"/api/v1/reports/{report_id}/traceability",
        params={"project_id": project_id},
    )
    assert trace_response.status_code == 200
    assert "chain_summary" in trace_response.json()


def test_api_report_not_found(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Missing Report"}).json()
    project_id = project["project"]["id"]

    response = api_client.get(
        f"/api/v1/reports/{uuid4()}",
        params={"project_id": project_id},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "REPORT_NOT_FOUND"
