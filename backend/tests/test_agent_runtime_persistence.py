"""Persistence tests for agent execution repository."""

from uuid import uuid4

from app.application.service_factory import build_project_service
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionStatus, AgentResult, AgentValidationStatus
from app.infrastructure.repositories.postgres_agent_definition_repository import (
    PostgresAgentDefinitionRepository,
)
from app.infrastructure.repositories.postgres_agent_execution_repository import (
    PostgresAgentExecutionRepository,
)


def _create_project(db_session: str):
    return build_project_service().create_project(name="Agent Runtime Project")


def test_agent_execution_repository_create_update_and_list(db_session: str) -> None:
    project = _create_project(db_session)
    definition_repo = PostgresAgentDefinitionRepository()
    execution_repo = PostgresAgentExecutionRepository()

    definition = definition_repo.create(
        key="analysis-agent",
        name="Analysis Agent",
        agent_type=EngineeringAgentType.ANALYSIS_AGENT,
    )

    created = execution_repo.create(
        project_id=project.project.id,
        agent_definition_id=definition.id,
        agent_version=1,
        input_request={"user_request": "Run analysis"},
        context_snapshot={"project_name": project.project.name},
        created_by="tester",
    )
    assert created.execution_status == AgentExecutionStatus.CREATED

    created.execution_status = AgentExecutionStatus.COMPLETED
    created.output = {"status": "stub_completed"}
    created.agent_result = AgentResult(structured_output={"status": "stub_completed"})
    created.validation_status = AgentValidationStatus.REQUIRES_ENGINEER_REVIEW
    updated = execution_repo.update(created)
    assert updated.execution_status == AgentExecutionStatus.COMPLETED
    assert updated.agent_result is not None

    loaded = execution_repo.get_by_id(updated.id)
    assert loaded is not None
    assert loaded.output == {"status": "stub_completed"}

    history = execution_repo.list_for_project(project.project.id)
    assert len(history) == 1
    assert history[0].id == updated.id


def test_agent_definition_repository_agent_type_fields(db_session: str) -> None:
    repo = PostgresAgentDefinitionRepository()
    created = repo.create(
        key="steel-design",
        name="Steel Design Agent",
        agent_type=EngineeringAgentType.STEEL_DESIGN_AGENT,
        configuration={"discipline": "steel"},
    )
    loaded = repo.get_by_id(created.id)
    assert loaded is not None
    assert loaded.agent_type == EngineeringAgentType.STEEL_DESIGN_AGENT
    assert loaded.configuration["discipline"] == "steel"

    by_type = repo.get_by_agent_type(EngineeringAgentType.STEEL_DESIGN_AGENT)
    assert by_type is not None
    assert by_type.id == created.id


def test_agent_execution_get_missing_returns_none(db_session: str) -> None:
    repo = PostgresAgentExecutionRepository()
    assert repo.get_by_id(uuid4()) is None
