"""Service tests for Agent Builder lifecycle."""

import pytest

from app.application.exceptions import AgentBuilderValidationFailedError
from app.application.service_factory import (
    build_agent_builder_service,
    build_agent_version_service,
    build_human_approval_service,
    build_project_service,
)
from app.domain.models.agent import AgentVersionStatus, EngineeringAgentType
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)


@pytest.fixture
def capability_repo(db_session: str) -> PostgresAgentCapabilityRepository:
    repo = PostgresAgentCapabilityRepository()
    if repo.get_by_key("routing") is None:
        repo.create(key="routing", name="Routing", description="Route tasks")
    return repo


def _create_project(db_session: str):
    return build_project_service().create_project(name="Builder Service Project")


def test_create_builder_agent_starts_in_draft(db_session: str, capability_repo) -> None:
    project = _create_project(db_session)
    builder = build_agent_builder_service()

    detail = builder.create_agent(
        key="builder-test-agent",
        name="Custom Validation Assistant",
        agent_type=EngineeringAgentType.VALIDATION_AGENT,
        project_id=project.project.id,
        instructions="Validate project readiness.",
        capability_keys=["routing"],
        created_by="engineer-1",
    )

    assert detail.definition.name == "Custom Validation Assistant"
    assert detail.version.version.status == AgentVersionStatus.DRAFT
    assert detail.validation is not None


def test_validate_version_reports_missing_fields(db_session: str) -> None:
    project = _create_project(db_session)
    builder = build_agent_builder_service()
    detail = builder.create_agent(
        key="invalid-builder-agent",
        name="Incomplete Assistant",
        project_id=project.project.id,
        created_by="engineer-1",
    )

    validation = builder.validate_version(detail.definition.id, detail.version.version.version)
    assert validation.valid is False
    assert any(issue.code == "MISSING_AGENT_TYPE" for issue in validation.issues)


def test_test_version_does_not_activate_draft(db_session: str, capability_repo) -> None:
    project = _create_project(db_session)
    builder = build_agent_builder_service()
    detail = builder.create_agent(
        key="testable-agent",
        name="Testable Assistant",
        agent_type=EngineeringAgentType.VALIDATION_AGENT,
        project_id=project.project.id,
        instructions="Run validation checks for the project.",
        capability_keys=["routing"],
        created_by="engineer-1",
    )

    test_record = builder.test_version(
        detail.definition.id,
        detail.version.version.version,
        project_id=project.project.id,
        user_request="Validate the project configuration",
        actor_id="engineer-1",
    )

    assert test_record.result["execution_status"] == "COMPLETED"
    reloaded = build_agent_version_service().get_version(
        detail.definition.id,
        detail.version.version.version,
    )
    assert reloaded.version.status == AgentVersionStatus.DRAFT


def test_publish_requires_validation(db_session: str) -> None:
    project = _create_project(db_session)
    builder = build_agent_builder_service()
    detail = builder.create_agent(
        key="publish-invalid",
        name="Incomplete Publish Assistant",
        project_id=project.project.id,
        created_by="engineer-1",
    )

    with pytest.raises(AgentBuilderValidationFailedError):
        builder.request_publish(
            detail.definition.id,
            detail.version.version.version,
            project_id=project.project.id,
            actor_id="engineer-1",
        )


def test_publish_and_approve_activates_version(db_session: str, capability_repo) -> None:
    project = _create_project(db_session)
    builder = build_agent_builder_service()
    approvals = build_human_approval_service()
    detail = builder.create_agent(
        key="publishable-agent",
        name="Publishable Assistant",
        agent_type=EngineeringAgentType.VALIDATION_AGENT,
        project_id=project.project.id,
        instructions="Validate project readiness before design work proceeds.",
        capability_keys=["routing"],
        created_by="engineer-1",
    )

    publication = builder.request_publish(
        detail.definition.id,
        detail.version.version.version,
        project_id=project.project.id,
        actor_id="engineer-1",
    )
    assert publication.approval_request_id is not None
    assert publication.status == "PENDING_APPROVAL"

    approvals.approve_request(
        project.project.id,
        publication.approval_request_id,
        approver="lead-engineer",
        decision_note="Approved for production use",
    )

    active = build_agent_version_service().get_active_version(detail.definition.id)
    assert active is not None
    assert active.version.version == detail.version.version.version
    assert active.version.status == AgentVersionStatus.ACTIVE
