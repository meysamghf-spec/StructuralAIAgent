"""Approval-gated engineering learning: isolation, provenance, and agent use."""

from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.application.exceptions import LearningRecordNotFoundError, LearningSafetyError
from app.application.service_factory import (
    build_agent_runtime_service,
    build_engineering_learning_service,
    build_project_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus
from app.domain.models.engineering_learning import (
    UNAVAILABLE,
    LearningApprovalStatus,
    LearningScope,
    authoritative_outcome,
)


def _learning():
    return build_engineering_learning_service()


def _project(name: str, account: str):
    return build_project_service().create_project(name, owner_account_id=account)


def _candidate(project, account: str = "engineer-a", **overrides):
    payload = {
        "owner_account_id": account,
        "learning_scope": LearningScope.PROJECT,
        "project_id": project.id,
        "agent_id": "ANALYSIS_AGENT",
        "engineering_reason": "Pattern A",
        "applicability": {"pattern": "Pattern A", "task_type": "lateral"},
        "source_element_type": "BEAM",
        "validation_result": "NOT_CHECKED",
        "agent_output": {"summary": "original recommendation"},
    }
    payload.update(overrides)
    return _learning().create_candidate(**payload)


def test_candidate_learning_can_be_created(db_session) -> None:
    project = _project("Learning create", "engineer-a").project
    record = _candidate(project)

    assert record.id is not None
    assert record.approval_status == LearningApprovalStatus.CANDIDATE
    assert record.learning_scope == LearningScope.PROJECT
    assert record.engineering_reason == "Pattern A"


def test_candidate_is_not_returned_as_approved_learning(db_session) -> None:
    project = _project("Learning candidate hidden", "engineer-a").project
    _candidate(project)

    retrieval = _learning().retrieve(project_id=project.id, account_id="engineer-a")

    assert retrieval.records == []
    assert retrieval.overrides_pem is False
    assert "No approved learning records applied" in retrieval.explanation


def test_authorized_reviewer_can_approve_candidate(db_session) -> None:
    project = _project("Learning approve", "engineer-a").project
    record = _candidate(project)
    service = _learning()

    reviewed = service.mark_review(record.id, project_id=project.id, account_id="engineer-a")
    approved = service.approve(reviewed.id, project_id=project.id, account_id="engineer-a")

    assert reviewed.approval_status == LearningApprovalStatus.REVIEW
    assert approved.approval_status == LearningApprovalStatus.APPROVED
    assert approved.reviewed_by == "engineer-a"


def test_approved_learning_can_be_retrieved(db_session) -> None:
    project = _project("Learning retrieve", "engineer-a").project
    record = _candidate(project)
    service = _learning()
    service.approve(record.id, project_id=project.id, account_id="engineer-a")

    retrieval = service.retrieve(
        project_id=project.id,
        account_id="engineer-a",
        agent_id="ANALYSIS_AGENT",
        element_type="BEAM",
        task_type="lateral",
    )

    assert [item.id for item in retrieval.records] == [record.id]
    assert retrieval.authority == "CONTEXT_ONLY"


def test_rejected_learning_is_not_approved_context(db_session) -> None:
    project = _project("Learning reject", "engineer-a").project
    record = _candidate(project, engineering_reason="Do not reuse")
    service = _learning()
    rejected = service.reject(record.id, project_id=project.id, account_id="engineer-a", reason="Not general")

    retrieval = service.retrieve(project_id=project.id, account_id="engineer-a")

    assert rejected.approval_status == LearningApprovalStatus.REJECTED
    assert retrieval.records == []


def test_project_learning_is_isolated_to_its_project(db_session) -> None:
    account = "shared-office"
    project_a = _project("Project A", account).project
    project_b = _project("Project B", account).project
    record = _candidate(project_a, account, engineering_reason="Pattern A")
    service = _learning()
    service.approve(record.id, project_id=project_a.id, account_id=account)

    visible_a = service.list_visible(project_id=project_a.id, account_id=account)
    visible_b = service.list_visible(project_id=project_b.id, account_id=account)
    retrieval_a = service.retrieve(project_id=project_a.id, account_id=account)

    assert record.id in {item.id for item in visible_a}
    assert record.id not in {item.id for item in visible_b}
    assert [item.id for item in retrieval_a.records] == [record.id]


def test_project_learning_cannot_leak_into_another_project(db_session) -> None:
    """Anti-contamination: Project A pattern stays out of Project B until a separate global approval."""
    account = "shared-office"
    project_a = _project("Contamination A", account).project
    project_b = _project("Contamination B", account).project
    pattern = _candidate(project_a, account, engineering_reason="Pattern A", applicability={"pattern": "Pattern A"})
    service = _learning()
    service.approve(pattern.id, project_id=project_a.id, account_id=account)

    leaked = service.retrieve(project_id=project_b.id, account_id=account, agent_id="ANALYSIS_AGENT")
    assert "Pattern A" not in [item.engineering_reason for item in leaked.records]
    assert pattern.id not in {item.id for item in leaked.records}

    global_record = service.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.GLOBAL,
        project_id=project_a.id,
        engineering_reason="Global checklist",
        applicability={"pattern": "Global checklist"},
        agent_id="ANALYSIS_AGENT",
    )
    assert global_record.approval_status == LearningApprovalStatus.CANDIDATE
    still_hidden = service.retrieve(project_id=project_b.id, account_id=account)
    assert global_record.id not in {item.id for item in still_hidden.records}

    service.approve(global_record.id, project_id=project_b.id, account_id=account)
    permitted = service.retrieve(project_id=project_b.id, account_id=account)
    reasons = [item.engineering_reason for item in permitted.records]
    assert "Global checklist" in reasons
    assert "Pattern A" not in reasons


