"""Integration tests — post-extraction document indexing readiness."""

from uuid import uuid4

import pytest

from app.application.document_indexing_service import is_file_ready_for_indexing
from app.application.exceptions import FileNotReadyForIndexingError
from app.application.service_factory import (
    build_document_indexing_service,
    build_file_ingestion_service,
    build_file_registry_service,
    build_project_service,
)
from app.domain.models.file_artifact import (
    ExtractionStatus,
    FileSource,
    FileType,
    ParsingStatus,
)
from app.infrastructure.repositories.postgres_file_repository import PostgresFileRepository


def test_upload_then_index_after_successful_extraction(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Post Extraction Index").project
    ingestion = build_file_ingestion_service()
    indexing = build_document_indexing_service()

    uploaded = ingestion.ingest_upload(
        project.id,
        filename="ready.txt",
        content=b"alpha\nbeta",
        content_type="text/plain",
        created_by="uploader",
    )

    assert uploaded.parsing_status == ParsingStatus.COMPLETE
    assert uploaded.extraction_status == ExtractionStatus.COMPLETE
    assert is_file_ready_for_indexing(uploaded)
    assert indexing.is_ready_for_indexing(project.id, uploaded.id)

    memory = indexing.index_file(project.id, uploaded.id, created_by="indexer")
    assert memory.source_type == "file"
    assert memory.source_id == uploaded.id

    reloaded = build_file_registry_service().get_project_file(project.id, uploaded.id)
    assert reloaded.parsing_status == ParsingStatus.COMPLETE
    assert reloaded.extraction_status == ExtractionStatus.COMPLETE


def test_index_rejected_when_extraction_not_successful(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Failed Extraction Index").project
    repo = PostgresFileRepository()
    file_id = uuid4()

    failed_record = repo.create(
        file_id=file_id,
        project_id=project.id,
        filename="failed.txt",
        content_type="text/plain",
        file_type=FileType.TEXT,
        file_version=None,
        source=FileSource.USER_UPLOAD,
        storage_path=f"{project.id}/{file_id}.txt",
        parsing_status=ParsingStatus.FAILED,
        extraction_status=ExtractionStatus.FAILED,
        confidence=None,
        metadata={"extraction": {"success": False, "error_message": "stub failure"}},
        created_by="tester",
    )

    assert is_file_ready_for_indexing(failed_record) is False

    indexing = build_document_indexing_service()
    assert indexing.is_ready_for_indexing(project.id, file_id) is False

    with pytest.raises(FileNotReadyForIndexingError):
        indexing.index_file(project.id, file_id)


def test_upload_flow_unchanged_without_indexing(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Upload Only Project").project
    ingestion = build_file_ingestion_service()

    uploaded = ingestion.ingest_upload(
        project.id,
        filename="no-index.txt",
        content=b"content only",
        content_type="text/plain",
        created_by="uploader",
    )

    assert uploaded.filename == "no-index.txt"
    assert uploaded.metadata.get("extraction", {}).get("success") is True

    memories = build_document_indexing_service().get_memories_for_file(project.id, uploaded.id)
    assert memories == []


def test_auto_index_on_upload_when_enabled(db_session, file_storage_root, monkeypatch) -> None:
    from app.infrastructure.config import get_settings

    monkeypatch.setenv("AUTO_INDEX_FILES", "true")
    get_settings.cache_clear()

    project = build_project_service().create_project("Auto Index Project").project
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="auto.txt",
        content=b"one\ntwo",
        content_type="text/plain",
        created_by="uploader",
    )

    memories = build_document_indexing_service().get_memories_for_file(project.id, uploaded.id)
    assert len(memories) == 1
    assert memories[0].source_type == "file"
    assert memories[0].source_id == uploaded.id
