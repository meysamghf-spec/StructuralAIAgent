"""Approval completion hook tests for agent executions."""

from app.application.service_factory import (
    build_agent_runtime_service,
    build_human_approval_service,
    build_project_memory_service,
    build_traceability_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus
from app.domain.models.agent_runtime_view import AGENT_EXECUTION_MEMORY_SOURCE_TYPE
from app.domain.models.project_memory import MemoryType
from app.domain.models.traceability import TraceabilityRelationshipType


def _create_project():
    from app.application.service_factory import build_project_service

    return build_project_service().create_project("Approval Completion Project").project


def test_approved_agent_execution_completes_and_links_report(db_session) -> None:
    project = _create_project()
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
    traceability = build_traceability_service()
    memory_service = build_project_memory_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            user_request="Update the structural model",
        ),
        actor_id="engineer-1",
    )
    assert execution.execution_status in {
        AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL,
        AgentExecutionStatus.WAITING_APPROVAL,
    }
    assert execution.approval_request_id is not None

    approval_service.approve_request(
        project.id,
        execution.approval_request_id,
        approver="reviewer-1",
        decision_note="Model change accepted",
    )

    completed = runtime.get_execution(execution.id)
    assert completed.execution_status == AgentExecutionStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.traceability_metadata.get("report_id") is not None
    assert completed.traceability_metadata.get("orchestration") is not None

    graph = traceability.get_project_graph(project.id)
    relationships = {link.relationship_type for link in graph.links}
    assert TraceabilityRelationshipType.APPROVAL_TO_AGENT_RESULT in relationships
    assert TraceabilityRelationshipType.AGENT_RESULT_TO_REPORT in relationships

    memories = memory_service.retrieve_memories(
        project.id,
        source_type=AGENT_EXECUTION_MEMORY_SOURCE_TYPE,
        source_id=execution.id,
    )
    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.DECISION


def test_rejected_agent_execution_stores_reason_and_memory(db_session) -> None:
    project = _create_project()
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
    memory_service = build_project_memory_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.STEEL_DESIGN_AGENT,
            user_request="Revise steel connection design",
        ),
        actor_id="engineer-1",
    )
    assert execution.approval_request_id is not None

    approval_service.reject_request(
        project.id,
        execution.approval_request_id,
        approver="reviewer-1",
        rejection_reason="Connection detail needs manual review",
    )

    rejected = runtime.get_execution(execution.id)
    assert rejected.execution_status == AgentExecutionStatus.CANCELLED
    assert rejected.error_metadata["approval_decision"] == "REJECTED"
    assert "manual review" in rejected.error_metadata["rejection_reason"]

    memories = memory_service.retrieve_memories(
        project.id,
        source_type=AGENT_EXECUTION_MEMORY_SOURCE_TYPE,
        source_id=execution.id,
    )
    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.REJECTION


def test_execution_user_view_reflects_progress(db_session) -> None:
    from app.domain.models.agent_runtime_view import build_agent_execution_user_view

    project = _create_project()
    runtime = build_agent_runtime_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            user_request="Modify lateral system",
        ),
        actor_id="engineer-1",
    )
    waiting_view = build_agent_execution_user_view(execution)
    assert waiting_view.progress == "awaiting_approval"
    assert waiting_view.requires_approval is True

    build_human_approval_service().approve_request(
        project.id,
        execution.approval_request_id,
        approver="reviewer-1",
    )
    completed = runtime.get_execution(execution.id)
    completed_view = build_agent_execution_user_view(completed)
    assert completed_view.progress == "completed"
    assert completed_view.requires_approval is False
    assert completed_view.final_result is not None
