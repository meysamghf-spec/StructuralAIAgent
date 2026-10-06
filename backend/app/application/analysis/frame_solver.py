"""
Direct-stiffness solver for planar (2D) frames.

This is a real finite-element implementation, not a wrapper around an external
program: it assembles element stiffness matrices, transforms them to global
coordinates, applies boundary conditions, solves ``K u = F`` and recovers member
end forces and reactions.

Conventions
-----------
* Each node has three degrees of freedom: translation ``ux``, translation ``uz``
  (vertical, positive up) and rotation ``ry`` about the out-of-plane axis.
* ``DOF_PER_NODE`` is a module constant rather than a hard-coded ``3`` so a 3D
  element (6 DOF per node) can be added alongside this one without reworking the
  assembly, boundary-condition and recovery code.
* Element local ``x`` runs from the start node to the end node; local ``y`` is
  local ``x`` rotated +90 degrees in the plane.
* Distributed loads are given as a global-axis intensity so gravity is simply
  ``(0, -w)`` for both beams and columns; the solver resolves it into local axial
  and transverse components.

Units are whatever the caller supplies consistently. The building pipeline uses
metres, kilonewtons and kilopascals (kN/m^2), giving ``EA`` in kN and ``EI`` in
kN*m^2.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.application.analysis.linear_algebra import SingularMatrixError, solve_linear_system

DOF_PER_NODE = 3
_DOF_LABELS = ("ux", "uz", "ry")


class FrameSolverError(Exception):
    """Raised when a frame model cannot be solved."""

    def __init__(self, message: str, *, details: dict | None = None) -> None:
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True)
class FrameNode:
    id: str
    x: float
    z: float
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SupportRestraint:
    node_id: str
    restrain_ux: bool = True
    restrain_uz: bool = True
    restrain_ry: bool = False

    def flags(self) -> tuple[bool, bool, bool]:
        return (self.restrain_ux, self.restrain_uz, self.restrain_ry)


@dataclass(frozen=True)
class FrameElement:
    """
    A prismatic 2D beam-column.

    ``udl_global_x`` / ``udl_global_z`` are force per unit length along the global
    axes (gravity is a negative ``udl_global_z``).
    """

    id: str
    start_node_id: str
    end_node_id: str
    elastic_modulus: float
    area: float
    moment_of_inertia: float
    udl_global_x: float = 0.0
    udl_global_z: float = 0.0
    member_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class NodalLoad:
    node_id: str
    fx: float = 0.0
    fz: float = 0.0
    my: float = 0.0


@dataclass(frozen=True)
class PlanarFrameModel:
    id: str
    nodes: list[FrameNode]
    elements: list[FrameElement]
    supports: list[SupportRestraint]
    nodal_loads: list[NodalLoad] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MemberEndForces:
    """
    Member end forces in the element's local frame.

    ``axial_start`` is positive in local +x at the start node. ``moment_start`` and
    ``moment_end`` are the end moments. ``max_*`` values are recovered along the
    member from the end forces and the distributed load, so a mid-span sagging
    moment is captured even though only end values are solved for.
    """

    element_id: str
    member_id: str | None
    length: float
    axial_start: float
    shear_start: float
    moment_start: float
    axial_end: float
    shear_end: float
    moment_end: float
    max_abs_moment: float
    max_abs_moment_position: float
    max_abs_shear: float
    max_abs_axial: float

    @property
    def max_abs_moment_kn_m(self) -> float:
        return self.max_abs_moment


@dataclass(frozen=True)
class FrameAnalysisResult:
    model_id: str
    displacements: dict[str, tuple[float, float, float]]
    reactions: dict[str, tuple[float, float, float]]
    member_forces: dict[str, MemberEndForces]
    dof_count: int
    free_dof_count: int
    max_abs_displacement: float
    solver: str = "internal_direct_stiffness_2d"

    def member(self, element_id: str) -> MemberEndForces:
        return self.member_forces[element_id]


def solve_planar_frame(model: PlanarFrameModel) -> FrameAnalysisResult:
    """Assemble and solve a planar frame; raises :class:`FrameSolverError` on failure."""
    if not model.nodes:
        raise FrameSolverError("Frame model has no nodes", details={"model_id": model.id})
    if not model.elements:
        raise FrameSolverError("Frame model has no elements", details={"model_id": model.id})
    if not model.supports:
        raise FrameSolverError(
            "Frame model has no supports; the structure is unrestrained",
            details={"model_id": model.id},
        )

    node_index = {node.id: index for index, node in enumerate(model.nodes)}
    if len(node_index) != len(model.nodes):
        raise FrameSolverError("Frame model contains duplicate node ids", details={"model_id": model.id})

    dof_count = len(model.nodes) * DOF_PER_NODE
    stiffness = [[0.0] * dof_count for _ in range(dof_count)]
    load_vector = [0.0] * dof_count

    element_cache: dict[str, tuple[list[list[float]], list[float], list[int], float, float, float]] = {}

    for element in model.elements:
        start = _lookup_node(model, node_index, element.start_node_id, element.id)
        end = _lookup_node(model, node_index, element.end_node_id, element.id)
        dx = end.x - start.x
        dz = end.z - start.z
        length = math.hypot(dx, dz)
        if length <= 1e-9:
            raise FrameSolverError(
                f"Element {element.id} has zero length",
                details={"element_id": element.id},
            )
        cosine = dx / length
        sine = dz / length

        local_stiffness = _local_stiffness(
            elastic_modulus=element.elastic_modulus,
            area=element.area,
            moment_of_inertia=element.moment_of_inertia,
            length=length,
        )
        transform = _transformation(cosine, sine)
        global_stiffness = _triple_product(transform, local_stiffness)

        # Resolve the global distributed load into local axial / transverse parts.
        axial_intensity = element.udl_global_x * cosine + element.udl_global_z * sine
        transverse_intensity = -element.udl_global_x * sine + element.udl_global_z * cosine

        fixed_end_local = _fixed_end_forces(axial_intensity, transverse_intensity, length)
        # Equivalent nodal loads are the negative of the fixed-end forces, rotated
        # back into global coordinates.
        equivalent_local = [-value for value in fixed_end_local]
        equivalent_global = _transpose_multiply(transform, equivalent_local)

        dofs = _element_dofs(node_index[element.start_node_id], node_index[element.end_node_id])
        for local_row, global_row in enumerate(dofs):
            load_vector[global_row] += equivalent_global[local_row]
            for local_col, global_col in enumerate(dofs):
                stiffness[global_row][global_col] += global_stiffness[local_row][local_col]

        element_cache[element.id] = (
            local_stiffness,
            fixed_end_local,
            dofs,
            length,
            cosine,
            sine,
        )

    for load in model.nodal_loads:
        if load.node_id not in node_index:
            raise FrameSolverError(
                f"Nodal load references unknown node {load.node_id}",
                details={"node_id": load.node_id},
            )
        base = node_index[load.node_id] * DOF_PER_NODE
        load_vector[base] += load.fx
        load_vector[base + 1] += load.fz
        load_vector[base + 2] += load.my

    restrained: set[int] = set()
    for support in model.supports:
        if support.node_id not in node_index:
            raise FrameSolverError(
                f"Support references unknown node {support.node_id}",
                details={"node_id": support.node_id},
            )
        base = node_index[support.node_id] * DOF_PER_NODE
        for offset, is_restrained in enumerate(support.flags()):
            if is_restrained:
                restrained.add(base + offset)

    free_dofs = [index for index in range(dof_count) if index not in restrained]
    displacement_vector = [0.0] * dof_count

    # A fully restrained model is a legitimate case (for example a single
    # fixed-fixed span): displacements are zero and the member forces are the
    # fixed-end forces, so there is simply nothing to solve.
    if free_dofs:
        reduced_matrix = [[stiffness[row][column] for column in free_dofs] for row in free_dofs]
        reduced_rhs = [load_vector[row] for row in free_dofs]

        try:
            reduced_solution = solve_linear_system(reduced_matrix, reduced_rhs)
        except SingularMatrixError as exc:
            raise FrameSolverError(
                "The stiffness matrix is singular, which means the frame is unstable "
                "(a mechanism or a missing restraint).",
                details={"model_id": model.id, "degree_of_freedom": exc.pivot_row},
            ) from exc

        for position, dof in enumerate(free_dofs):
            displacement_vector[dof] = reduced_solution[position]

    displacements = {
        node.id: (
            displacement_vector[index * DOF_PER_NODE],
            displacement_vector[index * DOF_PER_NODE + 1],
            displacement_vector[index * DOF_PER_NODE + 2],
        )
        for node, index in ((node, node_index[node.id]) for node in model.nodes)
    }

    member_forces: dict[str, MemberEndForces] = {}
    internal_force_vector = [0.0] * dof_count
    for element in model.elements:
        local_stiffness, fixed_end_local, dofs, length, cosine, sine = element_cache[element.id]
        transform = _transformation(cosine, sine)
        global_displacements = [displacement_vector[dof] for dof in dofs]
        local_displacements = _multiply(transform, global_displacements)
        local_forces = [
            sum(local_stiffness[row][col] * local_displacements[col] for col in range(6))
            + fixed_end_local[row]
            for row in range(6)
        ]
        member_forces[element.id] = _recover_member_forces(
            element=element,
            local_forces=local_forces,
            length=length,
            transverse_intensity=(-element.udl_global_x * sine + element.udl_global_z * cosine),
        )
        global_forces = _transpose_multiply(transform, local_forces)
        for local_row, global_row in enumerate(dofs):
            internal_force_vector[global_row] += global_forces[local_row]

    reactions: dict[str, tuple[float, float, float]] = {}
    for support in model.supports:
        base = node_index[support.node_id] * DOF_PER_NODE
        applied = [0.0, 0.0, 0.0]
        for load in model.nodal_loads:
            if load.node_id == support.node_id:
                applied[0] += load.fx
                applied[1] += load.fz
                applied[2] += load.my
        reactions[support.node_id] = (
            internal_force_vector[base] - applied[0],
            internal_force_vector[base + 1] - applied[1],
            internal_force_vector[base + 2] - applied[2],
        )

    max_displacement = max((abs(value) for value in displacement_vector), default=0.0)
    return FrameAnalysisResult(
        model_id=model.id,
        displacements=displacements,
        reactions=reactions,
        member_forces=member_forces,
        dof_count=dof_count,
        free_dof_count=len(free_dofs),
        max_abs_displacement=max_displacement,
    )


# ---------------------------------------------------------------------------
# element mechanics
# ---------------------------------------------------------------------------


def _lookup_node(
    model: PlanarFrameModel,
    node_index: dict[str, int],
    node_id: str,
    element_id: str,
) -> FrameNode:
    if node_id not in node_index:
        raise FrameSolverError(
            f"Element {element_id} references unknown node {node_id}",
            details={"element_id": element_id, "node_id": node_id},
        )
    return model.nodes[node_index[node_id]]


def _element_dofs(start_index: int, end_index: int) -> list[int]:
    start_base = start_index * DOF_PER_NODE
    end_base = end_index * DOF_PER_NODE
    return [
        start_base,
        start_base + 1,
        start_base + 2,
        end_base,
        end_base + 1,
        end_base + 2,
    ]


def _local_stiffness(
    *,
    elastic_modulus: float,
    area: float,
    moment_of_inertia: float,
    length: float,
) -> list[list[float]]:
    ea_over_l = elastic_modulus * area / length
    ei = elastic_modulus * moment_of_inertia
    a = 12.0 * ei / length**3
    b = 6.0 * ei / length**2
    c = 4.0 * ei / length
    d = 2.0 * ei / length
    return [
        [ea_over_l, 0.0, 0.0, -ea_over_l, 0.0, 0.0],
        [0.0, a, b, 0.0, -a, b],
        [0.0, b, c, 0.0, -b, d],
        [-ea_over_l, 0.0, 0.0, ea_over_l, 0.0, 0.0],
        [0.0, -a, -b, 0.0, a, -b],
        [0.0, b, d, 0.0, -b, c],
    ]


def _transformation(cosine: float, sine: float) -> list[list[float]]:
    return [
        [cosine, sine, 0.0, 0.0, 0.0, 0.0],
        [-sine, cosine, 0.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 1.0, 0.0, 0.0, 0.0],
        [0.0, 0.0, 0.0, cosine, sine, 0.0],
        [0.0, 0.0, 0.0, -sine, cosine, 0.0],
        [0.0, 0.0, 0.0, 0.0, 0.0, 1.0],
    ]


def _fixed_end_forces(
    axial_intensity: float,
    transverse_intensity: float,
    length: float,
) -> list[float]:
    """Fixed-end forces in local coordinates for constant axial/transverse intensity."""
    axial_half = axial_intensity * length / 2.0
    shear_half = transverse_intensity * length / 2.0
    moment = transverse_intensity * length**2 / 12.0
    return [
        -axial_half,
        -shear_half,
        -moment,
        -axial_half,
        -shear_half,
        moment,
    ]


def _recover_member_forces(
    *,
    element: FrameElement,
    local_forces: list[float],
    length: float,
    transverse_intensity: float,
) -> MemberEndForces:
    axial_start, shear_start, moment_start, axial_end, shear_end, moment_end = local_forces

    # M(x) = -M_i + V_i*x + q*x^2/2 with the sign convention used above.
    def moment_at(position: float) -> float:
        return -moment_start + shear_start * position + transverse_intensity * position**2 / 2.0

    candidates = [(0.0, moment_at(0.0)), (length, moment_at(length))]
    if abs(transverse_intensity) > 1e-12:
        stationary = -shear_start / transverse_intensity
        if 0.0 < stationary < length:
            candidates.append((stationary, moment_at(stationary)))
    max_position, max_moment = max(candidates, key=lambda item: abs(item[1]))

    shear_candidates = [abs(shear_start), abs(shear_end)]
    axial_candidates = [abs(axial_start), abs(axial_end)]

    return MemberEndForces(
        element_id=element.id,
        member_id=element.member_id,
        length=length,
        axial_start=axial_start,
        shear_start=shear_start,
        moment_start=moment_start,
        axial_end=axial_end,
        shear_end=shear_end,
        moment_end=moment_end,
        max_abs_moment=abs(max_moment),
        max_abs_moment_position=max_position,
        max_abs_shear=max(shear_candidates),
        max_abs_axial=max(axial_candidates),
    )


def _multiply(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[index] * vector[index] for index in range(len(vector))) for row in matrix]


def _transpose_multiply(matrix: list[list[float]], vector: list[float]) -> list[float]:
    size = len(vector)
    return [sum(matrix[row][column] * vector[row] for row in range(size)) for column in range(size)]


def _triple_product(transform: list[list[float]], local: list[list[float]]) -> list[list[float]]:
    """``T^T * k * T`` for the 6x6 planar frame element."""
    intermediate = [
        [sum(local[row][inner] * transform[inner][column] for inner in range(6)) for column in range(6)]
        for row in range(6)
    ]
    return [
        [sum(transform[inner][row] * intermediate[inner][column] for inner in range(6)) for column in range(6)]
        for row in range(6)
    ]
