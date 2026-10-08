"""Phase K: project assistants are versioned, approved, and traceable."""

from __future__ import annotations

from uuid import UUID

import pytest
from fastapi.testclient import TestClient

from app.application.drawing.drawing_set_service import SHEET_SPECS
from app.application.exceptions import AgentBuilderValidationFailedError, AgentNotExecutableError
from app.application.service_factory import (
    build_agent_builder_service,
    build_agent_runtime_service,
    build_agent_version_service,
    build_engineering_learning_service,
    build_human_approval_service,
    build_pem_service,
    build_project_service,
)
from app.domain.models.agent import AgentDefinitionStatus, AgentVersionStatus, EngineeringAgentType
from app.domain.models.agent_builder import AgentProductLifecycle, resolve_product_lifecycle
from app.domain.models.agent_runtime import AgentExecutionRequest
from app.domain.models.engineering_learning import LEARNING_AUTHORITY, LearningApprovalStatus, LearningScope
from app.infrastructure.config import get_settings
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)


@pytest.fixture
def capability_repo(db_session: str) -> PostgresAgentCapabilityRepository:
    repo = PostgresAgentCapabilityRepository()
    if repo.get_by_key("routing") is None:
        repo.create(key="routing", name="Routing", description="Route tasks")
    return repo


def _project(name: str, account: str = "phase-k-engineer"):
    return build_project_service().create_project(name, owner_account_id=account)


def _builder():
    return build_agent_builder_service()


def _publish(detail, project_id, actor: str = "phase-k-engineer"):
    builder = _builder()
    publication = builder.request_publish(
        detail.definition.id,
        detail.version.version.version,
        project_id=project_id,
        actor_id=actor,
    )
    assert publication.status == "PENDING_APPROVAL"
    build_human_approval_service().approve_request(
        project_id,
        publication.approval_request_id,
        approver="phase-k-reviewer",
        decision_note="Approved for project use",
    )
    return builder.get_builder_detail(detail.definition.id, detail.version.version.version)


def _create(project, **overrides):
    payload = {
        "key": "phase-k-validation",
        "name": "Project validation assistant",
        "description": "Checks the current project model before design.",
        "agent_type": EngineeringAgentType.VALIDATION_AGENT,
        "project_id": project.id,
        "instructions": "Use the current PEM. Do not invent missing engineering data.",
        "capability_keys": ["routing"],
        "created_by": "phase-k-engineer",
        "purpose": "Review project readiness",
        "engineering_domain": "VALIDATION",
        "task_types": ["project_validation"],
        "element_types": ["PROJECT"],
        "supported_codes": ["ACI318"],
        "input_contract": {"requires": ["pem"]},
        "output_contract": {"returns": ["validation"]},
        "allowed_tools": ["project.validate"],
        "change_summary": "Initial draft",
    }
    payload.update(overrides)
    return _builder().create_agent(**payload)


def test_product_lifecycle_labels_existing_statuses() -> None:
    assert resolve_product_lifecycle("DRAFT") is AgentProductLifecycle.DRAFT
    assert (
        resolve_product_lifecycle("DRAFT", publication_status="PENDING_APPROVAL")
        is AgentProductLifecycle.REVIEW
    )
    assert resolve_product_lifecycle("ACTIVE", approval_status="APPROVED") is AgentProductLifecycle.PUBLISHED
    assert resolve_product_lifecycle("INACTIVE", approval_status="APPROVED") is AgentProductLifecycle.APPROVED
    assert resolve_product_lifecycle("ARCHIVED") is AgentProductLifecycle.ARCHIVED


def test_create_and_edit_draft_agent(db_session: str, capability_repo) -> None:
    project = _project("Phase K create").project
    detail = _create(project)

    assert detail.definition.status == AgentDefinitionStatus.DRAFT
    assert detail.definition.configuration["purpose"] == "Review project readiness"
    assert detail.definition.configuration["engineering_domain"] == "VALIDATION"
    assert detail.version.version.status == AgentVersionStatus.DRAFT
    assert detail.version.version.configuration_metadata["task_types"] == ["project_validation"]
    assert detail.version.version.created_by == "phase-k-engineer"
    assert detail.lifecycle is AgentProductLifecycle.DRAFT

    updated = _builder().update_draft_version(
        detail.definition.id,
        detail.version.version.version,
        instructions="Use only the current PEM snapshot.",
        configuration_metadata={"change_summary": "Clarify PEM authority"},
    )
    assert updated.version.version.instructions == "Use only the current PEM snapshot."
    assert updated.version.version.configuration_metadata["change_summary"] == "Clarify PEM authority"
    assert updated.version.version.configuration_metadata["supported_codes"] == ["ACI318"]
    assert updated.version.version.status == AgentVersionStatus.DRAFT


