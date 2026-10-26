"""Mabhas 9 (Iranian National Building Code, Part 9 — RC, CSA-based limit states) member design.

Material resistance factors φc = 0.65 (concrete), φs = 0.85 (steel); εcu = 0.0035;
rectangular block α1 = 0.85 − 0.0015 f'c ≥ 0.67, β1 = 0.97 − 0.0025 f'c ≥ 0.67.

Implemented (simplified where marked) — units N, mm, MPa unless noted:
- Beam flexure: required As from Mr = φs·As·fy·(d − a/2); As,min = max(0.25√f'c, 1.4)/fy·b·d;
  ρ ≤ 0.025 (ductile frames); steel yielding c/d ≤ 700/(700+fy); Mr⁺ at face ≥ Mr⁻/3 (intermediate),
  ≥ Mr⁻/2 (special).
- Beam shear: Vc = 0.2·φc·√f'c·b·d; Vs = φs·Av·fy·d/s ≤ 4·Vc (simplified section limit);
  Av,min/s = 0.35·b/fy; s ≤ d/2 (d/4 when Vs > 2Vc); end zones 2h: s ≤ min(d/4, 8db, 24dt, 300).
  Simplified: shear from the analysis envelope (capacity-design shear not applied).
- Column P–M: strain compatibility with φc/φs, Pr,max = 0.8·Pr0 (tied); biaxial by the
  conservative load contour Mux/Mrx + Muy/Mry ≤ 1 (Bresler α = 1); 1 % ≤ ρ ≤ 6 %;
  ties s0 ≤ min(8db, 24dt, b/2, 300) over l0 = max(h, Ln/6, 450), elsewhere ≤ min(16db, 48dt, b).
  Not checked: column shear, slenderness, joint shear, confinement Ash (special frames).
- Strong column / weak beam ΣMnc ≥ 1.2·ΣMnb with nominal capacities (φ = 1) at the joint.
"""

from __future__ import annotations

import math
from functools import lru_cache
from typing import Any

PHI_C = 0.65
PHI_S = 0.85
ECU = 0.0035
ES = 200000.0
BEAM_BARS = (14, 16, 18, 20, 22, 25)
COLUMN_BARS = (16, 18, 20, 22, 25, 28)
STIRRUP_DB = 10.0
COVER = 40.0  # clear cover to stirrups/ties, mm

CLAUSES_IMPLEMENTED = [
    "Material factors φc = 0.65, φs = 0.85; εcu = 0.0035; α1, β1 stress block",
    "Beam flexure: required As, As,min = max(0.25√f'c, 1.4)·b·d/fy, ρ ≤ 0.025, c/d ≤ 700/(700+fy)",
    "Beam M⁺ ≥ M⁻/3 at the face (intermediate) / ≥ M⁻/2 (special)",
    "Beam shear: Vc = 0.2·φc·√f'c·b·d, Vs = φs·Av·fy·d/s, Av,min, spacing limits incl. end zones 2h",
    "Column P–M interaction by strain compatibility, Pr,max = 0.8·Pr0, ρ between 1 % and 6 %",
    "Column ties: s0 = min(8db, 24dt, b/2, 300) over l0 = max(h, Ln/6, 450); elsewhere min(16db, 48dt, b)",
    "Strong column / weak beam: ΣMnc ≥ 1.2·ΣMnb (nominal capacities)",
    "Practical detailing rule: longitudinal column bars at ≤ 200 mm, bars in one layer with clear spacing ≥ max(db, 25 mm)",
]
CLAUSES_SIMPLIFIED = [
    "Biaxial bending by linear load contour Mux/Mrx + Muy/Mry ≤ 1 (conservative Bresler α = 1)",
    "Beam/column shear from the analysis envelope; capacity-design shear (Mpr / 2E) not applied",
    "Section limit Vs ≤ 4·Vc used for the maximum shear reinforcement",
    "Moments at member centre-lines (not at support faces); no redistribution",
    "Not checked: column shear, member slenderness (local P-δ magnification; global P-Δ is in the analysis only when applied), beam-column joint shear, confinement Ash, development/splices, crack/deflection",
]


def alpha1(fc: float) -> float:
    return max(0.85 - 0.0015 * fc, 0.67)


def beta1(fc: float) -> float:
    return max(0.97 - 0.0025 * fc, 0.67)


def bar_area(db: float) -> float:
    return math.pi * db * db / 4.0


