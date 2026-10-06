"""Tests for chat attachment context building and end-to-end chat file path."""

from __future__ import annotations

import io
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.application.chat_attachment_context_service import (
    AVAILABILITY_INDEXED,
    AVAILABILITY_STORED_ONLY,
)
from app.application.exceptions import ProjectFileNotFoundError
from app.application.service_factory import (
    build_chat_attachment_context_service,
    build_conversation_service,
    build_file_ingestion_service,
    build_project_service,
)
from app.domain.models.agent_runtime import AgentExecutionRequest
from app.domain.models.user import AuthenticatedAccount, AuthMethod
from app.infrastructure.repositories.postgres_conversation_repository import (
    PostgresConversationRepository,
)


def _create_project(db_session, file_storage_root, name: str = "Attachment Context Project"):
    del db_session, file_storage_root
    return build_project_service().create_project(name).project


def test_text_attachment_includes_preview_and_indexes_on_chat(db_session, file_storage_root) -> None:
    project = _create_project(db_session, file_storage_root)
    ingestion = build_file_ingestion_service()
    uploaded = ingestion.ingest_upload(
        project.id,
        filename="loads.txt",
        content=b"dead load: 5 kPa\nlive load: 3 kPa",
        content_type="text/plain",
        created_by="engineer",
    )

    context_service = build_chat_attachment_context_service()
    bundle = context_service.build(project.id, [uploaded.id], created_by="engineer")

    assert len(bundle.entries) == 1
    entry = bundle.entries[0]
    assert entry.availability == AVAILABILITY_INDEXED
    assert "dead load" in (entry.text_preview or "")
    assert entry.indexed_memory_ids
    assert "loads.txt" in entry.indexed_memory_content[0]

    prompt = bundle.to_prompt_section()
    assert "Extracted content:" in prompt
    assert "dead load: 5 kPa" in prompt


def test_pdf_attachment_provides_extracted_content_when_valid(db_session, file_storage_root) -> None:
    from tests.fixtures.document_samples import sample_pdf_bytes

    project = _create_project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="spec.pdf",
        content=sample_pdf_bytes(text="Seismic mass 450 tons"),
        content_type="application/pdf",
        created_by="engineer",
    )

    entry = build_chat_attachment_context_service().build(
        project.id,
        [uploaded.id],
        created_by="engineer",
    ).entries[0]

    assert entry.availability == AVAILABILITY_INDEXED
    assert "Seismic mass 450 tons" in (entry.text_preview or "")


def test_edb_attachment_reports_binary_limitation(db_session, file_storage_root) -> None:
    project = _create_project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="model.edb",
        content=b"binary-edb-content",
        content_type="application/octet-stream",
        created_by="engineer",
    )

    entry = build_chat_attachment_context_service().build(
        project.id,
        [uploaded.id],
    ).entries[0]

    assert entry.availability == AVAILABILITY_STORED_ONLY
    assert entry.limitation is not None
    assert "ETABS EDB" in entry.limitation


def test_attachment_context_enforces_project_isolation(db_session, file_storage_root) -> None:
    project_a = _create_project(db_session, file_storage_root, "Project A")
    project_b = _create_project(db_session, file_storage_root, "Project B")
    uploaded = build_file_ingestion_service().ingest_upload(
        project_a.id,
        filename="private.txt",
        content=b"secret",
        content_type="text/plain",
        created_by="engineer",
    )

    with pytest.raises(ProjectFileNotFoundError):
        build_chat_attachment_context_service().build(project_b.id, [uploaded.id])


