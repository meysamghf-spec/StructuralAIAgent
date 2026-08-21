"""API test for deterministic design with validated results."""

from uuid import UUID

from fastapi.testclient import TestClient

from app.application.service_factory import build_engineering_result_service, build_pem_model_service
from app.domain.models.engineering_results import EngineeringResultIngestionRequest
from app.infrastructure.repositories.postgres_analysis_repository import PostgresAnalysisRepository
from app.domain.models.analysis import AnalysisStatus
from tests.test_api_design import _create_project, _populate_model


def _ingest_validated_results(project_id: str, analysis_run_id: str) -> None:
    project_uuid = UUID(project_id)
    model = build_pem_model_service()
    _, version, snapshot_id = model.get_current_model(project_uuid)
    build_engineering_result_service().ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project_uuid,
            analysis_run_id=UUID(analysis_run_id),
            pem_snapshot_id=snapshot_id,
            pem_version=version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results={
                "member_forces": [
                    {
                        "id": "mbr-1",
                        "values": [4.0, 0.0, -1.0],
                        "load_case": "lc-dead",
                    }
                ],
                "joint_displacements": [
                    {"joint_name": "pt-1", "values": [0.001], "load_case": "lc-dead"}
                ],
            },
            provenance={"source_software": "ETABS", "execution_mode": "vendor"},
        )
    )


def test_design_runs_with_validated_results(api_client: TestClient) -> None:
    project_id = _create_project(api_client)
    _populate_model(api_client, project_id)

    analysis = api_client.post(
        "/api/v1/engineering/analysis/run",
        json={"project_id": project_id, "analysis_type": "LINEAR_STATIC"},
    ).json()
    PostgresAnalysisRepository().update_run(
        UUID(project_id),
        UUID(analysis["id"]),
        status=AnalysisStatus.SUCCESS,
        capability_status="SUCCESS",
        message="Completed",
        outputs={"engineering_results_available": False},
    )
    _ingest_validated_results(project_id, analysis["id"])

    design = api_client.post(
        "/api/v1/engineering/design/run",
        json={"project_id": project_id, "design_type": "CONCRETE_BEAM"},
    )
    assert design.status_code == 200
    body = design.json()
    assert body["status"] in {"PASS", "FAIL", "WARNING"}
    assert body["outputs"].get("routine_connected") is True
    assert body["outputs"].get("result_set_id") is not None
