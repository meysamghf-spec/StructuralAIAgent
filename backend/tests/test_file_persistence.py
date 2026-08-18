"""Persistence tests for project file repository."""

from uuid import uuid4

from app.application.service_factory import build_project_service
from app.domain.models.file_artifact import (
    ExtractionStatus,
    FileSource,
    FileType,
    ParsingStatus,
)
from app.infrastructure.repositories.postgres_file_repository import PostgresFileRepository


def test_file_repository_create_list_and_update(db_session) -> None:
    project = build_project_service().create_project("Files Project").project
    repo = PostgresFileRepository()

    created = repo.create(
        project_id=project.id,
        filename="notes.txt",
        content_type="text/plain",
        file_type=FileType.TEXT,
        file_version=None,
        source=FileSource.USER_UPLOAD,
        storage_path=f"{project.id}/{uuid4()}.txt",
        parsing_status=ParsingStatus.PENDING,
        extraction_status=ExtractionStatus.PENDING,
        confidence=None,
        metadata={"seed": True},
        created_by="tester",
    )

    assert created.file_version == 1
    assert created.metadata["seed"] is True

    listed = repo.list_for_project(project.id)
    assert len(listed) == 1
    assert listed[0].id == created.id

    loaded = repo.get_by_id(project.id, created.id)
    assert loaded is not None
    assert loaded.filename == "notes.txt"

    updated = repo.update_statuses(
        project.id,
        created.id,
        parsing_status=ParsingStatus.COMPLETE,
        extraction_status=ExtractionStatus.COMPLETE,
        confidence=1.0,
        metadata={"seed": True, "done": True},
    )
    assert updated is not None
    assert updated.parsing_status == ParsingStatus.COMPLETE
    assert updated.metadata["done"] is True


def test_file_repository_increments_version_per_filename(db_session) -> None:
    project = build_project_service().create_project("Versioned Files").project
    repo = PostgresFileRepository()

    first = repo.create(
        project_id=project.id,
        filename="repeat.txt",
        content_type="text/plain",
        file_type=FileType.TEXT,
        file_version=None,
        source=FileSource.USER_UPLOAD,
        storage_path=f"{project.id}/{uuid4()}.txt",
        parsing_status=ParsingStatus.COMPLETE,
        extraction_status=ExtractionStatus.COMPLETE,
        confidence=1.0,
        metadata={},
        created_by=None,
    )
    second = repo.create(
        project_id=project.id,
        filename="repeat.txt",
        content_type="text/plain",
        file_type=FileType.TEXT,
        file_version=None,
        source=FileSource.USER_UPLOAD,
        storage_path=f"{project.id}/{uuid4()}.txt",
        parsing_status=ParsingStatus.COMPLETE,
        extraction_status=ExtractionStatus.COMPLETE,
        confidence=1.0,
        metadata={},
        created_by=None,
    )

    assert first.file_version == 1
    assert second.file_version == 2


def test_file_repository_is_project_scoped(db_session) -> None:
    service = build_project_service()
    project_a = service.create_project("Project A").project
    project_b = service.create_project("Project B").project
    repo = PostgresFileRepository()

    record = repo.create(
        project_id=project_a.id,
        filename="scoped.txt",
        content_type="text/plain",
        file_type=FileType.TEXT,
        file_version=None,
        source=FileSource.USER_UPLOAD,
        storage_path=f"{project_a.id}/{uuid4()}.txt",
        parsing_status=ParsingStatus.COMPLETE,
        extraction_status=ExtractionStatus.COMPLETE,
        confidence=1.0,
        metadata={},
        created_by=None,
    )

    assert repo.get_by_id(project_b.id, record.id) is None
    assert repo.list_for_project(project_b.id) == []
