"""Meta-Agent foundation tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.application.exceptions import MetaAgentApprovalRequiredError
from app.application.service_factory import (
    build_agent_runtime_service,
    build_conversation_service,
    build_human_approval_service,
    build_meta_agent_service,
    build_project_service,
)
from app.domain.models.agent import AgentDefinitionStatus, AgentVersionStatus, EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest
from app.domain.models.meta_agent import AgentBuildStatus, AgentProposalStatus, MetaAgentDecisionKind
from app.domain.models.user import AuthenticatedAccount, AuthMethod
from app.infrastructure.repositories.postgres_conversation_repository import (
    PostgresConversationRepository,
)


def _project(db_session, file_storage_root, name: str = "Meta Agent Project", owner: str = "legacy"):
    del db_session, file_storage_root
    return build_project_service().create_project(name, owner_account_id=owner).project


def _account(account_id: str = "meta-account") -> AuthenticatedAccount:
    return AuthenticatedAccount(
        account_id=account_id,
        auth_method=AuthMethod.LEGACY_ACTOR,
        email=f"{account_id}@example.com",
    )


def test_existing_agent_is_discovered_for_analysis_request(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    service = build_meta_agent_service()
    decision = service.decide(
        "Analyze modal drift for this tower",
        _account(),
        project_id=project.id,
    )

    assert decision.kind == MetaAgentDecisionKind.ROUTE_TO_EXISTING_AGENT
    assert decision.selected_agent_type == EngineeringAgentType.ANALYSIS_AGENT
    assert decision.matches
    assert decision.matches[0].confidence >= 0.45


def test_existing_agent_routes_through_runtime_orchestration(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Analyze drift for the lateral system",
            requires_approval=False,
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    assert record.execution_status.value in {"COMPLETED", "BLOCKED", "FAILED", "IN_PROGRESS", "QUEUED"}


def test_unknown_capability_produces_agent_specification(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    decision = build_meta_agent_service().decide(
        "Build a custom structural agent to monitor bridge corrosion sensors",
        _account(),
        project_id=project.id,
    )

    assert decision.kind == MetaAgentDecisionKind.CREATE_NEW_AGENT
    assert decision.proposal is not None
    assert decision.specification is not None
    assert decision.proposal.approval_required is True
    assert decision.proposal.status == AgentProposalStatus.DRAFT
    assert decision.proposal.domain == "structural_engineering"


def test_agent_specification_contains_originating_user_request(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    request = "Create an agent that monitors bridge corrosion sensors"
    decision = build_meta_agent_service().decide(
        request,
        _account(),
        project_id=project.id,
    )

    assert decision.specification is not None
    assert decision.specification.originating_user_request == request


def test_new_agent_creation_requires_human_approval(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    service = build_meta_agent_service()
    decision = service.decide(
        "Create an agent for corrosion monitoring",
        _account("creator-1"),
        project_id=project.id,
    )
    assert decision.specification is not None

    submission = service.submit_specification_for_approval(
        decision.specification,
        project_id=project.id,
        account=_account("creator-1"),
        actor_id="creator-1",
    )

    assert submission.approval_request_id
    assert submission.build_result is not None
    assert submission.build_result.status == AgentBuildStatus.PENDING_APPROVAL


def test_client_cannot_bypass_approval_for_build(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    service = build_meta_agent_service()
    decision = service.decide(
        "Create an agent for bridge corrosion monitoring",
        _account("creator-2"),
        project_id=project.id,
    )
    assert decision.specification is not None
    submission = service.submit_specification_for_approval(
        decision.specification,
        project_id=project.id,
        account=_account("creator-2"),
        actor_id="creator-2",
    )

    with pytest.raises(MetaAgentApprovalRequiredError):
        service.request_build_after_approval(
            project_id=project.id,
            approval_request_id=submission.approval_request_id,
            account=_account("creator-2"),
            actor_id="creator-2",
        )


def test_meta_agent_cannot_access_other_account_project(
    db_session,
    file_storage_root,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    project = _project(db_session, file_storage_root, "Private Project", owner="owner-1")
    service = build_meta_agent_service()

    from app.application.exceptions import ProjectAuthorizationError

    with pytest.raises(ProjectAuthorizationError):
        service.decide(
            "Analyze drift",
            _account("other-account"),
            project_id=project.id,
        )


def test_stub_builder_does_not_fake_successful_cursor_build() -> None:
    from app.domain.models.meta_agent import AgentSpecification
    from app.infrastructure.agent_builder.stub_agent_builder_port import StubAgentBuilderPort

    port = StubAgentBuilderPort()
    specification = AgentSpecification(
        name="Test Agent",
        purpose="Test",
        user_description="Test",
        originating_user_request="Create test agent",
    )
    result = port.submit_build(
        specification,
        approval_request_id=uuid.uuid4(),
        project_id=uuid.uuid4(),
        requested_by="tester",
    )

    assert result.status == AgentBuildStatus.UNAVAILABLE
    assert "not configured" in result.message.lower()
    assert result.metadata.get("build_completed") is False


def test_unsupported_empty_request_returns_typed_result(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    decision = build_meta_agent_service().decide("   ", _account(), project_id=project.id)

    assert decision.kind == MetaAgentDecisionKind.UNSUPPORTED
    assert decision.unsupported_reason


def test_structural_chat_api_remains_backward_compatible(api_client: TestClient) -> None:
    email = f"meta-chat-{uuid.uuid4().hex}@example.com"
    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Structural Chat"},
        headers=headers,
    ).json()["project"]["id"]

    response = api_client.post(
        "/api/v1/chat",
        json={
            "message": "Analyze this model for drift issues.",
            "project_id": project_id,
        },
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["assistant_message"]["content"]


def test_meta_agent_decide_api_returns_existing_agent_route(api_client: TestClient) -> None:
    email = f"meta-api-{uuid.uuid4().hex}@example.com"
    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Meta API Project"},
        headers=headers,
    ).json()["project"]["id"]

    response = api_client.post(
        "/api/v1/meta-agent/decide",
        json={
            "user_request": "Run seismic analysis for this structure",
            "project_id": project_id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == MetaAgentDecisionKind.ROUTE_TO_EXISTING_AGENT.value
    assert body["selected_agent_type"] == EngineeringAgentType.SEISMIC_AGENT.value


def test_meta_agent_decide_api_for_new_agent_includes_specification(api_client: TestClient) -> None:
    email = f"meta-new-{uuid.uuid4().hex}@example.com"
    register = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    )
    token = register.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Meta New Agent Project"},
        headers=headers,
    ).json()["project"]["id"]

    response = api_client.post(
        "/api/v1/meta-agent/decide",
        json={
            "user_request": "Create an agent that monitors bridge corrosion sensors",
            "project_id": project_id,
        },
        headers=headers,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == MetaAgentDecisionKind.CREATE_NEW_AGENT.value
    assert body["proposal"]["domain"] == "structural_engineering"
    assert body["proposal"]["originating_user_request"].startswith("Create an agent")
    assert body["specification"]["originating_user_request"].startswith("Create an agent")


def test_approved_proposal_registers_draft_agent(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    service = build_meta_agent_service()
    approvals = build_human_approval_service()
    decision = service.decide(
        "Create an agent for bridge structural corrosion monitoring",
        _account("register-user"),
        project_id=project.id,
    )
    assert decision.proposal is not None

    submission = service.submit_specification_for_approval(
        decision.specification,
        project_id=project.id,
        account=_account("register-user"),
        actor_id="register-user",
    )
    approvals.approve_request(
        project.id,
        submission.approval_request_id,
        approver="reviewer-1",
        decision_note="Approved for registration",
    )

    registration = service.register_approved_proposal(
        project_id=project.id,
        approval_request_id=submission.approval_request_id,
        account=_account("register-user"),
        actor_id="register-user",
    )

    assert registration.proposal_status == AgentProposalStatus.APPROVED
    assert registration.agent_definition_status == AgentDefinitionStatus.DRAFT
    assert registration.agent_version_status == AgentVersionStatus.DRAFT


def test_unapproved_proposal_cannot_register(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    service = build_meta_agent_service()
    decision = service.decide(
        "Create an agent for corrosion monitoring",
        _account("pending-user"),
        project_id=project.id,
    )
    assert decision.specification is not None
    submission = service.submit_specification_for_approval(
        decision.specification,
        project_id=project.id,
        account=_account("pending-user"),
        actor_id="pending-user",
    )

    with pytest.raises(MetaAgentApprovalRequiredError):
        service.register_approved_proposal(
            project_id=project.id,
            approval_request_id=submission.approval_request_id,
            account=_account("pending-user"),
            actor_id="pending-user",
        )


def test_conversation_records_meta_agent_proposal_provenance(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    account = _account("conv-user")
    conversations = build_conversation_service()
    conversation = conversations.create_conversation(
        account,
        title="Meta Agent Conversation",
        project_id=project.id,
    )
    service = build_meta_agent_service()
    decision = service.decide(
        "Create an agent for bridge corrosion monitoring",
        account,
        project_id=project.id,
    )
    assert decision.specification is not None

    submission = service.submit_specification_for_approval(
        decision.specification,
        project_id=project.id,
        account=account,
        actor_id="conv-user",
        conversation_id=conversation.id,
    )

    assert submission.conversation_message_id is not None
    messages = PostgresConversationRepository().list_messages(conversation.id)
    provenance_messages = [
        message
        for message in messages
        if message.metadata.get("meta_agent_proposal", {}).get("approval_request_id")
        == str(submission.approval_request_id)
    ]
    assert len(provenance_messages) == 1
    assert provenance_messages[0].metadata["meta_agent_proposal"]["proposal_name"] == decision.proposal.name


def test_registered_draft_agent_is_not_selected_for_existing_routing(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    service = build_meta_agent_service()
    approvals = build_human_approval_service()
    decision = service.decide(
        "Create an agent for bridge structural corrosion monitoring",
        _account("route-user"),
        project_id=project.id,
    )
    assert decision.specification is not None
    submission = service.submit_specification_for_approval(
        decision.specification,
        project_id=project.id,
        account=_account("route-user"),
        actor_id="route-user",
    )
    approvals.approve_request(
        project.id,
        submission.approval_request_id,
        approver="reviewer-1",
    )
    registration = service.register_approved_proposal(
        project_id=project.id,
        approval_request_id=submission.approval_request_id,
        account=_account("route-user"),
        actor_id="route-user",
    )
    assert registration.agent_version_status == AgentVersionStatus.DRAFT

    existing_route = service.decide(
        "Analyze modal drift for this tower",
        _account("route-user"),
        project_id=project.id,
    )
    assert existing_route.kind == MetaAgentDecisionKind.ROUTE_TO_EXISTING_AGENT
    assert existing_route.selected_agent_type == EngineeringAgentType.ANALYSIS_AGENT


def test_non_engineering_agent_request_is_unsupported(db_session, file_storage_root) -> None:
    project = _project(db_session, file_storage_root)
    decision = build_meta_agent_service().decide(
        "Create an agent that tracks inventory across warehouses",
        _account(),
        project_id=project.id,
    )

    assert decision.kind == MetaAgentDecisionKind.UNSUPPORTED
    assert decision.unsupported_reason
    assert "structural-engineering" in decision.unsupported_reason.lower()


def test_conversation_service_does_not_invoke_meta_agent() -> None:
    import inspect

    from app.application import conversation_service

    source = inspect.getsource(conversation_service)
    assert "MetaAgent" not in source
    assert "meta_agent" not in source


def test_chat_route_does_not_invoke_meta_agent() -> None:
    import inspect

    from app.api.routes import chat

    source = inspect.getsource(chat)
    assert "MetaAgent" not in source
    assert "meta_agent" not in source
