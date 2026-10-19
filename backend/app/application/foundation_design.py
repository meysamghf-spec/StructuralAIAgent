"""Isolated-footing design for the chat 3D frame (service bearing, one-way / punching shear, flexure).

Units: kN, m, kPa unless a name says mm / MPa. Factors φc = 0.65, φs = 0.85 and the stress block come from
``mabhas9_rc_design`` so the footing is consistent with the member design. Shear expressions use the
Mabhas 9 / ACI form (see CLAUSES_*). Not a geotechnical design: allowable pressure is a user/assumed value.
"""

from __future__ import annotations

import math
from typing import Any

from app.application import mabhas9_rc_design as m9

DEFAULT_QA_KPA = 150.0
DF_M = 1.5            # embedment depth (bottom of footing) used for the overburden deduction
GAMMA_AVG = 18.0      # kN/m³ average unit weight of footing + soil above the base
SEISMIC_QA_FACTOR = 1.33
COVER_M = 0.075
H_MIN_M = 0.30
B_MAX_M = 8.0
RHO_MIN = 0.0018      # temperature/shrinkage minimum for fy ≥ 400 MPa, on b·h
BAR_DIAMETERS = (14, 16, 18, 20, 22, 25)

CLAUSES_IMPLEMENTED = [
    "Service bearing: q = P/A·(1 + 6ex/B + 6ey/B) ≤ qa,net, kern check ex + ey ≤ B/6 (no uplift)",
    "Net allowable pressure qa,net = qa − γ·Df with Df = 1.5 m, γ = 18 kN/m³; qa × 1.33 for combinations with earthquake",
    "One-way shear at d from the column face: Vc = 0.2·φc·√f'c·b·d",
    "Punching shear on bo at d/2: vc = φc·√f'c·min(0.2(1+2/βc), 0.2(αs·d/bo + 2), 0.4)",
    "Flexure at the column face with the Mabhas 9 stress block (φc = 0.65, φs = 0.85), As,min = 0.0018·b·h",
]
CLAUSES_SIMPLIFIED = [
    "Square pad footings, one per base column, centred under the column; uniform soil, rigid footing",
    "Eccentricity from the base reactions (M + V·h); footing self-weight and soil are deducted from qa through Df",
    "Group size = envelope of the columns of the same position (corner / edge / interior) at the base",
    "Not checked: settlement, sliding, overturning, bearing capacity from soil data, development length, column dowels, bearing on the column base",
]


def _ceil(v: float, step: float) -> float:
    return math.ceil(v / step - 1e-9) * step


def _floor(v: float, step: float) -> float:
    return math.floor(v / step + 1e-9) * step


def service_combos() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {"D+L": {"f": {"D": 1.0, "L": 1.0}, "seismic": False}}
    for sg in (1.0, -1.0):
        for e in ("Ex", "Ey"):
            out[f"D+0.75L{'+' if sg > 0 else '-'}0.525{e}"] = {"f": {"D": 1.0, "L": 0.75, e: 0.525 * sg}, "seismic": True}
    return out


def _load(reactions: dict[str, dict[str, list[float]]], nid: str, factors: dict[str, float]) -> list[float]:
    out = [0.0] * 6
    for case, f in factors.items():
        if case in reactions:
            r = reactions[case][nid]
            out = [o + f * v for o, v in zip(out, r)]
    return out


def _bearing(p: float, mx: float, my: float, vx: float, vy: float, b: float, h: float) -> dict[str, float]:
    """Pressures under a square footing; moments about the footing base."""
    if p <= 0:
        return {"qmax": math.inf, "qmin": -math.inf, "ex": math.inf, "ey": math.inf}
    ex = (abs(my) + abs(vx) * h) / p
    ey = (abs(mx) + abs(vy) * h) / p
    q0 = p / (b * b)
    return {"qmax": q0 * (1 + 6 * (ex + ey) / b), "qmin": q0 * (1 - 6 * (ex + ey) / b), "ex": ex, "ey": ey}


