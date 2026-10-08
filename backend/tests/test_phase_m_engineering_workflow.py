"""Phase M: an analysis request records the PEM and the real analysis run."""

from fastapi.testclient import TestClient

from app.application.engineering_workflow_trace import engineering_workflow_trace
from app.application.service_factory import build_analysis_engine_service
from app.domain.models.agent import EngineeringAgentType
from uuid import UUID


def test_workflow_trace_keeps_only_real_identifiers() -> None:
    traced = engineering_workflow_trace(
        {
            "analysis_run_id": "run-1",
            "capability_status": "MODEL_NOT_READY",
            "engineering_results_available": False,
            "design_run_id": None,
            "pem_version": 4,
        }
    )
    assert traced == {
        "analysis_run_id": "run-1",
        "capability_status": "MODEL_NOT_READY",
        "engineering_results_available": False,
    }
    assert "pem_version" not in traced


def test_analysis_execution_links_the_current_pem_to_the_analysis_run(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Workflow project"}).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.ANALYSIS_AGENT.value,
            "user_request": "Run a lateral drift check",
            "requires_approval": False,
            "parameters": {"analysis_type": "LATERAL_DRIFT", "pem_version": 99},
        },
    )
    assert response.status_code == 201
    body = response.json()
    trace = body["traceability_metadata"]
    assert trace["pem_snapshot_id"]
    assert trace["pem_version"] != 99
    assert trace["analysis_run_id"]
    assert trace["capability_status"] == "MODEL_NOT_READY"
    assert trace["engineering_results_available"] is False
    assert body["output"].get("learning_overrides_pem") is not True

    stored = build_analysis_engine_service().get_run(UUID(project_id), UUID(trace["analysis_run_id"]))
    assert str(stored.pem_snapshot_id) == trace["pem_snapshot_id"]
    assert stored.pem_version == trace["pem_version"]
    assert stored.outputs.get("engineering_results_available") is False
