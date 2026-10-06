"""Preliminary automated structural irregularity screens. Not a complete ASCE 7 §12.3 check."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.domain.models.pem_architecture import BuildingModel
from app.domain.models.pem_structural import (
    DesignCheckStatus,
    MemberDesignCheck,
    MemberType,
    StoryDriftRecord,
    StoryMass,
    StructuralModel,
)


@dataclass
class IrregularityQAResult:
    checks: list[MemberDesignCheck]
    assumptions: list[str]
    warnings: list[str]


class IrregularityQAService:
    def evaluate(
        self,
        building: BuildingModel,
        structural: StructuralModel,
        *,
        story_masses: list[StoryMass] | None = None,
        story_drifts: list[StoryDriftRecord] | None = None,
    ) -> IrregularityQAResult:
        checks: list[MemberDesignCheck] = []
        warnings = [
            "These screens are preliminary. They do not constitute complete ASCE 7-22 Table 12.3-1 / 12.3-2 compliance."
        ]
        assumptions = [
            "Soft-storey uses relative elastic drift ratios as a stiffness proxy when drift data exist.",
            "Weak-storey (strength) is NOT_CHECKED because storey strength is not computed.",
        ]
        masses = story_masses or structural.story_masses
        drifts = story_drifts or structural.story_drifts
        checks.append(self._mass_discontinuity(masses))
        checks.append(self._soft_story(drifts))
        checks.append(self._vertical_discontinuity(structural))
        checks.append(self._plan_irregularity(building))
        checks.append(self._torsional(drifts))
        checks.append(
            MemberDesignCheck(
                member_id="BUILDING",
                member_name="Weak storey",
                check_kind="IRREGULARITY_WEAK_STORY",
                governing_combination="N/A",
                demand=0.0,
                capacity=0.0,
                utilization=0.0,
                demand_unit="-",
                code_reference="ASCE 7-22 Table 12.3-2 Type 5 — NOT_CHECKED",
                assumptions=["Storey shear strength is not calculated in this version."],
                status=DesignCheckStatus.NOT_CHECKED,
            )
        )
        return IrregularityQAResult(checks=checks, assumptions=assumptions, warnings=warnings)

    @staticmethod
    def _mass_discontinuity(masses: list[StoryMass]) -> MemberDesignCheck:
        # Base/support levels have little or no slab mass; ASCE 12.3-2 Type 2 compares
        # adjacent *storeys* of the SFRS, not a foundation node row to the first floor.
        elevated = list(masses)
        if (
            len(elevated) >= 2
            and elevated[0].live_weight_kN <= 0.0
            and elevated[0].mass_kg < 0.4 * max(elevated[1].mass_kg, 1.0)
        ):
            elevated = elevated[1:]
        ratios = []
        for index in range(1, len(elevated)):
            below = elevated[index - 1].mass_kg or 1.0
            current = elevated[index].mass_kg
            if below > 0:
                ratios.append(current / below)
        worst = max(ratios) if ratios else 0.0
        status = DesignCheckStatus.NOT_CHECKED
        if ratios:
            status = DesignCheckStatus.FAIL if worst > 1.5 else DesignCheckStatus.PASS
        return MemberDesignCheck(
            member_id="BUILDING",
            member_name="Mass discontinuity",
            check_kind="IRREGULARITY_MASS",
            governing_combination="N/A",
            demand=round(worst, 3),
            capacity=1.5,
            utilization=round(worst / 1.5, 3) if worst else 0.0,
            demand_unit="mass ratio",
            code_reference="ASCE 7-22 Table 12.3-2 Type 2 (preliminary mass ratio, elevated storeys only)",
            assumptions=[
                "FAIL when an elevated storey mass exceeds 150% of the adjacent storey below.",
                "The foundation/base level is excluded because it is not a diaphragmed storey.",
            ],
            status=status,
        )

    @staticmethod
    def _soft_story(drifts: list[StoryDriftRecord]) -> MemberDesignCheck:
        if len(drifts) < 3:
            return MemberDesignCheck(
                member_id="BUILDING",
                member_name="Soft storey",
                check_kind="IRREGULARITY_SOFT_STORY",
                governing_combination="N/A",
                demand=0.0,
                capacity=0.7,
                utilization=0.0,
                demand_unit="stiffness ratio proxy",
                code_reference="ASCE 7-22 Table 12.3-2 Type 1a — NOT_CHECKED",
                assumptions=["Need at least two elevated storeys of drift data."],
                status=DesignCheckStatus.NOT_CHECKED,
            )
        stiffness_proxy = []
        comparable = drifts[1:]
        # Roof storeys typically have smaller elastic drift because ELF force and mass
        # drop at the top. Inverse-drift is then not a storey-stiffness comparison.
        if len(comparable) >= 2:
            comparable = comparable[:-1]
        if len(comparable) < 2:
            return MemberDesignCheck(
                member_id="BUILDING",
                member_name="Soft storey",
                check_kind="IRREGULARITY_SOFT_STORY",
                governing_combination="N/A",
                demand=0.0,
                capacity=0.7,
                utilization=0.0,
                demand_unit="stiffness ratio proxy",
                code_reference="ASCE 7-22 Table 12.3-2 Type 1a — NOT_CHECKED",
                assumptions=["Storey stiffness is not computed; roof-to-typical inverse-drift is not used as a FAIL."],
                status=DesignCheckStatus.NOT_CHECKED,
            )
        for record in comparable:
            ratio = max(record.drift_ratio_x, record.drift_ratio_y, 1e-9)
            stiffness_proxy.append(1.0 / ratio)
        worst = 1.0
        for index in range(len(stiffness_proxy) - 1):
            above = stiffness_proxy[index + 1]
            current = stiffness_proxy[index]
            if above > 0:
                worst = min(worst, current / above)
        status = DesignCheckStatus.FAIL if worst < 0.70 else DesignCheckStatus.WARNING if worst < 0.80 else DesignCheckStatus.PASS
        return MemberDesignCheck(
            member_id="BUILDING",
            member_name="Soft storey",
            check_kind="IRREGULARITY_SOFT_STORY",
            governing_combination="N/A",
            demand=round(worst, 3),
            capacity=0.70,
            utilization=round(0.70 / max(worst, 1e-9), 3),
            demand_unit="Ki/Ki+1 proxy",
            code_reference="ASCE 7-22 Table 12.3-2 Type 1a (drift-based stiffness proxy, roof storey excluded)",
            assumptions=[
                "Stiffness proxied as inverse of elastic drift ratio between elevated typical storeys.",
                "The roof is excluded: smaller roof drift is not evidence of a soft storey below.",
                "This is not a full storey-stiffness calculation.",
            ],
            status=status,
        )

    @staticmethod
    def _vertical_discontinuity(structural: StructuralModel) -> MemberDesignCheck:
        points = {point.id: point for point in structural.geometry.points}
        columns = [member for member in structural.members.members if member.member_type is MemberType.COLUMN]
        by_xy: dict[tuple[float, float], int] = {}
        for member in columns:
            start = points.get(member.start_point_id or "")
            if start is None:
                continue
            key = (round(start.x, 2), round(start.y, 2))
            by_xy[key] = by_xy.get(key, 0) + 1
        levels = max(len(structural.geometry.levels) - 1, 1)
        missing = sum(1 for count in by_xy.values() if count < levels)
        status = DesignCheckStatus.FAIL if missing else DesignCheckStatus.PASS
        return MemberDesignCheck(
            member_id="BUILDING",
            member_name="Vertical discontinuity",
            check_kind="IRREGULARITY_VERTICAL_DISCONTINUITY",
            governing_combination="N/A",
            demand=float(missing),
            capacity=0.0,
            utilization=float(missing),
            demand_unit="discontinuous column stacks",
            code_reference="ASCE 7-22 Table 12.3-2 Type 4 (column stack screen)",
            assumptions=["A column grid that does not continue through every storey is flagged."],
            status=status,
        )

    @staticmethod
    def _plan_irregularity(building: BuildingModel) -> MemberDesignCheck:
        site = building.site
        if site is None:
            return MemberDesignCheck(
                member_id="BUILDING",
                member_name="Plan irregularity",
                check_kind="IRREGULARITY_PLAN",
                governing_combination="N/A",
                demand=0.0,
                capacity=0.0,
                utilization=0.0,
                demand_unit="-",
                code_reference="ASCE 7-22 Table 12.3-1 — NOT_CHECKED",
                assumptions=["No site polygon."],
                status=DesignCheckStatus.NOT_CHECKED,
            )
        bounds = site.boundary.bounds
        width = bounds[2] - bounds[0]
        depth = bounds[3] - bounds[1]
        area = site.boundary.area
        rect = max(width * depth, 1e-6)
        fill = area / rect
        status = DesignCheckStatus.WARNING if fill < 0.8 else DesignCheckStatus.PASS
        return MemberDesignCheck(
            member_id="BUILDING",
            member_name="Plan irregularity",
            check_kind="IRREGULARITY_PLAN",
            governing_combination="N/A",
            demand=round(1.0 - fill, 3),
            capacity=0.2,
            utilization=round((1.0 - fill) / 0.2, 3),
            demand_unit="1 - area/bounding_rect",
            code_reference="ASCE 7-22 Table 12.3-1 (bounding-rectangle screen, not a full re-entrant-corner check)",
            assumptions=["Rectangular fill ratio is a proxy; re-entrant corners and diaphragm openings are not fully classified."],
            status=status,
        )

    @staticmethod
    def _torsional(drifts: list[StoryDriftRecord]) -> MemberDesignCheck:
        return MemberDesignCheck(
            member_id="BUILDING",
            member_name="Torsional irregularity",
            check_kind="IRREGULARITY_TORSION",
            governing_combination="N/A",
            demand=0.0,
            capacity=1.2,
            utilization=0.0,
            demand_unit="δmax/δavg",
            code_reference="ASCE 7-22 Table 12.3-1 Type 1a — NOT_CHECKED",
            assumptions=["δmax/δavg requires multiple points on a flexible diaphragm; rigid-diaphragm analysis reports a single floor displacement."],
            status=DesignCheckStatus.NOT_CHECKED,
        )
