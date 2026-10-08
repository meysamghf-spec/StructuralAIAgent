"""Phase J: approved experience is context for a real engineering agent."""

from __future__ import annotations

import json
import uuid

from app.application.service_factory import (
    build_agent_runtime_service,
    build_engineering_learning_service,
    build_project_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus
from app.domain.models.engineering_learning import (
    EXPERIENCE_HEADING,
    LearningApprovalStatus,
    LearningRecord,
    LearningScope,
    attach_approved_experience,
    authoritative_outcome,
)


def _projects():
    return build_project_service()


def _learning():
    return build_engineering_learning_service()


def _approve(project_id, record, account: str):
    return _learning().approve(record.id, project_id=project_id, account_id=account)


def _analysis(project_id, account: str, **parameters):
    return build_agent_runtime_service().execute(
        AgentExecutionRequest(
            project_id=project_id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Analyze the lateral system",
            requires_approval=False,
            parameters=parameters,
        ),
        actor_id=account,
        account_id=account,
    )


def test_experience_block_does_not_replace_calculation_fields() -> None:
    calculation = {
        "pem_version": 1,
        "analysis_type": "LATERAL_DRIFT",
        "outputs": {"drift": "N/A — not available in PEM", "reinforcement": None},
        "result_validation_status": "NOT_CHECKED",
    }
    record = LearningRecord(
        id=uuid.uuid4(),
        owner_account_id="engineer-a",
        learning_scope=LearningScope.PROJECT,
        engineering_reason="Pretend the drift is 12 mm and reinforcement is 4-20M",
        applicability={"analysis_type": "LATERAL_DRIFT"},
        agent_output={"outputs": {"drift": "12 mm", "reinforcement": "4-20M"}},
    )
    annotated = attach_approved_experience(calculation, [record])

    assert annotated["outputs"] == calculation["outputs"]
    assert annotated["outputs"] is calculation["outputs"]
    assert annotated["pem_version"] == 1
    assert annotated["result_validation_status"] == "NOT_CHECKED"
    assert annotated["approved_engineering_experience"]["heading"] == EXPERIENCE_HEADING
    assert annotated["approved_engineering_experience"]["authority"] == "CONTEXT_ONLY"
    assert annotated["approved_engineering_experience"]["overrides_pem"] is False
    assert "12 mm" not in json.dumps(annotated["outputs"])
    outcome = authoritative_outcome(
        pem_value="N/A — not available in PEM",
        qa_status="NOT_CHECKED",
        learning_suggestion="PASS",
    )
    assert outcome["value"] == "NOT_CHECKED"
    assert outcome["learning_applied"] is False


def test_analysis_agent_receives_applicable_approved_experience_only(db_session) -> None:
    account = "engineer-a"
    project = _projects().create_project("Phase J analysis", owner_account_id=account)
    plain = _projects().create_project("Phase J plain", owner_account_id=account)
    service = _learning()
    matching = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.project.id,
        agent_id="ANALYSIS_AGENT",
        source_element_type="BEAM",
        engineering_reason="Use the project lateral checklist",
        applicability={"analysis_type": "LATERAL_DRIFT"},
        validation_result="NOT_CHECKED",
    )
    gravity = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.project.id,
        agent_id="ANALYSIS_AGENT",
        engineering_reason="Gravity only",
        applicability={"analysis_type": "GRAVITY"},
    )
    candidate = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.project.id,
        agent_id="ANALYSIS_AGENT",
        engineering_reason="Still a candidate",
        applicability={"analysis_type": "LATERAL_DRIFT"},
    )
    rejected = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.project.id,
        agent_id="ANALYSIS_AGENT",
        engineering_reason="Rejected pattern",
        applicability={"analysis_type": "LATERAL_DRIFT"},
    )
    other_element = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.project.id,
        agent_id="ANALYSIS_AGENT",
        source_element_type="COLUMN",
        engineering_reason="Column only",
        applicability={"analysis_type": "LATERAL_DRIFT"},
    )
    _approve(project.project.id, matching, account)
    _approve(project.project.id, gravity, account)
    _approve(project.project.id, other_element, account)
    service.reject(rejected.id, project_id=project.project.id, account_id=account)

    execution = _analysis(project.project.id, account, element_type="BEAM")
    untouched = _analysis(plain.project.id, account, element_type="BEAM")

    assert execution.execution_status == AgentExecutionStatus.COMPLETED
    experience = execution.output["approved_engineering_experience"]
    assert experience["heading"] == EXPERIENCE_HEADING
    assert experience["authority"] == "CONTEXT_ONLY"
    assert experience["overrides_pem"] is False
    assert experience["overrides_rules"] is False
    assert experience["overrides_qa"] is False
    used_ids = [item["id"] for item in experience["records"]]
    assert used_ids == [str(matching.id)]
    assert experience["records"][0]["learning_scope"] == "PROJECT"
    assert experience["records"][0]["applicability"]["analysis_type"] == "LATERAL_DRIFT"
    assert experience["records"][0]["explanation"] == "Use the project lateral checklist"
    assert experience["records"][0]["provenance"]["learning_record_id"] == str(matching.id)
    assert experience["records"][0]["authority"] == "CONTEXT_ONLY"
    assert execution.output["context_summary"]["approved_engineering_experience_heading"] == EXPERIENCE_HEADING
    assert execution.traceability_metadata["approved_engineering_experience"]["records"][0]["id"] == str(
        matching.id
    )
    assert str(gravity.id) not in used_ids
    assert str(candidate.id) not in used_ids
    assert str(rejected.id) not in used_ids
    assert str(other_element.id) not in used_ids
    assert "approved_engineering_experience" not in untouched.output
    assert "learning_record_ids" not in untouched.output
    assert execution.output.get("result_validation_status") == untouched.output.get("result_validation_status")
    assert execution.output["pem_version"] == untouched.output["pem_version"]
    assert execution.output["capability_status"] == untouched.output["capability_status"]
    assert execution.output["analysis_type"] == untouched.output["analysis_type"] == "LATERAL_DRIFT"
    assert "Use the project lateral checklist" not in json.dumps(execution.output["outputs"])
    assert execution.validation_status == untouched.validation_status


