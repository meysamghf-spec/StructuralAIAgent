"""Phase N: a named solver that is not installed is recorded and not executed."""

from uuid import UUID

from fastapi.testclient import TestClient

from app.application.service_factory import (
    build_pem_model_service,
    build_structural_solver_integration_service,
)
from app.domain.models.agent import EngineeringAgentType
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _populate(project_id: str) -> None:
    service = build_pem_model_service()
    project = UUID(project_id)
    service.update_geometry(project, sample_geometry(), summary="Geometry")
    service.update_materials(project, sample_materials(), summary="Materials")
    service.update_sections(project, sample_sections(), summary="Sections")
    service.update_members(project, sample_members(), summary="Members")
    service.update_supports(project, sample_supports(), summary="Supports")
    service.update_load_cases(project, sample_load_cases(), summary="Loads")
    service.update_load_combinations(project, sample_load_combinations(), summary="Combos")


def test_analysis_agent_records_etabs_as_not_executed(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "ETABS workflow"}).json()["project"]["id"]
    _populate(project_id)
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.ANALYSIS_AGENT.value,
            "user_request": "Run static analysis in ETABS",
            "requires_approval": False,
            "parameters": {"analysis_type": "STATIC", "solver": "ETABS"},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    trace = body["traceability_metadata"]
    assert body["output"].get("action") == "analysis"
    assert trace.get("solver") == "ETABS"
    assert trace["solver_status"] in {"REQUIRES_LOCAL_SOFTWARE", "NOT_INSTALLED", "NOT_ACCESSIBLE"}
    assert trace["engineering_results_available"] is False
    assert trace["integration_execution_id"]
    assert trace["pem_snapshot_id"]
    assert "engineering_results" not in body["output"].get("outputs", {})

    execution = build_structural_solver_integration_service().get_execution(
        UUID(project_id),
        UUID(trace["integration_execution_id"]),
    )
    assert execution.status.value == "REQUIRES_LOCAL_SOFTWARE"
    assert str(execution.pem_snapshot_id) == trace["pem_snapshot_id"]
    assert execution.outputs.get("executed") is False
    assert execution.outputs.get("engineering_results_available") is False
