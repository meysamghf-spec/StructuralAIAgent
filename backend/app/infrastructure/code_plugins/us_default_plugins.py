"""US default standard plugins — interface stubs for MVP CodeEngine."""

from __future__ import annotations

from typing import Any

from app.domain.models.code_engine import (
    CheckOutcome,
    CodeCheckResult,
    ProvisionReference,
    ProvisionStatus,
    StandardInfo,
    StandardRole,
)
from app.domain.models.pem import CodeConfiguration


class _BaseStandardPlugin:
    def __init__(
        self,
        *,
        plugin_id: str,
        family: str,
        edition: str,
        full_designation: str,
        roles: list[StandardRole],
    ) -> None:
        self._plugin_id = plugin_id
        self._family = family
        self._edition = edition
        self._full_designation = full_designation
        self._roles = roles

    @property
    def plugin_id(self) -> str:
        return self._plugin_id

    @property
    def family(self) -> str:
        return self._family

    @property
    def edition(self) -> str:
        return self._edition

    @property
    def roles(self) -> list[StandardRole]:
        return self._roles

    def get_info(self) -> StandardInfo:
        return StandardInfo(
            plugin_id=self._plugin_id,
            family=self._family,
            edition=self._edition,
            full_designation=self._full_designation,
            roles=self._roles,
        )

    def get_provision(self, section_ref: str) -> ProvisionReference:
        return ProvisionReference(
            plugin_id=self._plugin_id,
            section_ref=section_ref,
            status=ProvisionStatus.PROVISION_TEXT_UNAVAILABLE,
            summary=f"Provision reference for {self._family} {section_ref}",
        )

    def run_check(
        self,
        check_id: str,
        inputs: dict[str, Any],
        *,
        code_configuration: CodeConfiguration,
    ) -> CodeCheckResult:
        return CodeCheckResult(
            check_id=check_id,
            outcome=CheckOutcome.NOT_APPLICABLE,
            message=f"Check {check_id} is not implemented for {self._family}",
            code_family=self._family,
            code_edition=self._edition,
            inputs=inputs,
        )

    def get_compatible_with(self, other_plugin_id: str) -> bool:
        us_ids = {
            "IBC-2024",
            "ASCE7-22",
            "ACI318-25",
            "AISC360-22",
        }
        return other_plugin_id in us_ids


class Ibc2024Plugin(_BaseStandardPlugin):
    def __init__(self) -> None:
        super().__init__(
            plugin_id="IBC-2024",
            family="IBC",
            edition="IBC 2024",
            full_designation="2024 International Building Code",
            roles=[StandardRole.BUILDING_CODE],
        )


class Asce722Plugin(_BaseStandardPlugin):
    def __init__(self) -> None:
        super().__init__(
            plugin_id="ASCE7-22",
            family="ASCE 7",
            edition="ASCE 7-22",
            full_designation=(
                "ASCE/SEI 7-22 Minimum Design Loads and Associated Criteria "
                "for Buildings and Other Structures"
            ),
            roles=[StandardRole.LOADING, StandardRole.SEISMIC],
        )


class Aci31825Plugin(_BaseStandardPlugin):
    def __init__(self) -> None:
        super().__init__(
            plugin_id="ACI318-25",
            family="ACI 318",
            edition="ACI CODE-318-25",
            full_designation=(
                "ACI CODE-318-25 Building Code for Structural Concrete "
                "— Code Requirements and Commentary"
            ),
            roles=[StandardRole.CONCRETE],
        )


class Aisc36022Plugin(_BaseStandardPlugin):
    def __init__(self) -> None:
        super().__init__(
            plugin_id="AISC360-22",
            family="AISC 360",
            edition="AISC 360-22",
            full_designation="ANSI/AISC 360-22 Specification for Structural Steel Buildings",
            roles=[StandardRole.STEEL],
        )


def build_us_default_plugins() -> list[_BaseStandardPlugin]:
    return [
        Ibc2024Plugin(),
        Asce722Plugin(),
        Aci31825Plugin(),
        Aisc36022Plugin(),
    ]