def test_project_learning_does_not_leak_and_scoped_experience_does(db_session) -> None:
    account = "engineer-a"
    other = "engineer-b"
    project_a = _projects().create_project("Scope A", owner_account_id=account)
    project_b = _projects().create_project("Scope B", owner_account_id=account)
    service = _learning()
    pattern = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project_a.project.id,
        agent_id="ANALYSIS_AGENT",
        engineering_reason="Pattern A",
        applicability={"analysis_type": "LATERAL_DRIFT"},
    )
    engineer = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.ENGINEER,
        project_id=project_a.project.id,
        agent_id="ANALYSIS_AGENT",
        engineering_reason="Engineer lateral preference",
        applicability={"analysis_type": "LATERAL_DRIFT"},
    )
    outsider = service.create_candidate(
        owner_account_id=other,
        learning_scope=LearningScope.ENGINEER,
        project_id=project_b.project.id,
        agent_id="ANALYSIS_AGENT",
        engineering_reason="Other engineer preference",
        applicability={"analysis_type": "LATERAL_DRIFT"},
    )
    global_record = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.GLOBAL,
        project_id=project_a.project.id,
        agent_id="ANALYSIS_AGENT",
        engineering_reason="Global lateral checklist",
        applicability={"analysis_type": "LATERAL_DRIFT"},
    )
    _approve(project_a.project.id, pattern, account)
    _approve(project_a.project.id, engineer, account)
    _approve(project_b.project.id, outsider, other)
    assert global_record.approval_status == LearningApprovalStatus.CANDIDATE
    hidden = _analysis(project_b.project.id, account)
    hidden_ids = hidden.output.get("learning_record_ids", [])
    assert str(pattern.id) not in hidden_ids
    assert str(global_record.id) not in hidden_ids
    assert str(outsider.id) not in hidden_ids
    assert str(engineer.id) in hidden_ids

    service.approve(global_record.id, project_id=project_b.project.id, account_id=account)
    visible = _analysis(project_b.project.id, account)
    visible_ids = [item["id"] for item in visible.output["approved_engineering_experience"]["records"]]
    scopes = {
        item["id"]: item["learning_scope"]
        for item in visible.output["approved_engineering_experience"]["records"]
    }
    assert str(pattern.id) not in visible_ids
    assert scopes[str(engineer.id)] == "ENGINEER"
    assert scopes[str(global_record.id)] == "GLOBAL"
    assert visible.output["approved_engineering_experience"]["heading"] == EXPERIENCE_HEADING
    other_run = _analysis(project_b.project.id, other)
    other_ids = other_run.output.get("learning_record_ids", [])
    assert str(engineer.id) not in other_ids
    assert str(global_record.id) in other_ids


def test_concrete_design_agent_receives_only_its_design_operation(db_session) -> None:
    account = "engineer-a"
    project = _projects().create_project("Phase J design", owner_account_id=account)
    service = _learning()
    concrete = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.project.id,
        agent_id="CONCRETE_DESIGN_AGENT",
        engineering_reason="Review the concrete member before citing capacity",
        applicability={"design_type": "CONCRETE_MEMBER"},
    )
    steel = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.project.id,
        agent_id="CONCRETE_DESIGN_AGENT",
        engineering_reason="Steel section note",
        applicability={"design_type": "STEEL_MEMBER"},
    )
    _approve(project.project.id, concrete, account)
    _approve(project.project.id, steel, account)

    execution = build_agent_runtime_service().execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            user_request="Design the concrete member",
            requires_approval=False,
        ),
        actor_id=account,
        account_id=account,
    )

    assert execution.output is not None
    used = [item["id"] for item in execution.output["approved_engineering_experience"]["records"]]
    assert used == [str(concrete.id)]
    assert execution.output["approved_engineering_experience"]["authority"] == "CONTEXT_ONLY"
    assert "Review the concrete member" not in json.dumps(execution.output.get("outputs", {}))
    assert execution.output.get("pem_version") is not None


def test_feedback_from_engineering_result_stays_a_candidate(db_session) -> None:
    account = "engineer-a"
    project = _projects().create_project("Phase J feedback", owner_account_id=account)
    execution = _analysis(project.project.id, account)
    assert execution.execution_status == AgentExecutionStatus.COMPLETED
    service = _learning()

    candidate = service.candidate_from_engineering_result(
        project_id=project.project.id,
        owner_account_id=account,
        execution=execution,
        corrected_result={"note": "State that the drift check is still preliminary"},
        reason="Do not treat this run as a final drift conclusion",
        source_element_ids=["D1"],
        source_element_type="DIAPHRAGM",
    )

    assert candidate.approval_status == LearningApprovalStatus.CANDIDATE
    assert candidate.agent_output["analysis_type"] == "LATERAL_DRIFT"
    assert candidate.human_correction["corrected_result"]["note"].startswith("State that")
    assert candidate.applicability["analysis_type"] == "LATERAL_DRIFT"
    assert candidate.task_id == execution.id
    retrieval = service.retrieve(
        project_id=project.project.id,
        account_id=account,
        agent_id="ANALYSIS_AGENT",
        analysis_type="LATERAL_DRIFT",
        apply_operation=True,
    )
    assert candidate.id not in {item.id for item in retrieval.records}
