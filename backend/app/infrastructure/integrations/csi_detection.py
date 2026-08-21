"""Windows-local detection for CSI structural software (ETABS, SAP2000, SAFE)."""

from __future__ import annotations

import os
import platform
import re
from dataclasses import dataclass
from typing import Callable

from app.domain.models.integration import (
    IntegrationSoftware,
    SoftwareAvailabilityStatus,
    SoftwareCapabilityReport,
)


@dataclass(frozen=True)
class CsiSoftwareProfile:
    software: IntegrationSoftware
    expected_version: str
    env_path_var: str
    registry_paths: tuple[str, ...]
    prog_ids: tuple[str, ...]
    executable_names: tuple[str, ...]


CSI_PROFILES: dict[IntegrationSoftware, CsiSoftwareProfile] = {
    IntegrationSoftware.ETABS: CsiSoftwareProfile(
        software=IntegrationSoftware.ETABS,
        expected_version="23",
        env_path_var="ETABS_INSTALL_PATH",
        registry_paths=(
            r"SOFTWARE\Computers and Structures\ETABS 23",
            r"SOFTWARE\WOW6432Node\Computers and Structures\ETABS 23",
            r"SOFTWARE\Computers and Structures\ETABS",
        ),
        prog_ids=("ETABSv1.Helper",),
        executable_names=("ETABS.exe",),
    ),
    IntegrationSoftware.SAP2000: CsiSoftwareProfile(
        software=IntegrationSoftware.SAP2000,
        expected_version="27",
        env_path_var="SAP2000_INSTALL_PATH",
        registry_paths=(
            r"SOFTWARE\Computers and Structures\SAP2000 27",
            r"SOFTWARE\WOW6432Node\Computers and Structures\SAP2000 27",
            r"SOFTWARE\Computers and Structures\SAP2000",
        ),
        prog_ids=("Sap2000v1.Helper",),
        executable_names=("SAP2000.exe",),
    ),
    IntegrationSoftware.SAFE: CsiSoftwareProfile(
        software=IntegrationSoftware.SAFE,
        expected_version="23",
        env_path_var="SAFE_INSTALL_PATH",
        registry_paths=(
            r"SOFTWARE\Computers and Structures\SAFE 23",
            r"SOFTWARE\WOW6432Node\Computers and Structures\SAFE 23",
            r"SOFTWARE\Computers and Structures\SAFE",
        ),
        prog_ids=("SafeObject.v1.Helper",),
        executable_names=("SAFE.exe",),
    ),
}