def design_footing(reactions: dict[str, dict[str, list[float]]], nid: str, combo_factors: dict[str, dict[str, float]], *,
                   c1: float, c2: float, position: str, qa: float, fc: float, fy: float, b_min: float = 0.0) -> dict[str, Any]:
    qnet0 = qa - GAMMA_AVG * DF_M
    if qnet0 <= 10.0:
        return {"status": "FAIL", "notes": ["Allowable pressure too small after deducting the overburden"], "B_m": None}
    svc = {n: (c, _load(reactions, nid, c["f"])) for n, c in service_combos().items() if all(k in reactions for k in c["f"])}
    p_dl = svc["D+L"][1][2]
    h_guess = 0.5
    b = max(b_min, _ceil(math.sqrt(max(p_dl, 1.0) / qnet0), 0.1), 1.0)
    gov = ("", 0.0)
    while b <= B_MAX_M:
        ok, worst = True, 0.0
        for n, (c, r) in svc.items():
            allow = qa * (SEISMIC_QA_FACTOR if c["seismic"] else 1.0) - GAMMA_AVG * DF_M
            res = _bearing(r[2], r[3], r[4], r[0], r[1], b, h_guess)
            dc = res["qmax"] / allow
            if res["qmin"] < -1e-9 or dc > 1.0 + 1e-9:
                ok = False
            if dc >= worst:
                worst, gov = dc, (n, res["ex"] + res["ey"])
        if ok:
            break
        b = round(b + 0.1, 6)
    else:
        return {"status": "FAIL", "notes": ["No square footing up to 8 m satisfies bearing / kern: use a mat or combined footing"], "B_m": None}
    b = round(b, 6)
    # factored design
    beta = max(c1, c2) / min(c1, c2)
    alpha_s = {"interior": 40.0, "edge": 30.0, "corner": 20.0}[position]
    notes: list[str] = []
    uplift = [n for n, f in combo_factors.items() if _load(reactions, nid, f)[2] <= 0]
    if uplift:
        notes.append(f"Net uplift in {', '.join(uplift)}: those combinations are ignored for footing design (check overturning/anchorage)")
    h = H_MIN_M
    while h <= 2.5:
        d = h - COVER_M - 0.010
        qu = 0.0
        for n, f in combo_factors.items():
            r = _load(reactions, nid, f)
            if r[2] > 0:
                qu = max(qu, _bearing(r[2], r[3], r[4], r[0], r[1], b, h)["qmax"])
        a = (b - min(c1, c2)) / 2
        vu1 = qu * b * max((b - c1) / 2 - d, 0.0)
        vc1 = 0.2 * m9.PHI_C * math.sqrt(fc) * 1000 * b * d
        bo = 2 * (c1 + d) + 2 * (c2 + d)
        vu2 = qu * (b * b - (c1 + d) * (c2 + d))
        vc2 = m9.PHI_C * math.sqrt(fc) * 1000 * min(0.2 * (1 + 2 / beta), 0.2 * (alpha_s * d / bo + 2), 0.4) * bo * d
        if vu1 <= vc1 and vu2 <= vc2:
            break
        h = round(h + 0.05, 6)
    else:
        return {"status": "FAIL", "notes": ["Shear governs beyond h = 2.5 m"], "B_m": b}
    mu = qu * b * ((b - max(c1, c2)) / 2) ** 2 / 2
    best = None
    for db in BAR_DIAMETERS:
        d = h - COVER_M - db / 2000
        d_mm, b_mm = d * 1000, b * 1000
        as_req = m9.beam_required_as(mu, b_mm, d_mm, fc, fy)
        if as_req is None:
            continue
        as_min = RHO_MIN * b_mm * h * 1000
        as_need = max(as_req, as_min)
        s = _floor(min(1000 * m9.bar_area(db) / (as_need / b), 300.0), 25.0)
        if s >= 100.0:
            as_prov = 1000 * m9.bar_area(db) / s * b
            mr = m9.beam_moment_resistance(as_prov, b_mm, d_mm, fc, fy)
            best = {"db": db, "s_mm": s, "As_req_mm2": as_req, "As_min_mm2": as_min, "As_prov_mm2": as_prov,
                    "DC_flexure": mu / mr if mr > 0 else math.inf, "d_mm": d_mm}
            break
    if best is None:
        return {"status": "FAIL", "notes": ["Section too thin for the flexural demand"], "B_m": b}
    if best["As_min_mm2"] >= best["As_req_mm2"]:
        notes.append("Minimum steel governs")
    return {"status": "PASS", "B_m": b, "h_m": h, "qu_max_kpa": qu, "Mu_kn_m": mu, "bearing_dc": worst, "bearing_combo": gov[0],
            "e_total_m": gov[1], "P_service_kn": p_dl, "Vu1_kn": vu1, "Vc1_kn": vc1, "Vu2_kn": vu2, "Vc2_kn": vc2,
            "DC_oneway": vu1 / vc1, "DC_punching": vu2 / vc2, **best, "notes": notes, "net_pressure_allow_kpa": qnet0}


