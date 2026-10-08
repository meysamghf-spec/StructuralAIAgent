"""Licensed Windows integration tests.

These tests run only when this process is on Windows and the named application
actually starts. A skip is not a successful ETABS, SAFE, or AutoCAD execution.
"""

from __future__ import annotations

import platform
from uuid import uuid4

import pytest

from app.domain.models.integration import IntegrationOperationStatus, SoftwareAvailabilityStatus
from app.infrastructure.integrations.autocad_adapter import AutocadAdapter
from app.infrastructure.integrations.csi_structural_adapter import EtabsAdapter, SafeAdapter


def _require_windows(product: str) -> None:
    if platform.system().lower() != "windows":
        pytest.skip(
            f"{product} COM integration was not executed because this process is not running on Windows."
        )


@pytest.mark.integration
def test_etabs_licensed_analysis_when_installed(tmp_path) -> None:
    _require_windows("ETABS")
    adapter = EtabsAdapter()
    report = adapter.detect_capability()
    if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
        pytest.skip(
            "ETABS was not executed: "
            f"{report.availability.value}. {report.message}"
        )
    connect = adapter.connect(uuid4())
    if connect.status != IntegrationOperationStatus.SUCCESS:
        pytest.skip(
            "ETABS was not executed because the application did not connect: "
            f"{connect.status.value}. {connect.message}"
        )
    from tests.test_csi_pem_builder import _sample_pem

    pem = _sample_pem()
    snapshot_id = uuid4()
    exported = adapter.export_model_from_pem(
        pem.project_id,
        pem=pem,
        pem_snapshot_id=snapshot_id,
        pem_version=1,
        destination_path=str(tmp_path / "etabs.json"),
    )
    assert exported.status == IntegrationOperationStatus.SUCCESS, exported.message
    assert exported.metadata["vendor_export_status"] == "VENDOR_MODEL_BUILT"
    assert exported.metadata["analysis_executed"] is False
    analyzed = adapter.run_analysis(pem.project_id, parameters={"analysis_type": "STATIC"})
    assert analyzed.status == IntegrationOperationStatus.SUCCESS, analyzed.message
    assert analyzed.metadata["analysis_executed"] is True
    extracted = adapter.extract_results(
        pem.project_id,
        parameters={
            "pem_snapshot_id": str(snapshot_id),
            "pem_version": 1,
            "external_model_identity": exported.metadata["external_model_identity"],
            "member_ids": ["mbr-1"],
            "target_force_unit": "kip",
            "target_moment_unit": "kip-ft",
            "target_length_unit": "ft",
        },
    )
    assert extracted.status == IntegrationOperationStatus.SUCCESS, extracted.message
    assert extracted.metadata.get("result_types_present"), extracted.message
    adapter.disconnect(pem.project_id)


@pytest.mark.integration
def test_safe_licensed_foundation_analysis_when_installed(tmp_path) -> None:
    _require_windows("SAFE")
    adapter = SafeAdapter()
    report = adapter.detect_capability()
    if report.availability != SoftwareAvailabilityStatus.AVAILABLE:
        pytest.skip(
            "SAFE was not executed: "
            f"{report.availability.value}. {report.message}"
        )
    connect = adapter.connect(uuid4())
    if connect.status != IntegrationOperationStatus.SUCCESS:
        pytest.skip(
            "SAFE was not executed because the application did not connect: "
            f"{connect.status.value}. {connect.message}"
        )
    from app.application.safe_foundation_workflow import assess_safe_foundation_inputs
    from tests.test_safe_foundation_workflow import _pem

    pem = _pem()
    pem.structural_model.design_parameters.load_parameters = {
        "subgrade_modulus_kN_m3": 20000,
        "subgrade_modulus_origin": "USER_PROVIDED",
    }
    assessment = assess_safe_foundation_inputs(pem)
    assert assessment["ready"] is True
    snapshot_id = uuid4()
    exported = adapter.export_model_from_pem(
        pem.project_id,
        pem=pem,
        pem_snapshot_id=snapshot_id,
        pem_version=1,
        destination_path=str(tmp_path / "safe.json"),
        foundation_spec=assessment["spec"],
    )
    assert exported.status == IntegrationOperationStatus.SUCCESS, exported.message
    assert exported.metadata["vendor_export_status"] == "VENDOR_MODEL_BUILT"
    assert exported.metadata["analysis_executed"] is False
    analyzed = adapter.run_analysis(pem.project_id, parameters={"analysis_type": "STATIC"})
    assert analyzed.status == IntegrationOperationStatus.SUCCESS, analyzed.message
    assert analyzed.metadata["analysis_executed"] is True
    extracted = adapter.extract_results(
        pem.project_id,
        parameters={
            "pem_snapshot_id": str(snapshot_id),
            "pem_version": 1,
            "external_model_identity": exported.metadata["external_model_identity"],
            "target_force_unit": "kN",
            "target_moment_unit": "kN-m",
            "target_length_unit": "m",
        },
    )
    assert extracted.status == IntegrationOperationStatus.SUCCESS, extracted.message
    assert extracted.metadata.get("result_types_present"), extracted.message
    adapter.disconnect(pem.project_id)


@pytest.mark.integration
def test_autocad_licensed_drawing_when_installed(tmp_path) -> None:
    _require_windows("AutoCAD")
    adapter = AutocadAdapter()
    report = adapter.detect_capability()
    if report.availability.value != "AVAILABLE":
        pytest.skip(
            "AutoCAD was not executed: "
            f"{report.availability.value}. {report.message}"
        )
    result = adapter.generate_drawing(
        uuid4(),
        parameters={
            "sheet_plan": {
                "commands": [
                    {
                        "kind": "LINE",
                        "layer": "0",
                        "points": [[0.0, 0.0, 0.0], [1000.0, 0.0, 0.0]],
                        "closed": False,
                        "text": None,
                        "sheet": "S-101",
                        "source_element_ids": ["probe"],
                    }
                ],
                "geometry_count": 1,
                "annotation_count": 0,
                "sheets": [{"sheet": "S-101", "geometry_count": 1}],
                "missing_construction_details": ["S-301 structural sections", "S-401 reinforcement details"],
                "construction_ready": False,
            },
            "output_dir": str(tmp_path),
        },
    )
    assert result.status == IntegrationOperationStatus.SUCCESS
    assert result.metadata["drawing_executed"] is True
    assert result.metadata["dwg_bytes"] > 0
    assert result.metadata["construction_ready"] is False
