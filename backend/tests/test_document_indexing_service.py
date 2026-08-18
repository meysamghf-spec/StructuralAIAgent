"""Document indexing service tests."""

from uuid import UUID, uuid4

import pytest

from app.application.exceptions import ProjectFileNotFoundError, ProjectNotFoundError
from app.application.service_factory import (
    build_document_indexing_service,
    build_file_ingestion_service,
    build_project_service,
)
from app.domain.models.project_memory import FILE_MEMORY_SOURCE_TYPE, MemoryType


def _upload_file(project_id, *, content: bytes = b"line one\nline two") -> UUID:
    ingestion = build_file_ingestion_service()
    record = ingestion.ingest_upload(
        project_id,
        filename="notes.txt",
        content=content,
        content_type="text/plain",
        created_by="uploader",
    )
    return record.id


def test_index_file_creates_traceable_memory(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Index Project").project
    indexing = build_document_indexing_service()
    file_id = _upload_file(project.id)

    memory = indexing.index_file(project.id, file_id, created_by="indexer")

    assert memory.memory_type == MemoryType.EXTRACTED_INFORMATION
    assert memory.source_type == FILE_MEMORY_SOURCE_TYPE
    assert memory.source_id == file_id
    assert "notes.txt" in memory.content
    assert memory.metadata["filename"] == "notes.txt"
    assert memory.created_by == "indexer"


def test_get_memories_for_file(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Retrieve Index Project").project
    indexing = build_document_indexing_service()
    file_id = _upload_file(project.id)

    indexing.index_file(project.id, file_id)

    memories = indexing.get_memories_for_file(project.id, file_id)
    assert len(memories) == 1
    assert memories[0].source_type == FILE_MEMORY_SOURCE_TYPE
    assert memories[0].source_id == file_id


def test_index_file_project_isolation(db_session, file_storage_root) -> None:
    service = build_project_service()
    project_a = service.create_project("Index Iso A").project
    project_b = service.create_project("Index Iso B").project
    indexing = build_document_indexing_service()
    file_id = _upload_file(project_a.id)

    with pytest.raises(ProjectFileNotFoundError):
        indexing.index_file(project_b.id, file_id)

    with pytest.raises(ProjectFileNotFoundError):
        indexing.get_memories_for_file(project_b.id, file_id)


def test_index_file_unknown_project(db_session, file_storage_root) -> None:
    indexing = build_document_indexing_service()
    missing_project = uuid4()

    with pytest.raises(ProjectNotFoundError):
        indexing.index_file(missing_project, uuid4())
