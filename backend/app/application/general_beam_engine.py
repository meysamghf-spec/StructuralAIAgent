"""Deterministic beam engine for chat without a project or LLM (EN + FA)."""
from __future__ import annotations

import math
import re
from typing import Any

_FA = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
_BEAM = ("beam", "تیر")
_CANT = ("cantilever", "طره", "کنسول")
_CONT = ("continuous", "two-span", "two span", "پیوسته", "دو دهانه")
_RC = ("reinforced concrete", "rc ", "r.c", "بتن مسلح", "بتنی", "concrete")
_ENG_HINTS = _BEAM + ("frame", "قاب", "column", "ستون", "slab", "دال", "kn", "کیلونیوتن", "moment", "لنگر", "shear", "برش")


def _n(t: str) -> str:
    return (t or "").translate(_FA).replace("\u200c", " ")


def _num(t: str, pats: tuple[str, ...]) -> float | None:
    for p in pats:
        m = re.search(p, t, re.IGNORECASE)
        if m:
            return float(m.group(1))
    return None


def is_beam_prompt(text: str) -> bool:
    t = _n(text).lower()
    return any(w in t for w in _BEAM)


def looks_engineering(text: str) -> bool:
    t = _n(text).lower()
    return any(w in t for w in _ENG_HINTS)


