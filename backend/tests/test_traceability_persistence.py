"""Persistence tests for traceability repository."""

from uuid import uuid4

from app.application.service_factory import build_project_service
from app.domain.models.traceability import TraceabilityRelationshipType
from app.infrastructure.repositories.postgres_traceability_repository import (
    PostgresTraceabilityRepository,
)


def test_traceability_repository_create_and_query(db_session) -> None:
    project = build_project_service().create_project("Trace Repo").project
    repo = PostgresTraceabilityRepository()
    file_id = uuid4()
    memory_id = uuid4()

    link = repo.create_link(
        project.id,
        source_type="file",
        source_id=file_id,
        target_type="memory",
        target_id=memory_id,
        relationship_type=TraceabilityRelationshipType.SOURCE_TO_MEMORY,
        metadata={"filename": "loads.txt"},
    )

    by_source = repo.get_links_by_source(
        project.id,
        source_type="file",
        source_id=file_id,
    )
    assert len(by_source) == 1
    assert by_source[0].id == link.id

    by_target = repo.get_links_by_target(
        project.id,
        target_type="memory",
        target_id=memory_id,
    )
    assert len(by_target) == 1


def test_traceability_repository_project_scoped(db_session) -> None:
    service = build_project_service()
    project_a = service.create_project("Trace A").project
    project_b = service.create_project("Trace B").project
    repo = PostgresTraceabilityRepository()
    source_id = uuid4()
    target_id = uuid4()

    repo.create_link(
        project_a.id,
        source_type="file",
        source_id=source_id,
        target_type="memory",
        target_id=target_id,
        relationship_type=TraceabilityRelationshipType.SOURCE_TO_MEMORY,
    )

    assert repo.get_links_by_source(project_b.id, source_type="file", source_id=source_id) == []
    assert repo.list_for_project(project_b.id) == []


def test_traceability_repository_list_for_project(db_session) -> None:
    project = build_project_service().create_project("Trace Graph").project
    repo = PostgresTraceabilityRepository()

    repo.create_link(
        project.id,
        source_type="file",
        source_id=uuid4(),
        target_type="memory",
        target_id=uuid4(),
        relationship_type=TraceabilityRelationshipType.SOURCE_TO_MEMORY,
    )
    repo.create_link(
        project.id,
        source_type="memory",
        source_id=uuid4(),
        target_type="approval",
        target_id=uuid4(),
        relationship_type=TraceabilityRelationshipType.DECISION_TO_APPROVAL,
    )

    assert len(repo.list_for_project(project.id)) == 2
