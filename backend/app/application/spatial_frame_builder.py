"""
Build a 3D space-frame analysis model from the shared PEM geometry.

Nodes, beams and columns keep the PEM point/member IDs so analysis, design and
drawings stay on one model. Slabs are not meshed as plate elements; their gravity
effect is applied as tributary beam UDLs by the analysis service.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.application.analysis.frame3d_solver import (
    RigidDiaphragm,
    SpaceElement,
    SpaceFrameModel,
    SpaceNode,
    SpaceSupport,
    torsion_constant_rectangle,
)
from app.domain.models.pem_structural import (
    AnalysisElementReference,
    AnalysisNodeReference,
    BeamSection,
    ColumnSection,
    DiaphragmDefinition,
    DiaphragmKind,
    MemberType,
    PointDefinition,
    StructuralModel,
    SupportType,
)


@dataclass
class ConnectivityIssue:
    severity: str  # HARD_CONFLICT | WARNING
    code: str
    message: str
    element_ids: list[str] = field(default_factory=list)


@dataclass
class SpatialFrameBuildResult:
    model: SpaceFrameModel
    diaphragms: list[DiaphragmDefinition]
    issues: list[ConnectivityIssue] = field(default_factory=list)
    assumptions: list[str] = field(default_factory=list)


class SpatialFrameBuilder:
    def build(self, structural: StructuralModel) -> SpatialFrameBuildResult:
        points = {point.id: point for point in structural.geometry.points}
        issues = self._validate_connectivity(structural, points)
        nodes = [
            SpaceNode(id=point.id, x=point.x, y=point.y, z=point.z, level_id=point.level_id)
            for point in structural.geometry.points
        ]
        sections = {
            **{item.id: item for item in structural.sections.beams},
            **{item.id: item for item in structural.sections.columns},
        }
        materials = {item.id: item for item in structural.materials.concrete}
        elements: list[SpaceElement] = []
        for member in structural.members.members:
            if member.member_type not in (MemberType.BEAM, MemberType.COLUMN):
                continue
            if member.start_point_id is None or member.end_point_id is None:
                issues.append(
                    ConnectivityIssue("HARD_CONFLICT", "MISSING_NODES", "Member is missing end points", [member.id])
                )
                continue
            if member.start_point_id not in points or member.end_point_id not in points:
                issues.append(
                    ConnectivityIssue("HARD_CONFLICT", "UNKNOWN_NODE", "Member references unknown points", [member.id])
                )
                continue
            section = sections.get(member.section_id)
            material = materials.get(member.material_id)
            if section is None or material is None:
                issues.append(
                    ConnectivityIssue("WARNING", "MISSING_SECTION", "Member has no section or material", [member.id])
                )
                continue
            width = float(getattr(section, "width", 0.3) or 0.3)
            depth = float(getattr(section, "depth", 0.5) or 0.5)
            elastic = float(material.modulus_of_elasticity or (4700.0 * math.sqrt(max(material.compressive_strength, 1.0))))
            elements.append(
                SpaceElement(
                    id=member.id,
                    start_node_id=member.start_point_id,
                    end_node_id=member.end_point_id,
                    elastic_modulus=elastic * 1000.0,  # MPa → kN/m²
                    area=width * depth,
                    iy=width * depth**3 / 12.0,
                    iz=depth * width**3 / 12.0,
                    j=torsion_constant_rectangle(width, depth),
                    poisson=float(material.poisson_ratio or 0.2),
                    member_id=member.id,
                    metadata={"role": member.member_type.value, "level_id": member.level_id},
                )
            )

        supports = []
        for support in structural.supports:
            pinned = support.support_type is SupportType.PINNED
            supports.append(
                SpaceSupport(
                    node_id=support.point_id,
                    restrain_ux=support.restraint_tx,
                    restrain_uy=support.restraint_ty,
                    restrain_uz=support.restraint_tz,
                    restrain_rx=False if pinned else support.restraint_rx,
                    restrain_ry=False if pinned else support.restraint_ry,
                    restrain_rz=False if pinned else support.restraint_rz,
                )
            )

        diaphragms, rigid = self._diaphragms(structural, points)
        model = SpaceFrameModel(
            id="PEM-SPACE-FRAME",
            nodes=nodes,
            elements=elements,
            supports=supports,
            diaphragms=rigid,
            metadata={"source": "spatial_frame_builder"},
        )
        self._sync_analysis_model(structural, nodes, elements)
        assumptions = [
            "3D space-frame model uses PEM points as nodes and beam/column members as 12-DOF elements.",
            "Slabs are not meshed; gravity is applied as tributary uniform loads on supporting beams.",
            "Elevated floors use a rigid diaphragm (ux, uy, rz condensed to a floor master).",
            "Semi-rigid and flexible diaphragms are not implemented.",
        ]
        return SpatialFrameBuildResult(
            model=model,
            diaphragms=diaphragms,
            issues=issues,
            assumptions=assumptions,
        )

    def _diaphragms(
        self,
        structural: StructuralModel,
        points: dict[str, PointDefinition],
    ) -> tuple[list[DiaphragmDefinition], list[RigidDiaphragm]]:
        levels = sorted(structural.geometry.levels, key=lambda item: item.elevation)
        if not levels:
            return [], []
        base_elevation = levels[0].elevation
        pem_diaphragms: list[DiaphragmDefinition] = []
        rigid: list[RigidDiaphragm] = []
        for level in levels:
            if abs(level.elevation - base_elevation) <= 1e-9:
                continue
            node_ids = [point.id for point in points.values() if point.level_id == level.id]
            if len(node_ids) < 3:
                continue
            xs = [points[nid].x for nid in node_ids]
            ys = [points[nid].y for nid in node_ids]
            cx = sum(xs) / len(xs)
            cy = sum(ys) / len(ys)
            definition = DiaphragmDefinition(
                id=f"DIA-{level.id}",
                level_id=level.id,
                kind=DiaphragmKind.RIGID,
                center_of_mass_x=round(cx, 4),
                center_of_mass_y=round(cy, 4),
                node_ids=node_ids,
                metadata={"kind_status": "IMPLEMENTED", "semi_rigid": "NOT_IMPLEMENTED"},
            )
            pem_diaphragms.append(definition)
            rigid.append(
                RigidDiaphragm(
                    id=definition.id,
                    level_id=level.id,
                    node_ids=tuple(node_ids),
                    master_x=cx,
                    master_y=cy,
                )
            )
        return pem_diaphragms, rigid

    @staticmethod
    def _sync_analysis_model(
        structural: StructuralModel,
        nodes: list[SpaceNode],
        elements: list[SpaceElement],
    ) -> None:
        structural.analysis_model.nodes = [AnalysisNodeReference(id=node.id, point_id=node.id) for node in nodes]
        structural.analysis_model.elements = [
            AnalysisElementReference(id=f"AE-{element.id}", member_id=element.member_id)
            for element in elements
        ]
        configuration = dict(structural.analysis_model.configuration or {})
        configuration["solver"] = "internal_direct_stiffness_3d"
        configuration["decomposition"] = "3D space frame with rigid floor diaphragms"
        structural.analysis_model.configuration = configuration
        structural.analysis_model.capability_status = "READY_FOR_ANALYSIS_ENGINE"

    def _validate_connectivity(
        self,
        structural: StructuralModel,
        points: dict[str, PointDefinition],
    ) -> list[ConnectivityIssue]:
        issues: list[ConnectivityIssue] = []
        incident: dict[str, int] = {point_id: 0 for point_id in points}
        columns_by_xy: dict[tuple[float, float], list[str]] = {}
        for member in structural.members.members:
            if member.start_point_id is None or member.end_point_id is None:
                continue
            start = points.get(member.start_point_id)
            end = points.get(member.end_point_id)
            if start is None or end is None:
                continue
            incident[start.id] = incident.get(start.id, 0) + 1
            incident[end.id] = incident.get(end.id, 0) + 1
            dx, dy, dz = end.x - start.x, end.y - start.y, end.z - start.z
            length = math.sqrt(dx * dx + dy * dy + dz * dz)
            if length <= 1e-9:
                issues.append(ConnectivityIssue("HARD_CONFLICT", "ZERO_LENGTH", "Zero-length member", [member.id]))
                continue
            if member.member_type is MemberType.COLUMN:
                horiz = math.sqrt(dx * dx + dy * dy)
                if horiz > 0.05:
                    issues.append(
                        ConnectivityIssue(
                            "WARNING",
                            "COLUMN_NOT_VERTICAL",
                            f"Column {member.id} is not vertical (Δxy={horiz:.3f} m).",
                            [member.id],
                        )
                    )
                key = (round(start.x, 3), round(start.y, 3))
                columns_by_xy.setdefault(key, []).append(member.id)
            elif member.member_type is MemberType.BEAM and abs(dz) > 0.05:
                issues.append(
                    ConnectivityIssue(
                        "WARNING",
                        "BEAM_NOT_LEVEL",
                        f"Beam {member.id} has Δz={dz:.3f} m.",
                        [member.id],
                    )
                )
        for point_id, count in incident.items():
            if count == 0:
                issues.append(
                    ConnectivityIssue("WARNING", "FREE_NODE", f"Point {point_id} is not connected to a frame element.", [point_id])
                )
        support_ids = {item.point_id for item in structural.supports}
        if not support_ids:
            issues.append(ConnectivityIssue("HARD_CONFLICT", "NO_SUPPORTS", "The model has no supports.", []))
        return issues
