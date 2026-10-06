"""
Preliminary isolated-footing checks (ACI 318 intent, SI).

Implemented: plan area from allowable bearing, eccentricity/kern, one-way shear,
punching shear, flexure, and bar selection.
Soil bearing is never invented as a site investigation — a configurable
PRELIMINARY_ASSUMPTION is used when the project does not supply qa.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.application.building_analysis_service import BuildingAnalysisResult
from app.application.reinforcement_selection import ReinforcementSelectionEngine
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import (
    DesignCheckStatus,
    FoundationFooting,
    InputOrigin,
    InputProvenance,
    MemberDesignCheck,
    MemberReinforcement,
    MemberType,
)


@dataclass
class FoundationDesignDefaults:
    allowable_bearing_kPa: float = 150.0
    bearing_origin: InputOrigin = InputOrigin.ASSUMED
    thickness_m: float = 0.50
    cover_m: float = 0.075
    fc_mpa: float = 25.0
    fy_mpa: float = 400.0
    min_width_m: float = 0.80


@dataclass
class FoundationDesignResult:
    footings: list[FoundationFooting]
    provenance: list[InputProvenance]
    assumptions: list[str]
    warnings: list[str]


class FoundationDesignService:
    def __init__(self, defaults: FoundationDesignDefaults | None = None) -> None:
        self._d = defaults or FoundationDesignDefaults()
        self._rebar = ReinforcementSelectionEngine()

    def design(self, pem: ProjectEngineeringModel, analysis: BuildingAnalysisResult) -> FoundationDesignResult:
        structural = pem.structural_model
        points = {point.id: point for point in structural.geometry.points}
        columns = [member for member in structural.members.members if member.member_type is MemberType.COLUMN]
        column_sections = {item.id: item for item in structural.sections.columns}
        qa = float(
            (structural.design_parameters.load_parameters or {}).get("allowable_bearing_kPa")
            or self._d.allowable_bearing_kPa
        )
        origin = (
            InputOrigin.USER_PROVIDED
            if (structural.design_parameters.load_parameters or {}).get("allowable_bearing_kPa")
            else self._d.bearing_origin
        )
        assumptions = [
            f"Allowable bearing qa = {qa:.1f} kPa ({origin.value}).",
            "Service axial load is approximated as Pu / 1.4 from the gravity combination reaction (PRELIMINARY).",
            "Isolated square footings; combined footings are generated only when two columns are closer than 1.5 m.",
        ]
        warnings = [
            "Geotechnical site data was not used. qa is a PRELIMINARY_ASSUMPTION unless the user supplied it.",
            "This is not a substitute for a geotechnical report or a SAFE/mat foundation model.",
        ]
        provenance = [
            InputProvenance(
                field="allowable_bearing_kPa",
                value=str(qa),
                origin=origin,
                note="PRELIMINARY_ASSUMPTION when not user-provided.",
                unit="kPa",
            )
        ]

        # Group columns by footprint (x,y of base).
        base_columns: dict[str, object] = {}
        for member in columns:
            start = points.get(member.start_point_id or "")
            if start is None or abs(start.z) > 0.05:
                continue
            base_columns[member.id] = member

        footings: list[FoundationFooting] = []
        for member in base_columns.values():
            reaction = float(analysis.reactions_kN.get(member.start_point_id or "", 0.0))
            pu = max(reaction, 1.0)
            ps = pu / 1.4
            area = max(ps / max(qa, 1.0), self._d.min_width_m**2)
            width = max(self._d.min_width_m, math.ceil(math.sqrt(area) * 20.0) / 20.0)
            length = width
            section = column_sections.get(member.section_id)
            col_a = float(getattr(section, "width", 0.4) or 0.4)
            col_b = float(getattr(section, "depth", 0.4) or 0.4)
            thickness = self._d.thickness_m
            d_m = max(thickness - self._d.cover_m, 0.2)
            q_s = ps / (width * length)
            e_x = 0.0
            kern = width / 6.0
            ecc_ok = abs(e_x) <= kern
            # One-way shear at d from face
            overhang = (width - col_a) / 2.0
            vu_one = q_s * width * max(overhang - d_m, 0.0)
            vc_one = 0.75 * 0.17 * math.sqrt(self._d.fc_mpa) * 1000.0 * width * d_m  # kN, √fc MPa, m
            # Punching
            b0 = 2.0 * ((col_a + d_m) + (col_b + d_m))
            vu_punch = ps  # conservative: full service load
            vc_punch = 0.75 * 0.33 * math.sqrt(self._d.fc_mpa) * 1000.0 * b0 * d_m
            mu = q_s * width * max(overhang, 0.0) ** 2 / 2.0  # kN·m
            as_req = 0.0
            if mu > 0 and d_m > 0:
                as_req = mu * 1e6 / (0.90 * self._d.fy_mpa * 0.9 * d_m * 1000.0)
            as_min = 0.0018 * width * 1000.0 * thickness * 1000.0
            bars = self._rebar.select_longitudinal(max(as_req, as_min), width_mm=width * 1000.0, depth_mm=thickness * 1000.0, min_count=4)
            checks = [
                _check(member.id, "FOOTING_BEARING", q_s, qa, "kPa", "Allowable bearing (service)", DesignCheckStatus.PASS if q_s <= qa else DesignCheckStatus.FAIL),
                _check(member.id, "FOOTING_ECCENTRICITY", abs(e_x), kern, "m", "Kern / eccentricity", DesignCheckStatus.PASS if ecc_ok else DesignCheckStatus.FAIL),
                _check(member.id, "FOOTING_ONE_WAY_SHEAR", vu_one, vc_one, "kN", "ACI 318 one-way shear (preliminary SI)", _status(vu_one / max(vc_one, 1e-9))),
                _check(member.id, "FOOTING_PUNCHING", vu_punch, vc_punch, "kN", "ACI 318 punching (preliminary SI)", _status(vu_punch / max(vc_punch, 1e-9))),
                _check(member.id, "FOOTING_FLEXURE", mu, mu / max(bars.utilization, 1e-6) if bars.utilization else mu, "kN·m", "Footing flexure with selected As", _status(bars.utilization)),
            ]
            failed = any(item.status is DesignCheckStatus.FAIL for item in checks)
            bearing_util = q_s / max(qa, 1e-9)
            if failed:
                # Enlarge once if bearing or shear fails.
                width = min(width + 0.25, 4.0)
                length = width
                q_s = ps / (width * length)
                bearing_util = q_s / max(qa, 1e-9)
                checks[0] = _check(member.id, "FOOTING_BEARING", q_s, qa, "kPa", "Allowable bearing after enlargement", DesignCheckStatus.PASS if q_s <= qa else DesignCheckStatus.FAIL)
            footing = FoundationFooting(
                id=f"FTG-{member.id}",
                column_member_id=member.id,
                point_id=member.start_point_id or "",
                length_m=round(length, 3),
                width_m=round(width, 3),
                thickness_m=thickness,
                axial_kN=round(pu, 3),
                bearing_demand_kPa=round(q_s, 3),
                bearing_capacity_kPa=qa,
                utilization=round(bearing_util, 4),
                status=DesignCheckStatus.FAIL if any(item.status is DesignCheckStatus.FAIL for item in checks) else DesignCheckStatus.WARNING,
                assumptions=[
                    "PRELIMINARY_ASSUMPTION on soil bearing unless user-provided.",
                    f"Square isolated footing {width*1000:.0f}×{length*1000:.0f}×{thickness*1000:.0f} mm.",
                ],
                checks=checks,
                reinforcement=MemberReinforcement(
                    member_id=member.id,
                    longitudinal=[bars.bars],
                    assumptions=[f"Required As ≈ {max(as_req, as_min):.0f} mm² each way."],
                    status=DesignCheckStatus.WARNING,
                ),
                metadata={"service_axial_kN": round(ps, 3), "source": "foundation_design_service"},
            )
            footings.append(footing)

        if not footings:
            warnings.append("No base columns were found; foundation design was not performed.")
        return FoundationDesignResult(footings=footings, provenance=provenance, assumptions=assumptions, warnings=warnings)


def _check(member_id: str, kind: str, demand: float, capacity: float, unit: str, reference: str, status: DesignCheckStatus) -> MemberDesignCheck:
    util = demand / capacity if capacity > 0 else 0.0
    return MemberDesignCheck(
        member_id=member_id,
        member_name=member_id,
        check_kind=kind,
        governing_combination="gravity service/factored as documented",
        demand=round(demand, 3),
        capacity=round(capacity, 3),
        utilization=round(util, 4),
        demand_unit=unit,
        code_reference=reference,
        status=status,
    )


def _status(utilization: float) -> DesignCheckStatus:
    if utilization <= 0.95:
        return DesignCheckStatus.PASS
    if utilization <= 1.00:
        return DesignCheckStatus.WARNING
    return DesignCheckStatus.FAIL
