"""Iranian Standard 2800 (4th edition) — seismic parameters used by the chat 3D frame analysis.

Implemented (equivalent static + design spectrum):
- A by relative hazard zone (very high 0.35, high 0.30, moderate 0.25, low 0.20)
- Soil type I–IV spectrum parameters T0, Ts, S, S0 (Table 2-2, as encoded below)
- B1(T) spectrum shape, N(T) correction, B = B1·N
- Empirical period T = 0.05 H^0.75 (RC MRF) / 0.08 H^0.75 (steel MRF)
- Importance factor I, system R_u / C_d (moment frames only)
- C = A·B·I/R ≥ Cmin = 0.12·A·I
- Vertical distribution F_i = V·W_i h_i^k / Σ W_j h_j^k, k = 0.5T + 0.75 (1 ≤ k ≤ 2) (4th ed.)
- Inelastic drift Δm = C_d·Δe / I, limit 0.025 (< 5 storeys) / 0.020 (otherwise)
- Response-spectrum scaling to 85 % (regular) / 90 % (irregular) of the static base shear

Values must be verified against the official text by the engineer of record.
"""

from __future__ import annotations

import re

ZONE_A = {"VERY_HIGH": 0.35, "HIGH": 0.30, "MODERATE": 0.25, "LOW": 0.20}
ZONE_LABEL = {"VERY_HIGH": "very high", "HIGH": "high", "MODERATE": "moderate", "LOW": "low"}
# soil: (T0, Ts, S_high, S0_high, S_low, S0_low); "high" = very high + high zones
SOIL = {
    "I": (0.10, 0.40, 1.50, 1.00, 1.50, 1.00),
    "II": (0.10, 0.50, 1.50, 1.00, 1.50, 1.00),
    "III": (0.15, 0.70, 1.75, 1.10, 1.75, 1.10),
    "IV": (0.15, 1.00, 1.75, 1.10, 2.25, 1.30),
}
IMPORTANCE = {"VERY_HIGH": 1.4, "HIGH": 1.2, "MEDIUM": 1.0, "LOW": 0.8}
# system: (label, R_u, C_d, period coefficient)
SYSTEMS = {
    "RC_SMF": ("RC special moment frame", 7.5, 5.5, 0.05),
    "RC_IMF": ("RC intermediate moment frame", 5.0, 4.5, 0.05),
    "RC_OMF": ("RC ordinary moment frame", 3.5, 3.0, 0.05),
    "STEEL_SMF": ("Steel special moment frame", 7.5, 5.5, 0.08),
    "STEEL_IMF": ("Steel intermediate moment frame", 5.0, 4.0, 0.08),
    "STEEL_OMF": ("Steel ordinary moment frame", 3.5, 3.0, 0.08),
}


def soil_params(soil: str, zone: str) -> dict[str, float]:
    t0, ts, sh, s0h, sl, s0l = SOIL[soil]
    high = zone in ("VERY_HIGH", "HIGH")
    return {"T0": t0, "Ts": ts, "S": sh if high else sl, "S0": s0h if high else s0l}


def b1(t: float, soil: str, zone: str, *, static: bool = False) -> float:
    p = soil_params(soil, zone)
    if t < p["T0"]:
        # equivalent static: plateau value is used for very short periods
        return p["S"] + 1 if static else p["S0"] + (p["S"] - p["S0"] + 1) * t / p["T0"]
    if t <= p["Ts"]:
        return p["S"] + 1
    return (p["S"] + 1) * p["Ts"] / t


def n_factor(t: float, soil: str, zone: str) -> float:
    ts = soil_params(soil, zone)["Ts"]
    slope, cap = (0.7, 1.7) if zone in ("VERY_HIGH", "HIGH") else (0.4, 1.4)
    if t <= ts:
        return 1.0
    if t >= 4.0:
        return cap
    return slope * (t - ts) / (4.0 - ts) + 1.0


def spectral_b(t: float, soil: str, zone: str, *, static: bool = False) -> float:
    return b1(t, soil, zone, static=static) * n_factor(t, soil, zone)


def empirical_period(height_m: float, system: str) -> float:
    return SYSTEMS[system][3] * height_m ** 0.75


def distribution_exponent(t: float) -> float:
    if t <= 0.5:
        return 1.0
    if t >= 2.5:
        return 2.0
    return 0.5 * t + 0.75


def drift_limit(storeys: int) -> float:
    return 0.025 if storeys < 5 else 0.020