def test_conversation_send_message_persists_attachment_context(db_session, file_storage_root) -> None:
    project = _create_project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="notes.txt",
        content=b"column spacing: 8 m",
        content_type="text/plain",
        created_by="engineer",
    )

    repo = PostgresConversationRepository()
    conversation = repo.create(
        account_id="account-1",
        title="File chat",
        project_id=project.id,
    )
    account = AuthenticatedAccount(
        account_id="account-1",
        auth_method=AuthMethod.LEGACY_ACTOR,
        email="engineer@example.com",
        display_name="Engineer",
    )

    service = build_conversation_service()
    user_message, assistant_message = service.send_message(
        conversation.id,
        account,
        content="What is the column spacing?",
        attachment_file_ids=[uploaded.id],
        actor_id="engineer",
    )

    assert user_message.metadata.get("attachment_context")
    attachment_entries = user_message.metadata["attachment_context"]["attachments"]
    assert attachment_entries[0]["filename"] == "notes.txt"
    assert attachment_entries[0]["availability"] == AVAILABILITY_INDEXED
    assert "column spacing" in attachment_entries[0]["text_preview"]
    assert assistant_message.metadata.get("attachment_context")
    assert assistant_message.content


def test_orchestration_receives_attachment_context_in_parameters(db_session, file_storage_root) -> None:
    project = _create_project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="beam.txt",
        content=b"beam span 12 m",
        content_type="text/plain",
        created_by="engineer",
    )

    repo = PostgresConversationRepository()
    conversation = repo.create(
        account_id="account-2",
        title="Orchestration context",
        project_id=project.id,
    )
    account = AuthenticatedAccount(
        account_id="account-2",
        auth_method=AuthMethod.LEGACY_ACTOR,
        email="engineer2@example.com",
        display_name="Engineer",
    )

    captured: dict = {}

    def _capture_execute(request: AgentExecutionRequest, *, actor_id: str, account_id: str | None = None, **kwargs):
        captured["user_request"] = request.user_request
        captured["parameters"] = request.parameters
        from app.application.service_factory import build_agent_runtime_service

        return build_agent_runtime_service().execute(
            request,
            actor_id=actor_id,
            account_id=account_id,
            **kwargs,
        )

    service = build_conversation_service()
    with patch.object(service._agent_runtime, "execute", side_effect=_capture_execute):
        service.send_message(
            conversation.id,
            account,
            content="Summarize the beam span.",
            attachment_file_ids=[uploaded.id],
            actor_id="engineer",
        )

    assert "beam span 12 m" in captured["user_request"]
    assert captured["parameters"]["attachment_context"]["attachments"][0]["filename"] == "beam.txt"


def _register(api_client: TestClient) -> str:
    email = f"file-chat-{uuid.uuid4().hex}@example.com"
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_api_chat_message_includes_text_attachment_context(api_client: TestClient) -> None:
    token = _register(api_client)
    project = api_client.post(
        "/api/v1/projects",
        json={"name": "Chat File Context"},
        headers=_headers(token),
    )
    project_id = project.json()["project"]["id"]

    upload = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("gravity.txt", io.BytesIO(b"DL=6 kPa\nLL=4 kPa"), "text/plain")},
        headers=_headers(token),
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    create = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_headers(token),
    )
    conversation_id = create.json()["id"]

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "What are the gravity loads?",
            "conversation_id": conversation_id,
            "project_id": project_id,
            "attachments": [file_id],
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    user_meta = response.json()["user_message"]["metadata"]
    assert user_meta["attachment_context"]["attachments"][0]["availability"] == AVAILABILITY_INDEXED
    assert "DL=6 kPa" in user_meta["attachment_context"]["attachments"][0]["text_preview"]


def test_api_chat_invalid_pdf_reports_failed_extraction(api_client: TestClient) -> None:
    token = _register(api_client)
    project = api_client.post(
        "/api/v1/projects",
        json={"name": "PDF Failure"},
        headers=_headers(token),
    )
    project_id = project.json()["project"]["id"]

    upload = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("report.pdf", io.BytesIO(b"not-a-pdf"), "application/pdf")},
        headers=_headers(token),
    )
    file_id = upload.json()["id"]

    create = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_headers(token),
    )
    conversation_id = create.json()["id"]

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "Summarize this PDF.",
            "conversation_id": conversation_id,
            "project_id": project_id,
            "attachments": [file_id],
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    entry = response.json()["user_message"]["metadata"]["attachment_context"]["attachments"][0]
    assert entry["availability"] == "failed"
    assert entry.get("text_preview") is None
