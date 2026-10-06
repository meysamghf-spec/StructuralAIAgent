"""
Direct-stiffness solver for 3D space frames.

Each node has six DOFs: ux, uy, uz, rx, ry, rz. Prismatic beam-columns use the
standard 12×12 local stiffness (axial, torsion, biaxial bending). Optional rigid
floor diaphragms condense in-plane ux, uy, rz of every node on a level to a
master (Ux, Uy, Rz) at the diaphragm centre of mass:

    ux = Ux - (y - yc) * Rz
    uy = Uy + (x - xc) * Rz
    rz = Rz

The planar solver in ``frame_solver.py`` is unchanged and remains a valid backend.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from app.application.analysis.linear_algebra import SingularMatrixError, factor_linear_system

DOF_PER_NODE = 6


class SpaceFrameSolverError(Exception):
    def __init__(self, message: str, *, status: str = "FAILED", details: dict | None = None) -> None:
        self.status = status
        self.details = details or {}
        super().__init__(message)


@dataclass(frozen=True)
class SpaceNode:
    id: str
    x: float
    y: float
    z: float
    level_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SpaceSupport:
    node_id: str
    restrain_ux: bool = True
    restrain_uy: bool = True
    restrain_uz: bool = True
    restrain_rx: bool = True
    restrain_ry: bool = True
    restrain_rz: bool = True

    def flags(self) -> tuple[bool, ...]:
        return (
            self.restrain_ux,
            self.restrain_uy,
            self.restrain_uz,
            self.restrain_rx,
            self.restrain_ry,
            self.restrain_rz,
        )


@dataclass(frozen=True)
class SpaceElement:
    id: str
    start_node_id: str
    end_node_id: str
    elastic_modulus: float
    area: float
    iy: float
    iz: float
    j: float
    poisson: float = 0.2
    udl_gx: float = 0.0
    udl_gy: float = 0.0
    udl_gz: float = 0.0
    member_id: str | None = None
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SpaceNodalLoad:
    node_id: str
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0


@dataclass(frozen=True)
class RigidDiaphragm:
    id: str
    level_id: str
    node_ids: tuple[str, ...]
    master_x: float
    master_y: float


@dataclass
class SpaceFrameModel:
    id: str
    nodes: list[SpaceNode]
    elements: list[SpaceElement]
    supports: list[SpaceSupport]
    nodal_loads: list[SpaceNodalLoad] = field(default_factory=list)
    diaphragms: list[RigidDiaphragm] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)


@dataclass(frozen=True)
class SpaceMemberForces:
    element_id: str
    member_id: str | None
    length: float
    axial: float
    shear_y: float
    shear_z: float
    torsion: float
    moment_y: float
    moment_z: float
    max_abs_axial: float
    max_abs_shear: float
    max_abs_moment: float


@dataclass
class SpaceFrameResult:
    model_id: str
    status: str
    message: str
    displacements: dict[str, tuple[float, float, float, float, float, float]]
    reactions: dict[str, tuple[float, float, float, float, float, float]]
    member_forces: dict[str, SpaceMemberForces]
    dof_count: int
    free_dof_count: int
    max_abs_displacement: float
    solver: str = "internal_direct_stiffness_3d"
    warnings: list[str] = field(default_factory=list)


def torsion_constant_rectangle(width: float, depth: float) -> float:
    a = max(width, depth)
    b = min(width, depth)
    if a <= 0.0 or b <= 0.0:
        return 0.0
    ratio = b / a
    return a * b**3 * (1.0 / 3.0 - 0.21 * ratio * (1.0 - (b**4) / (12.0 * a**4)))


def solve_space_frame(model: SpaceFrameModel) -> SpaceFrameResult:
    prepared = assemble_space_system(model)
    load_vector = list(prepared["gravity_load"])
    node_index: dict[str, int] = prepared["node_index"]
    for load in model.nodal_loads:
        if load.node_id not in node_index:
            raise SpaceFrameSolverError(f"Nodal load references missing node {load.node_id}", status="FAILED")
        base = node_index[load.node_id] * DOF_PER_NODE
        load_vector[base + 0] += load.fx
        load_vector[base + 1] += load.fy
        load_vector[base + 2] += load.fz
        load_vector[base + 3] += load.mx
        load_vector[base + 4] += load.my
        load_vector[base + 5] += load.mz
    return recover_space_result(model, prepared, load_vector)


def assemble_space_system(model: SpaceFrameModel) -> dict:
    if not model.nodes:
        raise SpaceFrameSolverError("Space frame has no nodes", status="FAILED")
    if not model.elements:
        raise SpaceFrameSolverError("Space frame has no elements", status="FAILED")
    if not model.supports:
        raise SpaceFrameSolverError("Space frame has no supports", status="UNSTABLE")

    node_index = {node.id: index for index, node in enumerate(model.nodes)}
    if len(node_index) != len(model.nodes):
        raise SpaceFrameSolverError("Duplicate node ids", status="FAILED")

    n_full = len(model.nodes) * DOF_PER_NODE
    stiffness = [[0.0] * n_full for _ in range(n_full)]
    gravity_load = [0.0] * n_full
    element_cache: dict = {}

    for element in model.elements:
        start = _require_node(model, node_index, element.start_node_id, element.id)
        end = _require_node(model, node_index, element.end_node_id, element.id)
        dx, dy, dz = end.x - start.x, end.y - start.y, end.z - start.z
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length <= 1e-9:
            raise SpaceFrameSolverError(f"Element {element.id} has zero length", status="FAILED")
        cx, cy, cz = dx / length, dy / length, dz / length
        local_k = _local_stiffness(element, length)
        transform = _transformation(cx, cy, cz)
        global_k = _triple(transform, local_k)
        fixed_local = _fixed_end_forces(element, length, transform)
        equiv_global = _matvec(_transpose(transform), [-value for value in fixed_local])
        dofs = _element_dofs(node_index[start.id], node_index[end.id])
        _assemble(stiffness, global_k, dofs)
        for local_index, dof in enumerate(dofs):
            gravity_load[dof] += equiv_global[local_index]
        element_cache[element.id] = (local_k, fixed_local, dofs, length, transform)

    restrained = set()
    for support in model.supports:
        if support.node_id not in node_index:
            raise SpaceFrameSolverError(f"Support references missing node {support.node_id}", status="FAILED")
        base = node_index[support.node_id] * DOF_PER_NODE
        for offset, flag in enumerate(support.flags()):
            if flag:
                restrained.add(base + offset)

    mapping, reduced_count, couplings = _build_mapping(model, node_index, restrained, n_full)
    if reduced_count <= 0:
        raise SpaceFrameSolverError("No free degrees of freedom remain", status="UNSTABLE")

    k_red = [[0.0] * reduced_count for _ in range(reduced_count)]
    for i in range(n_full):
        i_terms = _terms(mapping, couplings, i)
        if not i_terms:
            continue
        row = stiffness[i]
        for j in range(n_full):
            j_terms = _terms(mapping, couplings, j)
            if not j_terms:
                continue
            kij = row[j]
            if kij == 0.0:
                continue
            for ri, ci in i_terms:
                for rj, cj in j_terms:
                    k_red[ri][rj] += ci * cj * kij

    try:
        factor = factor_linear_system(k_red)
    except SingularMatrixError as exc:
        raise SpaceFrameSolverError(
            "Global stiffness matrix is singular (unstable or disconnected structure)",
            status="SINGULAR",
            details={"pivot": exc.pivot_row, "free_dof": reduced_count},
        ) from exc

    return {
        "node_index": node_index,
        "n_full": n_full,
        "stiffness": stiffness,
        "gravity_load": gravity_load,
        "mapping": mapping,
        "couplings": couplings,
        "reduced_count": reduced_count,
        "factor": factor,
        "element_cache": element_cache,
        "restrained": restrained,
    }


def recover_space_result(
    model: SpaceFrameModel,
    prepared: dict,
    load_vector: list[float],
) -> SpaceFrameResult:
    mapping = prepared["mapping"]
    couplings = prepared["couplings"]
    n_full = prepared["n_full"]
    reduced_count = prepared["reduced_count"]
    f_red = [0.0] * reduced_count
    for i in range(n_full):
        for ri, coef in _terms(mapping, couplings, i):
            f_red[ri] += coef * load_vector[i]
    try:
        u_red = prepared["factor"].solve(f_red)
    except SingularMatrixError as exc:
        raise SpaceFrameSolverError(
            "Global stiffness matrix is singular",
            status="SINGULAR",
            details={"pivot": exc.pivot_row},
        ) from exc

    u_full = [0.0] * n_full
    for i in range(n_full):
        terms = _terms(mapping, couplings, i)
        if terms:
            u_full[i] = sum(coef * u_red[ri] for ri, coef in terms)

    node_index = prepared["node_index"]
    displacements: dict[str, tuple[float, float, float, float, float, float]] = {}
    max_disp = 0.0
    for node in model.nodes:
        base = node_index[node.id] * DOF_PER_NODE
        values = (
            u_full[base],
            u_full[base + 1],
            u_full[base + 2],
            u_full[base + 3],
            u_full[base + 4],
            u_full[base + 5],
        )
        displacements[node.id] = values
        max_disp = max(max_disp, abs(values[0]), abs(values[1]), abs(values[2]))

    ku = _matvec(prepared["stiffness"], u_full)
    reactions: dict[str, tuple[float, float, float, float, float, float]] = {}
    for support in model.supports:
        base = node_index[support.node_id] * DOF_PER_NODE
        residual = tuple(ku[base + k] - load_vector[base + k] for k in range(DOF_PER_NODE))
        reactions[support.node_id] = residual

    member_forces: dict[str, SpaceMemberForces] = {}
    for element in model.elements:
        local_k, fixed_local, dofs, length, transform = prepared["element_cache"][element.id]
        u_g = [u_full[dof] for dof in dofs]
        u_l = _matvec(transform, u_g)
        end_local = _matvec(local_k, u_l)
        forces = [end_local[i] + fixed_local[i] for i in range(12)]
        member_forces[element.id] = SpaceMemberForces(
            element_id=element.id,
            member_id=element.member_id,
            length=length,
            axial=forces[0],
            shear_y=forces[1],
            shear_z=forces[2],
            torsion=forces[3],
            moment_y=forces[4],
            moment_z=forces[5],
            max_abs_axial=max(abs(forces[0]), abs(forces[6])),
            max_abs_shear=max(abs(forces[1]), abs(forces[2]), abs(forces[7]), abs(forces[8])),
            max_abs_moment=max(abs(forces[4]), abs(forces[5]), abs(forces[10]), abs(forces[11])),
        )

    warnings: list[str] = []
    if max_disp > 0.15:
        warnings.append(
            f"Peak translational displacement is {max_disp * 1000:.1f} mm; verify supports and stiffness."
        )
    return SpaceFrameResult(
        model_id=model.id,
        status="SUCCESS",
        message=f"Solved 3D frame with {reduced_count} free DOF. Peak |u| = {max_disp * 1000:.2f} mm.",
        displacements=displacements,
        reactions=reactions,
        member_forces=member_forces,
        dof_count=n_full,
        free_dof_count=reduced_count,
        max_abs_displacement=max_disp,
        warnings=warnings,
    )


def build_space_load_vector(
    model: SpaceFrameModel,
    prepared: dict,
    nodal_loads: list[SpaceNodalLoad] | tuple[SpaceNodalLoad, ...] = (),
    element_udls: dict[str, tuple[float, float, float]] | None = None,
) -> list[float]:
    """Assemble a global load vector without mutating element UDLs on the model."""
    n_full = prepared["n_full"]
    node_index = prepared["node_index"]
    vector = [0.0] * n_full
    for element in model.elements:
        wx, wy, wz = element.udl_gx, element.udl_gy, element.udl_gz
        if element_udls is not None:
            wx, wy, wz = element_udls.get(element.id, (0.0, 0.0, 0.0))
        if wx == 0.0 and wy == 0.0 and wz == 0.0:
            continue
        _local_k, _fixed, dofs, length, transform = prepared["element_cache"][element.id]
        temp = SpaceElement(
            id=element.id,
            start_node_id=element.start_node_id,
            end_node_id=element.end_node_id,
            elastic_modulus=element.elastic_modulus,
            area=element.area,
            iy=element.iy,
            iz=element.iz,
            j=element.j,
            poisson=element.poisson,
            udl_gx=wx,
            udl_gy=wy,
            udl_gz=wz,
        )
        fixed_local = _fixed_end_forces(temp, length, transform)
        equiv_global = _matvec(_transpose(transform), [-value for value in fixed_local])
        for local_index, dof in enumerate(dofs):
            vector[dof] += equiv_global[local_index]
    for load in nodal_loads:
        if load.node_id not in node_index:
            raise SpaceFrameSolverError(f"Nodal load references missing node {load.node_id}", status="FAILED")
        base = node_index[load.node_id] * DOF_PER_NODE
        vector[base + 0] += load.fx
        vector[base + 1] += load.fy
        vector[base + 2] += load.fz
        vector[base + 3] += load.mx
        vector[base + 4] += load.my
        vector[base + 5] += load.mz
    return vector


def solve_prepared_space_frame(
    model: SpaceFrameModel,
    prepared: dict,
    load_vector: list[float],
) -> SpaceFrameResult:
    return recover_space_result(model, prepared, load_vector)


def _build_mapping(
    model: SpaceFrameModel,
    node_index: dict[str, int],
    restrained: set[int],
    n_full: int,
) -> tuple[list[int], int, dict[int, list[tuple[int, float]]]]:
    mapping = [-1] * n_full
    couplings: dict[int, list[tuple[int, float]]] = {}
    next_reduced = 0
    slave: set[int] = set()

    for diaphragm in model.diaphragms:
        ux_m, uy_m, rz_m = next_reduced, next_reduced + 1, next_reduced + 2
        next_reduced += 3
        for node_id in diaphragm.node_ids:
            if node_id not in node_index:
                continue
            node = model.nodes[node_index[node_id]]
            base = node_index[node_id] * DOF_PER_NODE
            dx = node.x - diaphragm.master_x
            dy = node.y - diaphragm.master_y
            if base + 0 not in restrained:
                couplings[base + 0] = [(ux_m, 1.0), (rz_m, -dy)]
                slave.add(base + 0)
            if base + 1 not in restrained:
                couplings[base + 1] = [(uy_m, 1.0), (rz_m, dx)]
                slave.add(base + 1)
            if base + 5 not in restrained:
                couplings[base + 5] = [(rz_m, 1.0)]
                slave.add(base + 5)

    for dof in range(n_full):
        if dof in restrained or dof in slave:
            continue
        mapping[dof] = next_reduced
        next_reduced += 1
    return mapping, next_reduced, couplings


def _terms(
    mapping: list[int],
    couplings: dict[int, list[tuple[int, float]]],
    dof: int,
) -> list[tuple[int, float]]:
    if dof in couplings:
        return couplings[dof]
    if mapping[dof] >= 0:
        return [(mapping[dof], 1.0)]
    return []


def _require_node(model: SpaceFrameModel, index: dict[str, int], node_id: str, element_id: str) -> SpaceNode:
    if node_id not in index:
        raise SpaceFrameSolverError(
            f"Element {element_id} references missing node {node_id}",
            status="FAILED",
        )
    return model.nodes[index[node_id]]


def _element_dofs(start_index: int, end_index: int) -> list[int]:
    start = start_index * DOF_PER_NODE
    end = end_index * DOF_PER_NODE
    return list(range(start, start + 6)) + list(range(end, end + 6))


def _local_stiffness(element: SpaceElement, length: float) -> list[list[float]]:
    e, a, iy, iz, j = element.elastic_modulus, element.area, element.iy, element.iz, element.j
    shear_modulus = e / (2.0 * (1.0 + element.poisson))
    k = [[0.0] * 12 for _ in range(12)]
    ea_l = e * a / length
    gj_l = shear_modulus * j / length
    k[0][0] = k[6][6] = ea_l
    k[0][6] = k[6][0] = -ea_l
    k[3][3] = k[9][9] = gj_l
    k[3][9] = k[9][3] = -gj_l

    a_z = 12.0 * e * iz / length**3
    b_z = 6.0 * e * iz / length**2
    c_z = 4.0 * e * iz / length
    d_z = 2.0 * e * iz / length
    k[1][1] = k[7][7] = a_z
    k[1][7] = k[7][1] = -a_z
    k[1][5] = k[5][1] = b_z
    k[1][11] = k[11][1] = b_z
    k[5][7] = k[7][5] = -b_z
    k[7][11] = k[11][7] = -b_z
    k[5][5] = k[11][11] = c_z
    k[5][11] = k[11][5] = d_z

    a_y = 12.0 * e * iy / length**3
    b_y = 6.0 * e * iy / length**2
    c_y = 4.0 * e * iy / length
    d_y = 2.0 * e * iy / length
    k[2][2] = k[8][8] = a_y
    k[2][8] = k[8][2] = -a_y
    k[2][4] = k[4][2] = -b_y
    k[2][10] = k[10][2] = -b_y
    k[4][8] = k[8][4] = b_y
    k[8][10] = k[10][8] = b_y
    k[4][4] = k[10][10] = c_y
    k[4][10] = k[10][4] = d_y
    return k


def _transformation(cx: float, cy: float, cz: float) -> list[list[float]]:
    """12×12 block-diagonal of the 3×3 direction-cosine matrix λ (u_local = λ u_global)."""
    if abs(cz) < 0.99:
        ref = (0.0, 0.0, 1.0)
    else:
        ref = (0.0, 1.0, 0.0)
    ex = (cx, cy, cz)
    ey = _cross(ref, ex)
    ey_norm = math.sqrt(ey[0] ** 2 + ey[1] ** 2 + ey[2] ** 2)
    if ey_norm <= 1e-12:
        ref = (1.0, 0.0, 0.0)
        ey = _cross(ref, ex)
        ey_norm = math.sqrt(ey[0] ** 2 + ey[1] ** 2 + ey[2] ** 2)
    ey = (ey[0] / ey_norm, ey[1] / ey_norm, ey[2] / ey_norm)
    ez = _cross(ex, ey)
    lam = [ex, ey, ez]
    transform = [[0.0] * 12 for _ in range(12)]
    for block in range(4):
        r0 = 3 * block
        for i in range(3):
            for j in range(3):
                transform[r0 + i][r0 + j] = lam[i][j]
    return transform


def _fixed_end_forces(element: SpaceElement, length: float, transform: list[list[float]]) -> list[float]:
    """Equivalent local fixed-end forces from a uniform global-axis line load."""
    wx, wy, wz = element.udl_gx, element.udl_gy, element.udl_gz
    if wx == 0.0 and wy == 0.0 and wz == 0.0:
        return [0.0] * 12
    w_local = _matvec([transform[i][:3] for i in range(3)], [wx, wy, wz])
    w_ax, w_y, w_z = w_local
    forces = [0.0] * 12
    forces[0] = -w_ax * length / 2.0
    forces[6] = -w_ax * length / 2.0
    forces[1] = -w_y * length / 2.0
    forces[7] = -w_y * length / 2.0
    forces[5] = -w_y * length**2 / 12.0
    forces[11] = w_y * length**2 / 12.0
    forces[2] = -w_z * length / 2.0
    forces[8] = -w_z * length / 2.0
    forces[4] = w_z * length**2 / 12.0
    forces[10] = -w_z * length**2 / 12.0
    return forces


def _assemble(global_k: list[list[float]], element_k: list[list[float]], dofs: list[int]) -> None:
    for i, di in enumerate(dofs):
        row = element_k[i]
        dest = global_k[di]
        for j, dj in enumerate(dofs):
            dest[dj] += row[j]


def _triple(transform: list[list[float]], local_k: list[list[float]]) -> list[list[float]]:
    """K_global = T^T K_local T."""
    kt = _matmul(local_k, transform)
    return _matmul(_transpose(transform), kt)


def _matmul(a: list[list[float]], b: list[list[float]]) -> list[list[float]]:
    n = len(a)
    m = len(b[0])
    p = len(b)
    result = [[0.0] * m for _ in range(n)]
    for i in range(n):
        ai = a[i]
        ri = result[i]
        for k in range(p):
            aik = ai[k]
            if aik == 0.0:
                continue
            bk = b[k]
            for j in range(m):
                ri[j] += aik * bk[j]
    return result


def _matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(row[j] * vector[j] for j in range(len(vector))) for row in matrix]


def _transpose(matrix: list[list[float]]) -> list[list[float]]:
    return [list(row) for row in zip(*matrix, strict=True)]


def _cross(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )
