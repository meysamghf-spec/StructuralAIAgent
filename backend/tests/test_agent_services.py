"""Application service tests for agent foundation lifecycle."""

import pytest

from app.application.exceptions import (
    AgentKeyConflictError,
    AgentVersionImmutableError,
    CapabilityNotFoundError,
    InvalidLifecycleTransitionError,
)
from app.application.service_factory import (
    build_agent_registry_service,
    build_agent_version_service,
    build_prompt_template_service,
)
from app.domain.models.agent import AgentDefinitionStatus, AgentVersionStatus
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)


@pytest.fixture
def capability_repo(db_session: str) -> PostgresAgentCapabilityRepository:
    repo = PostgresAgentCapabilityRepository()
    repo.create(key="routing", name="Routing", description="Route tasks")
    repo.create(key="planning", name="Planning", description="Plan workflows")
    return repo


def test_create_and_list_agents(db_session: str) -> None:
    registry = build_agent_registry_service()
    created = registry.create_agent(key="registry-agent", name="Registry Agent")
    assert created.status == AgentDefinitionStatus.DRAFT

    agents = registry.list_agents()
    assert any(agent.id == created.id for agent in agents)


def test_agent_key_conflict(db_session: str) -> None:
    registry = build_agent_registry_service()
    registry.create_agent(key="duplicate", name="One")
    with pytest.raises(AgentKeyConflictError):
        registry.create_agent(key="duplicate", name="Two")


def test_create_version_and_activate(db_session: str, capability_repo: PostgresAgentCapabilityRepository) -> None:
    registry = build_agent_registry_service()
    versions = build_agent_version_service()

    definition = registry.create_agent(key="lifecycle-agent", name="Lifecycle")
    v1 = versions.create_version(
        definition.id,
        instructions="v1 instructions",
        capability_keys=["routing"],
        created_by="engineer-1",
    )
    assert v1.version.status == AgentVersionStatus.DRAFT
    assert len(v1.capabilities) == 1

    activated = versions.activate_version(definition.id, v1.version.version)
    assert activated.version.status == AgentVersionStatus.ACTIVE

    updated_definition = registry.get_agent(definition.id)
    assert updated_definition.status == AgentDefinitionStatus.ACTIVE
    assert updated_definition.current_version == 1


def test_only_one_active_version(db_session: str, capability_repo: PostgresAgentCapabilityRepository) -> None:
    registry = build_agent_registry_service()
    versions = build_agent_version_service()

    definition = registry.create_agent(key="single-active", name="Single Active")
    v1 = versions.create_version(definition.id, instructions="v1")
    v2 = versions.create_version(definition.id, instructions="v2")

    versions.activate_version(definition.id, v1.version.version)
    versions.activate_version(definition.id, v2.version.version)

    active = versions.get_active_version(definition.id)
    assert active is not None
    assert active.version.version == 2

    reloaded_v1 = versions.get_version(definition.id, 1)
    assert reloaded_v1.version.status == AgentVersionStatus.ARCHIVED


def test_active_version_is_immutable(db_session: str) -> None:
    registry = build_agent_registry_service()
    versions = build_agent_version_service()
    prompts = build_prompt_template_service()

    definition = registry.create_agent(key="immutable-agent", name="Immutable")
    v1 = versions.create_version(definition.id, instructions="v1")
    versions.activate_version(definition.id, v1.version.version)

    with pytest.raises(AgentVersionImmutableError):
        prompts.create_prompt(
            definition.id,
            v1.version.version,
            name="system",
            template="Cannot add to active",
        )


def test_new_version_for_changes(db_session: str) -> None:
    registry = build_agent_registry_service()
    versions = build_agent_version_service()
    prompts = build_prompt_template_service()

    definition = registry.create_agent(key="change-agent", name="Change")
    v1 = versions.create_version(definition.id, instructions="v1")
    prompts.create_prompt(definition.id, v1.version.version, name="p", template="t1")
    versions.activate_version(definition.id, v1.version.version)

    v2 = versions.create_version(definition.id, instructions="v2")
    prompt_v2 = prompts.create_prompt(
        definition.id, v2.version.version, name="p", template="t2"
    )
    assert prompt_v2.version == 1

    historical = prompts.list_prompts(definition.id, v1.version.version)
    assert len(historical) == 1
    assert historical[0].template == "t1"


def test_unknown_capability_raises(db_session: str) -> None:
    registry = build_agent_registry_service()
    versions = build_agent_version_service()
    definition = registry.create_agent(key="bad-cap", name="Bad Cap")
    with pytest.raises(CapabilityNotFoundError):
        versions.create_version(definition.id, capability_keys=["missing"])


def test_archive_definition(db_session: str) -> None:
    registry = build_agent_registry_service()
    definition = registry.create_agent(key="archive-me", name="Archive")
    archived = registry.archive_agent(definition.id)
    assert archived.status == AgentDefinitionStatus.ARCHIVED

    versions = build_agent_version_service()
    with pytest.raises(InvalidLifecycleTransitionError):
        versions.create_version(definition.id, instructions="blocked")


def test_reactivate_archived_version_blocked(db_session: str) -> None:
    registry = build_agent_registry_service()
    versions = build_agent_version_service()
    definition = registry.create_agent(key="archived-version", name="Archived Version")
    v1 = versions.create_version(definition.id, instructions="v1")
    versions.activate_version(definition.id, v1.version.version)
    versions.archive_version(definition.id, v1.version.version)

    with pytest.raises(InvalidLifecycleTransitionError):
        versions.activate_version(definition.id, v1.version.version)