def analyze_beam_prompt(text: str) -> dict[str, Any] | None:
    if not is_beam_prompt(text):
        return None
    t = _n(text)
    low = t.lower()
    assumptions: list[str] = []
    support = "cantilever" if any(w in low for w in _CANT) else "continuous" if any(w in low for w in _CONT) else "simply_supported"
    L = _num(t, (r"(?:span|length|دهانه|طول)\D{0,12}(\d+(?:\.\d+)?)\s*(?:m\b|متر)", r"(\d+(?:\.\d+)?)\s*(?:m\b|متر)(?!m)"))
    if L is None:
        L = 6.0; assumptions.append("Span not given: assumed L = 6 m")
    w = _num(t, (r"(\d+(?:\.\d+)?)\s*(?:kN\s*/\s*m|کیلونیوتن\s*(?:بر|/)\s*متر)",))
    P = _num(t, (r"(\d+(?:\.\d+)?)\s*(?:kN|کیلونیوتن)(?!\s*(?:/|بر))",)) if w is None or re.search(r"point|concentrated|متمرکز", low) else None
    if w is None and P is None:
        w = 10.0; assumptions.append("Load not given: assumed UDL w = 10 kN/m")
    w = w or 0.0; P = P or 0.0
    rc = any(k in low + " " for k in _RC)
    b = _num(t, (r"\bb\s*=?\s*(\d+)\s*mm",)) or 300.0
    h = _num(t, (r"\bh\s*=?\s*(\d+)\s*mm",)) or 500.0
    fc = _num(t, (r"fc'?\s*=?\s*(\d+(?:\.\d+)?)", r"(\d+(?:\.\d+)?)\s*MPa")) or 25.0
    fy = _num(t, (r"fy\s*=?\s*(\d+(?:\.\d+)?)",)) or 400.0
    E = 4700 * math.sqrt(fc) * 1e3 if rc else 200e6  # kN/m²
    I = b * h ** 3 / 12 / 1e12 if rc else 8.36e-5  # m⁴
    if rc:
        assumptions.append(f"Section b×h = {b:.0f}×{h:.0f} mm, f'c = {fc:.0f} MPa, fy = {fy:.0f} MPa (defaults unless stated)")
        assumptions.append("Deflection uses gross section, E = 4700√f'c (uncracked, short-term)")
    else:
        assumptions.append("Deflection uses E = 200 GPa, I = 8.36e-5 m⁴ (IPE 300-like) as a default steel section")
    if support == "simply_supported":
        R = (w * L + P) / 2; R1 = R2 = R
        M = w * L ** 2 / 8 + P * L / 4; V = R
        d = 5 * w * L ** 4 / (384 * E * I) + P * L ** 3 / (48 * E * I)
        xs = [L * i / 20 for i in range(21)]
        Mx = [R * x - w * x * x / 2 - (P * (x - L / 2) if x > L / 2 else 0) for x in xs]
        Vx = [R - w * x - (P if x > L / 2 else 0) for x in xs]
        assumptions.append("Point load (if any) at midspan")
        react = [("Reaction R_A", R1), ("Reaction R_B", R2)]
    elif support == "cantilever":
        R = w * L + P; M = w * L ** 2 / 2 + P * L; V = R
        d = w * L ** 4 / (8 * E * I) + P * L ** 3 / (3 * E * I)
        xs = [L * i / 20 for i in range(21)]
        Mx = [-(w * (L - x) ** 2 / 2 + P * (L - x)) for x in xs]
        Vx = [w * (L - x) + P for x in xs]
        assumptions.append("Fixed at left end; point load (if any) at free end")
        react = [("Reaction R (fixed end)", R), ("Fixed-end moment", M)]
    else:
        # two equal spans, UDL (+ point loads at each midspan)
        RA = 0.375 * w * L + 0.3125 * P; RB = 1.25 * w * L + 1.375 * P
        M = w * L ** 2 / 8 + 0.1875 * P * L; V = 0.625 * w * L + 0.6875 * P
        d = w * L ** 4 / (185 * E * I) + 0.015 * P * L ** 3 / (E * I)
        xs = [2 * L * i / 40 for i in range(41)]
        def mx(x: float) -> float:
            x1 = x if x <= L else 2 * L - x
            return RA * x1 - w * x1 * x1 / 2 - (P * (x1 - L / 2) if x1 > L / 2 else 0)
        Mx = [mx(x) for x in xs]
        Vx = [(RA - w * x - (P if x > L / 2 else 0)) if x <= L else -(RA - w * (2 * L - x) - (P if 2 * L - x > L / 2 else 0)) for x in xs]
        assumptions.append("Two equal continuous spans, each of length L; point loads (if any) at each midspan")
        react = [("End reactions R_A = R_C", RA), ("Middle reaction R_B", RB)]
    fields = [
        {"label": "Support", "value": support.replace("_", " "), "unit": None},
        {"label": "Span L", "value": f"{L:g}", "unit": "m"},
    ]
    if w: fields.append({"label": "Uniform load w", "value": f"{w:g}", "unit": "kN/m"})
    if P: fields.append({"label": "Point load P", "value": f"{P:g}", "unit": "kN"})
    fields += [{"label": k, "value": f"{v:.2f}", "unit": "kN·m" if "moment" in k.lower() else "kN"} for k, v in react]
    fields += [{"label": "Max moment Mmax", "value": f"{M:.2f}", "unit": "kN·m"},
               {"label": "Max shear Vmax", "value": f"{V:.2f}", "unit": "kN"},
               {"label": "Max deflection", "value": f"{d * 1000:.2f}", "unit": "mm"}]
    design = None
    if rc:
        from app.application.mabhas9_rc_design import design_beam
        Mu, Vu = 1.4 * M, 1.4 * V
        assumptions.append("Mabhas 9 design: loads treated as service, Mu = 1.4·M, Vu = 1.4·V (dead-load factor; refine with actual combos)")
        neg = M if support != "simply_supported" else 0.0
        design = design_beam(m_neg_end=max(1.4 * neg, 0.0), m_pos_end=0.0, m_pos_mid=Mu, vu=Vu, b=b, h=h, fc=fc, fy=fy)
        fields.append({"label": "Mu / Vu (Mabhas 9)", "value": f"{Mu:.1f} / {Vu:.1f}", "unit": "kN·m / kN"})
        if design.get("bottom_bars"):
            fields += [{"label": "Bottom bars", "value": design["bottom_bars"], "unit": None},
                       {"label": "Top bars", "value": design["top_bars"], "unit": None}]
            sh = design.get("shear") or {}
            if sh.get("spacing_mm"):
                fields.append({"label": "Stirrups", "value": f"Φ10 @ {sh['spacing_mm']:.0f}", "unit": "mm"})
        fields.append({"label": "Design status", "value": str(design.get("status")), "unit": None})
    payload = {
        "kind": "demo_rc_beam", "status": "completed", "label": "BEAM ANALYSIS", "demo": False,
        "disclaimer": "Deterministic rule-based calculation (no LLM). Verify before use in practice.",
        "code": "Mabhas 9 (Iran)" if rc else "Elastic beam theory",
        "inputs": {"span_m": L, "uniform_load_kn_m": w, "point_load_kn": P, "support": support,
                   "width_mm": b, "height_mm": h, "fc_mpa": fc, "fy_mpa": fy},
        "results": {"max_moment_kn_m": round(M, 4), "max_shear_kn": round(V, 4), "max_deflection_mm": round(d * 1000, 3),
                    "diagram": {"x_m": [round(x, 3) for x in xs], "moment_kn_m": [round(m, 3) for m in Mx], "shear_kn": [round(v, 3) for v in Vx]}},
        "design": design, "fields": fields, "assumptions": assumptions, "warnings": list((design or {}).get("notes") or []),
    }
    lines = [f"**Beam analysis ({support.replace('_', ' ')}, L = {L:g} m)**", ""]
    lines += [f"- {f['label']}: {f['value']}{(' ' + f['unit']) if f['unit'] else ''}" for f in fields]
    lines += ["", "Assumptions:"] + [f"- {a}" for a in assumptions]
    return {"payload": payload, "markdown": "\n".join(lines)}


CAPABILITIES_MESSAGE = (
    "I couldn't match that to one of my built-in calculators, and no AI language model is configured on this server, "
    "so I can't answer free-form questions right now.\n\n"
    "What I can do without a project:\n"
    "- Beams: simply supported, cantilever, or two-span continuous with uniform (kN/m) or point (kN) loads -> reactions, Mmax, Vmax, deflection, diagrams\n"
    "- Reinforced concrete beam design to Mabhas 9 (mention \"reinforced concrete\")\n"
    "- 3D frame analysis (e.g. \"3D frame 3 stories, 2x2 bays\")\n\n"
    "Example: \"Analyze a simply supported reinforced concrete beam with a 6 m span and uniform load of 20 kN/m.\"\n"
    "مثال: «تیر ساده بتن مسلح با دهانه ۶ متر و بار گسترده ۲۰ کیلونیوتن بر متر را تحلیل کن»"
)
