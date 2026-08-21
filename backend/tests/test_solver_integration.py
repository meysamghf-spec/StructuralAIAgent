"""API and service tests for external solver integration."""

from uuid import uuid4

from fastapi.testclient import TestClient

from app.application.service_factory import (
    build_analysis_engine_service,
    build_project_service,
    build_structural_solver_integration_service,
)
from app.domain.models.integration import IntegrationSoftware
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)
from app.application.service_factory import build_pem_model_service
from app.domain.models.analysis import AnalysisRequest


def _create_project(name: str = "Solver Integration Project"):
    return build_project_service().create_project(name).project


def _populate_model(project_id):
    service = build_pem_model_service()
    service.update_geometry(project_id, sample_geometry(), summary="Geometry")
    service.update_materials(project_id, sample_materials(), summary="Materials")
    service.update_sections(project_id, sample_sections(), summary="Sections")
    service.update_members(project_id, sample_members(), summary="Members")
    service.update_supports(project_id, sample_supports(), summary="Supports")
    service.update_load_cases(project_id, sample_load_cases(), summary="Loads")
    service.update_load_combinations(project_id, sample_load_combinations(), summary="Combos")


def test_list_solver_capabilities(db_session) -> None:
    capabilities = build_structural_solver_integration_service().list_capabilities()
    assert len(capabilities) == 3
    assert {item.software for item in capabilities} == {
        IntegrationSoftware.ETABS,
        IntegrationSoftware.SAP2000,
        IntegrationSoftware.SAFE,
    }


def test_analysis_with_solver_returns_requires_local_software_when_unavailable(db_session) -> None:
    project = _create_project()
    _populate_model(project.id)
    result = build_analysis_engine_service().run_analysis(
        AnalysisRequest(
            project_id=project.id,
            analysis_type="STATIC",
            parameters={"solver": "ETABS"},
        )
    )
    assert result.status.value in {"REQUIRES_LOCAL_SOFTWARE", "FAILED"}
    assert result.outputs.get("engineering_results_available") is False
    assert result.outputs.get("solver") == "ETABS"


def test_api_list_solver_capabilities(api_client: TestClient) -> None:
    response = api_client.get("/api/v1/integrations/capabilities")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 3
    assert all(item["availability"] for item in body)


def test_api_integration_execute_status(api_client: TestClient) -> None:
    project = api_client.post("/api/v1/projects", json={"name": "ETABS Project"}).json()
    project_id = project["project"]["id"]
    response = api_client.post(
        "/api/v1/integrations/execute",
        json={
            "project_id": project_id,
            "software": "ETABS",
            "operation": "STATUS",
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] in {
        "REQUIRES_LOCAL_SOFTWARE",
        "NOT_INSTALLED",
        "NOT_ACCESSIBLE",
        "VERSION_MISMATCH",
        "SUCCESS",
    }


def test_api_analysis_with_solver(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Analysis Solver Project"}).json()[
        "project"
    ]["id"]
    _populate_model_api(api_client, project_id)
    response = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={
            "project_id": project_id,
            "analysis_type": "STATIC",
            "parameters": {"solver": "SAP2000"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outputs"]["solver"] == "SAP2000"
    assert body["outputs"]["engineering_results_available"] is False


def test_api_integration_executions_empty(api_client: TestClient) -> None:
    create = api_client.post("/api/v1/projects", json={"name": "Execution History Project"})
    project_id = create.json()["project"]["id"]
    response = api_client.get(f"/api/v1/integrations/{project_id}/executions")
    assert response.status_code == 200
    assert response.json() == []


def _populate_model_api(api_client: TestClient, project_id: str) -> None:
    headers = {"X-Actor-Id": "integration-tester"}
    api_client.put(
        f"/api/v1/projects/{project_id}/model/geometry",
        json={"summary": "Geometry", "geometry": sample_geometry().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/materials",
        json={"summary": "Materials", "materials": sample_materials().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/sections",
        json={"summary": "Sections", "sections": sample_sections().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/members",
        json={"summary": "Members", "members": sample_members().model_dump(mode="json")},
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/supports",
        json={
            "summary": "Supports",
            "supports": [item.model_dump(mode="json") for item in sample_supports()],
        },
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/load-cases",
        json={
            "summary": "Loads",
            "load_cases": [item.model_dump(mode="json") for item in sample_load_cases()],
        },
        headers=headers,
    )
    api_client.put(
        f"/api/v1/projects/{project_id}/model/load-combinations",
        json={
            "summary": "Combos",
            "load_combinations": [item.model_dump(mode="json") for item in sample_load_combinations()],
        },
        headers=headers,
    )
