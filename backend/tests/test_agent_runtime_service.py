"""Service tests for engineering agent runtime."""

from app.application.service_factory import (
    build_agent_runtime_service,
    build_project_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus


def _create_project(db_session: str):
    return build_project_service().create_project(name="Runtime Service Project")


def test_agent_runtime_executes_with_explicit_agent_type(db_session: str) -> None:
    project = _create_project(db_session)
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Analyze the lateral system",
            requires_approval=False,
        ),
        actor_id="engineer-1",
    )

    assert record.execution_status == AgentExecutionStatus.COMPLETED
    assert record.output is not None
    assert record.output["agent_type"] == EngineeringAgentType.ANALYSIS_AGENT.value
    assert record.context_snapshot["project_name"] == project.project.name
    assert record.traceability_metadata["request_trace_id"]


def test_agent_runtime_prompt_generation_selects_agent(db_session: str) -> None:
    project = _create_project(db_session)
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            user_request="Prepare a seismic load assessment",
            requires_approval=False,
        ),
        actor_id="engineer-1",
    )

    assert record.prompt_generation is not None
    assert record.output is not None
    assert record.output["agent_type"] == EngineeringAgentType.SEISMIC_AGENT.value


def test_agent_runtime_high_impact_agent_waits_for_approval(db_session: str) -> None:
    project = _create_project(db_session)
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            user_request="Update the structural model geometry",
        ),
        actor_id="engineer-1",
    )

    assert record.execution_status in {
        AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL,
        AgentExecutionStatus.WAITING_APPROVAL,
    }
    assert record.approval_request_id is not None


def test_agent_runtime_list_and_get_execution(db_session: str) -> None:
    project = _create_project(db_session)
    runtime = build_agent_runtime_service()

    created = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.VALIDATION_AGENT,
            user_request="Validate code checks",
            requires_approval=False,
        ),
        actor_id="engineer-1",
    )

    loaded = runtime.get_execution(created.id)
    assert loaded.id == created.id

    history = runtime.list_executions(project.project.id)
    assert len(history) == 1
