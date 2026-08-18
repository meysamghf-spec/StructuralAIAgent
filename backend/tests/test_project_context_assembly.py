"""Project context assembly service tests."""

from app.application.service_factory import (
    build_file_ingestion_service,
    build_project_context_assembly_service,
    build_project_memory_service,
    build_project_service,
)
from app.domain.models.project_memory import MemoryType


def test_assemble_project_context(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Context Assembly").project
    memory_service = build_project_memory_service()

    memory_service.create_memory(
        project.id,
        MemoryType.REQUIREMENT,
        "Minimum lateral drift limit 0.002.",
    )

    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="context.txt",
        content=b"file content",
        content_type="text/plain",
        created_by="uploader",
    )

    context = build_project_context_assembly_service().assemble(project.id)
    assert context.project_id == project.id
    assert context.project_name == "Context Assembly"
    assert context.pem_version == 1
    assert context.memory_total_count == 1
    assert len(context.files) == 1
    assert context.files[0].id == uploaded.id


def test_assemble_includes_indexed_file_memory(db_session, file_storage_root, monkeypatch) -> None:
    from app.infrastructure.config import get_settings

    monkeypatch.setenv("AUTO_INDEX_FILES", "true")
    get_settings.cache_clear()

    project = build_project_service().create_project("Context With Index").project
    build_file_ingestion_service().ingest_upload(
        project.id,
        filename="indexed.txt",
        content=b"a\nb",
        content_type="text/plain",
        created_by="uploader",
    )

    context = build_project_context_assembly_service().assemble(project.id)
    assert context.memory_total_count == 1
    assert context.memories[0].source_type == "file"
