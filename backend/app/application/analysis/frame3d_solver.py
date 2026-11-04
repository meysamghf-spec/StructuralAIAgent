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

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spla

from app.application.analysis.linear_algebra import SingularMatrixError

# Reduced systems up to this size keep the dense eigen path for the P-Δ critical load factor (exactly the
# previous behaviour); larger ones use ARPACK (scipy eigsh) on the sparse generalized problem.
DENSE_EIGEN_MAX_DOF = 1500

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
    u_full: object = None  # numpy array of all nodal DOFs (n_full), for vectorised post-processing


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
    """Assemble the sparse global stiffness (scipy CSR) and factor the reduced system (sparse LU).

    Element matrices are stacked in numpy arrays (E×12×12) and scattered into a sparse matrix, so the
    cost grows ~linearly with the model size (thousands of nodes/elements) instead of O(n²) memory.
    """
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
    n_el = len(model.elements)
    lk_all = np.empty((n_el, 12, 12))
    tr_all = np.empty((n_el, 12, 12))
    fl_all = np.empty((n_el, 12))
    dofs_all = np.empty((n_el, 12), dtype=np.int64)
    lengths: list[float] = []
    for e_i, element in enumerate(model.elements):
        start = _require_node(model, node_index, element.start_node_id, element.id)
        end = _require_node(model, node_index, element.end_node_id, element.id)
        dx, dy, dz = end.x - start.x, end.y - start.y, end.z - start.z
        length = math.sqrt(dx * dx + dy * dy + dz * dz)
        if length <= 1e-9:
            raise SpaceFrameSolverError(f"Element {element.id} has zero length", status="FAILED")
        cx, cy, cz = dx / length, dy / length, dz / length
        transform = _transformation(cx, cy, cz)
        lk_all[e_i] = _local_stiffness(element, length)
        tr_all[e_i] = transform
        fl_all[e_i] = _fixed_end_forces(element, length, transform)
        dofs_all[e_i] = _element_dofs(node_index[start.id], node_index[end.id])
        lengths.append(length)

    k_glob = np.einsum("eji,ejk,ekl->eil", tr_all, lk_all, tr_all, optimize=True)  # Tᵀ·K_local·T
    equiv = -np.einsum("eji,ej->ei", tr_all, fl_all)  # Tᵀ·(−fixed-end forces)
    gravity_load = np.bincount(dofs_all.ravel(), weights=equiv.ravel(), minlength=n_full)
    stiffness = _scatter(k_glob, dofs_all, n_full)
    element_cache: dict = {}
    for e_i, element in enumerate(model.elements):
        element_cache[element.id] = (lk_all[e_i], fl_all[e_i], dofs_all[e_i], lengths[e_i], tr_all[e_i])

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

    prepared = {
        "node_index": node_index,
        "n_full": n_full,
        "stiffness": stiffness,
        "gravity_load": gravity_load.tolist(),
        "mapping": mapping,
        "couplings": couplings,
        "reduced_count": reduced_count,
        "element_cache": element_cache,
        "element_arrays": {"lk": lk_all, "tr": tr_all, "fl": fl_all, "dofs": dofs_all},
        "element_ids": [e.id for e in model.elements],
        "restrained": restrained,
    }
    t = reduction_matrix(prepared)
    k_red = (t.T @ stiffness @ t).tocsc()
    k_red = (0.5 * (k_red + k_red.T)).tocsc()
    prepared["k_red"] = k_red
    try:
        prepared["factor"] = SparseFactor(k_red)
    except SingularMatrixError as exc:
        raise SpaceFrameSolverError(
            "Global stiffness matrix is singular (unstable or disconnected structure)",
            status="SINGULAR",
            details={"pivot": exc.pivot_row, "free_dof": reduced_count},
        ) from exc
    return prepared


def reload_space_loads(prepared: dict, model: SpaceFrameModel) -> dict:
    """Re-use an assembled/factored system for another load case of the SAME geometry and sections.

    Only the member line loads (fixed-end forces → equivalent nodal loads) are rebuilt; the stiffness and its
    sparse factor are shared, so D, L, Ex and Ey need a single factorisation (time and memory).
    """
    arr = prepared["element_arrays"]
    ids = prepared["element_ids"]
    if len(model.elements) != len(ids) or any(e.id != i for e, i in zip(model.elements, ids)):
        raise SpaceFrameSolverError("Load-case model does not match the assembled system", status="FAILED")
    cache = prepared["element_cache"]
    fl_all = np.zeros_like(arr["fl"])
    for e_i, element in enumerate(model.elements):
        if element.udl_gx or element.udl_gy or element.udl_gz:
            fl_all[e_i] = _fixed_end_forces(element, cache[element.id][3], arr["tr"][e_i])
    equiv = -np.einsum("eji,ej->ei", arr["tr"], fl_all)
    gravity_load = np.bincount(arr["dofs"].ravel(), weights=equiv.ravel(), minlength=prepared["n_full"])
    out = dict(prepared)
    out["element_arrays"] = {**arr, "fl": fl_all}
    out["element_cache"] = {eid: (c[0], fl_all[e_i], c[2], c[3], c[4]) for e_i, (eid, c) in enumerate(cache.items())}
    out["gravity_load"] = gravity_load.tolist()
    return out


