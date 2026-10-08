"""Phase L: a project run keeps PEM authority, file scope, and agent lifecycle."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.application.drawing.drawing_set_service import SHEET_SPECS
from app.application.drawing.schedule_sheets import build_schedule_sheets
from app.application.exceptions import AgentNotExecutableError
from app.application.execution_attachment_binding import bind_execution_attachments
from app.application.service_factory import (
    build_agent_builder_service,
    build_agent_runtime_service,
    build_chat_attachment_context_service,
    build_file_ingestion_service,
    build_human_approval_service,
    build_project_service,
)
from app.domain.models.agent import AgentDefinitionStatus, EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest
from app.domain.models.engineering_learning import LEARNING_AUTHORITY
from app.infrastructure.repositories.postgres_agent_capability_repository import (
    PostgresAgentCapabilityRepository,
)


@pytest.fixture
def capability_repo(db_session: str) -> PostgresAgentCapabilityRepository:
    repo = PostgresAgentCapabilityRepository()
    if repo.get_by_key("routing") is None:
        repo.create(key="routing", name="Routing", description="Route tasks")
    return repo


def test_direct_execution_rejects_another_projects_file(api_client: TestClient) -> None:
    project_a = api_client.post("/api/v1/projects", json={"name": "Owner"}).json()["project"]["id"]
    project_b = api_client.post("/api/v1/projects", json={"name": "Other"}).json()["project"]["id"]
    uploaded = build_file_ingestion_service().ingest_upload(
        UUID(project_a),
        filename="private.txt",
        content=b"private specification",
        content_type="text/plain",
        created_by="engineer",
    )

    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_b,
            "agent_type": EngineeringAgentType.VALIDATION_AGENT.value,
            "user_request": "Review the attached specification",
            "requires_approval": False,
            "parameters": {"attachment_file_ids": [str(uploaded.id)]},
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "PROJECT_FILE_NOT_FOUND"


def test_direct_execution_records_only_server_bound_attachments(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Attached"}).json()["project"]["id"]
    uploaded = build_file_ingestion_service().ingest_upload(
        UUID(project_id),
        filename="loads.txt",
        content=b"Dead load is recorded in the PEM.",
        content_type="text/plain",
        created_by="engineer",
    )
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.VALIDATION_AGENT.value,
            "user_request": "Check the current model",
            "requires_approval": False,
            "parameters": {
                "attachment_file_ids": [str(uploaded.id)],
                "attachment_context": {
                    "attachments": [
                        {
                            "file_id": "forged",
                            "filename": "other-project.txt",
                            "file_type": "TEXT",
                        }
                    ]
                },
                "pem_version": 99,
            },
        },
    )
    assert response.status_code == 201
    body = response.json()
    stored = body["input_request"]["parameters"]["attachment_context"]["attachments"]
    assert [item["file_id"] for item in stored] == [str(uploaded.id)]
    assert "other-project.txt" not in str(body["input_request"])
    assert body["traceability_metadata"]["attachment_file_ids"] == [str(uploaded.id)]
    assert body["traceability_metadata"]["pem_version"] != 99
    assert body["traceability_metadata"]["pem_snapshot_id"]
    assert body["traceability_metadata"]["agent_version"]
    assert "agent_version_id" in body["traceability_metadata"]
    assert body["traceability_metadata"]["run_id"] == body["id"]
    assert body["output"].get("learning_overrides_pem") is not True


def test_forged_attachment_context_without_file_ids_is_dropped() -> None:
    cleaned = bind_execution_attachments(
        project_id=uuid4(),
        parameters={
            "attachment_context": {"attachments": [{"filename": "secret.txt", "file_id": "x"}]},
        },
        context_service=build_chat_attachment_context_service(),
    )
    assert "attachment_context" not in cleaned


def test_phase_h_schedules_remain_outside_the_fixed_sheet_catalog() -> None:
    numbers = {spec.number for spec in SHEET_SPECS}
    assert {"S-001", "S-101", "S-102", "S-103", "S-104"}.issubset(numbers)
    assert not numbers & {"S-201", "S-202", "S-203"}
    assert callable(build_schedule_sheets)


def test_draft_project_agent_cannot_run_and_published_agent_can(
    db_session: str,
    capability_repo,
) -> None:
    project = build_project_service().create_project(
        "Phase L lifecycle",
        owner_account_id="phase-l-engineer",
    ).project
    builder = build_agent_builder_service()
    detail = builder.create_agent(
        key="phase-l-validation",
        name="Phase L validation",
        description="Project assistant",
        agent_type=EngineeringAgentType.VALIDATION_AGENT,
        project_id=project.id,
        instructions="Use the current PEM.",
        capability_keys=["routing"],
        created_by="phase-l-engineer",
        purpose="Review readiness",
        engineering_domain="VALIDATION",
        task_types=["project_validation"],
        change_summary="Initial draft",
    )
    runtime = build_agent_runtime_service()
    request = AgentExecutionRequest(
        project_id=project.id,
        agent_definition_id=detail.definition.id,
        user_request="Validate the project configuration",
    )
    with pytest.raises(AgentNotExecutableError):
        runtime.execute(request, actor_id="phase-l-engineer", account_id="phase-l-engineer")

    publication = builder.request_publish(
        detail.definition.id,
        detail.version.version.version,
        project_id=project.id,
        actor_id="phase-l-engineer",
    )
    build_human_approval_service().approve_request(
        project.id,
        publication.approval_request_id,
        approver="phase-l-reviewer",
    )
    published = runtime.execute(request, actor_id="phase-l-engineer", account_id="phase-l-engineer")
    assert published.traceability_metadata["agent_version"] == detail.version.version.version
    assert published.traceability_metadata["agent_version_id"] == str(detail.version.version.id)
    assert (published.output or {}).get("learning_authority", LEARNING_AUTHORITY) == LEARNING_AUTHORITY

    disabled = builder.disable_agent(
        detail.definition.id,
        project_id=project.id,
        actor_id="phase-l-engineer",
    )
    with pytest.raises(AgentNotExecutableError):
        runtime.execute(request, actor_id="phase-l-engineer", account_id="phase-l-engineer")
    history = runtime.list_executions(project.id)
    assert any(item.id == published.id for item in history)
    assert disabled.status is AgentDefinitionStatus.DISABLED
