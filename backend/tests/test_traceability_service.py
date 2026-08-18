"""Traceability service tests."""

from uuid import uuid4

from app.application.service_factory import (
    build_document_indexing_service,
    build_file_ingestion_service,
    build_human_approval_service,
    build_traceability_service,
    build_project_service,
)
from app.domain.models.human_approval import ApprovalTargetType
from app.domain.models.traceability import TraceObjectType, TraceabilityRelationshipType


def test_create_link_and_project_graph(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Trace Service").project
    service = build_traceability_service()
    source_id = uuid4()
    target_id = uuid4()

    service.create_link(
        project.id,
        source_type=TraceObjectType.REQUIREMENT.value,
        source_id=source_id,
        target_type=TraceObjectType.FILE.value,
        target_id=target_id,
        relationship_type=TraceabilityRelationshipType.REQUIREMENT_TO_SOURCE,
    )

    graph = service.get_project_graph(project.id)
    assert len(graph.links) == 1
    assert len(graph.nodes) == 2


def test_query_lineage_walks_backward(db_session) -> None:
    project = build_project_service().create_project("Lineage").project
    service = build_traceability_service()
    requirement_id = uuid4()
    file_id = uuid4()
    memory_id = uuid4()
    design_id = uuid4()

    service.create_link(
        project.id,
        source_type="requirement",
        source_id=requirement_id,
        target_type="file",
        target_id=file_id,
        relationship_type=TraceabilityRelationshipType.REQUIREMENT_TO_SOURCE,
    )
    service.create_link(
        project.id,
        source_type="file",
        source_id=file_id,
        target_type="memory",
        target_id=memory_id,
        relationship_type=TraceabilityRelationshipType.SOURCE_TO_MEMORY,
    )
    service.create_link(
        project.id,
        source_type="memory",
        source_id=memory_id,
        target_type="design_result",
        target_id=design_id,
        relationship_type=TraceabilityRelationshipType.ANALYSIS_TO_DESIGN,
    )

    chain = service.query_lineage(
        project.id,
        object_type="design_result",
        object_id=design_id,
    )
    relationship_types = {link.relationship_type for link in chain.links}
    assert TraceabilityRelationshipType.ANALYSIS_TO_DESIGN in relationship_types
    assert TraceabilityRelationshipType.SOURCE_TO_MEMORY in relationship_types
    assert TraceabilityRelationshipType.REQUIREMENT_TO_SOURCE in relationship_types


def test_document_indexing_creates_source_to_memory_link(db_session, file_storage_root) -> None:
    project = build_project_service().create_project("Index Trace").project
    uploaded = build_file_ingestion_service().ingest_upload(
        project.id,
        filename="trace.txt",
        content=b"line one",
        content_type="text/plain",
        created_by="uploader",
    )
    memory = build_document_indexing_service().index_file(project.id, uploaded.id)

    links = build_traceability_service().get_links_by_target(
        project.id,
        target_type=TraceObjectType.MEMORY.value,
        target_id=memory.id,
    )
    assert len(links) == 1
    assert links[0].relationship_type == TraceabilityRelationshipType.SOURCE_TO_MEMORY
    assert links[0].source_id == uploaded.id


def test_approval_creates_decision_to_approval_link(db_session) -> None:
    project = build_project_service().create_project("Approval Trace").project
    approval_service = build_human_approval_service()
    traceability = build_traceability_service()

    request = approval_service.create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.MODEL_CHANGE,
        target_action="pem.update",
        summary="Publish PEM update",
    )
    approval_service.approve_request(
        project.id,
        request.id,
        approver="reviewer-1",
    )

    links = traceability.get_links_by_target(
        project.id,
        target_type=TraceObjectType.APPROVAL.value,
        target_id=request.id,
    )
    assert len(links) == 1
    assert links[0].relationship_type == TraceabilityRelationshipType.DECISION_TO_APPROVAL