def detect_software_capability(
    profile: CsiSoftwareProfile,
    *,
    com_probe: Callable[[str], bool] | None = None,
) -> SoftwareCapabilityReport:
    if platform.system().lower() != "windows":
        return SoftwareCapabilityReport(
            software=profile.software,
            expected_version=profile.expected_version,
            availability=SoftwareAvailabilityStatus.REQUIRES_LOCAL_SOFTWARE,
            message=(
                f"{profile.software.value} automation requires a local Windows installation."
            ),
            metadata={"platform": platform.system()},
        )

    env_path = os.environ.get(profile.env_path_var, "").strip()
    install_path = _normalize_path(env_path) if env_path else None
    detected_version: str | None = None
    registry_path: str | None = None

    if install_path is None:
        install_path, detected_version, registry_path = _detect_from_registry(profile)

    if install_path is None or not _path_exists(install_path):
        return SoftwareCapabilityReport(
            software=profile.software,
            expected_version=profile.expected_version,
            availability=SoftwareAvailabilityStatus.NOT_INSTALLED,
            message=(
                f"{profile.software.value} {profile.expected_version} was not detected on this computer. "
                f"Install the software or set {profile.env_path_var} to its installation folder."
            ),
            metadata={
                "env_path_var": profile.env_path_var,
                "registry_path": registry_path,
            },
        )

    executable_found = _find_executable(install_path, profile.executable_names)
    if detected_version is None:
        detected_version = _extract_version_from_path(install_path) or profile.expected_version

    if not _version_matches(profile.expected_version, detected_version):
        return SoftwareCapabilityReport(
            software=profile.software,
            expected_version=profile.expected_version,
            detected_version=detected_version,
            install_path=install_path,
            availability=SoftwareAvailabilityStatus.VERSION_MISMATCH,
            message=(
                f"Detected {profile.software.value} version {detected_version}, "
                f"but this platform expects version {profile.expected_version}."
            ),
            metadata={
                "executable_found": executable_found,
                "registry_path": registry_path,
            },
        )

    com_accessible = False
    com_error: str | None = None
    if com_probe is not None:
        for prog_id in profile.prog_ids:
            try:
                if com_probe(prog_id):
                    com_accessible = True
                    break
            except Exception as exc:  # noqa: BLE001 - vendor COM failures vary widely
                com_error = str(exc)
    else:
        com_accessible, com_error = _probe_com_access(profile.prog_ids)

    if not com_accessible:
        return SoftwareCapabilityReport(
            software=profile.software,
            expected_version=profile.expected_version,
            detected_version=detected_version,
            install_path=install_path,
            availability=SoftwareAvailabilityStatus.NOT_ACCESSIBLE,
            message=(
                f"{profile.software.value} is installed but could not be accessed for automation. "
                "Check that the application can be opened by the current user."
            ),
            metadata={
                "executable_found": executable_found,
                "registry_path": registry_path,
                "com_error": com_error,
            },
        )

    return SoftwareCapabilityReport(
        software=profile.software,
        expected_version=profile.expected_version,
        detected_version=detected_version,
        install_path=install_path,
        availability=SoftwareAvailabilityStatus.AVAILABLE,
        message=f"{profile.software.value} {detected_version} is available for automation.",
        metadata={
            "executable_found": executable_found,
            "registry_path": registry_path,
            "com_accessible": True,
        },
    )


def _detect_from_registry(profile: CsiSoftwareProfile) -> tuple[str | None, str | None, str | None]:
    try:
        import winreg
    except ImportError:
        return None, None, None

    for registry_path in profile.registry_paths:
        for value_name in ("InstallPath", "InstallDir", "Path"):
            install_path = _read_registry_value(winreg, registry_path, value_name)
            if install_path:
                version = _extract_version_from_path(install_path) or _extract_version_from_path(
                    registry_path
                )
                return _normalize_path(install_path), version, registry_path
    return None, None, None


def _read_registry_value(winreg, registry_path: str, value_name: str) -> str | None:
    for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
        try:
            with winreg.OpenKey(hive, registry_path) as key:
                value, _ = winreg.QueryValueEx(key, value_name)
                if isinstance(value, str) and value.strip():
                    return value.strip()
        except OSError:
            continue
    return None


def _probe_com_access(prog_ids: tuple[str, ...]) -> tuple[bool, str | None]:
    last_error: str | None = None
    for prog_id in prog_ids:
        try:
            helper = _create_com_object(prog_id)
            if helper is not None:
                return True, None
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)
    return False, last_error


def _create_com_object(prog_id: str):
    try:
        import comtypes.client

        return comtypes.client.CreateObject(prog_id)
    except ImportError:
        pass
    except Exception:
        raise

    try:
        import win32com.client

        return win32com.client.Dispatch(prog_id)
    except ImportError as exc:
        raise RuntimeError("COM automation libraries are not installed") from exc


def _find_executable(install_path: str, executable_names: tuple[str, ...]) -> str | None:
    for name in executable_names:
        candidate = os.path.join(install_path, name)
        if os.path.isfile(candidate):
            return candidate
    return None


def _path_exists(path: str) -> bool:
    return os.path.isdir(path) or os.path.isfile(path)


def _normalize_path(path: str) -> str:
    return os.path.normpath(os.path.expandvars(path.strip()))


def _extract_version_from_path(path: str) -> str | None:
    match = re.search(r"(?:ETABS|SAP2000|SAFE)\s*(\d+)", path, re.IGNORECASE)
    if match:
        return match.group(1)
    match = re.search(r"\b(\d{2})\b", path)
    if match:
        return match.group(1)
    return None


def _version_matches(expected: str, detected: str) -> bool:
    return expected.strip() == detected.strip()
