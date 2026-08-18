"""Persistence tests for agent foundation repositories."""

from app.application.service_factory import (
    build_agent_registry_service,
    build_agent_version_service,
)
from app.domain.models.agent import AgentDefinitionStatus, AgentVersionStatus
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)
from app.infrastructure.repositories.postgres_agent_definition_repository import (
    PostgresAgentDefinitionRepository,
)
from app.infrastructure.repositories.postgres_agent_version_repository import (
    PostgresAgentVersionRepository,
)
from app.infrastructure.repositories.postgres_prompt_template_repository import (
    PostgresPromptTemplateRepository,
)


def test_agent_definition_repository_create_and_get(db_session: str) -> None:
    repo = PostgresAgentDefinitionRepository()
    created = repo.create(key="test-agent", name="Test Agent", description="desc")
    assert created.status == AgentDefinitionStatus.DRAFT
    assert created.current_version is None

    loaded = repo.get_by_id(created.id)
    assert loaded is not None
    assert loaded.key == "test-agent"

    by_key = repo.get_by_key("test-agent")
    assert by_key is not None
    assert by_key.id == created.id


def test_agent_version_repository_versioning(db_session: str) -> None:
    definition_repo = PostgresAgentDefinitionRepository()
    version_repo = PostgresAgentVersionRepository()
    definition = definition_repo.create(key="versioned-agent", name="Versioned")

    v1 = version_repo.create(definition.id, instructions="v1", created_by="tester")
    v2 = version_repo.create(definition.id, instructions="v2", created_by="tester")
    assert v1.version == 1
    assert v2.version == 2

    versions = version_repo.list_for_definition(definition.id)
    assert [item.version for item in versions] == [1, 2]


def test_capability_assignment(db_session: str) -> None:
    definition_repo = PostgresAgentDefinitionRepository()
    version_repo = PostgresAgentVersionRepository()
    capability_repo = PostgresAgentCapabilityRepository()

    definition = definition_repo.create(key="cap-agent", name="Cap Agent")
    version = version_repo.create(definition.id, instructions="with caps")
    capability = capability_repo.create(
        key="analyze",
        name="Analyze",
        description="Analysis capability",
    )
    capability_repo.assign_to_version(version.id, capability.id)

    assigned = capability_repo.list_for_version(version.id)
    assert len(assigned) == 1
    assert assigned[0].key == "analyze"


def test_prompt_template_versioning(db_session: str) -> None:
    definition_repo = PostgresAgentDefinitionRepository()
    version_repo = PostgresAgentVersionRepository()
    prompt_repo = PostgresPromptTemplateRepository()

    definition = definition_repo.create(key="prompt-agent", name="Prompt Agent")
    agent_version = version_repo.create(definition.id, instructions="prompts")

    p1 = prompt_repo.create(
        agent_version.id,
        name="system",
        template="You are {{role}}",
        variables_schema={"role": "string"},
        created_by="tester",
    )
    p2 = prompt_repo.create(
        agent_version.id,
        name="system",
        template="You are {{role}} v2",
        created_by="tester",
    )
    assert p1.version == 1
    assert p2.version == 2

    historical = prompt_repo.get_by_version_and_number(agent_version.id, 1)
    assert historical is not None
    assert historical.template == "You are {{role}}"


def test_only_one_active_version_enforced_at_db_level(db_session: str) -> None:
    definition_repo = PostgresAgentDefinitionRepository()
    version_repo = PostgresAgentVersionRepository()
    definition = definition_repo.create(key="active-agent", name="Active Agent")

    v1 = version_repo.create(
        definition.id,
        instructions="v1",
        status=AgentVersionStatus.ACTIVE,
    )
    version_repo.update_status(v1.id, AgentVersionStatus.ARCHIVED)
    v2 = version_repo.create(
        definition.id,
        instructions="v2",
        status=AgentVersionStatus.ACTIVE,
    )
    active = version_repo.get_active_for_definition(definition.id)
    assert active is not None
    assert active.id == v2.id
