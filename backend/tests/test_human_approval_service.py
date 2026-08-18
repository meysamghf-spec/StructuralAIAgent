"""Human Approval service tests."""

from uuid import uuid4

import pytest

from app.application.exceptions import ApprovalInvalidStateError, ApprovalNotFoundError
from app.application.service_factory import (
    build_human_approval_service,
    build_project_memory_service,
    build_project_service,
)
from app.domain.models.human_approval import (
    APPROVAL_MEMORY_SOURCE_TYPE,
    ApprovalStatus,
    ApprovalTargetType,
)
from app.domain.models.project_memory import MemoryType


def test_create_and_list_pending_approval(db_session) -> None:
    project = build_project_service().create_project("Approval Service").project
    service = build_human_approval_service()

    request = service.create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.CONFIGURATION_CHANGE,
        target_action="code.configuration.update",
        summary="Switch to jurisdictionally adopted IBC profile",
    )

    pending = service.list_pending(project.id)
    assert len(pending) == 1
    assert pending[0].id == request.id


def test_approve_request_records_decision_memory(db_session) -> None:
    project = build_project_service().create_project("Approve Memory").project
    service = build_human_approval_service()
    memory_service = build_project_memory_service()

    request = service.create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.MODEL_CHANGE,
        target_action="pem.update",
        summary="Publish revised PEM",
    )

    approved = service.approve_request(
        project.id,
        request.id,
        approver="reviewer-1",
        decision_note="Reviewed and accepted",
    )
    assert approved.status == ApprovalStatus.APPROVED

    memories = memory_service.retrieve_memories(
        project.id,
        source_type=APPROVAL_MEMORY_SOURCE_TYPE,
        source_id=request.id,
    )
    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.DECISION
    assert "Approved" in memories[0].content


def test_reject_request_records_rejection_memory(db_session) -> None:
    project = build_project_service().create_project("Reject Memory").project
    service = build_human_approval_service()
    memory_service = build_project_memory_service()

    request = service.create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.DESIGN_DECISION,
        target_action="design.assumption.approve",
        summary="Approve higher drift limit",
    )

    rejected = service.reject_request(
        project.id,
        request.id,
        approver="reviewer-1",
        rejection_reason="Drift limit exceeds client criteria",
    )
    assert rejected.status == ApprovalStatus.REJECTED

    memories = memory_service.retrieve_memories(
        project.id,
        source_type=APPROVAL_MEMORY_SOURCE_TYPE,
        source_id=request.id,
    )
    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.REJECTION


def test_cancel_request(db_session) -> None:
    project = build_project_service().create_project("Cancel Approval").project
    service = build_human_approval_service()

    request = service.create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.AGENT_ACTION,
        target_action="agent.activate",
        summary="Activate load agent",
    )

    cancelled = service.cancel_request(
        project.id,
        request.id,
        actor="engineer-1",
        reason="No longer needed",
    )
    assert cancelled.status == ApprovalStatus.CANCELLED


def test_approve_already_resolved_request_raises(db_session) -> None:
    project = build_project_service().create_project("Invalid State").project
    service = build_human_approval_service()

    request = service.create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.MODEL_CHANGE,
        target_action="pem.update",
        summary="Update PEM",
    )
    service.approve_request(project.id, request.id, approver="reviewer-1")

    with pytest.raises(ApprovalInvalidStateError):
        service.reject_request(
            project.id,
            request.id,
            approver="reviewer-1",
            rejection_reason="Too late",
        )


def test_get_missing_request_raises(db_session) -> None:
    project = build_project_service().create_project("Missing Approval").project
    service = build_human_approval_service()

    with pytest.raises(ApprovalNotFoundError):
        service.get_request(project.id, uuid4())
