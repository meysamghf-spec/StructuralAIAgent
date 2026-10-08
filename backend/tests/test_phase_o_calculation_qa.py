"""Phase O: QA pass is reserved for a check that actually passed."""

from app.application.agent_qa import resolve_agent_qa_status
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentValidationStatus
from fastapi.testclient import TestClient


def test_missing_check_is_not_a_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"capability_status": "PARTIALLY_COMPLETED"},
        structured_output={"action": "multi_step_workflow"},
        confidence=0.6,
    )
    assert status == AgentValidationStatus.NOT_RUN


def test_design_waiting_on_analysis_is_not_a_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"capability_status": "REQUIRES_ANALYSIS"},
        structured_output={
            "engineering_design_results_available": False,
            "capability_status": "REQUIRES_ANALYSIS",
        },
        confidence=0.9,
    )
    assert status == AgentValidationStatus.NOT_RUN


def test_unavailable_solver_is_not_a_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"capability_status": "REQUIRES_LOCAL_SOFTWARE"},
        structured_output={"engineering_results_available": False, "solver": "ETABS"},
        confidence=0.8,
    )
    assert status == AgentValidationStatus.NOT_RUN


def test_successful_analysis_is_not_treated_as_qa_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"capability_status": "SUCCESS"},
        structured_output={"engineering_results_available": True, "capability_status": "SUCCESS"},
        confidence=0.8,
    )
    assert status == AgentValidationStatus.NOT_RUN


def test_recorded_check_pass_remains_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"capability_status": "PASS", "validation_status": "PASS"},
        structured_output={"action": "concrete_design"},
        confidence=1.0,
    )
    assert status == AgentValidationStatus.PASS


def test_failed_check_remains_an_error() -> None:
    status = resolve_agent_qa_status(
        validation_information={"validation_status": "FAIL"},
        structured_output={},
        confidence=1.0,
    )
    assert status == AgentValidationStatus.ERROR


def test_pass_contradicted_by_missing_results_is_not_a_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"validation_status": "PASS"},
        structured_output={"engineering_results_available": False},
        confidence=1.0,
    )
    assert status == AgentValidationStatus.NOT_RUN


def test_design_check_with_results_can_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"capability_status": "PASS"},
        structured_output={"engineering_design_results_available": True, "capability_status": "PASS"},
        confidence=0.4,
    )
    assert status == AgentValidationStatus.PASS


def test_fabricated_results_cannot_pass() -> None:
    status = resolve_agent_qa_status(
        validation_information={"fabricated_results": True, "validation_status": "PASS"},
        structured_output={"engineering_results_available": True},
        confidence=1.0,
    )
    assert status == AgentValidationStatus.ERROR


def test_analysis_agent_without_a_model_is_not_qa_passed(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "QA analysis"}).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.ANALYSIS_AGENT.value,
            "user_request": "Run lateral drift analysis",
            "requires_approval": False,
            "parameters": {"analysis_type": "LATERAL_DRIFT", "allow_missing_inputs": True},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["validation_status"] == "NOT_RUN"
    assert body["traceability_metadata"]["qa_status"] == "NOT_RUN"
    assert body["traceability_metadata"]["engineering_results_available"] is False
    assert body["output"].get("outputs", {}).get("engineering_results") is None


def test_concrete_design_without_analysis_is_not_qa_passed(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "QA design"}).json()["project"]["id"]
    response = api_client.post(
        "/api/v1/agent-executions",
        json={
            "project_id": project_id,
            "agent_type": EngineeringAgentType.CONCRETE_DESIGN_AGENT.value,
            "user_request": "Run concrete member design",
            "requires_approval": False,
            "parameters": {"design_type": "CONCRETE_MEMBER", "allow_missing_inputs": True},
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    trace = body["traceability_metadata"]
    assert body["validation_status"] == "NOT_RUN"
    assert trace["qa_status"] == "NOT_RUN"
    assert trace["engineering_design_results_available"] is False
    assert trace["design_run_id"]
    assert trace["capability_status"] in {"REQUIRES_ANALYSIS", "MODEL_NOT_READY"}
