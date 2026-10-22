"""Unified chat endpoint tests."""

from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient


def _register(api_client: TestClient) -> str:
    email = f"chat-{uuid.uuid4().hex}@example.com"
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _project(api_client: TestClient, token: str) -> str:
    response = api_client.post(
        "/api/v1/projects",
        json={"name": "Chat API Project"},
        headers=_headers(token),
    )
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_chat_requires_authentication(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    response = api_client.post("/api/v1/chat", json={"message": "Hello"})
    assert response.status_code == 401


def test_chat_creates_conversation_and_delegates_to_orchestration(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "Analyze this model for drift issues.",
            "project_id": project_id,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["conversation_id"]
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"]
    assert body["execution_status"] is not None or body["assistant_message"]["metadata"].get("mode") in {"general_chat", "capabilities", "rule_based"}


def test_chat_with_existing_conversation_and_attachment(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)

    create = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_headers(token),
    )
    conversation_id = create.json()["id"]

    upload = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("loads.txt", io.BytesIO(b"load data"), "text/plain")},
        headers=_headers(token),
    )
    file_id = upload.json()["id"]

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "Extract loads from the attached file.",
            "conversation_id": conversation_id,
            "project_id": project_id,
            "attachments": [file_id],
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    assert response.json()["user_message"]["attachments"][0]["filename"] == "loads.txt"


def test_chat_rc_beam_request_does_not_route_to_load_assessment(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": (
                "Analyze this reinforced concrete beam and determine the governing design checks. "
                "Dead load is 5 kPa."
            ),
            "project_id": project_id,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    capability = response.json().get("selected_capability") or ""
    assert "Load Assessment" not in capability
    assert capability


def test_chat_frame3d_returns_analysis_results(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": (
                "Analyze a 3-storey RC moment frame, 2x2 bays of 5 m in X and Y, storey height 3.2 m, "
                "columns 40x40 cm, beams 30x45 cm, f'c=30 MPa, fy=400 MPa, dead load 6 kN/m2, "
                "live load 2 kN/m2, equivalent static seismic C=0.165 in X and Y."
            ),
            "project_id": project_id,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    metadata = response.json()["assistant_message"]["metadata"]
    results = metadata.get("engineering_results") or {}
    assert results.get("kind") == "frame3d_analysis"
    assert results.get("status") == "completed"
    assert abs(results["results"]["column_max_P_kn"] - 1175.42) < 0.5
    assert abs(results["results"]["max_drift_amplified_pct"] - 2.126) < 0.005


def test_chat_frame3d_export_follow_up_and_endpoint(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    first = api_client.post(
        "/api/v1/chat",
        json={"message": "Analyze a 3-storey RC moment frame, 2x2 bays of 5 m, storey height 3.2 m, C=0.165", "project_id": project_id},
        headers=_headers(token),
    )
    assert first.status_code == 201
    inputs = first.json()["assistant_message"]["metadata"]["engineering_results"]["inputs"]
    follow = api_client.post(
        "/api/v1/chat", json={"message": "خروجی ایتبس بده", "project_id": project_id}, headers=_headers(token)
    )
    assert follow.status_code == 201
    results = follow.json()["assistant_message"]["metadata"].get("engineering_results") or {}
    assert results.get("kind") == "frame3d_analysis"
    assert results.get("status") == "completed"
    assert results.get("export_requested") == ["e2k"]
    assert results.get("model_from_project_memory") is True
    exported = api_client.post(
        "/api/v1/frame3d/export", json={"format": "e2k", "inputs": inputs}, headers=_headers(token)
    )
    assert exported.status_code == 200
    assert 'filename="model.e2k"' in exported.headers["content-disposition"]
    assert "$ LINE CONNECTIVITIES" in exported.text
    assert api_client.post("/api/v1/frame3d/export", json={"format": "xyz", "inputs": inputs}, headers=_headers(token)).status_code == 422


def test_chat_demo_rc_beam_returns_deterministic_results(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": (
                "Analyze a simply supported reinforced concrete beam with a 6 m span "
                "and uniform load of 20 kN/m."
            ),
            "project_id": project_id,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    metadata = response.json()["assistant_message"]["metadata"]
    results = metadata.get("engineering_results") or {}
    assert results.get("kind") == "demo_rc_beam"
    assert results["results"]["max_moment_kn_m"] == 90.0
    assert results["results"]["max_shear_kn"] == 60.0
    assert results.get("demo") is True
    assert "Demo calculation" in (results.get("disclaimer") or "")
    agent_run = metadata.get("agent_run") or {}
    assert agent_run.get("lifecycle") == "completed"
    step_keys = [step.get("key") for step in agent_run.get("steps") or []]
    assert "understand" in step_keys
    assert "execute" in step_keys
    assert "validate" in step_keys
    assert "documents" not in step_keys


def test_chat_rejects_unknown_mode(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "Analyze this model.",
            "project_id": project_id,
            "mode": "exploit",
        },
        headers=_headers(token),
    )
    assert response.status_code == 422


