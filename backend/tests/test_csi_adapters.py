"""Tests for CSI software detection and adapter boundaries."""

from app.domain.models.integration import IntegrationSoftware, SoftwareAvailabilityStatus
from app.infrastructure.integrations.csi_detection import CSI_PROFILES, detect_software_capability


def test_detect_etabs_without_installation_reports_unavailable() -> None:
    report = detect_software_capability(
        CSI_PROFILES[IntegrationSoftware.ETABS],
        com_probe=lambda _prog_id: False,
    )
    assert report.availability in {
        SoftwareAvailabilityStatus.NOT_INSTALLED,
        SoftwareAvailabilityStatus.NOT_ACCESSIBLE,
        SoftwareAvailabilityStatus.VERSION_MISMATCH,
        SoftwareAvailabilityStatus.REQUIRES_LOCAL_SOFTWARE,
        SoftwareAvailabilityStatus.AVAILABLE,
    }


def test_detect_sap2000_with_env_path_but_no_com_is_not_accessible(monkeypatch) -> None:
    profile = CSI_PROFILES[IntegrationSoftware.SAP2000]
    monkeypatch.setenv(profile.env_path_var, __file__)
    report = detect_software_capability(profile, com_probe=lambda _prog_id: False)
    assert report.availability in {
        SoftwareAvailabilityStatus.NOT_ACCESSIBLE,
        SoftwareAvailabilityStatus.REQUIRES_LOCAL_SOFTWARE,
        SoftwareAvailabilityStatus.NOT_INSTALLED,
    }


def test_etabs_adapter_reports_status_without_local_software() -> None:
    from app.infrastructure.integrations.csi_structural_adapter import EtabsAdapter

    adapter = EtabsAdapter(com_probe=lambda _prog_id: False)
    status = adapter.get_status()
    assert status.software == IntegrationSoftware.ETABS
    assert status.status.value in {
        "REQUIRES_LOCAL_SOFTWARE",
        "NOT_INSTALLED",
        "NOT_ACCESSIBLE",
        "VERSION_MISMATCH",
    }
