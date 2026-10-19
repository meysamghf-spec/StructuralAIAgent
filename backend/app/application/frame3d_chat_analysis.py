"""Chat-driven analysis of a regular 3D RC moment-frame building.

Phase 1 of the ETABS-comparison roadmap. A plain-language request (English or
Persian keywords) is parsed deterministically (works with AI_PROVIDER=stub), a
regular grid frame is generated and solved with the in-repo verified
``frame3d_solver`` (linear elastic, direct stiffness, rigid diaphragms), and a
result card payload (``kind == "frame3d_analysis"``) is returned.

Extension points (not implemented yet, by design):
- ``seismic_code``: how the lateral coefficient C is obtained. Only
  ``"ASSUMED_C"`` (user supplied C) exists today. An Iranian Standard 2800
  provider (C = ABI/R from zone/soil/importance/system, later response
  spectrum) plugs into ``SEISMIC_PROVIDERS``.
- ``design_code``: member design. Only ``"NONE"`` (analysis only) today. A
  Mabhas 9 / ACI 318 design module consumes ``envelopes`` in the payload.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Callable

from app.application import iran2800
from app.application.analysis.modal import combine_cqc, generalized_eigen_diag_mass
from app.application.analysis.linear_algebra import factor_linear_system
from app.application.analysis.frame3d_solver import (
    DOF_PER_NODE,
    RigidDiaphragm,
    SpaceElement,
    SpaceFrameModel,
    SpaceFrameSolverError,
    SpaceNodalLoad,
    SpaceNode,
    SpaceSupport,
    assemble_space_system,
    recover_space_result,
    torsion_constant_rectangle,
)

KIND = "frame3d_analysis"
DISCLAIMER = (
    "Linear elastic 3D frame analysis with the internal StructuralAIAgent solver. "
    "Seismic load uses the user-supplied coefficient C (equivalent static); "
    "no Iranian Standard 2800 or Mabhas 9 checks are performed yet. Final "
    "engineering decisions require verification by a qualified engineer."
)
DISCLAIMER_2800 = (
    "Linear elastic 3D frame analysis with the internal StructuralAIAgent solver. Seismic loads follow "
    "Standard 2800 (4th ed.) as implemented here (equivalent static + response spectrum, simplifications "
    "listed under Assumptions). Not a certified code check; final engineering decisions require "
    "verification by a qualified engineer."
)


def _code_label(inp: "Frame3dInputs") -> str:
    seismic = "Standard 2800 (4th ed.) seismic loads" if inp.seismic_code == "IRAN_2800" else "user-supplied seismic C (no Standard 2800)"
    design = "Mabhas 9 RC design (simplified, see clauses)" if inp.design_code == "MABHAS9" else "no member design (no Mabhas 9 checks)"
    return f"Analysis with {seismic}; {design}"


MAX_STOREYS = 10
MAX_BAYS = 6
MAX_NODES = 220  # keeps the dense pure-Python solve within a few seconds

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
_NUM = r"(\d+(?:\.\d+)?)"


# --------------------------------------------------------------------------- inputs
@dataclass
class Frame3dInputs:
    storeys: int | None = None
    bays_x: int | None = None
    bays_y: int | None = None
    bay_x_m: float = 5.0
    bay_y_m: float = 5.0
    storey_height_m: float = 3.2
    column_b_m: float = 0.40
    column_h_m: float = 0.40
    beam_b_m: float = 0.30
    beam_h_m: float = 0.45
    slab_t_m: float = 0.12
    fc_mpa: float = 30.0
    fy_mpa: float = 400.0
    dead_kn_m2: float = 6.0
    live_kn_m2: float = 2.0
    roof_live_kn_m2: float = 1.5
    wall_kn_m: float = 7.0
    parapet_kn_m: float = 2.0
    seismic_code: str = "ASSUMED_C"
    seismic_c: float | None = None
    behaviour_r: float = 5.0
    accidental_ecc: float = 0.05
    design_code: str = "NONE"
    # Standard 2800 parameters (used when seismic_code == "IRAN_2800")
    zone: str = "HIGH"
    soil: str = "II"
    importance: float = 1.0
    system: str = "RC_IMF"
    irregular: bool = False
    parsed: list[str] = field(default_factory=list)


def _norm(text: str) -> str:
    return (text or "").translate(_PERSIAN_DIGITS).replace("×", "x").replace("*", "x")


def is_frame3d_request(user_request: str) -> bool:
    t = _norm(user_request).lower()
    storey = re.search(r"stor(e)?y|stories|storeys|floors?\b|طبقه", t)
    frame = re.search(r"\bframe\b|\bbays?\b|قاب|دهانه|3d|سه ?بعدی", t)
    return bool(storey and frame)


def _f(t: str, pats: tuple[str, ...], inp: Frame3dInputs, name: str, scale: float = 1.0, flags: int = re.IGNORECASE) -> None:
    for p in pats:
        m = re.search(p, t, flags=flags)
        if m:
            setattr(inp, name, float(m.group(1)) * scale)
            inp.parsed.append(name)
            return


def _section(t: str, words: str, inp: Frame3dInputs, b: str, h: str) -> None:
    m = re.search(rf"(?:{words})[^\d]{{0,20}}{_NUM}\s*x\s*{_NUM}\s*(mm|cm|m)?", t, flags=re.IGNORECASE)
    if not m:
        return
    unit = (m.group(3) or "cm").lower()
    s = {"mm": 0.001, "cm": 0.01, "m": 1.0}[unit]
    setattr(inp, b, float(m.group(1)) * s)
    setattr(inp, h, float(m.group(2)) * s)
    inp.parsed += [b, h]


def parse_frame3d_request(user_request: str) -> Frame3dInputs:
    t = _norm(user_request)
    inp = Frame3dInputs()
    m = re.search(r"(\d+)\s*-?\s*(?:stor(?:e)?y|stories|storeys|floors?|طبقه)", t, re.I)
    if m:
        inp.storeys = int(m.group(1)); inp.parsed.append("storeys")
    m = re.search(r"(\d+)\s*x\s*(\d+)\s*(?:bays?|دهانه)", t, re.I) or re.search(
        r"(?:bays?|دهانه)\s*[:=]?\s*(\d+)\s*x\s*(\d+)", t, re.I)
    if m:
        inp.bays_x, inp.bays_y = int(m.group(1)), int(m.group(2)); inp.parsed += ["bays_x", "bays_y"]
    else:
        mx = re.search(r"(\d+)\s*bays?\s*(?:in|along)\s*x", t, re.I)
        my = re.search(r"(\d+)\s*bays?\s*(?:in|along)\s*y", t, re.I)
        if mx: inp.bays_x = int(mx.group(1)); inp.parsed.append("bays_x")
        if my: inp.bays_y = int(my.group(1)); inp.parsed.append("bays_y")
    m = re.search(rf"bays?\s*(?:of|=|:)?\s*{_NUM}\s*m\b", t, re.I) or re.search(rf"دهانه[^\d]{{0,10}}{_NUM}\s*(?:m|متر)", t)
    if m:
        inp.bay_x_m = inp.bay_y_m = float(m.group(1)); inp.parsed += ["bay_x_m", "bay_y_m"]
    _f(t, (rf"bay\s*(?:width|length|span)?\s*(?:in\s*)?x\s*[:=]?\s*{_NUM}\s*m",), inp, "bay_x_m")
    _f(t, (rf"bay\s*(?:width|length|span)?\s*(?:in\s*)?y\s*[:=]?\s*{_NUM}\s*m",), inp, "bay_y_m")
    _f(t, (rf"(?:stor(?:e)?y|floor)\s*height\s*(?:of|=|:)?\s*{_NUM}\s*m", rf"ارتفاع\s*طبقه[^\d]{{0,10}}{_NUM}"), inp, "storey_height_m")
    _section(t, "columns?|ستون", inp, "column_b_m", "column_h_m")
    _section(t, "beams?|تیر", inp, "beam_b_m", "beam_h_m")
    _f(t, (rf"slab\s*(?:thickness)?\s*(?:of|=|:)?\s*{_NUM}\s*cm",), inp, "slab_t_m", 0.01)
    _f(t, (rf"f'?\s*c\s*[:=]?\s*{_NUM}", rf"f[’′]c\s*[:=]?\s*{_NUM}"), inp, "fc_mpa")
    _f(t, (rf"\bfy\s*[:=]?\s*{_NUM}",), inp, "fy_mpa")
    _f(t, (rf"dead\s*load\s*(?:of|=|:)?\s*{_NUM}", rf"بار\s*مرده[^\d]{{0,10}}{_NUM}"), inp, "dead_kn_m2")
    _f(t, (rf"(?<!roof )live\s*load\s*(?:of|=|:)?\s*{_NUM}", rf"بار\s*زنده[^\d]{{0,10}}{_NUM}"), inp, "live_kn_m2")
    _f(t, (rf"roof\s*live\s*load\s*(?:of|=|:)?\s*{_NUM}",), inp, "roof_live_kn_m2")
    _f(t, (rf"wall\s*load\s*(?:of|=|:)?\s*{_NUM}",), inp, "wall_kn_m")
    _f(t, (rf"parapet\s*(?:load)?\s*(?:of|=|:)?\s*{_NUM}",), inp, "parapet_kn_m")
    _f(t, (rf"(?<![A-Za-z'’′])C\s*[:=]\s*{_NUM}", rf"(?i:seismic|base shear)\s*(?i:coefficient)\s*(?:of|=|:)?\s*{_NUM}", rf"ضریب\s*زلزله[^\d]{{0,10}}{_NUM}"), inp, "seismic_c", flags=0)
    _f(t, (rf"(?<![A-Za-z'’′])R\s*[:=]\s*{_NUM}", rf"(?i:behaviou?r|response modification)\s*(?i:factor|coefficient)\s*(?:of|=|:)?\s*{_NUM}"), inp, "behaviour_r", flags=0)
    found = iran2800.parse_2800(t)
    for key, value in found.items():
        setattr(inp, key, value); inp.parsed.append(key)
    if found.keys() & {"zone", "soil"} or iran2800.wants_2800(t):
        inp.seismic_code = "IRAN_2800"
    if re.search(r"mabhas|مبحث\s*(?:9|نهم)|\bdesign\b|طراحی", t, re.I):
        inp.design_code = "MABHAS9"
    return inp


# --------------------------------------------------------------------------- seismic providers
SeismicProvider = Callable[[Frame3dInputs, dict[str, Any]], tuple[float | None, dict[str, Any]]]


def _iran_2800(inp: Frame3dInputs, ctx: dict[str, Any]) -> tuple[float | None, dict[str, Any]]:
    info = iran2800.equivalent_static(zone=inp.zone, soil=inp.soil, importance=inp.importance, system=inp.system,
                                      height_m=ctx["H"], storeys=inp.storeys)
    info["dynamic_scale_min"] = 0.90 if inp.irregular else 0.85
    info["regularity"] = "irregular" if inp.irregular else "regular (assumed)"
    return info["C"], info


def _assumed_c(inp: Frame3dInputs, ctx: dict[str, Any]) -> tuple[float | None, dict[str, Any]]:
    return inp.seismic_c, {
        "method": "Equivalent static, user-supplied base shear coefficient C",
        "C": inp.seismic_c,
        "vertical_distribution": "F_i = V·W_i·h_i / Σ W_j·h_j (linear mode shape, k=1)",
        "accidental_eccentricity": f"{inp.accidental_ecc:.0%} of plan dimension",
        "seismic_weight": "D + 0.2·L (assumed)",
        "iranian_2800": False,
        "k": 1.0,
        "drift_factor": 0.7 * inp.behaviour_r, "drift_factor_label": f"0.7R (R={inp.behaviour_r:g})",
        "drift_limit": 0.025,
    }


SEISMIC_PROVIDERS: dict[str, SeismicProvider] = {"ASSUMED_C": _assumed_c, "IRAN_2800": _iran_2800}


# --------------------------------------------------------------------------- analysis
def _nid(i: int, j: int, k: int) -> str:
    return f"N{i}_{j}_{k}"


def _matvec(a, v):
    return [sum(x * y for x, y in zip(row, v)) for row in a]


def run_frame3d(inp: Frame3dInputs) -> dict[str, Any]:
    nx, ny, ns = inp.bays_x, inp.bays_y, inp.storeys
    XS = [i * inp.bay_x_m for i in range(nx + 1)]
    YS = [j * inp.bay_y_m for j in range(ny + 1)]
    Z = [k * inp.storey_height_m for k in range(ns + 1)]
    fc, h = inp.fc_mpa, inp.storey_height_m
    Ec = 4700 * math.sqrt(fc) * 1000  # kN/m2
    cb, ch, bb, bh = inp.column_b_m, inp.column_h_m, inp.beam_b_m, inp.beam_h_m
    Ac = cb * ch; Icy = cb * ch**3 / 12 * 0.70; Icz = ch * cb**3 / 12 * 0.70
    Jc = torsion_constant_rectangle(cb, ch) * 0.15
    Ab = bb * bh; Iby = bb * bh**3 / 12 * 0.35; Ibz = bh * bb**3 / 12 * 0.35
    Jb = torsion_constant_rectangle(bb, bh) * 0.15
    sw_beam = bb * max(bh - inp.slab_t_m, 0.0) * 25.0
    sw_col = Ac * h * 25.0
    live = {k: (inp.roof_live_kn_m2 if k == ns else inp.live_kn_m2) for k in range(1, ns + 1)}
    wall = {k: (inp.parapet_kn_m if k == ns else inp.wall_kn_m) for k in range(1, ns + 1)}

    nodes = [SpaceNode(_nid(i, j, k), x, y, z, level_id=f"L{k}")
             for k, z in enumerate(Z) for i, x in enumerate(XS) for j, y in enumerate(YS)]
    P = {n.id: (n.x, n.y, n.z) for n in nodes}
    beams = []  # (id, a, b, k, length, trib_width_one_side_count, edge)
    for k in range(1, ns + 1):
        for i in range(nx + 1):
            for j in range(ny + 1):
                if i < nx:
                    edge = j in (0, ny)
                    beams.append((f"BX{i}_{j}_{k}", _nid(i, j, k), _nid(i + 1, j, k), k, inp.bay_x_m, inp.bay_y_m, edge))
                if j < ny:
                    edge = i in (0, nx)
                    beams.append((f"BY{i}_{j}_{k}", _nid(i, j, k), _nid(i, j + 1, k), k, inp.bay_y_m, inp.bay_x_m, edge))
    cols = [(f"C{i}_{j}_{k}", _nid(i, j, k - 1), _nid(i, j, k), k)
            for k in range(1, ns + 1) for i in range(nx + 1) for j in range(ny + 1)]

    def tributary(L: float, other: float) -> float:
        # two-way slab: triangular (short side) / trapezoidal share, equivalent UDL per panel side
        s, l = min(L, other), max(L, other)
        if L <= other:
            return s / 3.0
        m = s / l
        return s / 2.0 * (3 - m * m) / 3.0

    def beam_w(case: str, k: int, L: float, other: float, edge: bool) -> float:
        panels = 1 if edge else 2
        if case == "D":
            return panels * inp.dead_kn_m2 * tributary(L, other) + sw_beam + (wall[k] if edge else 0.0)
        if case == "L":
            return panels * live[k] * tributary(L, other)
        return 0.0

    supports = [SpaceSupport(_nid(i, j, 0)) for i in range(nx + 1) for j in range(ny + 1)]
    cx, cy = XS[-1] / 2, YS[-1] / 2
    diaphragms = [RigidDiaphragm(f"D{k}", f"L{k}", tuple(_nid(i, j, k) for i in range(nx + 1) for j in range(ny + 1)), cx, cy)
                  for k in range(1, ns + 1)]
    ncol_lvl = (nx + 1) * (ny + 1)
    W: dict[int, float] = {}
    for k in range(1, ns + 1):
        wD = sum(beam_w("D", k, L, o, e) * L for _, _, _, kk, L, o, e in beams if kk == k) + ncol_lvl * sw_col * (0.5 if k == ns else 1.0)
        wL = sum(beam_w("L", k, L, o, e) * L for _, _, _, kk, L, o, e in beams if kk == k)
        W[k] = wD + 0.2 * wL

    provider = SEISMIC_PROVIDERS.get(inp.seismic_code)
    if provider is None:
        raise ValueError(f"Seismic code '{inp.seismic_code}' is not available yet")
    C, seismic_info = provider(inp, {"H": Z[-1]})
    W_tot = sum(W.values())
    V = (C or 0.0) * W_tot
    kexp = seismic_info.get("k", 1.0)
    swh = sum(W[k] * Z[k] ** kexp for k in W)
    F = {k: V * W[k] * Z[k] ** kexp / swh for k in W}
    ecc_x, ecc_y = inp.accidental_ecc * YS[-1], inp.accidental_ecc * XS[-1]
    # lateral load applied at the node nearest the plan centre (rigid diaphragm transfers it)
    ci, cj = min(range(nx + 1), key=lambda i: abs(XS[i] - cx)), min(range(ny + 1), key=lambda j: abs(YS[j] - cy))
    dxc, dyc = XS[ci] - cx, YS[cj] - cy

    def model(case: str) -> SpaceFrameModel:
        els = [SpaceElement(cid, a, b, Ec, Ac, Icy, Icz, Jc, metadata={"type": "column"}) for cid, a, b, _ in cols]
        els += [SpaceElement(bid, a, b, Ec, Ab, Iby, Ibz, Jb, udl_gz=-beam_w(case, k, L, o, e), metadata={"type": "beam"})
                for bid, a, b, k, L, o, e in beams]
        nl: list[SpaceNodalLoad] = []
        if case == "D":
            nl = [SpaceNodalLoad(b, fz=-sw_col) for _, _, b, _ in cols]
        elif case == "Ex":
            nl = [SpaceNodalLoad(_nid(ci, cj, k), fx=F[k], mz=F[k] * (ecc_x + dyc)) for k in F]  # load at mass centre + e
        elif case == "Ey":
            nl = [SpaceNodalLoad(_nid(ci, cj, k), fy=F[k], mz=-F[k] * (ecc_y + dxc)) for k in F]
        return SpaceFrameModel(f"frame3d-{case}", nodes, els, supports, nl, diaphragms)

    cases = ["D", "L"] + (["Ex", "Ey"] if V > 0 else [])
    base: dict[str, dict[str, Any]] = {}
    equilibrium: dict[str, float] = {}
    lateral_prep: dict[str, Any] = {}
    for case in cases:
        m = model(case)
        if case in ("Ex", "Ey"):  # same stiffness, no member loads: assemble/factor once
            if "prep" not in lateral_prep:
                lateral_prep["prep"] = assemble_space_system(m); lateral_prep["model"] = m
            prep = lateral_prep["prep"]
        else:
            prep = assemble_space_system(m)
        lv = list(prep["gravity_load"])
        idx = prep["node_index"]
        for ld in m.nodal_loads:
            b0 = idx[ld.node_id] * DOF_PER_NODE
            for o, v in enumerate((ld.fx, ld.fy, ld.fz, ld.mx, ld.my, ld.mz)):
                lv[b0 + o] += v
        r = recover_space_result(m, prep, lv)
        ends, wloc = {}, {}
        for e in m.elements:
            lk, fl, dofs, _L, T = prep["element_cache"][e.id]
            u_el = []
            for d in dofs:
                nd = nodes[d // DOF_PER_NODE].id
                u_el.append(r.displacements[nd][d % DOF_PER_NODE])
            ul = _matvec(T, u_el)
            ends[e.id] = [a + b for a, b in zip(_matvec(lk, ul), fl)]
            T3 = [row[:3] for row in T[:3]]
            wloc[e.id] = _matvec(T3, [e.udl_gx, e.udl_gy, e.udl_gz])
        applied = [sum(getattr(l, c) for l in m.nodal_loads) for c in ("fx", "fy", "fz")]
        for e in m.elements:
            L = math.dist(P[e.start_node_id], P[e.end_node_id])
            applied = [applied[0] + e.udl_gx * L, applied[1] + e.udl_gy * L, applied[2] + e.udl_gz * L]
        reac = [sum(r.reactions[s.node_id][c] for s in supports) for c in range(3)]
        equilibrium[case] = max(abs(a + b) for a, b in zip(applied, reac))
        base[case] = {"res": r, "ends": ends, "w": wloc, "reac": reac}

    combos: dict[str, dict[str, float]] = {"1.4D": {"D": 1.4}, "1.2D+1.6L": {"D": 1.2, "L": 1.6}}
    if V > 0:
        for s in (1, -1):
            for E in ("Ex", "Ey"):
                sg = "+" if s > 0 else "-"
                combos[f"1.2D+1.0L{sg}{E}"] = {"D": 1.2, "L": 1.0, E: s}
                combos[f"0.9D{sg}{E}"] = {"D": 0.9, E: s}

    def comb_vec(cf, key, eid):
        out = None
        for c, v in cf.items():
            vec = base[c][key][eid]
            out = [v * x for x in vec] if out is None else [o + v * x for o, x in zip(out, vec)]
        return out

    def beam_curve(cf, eid, L, n=41):
        f = comb_vec(cf, "ends", eid); w = comb_vec(cf, "w", eid)
        xs = [L * i / (n - 1) for i in range(n)]
        M = [f[4] + x * f[2] + w[2] * x * x / 2 for x in xs]
        Vv = [f[2] + w[2] * x for x in xs]
        return M, Vv

    beam_env = []
    for bid, a, b, k, L, o, e in beams:
        M0, _ = beam_curve(combos["1.4D"], bid, L)
        s0 = 1.0 if M0[len(M0) // 2] >= 0 else -1.0
        sag = hog = vmax = 0.0; gov = {}
        neg_end = pos_end = pos_mid = 0.0
        for cn, cf in combos.items():
            M, Vv = beam_curve(cf, bid, L)
            ms, mh, vm = max(s0 * x for x in M), max(-s0 * x for x in M), max(abs(x) for x in Vv)
            ends_m = (s0 * M[0], s0 * M[-1])
            neg_end = max(neg_end, -min(ends_m)); pos_end = max(pos_end, max(ends_m))
            pos_mid = max(pos_mid, max(s0 * x for x in M[len(M) // 3: 2 * len(M) // 3 + 1]))
            if ms > sag: sag, gov["M_pos"] = ms, cn
            if mh > hog: hog, gov["M_neg"] = mh, cn
            if vm > vmax: vmax, gov["V"] = vm, cn
        beam_env.append({"id": bid, "storey": k, "direction": bid[1], "position": "edge" if e else "interior",
                         "M_neg_kn_m": hog, "M_pos_kn_m": sag, "V_kn": vmax, "governing": gov,
                         "M_neg_end_kn_m": neg_end, "M_pos_end_kn_m": pos_end, "M_pos_mid_kn_m": pos_mid, "length_m": L})
    col_env = []
    for cid, a, b, k in cols:
        pmax = mmax = 0.0; gov = {}; recs = []
        ii, jj = (int(x) for x in cid[1:].split("_")[:2])
        on_x, on_y = ii in (0, nx), jj in (0, ny)
        position = "corner" if on_x and on_y else "edge" if on_x or on_y else "interior"
        for cn, cf in combos.items():
            f = comb_vec(cf, "ends", cid)
            recs.append({"combo": cn, "seismic": "E" in cn, "P": f[0],
                         "ends": [(abs(f[4]), abs(f[5])), (abs(f[10]), abs(f[11]))]})
            pu = f[0] if f[0] > 0 else 0.0
            mu = max(abs(f[4]), abs(f[5]), abs(f[10]), abs(f[11]))
            if pu > pmax: pmax, gov["P"] = pu, cn
            if mu > mmax: mmax, gov["M"] = mu, cn
        col_env.append({"id": cid, "storey": k, "P_kn": pmax, "M_kn_m": mmax, "governing": gov,
                        "position": position, "i": ii, "j": jj, "records": recs})

    drift = []
    if V > 0:
        cd = seismic_info.get("drift_factor", 0.7 * inp.behaviour_r)
        for E, ax in (("Ex", 0), ("Ey", 1)):
            prev = 0.0
            for k in range(1, ns + 1):
                um = max(abs(base[E]["res"].displacements[_nid(i, j, k)][ax]) for i in range(nx + 1) for j in range(ny + 1))
                d = um - prev; prev = um
                drift.append({"direction": E[1].upper(), "storey": k, "u_max_mm": um * 1000, "drift_elastic_mm": d * 1000,
                              "ratio_elastic": d / h, "ratio_amplified": cd * d / h})
    base_shear = None
    if V > 0:
        base_shear = {
            "W_total_kn": W_tot, "C": C, "V_expected_kn": V,
            "V_reaction_x_kn": abs(base["Ex"]["reac"][0]), "V_reaction_y_kn": abs(base["Ey"]["reac"][1]),
        }
        base_shear["error_pct"] = 100 * max(abs(base_shear["V_reaction_x_kn"] - V), abs(base_shear["V_reaction_y_kn"] - V)) / V
    modal = None
    if V > 0 and inp.seismic_code == "IRAN_2800":
        modal = _modal_response_spectrum(inp, lateral_prep, nodes, XS, YS, Z, W, (ci, cj, dxc, dyc), V, seismic_info)
    total_gravity = abs(base["D"]["reac"][2]) + abs(base["L"]["reac"][2])
    return {
        "geometry": {"XS": XS, "YS": YS, "Z": Z},
        "model": {"nodes": len(nodes), "elements": len(cols) + len(beams), "columns": len(cols), "beams": len(beams),
                  "dof": base["D"]["res"].dof_count, "Ec_mpa": Ec / 1000},
        "W_level_kn": W, "F_level_kn": F, "seismic": seismic_info,
        "combos": list(combos), "equilibrium_error_kn": max(equilibrium.values()),
        "gravity_reaction_kn": {"D": abs(base["D"]["reac"][2]), "L": abs(base["L"]["reac"][2]), "D+L": total_gravity},
        "beams": beam_env, "columns": col_env, "drift": drift, "base_shear": base_shear, "modal": modal,
    }


G = 9.81


def _modal_response_spectrum(inp, lateral_prep, nodes, XS, YS, Z, W, centre, V_static, info) -> dict[str, Any]:
    """Modal + response-spectrum analysis on the diaphragm DOFs (ux, uy, rz per storey).

    Lateral stiffness is condensed from the full 3D model by unit loads at each diaphragm
    centre (exact static condensation for massless joints). Storey masses W/g with polar
    inertia m(Lx²+Ly²)/12 about the plan centre (uniform mass distribution assumed).
    """
    ci, cj, dxc, dyc = centre
    prep, model = lateral_prep["prep"], lateral_prep["model"]
    idx = prep["node_index"]
    ns = len(Z) - 1
    nx, ny = len(XS) - 1, len(YS) - 1
    n = 3 * ns

    def solve(forces: list[float]):
        lv = [0.0] * prep["n_full"]
        for k in range(1, ns + 1):
            fx, fy, mz = forces[3 * (k - 1): 3 * k]
            b0 = idx[_nid(ci, cj, k)] * DOF_PER_NODE
            lv[b0] += fx; lv[b0 + 1] += fy; lv[b0 + 5] += mz + fx * dyc - fy * dxc
        return recover_space_result(model, prep, lv)

    def centre_disp(r) -> list[float]:
        out = []
        for k in range(1, ns + 1):
            ux, uy, _, _, _, rz = r.displacements[_nid(ci, cj, k)]
            out += [ux + rz * dyc, uy - rz * dxc, rz]
        return out

    flex = [[0.0] * n for _ in range(n)]
    for col in range(n):
        unit = [0.0] * n; unit[col] = 1.0
        d = centre_disp(solve(unit))
        for row in range(n):
            flex[row][col] = d[row]
    flex = [[0.5 * (flex[i][j] + flex[j][i]) for j in range(n)] for i in range(n)]
    lu = factor_linear_system(flex)
    cols_k = [lu.solve([1.0 if i == j else 0.0 for i in range(n)]) for j in range(n)]
    stiff = [[cols_k[j][i] for j in range(n)] for i in range(n)]
    lx, ly = XS[-1], YS[-1]
    mass = []
    for k in range(1, ns + 1):
        m = W[k] / G
        mass += [m, m, m * (lx * lx + ly * ly) / 12.0]
    modes = generalized_eigen_diag_mass(stiff, mass)
    m_tot = sum(W.values()) / G
    rows = []
    omegas = []
    for w2, phi in modes:
        w = math.sqrt(max(w2, 1e-12)); omegas.append(w)
        T = 2 * math.pi / w
        part = {}
        for name, off in (("X", 0), ("Y", 1), ("RZ", 2)):
            l = sum(mass[i] * phi[i] for i in range(off, n, 3))
            denom = sum(mass[i] for i in range(off, n, 3))
            part[name] = l * l / denom
        rows.append({"T": T, "phi": phi, "part": part})
    cum = {"X": 0.0, "Y": 0.0, "RZ": 0.0}
    mode_table = []
    for i, r in enumerate(rows):
        for key in cum:
            cum[key] += r["part"][key]
        mode_table.append({"mode": i + 1, "T_s": r["T"], "mass_x_pct": 100 * r["part"]["X"], "mass_y_pct": 100 * r["part"]["Y"],
                           "mass_rz_pct": 100 * r["part"]["RZ"], "cum_x_pct": 100 * cum["X"], "cum_y_pct": 100 * cum["Y"]})
    a, I, R = info["A"], info["I"], info["R"]
    rs = {}
    for dname, off in (("X", 0), ("Y", 1)):
        shears, drifts_modes = [], []
        for r in rows:
            phi = r["phi"]
            gamma = sum(mass[i] * phi[i] for i in range(off, n, 3))  # φᵀMφ = 1
            sa = a * iran2800.spectral_b(r["T"], inp.soil, inp.zone) * I / R * G
            forces = [mass[i] * phi[i] * gamma * sa for i in range(n)]
            res = solve(forces)
            shears.append(sum(forces[off::3]))
            # inter-storey drift (max over plan nodes) per storey, signed per node
            per_storey = []
            for k in range(1, ns + 1):
                vals = []
                for ii in range(nx + 1):
                    for jj in range(ny + 1):
                        top = res.displacements[_nid(ii, jj, k)][off]
                        bot = res.displacements[_nid(ii, jj, k - 1)][off] if k > 1 else 0.0
                        vals.append(top - bot)
                per_storey.append(vals)
            drifts_modes.append(per_storey)
        v_dyn = combine_cqc(shears, omegas)
        scale = max(1.0, info["dynamic_scale_min"] * V_static / v_dyn) if v_dyn > 0 else 1.0
        drift_rows = []
        h = Z[1] - Z[0]
        for k in range(ns):
            n_nodes = len(drifts_modes[0][k])
            worst = max(combine_cqc([dm[k][p] for dm in drifts_modes], omegas) for p in range(n_nodes))
            de = worst * scale
            drift_rows.append({"storey": k + 1, "drift_elastic_mm": de * 1000, "ratio_elastic": de / h,
                               "ratio_amplified": info["drift_factor"] * de / h})
        rs[dname] = {"V_dynamic_kn": v_dyn, "V_static_kn": V_static, "ratio": v_dyn / V_static,
                     "scale_factor": scale, "V_dynamic_scaled_kn": v_dyn * scale, "drift": drift_rows}
    modes_90 = {key: next((m["mode"] for m in mode_table if m[f"cum_{key.lower()}_pct"] >= 90.0), None) for key in ("X", "Y")}
    return {"method": "Modal (condensed diaphragm DOFs) + Standard 2800 design spectrum A·B·I/R, CQC (5% damping)",
            "modes": mode_table, "modes_for_90pct": modes_90, "response_spectrum": rs,
            "T_fundamental_s": mode_table[0]["T_s"] if mode_table else None}


# --------------------------------------------------------------------------- payload
_LABELS = {
    "storeys": "number of storeys", "bays_x": "number of bays in X", "bays_y": "number of bays in Y",
}


def missing_inputs(inp: Frame3dInputs) -> list[str]:
    return [name for name in ("storeys", "bays_x", "bays_y") if getattr(inp, name) is None]


def _r(v: float, n: int = 2) -> float:
    return round(float(v), n)


def build_frame3d_payload(user_request: str) -> dict[str, Any] | None:
    if not is_frame3d_request(user_request):
        return None
    inp = parse_frame3d_request(user_request)
    inputs = {k: v for k, v in asdict(inp).items() if k != "parsed"}
    defaulted = [k for k in inputs if k not in inp.parsed and k not in ("seismic_code", "design_code", "accidental_ecc")]
    common = {
        "kind": KIND, "label": "3D FRAME ANALYSIS", "demo": False,
        "disclaimer": DISCLAIMER_2800 if inp.seismic_code == "IRAN_2800" else DISCLAIMER,
        "solver": "internal_direct_stiffness_3d (app/application/analysis/frame3d_solver.py)",
        "seismic_code": inp.seismic_code, "design_code": inp.design_code,
        "code": _code_label(inp),
        "inputs": inputs, "parsed_from_request": list(inp.parsed), "defaulted_inputs": defaulted,
    }
    missing = missing_inputs(inp)
    if missing:
        msg = ("Please specify: " + ", ".join(_LABELS[m] for m in missing)
               + ". Example: `3-storey RC moment frame, 2x2 bays of 5 m, storey height 3.2 m, C=0.165`.")
        return {**common, "status": "MISSING_REQUIRED_INPUT", "missing_inputs": missing, "message": msg, "warnings": [msg]}
    limits = []
    if inp.storeys > MAX_STOREYS: limits.append(f"at most {MAX_STOREYS} storeys")
    if max(inp.bays_x, inp.bays_y) > MAX_BAYS: limits.append(f"at most {MAX_BAYS} bays per direction")
    if (inp.bays_x + 1) * (inp.bays_y + 1) * (inp.storeys + 1) > MAX_NODES: limits.append(f"at most {MAX_NODES} nodes")
    if min(inp.storeys, inp.bays_x, inp.bays_y) < 1: limits.append("at least 1 storey and 1 bay per direction")
    if limits:
        msg = "This chat solver currently supports " + ", ".join(limits) + "."
        return {**common, "status": "UNSUPPORTED_SIZE", "message": msg, "warnings": [msg]}
    try:
        raw = run_frame3d(inp)
    except (SpaceFrameSolverError, ValueError) as exc:
        msg = f"3D frame analysis failed: {exc}"
        return {**common, "status": "FAILED", "message": msg, "warnings": [msg]}

    warnings: list[str] = []
    is2800 = inp.seismic_code == "IRAN_2800"
    si = raw["seismic"]
    if is2800:
        names = {"zone": f"hazard zone {iran2800.ZONE_LABEL[inp.zone]} (A={iran2800.ZONE_A[inp.zone]:g})",
                 "soil": f"soil type {inp.soil}", "importance": f"importance I={inp.importance:g}",
                 "system": iran2800.SYSTEMS[inp.system][0]}
        assumed = [label for key, label in names.items() if key not in inp.parsed]
        if assumed:
            warnings.append("Standard 2800 parameters not given and assumed: " + ", ".join(assumed) + ".")
        if inp.seismic_c is not None:
            warnings.append("A user C was given but Standard 2800 parameters take precedence; C was computed from A·B·I/R.")
    elif inp.seismic_c is None:
        warnings.append("No seismic coefficient C given (e.g. `C=0.165`): only gravity load cases were analysed; drift and base shear are not reported.")
    if not is2800 and "behaviour_r" not in inp.parsed and inp.seismic_c is not None:
        warnings.append(f"Behaviour factor R not given; assumed R={inp.behaviour_r:g} for amplified drift (0.7R·Δ).")
    if raw["equilibrium_error_kn"] > 1e-3:
        warnings.append(f"Equilibrium residual {raw['equilibrium_error_kn']:.3g} kN.")

    beams, cols = raw["beams"], raw["columns"]
    per_storey_beam = []
    for k in range(1, inp.storeys + 1):
        bk = [b for b in beams if b["storey"] == k]
        per_storey_beam.append({"storey": k, "M_neg_kn_m": _r(max(b["M_neg_kn_m"] for b in bk)),
                                "M_pos_kn_m": _r(max(b["M_pos_kn_m"] for b in bk)), "V_kn": _r(max(b["V_kn"] for b in bk))})
    gb_neg = max(beams, key=lambda b: b["M_neg_kn_m"]); gb_v = max(beams, key=lambda b: b["V_kn"])
    gb_pos = max(beams, key=lambda b: b["M_pos_kn_m"])
    gc = max(cols, key=lambda c: c["P_kn"]); gcm = max(cols, key=lambda c: c["M_kn_m"])
    drift = [{"direction": d["direction"], "storey": d["storey"], "u_max_mm": _r(d["u_max_mm"]),
              "drift_elastic_mm": _r(d["drift_elastic_mm"]), "ratio_elastic_pct": _r(d["ratio_elastic"] * 100, 3),
              "ratio_amplified_pct": _r(d["ratio_amplified"] * 100, 3)} for d in raw["drift"]]
    max_drift = max(drift, key=lambda d: d["ratio_amplified_pct"]) if drift else None
    bs = raw["base_shear"]
    base_shear = None
    if bs:
        base_shear = {k: _r(v, 4 if k == "C" else 2) for k, v in bs.items()}
        base_shear["status"] = "PASS" if bs["error_pct"] < 0.5 else "CHECK"
    results = {
        "max_drift_amplified_pct": max_drift["ratio_amplified_pct"] if max_drift else None,
        "max_drift_storey": max_drift["storey"] if max_drift else None,
        "max_drift_direction": max_drift["direction"] if max_drift else None,
        "beam_max_M_neg_kn_m": _r(gb_neg["M_neg_kn_m"]), "beam_max_M_neg_id": gb_neg["id"],
        "beam_max_M_pos_kn_m": _r(gb_pos["M_pos_kn_m"]), "beam_max_V_kn": _r(gb_v["V_kn"]),
        "column_max_P_kn": _r(gc["P_kn"]), "column_max_P_id": gc["id"], "column_max_M_kn_m": _r(gcm["M_kn_m"]),
        "seismic_weight_kn": _r(sum(raw["W_level_kn"].values())),
        "equilibrium_error_kn": raw["equilibrium_error_kn"],
    }
    assumptions = [
        "Regular orthogonal grid, fixed column bases, rigid floor diaphragms",
        "Cracked stiffness: beams 0.35·Ig, columns 0.70·Ig; torsion 0.15·J; Ec = 4700√f'c",
        "Two-way slab loads to beams by equivalent triangular/trapezoidal UDL; slab self-weight is part of the dead load",
        f"Perimeter wall {inp.wall_kn_m:g} kN/m on edge beams, roof parapet {inp.parapet_kn_m:g} kN/m; roof live load {inp.roof_live_kn_m2:g} kN/m²",
        "Combinations: 1.4D, 1.2D+1.6L, 1.2D+1.0L±E, 0.9D±E (Mabhas 6 / ACI form; no 30% orthogonal combination)",
        "No P-Δ",
    ]
    if is2800:
        assumptions += [
            f"Standard 2800 (4th ed.) equivalent static with the empirical period {si['T_formula']} = {si['T_empirical_s']:.3f} s (analytical period not used for C)",
            f"Inelastic drift Δm = Cd·Δe/I ({si['drift_factor_label']}), limit {si['drift_limit']*100:g}% ; drift from the design-force analysis (conservative)",
            "Modal analysis on rigid-diaphragm DOFs with storey masses (D+0.2L)/g and uniform-plate polar inertia; mass centre at plan centre",
            "Response spectrum: 2800 design spectrum A·B1·N·I/R, CQC 5% damping, no accidental torsion in the dynamic cases",
        ]
    else:
        assumptions.append(f"Drift amplified by 0.7R with R={inp.behaviour_r:g}; the 2.5% value shown is only a reference, not a 2800 check")
    if inp.design_code == "NONE":
        assumptions.append("No member design / code compliance checks requested (add 'design per Mabhas 9')")
    fields = [
        {"label": "Model", "value": f"{inp.storeys} storeys, {inp.bays_x}×{inp.bays_y} bays ({inp.bay_x_m:g}×{inp.bay_y_m:g} m), h={inp.storey_height_m:g} m", "unit": ""},
        {"label": "Elements", "value": f"{raw['model']['columns']} columns, {raw['model']['beams']} beams, {raw['model']['nodes']} nodes", "unit": ""},
        {"label": "Sections", "value": f"C {inp.column_b_m*100:g}×{inp.column_h_m*100:g}, B {inp.beam_b_m*100:g}×{inp.beam_h_m*100:g}", "unit": "cm"},
        {"label": "Seismic weight W", "value": f"{results['seismic_weight_kn']:.1f}", "unit": "kN"},
    ]
    if is2800:
        fields += [
            {"label": "2800 parameters", "value": f"A={si['A']:g} ({si['zone_label']}), soil {si['soil']}, I={si['I']:g}, {si['system_label']} R={si['R']:g}, Cd={si['Cd']:g}", "unit": ""},
            {"label": "T (empirical) / B1·N", "value": f"{si['T_empirical_s']:.3f} s / {si['B1']:.3f}×{si['N']:.3f} = {si['B']:.3f}", "unit": ""},
            {"label": "C = ABI/R (≥ 0.12AI)", "value": f"{si['C']:.4f} (Cmin {si['C_min']:.4f}), k={si['k']:.2f}", "unit": ""},
        ]
    if base_shear:
        fields.append({"label": "Base shear V = C·W", "value": f"{base_shear['V_expected_kn']:.1f} (C={base_shear['C']:g})", "unit": "kN"})
    modal = raw.get("modal")
    if modal:
        rs = modal["response_spectrum"]
        fields.append({"label": "T1 (modal)", "value": f"{modal['T_fundamental_s']:.3f}", "unit": "s"})
        fields.append({"label": "V dynamic / static", "value": " ; ".join(
            f"{d}: {rs[d]['V_dynamic_kn']:.1f}/{rs[d]['V_static_kn']:.1f} (×{rs[d]['scale_factor']:.3f})" for d in rs), "unit": "kN"})
    if max_drift:
        fields.append({"label": "Max drift " + ("Cd·Δ/(I·h)" if is2800 else "0.7R·Δ/h"), "value": f"{max_drift['ratio_amplified_pct']:.2f} (storey {max_drift['storey']}, {max_drift['direction']})", "unit": "%"})
    fields += [
        {"label": "Beam max M⁻", "value": f"{results['beam_max_M_neg_kn_m']:.1f}", "unit": "kN·m"},
        {"label": "Beam max M⁺", "value": f"{results['beam_max_M_pos_kn_m']:.1f}", "unit": "kN·m"},
        {"label": "Beam max V", "value": f"{results['beam_max_V_kn']:.1f}", "unit": "kN"},
        {"label": "Column max P", "value": f"{results['column_max_P_kn']:.1f}", "unit": "kN"},
    ]
    return {
        **common, "status": "completed", "message": "3D frame analysis completed",
        "model_summary": {**raw["model"], "storeys": inp.storeys, "bays_x": inp.bays_x, "bays_y": inp.bays_y,
                          "load_combinations": raw["combos"]},
        "geometry": raw["geometry"],
        "seismic": {**raw["seismic"], "W_level_kn": {str(k): _r(v) for k, v in raw["W_level_kn"].items()},
                    "F_level_kn": {str(k): _r(v) for k, v in raw["F_level_kn"].items()}},
        "results": results, "drift": drift,
        "drift_reference_limit_pct": _r(si.get("drift_limit", 0.025) * 100, 2),
        "drift_check": (("PASS" if max_drift["ratio_amplified_pct"] <= si["drift_limit"] * 100 + 1e-9 else "FAIL") if (is2800 and max_drift) else None),
        "modal": _modal_payload(modal, si) if modal else None,
        "beam_forces_by_storey": per_storey_beam,
        "column_forces_by_storey": [{"storey": k, "P_kn": _r(max(c["P_kn"] for c in cols if c["storey"] == k)),
                                     "M_kn_m": _r(max(c["M_kn_m"] for c in cols if c["storey"] == k))} for k in range(1, inp.storeys + 1)],
        "base_shear_check": base_shear,
        "gravity_reaction_kn": {k: _r(v) for k, v in raw["gravity_reaction_kn"].items()},
        # member envelopes for a future Mabhas 9 / ACI design module
        "envelopes": {"beams": [{**b, "M_neg_kn_m": _r(b["M_neg_kn_m"]), "M_pos_kn_m": _r(b["M_pos_kn_m"]), "V_kn": _r(b["V_kn"])} for b in beams],
                      "columns": [{k2: v for k2, v in {**c, "P_kn": _r(c["P_kn"]), "M_kn_m": _r(c["M_kn_m"])}.items() if k2 != "records"} for c in cols]},
        "assumptions": assumptions, "warnings": warnings, "fields": fields,
    }


def _modal_payload(modal: dict[str, Any], si: dict[str, Any]) -> dict[str, Any]:
    rs = {}
    for d, v in modal["response_spectrum"].items():
        rs[d] = {"V_dynamic_kn": _r(v["V_dynamic_kn"]), "V_static_kn": _r(v["V_static_kn"]), "ratio": _r(v["ratio"], 3),
                 "scale_factor": _r(v["scale_factor"], 3), "V_dynamic_scaled_kn": _r(v["V_dynamic_scaled_kn"]),
                 "drift": [{"storey": r["storey"], "drift_elastic_mm": _r(r["drift_elastic_mm"]),
                            "ratio_amplified_pct": _r(r["ratio_amplified"] * 100, 3)} for r in v["drift"]]}
    return {"method": modal["method"], "T_fundamental_s": _r(modal["T_fundamental_s"], 4),
            "modes": [{k: (_r(v, 4) if isinstance(v, float) else v) for k, v in m.items()} for m in modal["modes"][:12]],
            "modes_for_90pct": modal["modes_for_90pct"], "response_spectrum": rs,
            "scale_rule": f"V_dynamic ≥ {si['dynamic_scale_min']:.0%} V_static ({si.get('regularity', 'regular')})"}


def frame3d_markdown(payload: dict[str, Any]) -> str:
    if payload.get("status") != "completed":
        return f"### 3D frame analysis\n**Status:** {payload.get('status')}\n\n{payload.get('message')}"
    r = payload["results"]; ms = payload["model_summary"]
    lines = ["### 3D frame analysis", "**Status:** Completed", "",
             f"- Model: {ms['storeys']} storeys, {ms['bays_x']}×{ms['bays_y']} bays — {ms['columns']} columns, {ms['beams']} beams, {ms['nodes']} nodes"]
    si = payload.get("seismic") or {}
    if si.get("iranian_2800"):
        lines.append(f"- Standard 2800: A={si['A']:g} ({si['zone_label']}), soil {si['soil']} (T0={si['T0']:g}, Ts={si['Ts']:g}, S={si['S']:g}), "
                     f"I={si['I']:g}, {si['system_label']} (R={si['R']:g}, Cd={si['Cd']:g})")
        lines.append(f"- T = {si['T_empirical_s']:.3f} s, B1 = {si['B1']:.3f}, N = {si['N']:.3f}, **C = {si['C']:.4f}** (Cmin = {si['C_min']:.4f}), k = {si['k']:.2f}")
    bs = payload.get("base_shear_check")
    if bs:
        lines.append(f"- Base shear: V = C·W = {bs['C']:g} × {bs['W_total_kn']:.1f} = **{bs['V_expected_kn']:.1f} kN** (reactions X {bs['V_reaction_x_kn']:.1f}, Y {bs['V_reaction_y_kn']:.1f} kN — {bs['status']})")
    if payload["drift"]:
        label = "Cd·Δ/(I·h)" if si.get("iranian_2800") else "0.7R·Δ/h"
        check = f" — limit {payload['drift_reference_limit_pct']:g}% {payload['drift_check']}" if payload.get("drift_check") else ""
        lines.append(f"- Max storey drift ({label}): **{r['max_drift_amplified_pct']:.2f}%** at storey {r['max_drift_storey']}, direction {r['max_drift_direction']}{check}")
        lines.append("")
        lines.append(f"| Storey | Dir | Δ elastic (mm) | Δ/h elastic % | {label} % |")
        lines.append("|---|---|---|---|---|")
        for d in payload["drift"]:
            lines.append(f"| {d['storey']} | {d['direction']} | {d['drift_elastic_mm']:.2f} | {d['ratio_elastic_pct']:.3f} | {d['ratio_amplified_pct']:.3f} |")
        lines.append("")
    modal = payload.get("modal")
    if modal:
        lines.append(f"- Modal: T1 = **{modal['T_fundamental_s']:.3f} s**; modes for 90% mass X/Y: {modal['modes_for_90pct']['X']}/{modal['modes_for_90pct']['Y']}")
        lines.append("")
        lines.append("| Mode | T (s) | Mx % | My % | Rz % | ΣMx % | ΣMy % |")
        lines.append("|---|---|---|---|---|---|---|")
        for m in modal["modes"][:6]:
            lines.append(f"| {m['mode']} | {m['T_s']:.3f} | {m['mass_x_pct']:.1f} | {m['mass_y_pct']:.1f} | {m['mass_rz_pct']:.1f} | {m['cum_x_pct']:.1f} | {m['cum_y_pct']:.1f} |")
        lines.append("")
        for d, v in modal["response_spectrum"].items():
            md = max(x["ratio_amplified_pct"] for x in v["drift"])
            lines.append(f"- Response spectrum {d}: V_dyn = {v['V_dynamic_kn']:.1f} kN vs V_static = {v['V_static_kn']:.1f} kN "
                         f"({v['ratio']:.0%}) → scale ×{v['scale_factor']:.3f} ({modal['scale_rule']}); max scaled drift {md:.2f}%")
    lines += [f"- Beam max M⁻ **{r['beam_max_M_neg_kn_m']:.1f} kN·m** ({r['beam_max_M_neg_id']}), M⁺ {r['beam_max_M_pos_kn_m']:.1f} kN·m, V {r['beam_max_V_kn']:.1f} kN",
              f"- Column max axial P **{r['column_max_P_kn']:.1f} kN** ({r['column_max_P_id']})",
              "", "Assumptions:", *[f"- {a}" for a in payload["assumptions"]]]
    if payload["warnings"]:
        lines += ["", "Warnings:", *[f"- {w}" for w in payload["warnings"]]]
    lines += ["", f"*{payload['disclaimer']}*"]
    return "\n".join(lines)


def frame3d_memory_summary(payload: dict[str, Any]) -> str:
    r = payload.get("results") or {}; ms = payload.get("model_summary") or {}
    return (f"3D frame analysis: {ms.get('storeys')} storeys, {ms.get('bays_x')}x{ms.get('bays_y')} bays; "
            f"max drift 0.7R {r.get('max_drift_amplified_pct')}% (storey {r.get('max_drift_storey')}), "
            f"beam M- {r.get('beam_max_M_neg_kn_m')} kN·m, column P {r.get('column_max_P_kn')} kN. "
            "Seismic C user-supplied; no Iranian code checks yet.")