def test_successor_version_is_a_new_draft(db_session: str, capability_repo) -> None:
    project = _project("Phase K version").project
    published = _publish(_create(project), project.id)
    successor = _builder().create_successor_version(
        published.definition.id,
        published.version.version.version,
        change_summary="Add column checks",
        created_by="phase-k-engineer",
    )

    assert successor.version.version.version == published.version.version.version + 1
    assert successor.version.version.status == AgentVersionStatus.DRAFT
    assert successor.lifecycle is AgentProductLifecycle.DRAFT
    assert "approval" not in successor.version.version.configuration_metadata
    original = build_agent_version_service().get_version(
        published.definition.id,
        published.version.version.version,
    )
    assert original.version.status == AgentVersionStatus.ACTIVE
    assert original.version.instructions == published.version.version.instructions


def test_draft_cannot_execute_and_published_version_is_recorded(db_session: str, capability_repo) -> None:
    project = _project("Phase K execute").project
    detail = _create(project, key="phase-k-execute")
    runtime = build_agent_runtime_service()
    request = AgentExecutionRequest(
        project_id=project.id,
        agent_definition_id=detail.definition.id,
        user_request="Validate the project configuration",
        parameters={"pem_version": 99, "pem_snapshot_id": "not-the-project-pem"},
    )

    with pytest.raises(AgentNotExecutableError):
        runtime.execute(request, actor_id="phase-k-engineer", account_id="phase-k-engineer")

    tested = _builder().test_version(
        detail.definition.id,
        detail.version.version.version,
        project_id=project.id,
        user_request="Validate the project configuration",
        actor_id="phase-k-engineer",
    )
    assert tested.result["execution_status"] == "COMPLETED"
    still_draft = build_agent_version_service().get_version(
        detail.definition.id,
        detail.version.version.version,
    )
    assert still_draft.version.status == AgentVersionStatus.DRAFT

    published = _publish(detail, project.id)
    assert published.lifecycle is AgentProductLifecycle.PUBLISHED
    assert published.version.version.configuration_metadata["approval"]["status"] == "APPROVED"
    assert published.version.version.configuration_metadata["approval"]["approver"] == "phase-k-reviewer"

    snapshot = build_pem_service().get_current_snapshot_meta(project.id)
    assert snapshot is not None
    execution = runtime.execute(request, actor_id="phase-k-engineer", account_id="phase-k-engineer")

    assert execution.agent_definition_id == detail.definition.id
    assert execution.agent_version == published.version.version.version
    assert execution.traceability_metadata["agent_id"] == str(detail.definition.id)
    assert execution.traceability_metadata["agent_version_id"] == str(published.version.version.id)
    assert execution.traceability_metadata["project_id"] == str(project.id)
    assert execution.traceability_metadata["run_id"] == str(execution.id)
    assert execution.traceability_metadata["pem_snapshot_id"] == str(snapshot.id)
    assert execution.traceability_metadata["pem_version"] == snapshot.version
    assert execution.traceability_metadata["pem_version"] != 99
    assert execution.context_snapshot["pem_snapshot_id"] == str(snapshot.id)
    assert execution.validation_status is not None
    assert execution.traceability_metadata["qa_status"] == execution.validation_status.value
    assert build_pem_service().get_current_snapshot_meta(project.id).id == snapshot.id


def test_rollback_selects_previous_approved_version(db_session: str, capability_repo) -> None:
    project = _project("Phase K rollback").project
    first = _publish(_create(project, key="phase-k-rollback"), project.id)
    second = _builder().create_successor_version(
        first.definition.id,
        first.version.version.version,
        change_summary="Second published revision",
        created_by="phase-k-engineer",
        instructions="Second instructions.",
    )
    _publish(second, project.id)

    publication = _builder().request_rollback(
        first.definition.id,
        target_version=first.version.version.version,
        project_id=project.id,
        actor_id="phase-k-engineer",
    )
    build_human_approval_service().approve_request(
        project.id,
        publication.approval_request_id,
        approver="phase-k-reviewer",
    )

    versions = build_agent_version_service()
    restored = versions.get_version(first.definition.id, first.version.version.version)
    retained = versions.get_version(first.definition.id, second.version.version.version)
    definition = _builder().get_builder_detail(first.definition.id, restored.version.version).definition
    assert restored.version.status == AgentVersionStatus.ACTIVE
    assert retained.version.id != restored.version.id
    assert retained.version.status == AgentVersionStatus.ARCHIVED
    assert definition.current_version == first.version.version.version


def test_disabled_agent_cannot_execute_and_archive_keeps_history(db_session: str, capability_repo) -> None:
    project = _project("Phase K disable").project
    published = _publish(_create(project, key="phase-k-disable"), project.id)
    runtime = build_agent_runtime_service()
    execution = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_definition_id=published.definition.id,
            user_request="Validate the project configuration",
        ),
        actor_id="phase-k-engineer",
        account_id="phase-k-engineer",
    )

    disabled = _builder().disable_agent(
        published.definition.id,
        project_id=project.id,
        actor_id="phase-k-engineer",
    )
    assert disabled.status == AgentDefinitionStatus.DISABLED
    with pytest.raises(AgentNotExecutableError):
        runtime.execute(
            AgentExecutionRequest(
                project_id=project.id,
                agent_definition_id=published.definition.id,
                user_request="Validate the project configuration",
            ),
            actor_id="phase-k-engineer",
            account_id="phase-k-engineer",
        )

    archived = _builder().archive_agent(published.definition.id)
    assert archived.status == AgentDefinitionStatus.ARCHIVED
    history = runtime.list_executions(project.id)
    assert any(item.id == execution.id for item in history)
    retained = next(item for item in history if item.id == execution.id)
    assert retained.agent_version == published.version.version.version
    assert retained.agent_definition_id == published.definition.id


