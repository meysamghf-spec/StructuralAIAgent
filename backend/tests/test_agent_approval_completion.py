"""Approval completion hook tests for agent executions."""

from uuid import UUID

from app.application.service_factory import (
    build_agent_approval_completion_service,
    build_agent_runtime_service,
    build_human_approval_service,
    build_project_memory_service,
    build_traceability_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus
from app.domain.models.engineering_task import EngineeringTaskStatus
from app.domain.models.agent_runtime_view import AGENT_EXECUTION_MEMORY_SOURCE_TYPE
from app.domain.models.human_approval import ApprovalStatus
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


def test_multi_step_workflow_approval_resume_finalizes_report_and_memory(
    db_session,
    monkeypatch,
) -> None:
    from app.application.engineering_task_execution_service import WorkflowExecutionOutcome
    from app.application.service_factory import build_project_service
    from app.domain.models.agent import EngineeringAgentType
    from app.domain.models.agent_runtime import AgentResult
    from app.domain.models.engineering_task import EngineeringTask

    project = build_project_service().create_project("Multi-step Approval Project").project
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
    memory_service = build_project_memory_service()
    traceability = build_traceability_service()

    complex_request = (
        "Design a three-story reinforced-concrete two-way frame building with a "
        "200 m x 200 m plan. Produce architectural drawings, structural design drawings, "
        "and provide the ETABS model."
    )
    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            user_request=complex_request,
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    assert execution.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    assert execution.approval_request_id is not None
    task = execution.traceability_metadata.get("engineering_task")
    assert task is not None
    assert task.get("paused_step_id") is not None
    assert task.get("status") == "WAITING_FOR_APPROVAL"

    engineering_task = EngineeringTask.model_validate(task)
    completed_result = AgentResult(
        structured_output={
            "agent_type": "WORKFLOW",
            "action": "multi_step_workflow",
            "capability_status": "PARTIALLY_COMPLETED",
            "status_message": "Workflow resumed after approval.",
        },
        recommendations=["Continue with remaining deliverables when integrations are available."],
    )

    class _StubTaskExecution:
        def resume_after_approval(self, **kwargs):
            resumed_task = kwargs["task"]
            resumed_task.paused_step_id = None
            resumed_task.status = EngineeringTaskStatus.PARTIALLY_COMPLETED
            return WorkflowExecutionOutcome(
                task=resumed_task,
                agent_result=completed_result,
                requires_approval=False,
                approval_step_id=None,
                execution_status=AgentExecutionStatus.COMPLETED,
                selected_agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            )

    monkeypatch.setattr(
        "app.application.service_factory.build_engineering_task_execution_service",
        lambda: _StubTaskExecution(),
    )

    approval_service.approve_request(
        project.id,
        execution.approval_request_id,
        approver="reviewer-1",
        decision_note="Continue multi-step workflow",
    )

    completed = runtime.get_execution(execution.id)
    assert completed.execution_status == AgentExecutionStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.traceability_metadata.get("report_id") is not None
    assert completed.traceability_metadata.get("orchestration") is not None
    updated_task = completed.traceability_metadata.get("engineering_task")
    assert updated_task is not None
    assert updated_task.get("paused_step_id") is None

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


def test_multi_step_workflow_creates_second_approval_request_on_later_gate(
    db_session,
    monkeypatch,
) -> None:
    from app.application.engineering_task_execution_service import WorkflowExecutionOutcome
    from app.application.service_factory import build_project_service
    from app.domain.models.agent import EngineeringAgentType
    from app.domain.models.agent_runtime import AgentResult
    from app.domain.models.engineering_task import EngineeringTask

    project = build_project_service().create_project("Two-gate Approval Project").project
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
    memory_service = build_project_memory_service()
    traceability = build_traceability_service()

    complex_request = (
        "Design a three-story reinforced-concrete two-way frame building with a "
        "200 m x 200 m plan. Produce architectural drawings, structural design drawings, "
        "and provide the ETABS model."
    )
    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            user_request=complex_request,
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    first_approval_id = execution.approval_request_id
    assert execution.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    assert first_approval_id is not None

    engineering_task = EngineeringTask.model_validate(
        execution.traceability_metadata["engineering_task"]
    )
    first_paused_step = engineering_task.paused_step_id
    assert first_paused_step is not None

    second_gate_result = AgentResult(
        structured_output={
            "agent_type": "WORKFLOW",
            "action": "multi_step_workflow",
            "capability_status": "WAITING_FOR_APPROVAL",
            "status_message": "Paused at second approval gate.",
        },
        recommendations=["Review structural model before continuing."],
    )
    completed_result = AgentResult(
        structured_output={
            "agent_type": "WORKFLOW",
            "action": "multi_step_workflow",
            "capability_status": "PARTIALLY_COMPLETED",
            "status_message": "Workflow completed after second approval.",
        },
        recommendations=["Continue with remaining deliverables when integrations are available."],
    )

    class _TwoGateTaskExecution:
        resume_count = 0

        def resume_after_approval(self, **kwargs):
            _TwoGateTaskExecution.resume_count += 1
            resumed_task = kwargs["task"]
            if _TwoGateTaskExecution.resume_count == 1:
                resumed_task.paused_step_id = "structural_model"
                resumed_task.resume_from_step_id = "structural_model"
                resumed_task.status = EngineeringTaskStatus.WAITING_FOR_APPROVAL
                return WorkflowExecutionOutcome(
                    task=resumed_task,
                    agent_result=second_gate_result,
                    requires_approval=True,
                    approval_step_id="structural_model",
                    execution_status=AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL,
                    selected_agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
                )
            resumed_task.paused_step_id = None
            resumed_task.status = EngineeringTaskStatus.PARTIALLY_COMPLETED
            return WorkflowExecutionOutcome(
                task=resumed_task,
                agent_result=completed_result,
                requires_approval=False,
                approval_step_id=None,
                execution_status=AgentExecutionStatus.COMPLETED,
                selected_agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            )

    monkeypatch.setattr(
        "app.application.service_factory.build_engineering_task_execution_service",
        lambda: _TwoGateTaskExecution(),
    )

    approval_service.approve_request(
        project.id,
        first_approval_id,
        approver="reviewer-1",
        decision_note="Approve first workflow gate",
    )

    after_first = runtime.get_execution(execution.id)
    assert after_first.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    second_approval_id = after_first.approval_request_id
    assert second_approval_id is not None
    assert second_approval_id != first_approval_id

    second_request = approval_service.get_request(project.id, second_approval_id)
    assert second_request.status == ApprovalStatus.PENDING
    assert second_request.metadata.get("workflow_step_id") == "structural_model"
    assert second_request.metadata.get("prior_approval_request_id") == str(first_approval_id)

    gate_history = after_first.traceability_metadata.get("approval_gate_history") or []
    assert str(first_approval_id) in gate_history or len(gate_history) >= 1
    assert str(second_approval_id) in gate_history

    approval_service.approve_request(
        project.id,
        second_approval_id,
        approver="reviewer-2",
        decision_note="Approve second workflow gate",
    )

    completed = runtime.get_execution(execution.id)
    assert completed.execution_status == AgentExecutionStatus.COMPLETED
    assert completed.completed_at is not None
    assert completed.traceability_metadata.get("report_id") is not None
    updated_task = completed.traceability_metadata.get("engineering_task")
    assert updated_task is not None
    assert updated_task.get("paused_step_id") is None

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


def test_follow_up_approval_creation_is_idempotent_for_same_workflow_step(db_session) -> None:
    from app.application.engineering_task_execution_service import WorkflowExecutionOutcome
    from app.application.service_factory import build_project_service
    from app.domain.models.agent import AgentDefinition, EngineeringAgentType
    from app.domain.models.agent_runtime import AgentExecutionRecord, AgentResult
    from app.domain.models.engineering_task import EngineeringTask, EngineeringTaskStep, WorkflowStepStatus
    from app.domain.models.human_approval import ApprovalTargetType

    project = build_project_service().create_project("Idempotent Approval Project").project
    completion = build_agent_approval_completion_service()

    task = EngineeringTask(
        project_id=project.id,
        original_request="Design a building",
        normalized_objective="Design a building",
        steps=[
            EngineeringTaskStep(
                step_id="structural_model",
                step_number=1,
                title="Create structural model",
                description="Model step",
                capability=EngineeringAgentType.STRUCTURAL_MODELING_AGENT.value,
                capability_kind="agent",
                agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
                status=WorkflowStepStatus.EXECUTABLE,
            )
        ],
        status=EngineeringTaskStatus.WAITING_FOR_APPROVAL,
        paused_step_id="structural_model",
    )
    outcome = WorkflowExecutionOutcome(
        task=task,
        agent_result=AgentResult(structured_output={"capability_status": "WAITING_FOR_APPROVAL"}),
        requires_approval=True,
        approval_step_id="structural_model",
        execution_status=AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL,
        selected_agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
    )
    agent_definition = AgentDefinition(
        id=UUID("00000000-0000-4000-8000-000000000001"),
        key="structural-modeling-agent",
        name="Structural Modeling Agent",
        description="Test agent",
        agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
    )
    execution_id = UUID("00000000-0000-4000-8000-000000000099")
    resolved_request = build_human_approval_service().create_request(
        project.id,
        requester="engineer-1",
        target_type=ApprovalTargetType.AGENT_ACTION,
        target_action="agent.execute",
        summary="Initial gate",
        target_object_type="agent_execution",
        target_object_id=execution_id,
    )
    execution = AgentExecutionRecord(
        id=execution_id,
        project_id=project.id,
        agent_definition_id=agent_definition.id,
        agent_version=1,
        input_request={"user_request": "Design a building"},
        context_snapshot={},
        created_by="engineer-1",
    )

    first = completion._ensure_follow_up_approval_request(  # noqa: SLF001
        project_id=project.id,
        execution=execution,
        resolved_request=resolved_request,
        outcome=outcome,
        agent_definition=agent_definition,
    )
    second = completion._ensure_follow_up_approval_request(  # noqa: SLF001
        project_id=project.id,
        execution=execution,
        resolved_request=resolved_request,
        outcome=outcome,
        agent_definition=agent_definition,
    )
    assert first.id == second.id


def test_multi_step_workflow_supports_three_approval_gates(
    db_session,
    monkeypatch,
) -> None:
    from app.application.engineering_task_execution_service import WorkflowExecutionOutcome
    from app.application.service_factory import build_project_service
    from app.domain.models.agent import EngineeringAgentType
    from app.domain.models.agent_runtime import AgentResult
    from app.domain.models.engineering_task import EngineeringTask

    project = build_project_service().create_project("Three-gate Approval Project").project
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
    traceability = build_traceability_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            user_request=(
                "Design a three-story reinforced-concrete building. "
                "Produce architectural drawings and provide the ETABS model."
            ),
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    approval_ids: list = []
    first_id = execution.approval_request_id
    assert execution.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    assert first_id is not None
    approval_ids.append(first_id)

    gate_sequence = [
        ("structural_model", "Second gate"),
        ("concrete_design", "Third gate"),
    ]
    completed_result = AgentResult(
        structured_output={
            "agent_type": "WORKFLOW",
            "action": "multi_step_workflow",
            "capability_status": "PARTIALLY_COMPLETED",
            "status_message": "Workflow completed after third approval.",
        },
    )

    class _ThreeGateTaskExecution:
        resume_count = 0

        def resume_after_approval(self, **kwargs):
            _ThreeGateTaskExecution.resume_count += 1
            resumed_task = kwargs["task"]
            if _ThreeGateTaskExecution.resume_count <= len(gate_sequence):
                step_id, _ = gate_sequence[_ThreeGateTaskExecution.resume_count - 1]
                resumed_task.paused_step_id = step_id
                resumed_task.resume_from_step_id = step_id
                resumed_task.status = EngineeringTaskStatus.WAITING_FOR_APPROVAL
                return WorkflowExecutionOutcome(
                    task=resumed_task,
                    agent_result=AgentResult(
                        structured_output={
                            "capability_status": "WAITING_FOR_APPROVAL",
                            "status_message": f"Paused at {step_id}.",
                        }
                    ),
                    requires_approval=True,
                    approval_step_id=step_id,
                    execution_status=AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL,
                    selected_agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
                )
            resumed_task.paused_step_id = None
            resumed_task.status = EngineeringTaskStatus.PARTIALLY_COMPLETED
            return WorkflowExecutionOutcome(
                task=resumed_task,
                agent_result=completed_result,
                requires_approval=False,
                approval_step_id=None,
                execution_status=AgentExecutionStatus.COMPLETED,
                selected_agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            )

    monkeypatch.setattr(
        "app.application.service_factory.build_engineering_task_execution_service",
        lambda: _ThreeGateTaskExecution(),
    )

    for gate_index, (expected_step_id, _) in enumerate(gate_sequence, start=1):
        current_id = runtime.get_execution(execution.id).approval_request_id
        approval_service.approve_request(
            project.id,
            current_id,
            approver=f"reviewer-{gate_index}",
            decision_note=f"Approve gate {gate_index}",
        )
        after = runtime.get_execution(execution.id)
        assert after.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
        next_id = after.approval_request_id
        assert next_id is not None
        assert next_id not in approval_ids
        approval_ids.append(next_id)
        pending = approval_service.get_request(project.id, next_id)
        assert pending.status == ApprovalStatus.PENDING
        assert pending.metadata.get("workflow_step_id") == expected_step_id

    final_gate_id = runtime.get_execution(execution.id).approval_request_id
    approval_service.approve_request(
        project.id,
        final_gate_id,
        approver="reviewer-final",
        decision_note="Approve final gate",
    )

    completed = runtime.get_execution(execution.id)
    assert completed.execution_status == AgentExecutionStatus.COMPLETED
    assert completed.traceability_metadata.get("report_id") is not None
    gate_history = completed.traceability_metadata.get("approval_gate_history") or []
    assert len(gate_history) >= 3
    assert len(set(approval_ids)) == 3

    graph = traceability.get_project_graph(project.id)
    relationships = {link.relationship_type for link in graph.links}
    assert TraceabilityRelationshipType.APPROVAL_TO_AGENT_RESULT in relationships
    assert TraceabilityRelationshipType.AGENT_RESULT_TO_REPORT in relationships


def test_single_agent_approval_flow_remains_unchanged(db_session) -> None:
    project = _create_project()
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
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
    original_approval_id = execution.approval_request_id
    assert original_approval_id is not None

    approval_service.approve_request(
        project.id,
        original_approval_id,
        approver="reviewer-1",
        decision_note="Model change accepted",
    )

    completed = runtime.get_execution(execution.id)
    assert completed.execution_status == AgentExecutionStatus.COMPLETED
    assert completed.approval_request_id == original_approval_id
    assert completed.traceability_metadata.get("report_id") is not None

    memories = memory_service.retrieve_memories(
        project.id,
        source_type=AGENT_EXECUTION_MEMORY_SOURCE_TYPE,
        source_id=execution.id,
    )
    assert len(memories) == 1
    assert memories[0].memory_type == MemoryType.DECISION


def test_waiting_execution_actions_include_review_approval(db_session) -> None:
    from app.application.conversation_service import _build_workspace_actions

    project = _create_project()
    execution = build_agent_runtime_service().execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            user_request="Update the structural model",
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
    )
    assert execution.approval_request_id is not None
    actions = _build_workspace_actions(execution)
    review = next(item for item in actions if item["label"] == "Review approval")
    assert str(project.id) in review["href"]
    assert str(execution.approval_request_id) in review["href"]
    assert "/workspace/approvals" in review["href"]


