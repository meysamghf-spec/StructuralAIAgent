"""Agent orchestration core tests — lifecycle, prompt generation, authorization, blocking."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.application.agent_capability_catalog import get_agent_capability_profile
from app.application.exceptions import FeatureAccessDeniedError
from app.application.service_factory import (
    build_agent_orchestration_service,
    build_agent_runtime_service,
    build_project_service,
)
from app.domain.models.agent import EngineeringAgentType
from app.domain.models.agent_runtime import AgentExecutionRequest, AgentExecutionStatus, is_awaiting_human_approval
from app.infrastructure.config import get_settings


def _create_project(db_session: str):
    return build_project_service().create_project(name="Orchestration Project")


def test_orchestration_executes_analysis_agent_to_completion(db_session: str) -> None:
    project = _create_project(db_session)
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.ANALYSIS_AGENT,
            user_request="Analyze the lateral system",
            requires_approval=False,
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    assert record.execution_status == AgentExecutionStatus.COMPLETED
    assert record.traceability_metadata.get("request_trace_id")
    assert record.traceability_metadata.get("orchestration_trace")


def test_orchestration_prompt_generation_includes_structured_task_fields(db_session: str) -> None:
    project = _create_project(db_session)
    runtime = build_agent_runtime_service()

    plan = runtime.plan_request(
        project_id=project.project.id,
        user_request="Prepare a seismic load assessment",
    )

    assert plan.objective
    assert plan.available_tools
    assert plan.expected_output
    assert plan.validation_requirements
    assert "Do not fabricate CSI or analysis results" in plan.validation_requirements


def test_orchestration_blocks_when_required_inputs_missing(db_session: str) -> None:
    project = _create_project(db_session)
    orchestration = build_agent_orchestration_service()

    record = orchestration.orchestrate(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.DOCUMENT_INTERPRETATION_AGENT,
            user_request="Extract requirements from the specification PDF",
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    assert record.execution_status == AgentExecutionStatus.BLOCKED
    assert record.error_metadata.get("missing_inputs")


def test_orchestration_high_impact_agent_requires_human_approval(db_session: str) -> None:
    project = _create_project(db_session)
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.STRUCTURAL_MODELING_AGENT,
            user_request="Revise column layout on level 2",
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    assert is_awaiting_human_approval(record.execution_status)
    assert record.approval_request_id is not None


def test_capability_profile_declares_contracts() -> None:
    profile = get_agent_capability_profile(EngineeringAgentType.ANALYSIS_AGENT)
    assert profile.name
    assert profile.input_contract
    assert profile.output_contract
    assert "engineering.analysis.run" in profile.available_tools


@pytest.fixture
def enforced_entitlements(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ENTITLEMENT_ENFORCEMENT_ENABLED", "true")
    get_settings.cache_clear()


def test_orchestration_entitlement_denial_for_cad_agent(
    db_session: str,
    enforced_entitlements: None,
) -> None:
    project = _create_project(db_session)
    orchestration = build_agent_orchestration_service()

    with pytest.raises(FeatureAccessDeniedError):
        orchestration.orchestrate(
            AgentExecutionRequest(
                project_id=project.project.id,
                agent_type=EngineeringAgentType.CAD_AGENT,
                user_request="Generate drawings",
                parameters={"allow_missing_inputs": True},
            ),
            actor_id="engineer-1",
            account_id="engineer-1",
        )


@pytest.fixture
def enforced_project_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROJECT_ACCESS_ENFORCED", "true")
    get_settings.cache_clear()


def test_project_scoped_agent_requires_authorization(
    api_client: TestClient,
    enforced_project_access: None,
) -> None:
    owner_headers = {"X-Actor-Id": "agent-owner"}
    other_headers = {"X-Actor-Id": "agent-other"}

    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Agent Auth Project"},
        headers=owner_headers,
    ).json()["project"]["id"]

    created = api_client.post(
        "/api/v1/agents",
        json={
            "key": "project-agent",
            "name": "Project Agent",
            "agent_type": EngineeringAgentType.VALIDATION_AGENT.value,
            "project_id": project_id,
        },
        headers=owner_headers,
    )
    assert created.status_code == 201
    agent_id = created.json()["id"]

    allowed = api_client.get(f"/api/v1/agents/{agent_id}", headers=owner_headers)
    assert allowed.status_code == 200

    denied = api_client.get(f"/api/v1/agents/{agent_id}", headers=other_headers)
    assert denied.status_code == 403


def test_global_agent_listing_under_enforcement_excludes_project_agents(
    api_client: TestClient,
    enforced_project_access: None,
) -> None:
    owner_headers = {"X-Actor-Id": "list-owner"}
    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "List Agents Project"},
        headers=owner_headers,
    ).json()["project"]["id"]

    api_client.post(
        "/api/v1/agents",
        json={
            "key": "scoped-agent",
            "name": "Scoped Agent",
            "agent_type": EngineeringAgentType.VALIDATION_AGENT.value,
            "project_id": project_id,
        },
        headers=owner_headers,
    )

    listed = api_client.get("/api/v1/agents", headers=owner_headers)
    assert listed.status_code == 200
    assert all(item.get("project_id") is None for item in listed.json()["agents"])


def test_project_scoped_agent_version_routes_require_authorization(
    api_client: TestClient,
    enforced_project_access: None,
) -> None:
    owner_headers = {"X-Actor-Id": "version-owner"}
    other_headers = {"X-Actor-Id": "version-other"}

    project_id = api_client.post(
        "/api/v1/projects",
        json={"name": "Agent Version Auth Project"},
        headers=owner_headers,
    ).json()["project"]["id"]

    created = api_client.post(
        "/api/v1/agents",
        json={
            "key": "version-agent",
            "name": "Version Agent",
            "agent_type": EngineeringAgentType.VALIDATION_AGENT.value,
            "project_id": project_id,
        },
        headers=owner_headers,
    )
    agent_id = created.json()["id"]

    allowed = api_client.get(f"/api/v1/agents/{agent_id}/versions", headers=owner_headers)
    assert allowed.status_code == 200

    denied = api_client.get(f"/api/v1/agents/{agent_id}/versions", headers=other_headers)
    assert denied.status_code == 403


def test_high_impact_agent_cannot_bypass_approval_with_client_flag(db_session: str) -> None:
    project = build_project_service().create_project(name="Approval Bypass Project")
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            user_request="Run concrete member design for the project frames.",
            requires_approval=False,
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    assert record.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL


def test_aci_missing_inputs_do_not_create_approval(db_session: str) -> None:
    project = build_project_service().create_project(name="ACI Missing Input Project")
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            user_request="Design this beam.",
            requires_approval=False,
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    assert record.execution_status == AgentExecutionStatus.COMPLETED
    assert record.approval_request_id is None
    assert record.agent_result is not None
    assert record.agent_result.structured_output["capability_status"] == "MISSING_REQUIRED_INPUT"


def test_aci_completed_check_requires_approval(db_session: str) -> None:
    project = build_project_service().create_project(name="ACI Complete Check Project")
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.CONCRETE_DESIGN_AGENT,
            user_request=(
                "Check this RC beam per ACI 318: span 6 m, 20 kN/m, "
                "b=300 mm, h=500 mm, d=450 mm, fc=25 MPa, fy=400 MPa, As=1500 mm2."
            ),
            requires_approval=False,
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    assert record.execution_status == AgentExecutionStatus.REQUIRES_HUMAN_APPROVAL
    assert record.approval_request_id is not None
    assert record.agent_result is not None
    assert record.agent_result.structured_output["aci_rc_beam"]["kind"] == "aci_rc_beam"


def test_agent_orchestration_ignores_client_orchestration_task(db_session: str) -> None:
    project = build_project_service().create_project(name="Orchestration Injection Project")
    runtime = build_agent_runtime_service()

    record = runtime.execute(
        AgentExecutionRequest(
            project_id=project.project.id,
            agent_type=EngineeringAgentType.VALIDATION_AGENT,
            user_request="Validate the project",
            parameters={
                "orchestration_task": "engineering.optimization.run",
                "orchestration_payload": {
                    "optimization_type": "MULTI_MEMBER",
                    "parameters": {"member_ids": ["m1", "m2", "m3"]},
                },
            },
            requires_approval=False,
        ),
        actor_id="engineer-1",
        account_id="engineer-1",
    )

    orchestration = record.agent_result.validation_information.get("orchestration", {}) if record.agent_result else {}
    assert orchestration.get("task_type") == "project.validate"
