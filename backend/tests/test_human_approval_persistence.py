"""Persistence tests for human approval repository."""

from uuid import uuid4

from app.application.service_factory import build_project_service
from app.domain.models.human_approval import ApprovalEventType, ApprovalStatus, ApprovalTargetType
from app.infrastructure.repositories.postgres_human_approval_repository import (
    PostgresHumanApprovalRepository,
)


def test_human_approval_repository_create_get_and_list(db_session) -> None:
    project = build_project_service().create_project("Approval Project").project
    repo = PostgresHumanApprovalRepository()

    created = repo.create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.MODEL_CHANGE,
        target_action="pem.update",
        summary="Update lateral system assumptions",
        target_object_type="pem_snapshot",
        metadata={"version": 2},
    )

    assert created.status == ApprovalStatus.PENDING
    assert created.target_type == ApprovalTargetType.MODEL_CHANGE

    loaded = repo.get_request(project.id, created.id)
    assert loaded is not None
    assert loaded.summary == created.summary

    pending = repo.list_requests(project.id, status=ApprovalStatus.PENDING)
    assert len(pending) == 1


def test_human_approval_repository_update_and_events(db_session) -> None:
    project = build_project_service().create_project("Approval Events").project
    repo = PostgresHumanApprovalRepository()

    request = repo.create_request(
        project.id,
        requester="requester-1",
        target_type=ApprovalTargetType.AGENT_ACTION,
        target_action="agent.activate",
        summary="Activate structural modeling agent",
    )

    repo.create_event(
        project.id,
        request.id,
        event_type=ApprovalEventType.CREATED,
        actor="requester-1",
    )

    updated = repo.update_request(
        project.id,
        request.id,
        status=ApprovalStatus.APPROVED,
        approver="reviewer-1",
        decision=ApprovalStatus.APPROVED,
    )
    assert updated is not None
    assert updated.status == ApprovalStatus.APPROVED

    repo.create_event(
        project.id,
        request.id,
        event_type=ApprovalEventType.APPROVED,
        actor="reviewer-1",
    )

    events = repo.list_events(project.id, approval_request_id=request.id)
    assert len(events) == 2
    assert events[0].event_type == ApprovalEventType.CREATED
    assert events[1].event_type == ApprovalEventType.APPROVED


def test_human_approval_repository_is_project_scoped(db_session) -> None:
    service = build_project_service()
    project_a = service.create_project("Approval A").project
    project_b = service.create_project("Approval B").project
    repo = PostgresHumanApprovalRepository()

    request = repo.create_request(
        project_a.id,
        requester="engineer",
        target_type=ApprovalTargetType.DESIGN_DECISION,
        target_action="design.assumption.approve",
        summary="Approve base shear",
    )

    assert repo.get_request(project_b.id, request.id) is None
    assert repo.list_requests(project_b.id) == []
