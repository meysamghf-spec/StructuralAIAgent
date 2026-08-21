"""Windows-local detection for AutoCAD 2027."""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass

from app.domain.models.integration import (
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)


@dataclass(frozen=True)
class AutocadSoftwareProfile:
    software: IntegrationSoftware
    expected_version: str
    env_path_var: str
    registry_paths: tuple[str, ...]
    executable_names: tuple[str, ...]


AUTOCAD_PROFILE = AutocadSoftwareProfile(
    software=IntegrationSoftware.AUTOCAD,
    expected_version="2027",
    env_path_var="AUTOCAD_INSTALL_PATH",
    registry_paths=(
        r"SOFTWARE\Autodesk\AutoCAD\R28.0",
        r"SOFTWARE\WOW6432Node\Autodesk\AutoCAD\R28.0",
        r"SOFTWARE\Autodesk\AutoCAD",
    ),
    executable_names=("acad.exe",),
)


def detect_autocad_capability(profile: AutocadSoftwareProfile = AUTOCAD_PROFILE) -> SoftwareCapabilityReport:
    if platform.system().lower() != "windows":
        return SoftwareCapabilityReport(
            software=profile.software,
            expected_version=profile.expected_version,
            availability=SoftwareAvailabilityStatus.REQUIRES_LOCAL_SOFTWARE,
            message="AutoCAD automation requires a local Windows installation.",
        )

    env_path = os.environ.get(profile.env_path_var)
    install_path = env_path if env_path and os.path.isdir(env_path) else None
    detected_version = None

    if install_path:
        for name in profile.executable_names:
            candidate = os.path.join(install_path, name)
            if os.path.isfile(candidate):
                return SoftwareCapabilityReport(
                    software=profile.software,
                    expected_version=profile.expected_version,
                    detected_version=profile.expected_version,
                    install_path=install_path,
                    availability=SoftwareAvailabilityStatus.AVAILABLE,
                    message=f"AutoCAD {profile.expected_version} is available on this computer.",
                    metadata={"executable": candidate},
                )

    try:
        import winreg

        for reg_path in profile.registry_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path) as key:
                    install_path, _ = winreg.QueryValueEx(key, "AcadLocation")
                    detected_version = profile.expected_version
                    if install_path and os.path.isdir(install_path):
                        return SoftwareCapabilityReport(
                            software=profile.software,
                            expected_version=profile.expected_version,
                            detected_version=detected_version,
                            install_path=install_path,
                            availability=SoftwareAvailabilityStatus.AVAILABLE,
                            message=f"AutoCAD {profile.expected_version} is available on this computer.",
                        )
            except OSError:
                continue
    except ImportError:
        pass

    return SoftwareCapabilityReport(
        software=profile.software,
        expected_version=profile.expected_version,
        install_path=install_path,
        availability=SoftwareAvailabilityStatus.NOT_INSTALLED,
        message=(
            f"AutoCAD {profile.expected_version} is not available on this computer. "
            f"Install AutoCAD {profile.expected_version} to export DWG drawings."
        ),
    )
