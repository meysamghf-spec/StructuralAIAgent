"""Phase P: the PEM drawing set is readable, project-scoped, and not invented."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient


def test_current_drawing_set_is_tied_to_the_pem_snapshot(api_client: TestClient) -> None:
    created = api_client.post("/api/v1/projects", json={"name": "Drawing set"}).json()
    project_id = created["project"]["id"]
    pem = api_client.get(f"/api/v1/projects/{project_id}/pem/current")
    assert pem.status_code == 200
    current = pem.json()

    response = api_client.get(f"/api/v1/projects/{project_id}/drawing-set")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["project_id"] == project_id
    assert body["pem_snapshot_id"] == current["snapshot_id"]
    assert body["pem_version"] == current["version"]
    numbers = {sheet["sheet_number"] for sheet in body["sheets"]}
    assert {"S-001", "S-201", "S-202", "S-203"} <= numbers
    assert numbers.isdisjoint({"S-301", "S-401"})
    pending = {sheet["sheet_number"]: sheet for sheet in body["pending_sheets"]}
    assert pending["S-301"]["availability"] == "NOT_GENERATED"
    assert pending["S-401"]["availability"] == "NOT_GENERATED"
    schedules = {
        sheet["schedule_family"]: sheet
        for sheet in body["sheets"]
        if sheet["schedule_family"] in {"S-201", "S-202", "S-203"}
    }
    assert schedules["S-201"]["availability"] == "NOT_AVAILABLE"
    assert schedules["S-201"]["missing_data"]


def test_drawing_set_pdf_is_the_current_project_document(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Drawing pdf"}).json()["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}/drawing-set/pdf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert f"drawing-set-{project_id}-v" in response.headers["content-disposition"]


def test_drawing_set_does_not_cross_projects(api_client: TestClient) -> None:
    first = api_client.post("/api/v1/projects", json={"name": "Set A"}).json()["project"]["id"]
    second = api_client.post("/api/v1/projects", json={"name": "Set B"}).json()["project"]["id"]
    first_body = api_client.get(f"/api/v1/projects/{first}/drawing-set").json()
    second_body = api_client.get(f"/api/v1/projects/{second}/drawing-set").json()
    assert first_body["project_id"] == first
    assert second_body["project_id"] == second
    assert first_body["pem_snapshot_id"] != second_body["pem_snapshot_id"]
    assert first_body["drawing_set_id"] != second_body["drawing_set_id"]


def test_other_account_cannot_read_a_project_drawing_set(
    api_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    owner = {"X-Actor-Id": "drawing-owner"}
    other = {"X-Actor-Id": "drawing-other"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Private drawings"},
        headers=owner,
    ).json()["project"]["id"]
    response = api_client.get(f"/api/v1/projects/{project_id}/drawing-set", headers=other)
    assert response.status_code in {403, 404}
    pdf = api_client.get(f"/api/v1/projects/{project_id}/drawing-set/pdf", headers=other)
    assert pdf.status_code in {403, 404}
    missing = api_client.get(f"/api/v1/projects/{uuid4()}/drawing-set", headers=owner)
    assert missing.status_code == 404