def design_foundation(inp, raw: dict[str, Any]) -> dict[str, Any]:
    ex = raw["export"]
    reactions, combo_factors = ex["reactions"], ex["combo_factors"]
    nx, ny = inp.bays_x, inp.bays_y
    qa = float(inp.allowable_bearing_kpa)
    assumed = "allowable_bearing_kpa" not in inp.parsed
    members = []
    for i in range(nx + 1):
        for j in range(ny + 1):
            pos = "corner" if i in (0, nx) and j in (0, ny) else "edge" if i in (0, nx) or j in (0, ny) else "interior"
            members.append({"i": i, "j": j, "pos": pos, "nid": f"N{i}_{j}_0"})
    kw = dict(c1=inp.column_b_m, c2=inp.column_h_m, qa=qa, fc=inp.fc_mpa, fy=inp.fy_mpa)
    first = {m["nid"]: design_footing(reactions, m["nid"], combo_factors, position=m["pos"], **kw) for m in members}
    groups: dict[str, list[dict]] = {}
    for m in members:
        groups.setdefault(m["pos"], []).append(m)
    rows, size = [], {}
    for pos, ms in groups.items():
        fails = [m for m in ms if first[m["nid"]]["status"] != "PASS"]
        bmax = max((first[m["nid"]].get("B_m") or 0.0) for m in ms)
        if fails:
            rows.append({"group": f"F-{pos}", "position": pos, "members": len(ms), "status": "FAIL",
                         "notes": first[fails[0]["nid"]]["notes"], "B_m": None})
            continue
        second = [design_footing(reactions, m["nid"], combo_factors, position=pos, b_min=bmax, **kw) for m in ms]
        worst = max(second, key=lambda r: (r["h_m"], r["As_prov_mm2"]))
        pmax = max(r["P_service_kn"] for r in second)
        size[pos] = (worst["B_m"], worst["h_m"])
        rows.append({
            "group": f"F-{pos}", "position": pos, "members": len(ms), "status": "PASS",
            "P_service_kn": round(pmax, 1), "B_m": round(worst["B_m"], 2), "h_m": round(worst["h_m"], 2),
            "q_max_kpa": round(max(r["qu_max_kpa"] for r in second), 1),
            "bearing_dc": round(max(r["bearing_dc"] for r in second), 3), "e_total_m": round(max(r["e_total_m"] for r in second), 3),
            "Mu_kn_m": round(max(r["Mu_kn_m"] for r in second), 1),
            "DC_oneway": round(max(r["DC_oneway"] for r in second), 3), "DC_punching": round(max(r["DC_punching"] for r in second), 3),
            "As_req_mm2": round(max(r["As_req_mm2"] for r in second)), "As_prov_mm2": round(worst["As_prov_mm2"]),
            "bars": f"Φ{worst['db']}@{int(worst['s_mm'])} each way", "DC_flexure": round(max(r["DC_flexure"] for r in second), 3),
            "notes": sorted({n for r in second for n in r["notes"]}),
        })
    rows.sort(key=lambda r: r["group"])
    footings = [{"column": f"C{m['i']}_{m['j']}", "node": m["nid"], "x": raw["geometry"]["XS"][m["i"]], "y": raw["geometry"]["YS"][m["j"]],
                 "position": m["pos"], "B_m": size[m["pos"]][0], "h_m": size[m["pos"]][1]} for m in members if m["pos"] in size]
    overlap = _overlap(inp, raw, footings) if len(footings) == len(members) else None
    all_pass = all(r["status"] == "PASS" for r in rows)
    status = "PASS" if all_pass and overlap and not overlap["overlaps"] else ("OVERLAP" if all_pass and overlap else "FAIL")
    max_dc = max([max(r["bearing_dc"], r["DC_oneway"], r["DC_punching"], r["DC_flexure"]) for r in rows if r["status"] == "PASS"] or [0.0])
    return {"code": "ACI/MABHAS9-equivalent isolated footings", "status": status, "qa_kpa": qa, "qa_assumed": assumed,
            "qa_net_kpa": round(qa - GAMMA_AVG * DF_M, 1), "Df_m": DF_M, "phi_c": m9.PHI_C, "phi_s": m9.PHI_S,
            "rows": rows, "overlap": overlap, "footings": footings,
            "summary": {"max_DC": round(max_dc, 3), "groups": len(rows), "footings": len(footings)},
            "clauses_implemented": CLAUSES_IMPLEMENTED, "clauses_simplified": CLAUSES_SIMPLIFIED}


def _overlap(inp, raw: dict[str, Any], footings: list[dict]) -> dict[str, Any]:
    by = {(round(f["x"], 6), round(f["y"], 6)): f for f in footings}
    XS, YS = raw["geometry"]["XS"], raw["geometry"]["YS"]
    pairs, min_gap = [], math.inf
    for i, x in enumerate(XS):
        for j, y in enumerate(YS):
            a = by[(round(x, 6), round(y, 6))]
            for di, dj in ((1, 0), (0, 1)):
                if i + di < len(XS) and j + dj < len(YS):
                    b = by[(round(XS[i + di], 6), round(YS[j + dj], 6))]
                    dist = math.dist((x, y), (XS[i + di], YS[j + dj]))
                    gap = dist - (a["B_m"] + b["B_m"]) / 2
                    min_gap = min(min_gap, gap)
                    if gap < 0:
                        pairs.append({"a": a["column"], "b": b["column"], "overlap_m": round(-gap, 2)})
    area = sum(f["B_m"] ** 2 for f in footings)
    plan = (XS[-1] + 2.0) * (YS[-1] + 2.0)
    cover = area / plan
    if not pairs:
        rec = "Isolated footings do not overlap."
    elif cover > 0.5:
        rec = "Footings overlap and cover more than 50 % of the plan: use a mat foundation (SAFE mat)."
    else:
        rec = ("Footings overlap: use combined (strip) footings along the overlapping grid lines; a strap beam is an alternative "
               "for edge columns at the property line.")
    return {"overlaps": pairs, "min_gap_m": round(min_gap, 2), "coverage_ratio": round(cover, 3), "recommendation": rec}