# ------------------------------------------------------------------ beams
def beam_required_as(mu_knm: float, b: float, d: float, fc: float, fy: float) -> float | None:
    """Tension steel for factored moment Mu (kN·m); None if the compression block cannot carry it."""
    if mu_knm <= 0:
        return 0.0
    k = alpha1(fc) * PHI_C * fc * b
    disc = d * d - 2.0 * mu_knm * 1e6 / k
    if disc < 0:
        return None
    return k * (d - math.sqrt(disc)) / (PHI_S * fy)


def beam_moment_resistance(As: float, b: float, d: float, fc: float, fy: float, *, nominal: bool = False) -> float:
    """Mr (kN·m) of a singly reinforced rectangular section (Mn when nominal=True)."""
    pc, ps = (1.0, 1.0) if nominal else (PHI_C, PHI_S)
    a = ps * As * fy / (alpha1(fc) * pc * fc * b)
    return ps * As * fy * (d - a / 2.0) / 1e6


def beam_min_steel(b: float, d: float, fc: float, fy: float) -> float:
    return max(0.25 * math.sqrt(fc), 1.4) / fy * b * d


def beam_c_over_d(As: float, b: float, d: float, fc: float, fy: float) -> float:
    a = PHI_S * As * fy / (alpha1(fc) * PHI_C * fc * b)
    return a / beta1(fc) / d


def choose_beam_bars(As_req: float, b: float) -> tuple[int, int, float] | None:
    best = None
    for db in BEAM_BARS:
        for n in range(2, 9):
            clear = (b - 2 * (COVER + STIRRUP_DB) - n * db) / (n - 1)
            if clear < max(db, 25.0):
                break
            area = n * bar_area(db)
            if area >= As_req and (best is None or area < best[2] - 1e-9):
                best = (n, db, area)
                break
    return best


