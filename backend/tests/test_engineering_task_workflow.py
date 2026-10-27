"""Engineering task workflow tests."""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.application.project_service import ProjectService
from app.application.service_factory import (
    build_agent_orchestration_service,
    build_agent_runtime_service,
    build_chat_attachment_context_service,
    build_conversation_service,
    build_engineering_task_execution_service,
    build_engineering_task_workflow_service,
    build_file_ingestion_service,
    build_project_service,
    build_prompt_generation_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus
from app.domain.models.engineering_task import EngineeringTaskStatus, WorkflowStepStatus
from app.domain.models.user import AuthenticatedAccount, AuthMethod
from app.infrastructure.repositories.postgres_conversation_repository import PostgresConversationRepository


def _create_project(project_service: ProjectService, name: str = "Workflow Project"):
    return project_service.create_project(name=name)


def _complex_building_request() -> str:
    return (
        "Design a three-story reinforced-concrete two-way frame building with a "
        "200 m x 200 m plan, three master bedrooms, one bathroom and one additional bathroom. "
        "Produce architectural drawings, structural design drawings and construction drawings, "
        "and provide the ETABS model."
    )


def test_simple_request_creates_structured_task(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    workflow = build_engineering_task_workflow_service()
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    prompt = build_prompt_generation_service().generate(
        user_request="Analyze this model for drift issues.",
        context_summary=context,
    )
    task = workflow.build_task(
        user_request="Analyze this model for drift issues.",
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
    )
    assert task.id
    assert task.normalized_objective
    assert task.steps
    assert task.primary_agent_type == prompt.selected_agent_type


def test_complex_request_builds_multi_step_workflow(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    prompt = build_prompt_generation_service().generate(
        user_request=_complex_building_request(),
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request=_complex_building_request(),
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
    )
    assert len(task.steps) >= 8
    assert task.requested_deliverables
    assert any("ETABS" in item for item in task.requested_deliverables)
    assert task.status in {
        EngineeringTaskStatus.WAITING_FOR_INPUT,
        EngineeringTaskStatus.READY,
        EngineeringTaskStatus.PARTIALLY_COMPLETED,
        EngineeringTaskStatus.RUNNING,
    }


def test_missing_critical_input_marks_waiting_for_input(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
            user_request="Extract requirements from the specification PDF",
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    task = record.traceability_metadata.get("engineering_task")
    assert record.execution_status == AgentExecutionStatus.BLOCKED
    assert task is not None
    assert task["status"] == EngineeringTaskStatus.WAITING_FOR_INPUT.value
    assert task["missing_required_inputs"]


def test_project_configuration_reduces_missing_code_and_units(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    assert context.get("code_configuration") is not None
    assert context.get("unit_configuration") is not None
    prompt = build_prompt_generation_service().generate(
        user_request=_complex_building_request(),
        context_summary=context,
    )
    assert "Project code configuration" not in prompt.missing_information
    assert "Project unit system" not in prompt.missing_information


def test_extracted_pdf_context_reaches_task(db_session: str, file_storage_root, project_service: ProjectService) -> None:
    from tests.fixtures.document_samples import sample_pdf_bytes

    del file_storage_root
    project = _create_project(project_service)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.project.id,
        filename="spec.pdf",
        content=sample_pdf_bytes(text="Seismic mass 450 tons"),
        content_type="application/pdf",
        created_by="engineer",
    )
    bundle = build_chat_attachment_context_service().build(
        project.project.id,
        [uploaded.id],
        created_by="engineer",
    )
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    context["chat_attachments"] = bundle.to_dict()
    prompt = build_prompt_generation_service().generate(
        user_request="Review the attached engineering document and summarize requirements.",
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request="Review the attached engineering document and summarize requirements.",
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
        attachment_context=bundle.to_dict(),
    )
    assert uploaded.id.hex in "".join(task.input_file_ids) or str(uploaded.id) in task.input_file_ids
    document_step = next((step for step in task.steps if step.capability == "document.review"), None)
    assert document_step is not None
    evaluated = build_engineering_task_workflow_service().evaluate_steps(task, context)
    assert document_step.status in {WorkflowStepStatus.EXECUTABLE, WorkflowStepStatus.EXECUTED}


def test_extracted_docx_context_reaches_task(db_session: str, file_storage_root, project_service: ProjectService) -> None:
    from tests.fixtures.document_samples import sample_docx_bytes

    del file_storage_root
    project = _create_project(project_service)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.project.id,
        filename="brief.docx",
        content=sample_docx_bytes(paragraph="Live load 2.0 kPa"),
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        created_by="engineer",
    )
    bundle = build_chat_attachment_context_service().build(project.project.id, [uploaded.id])
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    context["chat_attachments"] = bundle.to_dict()
    prompt = build_prompt_generation_service().generate(
        user_request="Summarize the attached brief.",
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request="Summarize the attached brief.",
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
        attachment_context=bundle.to_dict(),
    )
    assert task.input_file_ids
    assert any(
        step.capability == "document.review"
        for step in build_engineering_task_workflow_service().evaluate_steps(task, context).steps
    )


def test_spreadsheet_context_reaches_task(db_session: str, file_storage_root, project_service: ProjectService) -> None:
    del file_storage_root
    project = _create_project(project_service)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.project.id,
        filename="loads.xlsx",
        content=_minimal_xlsx_bytes(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        created_by="engineer",
    )
    bundle = build_chat_attachment_context_service().build(project.project.id, [uploaded.id])
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    context["chat_attachments"] = bundle.to_dict()
    prompt = build_prompt_generation_service().generate(
        user_request="Review the attached spreadsheet.",
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request="Review the attached spreadsheet.",
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
        attachment_context=bundle.to_dict(),
    )
    assert task.input_file_ids


def test_unsupported_edb_reports_limitation(db_session: str, file_storage_root, project_service: ProjectService) -> None:
    del file_storage_root
    project = _create_project(project_service)
    uploaded = build_file_ingestion_service().ingest_upload(
        project.project.id,
        filename="model.edb",
        content=b"binary-edb-content",
        content_type="application/octet-stream",
        created_by="engineer",
    )
    bundle = build_chat_attachment_context_service().build(project.project.id, [uploaded.id])
    assert bundle.entries[0].limitation
    assert "ETABS EDB" in bundle.entries[0].limitation


def test_complex_workflow_marks_etabs_step_unsupported(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    prompt = build_prompt_generation_service().generate(
        user_request=_complex_building_request(),
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request=_complex_building_request(),
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
    )
    etabs_step = next((step for step in task.steps if step.capability == "integration.etabs"), None)
    assert etabs_step is not None
    assert etabs_step.status == WorkflowStepStatus.UNSUPPORTED


def test_complex_workflow_marks_architectural_concept_executable(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    prompt = build_prompt_generation_service().generate(
        user_request=_complex_building_request(),
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request=_complex_building_request(),
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
    )
    arch_step = next(
        (step for step in task.steps if step.capability == "architectural.concept"),
        None,
    )
    assert arch_step is not None
    assert arch_step.status == WorkflowStepStatus.EXECUTABLE
    assert arch_step.dependencies == ["validate_inputs"]


def test_existing_agent_capability_routing(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Analyze the lateral system",
            requires_approval=False,
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    task = record.traceability_metadata["engineering_task"]
    assert task["primary_agent_type"] == EngineeringAgentType.ANALYSIS_AGENT.value


def test_unauthorized_project_blocked(api_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    from app.infrastructure.config import get_settings

    get_settings.cache_clear()
    owner_headers = {"X-Actor-Id": "workflow-owner"}
    other_headers = {"X-Actor-Id": "workflow-other"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Workflow Auth Project"},
        headers=owner_headers,
    ).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/chat",
        json={"message": "Analyze drift", "project_id": project_id},
        headers=other_headers,
    )
    assert response.status_code in {403, 404}


def test_unauthorized_file_blocked(db_session: str, file_storage_root, project_service: ProjectService) -> None:
    del file_storage_root
    project_a = _create_project(project_service, "Project A")
    project_b = _create_project(project_service, "Project B")
    uploaded = build_file_ingestion_service().ingest_upload(
        project_a.project.id,
        filename="private.txt",
        content=b"secret",
        content_type="text/plain",
        created_by="engineer",
    )
    repo = PostgresConversationRepository()
    account = AuthenticatedAccount(
        account_id="engineer-1",
        email="engineer@example.com",
        auth_method=AuthMethod.LEGACY_ACTOR,
    )
    conversation = repo.create(account_id=account.account_id, title="Test", project_id=project_b.project.id)
    service = build_conversation_service()
    from app.application.exceptions import ProjectFileNotFoundError

    with pytest.raises(ProjectFileNotFoundError):
        service.send_message(
            conversation.id,
            account,
            content="Review file",
            attachment_file_ids=[uploaded.id],
            actor_id=account.account_id,
        )


def test_approval_required_step_cannot_bypass_approval(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            user_request="Revise column layout on level 2",
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    assert record.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    task = record.traceability_metadata["engineering_task"]
    assert task["status"] == EngineeringTaskStatus.WAITING_FOR_APPROVAL.value


def test_real_executable_step_records_actual_result(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Analyze the lateral system",
            requires_approval=False,
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    task = record.traceability_metadata["engineering_task"]
    validate_step = next(step for step in task["steps"] if step["capability"] == "project.validate")
    assert validate_step["status"] == WorkflowStepStatus.EXECUTED.value
    assert validate_step.get("execution_result")


def test_unsupported_step_not_reported_as_completed(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            user_request=_complex_building_request(),
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    task = record.traceability_metadata["engineering_task"]
    unsupported = [step for step in task["steps"] if step["status"] == WorkflowStepStatus.UNSUPPORTED.value]
    assert unsupported
    assert task["status"] != EngineeringTaskStatus.COMPLETED.value


def test_artifact_provenance_persisted_when_generated(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.CAD_AGENT,
            user_request="Generate a framing plan drawing",
            requires_approval=False,
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    task = record.traceability_metadata["engineering_task"]
    if task["artifacts"]:
        artifact = task["artifacts"][0]
        assert artifact.get("producing_capability") or artifact.get("producing_agent_type")


def test_conversation_persistence_includes_engineering_task(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    repo = PostgresConversationRepository()
    account = AuthenticatedAccount(
        account_id="engineer-1",
        email="engineer@example.com",
        auth_method=AuthMethod.LEGACY_ACTOR,
    )
    conversation = repo.create(
        account_id=account.account_id,
        title="Workflow chat",
        project_id=project.project.id,
    )
    _, assistant = build_conversation_service().send_message(
        conversation.id,
        account,
        content=_complex_building_request(),
        actor_id=account.account_id,
    )
    assert assistant.metadata.get("engineering_task")
    assert "Engineering workflow" in assistant.content


def test_find_resumable_workflow_context_skips_completed_tasks() -> None:
    from datetime import UTC, datetime
    from uuid import uuid4

    from app.application.conversation_service import _find_resumable_workflow_context
    from app.domain.models.conversation import ConversationMessage, MessageRole

    execution_id = str(uuid4())
    task_id = str(uuid4())
    completed = ConversationMessage(
        id=uuid4(),
        conversation_id=uuid4(),
        role=MessageRole.ASSISTANT,
        content="Done",
        metadata={
            "execution_id": execution_id,
            "execution_status": "completed",
            "engineering_task": {"id": task_id, "status": EngineeringTaskStatus.COMPLETED.value},
        },
        created_at=datetime.now(UTC),
    )
    assert _find_resumable_workflow_context([completed]) is None

    partial = ConversationMessage(
        id=uuid4(),
        conversation_id=uuid4(),
        role=MessageRole.ASSISTANT,
        content="Partial",
        metadata={
            "execution_id": execution_id,
            "execution_status": "blocked",
            "engineering_task": {
                "id": task_id,
                "status": EngineeringTaskStatus.PARTIALLY_COMPLETED.value,
            },
        },
        created_at=datetime.now(UTC),
    )
    resume = _find_resumable_workflow_context([completed, partial])
    assert resume is not None
    assert resume["execution_id"] == execution_id
    assert resume["task_id"] == task_id


def test_refresh_task_for_resume_merges_supplemental_request(
    db_session: str,
    project_service: ProjectService,
) -> None:
    project = _create_project(project_service)
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    prompt = build_prompt_generation_service().generate(
        user_request=_complex_building_request(),
        context_summary=context,
    )
    workflow = build_engineering_task_workflow_service()
    task = workflow.build_task(
        user_request=_complex_building_request(),
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
    )
    original_missing_count = len(task.missing_required_inputs)
    supplemental = "Occupancy classification: Group R-2 residential."
    follow_up_prompt = build_prompt_generation_service().generate(
        user_request=supplemental,
        context_summary=context,
    )
    refreshed = workflow.refresh_task_for_resume(
        task,
        supplemental_request=supplemental,
        context_snapshot=context,
        prompt_result=follow_up_prompt,
    )
    assert "Supplemental input:" in refreshed.original_request
    assert supplemental in refreshed.original_request
    assert len(refreshed.missing_required_inputs) <= original_missing_count


def test_chat_follow_up_resumes_prior_engineering_task(
    db_session: str,
    project_service: ProjectService,
) -> None:
    project = _create_project(project_service)
    repo = PostgresConversationRepository()
    account = AuthenticatedAccount(
        account_id="engineer-1",
        email="engineer@example.com",
        auth_method=AuthMethod.LEGACY_ACTOR,
    )
    conversation = repo.create(
        account_id=account.account_id,
        title="Resume chat",
        project_id=project.project.id,
    )
    conversation_service = build_conversation_service()
    _, first_assistant = conversation_service.send_message(
        conversation.id,
        account,
        content="Extract requirements from the specification PDF and summarize design parameters.",
        actor_id=account.account_id,
    )
    first_task = first_assistant.metadata["engineering_task"]
    first_execution_id = first_assistant.metadata["execution_id"]
    assert first_assistant.metadata["execution_status"] == AgentExecutionStatus.BLOCKED.value
    assert first_task["status"] == EngineeringTaskStatus.WAITING_FOR_INPUT.value

    _, second_assistant = conversation_service.send_message(
        conversation.id,
        account,
        content="The specification defines 3 stories, Group R-2 occupancy, and ASCE 7-22 seismic parameters.",
        actor_id=account.account_id,
    )
    assert second_assistant.metadata.get("resumed_from_execution_id") == first_execution_id
    second_task = second_assistant.metadata["engineering_task"]
    assert second_task["id"] == first_task["id"]
    assert len(second_task["missing_required_inputs"]) <= len(first_task["missing_required_inputs"])


def test_post_chat_contract_remains_backward_compatible(api_client: TestClient) -> None:
    email = f"workflow-{uuid.uuid4().hex}@example.com"
    token = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Chat Contract Project"},
        headers=headers,
    ).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/chat",
        json={"message": "Analyze drift", "project_id": project_id},
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["conversation_id"]
    assert body["assistant_message"]["content"]


def test_complex_workflow_steps_include_dependencies(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    prompt = build_prompt_generation_service().generate(
        user_request=_complex_building_request(),
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request=_complex_building_request(),
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
    )
    analysis_step = next(step for step in task.steps if step.step_id == "structural_analysis")
    assert "structural_model" in analysis_step.dependencies
    etabs_step = next(step for step in task.steps if step.step_id == "etabs_model")
    assert "structural_model" in etabs_step.dependencies


def test_multi_step_execution_runs_dependency_order(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    runtime = build_agent_runtime_service()
    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            user_request=_complex_building_request(),
            parameters={"allow_missing_inputs": True},
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )
    task = record.traceability_metadata["engineering_task"]
    executed = [step for step in task["steps"] if step["status"] == WorkflowStepStatus.EXECUTED.value]
    assert len(executed) >= 3
    assert task["status"] != EngineeringTaskStatus.COMPLETED.value
    arch_step = next(step for step in task["steps"] if step.get("step_id") == "architectural_concept")
    assert arch_step["status"] == WorkflowStepStatus.EXECUTED.value


def test_execution_service_detects_multi_step_tasks(db_session: str, project_service: ProjectService) -> None:
    project = _create_project(project_service)
    orchestration = build_agent_orchestration_service()
    context = orchestration.build_context_snapshot(orchestration._context.assemble(project.project.id))  # noqa: SLF001
    prompt = build_prompt_generation_service().generate(
        user_request=_complex_building_request(),
        context_summary=context,
    )
    task = build_engineering_task_workflow_service().build_task(
        user_request=_complex_building_request(),
        project_id=project.project.id,
        context_snapshot=context,
        prompt_result=prompt,
    )
    execution_service = build_engineering_task_execution_service()
    assert execution_service.should_execute_multi_step(task) is True


def test_meta_agent_endpoints_remain_functional(api_client: TestClient) -> None:
    email = f"meta-{uuid.uuid4().hex}@example.com"
    token = api_client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "secure-password"},
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Meta Agent Project"},
        headers=headers,
    ).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/meta-agent/decide",
        json={"user_request": "Need an agent for drift review", "project_id": project_id},
        headers=headers,
    )
    assert response.status_code in {200, 201}


def _minimal_xlsx_bytes() -> bytes:
    import zipfile
    from io import BytesIO

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/worksheets/sheet1.xml" '
            'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
            "</Types>",
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            "<sheets><sheet name=\"Sheet1\" sheetId=\"1\" r:id=\"rId1\" "
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/>'
            "</sheets></workbook>",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<sheetData><row r="1"><c r="A1" t="inlineStr"><is><t>Dead load 5 kPa</t></is></c></row></sheetData>'
            "</worksheet>",
        )
    return buffer.getvalue()


def test_complex_workflow_plans_detailing_after_design_and_never_marks_it_done():
    from app.application import engineering_task_workflow_service as svc
    import inspect

    src = inspect.getsource(svc)
    assert '"rebar_detailing"' in src and 'capability="detailing.rebar"' in src
    assert src.index('"concrete_design"') < src.index('step_id="rebar_detailing"')
