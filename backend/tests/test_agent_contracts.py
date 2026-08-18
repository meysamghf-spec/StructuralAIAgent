"""Contract-only model tests — no runtime execution or approval workflow."""

from uuid import uuid4

from app.domain.models.agent_execution import AgentExecution, AgentExecutionStatus
from app.domain.models.human_approval import ApprovalRequest, ApprovalStatus


def test_agent_execution_contract_shape() -> None:
    execution = AgentExecution(
        execution_id=uuid4(),
        agent_definition_id=uuid4(),
        agent_version=1,
        input={"task": "analyze"},
        status=AgentExecutionStatus.PENDING,
    )
    assert execution.output is None
    assert execution.status == AgentExecutionStatus.PENDING


def test_human_approval_request_contract_shape() -> None:
    request = ApprovalRequest(
        request_id=uuid4(),
        task_type="structural_system_selection",
        summary="Proposed steel moment frame",
        context={"alternative_count": 2},
    )
    assert request.status == ApprovalStatus.PENDING
