"""Orchestration integration tests for agent runtime."""

from app.application.service_factory import build_agent_runtime_service, build_project_service
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus


def test_agent_execution_delegates_validation_to_orchestration(db_session) -> None:
    project = build_project_service().create_project("Orchestration Runtime").project
    runtime = build_agent_runtime_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.VALIDATION_AGENT,
            user_request="Validate project configuration",
            requires_approval=False,
        ),
        actor_id="engineer-1",
    )

    assert execution.execution_status == AgentExecutionStatus.COMPLETED
    assert execution.agent_result is not None
    orchestration = execution.agent_result.validation_information.get("orchestration")
    assert orchestration is not None
    assert orchestration["task_type"] == "project.validate"
    assert orchestration["route"] == "VALIDATION"


def test_agent_execution_supports_explicit_orchestration_task(db_session) -> None:
    project = build_project_service().create_project("Orchestration Explicit").project
    runtime = build_agent_runtime_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Review code defaults",
            requires_approval=False,
            parameters={
                "orchestration_task": "code.defaults",
                "orchestration_payload": {},
            },
        ),
        actor_id="engineer-1",
    )

    orchestration = execution.agent_result.validation_information.get("orchestration")
    assert orchestration is not None
    assert orchestration["task_type"] == "code.defaults"
    assert orchestration["route"] == "DETERMINISTIC"