def test_approval_completion_appends_follow_up_chat_message(db_session) -> None:
    from app.domain.models.conversation import MessageRole
    from app.infrastructure.repositories.postgres_conversation_repository import (
        PostgresConversationRepository,
    )

    project = _create_project()
    repo = PostgresConversationRepository()
    conversation = repo.create(
        account_id="engineer-1",
        title="Approval follow-up",
        project_id=project.id,
    )
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            user_request="Update the structural model",
            parameters={
                "conversation_id": str(conversation.id),
                "allow_missing_inputs": True,
            },
        ),
        actor_id="engineer-1",
    )
    assert execution.approval_request_id is not None

    approval_service.approve_request(
        project.id,
        execution.approval_request_id,
        approver="reviewer-1",
        decision_note="Continue",
    )

    messages = repo.list_messages(conversation.id)
    follow_ups = [
        item
        for item in messages
        if item.role == MessageRole.ASSISTANT
        and (item.metadata or {}).get("follow_up_reason") == "approval_finalized"
    ]
    assert len(follow_ups) == 1
    action_labels = [action["label"] for action in follow_ups[0].metadata.get("actions") or []]
    assert "View Reports" in action_labels
    assert "View Memory" in action_labels
    assert "View Traceability" in action_labels
    assert follow_ups[0].metadata.get("report_id")


def test_real_multi_step_resume_creates_second_approval_request(db_session) -> None:
    project = _create_project()
    runtime = build_agent_runtime_service()
    approval_service = build_human_approval_service()
    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            user_request=(
                "Design a three-story reinforced-concrete two-way frame building with a "
                "200 m x 200 m plan. Produce architectural drawings, structural design drawings, "
                "and provide the ETABS model."
            ),
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    first_approval_id = execution.approval_request_id
    assert execution.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    assert first_approval_id is not None

    approval_service.approve_request(
        project.id,
        first_approval_id,
        approver="reviewer-1",
        decision_note="Approve first workflow gate",
    )

    after = runtime.get_execution(execution.id)
    assert after.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    second_approval_id = after.approval_request_id
    assert second_approval_id is not None
    assert second_approval_id != first_approval_id
    second_request = approval_service.get_request(project.id, second_approval_id)
    assert second_request.status == ApprovalStatus.PENDING
    assert second_request.metadata.get("prior_approval_request_id") == str(first_approval_id)