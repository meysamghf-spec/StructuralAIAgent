"""Application service tests for project memory."""

from uuid import uuid4

import pytest

from app.application.exceptions import ProjectNotFoundError
from app.application.service_factory import build_project_memory_service, build_project_service
from app.domain.models.project_memory import MemoryType


def test_project_memory_service_create_and_list(db_session) -> None:
    project = build_project_service().create_project("Service Memory").project
    service = build_project_memory_service()

    created = service.create_memory(
        project.id,
        MemoryType.DESIGN_CHOICE,
        "Use concrete core walls.",
        source_type="file",
        confidence=0.8,
        metadata={"discipline": "structural"},
        created_by="designer-1",
    )

    memories = service.list_memories(project.id)
    assert len(memories) == 1
    assert memories[0].id == created.id


def test_project_memory_service_list_by_type(db_session) -> None:
    project = build_project_service().create_project("Typed Service Memory").project
    service = build_project_memory_service()

    service.create_memory(project.id, MemoryType.ASSUMPTION, "Wind speed 120 mph")
    service.create_memory(project.id, MemoryType.REJECTION, "Rejected alternate framing")

    assumptions = service.list_memories_by_type(project.id, MemoryType.ASSUMPTION)
    assert len(assumptions) == 1
    assert assumptions[0].memory_type == MemoryType.ASSUMPTION


def test_project_memory_service_get_and_delete(db_session) -> None:
    project = build_project_service().create_project("Delete Memory").project
    service = build_project_memory_service()

    created = service.create_memory(
        project.id,
        MemoryType.VALIDATION_RESULT,
        "Gravity load check passed.",
    )

    loaded = service.get_memory(project.id, created.id)
    assert loaded is not None
    assert loaded.content == "Gravity load check passed."

    assert service.delete_memory(project.id, created.id) is True
    assert service.get_memory(project.id, created.id) is None


def test_project_memory_service_unknown_project(db_session) -> None:
    service = build_project_memory_service()
    missing_project = uuid4()

    with pytest.raises(ProjectNotFoundError):
        service.list_memories(missing_project)

    with pytest.raises(ProjectNotFoundError):
        service.create_memory(
            missing_project,
            MemoryType.CONVERSATION,
            "Should fail",
        )


def test_project_memory_service_project_isolation(db_session) -> None:
    service = build_project_service()
    project_a = service.create_project("Iso Memory A").project
    project_b = service.create_project("Iso Memory B").project
    memory_service = build_project_memory_service()

    record = memory_service.create_memory(
        project_a.id,
        MemoryType.REVISION,
        "Revision note for project A",
    )

    assert memory_service.list_memories(project_b.id) == []
    assert memory_service.get_memory(project_b.id, record.id) is None
    assert memory_service.delete_memory(project_b.id, record.id) is False


def test_project_memory_service_retrieve_by_source(db_session) -> None:
    project = build_project_service().create_project("Retrieve Memory").project
    service = build_project_memory_service()
    source_id = uuid4()

    service.create_memory(
        project.id,
        MemoryType.EXTRACTED_INFORMATION,
        "Extracted beam sizes.",
        source_type="file",
        source_id=source_id,
    )
    service.create_memory(
        project.id,
        MemoryType.DECISION,
        "Unrelated decision",
        source_type="conversation",
    )

    results = service.retrieve_memories(
        project.id,
        source_type="file",
        source_id=source_id,
    )
    assert len(results) == 1
    assert results[0].content == "Extracted beam sizes."


def test_project_memory_service_get_project_context(db_session) -> None:
    project = build_project_service().create_project("Context Memory").project
    service = build_project_memory_service()

    service.create_memory(project.id, MemoryType.DECISION, "Decision 1")
    service.create_memory(project.id, MemoryType.DECISION, "Decision 2")
    service.create_memory(project.id, MemoryType.ASSUMPTION, "Assumption 1")

    context = service.get_project_context(project.id)
    assert context.project_id == project.id
    assert context.total_count == 3
    assert context.counts_by_type == {"DECISION": 2, "ASSUMPTION": 1}
    assert len(context.memories) == 3
