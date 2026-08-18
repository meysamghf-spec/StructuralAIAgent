"""Domain tests for engineering agent runtime models."""

from uuid import uuid4

from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import (
    AgentExecutionRecord,
    AgentExecutionRequest,
    AgentExecutionStatus,
    AgentResult,
    AgentValidationStatus,
    PromptGenerationResult,
)
from app.domain.models.traceability import TraceObjectType, TraceabilityRelationshipType


def test_engineering_agent_types_include_specialized_agents() -> None:
    values = {item.value for item in EngineeringAgentType}
    assert "STRUCTURAL_MODELING_AGENT" in values
    assert "DOCUMENT_INTERPRETATION_AGENT" in values
    assert "PROMPT_GENERATION_AGENT" in values


def test_agent_execution_statuses_include_approval_gate() -> None:
    values = {item.value for item in AgentExecutionStatus}
    assert "WAITING_APPROVAL" in values
    assert "COMPLETED" in values


def test_agent_result_contract_shape() -> None:
    result = AgentResult(
        structured_output={"action": "stub"},
        confidence=0.0,
        recommendations=["review"],
        validation_information={"stub": True},
    )
    assert result.generated_artifacts == []


def test_agent_execution_record_round_trip_fields() -> None:
    record = AgentExecutionRecord(
        id=uuid4(),
        project_id=uuid4(),
        agent_definition_id=uuid4(),
        agent_version=1,
        execution_status=AgentExecutionStatus.CREATED,
        validation_status=AgentValidationStatus.NOT_RUN,
    )
    assert record.output is None
    assert record.approval_request_id is None


def test_prompt_generation_result_contract() -> None:
    result = PromptGenerationResult(
        selected_agent_type=EngineeringAgentType.ANALYSIS_AGENT,
        generated_prompt="Analyze the frame",
        context_requirements=["project_memory"],
    )
    assert "project_memory" in result.context_requirements


def test_traceability_enums_include_agent_runtime() -> None:
    assert TraceObjectType.AGENT_EXECUTION.value == "agent_execution"
    assert TraceObjectType.AGENT_RESULT.value == "agent_result"
    assert TraceabilityRelationshipType.REQUEST_TO_AGENT_EXECUTION.value == "REQUEST_TO_AGENT_EXECUTION"
    assert TraceabilityRelationshipType.AGENT_RESULT_TO_REPORT.value == "AGENT_RESULT_TO_REPORT"
