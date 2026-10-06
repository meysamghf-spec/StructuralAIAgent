"""SSE chat stream tests — incremental agent-run events from real execution."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.application.agent_run_events import parse_sse_stream


def _register(api_client: TestClient) -> str:
    email = f"stream-{uuid.uuid4().hex}@example.com"
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
        json={"name": "Stream Project"},
        headers=_headers(token),
    )
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_stream_requires_authentication(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("AUTH_REQUIRED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    response = api_client.post("/api/v1/chat/stream", json={"message": "Analyze this model."})
    assert response.status_code == 401


def test_stream_rejects_unauthorized_conversation(api_client: TestClient) -> None:
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
        "/api/v1/chat/stream",
        json={"message": "Analyze this model.", "conversation_id": conversation_id},
        headers=_headers(token_b),
    )
    assert response.status_code == 403


def test_stream_rejects_foreign_project_on_create(api_client: TestClient, monkeypatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    token_a = _register(api_client)
    token_b = _register(api_client)
    project_id = _project(api_client, token_a)
    response = api_client.post(
        "/api/v1/chat/stream",
        json={"message": "Analyze this model.", "project_id": project_id},
        headers=_headers(token_b),
    )
    assert response.status_code == 403
    get_settings.cache_clear()


def test_stream_emits_real_lifecycle_and_completes(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    response = api_client.post(
        "/api/v1/chat/stream",
        json={
            "message": (
                "Analyze a simply supported reinforced concrete beam with a 6 m span "
                "and uniform load of 20 kN/m."
            ),
            "project_id": project_id,
        },
        headers=_headers(token),
    )
    assert response.status_code == 200
    assert "text/event-stream" in response.headers["content-type"]
    events = parse_sse_stream(response.text)
    types = [event_type for event_type, _payload in events]
    assert types[0] == "agent_run.started"
    assert "agent_run.step" in types
    assert "agent_run.completed" in types
    assert types.index("agent_run.started") < types.index("agent_run.completed")
    started = events[0][1]
    assert started["user_message"]["role"] == "user"
    completed = next(payload for event_type, payload in events if event_type == "agent_run.completed")
    assert completed["assistant_message"]["role"] == "assistant"
    metadata = completed["assistant_message"]["metadata"]
    assert metadata.get("agent_run", {}).get("lifecycle") == "completed"
    results = metadata.get("engineering_results") or {}
    assert results.get("kind") == "demo_rc_beam"
    assert results["results"]["max_moment_kn_m"] == 90.0
    understand = [
        payload
        for event_type, payload in events
        if event_type == "agent_run.step" and payload.get("step_id") == "understand"
    ]
    assert understand[0]["status"] == "current"
    assert understand[-1]["status"] == "complete"
    assert not any("traceback" in response.text.lower() for _ in [0])


def test_stream_failed_event_is_safe(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    response = api_client.post(
        "/api/v1/chat/stream",
        json={"message": "", "project_id": project_id},
        headers=_headers(token),
    )
    assert response.status_code == 200
    events = parse_sse_stream(response.text)
    types = [event_type for event_type, _payload in events]
    assert "agent_run.failed" in types
    failed = next(payload for event_type, payload in events if event_type == "agent_run.failed")
    reason = failed["error"]["reason"]
    assert "traceback" not in reason.lower()
    assert "password" not in reason.lower()
    assert reason


def test_stream_approval_required_when_run_awaits_approval() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.application.agent_run_events import EVENT_APPROVAL_REQUIRED
    from app.application.conversation_service import _emit_terminal_chat_event
    from app.domain.models.conversation import ConversationMessage, MessageRole

    class _Sink:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        def emit(self, event_type: str, payload: dict) -> None:
            self.events.append((event_type, payload))

    conversation_id = uuid4()
    user = ConversationMessage(
        id=uuid4(),
        conversation_id=conversation_id,
        role=MessageRole.USER,
        content="Update the structural model",
        created_at=datetime.now(UTC),
    )
    assistant = ConversationMessage(
        id=uuid4(),
        conversation_id=conversation_id,
        role=MessageRole.ASSISTANT,
        content="Approval required",
        metadata={
            "progress": "awaiting_approval",
            "requires_approval": True,
            "approval_request_id": "apr-1",
            "execution_id": str(uuid4()),
            "agent_run": {"lifecycle": "waiting_for_approval"},
        },
        created_at=datetime.now(UTC),
    )
    sink = _Sink()
    _emit_terminal_chat_event(
        sink,
        conversation_id=conversation_id,
        user_message=user,
        assistant_message=assistant,
    )
    assert sink.events[0][0] == EVENT_APPROVAL_REQUIRED
    assert sink.events[0][1]["approval_request_id"] == "apr-1"


def test_stream_disconnect_keeps_execution_consistent(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    with api_client.stream(
        "POST",
        "/api/v1/chat/stream",
        json={
            "message": (
                "Analyze a simply supported reinforced concrete beam with a 6 m span "
                "and uniform load of 20 kN/m."
            ),
            "project_id": project_id,
        },
        headers=_headers(token),
    ) as response:
        assert response.status_code == 200
        saw_started = False
        for line in response.iter_lines():
            if line.startswith("event: agent_run.started"):
                saw_started = True
                break
        assert saw_started

    conversations = api_client.get("/api/v1/conversations", headers=_headers(token))
    assert conversations.status_code == 200
    items = conversations.json()["conversations"]
    assert items
    messages = api_client.get(
        f"/api/v1/conversations/{items[0]['id']}/messages",
        headers=_headers(token),
    )
    assert messages.status_code == 200
    roles = [item["role"] for item in messages.json()["messages"]]
    assert "user" in roles
    assert "assistant" in roles


def test_stream_aci_rc_beam_emits_real_tool_and_validation_events(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _project(api_client, token)
    response = api_client.post(
        "/api/v1/chat/stream",
        json={
            "message": (
                "Check this RC beam per ACI 318: span 6 m, 20 kN/m, "
                "b=300 mm, h=500 mm, d=450 mm, fc=25 MPa, fy=400 MPa, As=1500 mm2."
            ),
            "project_id": project_id,
        },
        headers=_headers(token),
    )
    assert response.status_code == 200
    events = parse_sse_stream(response.text)
    types = [event_type for event_type, _payload in events]
    assert "agent_run.tool" in types
    assert "agent_run.validation" in types
    assert "agent_run.approval_required" in types
    tools = [payload["tool"] for event_type, payload in events if event_type == "agent_run.tool" and payload.get("tool")]
    aci_labels = [
        detail.get("label", "")
        for tool in tools
        for detail in tool.get("details") or []
        if isinstance(detail, dict)
    ]
    assert any("ACI 318" in label for label in aci_labels)
    assert any("ENGINEERING_CODE_CHECK" in (tool.get("operations") or []) for tool in tools)
    approvals = [payload for event_type, payload in events if event_type == "agent_run.approval_required"]
    assert approvals
    approval = next(
        (payload for payload in reversed(approvals) if payload.get("assistant_message")),
        approvals[-1],
    )
    assert approval.get("approval_request_id") or (approval.get("assistant_message") or {}).get("metadata", {}).get(
        "approval_request_id"
    )
    metadata = (approval.get("assistant_message") or {}).get("metadata") or {}
    results = metadata.get("engineering_results") or {}
    assert results.get("kind") == "aci_rc_beam"
    assert results["demands"]["mu_kn_m"] == 90.0
    assert results.get("demo") is False
