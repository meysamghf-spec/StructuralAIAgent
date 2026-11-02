"""SAIA sparse 3D frame engine for imported models (numpy + scipy.sparse). Deterministic, no LLM.

Features: 12-DOF Euler-Bernoulli frame elements with end releases (static condensation), piecewise
uniform member loads in global directions (slab loads arrive this way), rigid floor diaphragms
(master-slave constraint, master at the floor mass centre), P-Delta (geometric stiffness from the
axial forces of a gravity case, iterated), modal analysis (lumped seismic mass, shift-invert Lanczos),
and response-spectrum analysis with CQC combination. Sparse LU (SuperLU) is factorised once and
reused for every load case, so there is no fixed node limit.

Sign/units: kN, m, kN.m, tonnes (kN.s2/m). Global Z is up, gravity is -Z.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp
import scipy.sparse.linalg as spla

G_ACC = 9.80665
N_STATIONS = 9


class EngineError(ValueError):
    pass


@dataclass
class Element:
    id: str
    i: int
    j: int
    E: float
    G: float
    A: float
    I33: float
    I22: float
    J: float
    rel_i: tuple[bool, ...] = (False,) * 6   # local P, V2, V3, T, M2, M3
    rel_j: tuple[bool, ...] = (False,) * 6
    L: float = 0.0
    R: np.ndarray = field(default_factory=lambda: np.eye(3))


def rotation(xi: np.ndarray, xj: np.ndarray) -> tuple[float, np.ndarray]:
    d = xj - xi
    L = float(np.linalg.norm(d))
    if L < 1e-9:
        raise EngineError("zero-length member")
    e1 = d / L
    if abs(e1[2]) > 0.999:          # vertical: local 2 = +X (CSI convention)
        e2 = np.array([1.0, 0.0, 0.0])
        e2 = e2 - e2.dot(e1) * e1
    else:                            # local 2 has an upward component
        z = np.array([0.0, 0.0, 1.0])
        e2 = z - z.dot(e1) * e1
    e2 /= np.linalg.norm(e2)
    e3 = np.cross(e1, e2)
    return L, np.vstack([e1, e2, e3])


def _bend4(EI: float, L: float) -> np.ndarray:
    return EI / L**3 * np.array([[12, 6 * L, -12, 6 * L], [6 * L, 4 * L * L, -6 * L, 2 * L * L],
                                 [-12, -6 * L, 12, -6 * L], [6 * L, 2 * L * L, -6 * L, 4 * L * L]], dtype=float)


def _geo4(P: float, L: float) -> np.ndarray:
    return P / L * np.array([[6 / 5, L / 10, -6 / 5, L / 10], [L / 10, 2 * L * L / 15, -L / 10, -L * L / 30],
                             [-6 / 5, -L / 10, 6 / 5, -L / 10], [L / 10, -L * L / 30, -L / 10, 2 * L * L / 15]], dtype=float)


# plane 1-2: v=u2 (idx 1,7), phi=+r3 (5,11); plane 1-3: v=u3 (2,8), phi=-r2 (4,10)
_P12 = ((1, 1.0), (5, 1.0), (7, 1.0), (11, 1.0))
_P13 = ((2, 1.0), (4, -1.0), (8, 1.0), (10, -1.0))


def _place(k: np.ndarray, k4: np.ndarray, plane) -> None:
    for a, (ia, sa) in enumerate(plane):
        for b, (ib, sb) in enumerate(plane):
            k[ia, ib] += sa * sb * k4[a, b]


def local_k(el: Element, P: float = 0.0) -> np.ndarray:
    L = el.L
    k = np.zeros((12, 12))
    ea, gj = el.E * el.A / L, el.G * el.J / L
    for a, b, v in ((0, 0, ea), (6, 6, ea), (0, 6, -ea), (6, 0, -ea), (3, 3, gj), (9, 9, gj), (3, 9, -gj), (9, 3, -gj)):
        k[a, b] += v
    _place(k, _bend4(el.E * el.I33, L), _P12)
    _place(k, _bend4(el.E * el.I22, L), _P13)
    if P:
        _place(k, _geo4(P, L), _P12)
        _place(k, _geo4(P, L), _P13)
    return k


_GX, _GW = np.polynomial.legendre.leggauss(4)


def local_eq_loads(L: float, segs: list[tuple[float, float, np.ndarray]]) -> np.ndarray:
    """Equivalent nodal loads (local) for piecewise-uniform local loads: segs = (a, b [m], w_local[3])."""
    f = np.zeros(12)
    for a, b, w in segs:
        if b <= a:
            continue
        for gx, gw in zip(_GX, _GW):
            x = (a + b) / 2 + (b - a) / 2 * gx
            wt = gw * (b - a) / 2
            s = x / L
            n1, n2 = 1 - 3 * s * s + 2 * s**3, L * (s - 2 * s * s + s**3)
            n3, n4 = 3 * s * s - 2 * s**3, L * (-s * s + s**3)
            f[0] += w[0] * (1 - s) * wt
            f[6] += w[0] * s * wt
            for (iv, ip, jv, jp, comp, sg) in ((1, 5, 7, 11, 1, 1.0), (2, 4, 8, 10, 2, -1.0)):
                q = w[comp] * wt
                f[iv] += n1 * q
                f[ip] += sg * n2 * q
                f[jv] += n3 * q
                f[jp] += sg * n4 * q
    return f


def condense(k: np.ndarray, f: np.ndarray | None, rel: list[int]) -> tuple[np.ndarray, np.ndarray | None]:
    if not rel:
        return k, f
    keep = [i for i in range(12) if i not in rel]
    krr = k[np.ix_(rel, rel)]
    krk = k[np.ix_(rel, keep)]
    try:
        x = np.linalg.solve(krr, krk)
    except np.linalg.LinAlgError as exc:
        raise EngineError("member end releases make the member unstable") from exc
    kc = np.zeros((12, 12))
    kc[np.ix_(keep, keep)] = k[np.ix_(keep, keep)] - k[np.ix_(keep, rel)] @ x
    fc = None
    if f is not None:
        y = np.linalg.solve(krr, f[rel])
        fc = np.zeros(12)
        fc[keep] = f[keep] - k[np.ix_(keep, rel)] @ y
    return kc, fc


def rel_list(el: Element) -> list[int]:
    return [i for i, r in enumerate(el.rel_i) if r] + [6 + i for i, r in enumerate(el.rel_j) if r]


def big_T(R: np.ndarray) -> np.ndarray:
    T = np.zeros((12, 12))
    for b in range(4):
        T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R
    return T


class FrameEngine:
    """Assemble once, solve many. ``nodes``: list of (id, x, y, z); supports: id -> 6 bools."""

    def __init__(self, nodes: list[tuple[str, float, float, float]], elements: list[dict[str, Any]],
                 supports: dict[str, list[bool]], diaphragms: list[dict[str, Any]] | None = None,
                 nodal_mass: dict[str, float] | None = None) -> None:
        self.node_ids = [n[0] for n in nodes]
        self.index = {nid: k for k, nid in enumerate(self.node_ids)}
        self.xyz = np.array([[n[1], n[2], n[3]] for n in nodes], dtype=float)
        self.nn = len(nodes)
        self.ndof = 6 * self.nn
        self.elements: list[Element] = []
        for e in elements:
            el = Element(e["id"], self.index[e["i"]], self.index[e["j"]], e["E"], e.get("G") or e["E"] / (2 * (1 + e.get("nu", 0.2))),
                         e["A"], e["I33"], e["I22"], e["J"], tuple(e.get("rel_i") or (False,) * 6), tuple(e.get("rel_j") or (False,) * 6))
            el.L, el.R = rotation(self.xyz[el.i], self.xyz[el.j])
            self.elements.append(el)
        self.el_index = {el.id: k for k, el in enumerate(self.elements)}
        self.supports = {self.index[k]: v for k, v in supports.items() if k in self.index}
        self.nodal_mass = nodal_mass or {}
        self._build_constraints(diaphragms or [])
        self.axial_pd: np.ndarray | None = None
        self._kc: dict[int, tuple[np.ndarray, np.ndarray]] = {}
        self._Kfull: sp.csr_matrix | None = None
        self.notes: list[str] = []
        self._factor()

    # ---- constraints (rigid diaphragms) ----------------------------------------------------
    def _build_constraints(self, diaphragms: list[dict[str, Any]]) -> None:
        slave_of: dict[int, int] = {}
        masters = []
        for d in diaphragms:
            ids = [self.index[n] for n in d["nodes"] if n in self.index and not any(self.supports.get(self.index[n], [False] * 6)[k] for k in (0, 1, 5))]
            if len(ids) < 2:
                continue
            w = np.array([self.nodal_mass.get(self.node_ids[i], 0.0) for i in ids])
            pts = self.xyz[ids]
            c = (w[:, None] * pts).sum(0) / w.sum() if w.sum() > 0 else pts.mean(0)
            masters.append({"name": d["name"], "xy": c[:2], "z": float(pts[:, 2].mean()), "nodes": ids})
            for i in ids:
                slave_of[i] = len(masters) - 1
        self.masters = masters
        rows, cols, vals = [], [], []
        nred = 0
        red_of_full: dict[int, int] = {}
        for i in range(self.nn):
            for k in range(6):
                if i in slave_of and k in (0, 1, 5):
                    continue
                red_of_full[6 * i + k] = nred
                rows.append(6 * i + k); cols.append(nred); vals.append(1.0)
                nred += 1
        self.master_dof = []
        for mi, m in enumerate(masters):
            base = nred
            self.master_dof.append((base, base + 1, base + 2))
            nred += 3
            for i in m["nodes"]:
                dx, dy = self.xyz[i, 0] - m["xy"][0], self.xyz[i, 1] - m["xy"][1]
                for r, c, v in ((6 * i, base, 1.0), (6 * i, base + 2, -dy), (6 * i + 1, base + 1, 1.0), (6 * i + 1, base + 2, dx), (6 * i + 5, base + 2, 1.0)):
                    rows.append(r); cols.append(c); vals.append(v)
        self.nred = nred
        self.T = sp.csr_matrix((vals, (rows, cols)), shape=(self.ndof, nred))
        fixed = set()
        for i, fl in self.supports.items():
            for k in range(6):
                if fl[k] and 6 * i + k in red_of_full:
                    fixed.add(red_of_full[6 * i + k])
        self.free = np.array([d for d in range(nred) if d not in fixed], dtype=int)

    # ---- assembly ---------------------------------------------------------------------------
    def _kl(self, n: int) -> tuple[np.ndarray, np.ndarray]:
        """(uncondensed local k, condensed local k) for element n under the current P-Delta axial forces (cached)."""
        c = self._kc.get(n)
        if c is None:
            el = self.elements[n]
            k = local_k(el, float(self.axial_pd[n]) if self.axial_pd is not None else 0.0)
            c = (k, condense(k, None, rel_list(el))[0])
            self._kc[n] = c
        return c

    def _element_k(self, el: Element, P: float = 0.0) -> np.ndarray:
        kl, _ = condense(local_k(el, P), None, rel_list(el))
        T = big_T(el.R)
        return T.T @ kl @ T

    def _assemble(self, axial: np.ndarray | None = None) -> sp.csr_matrix:
        rows, cols, vals = [], [], []
        for n, el in enumerate(self.elements):
            T = big_T(el.R)
            kg = T.T @ self._kl(n)[1] @ T
            dofs = np.r_[6 * el.i:6 * el.i + 6, 6 * el.j:6 * el.j + 6]
            rr, cc = np.meshgrid(dofs, dofs, indexing="ij")
            rows.append(rr.ravel()); cols.append(cc.ravel()); vals.append(kg.ravel())
        K = sp.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(self.ndof, self.ndof)) if rows else sp.csr_matrix((self.ndof, self.ndof))
        return K

    def _factor(self, axial: np.ndarray | None = None) -> None:
        K = self._assemble(axial)
        self._Kfull = K
        Kr = (self.T.T @ K @ self.T).tocsc()
        Kff = Kr[self.free][:, self.free].tocsc()
        diag = Kff.diagonal()
        kmax = float(np.abs(diag).max()) if diag.size else 1.0
        weak = np.where(np.abs(diag) < 1e-9 * kmax)[0]
        if weak.size:
            Kff = Kff + sp.csc_matrix((np.full(weak.size, 1e-6 * kmax), (weak, weak)), shape=Kff.shape)
            self.notes.append(f"{weak.size} DOFs had no stiffness (e.g. joints where every member is pinned) and were restrained by a tiny spring.")
        self.Kff = Kff
        try:
            self.lu = spla.splu(Kff)
        except RuntimeError as exc:
            raise EngineError("The structure is unstable (singular stiffness matrix): check supports, releases and connectivity.") from exc

    def set_pdelta(self, axial: np.ndarray) -> None:
        self.axial_pd = axial
        self._kc = {}
        self._factor(axial)

    # ---- loads and solution ---------------------------------------------------------------
    def element_loads(self, member_segs: dict[str, list[tuple[float, float, np.ndarray]]]) -> tuple[np.ndarray, dict[int, np.ndarray]]:
        """member_segs: id -> [(a, b, w_global[3])] with a,b in metres. Returns global F and local condensed eq loads."""
        F = np.zeros(self.ndof)
        eql: dict[int, tuple[np.ndarray, list]] = {}
        for mid, segs in member_segs.items():
            n = self.el_index.get(mid)
            if n is None:
                continue
            el = self.elements[n]
            lsegs = [(max(0.0, a), min(el.L, b), el.R @ np.asarray(w, float)) for a, b, w in segs]
            f = local_eq_loads(el.L, lsegs)
            _, fc = condense(self._kl(n)[0], f, rel_list(el))
            eql[n] = (fc, lsegs)
            fg = big_T(el.R).T @ fc
            F[6 * el.i:6 * el.i + 6] += fg[:6]
            F[6 * el.j:6 * el.j + 6] += fg[6:]
        return F, eql

    def solve(self, F_full: np.ndarray) -> np.ndarray:
        Fr = self.T.T @ F_full
        u = np.zeros(self.nred)
        u[self.free] = self.lu.solve(Fr[self.free])
        if not np.all(np.isfinite(u)) or (u.size and np.abs(u).max() > 1e4):
            raise EngineError("The structure is unstable (huge displacements): check supports, releases and connectivity.")
        return self.T @ u

    def end_forces(self, U: np.ndarray, eql: dict[int, tuple[np.ndarray, list]]) -> np.ndarray:
        out = np.zeros((len(self.elements), 12))
        for n, el in enumerate(self.elements):
            T = big_T(el.R)
            ue = np.r_[U[6 * el.i:6 * el.i + 6], U[6 * el.j:6 * el.j + 6]]
            kl = self._kl(n)[1]
            f = kl @ (T @ ue)
            if n in eql:
                f = f - eql[n][0]
            out[n] = f
        return out

    def stations(self, ends: np.ndarray, eql: dict[int, tuple[np.ndarray, list]]) -> np.ndarray:
        """Internal forces N, V2, V3, T, M2, M3 at N_STATIONS points per member -> (nel, ns, 6)."""
        res = np.zeros((len(self.elements), N_STATIONS, 6))
        for n, el in enumerate(self.elements):
            f = ends[n]
            segs = eql[n][1] if n in eql else []
            for s in range(N_STATIONS):
                x = el.L * s / (N_STATIONS - 1)
                iw = np.zeros(3)
                mw2 = mw3 = 0.0
                for a, b, w in segs:
                    bb = min(b, x)
                    if bb <= a:
                        continue
                    ln = bb - a
                    iw += w * ln
                    mom = (bb * bb - a * a) / 2 - x * ln
                    mw3 += mom * w[1]
                    mw2 += -mom * w[2]
                N = -(f[0] + iw[0])
                V2 = -(f[1] + iw[1])
                V3 = -(f[2] + iw[2])
                Tq = -f[3]
                M3 = -(f[5] + (-x) * f[1] + mw3)
                M2 = -(f[4] - (-x) * f[2] + mw2)
                res[n, s] = (N, V2, V3, Tq, M2, M3)
        return res

    def reactions(self, U: np.ndarray, F_full: np.ndarray) -> np.ndarray:
        K = self._Kfull if self._Kfull is not None else self._assemble(self.axial_pd)
        return K @ U - F_full

    # ---- modal ------------------------------------------------------------------------------
    def mass_full(self) -> sp.csr_matrix:
        m = np.zeros(self.ndof)
        for nid, mass in self.nodal_mass.items():
            i = self.index.get(nid)
            if i is not None and mass > 0:
                m[6 * i] += mass
                m[6 * i + 1] += mass
        return sp.diags(m).tocsr()

    def modal(self, n_modes: int = 12) -> dict[str, Any]:
        Mf = self.mass_full()
        Mr = (self.T.T @ Mf @ self.T).tocsc()[self.free][:, self.free].tocsc()
        n_mass = int((Mr.diagonal() > 0).sum())
        if n_mass == 0:
            raise EngineError("No seismic mass: modal analysis needs dead/live loads or self-weight.")
        nf = self.Kff.shape[0]
        md = Mr.diagonal()
        mi = np.where(md > 0)[0]
        oi = np.where(md <= 0)[0]
        if mi.size <= 1500:
            # exact static condensation of the massless DOFs (sparse LU), then a dense eigen solve
            k = max(1, min(n_modes, mi.size))
            K = self.Kff.tocsc()
            Kmm = K[mi][:, mi].toarray()
            if oi.size:
                Koo = K[oi][:, oi].tocsc()
                Kom = K[oi][:, mi].toarray()
                X = spla.splu(Koo).solve(Kom)
                Kc = Kmm - K[mi][:, oi] @ X
            else:
                X = None
                Kc = Kmm
            Kc = 0.5 * (Kc + Kc.T)
            Mc = Mr[mi][:, mi].toarray()
            w2, vec = sla.eigh(Kc, Mc)
            order = np.argsort(w2)[:k]
            w2, vec = w2[order], vec[:, order]
            phi = np.zeros((nf, len(w2)))
            phi[mi] = vec
            if oi.size:
                phi[oi] = -X @ vec
        else:
            k = max(1, min(n_modes, n_mass - 1))
            w2, phi = spla.eigsh(self.Kff, k=k, M=Mr, sigma=0.0, which="LM", ncv=min(nf, max(4 * k + 1, 40)), maxiter=nf * 20)
            order = np.argsort(w2)
            w2, phi = w2[order], phi[:, order]
        w2 = np.maximum(w2, 1e-12)
        rx = np.zeros(self.ndof); rx[0::6] = 1.0
        ry = np.zeros(self.ndof); ry[1::6] = 1.0
        # influence vectors in reduced space: masters take 1 on their ux/uy
        Rx = np.zeros(self.nred); Ry = np.zeros(self.nred)
        TT = self.T.tocsc()
        for d in range(self.nred):
            col = TT.getcol(d)
            for r, v in zip(col.indices, col.data):
                if r % 6 == 0 and abs(v - 1) < 1e-12:
                    Rx[d] = 1.0
                if r % 6 == 1 and abs(v - 1) < 1e-12:
                    Ry[d] = 1.0
        Rx, Ry = Rx[self.free], Ry[self.free]
        modes = []
        Mtot_x = float(Rx @ (Mr @ Rx)); Mtot_y = float(Ry @ (Mr @ Ry))
        cum_x = cum_y = 0.0
        for n in range(len(w2)):
            ph = phi[:, n]
            mn = float(ph @ (Mr @ ph))
            lx, ly = float(ph @ (Mr @ Rx)), float(ph @ (Mr @ Ry))
            ex, ey = lx * lx / mn, ly * ly / mn
            cum_x += ex; cum_y += ey
            w = math.sqrt(w2[n])
            modes.append({"mode": n + 1, "omega": w, "T": 2 * math.pi / w, "f": w / (2 * math.pi),
                          "gamma_x": lx / mn, "gamma_y": ly / mn,
                          "mass_ratio_x": ex / Mtot_x if Mtot_x else 0.0, "mass_ratio_y": ey / Mtot_y if Mtot_y else 0.0,
                          "cum_x": cum_x / Mtot_x if Mtot_x else 0.0, "cum_y": cum_y / Mtot_y if Mtot_y else 0.0})
        self._phi = phi
        return {"modes": modes, "total_mass_t": Mtot_x, "phi": phi}

    def mode_full(self, n: int) -> np.ndarray:
        u = np.zeros(self.nred)
        u[self.free] = self._phi[:, n]
        return self.T @ u


def cqc(values: np.ndarray, omegas: np.ndarray, zeta: float = 0.05) -> np.ndarray:
    """values: (n_modes, ...) modal responses -> CQC combined (abs)."""
    nm = values.shape[0]
    rho = np.zeros((nm, nm))
    for i in range(nm):
        for j in range(nm):
            r = omegas[j] / omegas[i]
            rho[i, j] = 8 * zeta**2 * (1 + r) * r**1.5 / ((1 - r * r) ** 2 + 4 * zeta**2 * r * (1 + r) ** 2)
    flat = values.reshape(nm, -1)
    tot = np.einsum("ik,ij,jk->k", flat, rho, flat)
    return np.sqrt(np.maximum(tot, 0.0)).reshape(values.shape[1:])
