"""Preliminary member checks for imported models, from engine forces (no LLM).

Steel (catalog / I / box / pipe sections): AISC 360 / Mabhas 10 LRFD H1-1 interaction with
compression capacity from E3 (K = 1, unbraced length = member length, flexural buckling about the weak
axis) and plastic moment capacity (lateral-torsional buckling not checked).
Concrete: beams - required flexural steel top/bottom (ACI 318 / Mabhas 9 rectangular block, phi = 0.9);
columns - axial ratio Pu / (fc' Ag) and a 1% steel axial-capacity check. Shear and detailing not checked.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

FY_STEEL = 240.0  # MPa (ST37)
FC = 25.0         # MPa
FY_REBAR = 400.0  # MPa
E_STEEL = 2.0e5   # MPa


def _steel_props(sec: dict[str, Any]) -> dict[str, float] | None:
    A, I33, I22 = sec.get("A"), sec.get("I33"), sec.get("I22")
    if not (A and I33 and I22):
        return None
    d = sec.get("d") or sec.get("h") or math.sqrt(12 * I33 / A)
    bf = sec.get("bf") or sec.get("b") or math.sqrt(12 * I22 / A)
    Z33 = sec.get("Z33") or 1.12 * I33 / (d / 2)
    Z22 = sec.get("Z22") or 1.5 * I22 / (bf / 2)
    return {"A": A, "I33": I33, "I22": I22, "Z33": Z33, "Z22": Z22, "r": math.sqrt(min(I33, I22) / A)}


def design_members(model: dict[str, Any], eng: Any, cases: dict[str, np.ndarray], lengths: dict[str, float], limit: int = 300) -> dict[str, Any]:
    rows = []
    idx = {el.id: n for n, el in enumerate(eng.elements)}
    for mem in model["members"]:
        n = idx.get(mem["id"])
        if n is None:
            continue
        sec = model["sections"][mem["section"]]
        mat = model["materials"].get(sec.get("material")) or {}
        mtyp = str(mat.get("type") or "").lower()
        st = np.array([c[n] for c in cases.values()])  # (cases, stations, 6)
        if st.size == 0:
            continue
        L = lengths[mem["id"]]
        is_steel = "steel" in mtyp or sec.get("catalog")
        if is_steel:
            p = _steel_props(sec)
            if not p:
                continue
            fy = (mat.get("Fy") or FY_STEEL * 1e3) / 1e3  # stored kN/m2 -> MPa
            fy_k = fy * 1e3  # kN/m2
            lam = L / p["r"]
            fe = math.pi**2 * E_STEEL * 1e3 / lam**2 if lam > 0 else 1e12
            fcr = (0.658 ** (fy_k / fe)) * fy_k if fy_k / fe <= 2.25 else 0.877 * fe
            pc_c, pc_t = 0.9 * fcr * p["A"], 0.9 * fy_k * p["A"]
            mcx, mcy = 0.9 * fy_k * p["Z33"], 0.9 * fy_k * p["Z22"]
            N, M2, M3 = st[:, :, 0], np.abs(st[:, :, 4]), np.abs(st[:, :, 5])
            pc = np.where(N < 0, pc_c, pc_t)
            pr = np.abs(N) / pc
            mm = M3 / mcx + M2 / mcy
            ratio = np.where(pr >= 0.2, pr + 8 / 9 * mm, pr / 2 + mm)
            k = np.unravel_index(int(np.argmax(ratio)), ratio.shape)
            r = float(ratio[k])
            rows.append({"member": mem["id"], "type": mem["type"], "section": mem["section"], "kind": "steel",
                         "ratio": round(r, 3), "ok": r <= 1.0, "case": list(cases)[k[0]],
                         "detail": f"H1-1: Pr/Pc={float(pr[k]):.2f}, Mr3/Mc3={float(M3[k] / mcx):.2f}, Mr2/Mc2={float(M2[k] / mcy):.2f}; KL/r={lam:.0f}"})
            continue
        b, h = sec.get("b"), sec.get("h")
        if not (b and h):
            continue
        fc = (mat.get("Fc") or FC * 1e3) / 1e3
        fck, fyk = fc * 1e3, FY_REBAR * 1e3
        Ag = b * h
        if mem["type"] == "beam":
            d = h - 0.06
            M3 = st[:, :, 5]
            need = {}
            for side, Mu in (("bottom", max(0.0, float(M3.max()))), ("top", max(0.0, float(-M3.min())))):
                # Mu = 0.9 As fy (d - As fy / (1.7 fc b))
                a_ = 0.9 * fyk**2 / (1.7 * fck * b)
                b_ = -0.9 * fyk * d
                disc = b_ * b_ - 4 * a_ * Mu
                As = (-b_ - math.sqrt(disc)) / (2 * a_) if disc >= 0 else float("inf")
                As_min = max(0.25 * math.sqrt(fc) / FY_REBAR, 1.4 / FY_REBAR) * b * d if Mu > 0 else 0.0
                need[side] = max(As, As_min)
            rho = max(need.values()) / (b * d)
            ok = rho <= 0.025
            rows.append({"member": mem["id"], "type": "beam", "section": mem["section"], "kind": "concrete",
                         "ratio": round(rho / 0.025, 3) if math.isfinite(rho) else 99.0, "ok": ok,
                         "As_top_cm2": round(need["top"] * 1e4, 2) if math.isfinite(need["top"]) else None,
                         "As_bottom_cm2": round(need["bottom"] * 1e4, 2) if math.isfinite(need["bottom"]) else None,
                         "detail": f"rho = {rho * 100:.2f}% (max 2.5%)" if math.isfinite(rho) else "section too small for the moment"})
        else:
            Pu = float(max(0.0, -st[:, :, 0].min()))
            Pmax = 0.8 * 0.65 * (0.85 * fck * (Ag * 0.99) + fyk * 0.01 * Ag)
            r = Pu / Pmax
            rows.append({"member": mem["id"], "type": mem["type"], "section": mem["section"], "kind": "concrete",
                         "ratio": round(r, 3), "ok": r <= 1.0,
                         "detail": f"Pu/(fc'Ag) = {Pu / (fck * Ag):.2f}; Pu/phiPn,max(1% steel) = {r:.2f} (P-M interaction not checked)"})
    rows.sort(key=lambda x: -x["ratio"])
    return {
        "method": "Preliminary: steel AISC 360 H1-1 (no LTB), concrete required flexural steel / axial capacity (Mabhas 9 / ACI 318)",
        "materials": {"Fy_steel_MPa": FY_STEEL, "fc_MPa": FC, "fy_rebar_MPa": FY_REBAR},
        "count": len(rows), "failing": sum(1 for r in rows if not r["ok"]),
        "members": rows[:limit],
    }
