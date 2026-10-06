"""US default standard plugins — interface stubs for MVP CodeEngine."""

from __future__ import annotations

import math
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

    def run_check(
        self,
        check_id: str,
        inputs: dict[str, Any],
        *,
        code_configuration: CodeConfiguration,
    ) -> CodeCheckResult:
        if check_id == "CONCRETE_BEAM_FLEXURE":
            return self._concrete_beam_flexure(inputs)
        if check_id == "CONCRETE_BEAM_SHEAR":
            return self._concrete_beam_shear(inputs)
        if check_id == "CONCRETE_COLUMN_FLEXURE":
            return self._concrete_column_flexure(inputs)
        if check_id == "CONCRETE_COLUMN_AXIAL":
            return self._concrete_column_axial(inputs)
        if check_id == "CONCRETE_COLUMN_COMBINED":
            return self._concrete_column_combined(inputs)
        return super().run_check(check_id, inputs, code_configuration=code_configuration)

    def _concrete_beam_flexure(self, inputs: dict[str, Any]) -> CodeCheckResult:
        mu = float(inputs["Mu_kipft"])
        fc = float(inputs["fc_psi"])
        fy = float(inputs["fy_psi"])
        b = float(inputs["width_in"])
        h = float(inputs["depth_in"])
        d = float(inputs["d_in"]) if inputs.get("d_in") is not None else (h - 1.5 - 0.5)
        if inputs.get("As_in2") is not None:
            steel_area = float(inputs["As_in2"])
            a = (steel_area * fy) / max(0.85 * fc * b, 1.0)
            method = "whitney_rectangular_stress_block"
        else:
            a = (0.85 * fc * b * d) / max(fy, 1.0)
            a = min(a, 0.75 * d)
            method = "simplified_rectangular_stress_block"
        phi = 0.9
        mn_kipft = phi * 0.85 * fc * b * a * (d - a / 2.0) / 12.0 / 1000.0
        utilization = mu / mn_kipft if mn_kipft > 0 else math.inf
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="CONCRETE_BEAM_FLEXURE",
            outcome=outcome,
            message=f"Flexural utilization {utilization:.3f} (φMn={mn_kipft:.2f} kip-ft, Mu={mu:.2f} kip-ft)",
            code_family=self._family,
            code_edition=self._edition,
            code_section="22.3",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "phiMn_kipft": round(mn_kipft, 4),
                "a_in": round(a, 4),
                "d_in": round(d, 4),
                "method": method,
            },
        )

    def _concrete_beam_shear(self, inputs: dict[str, Any]) -> CodeCheckResult:
        vu = float(inputs["Vu_kip"])
        fc = float(inputs["fc_psi"])
        b = float(inputs["width_in"])
        h = float(inputs["depth_in"])
        d = float(inputs["d_in"]) if inputs.get("d_in") is not None else (h - 1.5 - 0.5)
        phi = 0.75
        vc_kip = phi * 2.0 * math.sqrt(max(fc, 1.0)) * b * d / 1000.0
        utilization = vu / vc_kip if vc_kip > 0 else math.inf
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="CONCRETE_BEAM_SHEAR",
            outcome=outcome,
            message=f"Shear utilization {utilization:.3f} (φVc={vc_kip:.2f} kip, Vu={vu:.2f} kip)",
            code_family=self._family,
            code_edition=self._edition,
            code_section="22.5",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "phiVc_kip": round(vc_kip, 4),
                "d_in": round(d, 4),
                "method": "simplified_concrete_shear",
            },
        )

    def _concrete_column_flexure(self, inputs: dict[str, Any]) -> CodeCheckResult:
        mu = float(inputs["Mu_kipft"])
        fc = float(inputs["fc_psi"])
        fy = float(inputs["fy_psi"])
        width = float(inputs["width_in"])
        depth = float(inputs["depth_in"])
        cover = 1.5
        d = depth - cover - 0.5
        a = (0.85 * fc * width * d) / max(fy, 1.0)
        a = min(a, 0.75 * d)
        phi = 0.65
        mn_kipft = phi * 0.85 * fc * width * a * (d - a / 2.0) / 12.0 / 1000.0
        utilization = mu / mn_kipft if mn_kipft > 0 else math.inf
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="CONCRETE_COLUMN_FLEXURE",
            outcome=outcome,
            message=f"Column flexural utilization {utilization:.3f} (φMn={mn_kipft:.2f} kip-ft, Mu={mu:.2f} kip-ft)",
            code_family=self._family,
            code_edition=self._edition,
            code_section="22.3",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "phiMn_kipft": round(mn_kipft, 4),
                "method": "simplified_column_flexure",
            },
        )

    def _concrete_column_axial(self, inputs: dict[str, Any]) -> CodeCheckResult:
        pu = float(inputs["Pu_kip"])
        fc = float(inputs["fc_psi"])
        width = float(inputs["width_in"])
        depth = float(inputs["depth_in"])
        ag_in2 = width * depth
        phi = 0.65
        pn_kip = phi * 0.85 * fc * ag_in2 / 1000.0
        utilization = pu / pn_kip if pn_kip > 0 else math.inf
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="CONCRETE_COLUMN_AXIAL",
            outcome=outcome,
            message=f"Column axial utilization {utilization:.3f} (φPn={pn_kip:.2f} kip, Pu={pu:.2f} kip)",
            code_family=self._family,
            code_edition=self._edition,
            code_section="22.4",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "phiPn_kip": round(pn_kip, 4),
                "method": "simplified_column_axial",
            },
        )

    def _concrete_column_combined(self, inputs: dict[str, Any]) -> CodeCheckResult:
        pu = float(inputs["Pu_kip"])
        mu = float(inputs["Mu_kipft"])
        fc = float(inputs["fc_psi"])
        fy = float(inputs["fy_psi"])
        width = float(inputs["width_in"])
        depth = float(inputs["depth_in"])
        cover = 1.5
        d = depth - cover - 0.5
        ag_in2 = width * depth
        phi_axial = 0.65
        phi_flexure = 0.65
        pn_kip = phi_axial * 0.85 * fc * ag_in2 / 1000.0
        a = min((0.85 * fc * width * d) / max(fy, 1.0), 0.75 * d)
        mn_kipft = phi_flexure * 0.85 * fc * width * a * (d - a / 2.0) / 12.0 / 1000.0
        axial_ratio = pu / pn_kip if pn_kip > 0 else math.inf
        flexure_ratio = mu / mn_kipft if mn_kipft > 0 else math.inf
        utilization = axial_ratio + flexure_ratio
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="CONCRETE_COLUMN_COMBINED",
            outcome=outcome,
            message=(
                f"Column P-M interaction utilization {utilization:.3f} "
                f"(Pu/φPn={axial_ratio:.3f}, Mu/φMn={flexure_ratio:.3f})"
            ),
            code_family=self._family,
            code_edition=self._edition,
            code_section="22.4",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "axial_ratio": round(axial_ratio, 4),
                "flexure_ratio": round(flexure_ratio, 4),
                "method": "linear_p_m_interaction",
            },
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

    def run_check(
        self,
        check_id: str,
        inputs: dict[str, Any],
        *,
        code_configuration: CodeConfiguration,
    ) -> CodeCheckResult:
        if check_id == "STEEL_BEAM_FLEXURE":
            return self._steel_beam_flexure(inputs)
        if check_id == "STEEL_MEMBER_AXIAL":
            return self._steel_member_axial(inputs)
        if check_id == "STEEL_MEMBER_INTERACTION":
            return self._steel_member_interaction(inputs)
        return super().run_check(check_id, inputs, code_configuration=code_configuration)

    def _steel_beam_flexure(self, inputs: dict[str, Any]) -> CodeCheckResult:
        mu = float(inputs["Mu_kipft"])
        fy = float(inputs["Fy_ksi"])
        zx = float(inputs["Zx_in3"])
        phi = 0.9
        mn_kipft = phi * fy * zx / 12.0
        utilization = mu / mn_kipft if mn_kipft > 0 else math.inf
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="STEEL_BEAM_FLEXURE",
            outcome=outcome,
            message=f"Flexural utilization {utilization:.3f} (φMn={mn_kipft:.2f} kip-ft, Mu={mu:.2f} kip-ft)",
            code_family=self._family,
            code_edition=self._edition,
            code_section="F2",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "phiMn_kipft": round(mn_kipft, 4),
                "method": "plastic_moment_capacity",
            },
        )

    def _steel_member_axial(self, inputs: dict[str, Any]) -> CodeCheckResult:
        pu = float(inputs["Pu_kip"])
        fy = float(inputs["Fy_ksi"])
        ag = float(inputs["Ag_in2"])
        phi = 0.9
        pn_kip = phi * fy * ag
        utilization = pu / pn_kip if pn_kip > 0 else math.inf
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="STEEL_MEMBER_AXIAL",
            outcome=outcome,
            message=f"Axial utilization {utilization:.3f} (φPn={pn_kip:.2f} kip, Pu={pu:.2f} kip)",
            code_family=self._family,
            code_edition=self._edition,
            code_section="E3",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "phiPn_kip": round(pn_kip, 4),
                "method": "yielding_limit_state",
            },
        )

    def _steel_member_interaction(self, inputs: dict[str, Any]) -> CodeCheckResult:
        mu = float(inputs["Mu_kipft"])
        pu = float(inputs["Pu_kip"])
        fy = float(inputs["Fy_ksi"])
        zx = float(inputs["Zx_in3"])
        ag = float(inputs["Ag_in2"])
        phi = 0.9
        pn_kip = phi * fy * ag
        mn_kipft = phi * fy * zx / 12.0
        axial_ratio = pu / pn_kip if pn_kip > 0 else math.inf
        flexure_ratio = mu / mn_kipft if mn_kipft > 0 else math.inf
        utilization = axial_ratio + flexure_ratio
        outcome = CheckOutcome.PASS if utilization <= 1.0 else CheckOutcome.FAIL
        return CodeCheckResult(
            check_id="STEEL_MEMBER_INTERACTION",
            outcome=outcome,
            message=(
                f"Steel P-M interaction utilization {utilization:.3f} "
                f"(Pu/φPn={axial_ratio:.3f}, Mu/φMn={flexure_ratio:.3f})"
            ),
            code_family=self._family,
            code_edition=self._edition,
            code_section="H1",
            inputs=inputs,
            metadata={
                "utilization": round(utilization, 4),
                "axial_ratio": round(axial_ratio, 4),
                "flexure_ratio": round(flexure_ratio, 4),
                "method": "linear_p_m_interaction",
            },
        )


def build_us_default_plugins() -> list[_BaseStandardPlugin]:
    return [
        Ibc2024Plugin(),
        Asce722Plugin(),
        Aci31825Plugin(),
        Aisc36022Plugin(),
    ]
