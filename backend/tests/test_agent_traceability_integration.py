"""Traceability integration tests for agent runtime workflow."""

from app.application.service_factory import (
    build_agent_runtime_service,
    build_human_approval_service,
    build_traceability_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest
from app.domain.models.traceability import TraceObjectType, TraceabilityRelationshipType


def test_agent_execution_traceability_chain_includes_report(db_session) -> None:
    from app.application.service_factory import build_project_service

    project = build_project_service().create_project("Traceability Workflow").project
    runtime = build_agent_runtime_service()
    approvals = build_human_approval_service()
    traceability = build_traceability_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            user_request="Revise slab thickness",
        ),
        actor_id="engineer-1",
    )
    approvals.approve_request(
        project.id,
        execution.approval_request_id,
        approver="reviewer-1",
    )

    graph = traceability.get_project_graph(project.id)
    link_pairs = {
        (link.source_type, link.target_type, link.relationship_type)
        for link in graph.links
    }

    assert (
        TraceObjectType.USER_REQUEST.value,
        TraceObjectType.AGENT_EXECUTION.value,
        TraceabilityRelationshipType.REQUEST_TO_AGENT_EXECUTION,
    ) in link_pairs
    assert (
        TraceObjectType.AGENT_EXECUTION.value,
        TraceObjectType.AGENT_RESULT.value,
        TraceabilityRelationshipType.AGENT_EXECUTION_TO_RESULT,
    ) in link_pairs
    assert (
        TraceObjectType.AGENT_RESULT.value,
        TraceObjectType.APPROVAL.value,
        TraceabilityRelationshipType.AGENT_RESULT_TO_APPROVAL,
    ) in link_pairs
    assert (
        TraceObjectType.APPROVAL.value,
        TraceObjectType.AGENT_RESULT.value,
        TraceabilityRelationshipType.APPROVAL_TO_AGENT_RESULT,
    ) in link_pairs
    assert (
        TraceObjectType.AGENT_RESULT.value,
        TraceObjectType.REPORT.value,
        TraceabilityRelationshipType.AGENT_RESULT_TO_REPORT,
    ) in link_pairs
