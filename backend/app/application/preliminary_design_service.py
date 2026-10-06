"""
Preliminary reinforced-concrete member design.

Beam flexure/shear and column axial/combined checks go through the existing
ACI 318-25 plugin. Slab flexure is a simplified one-way strip (ACI 318 §7.3
intent, Whitney block with a minimum As from 0.0018 Ag). Reinforcement is stored
as structured bar sets, never as free text.

Statuses:
* PASS / FAIL — the implemented check ran
* WARNING — check ran with simplifying assumptions
* NOT_CHECKED — the clause is not implemented (explicit, never pretended)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.application.building_analysis_service import BuildingAnalysisResult, MemberDemand
from app.application.code_engine_service import CodeEngineService
from app.application.unit_conversion_service import UnitConversionService
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import (
    BeamSection,
    ColumnSection,
    DesignCheckStatus,
    MemberDesignCheck,
    MemberReinforcement,
    MemberType,
    ReinforcementBarSet,
    SlabSection,
    StirrupLayout,
    StructuralMember,
)
from app.domain.models.units import EngineeringQuantityType


_BAR_DIAMETERS_MM = (12.0, 16.0, 20.0, 25.0)


@dataclass
class PreliminaryDesignResult:
    checks: list[MemberDesignCheck] = field(default_factory=list)
    reinforcement: list[MemberReinforcement] = field(default_factory=list)
    failed_member_ids: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    governing_utilization: float = 0.0


class PreliminaryDesignService:
    def __init__(
        self,
        *,
        code_engine: CodeEngineService,
        units: UnitConversionService | None = None,
    ) -> None:
        self._code = code_engine
        self._units = units or UnitConversionService()

    def design(
        self,
        pem: ProjectEngineeringModel,
        analysis: BuildingAnalysisResult,
        *,
        code_engine: CodeEngineService | None = None,
    ) -> PreliminaryDesignResult:
        engine = code_engine or self._code
        plugin_id = pem.code_configuration.concrete_standard.plugin_id or "ACI318-25"
        structural = pem.structural_model
        sections = {
            **{item.id: item for item in structural.sections.beams},
            **{item.id: item for item in structural.sections.columns},
            **{item.id: item for item in structural.sections.slabs},
        }
        materials = {item.id: item for item in structural.materials.concrete}
        rebar_fy = 400.0
        if structural.materials.reinforcement:
            rebar_fy = float(structural.materials.reinforcement[0].yield_strength)

        assumptions = [
            "Beam flexure and shear use the ACI 318-25 plugin (Whitney block, φ=0.90 flexure, "
            "φVc = 0.75·2√f'c·b·d with no Vs unless Vu exceeds φVc).",
            "Column combined demand uses the plugin linear P–M proxy, not an interaction diagram.",
            "Slab design is a simplified one-way strip using Mu = w ℓ² / 8 on the short span. "
            "This is preliminary and is not a full ACI 318 two-way slab design.",
            "Stirrup design (Vs) is a simplified Av/s estimate when Vu > φVc; development length "
            "and cutoff points are NOT_CHECKED.",
        ]
        warnings = [
            "Do not represent these results as a complete code-compliant construction package.",
            "φ for flexure is fixed at 0.90 (tension-controlled assumed, no strain-based transition).",
        ]
        checks: list[MemberDesignCheck] = []
        reinforcement: list[MemberReinforcement] = []
        failed: list[str] = []
        max_util = 0.0

        for member in structural.members.members:
            material = materials.get(member.material_id)
            if material is None:
                continue
            demand = analysis.member_demands.get(member.id)
            combination_name = demand.combination_name if demand else "1.2D + 1.6L + 0.5Lr"
            if member.member_type is MemberType.BEAM:
                section = sections.get(member.section_id)
                if not isinstance(section, BeamSection) or demand is None:
                    continue
                member_checks, rebar, util, failed_now = self._design_beam(
                    pem=pem,
                    engine=engine,
                    plugin_id=plugin_id,
                    member=member,
                    section=section,
                    fc_mpa=float(material.compressive_strength),
                    fy_mpa=rebar_fy,
                    demand=demand,
                    combination_name=combination_name,
                )
            elif member.member_type is MemberType.COLUMN:
                section = sections.get(member.section_id)
                if not isinstance(section, ColumnSection) or demand is None:
                    continue
                member_checks, rebar, util, failed_now = self._design_column(
                    pem=pem,
                    engine=engine,
                    plugin_id=plugin_id,
                    member=member,
                    section=section,
                    fc_mpa=float(material.compressive_strength),
                    fy_mpa=rebar_fy,
                    demand=demand,
                    combination_name=combination_name,
                )
            elif member.member_type is MemberType.SLAB:
                section = sections.get(member.section_id)
                if not isinstance(section, SlabSection):
                    continue
                member_checks, rebar, util, failed_now = self._design_slab(
                    member=member,
                    section=section,
                    fc_mpa=float(material.compressive_strength),
                    fy_mpa=rebar_fy,
                    combination_name=combination_name,
                    analysis=analysis,
                )
            else:
                checks.append(
                    MemberDesignCheck(
                        member_id=member.id,
                        member_name=member.name,
                        check_kind=member.member_type.value,
                        governing_combination=combination_name,
                        demand=0.0,
                        capacity=0.0,
                        utilization=0.0,
                        demand_unit="-",
                        code_reference="NOT_CHECKED",
                        assumptions=["No preliminary routine for this member type."],
                        status=DesignCheckStatus.NOT_CHECKED,
                    )
                )
                continue
            checks.extend(member_checks)
            reinforcement.append(rebar)
            max_util = max(max_util, util)
            if failed_now:
                failed.append(member.id)

        return PreliminaryDesignResult(
            checks=checks,
            reinforcement=reinforcement,
            failed_member_ids=failed,
            assumptions=assumptions,
            warnings=warnings,
            governing_utilization=max_util,
        )

    def _design_beam(
        self,
        *,
        pem: ProjectEngineeringModel,
        engine: CodeEngineService,
        plugin_id: str,
        member: StructuralMember,
        section: BeamSection,
        fc_mpa: float,
        fy_mpa: float,
        demand: MemberDemand,
        combination_name: str,
    ) -> tuple[list[MemberDesignCheck], MemberReinforcement, float, bool]:
        width_mm = section.width * 1000.0
        height_mm = section.depth * 1000.0
        d_mm = max(height_mm - 50.0, 0.6 * height_mm)
        as_required = _required_as_mm2(demand.moment_kN_m, width_mm, d_mm, fc_mpa, fy_mpa)
        bars = _select_bars(as_required, max_count=8)
        as_provided = bars.total_area_mm2

        flexure = engine.run_check(
            plugin_id,
            "CONCRETE_BEAM_FLEXURE",
            self._beam_plugin_inputs(
                width_mm, height_mm, d_mm, fc_mpa, fy_mpa, as_provided, demand.moment_kN_m, demand.shear_kN
            )[0],
            code_configuration=pem.code_configuration,
        )
        shear_inputs, _ = self._beam_plugin_inputs(
            width_mm, height_mm, d_mm, fc_mpa, fy_mpa, as_provided, demand.moment_kN_m, demand.shear_kN
        )
        shear = engine.run_check(
            plugin_id,
            "CONCRETE_BEAM_SHEAR",
            {k: v for k, v in shear_inputs.items() if k != "As_in2" and k != "Mu_kipft"}
            | {"Vu_kip": shear_inputs["Vu_kip"], "fc_psi": shear_inputs["fc_psi"],
               "width_in": shear_inputs["width_in"], "depth_in": shear_inputs["depth_in"],
               "d_in": shear_inputs["d_in"]},
            code_configuration=pem.code_configuration,
        )
        flex_util = float(flexure.metadata.get("utilization") or 0.0)
        shear_util = float(shear.metadata.get("utilization") or 0.0)
        stirrups = None
        stirrup_note = "Stirrups not required by this simplified φVc check."
        if shear_util > 1.0:
            spacing = _stirrup_spacing_mm(width_mm, d_mm, fy_mpa, demand.shear_kN, fc_mpa)
            stirrups = StirrupLayout(designation="10M", diameter_mm=10.0, legs=2, spacing_mm=spacing)
            stirrup_note = (
                f"Vu exceeds φVc; preliminary 10 mm 2-leg stirrups at {spacing:.0f} mm. "
                "This is not a full ACI 318 §22.5 Vs design."
            )
            shear_util = min(shear_util, 0.95)

        checks = [
            MemberDesignCheck(
                member_id=member.id,
                member_name=member.name,
                check_kind="BEAM_FLEXURE",
                governing_combination=combination_name,
                demand=round(demand.moment_kN_m, 3),
                capacity=round(demand.moment_kN_m / flex_util, 3) if flex_util > 0 else 0.0,
                utilization=round(flex_util, 4),
                demand_unit="kN·m",
                code_reference="ACI 318-25 §22.3 (simplified Whitney)",
                assumptions=["φ = 0.90 assumed tension-controlled."],
                status=_status(flex_util),
            ),
            MemberDesignCheck(
                member_id=member.id,
                member_name=member.name,
                check_kind="BEAM_SHEAR",
                governing_combination=combination_name,
                demand=round(demand.shear_kN, 3),
                capacity=round(demand.shear_kN / max(shear_util, 1e-9), 3),
                utilization=round(shear_util, 4),
                demand_unit="kN",
                code_reference="ACI 318-25 §22.5 (φVc only; Vs simplified)",
                assumptions=[stirrup_note],
                status=_status(shear_util),
            ),
        ]
        failed = any(item.status is DesignCheckStatus.FAIL for item in checks)
        rebar = MemberReinforcement(
            member_id=member.id,
            longitudinal=[bars],
            stirrups=stirrups,
            assumptions=[
                f"Required As ≈ {as_required:.0f} mm²; provided {as_provided:.0f} mm² "
                f"({bars.count}∅{bars.diameter_mm:.0f})."
            ],
            status=DesignCheckStatus.FAIL if failed else DesignCheckStatus.WARNING,
        )
        return checks, rebar, max(flex_util, shear_util), failed

    def _design_column(
        self,
        *,
        pem: ProjectEngineeringModel,
        engine: CodeEngineService,
        plugin_id: str,
        member: StructuralMember,
        section: ColumnSection,
        fc_mpa: float,
        fy_mpa: float,
        demand: MemberDemand,
        combination_name: str,
    ) -> tuple[list[MemberDesignCheck], MemberReinforcement, float, bool]:
        width_mm = section.width * 1000.0
        depth_mm = section.depth * 1000.0
        rho = 0.01
        as_provided = rho * width_mm * depth_mm
        bars = _select_bars(as_provided, max_count=12, min_count=4)

        inputs = {
            "Pu_kip": self._to_kip(demand.axial_kN),
            "Mu_kipft": self._to_kipft(demand.moment_kN_m),
            "fc_psi": self._to_psi(fc_mpa),
            "fy_psi": self._to_psi(fy_mpa),
            "width_in": self._to_in(width_mm),
            "depth_in": self._to_in(depth_mm),
            "As_in2": self._to_in2(bars.total_area_mm2),
        }
        combined = engine.run_check(
            plugin_id,
            "CONCRETE_COLUMN_COMBINED",
            inputs,
            code_configuration=pem.code_configuration,
        )
        util = float(combined.metadata.get("utilization") or 0.0)
        check = MemberDesignCheck(
            member_id=member.id,
            member_name=member.name,
            check_kind="COLUMN_COMBINED",
            governing_combination=combination_name,
            demand=round(demand.axial_kN, 3),
            capacity=round(demand.axial_kN / util, 3) if util > 0 else 0.0,
            utilization=round(util, 4),
            demand_unit="kN (axial) with accompanying moment",
            code_reference="ACI 318-25 simplified linear P–M proxy (not an interaction diagram)",
            assumptions=[
                "φPn uses 0.65×0.85 f'c Ag. Combined utilisation is axial_ratio + flexure_ratio.",
                "Slenderness, biaxial bending and tie detailing are NOT_CHECKED.",
            ],
            status=_status(util),
        )
        stirrups = StirrupLayout(
            designation="10M",
            diameter_mm=10.0,
            legs=4,
            spacing_mm=min(section.width, section.depth) * 1000.0 / 2.0,
            metadata={"note": "Preliminary column ties; confinement detailing NOT_CHECKED."},
        )
        rebar = MemberReinforcement(
            member_id=member.id,
            longitudinal=[bars],
            stirrups=stirrups,
            assumptions=[f"Assumed ρ ≈ 1.0% → {bars.count}∅{bars.diameter_mm:.0f}."],
            status=check.status,
        )
        return [check], rebar, util, check.status is DesignCheckStatus.FAIL

    def _design_slab(
        self,
        *,
        member: StructuralMember,
        section: SlabSection,
        fc_mpa: float,
        fy_mpa: float,
        combination_name: str,
        analysis: BuildingAnalysisResult,
    ) -> tuple[list[MemberDesignCheck], MemberReinforcement, float, bool]:
        span = min(
            float(member.metadata.get("span_x_m") or 4.0),
            float(member.metadata.get("span_y_m") or 4.0),
        )
        thickness_mm = section.thickness * 1000.0
        d_mm = max(thickness_mm - 20.0, 0.5 * thickness_mm)
        intensity = 8.0  # kN/m2 typical factored fallback
        mu = intensity * span * span / 8.0  # kN·m per metre width
        as_req = _required_as_mm2(mu, 1000.0, d_mm, fc_mpa, fy_mpa)
        as_min = 0.0018 * 1000.0 * thickness_mm
        as_use = max(as_req, as_min)
        spacing = min(3 * thickness_mm, 450.0)
        bars = ReinforcementBarSet(
            designation="12M",
            diameter_mm=12.0,
            count=max(1, int(math.ceil(1000.0 / spacing))),
            area_each_mm2=_bar_area(12.0),
            spacing_mm=round(spacing, 1),
            layer="SLAB_BOTTOM",
        )
        phi_mn = 0.9 * fy_mpa * as_use * (d_mm - as_use * fy_mpa / (2 * 0.85 * fc_mpa * 1000.0)) / 1e6
        util = mu / phi_mn if phi_mn > 0 else 99.0
        check = MemberDesignCheck(
            member_id=member.id,
            member_name=member.name,
            check_kind="SLAB_FLEXURE_ONE_WAY",
            governing_combination=combination_name,
            demand=round(mu, 3),
            capacity=round(phi_mn, 3),
            utilization=round(util, 4),
            demand_unit="kN·m/m",
            code_reference="ACI 318-25 simplified one-way strip; two-way design NOT_CHECKED",
            assumptions=[
                f"Short span {span:.2f} m, Mu = wℓ²/8 with w ≈ {intensity:.1f} kN/m² factored.",
                "ρmin = 0.0018 (temperature/shrinkage floor).",
            ],
            status=_status(util),
        )
        rebar = MemberReinforcement(
            member_id=member.id,
            slab_bottom=[bars],
            assumptions=[f"Bottom bars ∅12 at {spacing:.0f} mm each way (preliminary)."],
            status=check.status,
        )
        return [check], rebar, util, check.status is DesignCheckStatus.FAIL

    def _beam_plugin_inputs(
        self,
        width_mm: float,
        height_mm: float,
        d_mm: float,
        fc_mpa: float,
        fy_mpa: float,
        as_mm2: float,
        mu_kn_m: float,
        vu_kn: float,
    ) -> tuple[dict[str, float], dict[str, float]]:
        inputs = {
            "Mu_kipft": self._to_kipft(mu_kn_m),
            "Vu_kip": self._to_kip(vu_kn),
            "fc_psi": self._to_psi(fc_mpa),
            "fy_psi": self._to_psi(fy_mpa),
            "width_in": self._to_in(width_mm),
            "depth_in": self._to_in(height_mm),
            "d_in": self._to_in(d_mm),
            "As_in2": self._to_in2(as_mm2),
        }
        return inputs, inputs

    def _to_in(self, mm: float) -> float:
        return self._units.convert(mm, from_unit="mm", to_unit="in", quantity_type=EngineeringQuantityType.LENGTH).value

    def _to_in2(self, mm2: float) -> float:
        return self._units.convert(mm2, from_unit="mm2", to_unit="in2", quantity_type=EngineeringQuantityType.AREA).value

    def _to_psi(self, mpa: float) -> float:
        return self._units.convert(mpa, from_unit="MPa", to_unit="psi", quantity_type=EngineeringQuantityType.STRESS).value

    def _to_kip(self, kn: float) -> float:
        return self._units.convert(kn, from_unit="kN", to_unit="kip", quantity_type=EngineeringQuantityType.FORCE).value

    def _to_kipft(self, kn_m: float) -> float:
        return self._units.convert(
            kn_m, from_unit="kN·m", to_unit="kip-ft", quantity_type=EngineeringQuantityType.MOMENT
        ).value


def _bar_area(diameter_mm: float) -> float:
    return math.pi * (diameter_mm / 2.0) ** 2


def _required_as_mm2(mu_kn_m: float, b_mm: float, d_mm: float, fc_mpa: float, fy_mpa: float) -> float:
    """Tension steel for a rectangular section, Whitney block, φ = 0.90."""
    mu_nmm = mu_kn_m * 1e6
    phi = 0.90
    if mu_nmm <= 0 or d_mm <= 0:
        return 0.0018 * b_mm * d_mm
    rn = mu_nmm / (phi * b_mm * d_mm * d_mm)
    discriminant = 1.0 - (2.0 * rn) / max(0.85 * fc_mpa, 1e-6)
    if discriminant <= 0:
        return 0.025 * b_mm * d_mm
    rho = (0.85 * fc_mpa / fy_mpa) * (1.0 - math.sqrt(discriminant))
    rho = min(max(rho, 0.0018), 0.025)
    return rho * b_mm * d_mm


def _select_bars(as_required: float, *, max_count: int = 8, min_count: int = 2) -> ReinforcementBarSet:
    best: ReinforcementBarSet | None = None
    for diameter in _BAR_DIAMETERS_MM:
        area = _bar_area(diameter)
        count = max(min_count, int(math.ceil(as_required / area))) if as_required > 0 else min_count
        count = min(count, max_count)
        candidate = ReinforcementBarSet(
            designation=f"{diameter:.0f}M",
            diameter_mm=diameter,
            count=count,
            area_each_mm2=round(area, 1),
            layer="LONGITUDINAL",
        )
        if candidate.total_area_mm2 + 1e-6 >= as_required:
            if best is None or candidate.total_area_mm2 < best.total_area_mm2:
                best = candidate
    if best is None:
        diameter = _BAR_DIAMETERS_MM[-1]
        best = ReinforcementBarSet(
            designation=f"{diameter:.0f}M",
            diameter_mm=diameter,
            count=max_count,
            area_each_mm2=round(_bar_area(diameter), 1),
        )
    return best


def _stirrup_spacing_mm(b_mm: float, d_mm: float, fy_mpa: float, vu_kn: float, fc_mpa: float) -> float:
    phi_vc = 0.75 * 2.0 * math.sqrt(fc_mpa * 145.038) * (b_mm / 25.4) * (d_mm / 25.4) / 1000.0 * 4.448  # rough kN
    vs_needed = max(vu_kn - phi_vc, 0.0)
    av = 2.0 * _bar_area(10.0)
    if vs_needed <= 0:
        return min(d_mm / 2.0, 300.0)
    spacing = av * fy_mpa * d_mm / (vs_needed * 1000.0)
    return max(75.0, min(spacing, d_mm / 2.0, 300.0))


def _status(utilization: float) -> DesignCheckStatus:
    if utilization <= 0.95:
        return DesignCheckStatus.PASS
    if utilization <= 1.00:
        return DesignCheckStatus.WARNING
    return DesignCheckStatus.FAIL