def beam_shear_design(vu_kn: float, b: float, d: float, h: float, fc: float, fy: float, db_long: float, ductility: str) -> dict[str, Any]:
    vc = 0.2 * PHI_C * math.sqrt(fc) * b * d / 1000.0
    av = 2 * bar_area(STIRRUP_DB)
    vs_req = max(vu_kn - vc, 0.0)
    vs_max = 4.0 * vc
    ok_section = vs_req <= vs_max
    s_list = [d / 2.0 if vs_req <= 2 * vc else d / 4.0, 600.0, av * fy / (0.35 * b)]
    if vs_req > 0:
        s_list.append(PHI_S * av * fy * d / (vs_req * 1000.0))
    s_mid = min(s_list)
    s_end = min(s_mid, d / 4.0, 8 * db_long, 24 * STIRRUP_DB, 300.0) if ductility in ("intermediate", "special") else s_mid
    s_mid_p = max(50, int(s_mid // 25 * 25)); s_end_p = max(50, int(s_end // 5 * 5))
    vr_end = vc + PHI_S * av * fy * d / s_end_p / 1000.0
    return {"Vc_kn": vc, "Vs_req_kn": vs_req, "Vs_max_kn": vs_max, "section_ok": ok_section,
            "s_end_mm": s_end_p, "s_mid_mm": s_mid_p, "end_zone_mm": 2 * h,
            "stirrups": f"Φ{STIRRUP_DB:g}@{s_end_p} (2h = {2*h:.0f} mm), Φ{STIRRUP_DB:g}@{s_mid_p} elsewhere",
            "DC": vu_kn / vr_end if ok_section else max(vu_kn / (vc + vs_max), 1.0001)}


def design_beam(*, m_neg_end: float, m_pos_end: float, m_pos_mid: float, vu: float, b: float, h: float, fc: float, fy: float,
                ductility: str = "intermediate") -> dict[str, Any]:
    d = h - (COVER + STIRRUP_DB + 10.0)  # ≈ h − 60 for Φ20
    as_min = beam_min_steel(b, d, fc, fy)
    rho_max = 0.025
    notes: list[str] = []
    req_top = beam_required_as(m_neg_end, b, d, fc, fy)
    req_bot_end = beam_required_as(m_pos_end, b, d, fc, fy)
    req_bot_mid = beam_required_as(m_pos_mid, b, d, fc, fy)
    if None in (req_top, req_bot_end, req_bot_mid):
        return {"status": "FAIL", "notes": ["Section too small: compression block cannot develop Mu"], "d_mm": d,
                "DC_flexure": float("inf"), "DC_shear": None}
    as_top = max(req_top, as_min)
    ratio = 0.5 if ductility == "special" else 1.0 / 3.0 if ductility == "intermediate" else 0.0
    as_bot = max(req_bot_end, req_bot_mid, as_min, ratio * as_top)
    top = choose_beam_bars(as_top, b); bot = choose_beam_bars(as_bot, b)
    if top is None or bot is None:
        return {"status": "FAIL", "notes": ["Required bars do not fit in one layer"], "d_mm": d,
                "As_top_req_mm2": as_top, "As_bot_req_mm2": as_bot, "DC_flexure": float("inf"), "DC_shear": None}
    mr_top = beam_moment_resistance(top[2], b, d, fc, fy)
    mr_bot = beam_moment_resistance(bot[2], b, d, fc, fy)
    dc = max(m_neg_end / mr_top, max(m_pos_end, m_pos_mid) / mr_bot)
    rho = top[2] / (b * d)
    if rho > rho_max:
        notes.append(f"ρ = {rho:.3f} > 0.025 (ductile-frame limit)")
    cd = beam_c_over_d(top[2], b, d, fc, fy)
    if cd > 700.0 / (700.0 + fy):
        notes.append(f"c/d = {cd:.2f} > {700/(700+fy):.2f}: tension steel does not yield")
    shear = beam_shear_design(vu, b, d, h, fc, fy, min(top[1], bot[1]), ductility)
    if not shear["section_ok"]:
        notes.append("Shear exceeds the section limit Vs ≤ 4Vc: enlarge the section")
    status = "PASS" if dc <= 1.0 + 1e-9 and shear["DC"] <= 1.0 + 1e-9 and not notes else "FAIL"
    return {"status": status, "d_mm": d, "As_min_mm2": as_min,
            "As_top_req_mm2": as_top, "As_bot_req_mm2": as_bot,
            "top_bars": f"{top[0]}Φ{top[1]}", "bottom_bars": f"{bot[0]}Φ{bot[1]}",
            "As_top_mm2": top[2], "As_bot_mm2": bot[2], "Mr_top_kn_m": mr_top, "Mr_bot_kn_m": mr_bot,
            "Mn_top_kn_m": beam_moment_resistance(top[2], b, d, fc, fy, nominal=True),
            "Mn_bot_kn_m": beam_moment_resistance(bot[2], b, d, fc, fy, nominal=True),
            "rho_top": rho, "DC_flexure": dc, "shear": shear, "DC_shear": shear["DC"], "notes": notes}


# ------------------------------------------------------------------ columns
def _layers(h: float, nface: int, db: float) -> list[tuple[float, float]]:
    cov = COVER + STIRRUP_DB + db / 2.0
    a1 = bar_area(db)
    rows = [(cov, nface * a1)]
    for i in range(1, nface - 1):
        rows.append((cov + (h - 2 * cov) * i / (nface - 1), 2 * a1))
    rows.append((h - cov, nface * a1))
    return rows


@lru_cache(maxsize=512)
def interaction_curve(b: float, h: float, nface: int, db: float, fc: float, fy: float, nominal: bool = False) -> tuple:
    """Points (P kN, M kN·m) for bending with depth h, sorted by P; plus Pr,max (kN)."""
    pc, ps = (1.0, 1.0) if nominal else (PHI_C, PHI_S)
    a1, b1 = alpha1(fc), beta1(fc)
    layers = _layers(h, nface, db)
    ast = sum(a for _, a in layers)
    p0 = a1 * pc * fc * (b * h - ast) + ps * fy * ast
    pmax = 0.8 * p0
    pts = []
    for i in range(1, 301):
        c = h * 3.0 * i / 300.0
        a = min(b1 * c, h)
        cc = a1 * pc * fc * a * b
        p, m = cc, cc * (h / 2 - a / 2)
        for y, As in layers:
            fs = max(-fy, min(fy, ES * ECU * (c - y) / c))
            force = ps * fs * As - (a1 * pc * fc * As if y < a else 0.0)
            p += force; m += force * (h / 2 - y)
        pts.append((p / 1000.0, m / 1e6))
    pts.append((-ps * fy * ast / 1000.0, 0.0))
    pts.sort()
    return tuple(pts), pmax / 1000.0, ast


def column_moment_resistance(pu_kn: float, b: float, h: float, nface: int, db: float, fc: float, fy: float, *, nominal: bool = False) -> float:
    pts, pmax, _ = interaction_curve(b, h, nface, db, fc, fy, nominal)
    if pu_kn > pmax:
        return 0.0
    for (p0, m0), (p1, m1) in zip(pts, pts[1:]):
        if p0 <= pu_kn <= p1:
            return m0 + (m1 - m0) * (pu_kn - p0) / (p1 - p0) if p1 > p0 else max(m0, m1)
    return 0.0


def column_options(b: float, h: float) -> list[tuple[int, int, float]]:
    opts = []
    for nface in range(2, 7):
        for db in COLUMN_BARS:
            clear = (min(b, h) - 2 * (COVER + STIRRUP_DB) - nface * db) / (nface - 1)
            if clear < max(1.5 * db, 40.0):
                continue
            if (min(b, h) - 2 * (COVER + STIRRUP_DB + db / 2)) / (nface - 1) > 200.0:
                continue  # practical rule: longitudinal bars at ≤ 200 mm
            opts.append((nface, db, (4 * nface - 4) * bar_area(db)))
    return sorted(opts, key=lambda o: (o[2], o[0]))


def column_dc(records: list[dict], b: float, h: float, nface: int, db: float, fc: float, fy: float) -> tuple[float, dict]:
    """Max D/C over records. Each record: P (kN, compression +) and ends [(M_about_local_y, M_about_local_z)]."""
    worst = (0.0, {})
    _, pmax, _ = interaction_curve(b, h, nface, db, fc, fy)
    for rec in records:
        pu = rec["P"]
        mry = column_moment_resistance(pu, b, h, nface, db, fc, fy)  # bending with depth h
        mrz = column_moment_resistance(pu, h, b, nface, db, fc, fy)  # bending with depth b
        for my, mz in rec["ends"]:
            if mry <= 0 or mrz <= 0:
                dc = max(pu / pmax, 9.99)
            else:
                dc = max(my / mry + mz / mrz, pu / pmax)
            if dc > worst[0]:
                worst = (dc, {"combo": rec["combo"], "Pu_kn": pu, "Mu_y_kn_m": my, "Mu_z_kn_m": mz,
                              "Mr_y_kn_m": mry, "Mr_z_kn_m": mrz, "Pr_max_kn": pmax})
    return worst


def ties(b: float, h: float, db: float, clear_height: float) -> dict[str, Any]:
    dmin = min(b, h)
    s0 = min(8 * db, 24 * STIRRUP_DB, dmin / 2, 300.0)
    s = min(16 * db, 48 * STIRRUP_DB, dmin)
    l0 = max(max(b, h), clear_height / 6.0, 450.0)
    s0p, sp = int(s0 // 25 * 25), int(s // 25 * 25)
    return {"s0_mm": s0p, "l0_mm": l0, "s_mm": sp, "text": f"Φ{STIRRUP_DB:g}@{s0p} over l0 = {l0:.0f} mm at both ends, Φ{STIRRUP_DB:g}@{sp} elsewhere"}


def design_column_group(records_by_member: dict[str, list[dict]], b: float, h: float, fc: float, fy: float, clear_height: float) -> dict[str, Any]:
    ag = b * h
    chosen = None
    last = None
    for nface, db, ast in column_options(b, h):
        rho = ast / ag
        if rho < 0.01:
            continue
        if rho > 0.06:
            break
        worst = (0.0, {}, None)
        for mid, recs in records_by_member.items():
            dc, gov = column_dc(recs, b, h, nface, db, fc, fy)
            if dc > worst[0]:
                worst = (dc, gov, mid)
        last = (nface, db, ast, rho, worst)
        if worst[0] <= 1.0:
            chosen = last
            break
    status = "PASS"
    if chosen is None:
        chosen = last; status = "FAIL"
    if chosen is None:
        return {"status": "FAIL", "notes": ["No bar arrangement fits"], "DC": float("inf")}
    nface, db, ast, rho, (dc, gov, mid) = chosen
    return {"status": status, "bars": f"{4*nface-4}Φ{db}", "nface": nface, "db": db, "As_mm2": ast, "rho": rho,
            "DC": dc, "governing_member": mid, "governing": gov, "ties": ties(b, h, db, clear_height),
            "notes": [] if status == "PASS" else ["D/C > 1 even at ρ = 6 %: enlarge the column"]}
