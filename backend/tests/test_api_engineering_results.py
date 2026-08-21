"""API tests for engineering results endpoints."""

from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient

from uuid import UUID

from app.application.service_factory import (
    build_engineering_result_service,
    build_pem_model_service,
    build_project_service,
)
from app.domain.models.engineering_results import EngineeringResultIngestionRequest
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)
from tests.test_api_design import _populate_model


def _ingest_sample_result(project_id: str) -> None:
    project_uuid = UUID(project_id)
    model = build_pem_model_service()
    model.update_geometry(project_uuid, sample_geometry(), summary="Geometry")
    model.update_materials(project_uuid, sample_materials(), summary="Materials")
    model.update_sections(project_uuid, sample_sections(), summary="Sections")
    model.update_members(project_uuid, sample_members(), summary="Members")
    model.update_supports(project_uuid, sample_supports(), summary="Supports")
    model.update_load_cases(project_uuid, sample_load_cases(), summary="Loads")
    model.update_load_combinations(project_uuid, sample_load_combinations(), summary="Combos")
    _, version, snapshot_id = model.get_current_model(project_uuid)

    service = build_engineering_result_service()
    service.ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project_uuid,
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results={
                "member_forces": [
                    {"id": "mbr-1", "values": [1.0, 2.0], "load_case": "lc-dead"}
                ],
                "joint_displacements": [
                    {"joint_name": "pt-1", "values": [0.001], "load_case": "lc-dead"}
                ],
            },
            provenance={"source_software": "ETABS", "execution_mode": "vendor"},
        )
    )


def test_api_list_and_get_engineering_results(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Results API Project"}).json()[
        "project"
    ]["id"]
    _ingest_sample_result(project_id)

    listed = api_client.get(f"/api/v1/engineering/results/{project_id}")
    assert listed.status_code == 200
    assert len(listed.json()["results"]) == 1

    result_id = listed.json()["results"][0]["id"]
    detail = api_client.get(f"/api/v1/engineering/results/{project_id}/{result_id}")
    assert detail.status_code == 200
    assert detail.json()["validation_status"] == "VALIDATED"

    validation = api_client.get(
        f"/api/v1/engineering/results/{project_id}/{result_id}/validation"
    )
    assert validation.status_code == 200
    assert validation.json()["engineering_results_available"] is True


def test_api_engineering_result_not_found(api_client: TestClient) -> None:
    project_id = api_client.post("/api/v1/projects", json={"name": "Missing Result Project"}).json()[
        "project"
    ]["id"]
    response = api_client.get(f"/api/v1/engineering/results/{project_id}/{uuid4()}")
    assert response.status_code == 404
