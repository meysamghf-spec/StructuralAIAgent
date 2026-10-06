"""Application service tests for file registry and ingestion."""

from uuid import uuid4

import pytest

from app.application.exceptions import ProjectFileNotFoundError, ProjectNotFoundError
from app.application.service_factory import (
    build_file_ingestion_service,
    build_file_registry_service,
    build_project_service,
)
from app.domain.models.file_artifact import ExtractionStatus, ParsingStatus
from app.infrastructure.config import get_settings


def test_file_registry_lists_and_gets_project_files(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Registry Project").project
    ingestion = build_file_ingestion_service()
    registry = build_file_registry_service()

    created = ingestion.ingest_upload(
        project.id,
        filename="registry.txt",
        content=b"registry content",
        content_type="text/plain",
        created_by="registry-user",
    )

    files = registry.list_project_files(project.id)
    assert len(files) == 1
    assert files[0].id == created.id

    loaded = registry.get_project_file(project.id, created.id)
    assert loaded.filename == "registry.txt"


def test_file_ingestion_status_transitions(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Ingestion Project").project
    ingestion = build_file_ingestion_service()

    record = ingestion.ingest_upload(
        project.id,
        filename="status.txt",
        content=b"alpha\nbeta",
        content_type="text/plain",
        created_by="ingest-user",
    )

    assert record.parsing_status == ParsingStatus.COMPLETE
    assert record.extraction_status == ExtractionStatus.COMPLETE
    assert record.confidence == 1.0
    assert record.metadata["extraction"]["parser_key"] == "text_plain"


def test_file_ingestion_persists_content(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Content Project").project
    ingestion = build_file_ingestion_service()
    payload = b"download me"

    record = ingestion.ingest_upload(
        project.id,
        filename="content.txt",
        content=payload,
        content_type="text/plain",
        created_by="content-user",
    )

    loaded, content = ingestion.get_file_content(project.id, record.id)
    assert loaded.id == record.id
    assert content == payload


def test_project_isolation_for_registry_and_content(db_session, file_storage_root) -> None:
    service = build_project_service()
    project_a = service.create_project("Iso A").project
    project_b = service.create_project("Iso B").project
    ingestion = build_file_ingestion_service()
    registry = build_file_registry_service()

    record = ingestion.ingest_upload(
        project_a.id,
        filename="iso.txt",
        content=b"iso",
        content_type="text/plain",
        created_by="iso-user",
    )

    assert registry.list_project_files(project_b.id) == []
    with pytest.raises(ProjectFileNotFoundError):
        registry.get_project_file(project_b.id, record.id)
    with pytest.raises(ProjectFileNotFoundError):
        ingestion.get_file_content(project_b.id, record.id)


def test_unknown_project_errors(db_session, file_storage_root) -> None:
    registry = build_file_registry_service()
    ingestion = build_file_ingestion_service()
    missing_project = uuid4()
    missing_file = uuid4()

    with pytest.raises(ProjectNotFoundError):
        registry.list_project_files(missing_project)
    with pytest.raises(ProjectNotFoundError):
        ingestion.ingest_upload(
            missing_project,
            filename="missing.txt",
            content=b"x",
            content_type="text/plain",
            created_by="x",
        )
    with pytest.raises(ProjectNotFoundError):
        ingestion.get_file_content(missing_project, missing_file)


def test_upload_size_limit(db_session, file_storage_root, monkeypatch) -> None:
    monkeypatch.setenv("MAX_UPLOAD_BYTES", "8")
    get_settings.cache_clear()

    project = build_project_service().create_project("Limit Project").project
    ingestion = build_file_ingestion_service()

    from app.application.exceptions import UploadTooLargeError

    with pytest.raises(UploadTooLargeError):
        ingestion.ingest_upload(
            project.id,
            filename="big.txt",
            content=b"123456789",
            content_type="text/plain",
            created_by="limit-user",
        )
