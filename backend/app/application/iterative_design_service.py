"""Resize failing RC members and re-run analysis/design until they pass or the budget is spent."""

from __future__ import annotations

from dataclasses import dataclass, field

from app.application.building_analysis_service import BuildingAnalysisResult, BuildingAnalysisService
from app.application.preliminary_design_service import PreliminaryDesignResult, PreliminaryDesignService
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import BeamSection, ColumnSection, DesignCheckStatus, MemberType


@dataclass
class IterationRecord:
    iteration: int
    resized_member_ids: list[str]
    failed_member_ids: list[str]
    governing_utilization: float
    notes: list[str]


@dataclass
class IterativeDesignResult:
    pem: ProjectEngineeringModel
    analysis: BuildingAnalysisResult
    design: PreliminaryDesignResult
    iterations: list[IterationRecord] = field(default_factory=list)
    converged: bool = False


class IterativeDesignService:
    def __init__(
        self,
        *,
        analysis: BuildingAnalysisService,
        design: PreliminaryDesignService,
        max_iterations: int = 5,
        beam_depth_step_m: float = 0.05,
        column_step_m: float = 0.05,
        max_beam_depth_m: float = 0.90,
        max_column_size_m: float = 0.80,
    ) -> None:
        self._analysis = analysis
        self._design = design
        self._max_iterations = max_iterations
        self._beam_step = beam_depth_step_m
        self._column_step = column_step_m
        self._max_beam = max_beam_depth_m
        self._max_column = max_column_size_m

    def iterate(
        self,
        pem: ProjectEngineeringModel,
        analysis: BuildingAnalysisResult,
        design: PreliminaryDesignResult,
    ) -> IterativeDesignResult:
        records: list[IterationRecord] = []
        current_pem = pem
        current_analysis = analysis
        current_design = design

        for iteration in range(1, self._max_iterations + 1):
            failed = [
                check.member_id
                for check in current_design.checks
                if check.status is DesignCheckStatus.FAIL
            ]
            if not failed:
                notes = ["All implemented member checks passed; iteration stopped."]
                drift_fail = [
                    record.level_id
                    for record in current_pem.structural_model.story_drifts
                    if record.status is DesignCheckStatus.FAIL
                ]
                if drift_fail:
                    resized, notes = self._stiffen_columns(current_pem)
                    if resized:
                        current_analysis = self._analysis.analyze(current_pem)
                        current_design = self._design.design(current_pem, current_analysis)
                        records.append(
                            IterationRecord(
                                iteration=iteration,
                                resized_member_ids=resized,
                                failed_member_ids=current_design.failed_member_ids,
                                governing_utilization=current_design.governing_utilization,
                                notes=notes,
                            )
                        )
                        continue
                records.append(
                    IterationRecord(
                        iteration=iteration,
                        resized_member_ids=[],
                        failed_member_ids=[],
                        governing_utilization=current_design.governing_utilization,
                        notes=notes,
                    )
                )
                return IterativeDesignResult(
                    pem=current_pem,
                    analysis=current_analysis,
                    design=current_design,
                    iterations=records,
                    converged=True,
                )

            resized, notes = self._enlarge(current_pem, failed)
            if not resized:
                records.append(
                    IterationRecord(
                        iteration=iteration,
                        resized_member_ids=[],
                        failed_member_ids=failed,
                        governing_utilization=current_design.governing_utilization,
                        notes=notes or ["No further section increase is available."],
                    )
                )
                break

            current_analysis = self._analysis.analyze(current_pem)
            current_design = self._design.design(current_pem, current_analysis)
            records.append(
                IterationRecord(
                    iteration=iteration,
                    resized_member_ids=resized,
                    failed_member_ids=current_design.failed_member_ids,
                    governing_utilization=current_design.governing_utilization,
                    notes=notes,
                )
            )

        remaining_fail = any(check.status is DesignCheckStatus.FAIL for check in current_design.checks)
        return IterativeDesignResult(
            pem=current_pem,
            analysis=current_analysis,
            design=current_design,
            iterations=records,
            converged=not remaining_fail,
        )

    def _enlarge(
        self,
        pem: ProjectEngineeringModel,
        failed_member_ids: list[str],
    ) -> tuple[list[str], list[str]]:
        members = {member.id: member for member in pem.structural_model.members.members}
        beam_sections = {item.id: item for item in pem.structural_model.sections.beams}
        column_sections = {item.id: item for item in pem.structural_model.sections.columns}
        resized: list[str] = []
        notes: list[str] = []
        for member_id in failed_member_ids:
            member = members.get(member_id)
            if member is None:
                continue
            if member.member_type is MemberType.BEAM:
                section = beam_sections.get(member.section_id)
                if not isinstance(section, BeamSection):
                    continue
                new_depth = min(section.depth + self._beam_step, self._max_beam)
                if new_depth <= section.depth + 1e-9:
                    notes.append(f"{member.name}: beam depth already at maximum {self._max_beam:.2f} m.")
                    continue
                section.depth = round(new_depth, 3)
                section.name = f"B{section.width * 1000:.0f}x{section.depth * 1000:.0f}"
                resized.append(member_id)
                notes.append(f"{member.name}: beam depth increased to {section.depth * 1000:.0f} mm.")
            elif member.member_type is MemberType.COLUMN:
                section = column_sections.get(member.section_id)
                if not isinstance(section, ColumnSection):
                    continue
                new_w = min(section.width + self._column_step, self._max_column)
                new_d = min(section.depth + self._column_step, self._max_column)
                if new_w <= section.width + 1e-9 and new_d <= section.depth + 1e-9:
                    notes.append(f"{member.name}: column size already at maximum {self._max_column:.2f} m.")
                    continue
                section.width = round(new_w, 3)
                section.depth = round(new_d, 3)
                section.name = f"C{section.width * 1000:.0f}x{section.depth * 1000:.0f}"
                resized.append(member_id)
                notes.append(
                    f"{member.name}: column size increased to "
                    f"{section.width * 1000:.0f}x{section.depth * 1000:.0f} mm."
                )
        for footing in pem.structural_model.footings:
            if footing.status is DesignCheckStatus.FAIL and footing.column_member_id in failed_member_ids:
                footing.width_m = min(footing.width_m + 0.25, 4.0)
                footing.length_m = min(footing.length_m + 0.25, 4.0)
                resized.append(footing.id)
                notes.append(f"{footing.id}: footing plan increased to {footing.width_m:.2f}×{footing.length_m:.2f} m.")
        return resized, notes

    def _stiffen_columns(self, pem: ProjectEngineeringModel) -> tuple[list[str], list[str]]:
        resized: list[str] = []
        notes: list[str] = ["Drift limit exceeded; increasing all column sections to raise lateral stiffness."]
        for section in pem.structural_model.sections.columns:
            new_w = min(section.width + self._column_step, self._max_column)
            new_d = min(section.depth + self._column_step, self._max_column)
            if new_w <= section.width + 1e-9 and new_d <= section.depth + 1e-9:
                continue
            section.width = round(new_w, 3)
            section.depth = round(new_d, 3)
            section.name = f"C{section.width * 1000:.0f}x{section.depth * 1000:.0f}"
            resized.append(section.id)
            notes.append(f"{section.name}: column size increased for drift.")
        return resized, notes