def test_duplicate_does_not_share_mutable_configuration(db_session: str, capability_repo) -> None:
    project = _project("Phase K duplicate").project
    original = _create(project, key="phase-k-original")
    duplicate = _builder().duplicate_agent(
        original.definition.id,
        project_id=project.id,
        actor_id="phase-k-engineer",
        name="Copied assistant",
    )

    assert duplicate.definition.id != original.definition.id
    assert duplicate.version.version.status == AgentVersionStatus.DRAFT
    assert duplicate.definition.current_version is None
    _builder().update_draft_version(
        duplicate.definition.id,
        duplicate.version.version.version,
        configuration_metadata={"task_types": ["steel_member"]},
    )
    reloaded = build_agent_version_service().get_version(
        original.definition.id,
        original.version.version.version,
    )
    assert reloaded.version.configuration_metadata["task_types"] == ["project_validation"]


def test_configuration_cannot_bypass_pem_or_learning_authority(db_session: str, capability_repo) -> None:
    project = _project("Phase K authority").project
    detail = _create(project, key="phase-k-authority")
    _builder().update_draft_version(
        detail.definition.id,
        detail.version.version.version,
        configuration_metadata={"overrides_pem": True, "learning_authority": "DEFINITIVE"},
    )

    with pytest.raises(AgentBuilderValidationFailedError) as caught:
        _builder().request_publish(
            detail.definition.id,
            detail.version.version.version,
            project_id=project.id,
            actor_id="phase-k-engineer",
        )
    codes = {issue["code"] for issue in caught.value.details["issues"]}
    assert "UNSAFE_CONFIGURATION" in codes


def test_published_run_keeps_phase_i_learning_as_context(db_session: str, capability_repo) -> None:
    account = "phase-k-engineer"
    project = _project("Phase K learning", account).project
    learning = build_engineering_learning_service()
    candidate = learning.create_candidate(
        owner_account_id=account,
        learning_scope=LearningScope.PROJECT,
        project_id=project.id,
        agent_id="VALIDATION_AGENT",
        engineering_reason="Check the current model before recommending a change.",
        applicability={"pattern": "readiness"},
        validation_result="NOT_CHECKED",
        agent_output={"summary": "context only"},
    )
    learning.mark_review(candidate.id, project_id=project.id, account_id=account)
    approved = learning.approve(candidate.id, project_id=project.id, account_id=account)
    assert approved.approval_status == LearningApprovalStatus.APPROVED

    published = _publish(_create(project, key="phase-k-learning"), project.id)
    execution = build_agent_runtime_service().execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_definition_id=published.definition.id,
            user_request="Validate the project configuration",
        ),
        actor_id=account,
        account_id=account,
    )

    assert str(approved.id) in execution.traceability_metadata["learning_record_ids"]
    assert execution.traceability_metadata["learning_authority"] == LEARNING_AUTHORITY
    output = execution.output or {}
    assert output.get("learning_overrides_pem") is False


def test_phase_g_drawing_sheet_contract_remains() -> None:
    numbers = {spec.number for spec in SHEET_SPECS}
    assert {"S-001", "S-101", "S-102", "S-103", "S-104"}.issubset(numbers)
    assert not numbers & {"S-201", "S-202", "S-203"}


def test_other_account_cannot_read_project_agent(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    get_settings.cache_clear()

    def register(email: str) -> str:
        response = api_client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": "secure-password"},
        )
        assert response.status_code == 201
        return response.json()["access_token"]

    owner = register("phase-k-owner@example.com")
    other = register("phase-k-other@example.com")
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Owner project"},
        headers={"Authorization": f"Bearer {owner}"},
    ).json()["project"]["id"]
    created = api_client.post(
        "/api/v1/agents/builder",
        json={
            "key": "owner-only-agent",
            "name": "Owner assistant",
            "agent_type": "VALIDATION_AGENT",
            "project_id": project_id,
            "instructions": "Owner instructions",
            "purpose": "Owner purpose",
        },
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert created.status_code == 201
    agent_id = created.json()["agent"]["id"]

    denied = api_client.get(
        f"/api/v1/agents/{agent_id}",
        headers={"Authorization": f"Bearer {other}"},
    )
    assert denied.status_code == 403
    activate = api_client.post(
        f"/api/v1/agents/{agent_id}/versions/1/activate",
        headers={"Authorization": f"Bearer {owner}"},
    )
    assert activate.status_code == 400
    assert activate.json()["error"]["code"] == "AGENT_BUILDER_INVALID_STATE"
    get_settings.cache_clear()
    UUID(agent_id)
