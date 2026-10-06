"""Engineering QA for generated architecture, structure, analysis and design."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.building_analysis_service import BuildingAnalysisResult
from app.application.preliminary_design_service import PreliminaryDesignResult
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_architecture import BuildingModel, SpaceUsage
from app.domain.models.pem_structural import DesignCheckStatus, MemberType
from app.domain.models.validation import ValidationCategory, ValidationFinding, ValidationStatus


@dataclass
class BuildingQAResult:
    overall_status: str
    findings: list[ValidationFinding] = field(default_factory=list)
    geometry_ok: bool = True
    architecture_ok: bool = True
    structure_ok: bool = True
    analysis_ok: bool = True
    design_ok: bool = True

    @property
    def error_count(self) -> int:
        return sum(1 for item in self.findings if item.status is ValidationStatus.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for item in self.findings if item.status is ValidationStatus.WARNING)


class BuildingQAService:
    def validate(
        self,
        pem: ProjectEngineeringModel,
        *,
        analysis: BuildingAnalysisResult | None = None,
        design: PreliminaryDesignResult | None = None,
        overlaps: list[str] | None = None,
        placement_conflicts: list[str] | None = None,
    ) -> BuildingQAResult:
        findings: list[ValidationFinding] = []
        findings.extend(self._geometry(pem))
        findings.extend(self._architecture(pem.building_model, overlaps or []))
        findings.extend(self._structure(pem, placement_conflicts or []))
        if analysis is not None:
            findings.extend(self._analysis(analysis, pem))
        if design is not None:
            findings.extend(self._design(design))

        errors = [item for item in findings if item.status is ValidationStatus.ERROR]
        overall = "FAIL" if errors else "PASS" if findings else "PASS"
        if errors:
            overall = "FAIL"
        elif findings:
            overall = "WARNING"
        else:
            overall = "PASS"

        def _ok(category: ValidationCategory) -> bool:
            return not any(
                item.status is ValidationStatus.ERROR and item.category == category for item in findings
            )

        return BuildingQAResult(
            overall_status=overall,
            findings=findings,
            geometry_ok=_ok(ValidationCategory.INPUT),
            architecture_ok=_ok(ValidationCategory.ARCHITECTURE),
            structure_ok=_ok(ValidationCategory.STRUCTURAL),
            analysis_ok=_ok(ValidationCategory.ANALYSIS),
            design_ok=_ok(ValidationCategory.DESIGN),
        )

    def _geometry(self, pem: ProjectEngineeringModel) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        site = pem.building_model.site
        if site is None or site.boundary.area <= 0:
            findings.append(_error(ValidationCategory.INPUT, "SITE_MISSING", "Plot boundary is missing or has zero area."))
            return findings
        if site.frontage_m <= 0 or site.depth_m <= 0:
            findings.append(_error(ValidationCategory.INPUT, "SITE_DIMENSIONS", "Site frontage or depth is not positive."))
        if site.buildable_area_m2 <= 0:
            findings.append(_error(ValidationCategory.INPUT, "NO_BUILDABLE_AREA", "Setbacks consume the entire plot."))
        elevations = [plan.elevation_m for plan in pem.building_model.floor_plans]
        if elevations != sorted(elevations):
            findings.append(_error(ValidationCategory.INPUT, "LEVEL_ORDER", "Floor elevations are not monotonically increasing."))
        for plan in pem.building_model.floor_plans:
            if plan.boundary.area <= 0:
                findings.append(_error(ValidationCategory.INPUT, "FLOOR_AREA", f"{plan.name} has a non-positive footprint."))
            if plan.storey_height_m < 0:
                findings.append(_error(ValidationCategory.INPUT, "STOREY_HEIGHT", f"{plan.name} has a negative storey height."))
        return findings

    def _architecture(self, building: BuildingModel, overlaps: list[str]) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        cat = ValidationCategory.ARCHITECTURE
        if not building.is_populated:
            findings.append(_error(cat, "NO_LAYOUT", "No architectural layout has been generated."))
            return findings
        site = building.site
        assert site is not None
        buildable = site.buildable_boundary
        for plan in building.floor_plans:
            if not buildable.contains_polygon(plan.boundary):
                findings.append(
                    _warn(cat, "FOOTPRINT_OUTSIDE_PLOT", f"{plan.name} extends outside the buildable plot.")
                )
            for space in plan.spaces:
                if space.area_m2 <= 0:
                    findings.append(_error(cat, "SPACE_AREA", f"{space.name} has non-positive area."))
                if not plan.boundary.contains_polygon(space.boundary):
                    findings.append(
                        _error(cat, "SPACE_OUTSIDE_FLOOR", f"{space.name} is not inside {plan.name}.")
                    )
            door_spaces = {space_id for door in plan.doors for space_id in door.connects_space_ids}
            usable = [
                space
                for space in plan.spaces
                if space.usage
                not in (SpaceUsage.SHAFT, SpaceUsage.ROOF, SpaceUsage.DRIVE_AISLE, SpaceUsage.CORRIDOR)
            ]
            for space in usable:
                if space.id not in door_spaces and space.usage not in (SpaceUsage.STAIR, SpaceUsage.ELEVATOR):
                    findings.append(
                        _warn(cat, "SPACE_WITHOUT_DOOR", f"{space.name} has no door to circulation.")
                    )
            for slot in plan.parking_spaces:
                if not plan.boundary.contains_polygon(slot.boundary):
                    findings.append(
                        _error(cat, "PARKING_OUTSIDE", f"{slot.label} is not inside the parking floor.")
                    )
        if not building.stairs:
            findings.append(_error(cat, "NO_STAIR", "No stair connects the generated levels."))
        else:
            stair = building.stairs[0]
            if len(stair.served_level_ids) < 2:
                findings.append(_warn(cat, "STAIR_LEVELS", "Stair serves fewer than two levels."))
        for overlap in overlaps:
            findings.append(_error(cat, "SPACE_OVERLAP", overlap))
        return findings

    def _structure(
        self,
        pem: ProjectEngineeringModel,
        placement_conflicts: list[str],
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        cat = ValidationCategory.STRUCTURAL
        structural = pem.structural_model
        points = {point.id: point for point in structural.geometry.points}
        if not structural.members.members:
            findings.append(_error(cat, "NO_MEMBERS", "No structural members were generated."))
            return findings
        if not structural.supports:
            findings.append(_error(cat, "NO_SUPPORTS", "No supports are defined."))
        if not structural.load_cases:
            findings.append(_error(cat, "NO_LOADS", "No load cases are defined."))
        if not structural.load_combinations:
            findings.append(_error(cat, "NO_COMBINATIONS", "No load combinations are defined."))
        for member in structural.members.members:
            if member.member_type in (MemberType.BEAM, MemberType.COLUMN):
                if not member.start_point_id or not member.end_point_id:
                    findings.append(_error(cat, "MEMBER_ENDPOINTS", f"{member.name} is missing endpoints."))
                elif member.start_point_id not in points or member.end_point_id not in points:
                    findings.append(_error(cat, "ORPHAN_MEMBER", f"{member.name} references unknown points."))
            if member.member_type is MemberType.SLAB and not member.area_id:
                findings.append(_error(cat, "SLAB_BOUNDARY", f"{member.name} has no slab boundary."))
            if member.member_type is MemberType.COLUMN and member.level_id is None:
                findings.append(_warn(cat, "COLUMN_LEVEL", f"{member.name} has no storey assignment."))
        for conflict in placement_conflicts:
            findings.append(_warn(cat, "PLACEMENT_CONFLICT", conflict))
        return findings

    def _analysis(
        self,
        analysis: BuildingAnalysisResult,
        pem: ProjectEngineeringModel,
    ) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        cat = ValidationCategory.ANALYSIS
        if analysis.status != "SUCCESS":
            findings.append(_error(cat, "SOLVER_FAILED", analysis.message))
            return findings
        if not pem.structural_model.supports:
            findings.append(_error(cat, "UNRESTRAINED", "Analysis ran without supports."))
        if analysis.max_abs_displacement_m > 0.05:
            findings.append(
                _warn(
                    cat,
                    "LARGE_DISPLACEMENT",
                    f"Peak |displacement| {analysis.max_abs_displacement_m * 1000:.1f} mm exceeds 50 mm "
                    "serviceability screen (not a code drift check).",
                )
            )
        if not analysis.member_demands:
            findings.append(_error(cat, "NO_DEMANDS", "Solver produced no member demands."))
        return findings

    def _design(self, design: PreliminaryDesignResult) -> list[ValidationFinding]:
        findings: list[ValidationFinding] = []
        cat = ValidationCategory.DESIGN
        if not design.checks:
            findings.append(_error(cat, "NO_CHECKS", "No member design checks were produced."))
            return findings
        for check in design.checks:
            if check.status is DesignCheckStatus.FAIL:
                findings.append(
                    _error(
                        cat,
                        "MEMBER_FAIL",
                        f"{check.member_name} {check.check_kind} utilisation {check.utilization:.2f} "
                        f"on {check.governing_combination}.",
                    )
                )
            elif check.status is DesignCheckStatus.NOT_CHECKED:
                findings.append(
                    _warn(cat, "NOT_CHECKED", f"{check.member_name}: {check.check_kind} is NOT_CHECKED.")
                )
        return findings


def _error(category: ValidationCategory, code: str, message: str) -> ValidationFinding:
    return ValidationFinding(
        category=category,
        status=ValidationStatus.ERROR,
        code=code,
        message=message,
    )


def _warn(category: ValidationCategory, code: str, message: str) -> ValidationFinding:
    return ValidationFinding(
        category=category,
        status=ValidationStatus.WARNING,
        code=code,
        message=message,
    )