def test_chat_upload_model_request_is_not_load_assessment(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "Please upload the ETABS model and update geometry.",
            "project_id": project_id,
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    capability = response.json().get("selected_capability") or ""
    assert "Load Assessment" not in capability
    assert "Structural Modeling" in capability


def test_chat_rejects_unauthorized_conversation(api_client: TestClient) -> None:
    token_a = _register(api_client)
    token_b = _register(api_client)
    project_id = _project(api_client, token_a)

    create = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_headers(token_a),
    )
    conversation_id = create.json()["id"]

    response = api_client.post(
        "/api/v1/chat",
        json={"message": "Hello", "conversation_id": conversation_id},
        headers=_headers(token_b),
    )
    assert response.status_code == 403


def test_chat_empty_message_without_attachments_rejected(api_client: TestClient) -> None:
    token = _register(api_client)
    response = api_client.post(
        "/api/v1/chat",
        json={"message": "   "},
        headers=_headers(token),
    )
    assert response.status_code == 403


_ACI_BEAM = (
    "Check this RC beam per ACI 318: span 6 m, 20 kN/m, "
    "b=300 mm, h=500 mm, d=450 mm, fc=25 MPa, fy=400 MPa, As=1500 mm2."
)


def test_chat_aci_rc_beam_check_returns_deterministic_results(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    response = api_client.post(
        "/api/v1/chat",
        json={"message": _ACI_BEAM, "project_id": project_id},
        headers=_headers(token),
    )
    assert response.status_code == 201
    metadata = response.json()["assistant_message"]["metadata"]
    results = metadata.get("engineering_results") or {}
    assert results.get("kind") == "aci_rc_beam"
    assert results.get("demo") is False
    assert results["demands"]["mu_kn_m"] == 90.0
    assert results["demands"]["vu_kn"] == 60.0
    assert results["results"]["phi_mn_kn_m"] > 200
    assert results["results"]["flexure_outcome"] == "PASS"
    assert metadata.get("requires_approval") is True
    assert metadata.get("approval_request_id")
    assert results.get("kind") != "demo_rc_beam"


def test_chat_aci_rc_beam_missing_inputs_does_not_approve_or_invent(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    response = api_client.post(
        "/api/v1/chat",
        json={"message": "Design this beam.", "project_id": project_id},
        headers=_headers(token),
    )
    assert response.status_code == 201
    body = response.json()
    metadata = body["assistant_message"]["metadata"]
    results = metadata.get("engineering_results") or {}
    assert results.get("kind") == "aci_rc_beam"
    assert results.get("status") == "MISSING_REQUIRED_INPUT"
    assert metadata.get("requires_approval") is False
    assert metadata.get("approval_request_id") in {None, ""}
    content = body["assistant_message"]["content"]
    assert "I will not invent" in content
    assert "90" not in (results.get("results") or {})


def test_chat_aci_rc_beam_rejects_unauthorized_project(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    token_a = _register(api_client)
    token_b = _register(api_client)
    project_id = _project(api_client, token_a)
    response = api_client.post(
        "/api/v1/chat",
        json={"message": _ACI_BEAM, "project_id": project_id},
        headers=_headers(token_b),
    )
    assert response.status_code == 403
    get_settings.cache_clear()
