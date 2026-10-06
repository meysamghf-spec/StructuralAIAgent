"""Engineering document extraction v1 tests."""

from __future__ import annotations

import io
import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.application.chat_attachment_context_service import AVAILABILITY_FAILED, AVAILABILITY_INDEXED
from app.application.document_extraction_service import document_from_file_record
from app.application.exceptions import ProjectFileNotFoundError
from app.application.service_factory import (
    build_chat_attachment_context_service,
    build_conversation_service,
    build_document_indexing_service,
    build_file_ingestion_service,
    build_project_service,
)
from app.domain.models.file_artifact import ExtractionStatus, FileType, ParsingStatus
from app.domain.models.user import AuthenticatedAccount, AuthMethod
from app.infrastructure.parsers.docx_parser import DocxTextParser
from app.infrastructure.parsers.pdf_parser import PdfTextParser
from app.infrastructure.parsers.spreadsheet_parser import SpreadsheetParser
from app.infrastructure.repositories.postgres_conversation_repository import PostgresConversationRepository
from tests.fixtures.document_samples import sample_docx_bytes, sample_pdf_bytes, sample_xlsx_bytes


def _project(db_session, file_storage_root, name: str = "Extraction Project"):
    del db_session, file_storage_root
    return build_project_service().create_project(name).project


def test_pdf_parser_extracts_page_text() -> None:
    parser = PdfTextParser()
    content = sample_pdf_bytes(text="Beam B1 moment envelope")
    result = parser.extract(content, filename="report.pdf")

    assert result.success is True
    document = result.metadata["document"]
    assert "Beam B1 moment envelope" in (document["extracted_text"] or "")
    assert document["structured_data"]["page_count"] >= 1


def test_docx_parser_extracts_paragraphs_and_tables() -> None:
    parser = DocxTextParser()
    content = sample_docx_bytes(paragraph="Shear wall thickness 300 mm", table_row=("Level", "Load kN"))
    result = parser.extract(content, filename="spec.docx")

    assert result.success is True
    document = result.metadata["document"]
    assert "Shear wall thickness 300 mm" in (document["extracted_text"] or "")
    assert "Level" in (document["extracted_text"] or "")
    assert document["metadata"]["table_count"] == 1


def test_spreadsheet_parser_extracts_structured_cells() -> None:
    parser = SpreadsheetParser()
    content = sample_xlsx_bytes(rows=[["Case", "kPa"], ["DL", "6"], ["LL", "4"]])
    result = parser.extract(content, filename="loads.xlsx")

    assert result.success is True
    document = result.metadata["document"]
    sheets = document["structured_data"]["sheets"]
    assert sheets[0]["name"] == "Loads"
    assert any(cell["value"] == "DL" for row in sheets[0]["rows"] for cell in row["cells"])
    assert "Sheet: Loads" in (document["extracted_text"] or "")


def test_pdf_extraction_failure_does_not_fabricate_content() -> None:
    parser = PdfTextParser()
    result = parser.extract(b"not-a-pdf", filename="broken.pdf")

    assert result.success is False
    document = result.metadata["document"]
    assert document["status"] == "failed"
    assert not document.get("extracted_text")


