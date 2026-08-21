"""Shared helpers for end-to-end integration tests."""

from __future__ import annotations

from uuid import UUID, uuid4

from app.application.service_factory import (
    build_engineering_result_service,
    build_pem_model_service,
    build_project_service,
)
from app.domain.models.engineering_results import EngineeringResultIngestionRequest
from app.domain.models.integration import (
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)
from app.infrastructure.integrations.csi_structural_adapter import EtabsAdapter
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_multi_beam_geometry,
    sample_multi_beam_members,
    sample_sections,
    sample_supports,
)
from tests.test_csi_result_extractor import _MockSapModel


def create_project(name: str = "E2E Project"):
    return build_project_service().create_project(name).project


def populate_standard_pem(project_id: UUID, *, members=None) -> tuple[int, UUID]:
    model = build_pem_model_service()
    model.update_geometry(project_id, sample_geometry(), summary="Geometry")
    model.update_materials(project_id, sample_materials(), summary="Materials")
    model.update_sections(project_id, sample_sections(), summary="Sections")
    model.update_members(project_id, members or sample_members(), summary="Members")
    model.update_supports(project_id, sample_supports(), summary="Supports")
    model.update_load_cases(project_id, sample_load_cases(), summary="Loads")
    model.update_load_combinations(project_id, sample_load_combinations(), summary="Combos")
    _, version, snapshot_id = model.get_current_model(project_id)
    return version, snapshot_id


def populate_multi_beam_pem(project_id: UUID) -> tuple[int, UUID]:
    model = build_pem_model_service()
    model.update_geometry(project_id, sample_multi_beam_geometry(), summary="Geometry")
    model.update_materials(project_id, sample_materials(), summary="Materials")
    model.update_sections(project_id, sample_sections(), summary="Sections")
    model.update_members(project_id, sample_multi_beam_members(), summary="Members")
    model.update_supports(project_id, sample_supports(), summary="Supports")
    model.update_load_cases(project_id, sample_load_cases(), summary="Loads")
    model.update_load_combinations(project_id, sample_load_combinations(), summary="Combos")
    _, version, snapshot_id = model.get_current_model(project_id)
    return version, snapshot_id


def ingest_vendor_frame_results(
    project_id: UUID,
    *,
    pem_version: int,
    pem_snapshot_id: UUID,
    analysis_run_id: UUID | None = None,
    member_forces: list[dict] | None = None,
) -> UUID:
    forces = member_forces or [
        {
            "id": "mbr-1",
            "axial_force": 10.0,
            "shear_v2": 4.0,
            "shear_v3": 0.0,
            "moment_m2": 120.0,
            "moment_m3": 15.0,
            "values": [10.0, 4.0, 0.0, 0.0, 120.0, 15.0],
            "load_case": "lc-dead",
            "units": {"force": "kip", "moment": "kip-ft"},
        }
    ]
    result_set = build_engineering_result_service().ingest_results(
        EngineeringResultIngestionRequest(
            project_id=project_id,
            analysis_run_id=analysis_run_id,
            pem_snapshot_id=pem_snapshot_id,
            pem_version=pem_version,
            software="ETABS",
            software_version="23",
            analysis_type="LINEAR_STATIC",
            raw_results={
                "member_forces": forces,
                "joint_displacements": [
                    {"joint_name": "pt-1", "values": [0.001], "load_case": "lc-dead"}
                ],
                "execution_mode": "vendor",
            },
            provenance={"source_software": "ETABS", "execution_mode": "vendor"},
        )
    )
    assert result_set.engineering_results_available is True
    return result_set.id


def build_mock_csi_adapter() -> EtabsAdapter:
    report = SoftwareCapabilityReport(
        software=IntegrationSoftware.ETABS,
        expected_version="23",
        availability=SoftwareAvailabilityStatus.AVAILABLE,
        message="Mock CSI available for integration tests",
    )
    adapter = EtabsAdapter(capability_override=report)
    adapter._helper = type("Helper", (), {"SapModel": _MockSapModel()})()
    adapter._connected = True
    return adapter


def unavailable_csi_adapter() -> EtabsAdapter:
    return EtabsAdapter(com_probe=lambda _prog_id: False)