def test_engineer_learning_respects_account_boundaries(db_session) -> None:
    project = _project("Engineer boundary", "engineer-a").project
    service = _learning()
    record = service.create_candidate(
        owner_account_id="engineer-a",
        learning_scope=LearningScope.ENGINEER,
        project_id=project.id,
        engineering_reason="Prefer explicit load paths",
        agent_id="ANALYSIS_AGENT",
    )
    service.approve(record.id, project_id=project.id, account_id="engineer-a")

    owner_view = service.retrieve(project_id=project.id, account_id="engineer-a")
    other_view = service.retrieve(project_id=project.id, account_id="engineer-b")
    other_list = service.list_visible(project_id=project.id, account_id="engineer-b")

    assert record.id in {item.id for item in owner_view.records}
    assert record.id not in {item.id for item in other_view.records}
    assert record.id not in {item.id for item in other_list}
    try:
        service.get(record.id, project_id=project.id, account_id="engineer-b")
    except LearningRecordNotFoundError:
        hidden = True
    else:
        hidden = False
    assert hidden is True


def test_global_learning_requires_explicit_approval(db_session) -> None:
    project = _project("Global gate", "engineer-a").project
    service = _learning()
    record = service.create_candidate(
        owner_account_id="engineer-a",
        learning_scope=LearningScope.GLOBAL,
        project_id=project.id,
        engineering_reason="Check diaphragm continuity before drift review",
        agent_id="ANALYSIS_AGENT",
    )

    before = service.retrieve(project_id=project.id, account_id="engineer-a", learning_scope=LearningScope.GLOBAL)
    assert before.records == []

    approved = service.approve(record.id, project_id=project.id, account_id="engineer-a")
    after = service.retrieve(project_id=project.id, account_id="engineer-a", learning_scope=LearningScope.GLOBAL)

    assert approved.approval_status == LearningApprovalStatus.APPROVED
    assert [item.id for item in after.records] == [record.id]


