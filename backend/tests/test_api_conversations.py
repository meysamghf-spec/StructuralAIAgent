"""Conversation and chat API tests."""

from __future__ import annotations

import io
import uuid

from fastapi.testclient import TestClient


def _register_and_token(api_client: TestClient, email: str | None = None) -> tuple[str, str]:
    address = email or f"chat-user-{uuid.uuid4().hex}@example.com"
    password = "secure-password"
    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": address, "password": password, "display_name": "Chat User"},
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    account_id = register.json()["user"]["account_id"]
    return token, account_id


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_project(api_client: TestClient, token: str, name: str = "Chat Project") -> str:
    response = api_client.post(
        "/api/v1/projects",
        json={"name": name, "description": "Conversation test project"},
        headers=_auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()["project"]["id"]


def test_create_and_list_conversations(api_client: TestClient) -> None:
    token, _ = _register_and_token(api_client)
    project_id = _create_project(api_client, token)

    create = api_client.post(
        "/api/v1/conversations",
        json={"title": "Seismic review", "project_id": project_id},
        headers=_auth_headers(token),
    )
    assert create.status_code == 201
    conversation_id = create.json()["id"]
    assert create.json()["title"] == "Seismic review"
    assert create.json()["project_id"] == project_id

    listing = api_client.get("/api/v1/conversations", headers=_auth_headers(token))
    assert listing.status_code == 200
    ids = [item["id"] for item in listing.json()["conversations"]]
    assert conversation_id in ids


def test_unauthorized_conversation_access(api_client: TestClient) -> None:
    token_a, _ = _register_and_token(api_client)
    token_b, _ = _register_and_token(api_client)
    project_id = _create_project(api_client, token_a)

    create = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_auth_headers(token_a),
    )
    conversation_id = create.json()["id"]

    forbidden = api_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=_auth_headers(token_b),
    )
    assert forbidden.status_code == 403


def test_send_message_persists_and_returns_assistant(api_client: TestClient) -> None:
    token, _ = _register_and_token(api_client)
    project_id = _create_project(api_client, token)

    create = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_auth_headers(token),
    )
    conversation_id = create.json()["id"]

    send = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "Analyze this model for drift issues."},
        headers=_auth_headers(token),
    )
    assert send.status_code == 201
    body = send.json()
    assert body["user_message"]["role"] == "user"
    assert body["assistant_message"]["role"] == "assistant"
    assert body["assistant_message"]["content"]
    assert body["assistant_message"]["metadata"].get("mode") == "agent_execution"

    messages = api_client.get(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers=_auth_headers(token),
    )
    assert messages.status_code == 200
    assert len(messages.json()["messages"]) == 2


def test_general_chat_without_project(api_client: TestClient) -> None:
    token, _ = _register_and_token(api_client)
    create = api_client.post(
        "/api/v1/conversations",
        json={"title": "General question"},
        headers=_auth_headers(token),
    )
    conversation_id = create.json()["id"]

    send = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={"content": "What is structural drift?"},
        headers=_auth_headers(token),
    )
    assert send.status_code == 201
    assert send.json()["assistant_message"]["metadata"].get("mode") in {"general_chat", "capabilities", "rule_based"}


def test_upload_attachment_and_send_with_file(api_client: TestClient) -> None:
    token, _ = _register_and_token(api_client)
    project_id = _create_project(api_client, token)

    create = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_auth_headers(token),
    )
    conversation_id = create.json()["id"]

    upload = api_client.post(
        f"/api/v1/conversations/{conversation_id}/attachments",
        files={"file": ("loads.pdf", io.BytesIO(b"%PDF-1.4 sample"), "application/pdf")},
        headers=_auth_headers(token),
    )
    assert upload.status_code == 201
    file_id = upload.json()["attachment"]["file_id"]

    send = api_client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        json={
            "content": "Extract the structural loads from this PDF.",
            "attachment_file_ids": [file_id],
        },
        headers=_auth_headers(token),
    )
    assert send.status_code == 201
    assert send.json()["user_message"]["attachments"][0]["filename"] == "loads.pdf"
    assert send.json()["assistant_message"]["content"]


def test_invalid_conversation_id(api_client: TestClient) -> None:
    token, _ = _register_and_token(api_client)
    missing = uuid.uuid4()
    response = api_client.get(
        f"/api/v1/conversations/{missing}",
        headers=_auth_headers(token),
    )
    assert response.status_code == 404


def test_delete_conversation(api_client: TestClient) -> None:
    token, _ = _register_and_token(api_client)
    create = api_client.post(
        "/api/v1/conversations",
        json={"title": "Temporary"},
        headers=_auth_headers(token),
    )
    conversation_id = create.json()["id"]

    delete = api_client.delete(
        f"/api/v1/conversations/{conversation_id}",
        headers=_auth_headers(token),
    )
    assert delete.status_code == 204

    get_response = api_client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers=_auth_headers(token),
    )
    assert get_response.status_code == 404


def test_list_conversations_scoped_by_project(api_client: TestClient) -> None:
    token, _ = _register_and_token(api_client)
    headers = _auth_headers(token)
    project_a = _create_project(api_client, token, "Project A")
    project_b = _create_project(api_client, token, "Project B")

    def _make(project_id: str | None, title: str) -> str:
        body: dict[str, str] = {"title": title}
        if project_id:
            body["project_id"] = project_id
        response = api_client.post("/api/v1/conversations", json=body, headers=headers)
        assert response.status_code == 201
        return response.json()["id"]

    chat_a = _make(project_a, "Chat A")
    chat_b = _make(project_b, "Chat B")
    chat_general = _make(None, "General chat")

    def _ids(params: dict[str, str]) -> set[str]:
        response = api_client.get("/api/v1/conversations", params=params, headers=headers)
        assert response.status_code == 200
        return {item["id"] for item in response.json()["conversations"]}

    assert _ids({"project_id": project_a}) == {chat_a}
    assert _ids({"project_id": project_b}) == {chat_b}
    assert _ids({"unassigned": "true"}) == {chat_general}
    # Unscoped listing keeps returning everything (backward compatible).
    assert {chat_a, chat_b, chat_general} <= _ids({})
