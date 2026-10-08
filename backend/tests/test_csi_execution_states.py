"""Vendor execution states. These tests do not start ETABS or SAFE."""

from __future__ import annotations

from uuid import uuid4

from app.domain.models.integration import (
    IntegrationOperationStatus,
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)
from app.infrastructure.integrations.csi_detection import CSI_PROFILES
from app.infrastructure.integrations.csi_structural_adapter import EtabsAdapter, SafeAdapter, classify_vendor_failure
from tests.test_csi_pem_builder import _sample_pem


def _available(software: IntegrationSoftware) -> SoftwareCapabilityReport:
    return SoftwareCapabilityReport(
        software=software,
        expected_version="23",
        availability=SoftwareAvailabilityStatus.AVAILABLE,
        detected_version="23.0.0",
        message="Fake capability for a unit test. The application was not started.",
    )


def test_license_text_is_not_labeled_as_missing_software() -> None:
    status, failure_class = classify_vendor_failure(
        RuntimeError("ETABS license server refused the seat"),
        default_class="ANALYSIS_FAILURE",
    )
    assert status == IntegrationOperationStatus.NOT_ACCESSIBLE
    assert failure_class == "LICENSING_FAILURE"


def test_manifest_and_partial_build_are_not_analysis(tmp_path) -> None:
    adapter = EtabsAdapter(capability_override=_available(IntegrationSoftware.ETABS))

    class _SapModel:
        def InitializeNewModel(self, unit_system: int) -> int:
            assert unit_system == 6
            return 0

    class _Helper:
        SapModel = _SapModel()

    adapter._connected = True
    adapter._helper = _Helper()
    pem = _sample_pem()
    result = adapter.export_model_from_pem(
        pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        destination_path=str(tmp_path / "manifest.json"),
    )
    assert result.status == IntegrationOperationStatus.FAILED
    assert result.metadata["failure_class"] == "MODEL_BUILD_FAILURE"
    assert result.metadata["analysis_executed"] is False
    assert result.metadata["manifest_is_not_analysis"] is True
    assert result.metadata["vendor_export_status"] != "VENDOR_MODEL_BUILT"
    assert "not an analysis" in result.message


def test_initialize_return_code_is_a_model_build_failure(tmp_path) -> None:
    adapter = EtabsAdapter(capability_override=_available(IntegrationSoftware.ETABS))

    class _SapModel:
        def InitializeNewModel(self, unit_system: int) -> int:
            return 5

    class _Helper:
        SapModel = _SapModel()

    adapter._connected = True
    adapter._helper = _Helper()
    pem = _sample_pem()
    result = adapter.export_model_from_pem(
        pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        destination_path=str(tmp_path / "manifest.json"),
    )
    assert result.status == IntegrationOperationStatus.FAILED
    assert result.metadata["failure_class"] == "MODEL_BUILD_FAILURE"
    assert "code 5" in result.metadata["vendor_error"]
    assert result.status != IntegrationOperationStatus.REQUIRES_LOCAL_SOFTWARE


def test_safe_without_a_foundation_spec_does_not_run(tmp_path) -> None:
    adapter = SafeAdapter(capability_override=_available(IntegrationSoftware.SAFE))
    adapter._connected = True
    pem = _sample_pem()
    result = adapter.export_model_from_pem(
        pem.project_id,
        pem=pem,
        pem_snapshot_id=uuid4(),
        pem_version=1,
        destination_path=str(tmp_path / "safe.json"),
        foundation_spec=None,
    )
    assert result.status == IntegrationOperationStatus.FAILED
    assert result.metadata["failure_class"] == "MISSING_INPUTS"
    assert result.metadata["analysis_executed"] is False
    assert CSI_PROFILES[IntegrationSoftware.SAFE].software == IntegrationSoftware.SAFE