def test_learning_preserves_provenance_and_unavailable_sources(db_session) -> None:
    project = _project("Provenance", "engineer-a").project
    task_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    service = _learning()
    linked = service.create_candidate(
        owner_account_id="engineer-a",
        learning_scope=LearningScope.PROJECT,
        project_id=project.id,
        agent_id="ANALYSIS_AGENT",
        task_id=task_id,
        source_snapshot_id=snapshot_id,
        source_element_ids=["B1", "B2"],
        source_element_type="BEAM",
        engineering_result_id="result-77",
        validation_result="WARNING",
        engineering_reason="Linked experience",
    )
    missing = service.create_candidate(
        owner_account_id="engineer-a",
        learning_scope=LearningScope.PROJECT,
        project_id=project.id,
        engineering_reason="Unlinked experience",
    )

    linked_view = service.provenance(linked.id, project_id=project.id, account_id="engineer-a")
    missing_view = service.provenance(missing.id, project_id=project.id, account_id="engineer-a")

    assert linked_view["task_id"] == str(task_id)
    assert linked_view["source_snapshot_id"] == str(snapshot_id)
    assert linked_view["source_element_ids"] == ["B1", "B2"]
    assert linked_view["engineering_result_id"] == "result-77"
    assert linked_view["agent_id"] == "ANALYSIS_AGENT"
    assert missing_view["task_id"] == UNAVAILABLE
    assert missing_view["agent_id"] == UNAVAILABLE
    assert missing_view["source_snapshot_id"] == UNAVAILABLE
    assert missing_view["engineering_result_id"] == UNAVAILABLE


def test_retrieval_is_deterministic_and_only_relevant_approved_records(db_session) -> None:
    project = _project("Deterministic retrieval", "engineer-a").project
    service = _learning()
    first = _candidate(project, engineering_reason="First relevant")
    second = _candidate(project, engineering_reason="Second relevant")
    other_agent = _candidate(
        project,
        engineering_reason="Steel only",
        agent_id="STEEL_DESIGN_AGENT",
        source_element_type="COLUMN",
        applicability={"task_type": "steel"},
    )
    candidate = _candidate(project, engineering_reason="Still a candidate")
    service.approve(first.id, project_id=project.id, account_id="engineer-a")
    service.approve(second.id, project_id=project.id, account_id="engineer-a")
    service.approve(other_agent.id, project_id=project.id, account_id="engineer-a")

    first_pass = service.retrieve(
        project_id=project.id,
        account_id="engineer-a",
        agent_id="ANALYSIS_AGENT",
        element_type="BEAM",
        task_type="lateral",
    )
    second_pass = service.retrieve(
        project_id=project.id,
        account_id="engineer-a",
        agent_id="ANALYSIS_AGENT",
        element_type="BEAM",
        task_type="lateral",
    )

    ids = [item.id for item in first_pass.records]
    assert ids == [item.id for item in second_pass.records]
    assert ids == sorted(ids, key=lambda item: (next(r.created_at for r in first_pass.records if r.id == item), str(item)))
    assert ids == [first.id, second.id]
    assert other_agent.id not in ids
    assert candidate.id not in ids
    assert "2 approved learning records" in first_pass.explanation
    assert "not code requirements" in first_pass.explanation


def test_learning_cannot_override_pem_rules_or_unchecked_qa(db_session) -> None:
    pem_wins = authoritative_outcome(
        pem_value="f'c = 30 MPa from PEM",
        learning_suggestion="f'c = 40 MPa",
    )
    rule_wins = authoritative_outcome(
        pem_value="section 300x500",
        rule_value="Use the explicit user section",
        learning_suggestion="section 400x600",
    )
    qa_stays = authoritative_outcome(
        qa_status="NOT_CHECKED",
        learning_suggestion="PASS",
    )

    assert pem_wins == {"value": "f'c = 30 MPa from PEM", "authority": "PEM", "learning_applied": False}
    assert rule_wins["authority"] == "ENGINEERING_RULE"
    assert rule_wins["value"] == "Use the explicit user section"
    assert rule_wins["learning_applied"] is False
    assert qa_stays == {"value": "NOT_CHECKED", "authority": "QA", "learning_applied": False}

    project = _project("Safety gate", "engineer-a").project
    try:
        _learning().create_candidate(
            owner_account_id="engineer-a",
            learning_scope=LearningScope.PROJECT,
            project_id=project.id,
            validation_result="PASS",
            input_context={"qa_status": "NOT_CHECKED"},
            engineering_reason="Pretend the check passed",
        )
    except LearningSafetyError:
        rejected = True
    else:
        rejected = False
    assert rejected is True


