"""
Build planar frames from a generated PEM and solve them with the in-repo stiffness engine.

A 3D building is decomposed into orthogonal 2D frames along each grid line. Gravity
UDLs on beams come from tributary slab area × combination intensity, plus beam
self-weight. Column axial load is recovered from the solved frames, not invented.

This is linear-static gravity analysis. Wind/seismic cases are stored on the PEM
but are not applied to the frames — their fidelity is PRELIMINARY_NOT_CODE.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.application.analysis.frame_solver import (
    FrameAnalysisResult,
    FrameElement,
    FrameNode,
    FrameSolverError,
    NodalLoad,
    PlanarFrameModel,
    SupportRestraint,
    solve_planar_frame,
)
from app.application.load_combination_engine import LoadCombinationEngine
from app.domain.models.pem import ProjectEngineeringModel
from app.domain.models.pem_structural import (
    BeamSection,
    ColumnSection,
    LoadCase,
    LoadCategory,
    LoadCombination,
    MemberType,
    PointDefinition,
    StructuralMember,
    StructuralModel,
)


@dataclass
class MemberDemand:
    member_id: str
    member_type: str
    axial_kN: float = 0.0
    shear_kN: float = 0.0
    moment_kN_m: float = 0.0
    moment_y_kNm: float = 0.0
    moment_z_kNm: float = 0.0
    combination_id: str = ""
    combination_name: str = ""
    source_frames: list[str] = field(default_factory=list)


@dataclass
class BuildingAnalysisResult:
    status: str
    message: str
    frame_results: dict[str, FrameAnalysisResult] = field(default_factory=dict)
    member_demands: dict[str, MemberDemand] = field(default_factory=dict)
    engineering_results: dict[str, Any] = field(default_factory=dict)
    reactions_kN: dict[str, float] = field(default_factory=dict)
    max_abs_displacement_m: float = 0.0
    assumptions: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    solver: str = "internal_direct_stiffness_2d"
    case_results: dict[str, Any] = field(default_factory=dict)
    connectivity_issues: list[str] = field(default_factory=list)
    lateral_case_id: str | None = None


class BuildingAnalysisService:
    def analyze(
        self,
        pem: ProjectEngineeringModel,
        *,
        combination: LoadCombination | None = None,
    ) -> BuildingAnalysisResult:
        solver = str((pem.structural_model.analysis_model.configuration or {}).get("solver", "")).strip().lower()
        if solver in {"internal_direct_stiffness_3d", "internal"}:
            node_count = len(pem.structural_model.geometry.points)
            if node_count > 280:
                result = self._analyze_2d(pem, combination=combination)
                result.warnings = list(result.warnings) + [
                    f"3D space-frame analysis was not run: the model has {node_count} nodes, "
                    "which exceeds the in-repository dense-solver limit (280). "
                    "Planar 2D frames were used instead. Use ETABS/SAP2000 for a full 3D solution."
                ]
                return result
            return self._analyze_3d(pem, combination=combination)
        return self._analyze_2d(pem, combination=combination)

    def _analyze_2d(
        self,
        pem: ProjectEngineeringModel,
        *,
        combination: LoadCombination | None = None,
    ) -> BuildingAnalysisResult:
        structural = pem.structural_model
        combination = combination or LoadCombinationEngine.governing_gravity_combination(
            structural.load_combinations
        )
        if combination is None:
            return BuildingAnalysisResult(
                status="MODEL_NOT_READY",
                message="No load combination is available for gravity analysis.",
            )

        intensity_by_area = self._combined_area_intensities(structural, combination)
        frames = self._decompose_frames(structural, intensity_by_area)
        if not frames:
            return BuildingAnalysisResult(
                status="MODEL_NOT_READY",
                message="Could not assemble any planar frames from the structural model.",
            )

        frame_results: dict[str, FrameAnalysisResult] = {}
        warnings: list[str] = []
        try:
            for frame in frames:
                frame_results[frame.id] = solve_planar_frame(frame)
        except FrameSolverError as exc:
            return BuildingAnalysisResult(
                status="FAILED",
                message=str(exc),
                warnings=[str(exc)],
                frame_results=frame_results,
            )

        demands = self._collect_demands(structural, frame_results, combination)
        max_disp = max((result.max_abs_displacement for result in frame_results.values()), default=0.0)
        engineering_results = self._engineering_results(demands, frame_results, combination)
        reactions = self._support_reactions(structural, frame_results)

        assumptions = [
            "Analysis method: linear-elastic direct stiffness, planar frames along each grid line.",
            f"Governing combination for gravity design: {combination.name} ({combination.code_source}).",
            "Beam UDL = tributary slab intensity × tributary width + beam self-weight. "
            "Tributary width is half the adjacent slab span on each side.",
            "Units: metres, kN, kN·m. Concrete Ec = 4700√f'c MPa as stored on the material.",
            "P-delta, cracked stiffness, live-load reduction and 3D compatibility are not included.",
        ]
        warnings.append(
            "This is a preliminary 2D-frame gravity analysis. It is not a substitute for a "
            "3D model in ETABS/SAP2000 when those tools are required by the project."
        )
        if any(case.category in (LoadCategory.WIND, LoadCategory.SEISMIC) for case in structural.load_cases):
            warnings.append(
                "WIND and SEISMIC load cases exist on the model but were not applied to the "
                "planar 2D frames. Use the 3D solver for lateral analysis."
            )

        return BuildingAnalysisResult(
            status="SUCCESS",
            message=(
                f"Solved {len(frame_results)} planar frames under {combination.name}. "
                f"Peak |displacement| = {max_disp * 1000:.2f} mm."
            ),
            frame_results=frame_results,
            member_demands=demands,
            engineering_results=engineering_results,
            reactions_kN=reactions,
            max_abs_displacement_m=max_disp,
            assumptions=assumptions,
            warnings=warnings,
        )

    def _combined_area_intensities(
        self,
        structural: StructuralModel,
        combination: LoadCombination,
    ) -> dict[str, float]:
        cases = {case.id: case for case in structural.load_cases}
        intensities: dict[str, float] = {}
        for term in combination.terms:
            case = cases.get(term.load_case_id)
            if case is None or case.category in (LoadCategory.WIND, LoadCategory.SEISMIC):
                continue
            for load in case.loads:
                if load.area_id is None:
                    continue
                intensities[load.area_id] = intensities.get(load.area_id, 0.0) + term.factor * load.magnitude
        return intensities

    def _decompose_frames(
        self,
        structural: StructuralModel,
        intensity_by_area: dict[str, float],
    ) -> list[PlanarFrameModel]:
        points = {point.id: point for point in structural.geometry.points}
        grid = structural.geometry.grids[0].metadata if structural.geometry.grids else {}
        x_ordinates = [float(value) for value in grid.get("x_ordinates") or []]
        y_ordinates = [float(value) for value in grid.get("y_ordinates") or []]
        x_labels = [str(value) for value in grid.get("x_labels") or []]
        y_labels = [str(value) for value in grid.get("y_labels") or []]
        if not x_ordinates or not y_ordinates:
            return []

        members_by_id = {member.id: member for member in structural.members.members}
        sections = {
            **{section.id: section for section in structural.sections.beams},
            **{section.id: section for section in structural.sections.columns},
        }
        materials = {material.id: material for material in structural.materials.concrete}
        support_points = {support.point_id: support for support in structural.supports}

        frames: list[PlanarFrameModel] = []
        # Frames in the XZ plane: constant y (grid line 1, 2, ...)
        for y_index, y_value in enumerate(y_ordinates):
            label = y_labels[y_index] if y_index < len(y_labels) else str(y_index + 1)
            tributary = _tributary(y_ordinates, y_index)
            frames.append(
                self._frame_along_x(
                    frame_id=f"FR-Y{label}",
                    y_value=y_value,
                    tributary_m=tributary,
                    points=points,
                    members_by_id=members_by_id,
                    sections=sections,
                    materials=materials,
                    support_points=support_points,
                    intensity_by_area=intensity_by_area,
                    structural=structural,
                )
            )
        # Frames in the YZ plane: constant x (grid line A, B, ...)
        for x_index, x_value in enumerate(x_ordinates):
            label = x_labels[x_index] if x_index < len(x_labels) else _letter(x_index)
            tributary = _tributary(x_ordinates, x_index)
            frames.append(
                self._frame_along_y(
                    frame_id=f"FR-X{label}",
                    x_value=x_value,
                    tributary_m=tributary,
                    points=points,
                    members_by_id=members_by_id,
                    sections=sections,
                    materials=materials,
                    support_points=support_points,
                    intensity_by_area=intensity_by_area,
                    structural=structural,
                )
            )
        return [frame for frame in frames if frame.elements]

    def _frame_along_x(
        self,
        *,
        frame_id: str,
        y_value: float,
        tributary_m: float,
        points: dict[str, PointDefinition],
        members_by_id: dict[str, StructuralMember],
        sections: dict[str, BeamSection | ColumnSection],
        materials: dict,
        support_points: dict,
        intensity_by_area: dict[str, float],
        structural: StructuralModel,
    ) -> PlanarFrameModel:
        def on_line(point: PointDefinition) -> bool:
            return abs(point.y - y_value) <= 1e-6

        return self._assemble_frame(
            frame_id=frame_id,
            planar_coord=lambda point: (point.x, point.z),
            on_line=on_line,
            beam_direction="X",
            tributary_m=tributary_m,
            points=points,
            members_by_id=members_by_id,
            sections=sections,
            materials=materials,
            support_points=support_points,
            intensity_by_area=intensity_by_area,
            structural=structural,
        )

    def _frame_along_y(
        self,
        *,
        frame_id: str,
        x_value: float,
        tributary_m: float,
        points: dict[str, PointDefinition],
        members_by_id: dict[str, StructuralMember],
        sections: dict[str, BeamSection | ColumnSection],
        materials: dict,
        support_points: dict,
        intensity_by_area: dict[str, float],
        structural: StructuralModel,
    ) -> PlanarFrameModel:
        def on_line(point: PointDefinition) -> bool:
            return abs(point.x - x_value) <= 1e-6

        return self._assemble_frame(
            frame_id=frame_id,
            planar_coord=lambda point: (point.y, point.z),
            on_line=on_line,
            beam_direction="Y",
            tributary_m=tributary_m,
            points=points,
            members_by_id=members_by_id,
            sections=sections,
            materials=materials,
            support_points=support_points,
            intensity_by_area=intensity_by_area,
            structural=structural,
        )

    def _assemble_frame(
        self,
        *,
        frame_id: str,
        planar_coord,
        on_line,
        beam_direction: str,
        tributary_m: float,
        points: dict[str, PointDefinition],
        members_by_id: dict[str, StructuralMember],
        sections: dict[str, BeamSection | ColumnSection],
        materials: dict,
        support_points: dict,
        intensity_by_area: dict[str, float],
        structural: StructuralModel,
    ) -> PlanarFrameModel:
        node_ids: set[str] = set()
        elements: list[FrameElement] = []
        for member in members_by_id.values():
            if member.start_point_id is None or member.end_point_id is None:
                continue
            start = points.get(member.start_point_id)
            end = points.get(member.end_point_id)
            if start is None or end is None:
                continue
            if not (on_line(start) and on_line(end)):
                continue
            if member.member_type is MemberType.BEAM and member.metadata.get("direction") != beam_direction:
                continue
            if member.member_type not in (MemberType.BEAM, MemberType.COLUMN):
                continue
            node_ids.add(start.id)
            node_ids.add(end.id)
            section = sections.get(member.section_id)
            material = materials.get(member.material_id)
            if section is None or material is None:
                continue
            width = float(getattr(section, "width", 0.3) or 0.3)
            depth = float(getattr(section, "depth", 0.5) or 0.5)
            area = width * depth
            inertia = width * depth**3 / 12.0
            elastic = float(material.modulus_of_elasticity or (4700.0 * math.sqrt(max(material.compressive_strength, 1.0))))
            # Ec is stored in MPa; convert to kN/m² (1 MPa = 1000 kN/m²).
            elastic_kn_m2 = elastic * 1000.0
            unit_weight = float(material.unit_weight or 25.0)
            self_weight_udl = unit_weight * area  # kN/m
            slab_udl = 0.0
            if member.member_type is MemberType.BEAM:
                slab_udl = self._beam_slab_udl(member, structural, intensity_by_area, tributary_m)
            udl = -(self_weight_udl + slab_udl)
            elements.append(
                FrameElement(
                    id=f"{frame_id}-{member.id}",
                    start_node_id=start.id,
                    end_node_id=end.id,
                    elastic_modulus=elastic_kn_m2,
                    area=area,
                    moment_of_inertia=inertia,
                    udl_global_x=0.0,
                    udl_global_z=udl,
                    member_id=member.id,
                    metadata={"role": member.member_type.value, "tributary_m": tributary_m},
                )
            )

        nodes = [
            FrameNode(id=point_id, x=planar_coord(points[point_id])[0], z=planar_coord(points[point_id])[1])
            for point_id in sorted(node_ids)
        ]
        supports = [
            SupportRestraint(
                node_id=point_id,
                restrain_ux=True,
                restrain_uz=True,
                restrain_ry=True,
            )
            for point_id in node_ids
            if point_id in support_points
        ]
        return PlanarFrameModel(
            id=frame_id,
            nodes=nodes,
            elements=elements,
            supports=supports,
            nodal_loads=[],
            metadata={"tributary_m": tributary_m, "beam_direction": beam_direction},
        )

    @staticmethod
    def _beam_slab_udl(
        member: StructuralMember,
        structural: StructuralModel,
        intensity_by_area: dict[str, float],
        tributary_m: float,
    ) -> float:
        """kN/m on the beam from slabs that share this span."""
        span = float(member.metadata.get("span_m") or 0.0)
        if span <= 0:
            return 0.0
        # Average intensity of slabs on this level.
        intensities: list[float] = []
        for slab in structural.members.members:
            if slab.member_type is not MemberType.SLAB:
                continue
            if slab.level_id != member.level_id:
                continue
            if slab.area_id and slab.area_id in intensity_by_area:
                intensities.append(intensity_by_area[slab.area_id])
        if not intensities:
            return 0.0
        return (sum(intensities) / len(intensities)) * tributary_m

    def _collect_demands(
        self,
        structural: StructuralModel,
        frame_results: dict[str, FrameAnalysisResult],
        combination: LoadCombination,
    ) -> dict[str, MemberDemand]:
        demands: dict[str, MemberDemand] = {}
        members = {member.id: member for member in structural.members.members}
        for frame_id, result in frame_results.items():
            for forces in result.member_forces.values():
                member_id = forces.member_id
                if not member_id or member_id not in members:
                    continue
                member = members[member_id]
                current = demands.get(member_id)
                if current is None:
                    current = MemberDemand(
                        member_id=member_id,
                        member_type=member.member_type.value,
                        combination_id=combination.id,
                        combination_name=combination.name,
                    )
                    demands[member_id] = current
                current.axial_kN = max(current.axial_kN, forces.max_abs_axial)
                current.shear_kN = max(current.shear_kN, forces.max_abs_shear)
                current.moment_kN_m = max(current.moment_kN_m, forces.max_abs_moment)
                if frame_id not in current.source_frames:
                    current.source_frames.append(frame_id)
        return demands

    @staticmethod
    def _engineering_results(
        demands: dict[str, MemberDemand],
        frame_results: dict[str, FrameAnalysisResult],
        combination: LoadCombination,
    ) -> dict[str, Any]:
        frame_forces = []
        for demand in demands.values():
            frame_forces.append(
                {
                    "id": demand.member_id,
                    "source_identifier": demand.member_id,
                    "member_type": demand.member_type,
                    "axial_force": demand.axial_kN,
                    "shear_v2": demand.shear_kN,
                    "moment_m3": demand.moment_kN_m,
                    "combination": demand.combination_name,
                }
            )
        return {
            "execution_mode": "internal_direct_stiffness_2d",
            "combination": {"id": combination.id, "name": combination.name},
            "frame_forces": frame_forces,
            "frame_count": len(frame_results),
            "member_count": len(demands),
        }

    @staticmethod
    def _support_reactions(
        structural: StructuralModel,
        frame_results: dict[str, FrameAnalysisResult],
    ) -> dict[str, float]:
        reactions: dict[str, float] = {}
        for result in frame_results.values():
            for node_id, (_fx, fz, _my) in result.reactions.items():
                reactions[node_id] = reactions.get(node_id, 0.0) + abs(fz)
        return reactions


    def _analyze_3d(
        self,
        pem: ProjectEngineeringModel,
        *,
        combination: LoadCombination | None = None,
    ) -> BuildingAnalysisResult:
        from app.application.analysis.frame3d_solver import (
            SpaceFrameSolverError,
            SpaceNodalLoad,
            assemble_space_system,
            build_space_load_vector,
            solve_prepared_space_frame,
        )
        from app.application.spatial_frame_builder import SpatialFrameBuilder
        from app.application.story_drift_service import StoryDriftService

        structural = pem.structural_model
        combination = combination or LoadCombinationEngine.governing_gravity_combination(
            structural.load_combinations
        )
        if combination is None:
            return BuildingAnalysisResult(
                status="MODEL_NOT_READY",
                message="No load combination is available for analysis.",
                solver="internal_direct_stiffness_3d",
            )
        built = SpatialFrameBuilder().build(structural)
        structural.diaphragms = built.diaphragms
        hard = [issue.message for issue in built.issues if issue.severity == "HARD_CONFLICT"]
        if hard:
            return BuildingAnalysisResult(
                status="FAILED",
                message="3D model failed connectivity validation.",
                warnings=hard,
                connectivity_issues=hard,
                solver="internal_direct_stiffness_3d",
            )
        try:
            prepared = assemble_space_system(built.model)
        except SpaceFrameSolverError as exc:
            return BuildingAnalysisResult(
                status=exc.status,
                message=str(exc),
                warnings=[str(exc)],
                solver="internal_direct_stiffness_3d",
                connectivity_issues=[issue.message for issue in built.issues],
            )

        case_results = {}
        for case in structural.load_cases:
            udls = self._case_beam_udls(structural, case)
            nodals = self._case_nodal_loads(structural, case)
            try:
                vector = build_space_load_vector(built.model, prepared, nodals, udls)
                case_results[case.id] = solve_prepared_space_frame(built.model, prepared, vector)
            except SpaceFrameSolverError as exc:
                return BuildingAnalysisResult(
                    status=exc.status,
                    message=f"{case.name}: {exc}",
                    warnings=[str(exc)],
                    solver="internal_direct_stiffness_3d",
                )

        combo_forces: dict[str, dict[str, float]] = {}
        combo_disp = 0.0
        reactions: dict[str, float] = {}
        for term in combination.terms:
            result = case_results.get(term.load_case_id)
            if result is None:
                continue
            combo_disp = max(combo_disp, result.max_abs_displacement * abs(term.factor))
            for node_id, residual in result.reactions.items():
                reactions[node_id] = reactions.get(node_id, 0.0) + abs(residual[2] * term.factor)
            for element_id, forces in result.member_forces.items():
                current = combo_forces.setdefault(
                    forces.member_id or element_id,
                    {"axial": 0.0, "shear": 0.0, "moment": 0.0, "my": 0.0, "mz": 0.0},
                )
                current["axial"] += abs(forces.max_abs_axial * term.factor)
                current["shear"] += abs(forces.max_abs_shear * term.factor)
                current["moment"] += abs(forces.max_abs_moment * term.factor)
                current["my"] += abs(forces.moment_y * term.factor)
                current["mz"] += abs(forces.moment_z * term.factor)

        # Envelope remaining combinations so lateral moments enter column design.
        for other in structural.load_combinations:
            if other.id == combination.id:
                continue
            envelope: dict[str, dict[str, float]] = {}
            for term in other.terms:
                result = case_results.get(term.load_case_id)
                if result is None:
                    continue
                for element_id, forces in result.member_forces.items():
                    mid = forces.member_id or element_id
                    bucket = envelope.setdefault(mid, {"axial": 0.0, "shear": 0.0, "moment": 0.0, "my": 0.0, "mz": 0.0})
                    bucket["axial"] += abs(forces.max_abs_axial * term.factor)
                    bucket["shear"] += abs(forces.max_abs_shear * term.factor)
                    bucket["moment"] += abs(forces.max_abs_moment * term.factor)
                    bucket["my"] += abs(forces.moment_y * term.factor)
                    bucket["mz"] += abs(forces.moment_z * term.factor)
            for mid, bucket in envelope.items():
                current = combo_forces.setdefault(mid, bucket)
                for key in ("axial", "shear", "moment", "my", "mz"):
                    current[key] = max(current[key], bucket[key])

        members = {member.id: member for member in structural.members.members}
        demands: dict[str, MemberDemand] = {}
        for member_id, bucket in combo_forces.items():
            member = members.get(member_id)
            if member is None:
                continue
            demands[member_id] = MemberDemand(
                member_id=member_id,
                member_type=member.member_type.value,
                axial_kN=bucket["axial"],
                shear_kN=bucket["shear"],
                moment_kN_m=bucket["moment"],
                moment_y_kNm=bucket["my"],
                moment_z_kNm=bucket["mz"],
                combination_id=combination.id,
                combination_name=combination.name,
                source_frames=["SPACE-FRAME"],
            )

        eq_case = next((case for case in structural.load_cases if case.name == "EQ_X+"), None)
        drift_result = None
        if eq_case is not None and eq_case.id in case_results:
            drift_result = StoryDriftService().evaluate(
                structural,
                case_results[eq_case.id],
                built.diaphragms,
                cd=4.5,
                ie=1.0,
                case_name=eq_case.name,
            )
            structural.story_drifts = drift_result.records

        gravity_result = case_results.get(combination.terms[0].load_case_id) if combination.terms else None
        max_disp = combo_disp
        if gravity_result is not None:
            max_disp = max(max_disp, gravity_result.max_abs_displacement)

        engineering_results = {
            "execution_mode": "internal_direct_stiffness_3d",
            "combination": {"id": combination.id, "name": combination.name},
            "frame_forces": [
                {
                    "id": demand.member_id,
                    "source_identifier": demand.member_id,
                    "member_type": demand.member_type,
                    "axial_force": demand.axial_kN,
                    "shear_v2": demand.shear_kN,
                    "moment_m3": demand.moment_kN_m,
                    "moment_m2": demand.moment_y_kNm,
                    "combination": demand.combination_name,
                }
                for demand in demands.values()
            ],
            "member_count": len(demands),
            "free_dof": next(iter(case_results.values())).free_dof_count if case_results else 0,
        }
        assumptions = list(built.assumptions)
        assumptions.append(
            f"Linear-elastic 3D direct stiffness. Governing gravity combination: {combination.name}."
        )
        assumptions.append("Load cases solved independently and superposed; P-delta is not included.")
        warnings = [issue.message for issue in built.issues]
        warnings.append(
            "Preliminary 3D linear-static analysis. Cracked stiffness, P-delta, accidental torsion "
            "and construction-stage effects are not included. ETABS/SAP2000 remain required for "
            "final documents."
        )
        if drift_result is not None:
            assumptions.extend(drift_result.assumptions)
            warnings.extend(drift_result.warnings)

        return BuildingAnalysisResult(
            status="SUCCESS",
            message=(
                f"Solved 3D space frame ({len(built.model.elements)} elements, "
                f"{len(case_results)} load cases). Peak |u| = {max_disp * 1000:.2f} mm."
            ),
            member_demands=demands,
            engineering_results=engineering_results,
            reactions_kN=reactions,
            max_abs_displacement_m=max_disp,
            assumptions=assumptions,
            warnings=warnings,
            solver="internal_direct_stiffness_3d",
            case_results=case_results,
            connectivity_issues=[issue.message for issue in built.issues],
            lateral_case_id=eq_case.id if eq_case else None,
        )

    def _case_beam_udls(self, structural: StructuralModel, case) -> dict[str, tuple[float, float, float]]:
        intensity_by_area: dict[str, float] = {}
        for load in case.loads:
            if load.area_id is None:
                continue
            intensity_by_area[load.area_id] = intensity_by_area.get(load.area_id, 0.0) + load.magnitude
        grid = structural.geometry.grids[0].metadata if structural.geometry.grids else {}
        x_ordinates = [float(value) for value in grid.get("x_ordinates") or []]
        y_ordinates = [float(value) for value in grid.get("y_ordinates") or []]
        points = {point.id: point for point in structural.geometry.points}
        sections = {
            **{section.id: section for section in structural.sections.beams},
            **{section.id: section for section in structural.sections.columns},
        }
        materials = {material.id: material for material in structural.materials.concrete}
        udls: dict[str, tuple[float, float, float]] = {}
        include_self_weight = case.category in (LoadCategory.DEAD,)
        for member in structural.members.members:
            if member.start_point_id is None or member.end_point_id is None:
                continue
            if member.member_type not in (MemberType.BEAM, MemberType.COLUMN):
                continue
            section = sections.get(member.section_id)
            material = materials.get(member.material_id)
            if section is None or material is None:
                continue
            width = float(getattr(section, "width", 0.3) or 0.3)
            depth = float(getattr(section, "depth", 0.5) or 0.5)
            unit_weight = float(material.unit_weight or 25.0)
            self_weight = unit_weight * width * depth if include_self_weight else 0.0
            slab_udl = 0.0
            if member.member_type is MemberType.BEAM:
                direction = str(member.metadata.get("direction") or "X")
                start = points.get(member.start_point_id)
                if start is not None and x_ordinates and y_ordinates:
                    if direction == "X":
                        index = min(range(len(y_ordinates)), key=lambda i: abs(y_ordinates[i] - start.y))
                        slab_udl = self._beam_slab_udl(member, structural, intensity_by_area, _tributary(y_ordinates, index))
                    else:
                        index = min(range(len(x_ordinates)), key=lambda i: abs(x_ordinates[i] - start.x))
                        slab_udl = self._beam_slab_udl(member, structural, intensity_by_area, _tributary(x_ordinates, index))
            udls[member.id] = (0.0, 0.0, -(self_weight + slab_udl))
        return udls

    @staticmethod
    def _case_nodal_loads(structural: StructuralModel, case) -> list:
        from app.application.analysis.frame3d_solver import SpaceNodalLoad

        forces_by_level: dict[str, tuple[float, float]] = {}
        for story in structural.story_forces:
            if story.case_id != case.id:
                continue
            forces_by_level[story.level_id] = (
                forces_by_level.get(story.level_id, (0.0, 0.0))[0] + story.fx_kN,
                forces_by_level.get(story.level_id, (0.0, 0.0))[1] + story.fy_kN,
            )
        if not forces_by_level:
            for load in case.loads:
                level_id = str((load.metadata or {}).get("level_id") or "")
                if not level_id:
                    continue
                fx = load.magnitude * load.direction_x
                fy = load.magnitude * load.direction_y
                current = forces_by_level.get(level_id, (0.0, 0.0))
                forces_by_level[level_id] = (current[0] + fx, current[1] + fy)
        nodals = []
        diaphragms = {item.level_id: item for item in structural.diaphragms}
        points = {point.id: point for point in structural.geometry.points}
        for level_id, (fx, fy) in forces_by_level.items():
            node_ids = []
            diaphragm = diaphragms.get(level_id)
            if diaphragm is not None:
                node_ids = list(diaphragm.node_ids)
            else:
                node_ids = [point.id for point in points.values() if point.level_id == level_id]
            if not node_ids:
                continue
            share_x, share_y = fx / len(node_ids), fy / len(node_ids)
            for node_id in node_ids:
                nodals.append(SpaceNodalLoad(node_id=node_id, fx=share_x, fy=share_y))
        return nodals


def _tributary(ordinates: list[float], index: int) -> float:
    width = 0.0
    if index > 0:
        width += 0.5 * (ordinates[index] - ordinates[index - 1])
    if index < len(ordinates) - 1:
        width += 0.5 * (ordinates[index + 1] - ordinates[index])
    return max(width, 0.5)


def _letter(index: int) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ"
    return alphabet[index] if index < len(alphabet) else str(index + 1)