def test_ingestion_indexes_extracted_pdf_idempotently(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    ingestion = build_file_ingestion_service()
    indexing = build_document_indexing_service()
    uploaded = ingestion.ingest_upload(
        project.id,
        filename="design.pdf",
        content=sample_pdf_bytes(text="Foundation settlement limit 25 mm"),
        content_type="application/pdf",
        created_by="engineer",
    )

    assert uploaded.file_type == FileType.PDF
    assert uploaded.extraction_status == ExtractionStatus.COMPLETE
    document = document_from_file_record(uploaded)
    assert document is not None
    assert "Foundation settlement limit 25 mm" in (document.extracted_text or "")

    first = indexing.index_file(project.id, uploaded.id, created_by="engineer")
    second = indexing.index_file(project.id, uploaded.id, created_by="engineer")
    assert first.id == second.id


def test_chat_context_includes_extracted_pdf(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="calc.pdf",
        content=sample_pdf_bytes(text="Drift ratio 0.002"),
        content_type="application/pdf",
        created_by="engineer",
    )

    entry = build_chat_attachment_context_service().build(
        project.id,
        [uploaded.id],
        created_by="engineer",
    ).entries[0]

    assert entry.availability == AVAILABILITY_INDEXED
    assert "Drift ratio 0.002" in (entry.text_preview or "")


def test_chat_context_includes_extracted_docx(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="notes.docx",
        content=sample_docx_bytes(paragraph="Grade 60 rebar required"),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        created_by="engineer",
    )

    entry = build_chat_attachment_context_service().build(
        project.id,
        [uploaded.id],
    ).entries[0]
    assert "Grade 60 rebar required" in (entry.text_preview or "")


def test_chat_context_includes_extracted_xlsx(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="loads.xlsx",
        content=sample_xlsx_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        created_by="engineer",
    )

    entry = build_chat_attachment_context_service().build(
        project.id,
        [uploaded.id],
    ).entries[0]
    assert entry.structured_preview is not None
    assert "DL" in (entry.text_preview or "")


def test_edb_and_dwg_remain_unparsed_with_explicit_limitations(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    ingestion = build_file_ingestion_service()
    edb = ingestion.ingest_upload(
        project.id,
        filename="model.edb",
        content=b"binary-edb",
        content_type="application/octet-stream",
        created_by="engineer",
    )
    dwg = ingestion.ingest_upload(
        project.id,
        filename="plan.dwg",
        content=b"binary-dwg",
        content_type="application/octet-stream",
        created_by="engineer",
    )

    assert edb.parsing_status == ParsingStatus.SKIPPED
    assert dwg.parsing_status == ParsingStatus.SKIPPED
    bundle = build_chat_attachment_context_service().build(project.id, [edb.id, dwg.id])
    limitations = [entry.limitation or "" for entry in bundle.entries]
    assert any("ETABS EDB" in item for item in limitations)
    assert any("DWG" in item for item in limitations)
    assert all(entry.text_preview is None for entry in bundle.entries)


def test_extraction_project_isolation(db_session, file_storage_root) -> None:
    project_a = _project(db_session, file_storage_root, "A")
    project_b = _project(db_session, file_storage_root, "B")
    uploaded = build_file_ingestion_service().ingest_upload(
        project_a.id,
        filename="secret.pdf",
        content=sample_pdf_bytes(text="Private load combination"),
        content_type="application/pdf",
        created_by="engineer",
    )
    with pytest.raises(ProjectFileNotFoundError):
        build_chat_attachment_context_service().build(project_b.id, [uploaded.id])


def test_api_chat_pdf_attachment_provides_extracted_context(api_client: TestClient) -> None:
    token = _register(api_client)
    project_id = _create_project(api_client, token)
    upload = api_client.post(
        f"/api/v1/projects/{project_id}/files",
        files={"file": ("report.pdf", io.BytesIO(sample_pdf_bytes(text="Base shear 1200 kN")), "application/pdf")},
        headers=_headers(token),
    )
    assert upload.status_code == 201
    file_id = upload.json()["id"]

    conversation_id = api_client.post(
        "/api/v1/conversations",
        json={"project_id": project_id},
        headers=_headers(token),
    ).json()["id"]

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "Summarize the base shear from the PDF.",
            "conversation_id": conversation_id,
            "project_id": project_id,
            "attachments": [file_id],
        },
        headers=_headers(token),
    )
    assert response.status_code == 201
    entry = response.json()["user_message"]["metadata"]["attachment_context"]["attachments"][0]
    assert entry["availability"] == AVAILABILITY_INDEXED
    assert "Base shear 1200 kN" in entry["text_preview"]


def test_orchestration_receives_extracted_attachment_context(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="brief.docx",
        content=sample_docx_bytes(paragraph="Expansion joint at grid 4"),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        created_by="engineer",
    )
    conversation = PostgresConversationRepository().create(
        account_id="account-3",
        title="Doc chat",
        project_id=project.id,
    )
    account = AuthenticatedAccount(
        account_id="account-3",
        auth_method=AuthMethod.LEGACY_ACTOR,
        email="engineer3@example.com",
    )
    captured: dict = {}

    def _capture_execute(request, *, actor_id: str, account_id: str | None = None, **kwargs):
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
            content="What does the document say about the expansion joint?",
            attachment_file_ids=[uploaded.id],
            actor_id="engineer",
        )

    assert "Expansion joint at grid 4" in captured["user_request"]
    assert captured["parameters"]["attachment_context"]["attachments"][0]["filename"] == "brief.docx"


def _register(api_client: TestClient) -> str:
    email = f"extract-{uuid.uuid4().hex}@example.com"
    response = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_project(api_client: TestClient, token: str) -> str:
    response = api_client.post(
        "/api/v1/projects",
        json={"name": "Extraction API Project"},
        headers=_headers(token),
    )
    assert response.status_code == 201
    return response.json()["project"]["id"]
