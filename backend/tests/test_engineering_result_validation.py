"""Tests for engineering result normalization and validation."""

from __future__ import annotations

from uuid import uuid4

from app.application.engineering_result_normalization import normalize_vendor_results
from app.application.engineering_result_validation import validate_engineering_results
from app.application.service_factory import build_pem_model_service, build_project_service
from app.domain.models.engineering_results import ResultValidationStatus
from tests.fixtures.pem_structural_samples import (
    sample_geometry,
    sample_load_cases,
    sample_load_combinations,
    sample_materials,
    sample_members,
    sample_sections,
    sample_supports,
)


def _build_pem(db_session):
    project = build_project_service().create_project("Result Validation Project").project
    model = build_pem_model_service()
    model.update_geometry(project.id, sample_geometry(), summary="Geometry")
    model.update_materials(project.id, sample_materials(), summary="Materials")
    model.update_sections(project.id, sample_sections(), summary="Sections")
    model.update_members(project.id, sample_members(), summary="Members")
    model.update_supports(project.id, sample_supports(), summary="Supports")
    model.update_load_cases(project.id, sample_load_cases(), summary="Loads")
    model.update_load_combinations(project.id, sample_load_combinations(), summary="Combos")
    pem, _, _ = model.get_current_model(project.id)
    return project.id, pem


def test_normalize_vendor_results_maps_member_forces(db_session) -> None:
    normalized = normalize_vendor_results(
        {
            "member_forces": [
                {
                    "id": "mbr-1",
                    "values": [10.0, 0.0, -5.0],
                    "units": "kip",
                    "load_case": "lc-dead",
                }
            ]
        }
    )
    assert normalized.frame_forces
    assert normalized.frame_forces[0]["source_identifier"] == "mbr-1"


def test_validate_rejects_mock_execution(db_session) -> None:
    _, pem = _build_pem(db_session)
    normalized = normalize_vendor_results(
        {"member_forces": [{"id": "mbr-1", "values": [1.0], "load_case": "lc-dead"}]}
    )
    status, summary = validate_engineering_results(
        normalized=normalized,
        pem=pem,
        analysis_type="LINEAR_STATIC",
        software="ETABS",
        software_version="23",
        provenance={"source_software": "ETABS", "execution_mode": "mock"},
    )
    assert status == ResultValidationStatus.INVALID
    assert summary["findings"]


def test_validate_accepts_vendor_member_forces(db_session) -> None:
    _, pem = _build_pem(db_session)
    normalized = normalize_vendor_results(
        {
            "member_forces": [
                {
                    "id": "mbr-1",
                    "values": [12.5, -2.0, 0.0],
                    "units": "kip",
                    "load_case": "lc-dead",
                }
            ],
            "joint_displacements": [
                {
                    "joint_name": "pt-1",
                    "values": [0.001, 0.0, 0.0],
                    "units": "in",
                    "load_case": "lc-dead",
                }
            ],
        }
    )
    status, summary = validate_engineering_results(
        normalized=normalized,
        pem=pem,
        analysis_type="LINEAR_STATIC",
        software="ETABS",
        software_version="23",
        provenance={"source_software": "ETABS", "execution_mode": "vendor"},
    )
    assert status == ResultValidationStatus.VALIDATED
    assert summary["result_entry_count"] >= 2


def test_validate_rejects_non_finite_values(db_session) -> None:
    _, pem = _build_pem(db_session)
    normalized = normalize_vendor_results(
        {"member_forces": [{"id": "mbr-1", "values": [float("nan")], "load_case": "lc-dead"}]}
    )
    status, _ = validate_engineering_results(
        normalized=normalized,
        pem=pem,
        analysis_type="LINEAR_STATIC",
        software="ETABS",
        software_version="23",
        provenance={"source_software": "ETABS", "execution_mode": "vendor"},
    )
    assert status == ResultValidationStatus.INVALID