def test_human_correction_creates_candidate_not_automatic_approval(db_session) -> None:
    boot = _project("Correction", "engineer-a")
    service = _learning()
    record = service.record_correction(
        project_id=boot.project.id,
        owner_account_id="engineer-a",
        original_output={"recommendation": "ignore the transfer girder"},
        corrected_result={"recommendation": "review the transfer girder before drift conclusions"},
        reason="The girder changes the lateral path",
        agent_id="ANALYSIS_AGENT",
        task_id=uuid.uuid4(),
        source_snapshot_id=boot.snapshot_id,
        source_element_ids=["TG-1"],
        source_element_type="BEAM",
        learning_scope=LearningScope.PROJECT,
    )

    retrieval = service.retrieve(project_id=boot.project.id, account_id="engineer-a")

    assert record.approval_status == LearningApprovalStatus.CANDIDATE
    assert record.learning_scope == LearningScope.PROJECT
    assert record.agent_output["recommendation"] == "ignore the transfer girder"
    assert record.human_correction["corrected_result"]["recommendation"].startswith("review the transfer")
    assert record.engineering_reason == "The girder changes the lateral path"
    assert record.source_element_ids == ["TG-1"]
    assert retrieval.records == []


def test_traceable_correction_is_consumed_by_the_analysis_agent(db_session) -> None:
    boot = _project("Traceable learning", "engineer-a")
    runtime = build_agent_runtime_service()
    service = _learning()
    request = AgentExecutionRequest(
        project_id=boot.project.id,
        agent_type=EngineeringAgentType.ANALYSIS_AGENT,
        user_request="Analyze the lateral system",
        requires_approval=False,
    )

    first = runtime.execute(request, actor_id="engineer-a", account_id="engineer-a")
    assert first.execution_status == AgentExecutionStatus.COMPLETED
    assert first.agent_result is not None
    assert "learning_record_ids" not in first.output

    correction = service.record_correction(
        project_id=boot.project.id,
        owner_account_id="engineer-a",
        original_output=first.output,
        corrected_result={"note": "State that drift results are preliminary until the diaphragm is confirmed"},
        reason="Pattern A: call out diaphragm confirmation before drift conclusions",
        agent_id="ANALYSIS_AGENT",
        task_id=first.id,
        source_snapshot_id=boot.snapshot_id,
        source_element_ids=["DIAPHRAGM-1"],
        source_element_type="DIAPHRAGM",
        engineering_result_id=str(first.traceability_metadata.get("result_trace_id")),
        validation_result=str(first.validation_status.value),
        applicability={"pattern": "Pattern A", "task_type": "lateral"},
    )
    assert correction.approval_status == LearningApprovalStatus.CANDIDATE
    provenance = service.provenance(correction.id, project_id=boot.project.id, account_id="engineer-a")
    assert provenance["task_id"] == str(first.id)
    assert provenance["agent_id"] == "ANALYSIS_AGENT"
    assert provenance["source_snapshot_id"] == str(boot.snapshot_id)
    assert provenance["human_decision"] == "CANDIDATE"

    approved = service.approve(correction.id, project_id=boot.project.id, account_id="engineer-a")
    assert approved.approval_status == LearningApprovalStatus.APPROVED

    second = runtime.execute(request, actor_id="engineer-a", account_id="engineer-a")
    assert second.execution_status == AgentExecutionStatus.COMPLETED
    assert second.output["learning_record_ids"] == [str(approved.id)]
    assert "not code requirements" in second.output["learning_explanation"]
    assert second.output["learning_overrides_pem"] is False
    assert second.output["learning_overrides_rules"] is False
    assert second.output["learning_overrides_qa"] is False
    assert second.output["context_summary"]["learning_record_ids"] == [str(approved.id)]
    assert second.validation_status == first.validation_status
    assert second.output.get("result_validation_status") == first.output.get("result_validation_status")
    uses = service.uses_for_task(project_id=boot.project.id, task_id=second.id)
    assert [item["learning_record_id"] for item in uses] == [str(approved.id)]
    assert str(approved.id) in uses[0]["explanation"]
    assert "not code requirements" in uses[0]["explanation"]
    statements = second.context_snapshot.get("approved_learning", [])
    assert statements[0]["statement"].startswith("Pattern A")
    assert statements[0]["authority"] == "CONTEXT_ONLY"
    why = service.provenance(approved.id, project_id=boot.project.id, account_id="engineer-a")
    assert why["task_id"] == str(first.id)
    assert why["human_decision"] == "APPROVED"
    assert why["source_element_ids"] == ["DIAPHRAGM-1"]