def equivalent_static(*, zone: str, soil: str, importance: float, system: str, height_m: float, storeys: int) -> dict:
    a = ZONE_A[zone]
    label, r, cd, _ = SYSTEMS[system]
    t = empirical_period(height_m, system)
    p = soil_params(soil, zone)
    b1v = b1(t, soil, zone, static=True)
    nv = n_factor(t, soil, zone)
    c_raw = a * b1v * nv * importance / r
    c_min = 0.12 * a * importance
    return {
        "method": "Standard 2800 (4th ed.) equivalent static",
        "iranian_2800": True,
        "zone": zone, "zone_label": ZONE_LABEL[zone], "A": a,
        "soil": soil, **p,
        "system": system, "system_label": label, "R": r, "Cd": cd,
        "I": importance, "H_m": height_m,
        "T_empirical_s": t, "T_formula": f"T = {SYSTEMS[system][3]}·H^0.75",
        "B1": b1v, "N": nv, "B": b1v * nv,
        "C_raw": c_raw, "C_min": c_min, "C": max(c_raw, c_min),
        "k": distribution_exponent(t),
        "vertical_distribution": "F_i = V·W_i·h_i^k / Σ W_j·h_j^k (4th ed.; replaces the 3rd-ed. Ft)",
        "accidental_eccentricity": "5% of plan dimension",
        "seismic_weight": "D + 0.2·L (live-load share for normal occupancies)",
        "drift_factor": cd / importance, "drift_factor_label": f"Cd/I = {cd:g}/{importance:g}",
        "drift_limit": drift_limit(storeys),
        "dynamic_scale_min": 0.85,
    }


# ------------------------------------------------------------------ parsing
_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "i": "I", "ii": "II", "iii": "III", "iv": "IV"}
_ZONE_WORDS = [
    (r"very\s*high|خیلی\s*زیاد|بسیار\s*زیاد", "VERY_HIGH"),
    (r"high|زیاد", "HIGH"),
    (r"moderate|medium|متوسط", "MODERATE"),
    (r"low|کم", "LOW"),
]


def parse_2800(text: str) -> dict:
    """Return the 2800 parameters found in ``text`` (already digit-normalised)."""
    found: dict = {}
    zone_alt = "|".join(p for p, _ in _ZONE_WORDS)
    m = re.search(rf"(?:خطر\s*نسبی|(?:زون|پهنه|منطقه)(?:\s*(?:لرزه\s*خیزی|زلزله))?|(?:seismic\s*)?hazard|seismicity|zone)\s*(?:zone|level|is|:|=|را|رو|به)?\s*({zone_alt})", text, re.I) or \
        re.search(rf"({zone_alt})\s*(?:seismic\s*)?(?:hazard|seismicity|zone)", text, re.I)
    if m:
        word = m.group(1)
        for pat, code in _ZONE_WORDS:
            if re.fullmatch(pat, word.strip(), re.I):
                found["zone"] = code
                break
    m = re.search(r"\bA\s*=\s*(0?\.\d+)", text)
    if m and "zone" not in found:
        a = float(m.group(1))
        found["zone"] = min(ZONE_A, key=lambda z: abs(ZONE_A[z] - a))
    m = re.search(r"(?:soil|site)\s*(?:type|class|category)?\s*[:=]?\s*(IV|III|II|I|[1-4])\b", text, re.I) or \
        re.search(r"(?:نوع\s*خاک|خاک\s*نوع|زمین\s*نوع|خاک)\s*[:=]?\s*(IV|III|II|I|[1-4])\b", text, re.I)
    if m:
        found["soil"] = _ROMAN.get(m.group(1).lower(), m.group(1).upper())
    m = re.search(r"(?:importance(?:\s*factor)?|ضریب\s*اهمیت)\s*(?:I\s*)?[:=]?\s*(\d(?:\.\d+)?)", text, re.I) or \
        re.search(r"(?<![A-Za-z'’])I\s*=\s*(\d(?:\.\d+)?)", text)
    if m:
        found["importance"] = float(m.group(1))
    else:
        m = re.search(r"(?:importance|اهمیت)\s*(?:category|group|گروه)?\s*[:=]?\s*(very\s*high|خیلی\s*زیاد|high|زیاد|medium|moderate|normal|متوسط|low|کم)", text, re.I)
        if m:
            w = m.group(1).lower()
            found["importance"] = 1.4 if ("very" in w or "خیلی" in w) else 1.2 if w in ("high", "زیاد") else 0.8 if w in ("low", "کم") else 1.0
    steel = bool(re.search(r"steel|فولاد", text, re.I))
    duct = None
    m = re.search(r"(special|intermediate|ordinary|SMF|IMF|OMF)\b", text, re.I)
    if m:
        duct = {"special": "SMF", "smf": "SMF", "intermediate": "IMF", "imf": "IMF", "ordinary": "OMF", "omf": "OMF"}[m.group(1).lower()]
    else:
        m = re.search(r"قاب\s*خمشی\s*(?:بتنی|بتن\s*آرمه|فولادی)?\s*(ویژه|متوسط|معمولی)", text)
        if m:
            duct = {"ویژه": "SMF", "متوسط": "IMF", "معمولی": "OMF"}[m.group(1)]
    if duct:
        found["system"] = ("STEEL_" if steel else "RC_") + duct
    m = re.search(r"\birregular|نامنظم", text, re.I)
    if m:
        found["irregular"] = True
    return found


def wants_2800(text: str) -> bool:
    return bool(re.search(r"2800|۲۸۰۰|خطر\s*نسبی|soil\s*type|نوع\s*خاک|seismic\s*hazard|hazard\s*zone", text, re.I))
