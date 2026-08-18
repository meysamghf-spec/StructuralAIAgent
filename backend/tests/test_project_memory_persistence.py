"""Persistence tests for project memory repository."""

from uuid import uuid4

from app.application.service_factory import build_project_service
from app.domain.models.project_memory import MemoryType
from app.infrastructure.repositories.postgres_project_memory_repository import (
    PostgresProjectMemoryRepository,
)


def test_project_memory_repository_create_get_list_and_delete(db_session) -> None:
    project = build_project_service().create_project("Memory Project").project
    repo = PostgresProjectMemoryRepository()

    created = repo.create(
        project.id,
        MemoryType.DECISION,
        "Use US customary units for this tower.",
        source_type="conversation",
        confidence=0.95,
        metadata={"topic": "units"},
        created_by="engineer-1",
    )

    assert created.project_id == project.id
    assert created.memory_type == MemoryType.DECISION
    assert created.metadata["topic"] == "units"

    loaded = repo.get_by_id(project.id, created.id)
    assert loaded is not None
    assert loaded.content == created.content

    listed = repo.list_for_project(project.id)
    assert len(listed) == 1
    assert listed[0].id == created.id

    assert repo.delete(project.id, created.id) is True
    assert repo.get_by_id(project.id, created.id) is None


def test_project_memory_repository_list_by_type(db_session) -> None:
    project = build_project_service().create_project("Typed Memory").project
    repo = PostgresProjectMemoryRepository()

    repo.create(project.id, MemoryType.DECISION, "Decision A")
    repo.create(project.id, MemoryType.ASSUMPTION, "Assumption B")
    repo.create(project.id, MemoryType.DECISION, "Decision C")

    decisions = repo.list_by_type(project.id, MemoryType.DECISION)
    assert len(decisions) == 2
    assert {item.content for item in decisions} == {"Decision A", "Decision C"}


def test_project_memory_repository_is_project_scoped(db_session) -> None:
    service = build_project_service()
    project_a = service.create_project("Memory A").project
    project_b = service.create_project("Memory B").project
    repo = PostgresProjectMemoryRepository()

    record = repo.create(project_a.id, MemoryType.REQUIREMENT, "Project A requirement")

    assert repo.get_by_id(project_b.id, record.id) is None
    assert repo.list_for_project(project_b.id) == []
    assert repo.list_by_type(project_b.id, MemoryType.REQUIREMENT) == []
    assert repo.delete(project_b.id, record.id) is False


def test_project_memory_repository_search_by_source_and_type(db_session) -> None:
    project = build_project_service().create_project("Search Memory").project
    repo = PostgresProjectMemoryRepository()
    source_id = uuid4()

    repo.create(
        project.id,
        MemoryType.DECISION,
        "From file A",
        source_type="file",
        source_id=source_id,
    )
    repo.create(
        project.id,
        MemoryType.ASSUMPTION,
        "From file A assumption",
        source_type="file",
        source_id=source_id,
    )
    repo.create(
        project.id,
        MemoryType.DECISION,
        "From conversation",
        source_type="conversation",
    )

    by_source = repo.search(project.id, source_type="file", source_id=source_id)
    assert len(by_source) == 2

    by_type = repo.search(
        project.id,
        source_type="file",
        source_id=source_id,
        memory_type=MemoryType.DECISION,
    )
    assert len(by_type) == 1
    assert by_type[0].content == "From file A"