def test_analysis_agent_does_not_receive_another_projects_learning(db_session) -> None:
    account = "engineer-a"
    project_a = _project("Agent A", account)
    project_b = _project("Agent B", account)
    service = _learning()
    pattern = _candidate(
        project_a.project,
        account,
        engineering_reason="Pattern A",
        applicability={"pattern": "Pattern A"},
        source_element_type=None,
        agent_id="ANALYSIS_AGENT",
    )
    service.approve(pattern.id, project_id=project_a.project.id, account_id=account)
    runtime = build_agent_runtime_service()

    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project_b.project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Analyze the lateral system",
            requires_approval=False,
        ),
        actor_id=account,
        account_id=account,
    )

    assert execution.execution_status == AgentExecutionStatus.COMPLETED
    assert "learning_record_ids" not in execution.output
    assert pattern.id not in set(execution.traceability_metadata.get("learning_record_ids", []))


def test_learning_api_approves_and_explains_provenance(api_client: TestClient) -> None:
    email = f"learn-{uuid.uuid4().hex}@example.com"
    registered = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    created = api_client.post("/api/v1/projects", json={"name": "Learning API"}, headers=headers)
    assert created.status_code == 201
    project_id = created.json()["project"]["id"]

    candidate = api_client.post(
        f"/api/v1/projects/{project_id}/learning",
        headers=headers,
        json={
            "learning_scope": "GLOBAL",
            "engineering_reason": "Confirm the lateral system before citing drift.",
            "agent_id": "ANALYSIS_AGENT",
            "approval_status": "APPROVED",
            "validation_result": "NOT_CHECKED",
        },
    )
    assert candidate.status_code == 201
    body = candidate.json()
    assert body["approval_status"] == "CANDIDATE"
    assert body["learning_scope"] == "GLOBAL"
    record_id = body["id"]

    hidden = api_client.get(
        f"/api/v1/projects/{project_id}/learning/retrieval",
        headers=headers,
    )
    assert hidden.status_code == 200
    assert hidden.json()["records"] == []
    assert hidden.json()["overrides_pem"] is False

    approved = api_client.post(
        f"/api/v1/projects/{project_id}/learning/{record_id}/approve",
        headers=headers,
        json={"note": "Reviewed for reuse"},
    )
    assert approved.status_code == 200
    assert approved.json()["approval_status"] == "APPROVED"

    visible = api_client.get(
        f"/api/v1/projects/{project_id}/learning/retrieval?learning_scope=GLOBAL",
        headers=headers,
    )
    assert visible.status_code == 200
    assert visible.json()["records"][0]["id"] == record_id
    assert "not code requirements" in visible.json()["explanation"]

    provenance = api_client.get(
        f"/api/v1/projects/{project_id}/learning/{record_id}/provenance",
        headers=headers,
    )
    assert provenance.status_code == 200
    assert provenance.json()["human_decision"] == "APPROVED"
    assert provenance.json()["task_id"] == "UNAVAILABLE"

    correction = api_client.post(
        f"/api/v1/projects/{project_id}/learning/corrections",
        headers=headers,
        json={
            "original_output": {"note": "agent"},
            "corrected_result": {"note": "engineer"},
            "reason": "Project convention",
            "learning_scope": "PROJECT",
        },
    )
    assert correction.status_code == 201
    assert correction.json()["approval_status"] == "CANDIDATE"
