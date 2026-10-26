"""API tests — Human Approval Gate endpoints."""

from uuid import uuid4

from fastapi.testclient import TestClient


def test_api_create_and_list_pending_approval(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Approval API Project"}).json()
    project_id = project["project"]["id"]

    create_response = api_client.post(
        "/api/v1/approvals",
        json={
            "project_id": project_id,
            "requester": "engineer-1",
            "target_type": "MODEL_CHANGE",
            "target_action": "pem.update",
            "summary": "Publish updated PEM",
        },
    )
    assert create_response.status_code == 201
    request_id = create_response.json()["id"]

    pending_response = api_client.get(
        "/api/v1/approvals/pending",
        params={"project_id": project_id},
    )
    assert pending_response.status_code == 200
    assert len(pending_response.json()["requests"]) == 1
    assert pending_response.json()["requests"][0]["id"] == request_id


def test_api_approve_and_history(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Approval History Project"}).json()
    project_id = project["project"]["id"]

    request_id = api_client.post(
        "/api/v1/approvals",
        json={
            "project_id": project_id,
            "requester": "engineer-1",
            "target_type": "AGENT_ACTION",
            "target_action": "agent.activate",
            "summary": "Activate validation agent",
        },
    ).json()["id"]

    approve_response = api_client.post(
        f"/api/v1/approvals/{request_id}/approve",
        params={"project_id": project_id},
        json={"approver": "reviewer-1", "decision_note": "Approved for pilot use"},
        headers={"X-Actor-Id": "reviewer-1"},
    )
    assert approve_response.status_code == 200
    assert approve_response.json()["status"] == "APPROVED"
    assert approve_response.json()["approver"] == "reviewer-1"

    history_response = api_client.get(
        "/api/v1/approvals/history",
        params={"project_id": project_id, "approval_request_id": request_id},
    )
    assert history_response.status_code == 200
    event_types = [item["event_type"] for item in history_response.json()["events"]]
    assert event_types == ["CREATED", "APPROVED"]


def test_api_reject_approval(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Reject Project"}).json()
    project_id = project["project"]["id"]

    request_id = api_client.post(
        "/api/v1/approvals",
        json={
            "project_id": project_id,
            "requester": "engineer-1",
            "target_type": "DESIGN_DECISION",
            "target_action": "design.assumption.approve",
            "summary": "Approve higher drift",
        },
    ).json()["id"]

    reject_response = api_client.post(
        f"/api/v1/approvals/{request_id}/reject",
        params={"project_id": project_id},
        json={
            "approver": "reviewer-1",
            "rejection_reason": "Exceeds client criteria",
        },
        headers={"X-Actor-Id": "reviewer-1"},
    )
    assert reject_response.status_code == 200
    assert reject_response.json()["status"] == "REJECTED"


def test_api_cancel_approval(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Cancel Project"}).json()
    project_id = project["project"]["id"]

    request_id = api_client.post(
        "/api/v1/approvals",
        json={
            "project_id": project_id,
            "requester": "engineer-1",
            "target_type": "CONFIGURATION_CHANGE",
            "target_action": "unit.configuration.update",
            "summary": "Switch to SI units",
        },
    ).json()["id"]

    cancel_response = api_client.post(
        f"/api/v1/approvals/{request_id}/cancel",
        params={"project_id": project_id},
        json={"actor": "engineer-1", "reason": "Superseded by new request"},
        headers={"X-Actor-Id": "engineer-1"},
    )
    assert cancel_response.status_code == 200
    assert cancel_response.json()["status"] == "CANCELLED"


def test_api_approval_not_found(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "Missing Approval Project"}).json()
    project_id = project["project"]["id"]

    response = api_client.get(
        f"/api/v1/approvals/{uuid4()}",
        params={"project_id": project_id},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "APPROVAL_NOT_FOUND"


def _mk(api_client: TestClient, project_id: str, summary: str) -> str:
    return api_client.post(
        "/api/v1/approvals",
        json={"project_id": project_id, "requester": "e", "target_type": "DESIGN_DECISION",
              "target_action": "engineering_run", "summary": summary},
    ).json()["id"]


def test_double_approve_is_idempotent_and_conflicts_are_explained(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Idem"}).json()["project"]["id"]
    rid = _mk(api_client, project_id, "Run 1")
    url = f"/api/v1/approvals/{rid}/approve"
    first = api_client.post(url, params={"project_id": project_id}, json={"approver": "r1"})
    second = api_client.post(url, params={"project_id": project_id}, json={"approver": "r1"})
    assert first.status_code == 200 and second.status_code == 200
    assert second.json()["status"] == "APPROVED"
    # rejecting an already approved item is a real conflict with a clear bilingual message
    rej = api_client.post(f"/api/v1/approvals/{rid}/reject", params={"project_id": project_id},
                          json={"approver": "r1", "rejection_reason": "drift too high"})
    assert rej.status_code == 409
    assert "already approved" in rej.json()["error"]["message"]


def test_project_approval_summary_explains_blockers(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Sum"}).json()["project"]["id"]
    empty = api_client.get("/api/v1/approvals/summary", params={"project_id": project_id}).json()
    assert empty["project_approved"] is False and empty["blockers"][0]["code"] == "no_runs"
    rid = _mk(api_client, project_id, "Run 1")
    pending = api_client.get("/api/v1/approvals/summary", params={"project_id": project_id}).json()
    assert pending["state"] == "pending" and pending["blockers"][0]["fa"]
    api_client.post(f"/api/v1/approvals/{rid}/approve", params={"project_id": project_id}, json={"approver": "r1"})
    done = api_client.get("/api/v1/approvals/summary", params={"project_id": project_id}).json()
    assert done["project_approved"] is True and done["blockers"] == []