def _scatter(blocks: np.ndarray, dofs: np.ndarray, n_full: int) -> sp.csr_matrix:
    """Sum E×12×12 element blocks into an n_full×n_full sparse matrix."""
    rows = np.repeat(dofs, 12, axis=1).ravel()
    cols = np.tile(dofs, (1, 12)).ravel()
    return sp.csr_matrix((blocks.ravel(), (rows, cols)), shape=(n_full, n_full))


def element_end_forces(prepared: dict, u_full: np.ndarray, *, with_fixed: bool = True) -> np.ndarray:
    """Local end forces of every element (E×12, or E×12×m for an n_full×m displacement array)."""
    arr = prepared["element_arrays"]
    lkt = arr.get("lkt")
    if lkt is None:
        lkt = arr["lkt"] = np.einsum("eij,ejk->eik", arr["lk"], arr["tr"], optimize=True)
    u_el = np.asarray(u_full)[arr["dofs"]]
    if u_el.ndim == 2:
        out = np.einsum("eij,ej->ei", lkt, u_el)
        return out + arr["fl"] if with_fixed else out
    return np.einsum("eij,ejm->eim", lkt, u_el)


def recover_space_result(
    model: SpaceFrameModel,
    prepared: dict,
    load_vector: list[float],
) -> SpaceFrameResult:
    t = reduction_matrix(prepared)
    lv = np.asarray(load_vector, dtype=float)
    reduced_count = prepared["reduced_count"]
    n_full = prepared["n_full"]
    f_red = t.T @ lv
    try:
        u_red = prepared["factor"].solve_many(f_red)
    except SingularMatrixError as exc:
        raise SpaceFrameSolverError(
            "Global stiffness matrix is singular",
            status="SINGULAR",
            details={"pivot": exc.pivot_row},
        ) from exc
    u_full = t @ u_red

    node_index = prepared["node_index"]
    u_nodes = u_full.reshape(-1, DOF_PER_NODE)
    u_list = u_nodes.tolist()
    displacements: dict[str, tuple[float, float, float, float, float, float]] = {
        node.id: tuple(u_list[node_index[node.id]]) for node in model.nodes
    }
    max_disp = float(np.abs(u_nodes[:, :3]).max()) if len(u_list) else 0.0

    ku = prepared["stiffness"] @ u_full
    if prepared.get("kg_full") is not None:  # second-order (P-Δ): + K_G·u
        ku = ku + prepared["kg_full"] @ u_full
    reactions: dict[str, tuple[float, float, float, float, float, float]] = {}
    for support in model.supports:
        base = node_index[support.node_id] * DOF_PER_NODE
        reactions[support.node_id] = tuple(float(ku[base + k] - lv[base + k]) for k in range(DOF_PER_NODE))

    ends = element_end_forces(prepared, u_full)
    ab = np.abs(ends)
    max_ax = np.maximum(ab[:, 0], ab[:, 6])
    max_sh = ab[:, [1, 2, 7, 8]].max(axis=1)
    max_mo = ab[:, [4, 5, 10, 11]].max(axis=1)
    ends_l = ends[:, :6].tolist()
    member_forces: dict[str, SpaceMemberForces] = {}
    for e_i, element in enumerate(model.elements):
        f = ends_l[e_i]
        member_forces[element.id] = SpaceMemberForces(
            element_id=element.id,
            member_id=element.member_id,
            length=prepared["element_cache"][element.id][3],
            axial=f[0],
            shear_y=f[1],
            shear_z=f[2],
            torsion=f[3],
            moment_y=f[4],
            moment_z=f[5],
            max_abs_axial=float(max_ax[e_i]),
            max_abs_shear=float(max_sh[e_i]),
            max_abs_moment=float(max_mo[e_i]),
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
        u_full=u_full,
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


# --------------------------------------------------------------------------- second order (P-Δ)
def geometric_stiffness_local(element: SpaceElement, length: float, compression: float) -> list[list[float]]:
    """12×12 linear geometric (initial-stress) stiffness of a prismatic beam-column.

    ``compression`` is the axial force (positive = compression). Standard consistent
    matrix for cubic (Hermite) bending shape functions, axial/torsion terms:

        v1-v1 = 6N/5L,  v1-θz1 = N/10,  θz1-θz1 = 2NL/15,  θz1-θz2 = -NL/30,  ...
        θx-θx = N·(Iy+Iz)/(A·L)

    with N = -compression (tension positive). Signs follow ``_local_stiffness``.
    """
    n_t = -compression
    k = [[0.0] * 12 for _ in range(12)]
    a = 6.0 * n_t / (5.0 * length)
    b = n_t / 10.0
    c = 2.0 * n_t * length / 15.0
    d = -n_t * length / 30.0
    # plane x-y: v1(1) θz1(5) v2(7) θz2(11)
    for (i, j), val in {
        (1, 1): a, (1, 5): b, (1, 7): -a, (1, 11): b,
        (5, 5): c, (5, 7): -b, (5, 11): d,
        (7, 7): a, (7, 11): -b,
        (11, 11): c,
    }.items():
        k[i][j] = k[j][i] = val
    # plane x-z: w1(2) θy1(4) w2(8) θy2(10) — coupling signs mirror the elastic matrix
    for (i, j), val in {
        (2, 2): a, (2, 4): -b, (2, 8): -a, (2, 10): -b,
        (4, 4): c, (4, 8): b, (4, 10): d,
        (8, 8): a, (8, 10): b,
        (10, 10): c,
    }.items():
        k[i][j] = k[j][i] = val
    polar = (element.iy + element.iz) / element.area if element.area > 0 else 0.0
    tors = n_t * polar / length
    k[3][3] = k[9][9] = tors
    k[3][9] = k[9][3] = -tors
    return k


def reduction_matrix(prepared: dict) -> sp.csr_matrix:
    """Sparse (n_full × n_reduced) matrix T with u_full = T·u_reduced (supports and diaphragm slaves included)."""
    cached = prepared.get("_tmat")
    if cached is not None:
        return cached
    n_full, n_red = prepared["n_full"], prepared["reduced_count"]
    rows: list[int] = []
    cols: list[int] = []
    vals: list[float] = []
    mapping, couplings = prepared["mapping"], prepared["couplings"]
    for dof in range(n_full):
        for ri, coef in _terms(mapping, couplings, dof):
            rows.append(dof); cols.append(ri); vals.append(coef)
    t = sp.csr_matrix((vals, (rows, cols)), shape=(n_full, n_red))
    prepared["_tmat"] = t
    return t


class SparseFactor:
    """Sparse LU (SuperLU, symmetric ordering) of a symmetric reduced stiffness matrix.

    A pivot below ``pivot_tolerance``·max|K| flags a singular (unstable / disconnected) structure, the same
    criterion as the previous dense Gaussian elimination.
    """

    def __init__(self, matrix, *, pivot_tolerance: float = 1e-12) -> None:
        m = sp.csc_matrix(matrix)
        self.size = m.shape[0]
        self.matrix = m
        scale = float(abs(m).max()) if m.nnz else 0.0
        threshold = pivot_tolerance * max(scale, 1.0)
        try:
            self.lu = spla.splu(m, permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.0,
                                options={"SymmetricMode": True})
        except RuntimeError as exc:  # "Factor is exactly singular"
            raise SingularMatrixError(-1) from exc
        diag = np.abs(self.lu.U.diagonal())
        if diag.size and (not np.all(np.isfinite(diag)) or float(diag.min()) <= threshold):
            raise SingularMatrixError(int(np.argmin(diag)))

    def solve(self, rhs) -> list[float]:
        return self.solve_many(np.asarray(rhs, dtype=float)).tolist()

    def solve_many(self, rhs: np.ndarray) -> np.ndarray:
        out = self.lu.solve(np.asarray(rhs, dtype=float))
        if not np.all(np.isfinite(out)):
            raise SingularMatrixError(-1)
        return out


class DenseCholeskyFactor:
    """Cholesky factor (numpy) of a symmetric positive-definite reduced matrix (small systems)."""

    def __init__(self, matrix: np.ndarray) -> None:
        self.matrix = matrix
        try:
            self.chol = np.linalg.cholesky(matrix)
        except np.linalg.LinAlgError as exc:
            raise SingularMatrixError(-1) from exc
        self.linv = np.linalg.inv(self.chol)

    def solve(self, rhs) -> list[float]:
        return (self.linv.T @ (self.linv @ np.asarray(rhs, dtype=float))).tolist()

    def solve_many(self, rhs: np.ndarray) -> np.ndarray:
        return self.linv.T @ (self.linv @ rhs)


SOLVE_CHUNK = 64  # right-hand sides per sparse solve (bounds peak memory of n_full × m results)


def solve_space_many(prepared: dict, load_vectors) -> np.ndarray:
    """Solve several full-DOF load vectors at once. Returns u_full as an (n_full × m) array.

    Uses the sparse factor of the reduced elastic (or second-order) matrix of ``prepared``.
    """
    t = reduction_matrix(prepared)
    f_full = np.asarray(load_vectors, dtype=float).T  # n_full × m
    if f_full.ndim == 1:
        f_full = f_full[:, None]
    f_red = np.asarray(t.T @ f_full)
    factor = prepared["factor"]
    out = np.empty((prepared["n_full"], f_red.shape[1]))
    for c0 in range(0, f_red.shape[1], SOLVE_CHUNK):
        u_red = factor.solve_many(f_red[:, c0:c0 + SOLVE_CHUNK])
        out[:, c0:c0 + SOLVE_CHUNK] = (t @ u_red).reshape(prepared["n_full"], -1)
    return out


def prepare_second_order(
    model: SpaceFrameModel,
    prepared: dict,
    compression: dict[str, float],
    *,
    min_load_factor: float = 1.0,
) -> dict:
    """Return a new ``prepared`` dict for the second-order system (K + K_G) with frozen member axial forces.

    ``compression`` maps element id -> axial force (positive = compression) from a gravity combination.
    The returned dict carries ``second_order`` info: elastic critical load factor λcr of that
    gravity pattern (K φ = λ·(-K_G) φ) — the P-Δ solution exists only for λcr > 1.
    Raises ``SpaceFrameSolverError(status="UNSTABLE")`` otherwise.
    Member end forces recovered with the elastic ``local_k`` (internal bending actions); the
    reactions include K_G so global equilibrium in the deformed geometry is exact.
    """
    n_full = prepared["n_full"]
    by_id = {e.id: e for e in model.elements}
    arr = prepared["element_arrays"]
    sel, kgl = [], []
    for e_i, eid in enumerate(prepared["element_ids"]):
        p = compression.get(eid, 0.0)
        if p == 0.0:
            continue
        sel.append(e_i)
        kgl.append(geometric_stiffness_local(by_id[eid], prepared["element_cache"][eid][3], p))
    if sel:
        tr = arr["tr"][sel]
        kg_glob = np.einsum("eji,ejk,ekl->eil", tr, np.asarray(kgl), tr, optimize=True)
        kg_full = _scatter(kg_glob, arr["dofs"][sel], n_full)
    else:
        kg_full = sp.csr_matrix((n_full, n_full))
    t = reduction_matrix(prepared)
    kg_red = (t.T @ kg_full @ t).tocsc()
    kg_red = (0.5 * (kg_red + kg_red.T)).tocsc()
    k_el = prepared["k_red"]
    try:
        lam = _critical_load_factor(k_el, kg_red, prepared["factor"])
    except SingularMatrixError as exc:
        raise SpaceFrameSolverError("Elastic stiffness is not positive definite", status="SINGULAR") from exc
    if lam <= min_load_factor:
        raise SpaceFrameSolverError(
            f"Gravity load pattern exceeds the elastic critical load (λcr = {lam:.3f} ≤ {min_load_factor:g}); "
            "the second-order (P-Δ) solution does not exist — the structure is unstable.",
            status="UNSTABLE", details={"lambda_cr": lam},
        )
    try:
        factor = SparseFactor(k_el + kg_red)
    except SingularMatrixError as exc:
        raise SpaceFrameSolverError("Second-order stiffness is not positive definite (unstable)", status="UNSTABLE",
                                    details={"lambda_cr": lam}) from exc
    second = dict(prepared)
    second.update({"factor": factor, "kg_full": kg_full, "k_geo_red": kg_red,
                   "second_order": {"lambda_cr": lam, "method": "geometric stiffness K_G, frozen axial forces"}})
    return second


def _critical_load_factor(k_el, kg_red, factor: "SparseFactor") -> float:
    """λcr = 1/μmax of K φ = λ(−K_G) φ. Dense eigen for small systems, ARPACK (eigsh, mode 2) otherwise."""
    n = k_el.shape[0]
    if n <= DENSE_EIGEN_MAX_DOF:
        k_d = k_el.toarray()
        k_d = 0.5 * (k_d + k_d.T)
        g_d = kg_red.toarray()
        el = DenseCholeskyFactor(k_d)
        a = el.linv @ (-g_d) @ el.linv.T
        mu = float(np.linalg.eigvalsh(0.5 * (a + a.T)).max())
    else:
        if kg_red.nnz == 0:
            return math.inf
        minv = spla.LinearOperator((n, n), matvec=factor.solve_many, dtype=float)
        vals = spla.eigsh(-kg_red, k=1, M=k_el, Minv=minv, which="LA", return_eigenvectors=False,
                          tol=1e-10, maxiter=5000, ncv=min(n - 1, 40))
        mu = float(vals.max())
    return (1.0 / mu) if mu > 1e-12 else math.inf
