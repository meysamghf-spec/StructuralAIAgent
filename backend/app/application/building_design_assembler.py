"""
In-memory building design assembler.

Turns a natural-language brief into a fully populated PEM (architecture, structure,
loads, combinations, analysis, preliminary design, QA) without touching the database.
The persistence/orchestration wrapper is :class:`BuildingDesignPipeline`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from app.application.building_analysis_service import BuildingAnalysisResult, BuildingAnalysisService
from app.application.building_brief_parser import BuildingBriefParser
from app.application.building_layout_generator import BuildingLayoutGenerator, BuildingLayoutResult
from app.application.building_qa_service import BuildingQAResult, BuildingQAService
from app.application.code_engine_service import CodeEngineService
from app.application.iterative_design_service import IterativeDesignResult, IterativeDesignService
from app.application.load_combination_engine import LoadCombinationEngine
from app.application.load_generation_service import LoadGenerationService
from app.application.preliminary_design_service import PreliminaryDesignResult, PreliminaryDesignService
from app.application.structural_layout_generator import (
    GridAxis,
    StructuralLayoutGenerator,
    StructuralLayoutResult,
)
from app.domain.models.building_brief import BuildingBrief
from app.domain.models.pem import (
    ProjectEngineeringModel,
    UnitConfiguration,
    UnitConfigurationStatus,
    UnitSystem,
    create_initial_pem,
)
from app.domain.models.pem_architecture import FloorType


@dataclass
class AssembledBuilding:
    brief: BuildingBrief
    pem: ProjectEngineeringModel
    layout: BuildingLayoutResult
    structure: StructuralLayoutResult
    analysis: BuildingAnalysisResult
    design: PreliminaryDesignResult
    qa: BuildingQAResult
    iteration: IterativeDesignResult | None
    missing_inputs: list[str] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    door_adjustments: list[str] = field(default_factory=list)
    status: str = "GENERATED"


class BuildingDesignAssembler:
    def __init__(
        self,
        *,
        code_engine: CodeEngineService,
        parser: BuildingBriefParser | None = None,
        layout: BuildingLayoutGenerator | None = None,
        structure: StructuralLayoutGenerator | None = None,
        loads: LoadGenerationService | None = None,
        combinations: LoadCombinationEngine | None = None,
        analysis: BuildingAnalysisService | None = None,
        design: PreliminaryDesignService | None = None,
        qa: BuildingQAService | None = None,
        iteration: IterativeDesignService | None = None,
    ) -> None:
        self._parser = parser or BuildingBriefParser()
        self._layout = layout or BuildingLayoutGenerator()
        self._structure = structure or StructuralLayoutGenerator()
        self._loads = loads or LoadGenerationService()
        self._combinations = combinations or LoadCombinationEngine()
        self._analysis = analysis or BuildingAnalysisService()
        self._design = design or PreliminaryDesignService(code_engine=code_engine)
        self._qa = qa or BuildingQAService()
        self._iteration = iteration or IterativeDesignService(
            analysis=self._analysis,
            design=self._design,
        )

    def assemble_from_text(
        self,
        text: str,
        *,
        project_id: UUID | None = None,
        project_name: str = "Generated building",
        max_iterations: int = 5,
    ) -> AssembledBuilding:
        brief = self._parser.parse(text)
        return self.assemble(
            brief,
            project_id=project_id,
            project_name=project_name,
            max_iterations=max_iterations,
        )

    def assemble(
        self,
        brief: BuildingBrief,
        *,
        project_id: UUID | None = None,
        project_name: str = "Generated building",
        max_iterations: int = 5,
    ) -> AssembledBuilding:
        missing = brief.missing_critical_inputs()
        if missing:
            empty = create_initial_pem(project_id or UUID(int=0), project_name)
            return AssembledBuilding(
                brief=brief,
                pem=empty,
                layout=BuildingLayoutResult(building_model=empty.building_model),
                structure=StructuralLayoutResult(
                    structural_model=empty.structural_model,
                    grid_x=GridAxis(ordinates=[], labels=[]),
                    grid_y=GridAxis(ordinates=[], labels=[]),
                ),
                analysis=BuildingAnalysisResult(status="WAITING_FOR_INPUT", message="Missing critical inputs."),
                design=PreliminaryDesignResult(),
                qa=BuildingQAResult(overall_status="FAIL"),
                iteration=None,
                missing_inputs=missing,
                status="WAITING_FOR_INPUT",
            )

        layout = self._layout.generate(brief)
        structure = self._structure.generate(layout.building_model)
        door_adjustments = self._structure.coordinate_doors(
            layout.building_model, structure.grid_x, structure.grid_y
        )
        loads = self._loads.generate(layout.building_model, structure.structural_model)
        structure.structural_model.load_cases = loads.load_cases
        structure.structural_model.story_forces = loads.story_forces
        structure.structural_model.story_masses = loads.story_masses
        structure.structural_model.input_provenance = loads.provenance
        combos = self._combinations.generate(loads.load_cases)
        structure.structural_model.load_combinations = combos.combinations
        structure.structural_model.analysis_model.load_case_ids = [case.id for case in loads.load_cases]
        structure.structural_model.analysis_model.load_combination_ids = [item.id for item in combos.combinations]

        pem = create_initial_pem(project_id or UUID(int=0), project_name, brief.raw_text[:200] or None)
        pem.unit_configuration = UnitConfiguration(
            system=UnitSystem.SI_METRIC,
            length_unit="m",
            force_unit="kN",
            moment_unit="kN·m",
            stress_unit="MPa",
            area_unit="m2",
            volume_unit="m3",
            status=UnitConfigurationStatus.USER_CONFIRMED,
        )
        pem.building_model = layout.building_model
        pem.structural_model = structure.structural_model
        pem.requirements = {
            "brief": brief.model_dump(mode="json"),
            "source": "building_brief_parser",
            "input_provenance": [item.model_dump(mode="json") for item in loads.provenance],
        }
        pem.architecture = {
            "floor_count": layout.building_model.floor_count,
            "generated_by": layout.building_model.generated_by,
        }
        pem.structural_system = {"system": layout.building_model.structural_system.value}

        analysis = self._analysis.analyze(pem)
        design = self._design.design(pem, analysis)
        iteration = None
        if design.failed_member_ids and max_iterations > 0:
            self._iteration._max_iterations = max_iterations  # noqa: SLF001
            iteration = self._iteration.iterate(pem, analysis, design)
            pem = iteration.pem
            analysis = iteration.analysis
            design = iteration.design

        from app.application.coordination_service import CoordinationService
        from app.application.engineering_report_service import EngineeringReportService
        from app.application.foundation_design_service import FoundationDesignService
        from app.application.irregularity_qa_service import IrregularityQAService

        foundation = FoundationDesignService().design(pem, analysis)
        pem.structural_model.footings = foundation.footings
        pem.structural_model.input_provenance.extend(foundation.provenance)
        irregularity = IrregularityQAService().evaluate(
            pem.building_model,
            pem.structural_model,
            story_masses=pem.structural_model.story_masses,
            story_drifts=pem.structural_model.story_drifts,
        )
        pem.structural_model.irregularity_checks = irregularity.checks
        coordination = CoordinationService().check(pem.building_model, pem.structural_model)

        pem.structural_model.design_checks = design.checks + irregularity.checks
        pem.structural_model.reinforcement = design.reinforcement
        pem.design_results = [check.model_dump(mode="json") for check in pem.structural_model.design_checks]
        cfg = dict(pem.structural_model.analysis_model.configuration)
        lifecycle = "GENERATED"
        if analysis.status == "SUCCESS":
            lifecycle = "ANALYZED"
        if design.checks:
            lifecycle = "DESIGNED"
        cfg.update(
            {
                "last_analysis_status": analysis.status,
                "last_analysis_message": analysis.message,
                "max_abs_displacement_m": analysis.max_abs_displacement_m,
                "member_demand_count": len(analysis.member_demands),
                "solver": analysis.solver,
            }
        )
        pem.structural_model.analysis_model.configuration = cfg
        pem.assumptions = (
            layout.assumptions
            + structure.assumptions
            + loads.assumptions
            + combos.assumptions
            + analysis.assumptions
            + design.assumptions
            + foundation.assumptions
            + irregularity.assumptions
        )
        pem.validation_results = []
        pem.code_compliance = {
            "ACI 318-25": "PARTIAL_IMPLEMENTATION",
            "ASCE 7-22": "PARTIAL_IMPLEMENTATION",
            "AISC 360-22": "PARTIAL_IMPLEMENTATION",
            "IBC 2024": "PARTIAL_IMPLEMENTATION",
        }
        pem.decisions = [
            {
                "kind": record.__class__.__name__,
                "iteration": record.iteration,
                "resized": record.resized_member_ids,
                "notes": record.notes,
            }
            for record in (iteration.iterations if iteration else [])
        ]

        qa = self._qa.validate(
            pem,
            analysis=analysis,
            design=design,
            overlaps=layout.overlaps,
            placement_conflicts=structure.placement_conflicts
            + [item.message for item in coordination.conflicts if item.severity == "HARD_CONFLICT"],
        )
        pem.validation_results = [finding.model_dump(mode="json") for finding in qa.findings]
        if qa.error_count > 0 or coordination.hard_count > 0:
            pem.lifecycle_status = "QA_FAILED"
        elif qa.overall_status in {"PASS", "WARNING"}:
            pem.lifecycle_status = "QA_PASSED"
        else:
            pem.lifecycle_status = lifecycle
        pem.engineering_report = EngineeringReportService().generate(pem, analysis=analysis, design=design)

        warnings = (
            layout.warnings
            + structure.warnings
            + loads.warnings
            + combos.warnings
            + analysis.warnings
            + design.warnings
            + foundation.warnings
            + irregularity.warnings
            + door_adjustments
            + [item.message for item in coordination.conflicts]
        )
        status = "GENERATED" if qa.overall_status != "FAIL" else "GENERATED_WITH_ERRORS"
        return AssembledBuilding(
            brief=brief,
            pem=pem,
            layout=layout,
            structure=structure,
            analysis=analysis,
            design=design,
            qa=qa,
            iteration=iteration,
            missing_inputs=[],
            assumptions=list(pem.assumptions) if isinstance(pem.assumptions, list) else [],
            warnings=warnings,
            door_adjustments=door_adjustments,
            status=status,
        )


def typical_residential_floor(assembled: AssembledBuilding):
    for plan in assembled.pem.building_model.floor_plans:
        if plan.floor_type is FloorType.RESIDENTIAL:
            return plan
    return None
