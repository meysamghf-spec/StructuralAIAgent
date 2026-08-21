"""Integration, AI Gateway, and orchestration tests."""

from uuid import uuid4

from app.application.service_factory import (
    build_ai_gateway_service,
    build_hybrid_orchestration_service,
    build_integration_service,
    build_project_service,
)
from app.domain.models.ai_gateway import AICompletionRequest, AIMessage, AIMessageRole
from app.domain.models.integration import IntegrationOperation, IntegrationRequest, IntegrationSoftware
from app.domain.models.orchestration import OrchestrationTask


def test_list_integration_adapters() -> None:
    adapters = build_integration_service().list_adapters()
    names = {item.software.value for item in adapters}
    assert names == {"AUTOCAD", "ETABS", "SAFE", "SAP2000"}


def test_execute_etabs_status(db_session) -> None:
    project = build_project_service().create_project("Integration Project").project
    result = build_integration_service().execute(
        IntegrationRequest(
            project_id=project.id,
            software=IntegrationSoftware.ETABS,
            operation=IntegrationOperation.STATUS,
        )
    )
    assert result.status.value in {
        "REQUIRES_LOCAL_SOFTWARE",
        "NOT_INSTALLED",
        "NOT_ACCESSIBLE",
        "VERSION_MISMATCH",
    }


def test_stub_ai_gateway_complete() -> None:
    response = build_ai_gateway_service().complete(
        AICompletionRequest(
            model="stub-default",
            messages=[AIMessage(role=AIMessageRole.USER, content="Summarize drift limits")],
            context={"project_id": str(uuid4())},
        )
    )
    assert response.provider.value == "STUB"
    assert response.structured_output is not None


def test_orchestration_routes_validation(db_session) -> None:
    project = build_project_service().create_project("Orchestration Project").project
    result = build_hybrid_orchestration_service().execute(
        OrchestrationTask(task_type="project.validate", project_id=project.id)
    )
    assert result.route.value == "VALIDATION"


def test_orchestration_routes_ai_for_unknown_task() -> None:
    result = build_hybrid_orchestration_service().execute(
        OrchestrationTask(task_type="interpret.document", payload={"prompt": "hello"})
    )
    assert result.route.value == "AI"
