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

import json
import math
import threading
import re
from dataclasses import asdict, dataclass, field
from dataclasses import fields as dc_fields
from typing import Any, Callable

import numpy as np

from app.application import csi_text_export as cte
from app.application import detailing_assumptions as da
from app.application import foundation_design as fnd
from app.application import frame3d_followup as fu
from app.application import frame3d_bays as bays_parser
from app.application.length_units import normalize_digits, parse_length_m, to_metres
from app.application import frame3d_i18n as i18n
from app.application import iran2800
from app.application import mabhas9_rc_design as m9
from app.application.analysis.modal import combine_cqc, cqc_coefficient, generalized_eigen_diag_mass
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
    element_end_forces,
    prepare_second_order,
    reload_space_loads,
    recover_space_result,
    solve_space_many,
    torsion_constant_rectangle,
)
from app.application.analysis.frame3d_solver import SOLVE_CHUNK

P_DELTA_IGNORE = 0.1  # Standard 2800 (4th ed.) §3-6: θ < 0.1 → P-Δ may be ignored
P_DELTA_RULE = ("auto: P-Δ is included for IRAN_2800 projects when the storey stability index θ = Pu·Δe/(V·h) exceeds 0.1 "
                "(Standard 2800 4th ed. §3-6, eq. 3-12); on = always; off = never (θ is still reported)")
KIND = "frame3d_analysis"
DISCLAIMER = (
    "Linear elastic 3D frame analysis with the internal SAIA solver. "
    "Seismic load uses the user-supplied coefficient C (equivalent static); "
    "no Iranian Standard 2800 or Mabhas 9 checks are performed yet. Final "
    "engineering decisions require verification by a qualified engineer."
)
DISCLAIMER_2800 = (
    "Linear elastic 3D frame analysis with the internal SAIA solver. Seismic loads follow "
    "Standard 2800 (4th ed.) as implemented here (equivalent static + response spectrum, simplifications "
    "listed under Assumptions). Not a certified code check; final engineering decisions require "
    "verification by a qualified engineer."
)


def _code_label(inp: "Frame3dInputs") -> str:
    seismic = "Standard 2800 (4th ed.) seismic loads" if inp.seismic_code == "IRAN_2800" else "user-supplied seismic C (no Standard 2800)"
    design = "Mabhas 9 RC design (simplified, see clauses)" if inp.design_code == "MABHAS9" else "no member design (no Mabhas 9 checks)"
    return f"Analysis with {seismic}; {design}"


# model size limits live in frame3d_limits (shared by chat, form, optimisation and downloads)
from app.application.frame3d_limits import BACKGROUND_NODES, node_count  # noqa: E402
from app.application.frame3d_limits import MAX_BAYS, MAX_NODES, MAX_RS_MODES, MAX_SPAN_M, MAX_STOREYS, MIN_SPAN_M  # noqa: E402
RS_ELEMENT_CHUNK = 4000  # elements per vectorised response-spectrum force recovery block


def rs_mode_count(mode_table: list[dict[str, Any]]) -> int:
    """Modes used in the response-spectrum combination: all of them for models with ≤ MAX_RS_MODES diaphragm
    modes (unchanged behaviour), otherwise the leading modes until ≥ 90 % mass in X and Y (Standard 2800 §3-4-2-2),
    but never fewer than MAX_RS_MODES."""
    n = len(mode_table)
    if n <= MAX_RS_MODES:
        return n
    need = MAX_RS_MODES
    for key in ("cum_x_pct", "cum_y_pct"):
        hit = next((m["mode"] for m in mode_table if m[key] >= 90.0), n)
        need = max(need, hit)
    return min(n, need)

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
    allowable_bearing_kpa: float = 150.0
    foundation: bool = False
    lang: str = "en"
    p_delta: str = "auto"  # auto | on | off — second-order (P-Δ) lateral analysis
    # per-project design / rebar-detailing assumptions changed from chat (see detailing_assumptions.py)
    assumptions: dict | None = None
    # optional per-storey sections from the optimizer: {"C1": [b, h], "B1": [b, h], ...} (metres)
    group_sections: dict | None = None
    parsed: list[str] = field(default_factory=list)
    # True when the user said "assume defaults" and the bay spans were filled with the 5 m default (stated in the assumptions)
    spans_assumed: bool = False
    # a bay count given without a direction («۲ دهانه», "3 bays"); never persisted, only used to ask "which direction?"
    pending_bays: int | None = None


INTERNAL_FIELDS = ("parsed", "pending_bays", "spans_assumed")
SPAN_KEYS = ("bay_x_m", "bay_y_m")


def _norm(text: str) -> str:
    return (text or "").translate(_PERSIAN_DIGITS).replace("×", "x").replace("*", "x")


def requested_foundation_view(user_request: str) -> bool:
    """'show foundation' / «فونداسیون را نشان بده» / «نمایش پی» -> SAFE-like footing view."""
    t = _norm(user_request).lower()
    return bool(re.search(r"(?:show|display|view)\s+(?:the\s+)?(?:foundation|footings?)|(?:فونداسیون|پی ?ها?)\s*(?:را\s*)?نشان|نمایش\s*(?:فونداسیون|پی)", t))


def requested_mode_shape(user_request: str) -> int | None:
    """'animate mode 2' / 'show mode shape 3' / «مود ۲ را نشان بده» / «شکل مود ۲» -> mode number."""
    t = _norm(user_request).lower()
    m = re.search(r"(?:animate|show|display|نمایش|انیمیشن|شکل)?\s*(?:mode|مود)\s*(?:shape\s*)?(?:no\.?\s*|شماره\s*)?(\d{1,2})", t)
    if not m or not re.search(r"animate|show|display|view|نشان|نمایش|انیمیشن|شکل|ببینم", t):
        return None
    return int(m.group(1))


def is_frame3d_request(user_request: str) -> bool:
    t = _fa_numbers(_norm(user_request)).lower()  # also maps colloquial «دهنه» -> «دهانه»
    storey = re.search(r"stor(e)?y|stories|storeys|floors?\b|طبقه", t)
    frame = re.search(r"\bframe\b|\bbays?\b|قاب|دهانه|3d|سه ?بعدی", t)
    if storey and frame:
        return True
    # «قاب سه بعدی ... تحلیل کن» / "analyze a 3D frame" without storey words -> frame solver (asks for missing params)
    frame3d = re.search(r"قاب\s*(?:ی\s*)?(?:بتنی\s*|فولادی\s*)?سه\s*‌?\s*بعدی|3d\s*(?:rc\s*|concrete\s*|steel\s*)?frame|ghab(?:e)?\s*3d|space\s*frame", t)
    analyse = re.search(r"تحلیل|analy[sz]|tahlil|solve|حل کن", t)
    return bool(frame3d and analyse)


_EXPORT_WORD = r"export|download|خروجی|اکسپورت|دانلود|فایل"
_REBAR_WORDS = r"آرماتور ?بندی|دیتیل آرماتور|جزئیات آرماتور|جدول (?:وزن )?میلگرد|rebar|reinforcement detail|bar bending|\bbbs\b"
_EXPORT_TARGETS = {
    "e2k": r"etabs|\be2k\b|ایتبس|ای ?تبس",
    "f2k": r"\bsafe\b|\bf2k\b|سیف|سیفی|فونداسیون|پی\b",
    "s2k": r"sap ?2000|\bsap\b|\bs2k\b|ساپ",
    "dxf_plans": r"autocad|auto ?cad|\bdxf\b|\bcad\b|اتوکد|اتو ?کد|نقشه|پلان",
    "dxf_3d": r"autocad|auto ?cad|\bdxf\b|\bcad\b|اتوکد|اتو ?کد|3d|سه ?بعدی",
    "dxf_rebar": _REBAR_WORDS,
    "dxf_foundation": r"نقشه (?:ی )?(?:فونداسیون|پی)|دیتیل (?:فونداسیون|پی)|foundation (?:drawing|detail|sheet|plan)|footing (?:detail|drawing)",
}
_FOUNDATION_DRAWING = _EXPORT_TARGETS["dxf_foundation"]


def requested_export_formats(user_request: str) -> list[str]:
    """Formats asked for in an export prompt ("خروجی ایتبس بده", "export to ETABS/SAFE/AutoCAD")."""
    t = _norm(user_request).lower()
    if re.search(_FOUNDATION_DRAWING, t):  # «نقشه فونداسیون» is itself a drawing request
        return ["dxf_foundation"] + (["dxf_rebar"] if re.search(_REBAR_WORDS, t) else [])
    if re.search(_REBAR_WORDS, t):  # "نقشه آرماتوربندی" is itself a drawing request (no export word needed)
        return ["dxf_rebar"] + [f for f in ("e2k", "f2k", "s2k") if re.search(_EXPORT_TARGETS[f], t)]
    if not re.search(_EXPORT_WORD, t):
        return []
    found = [f for f, pat in _EXPORT_TARGETS.items() if f not in ("dxf_rebar", "dxf_foundation") and re.search(pat, t)]
    if "dxf_3d" in found and "dxf_plans" not in found and not re.search(r"autocad|auto ?cad|dxf|cad|اتوکد|اتو ?کد", t):
        found.remove("dxf_3d")  # "3D" alone (e.g. in a frame description) is not a CAD request
    if re.search(r"\ball\b|همه", t) and found:
        found = [f for f in _EXPORT_TARGETS if f not in ("dxf_rebar", "dxf_foundation")]
    return found


def is_export_request(user_request: str) -> bool:
    """ETABS/SAFE exports always; CAD-only exports when the frame/model is mentioned (other CAD exports keep their agents)."""
    found = requested_export_formats(user_request)
    if {"e2k", "f2k", "s2k", "dxf_rebar", "dxf_foundation"} & set(found):
        return True
    if wants_foundation(user_request) and re.search(r"frame|model|structure|قاب|مدل|سازه", _norm(user_request).lower()):
        return True
    return bool(found) and bool(re.search(r"frame|model|structure|قاب|مدل|سازه", _norm(user_request).lower()))


SPEC_TAG = "[frame3d-spec]"


def frame3d_spec(inp: "Frame3dInputs") -> str:
    """Compact, re-parseable model spec stored as the first line of the project memory."""
    d = {k: v for k, v in asdict(inp).items() if k not in ("parsed", "pending_bays") and v != getattr(Frame3dInputs, k, None)}
    d["_p"] = list(inp.parsed)
    return SPEC_TAG + json.dumps(d, separators=(",", ":"), ensure_ascii=False)


def inputs_from_dict(data: dict[str, Any]) -> "Frame3dInputs":
    allowed = {f.name for f in dc_fields(Frame3dInputs)} - {"parsed", "pending_bays"}
    inp = Frame3dInputs(**{k: v for k, v in data.items() if k in allowed})
    inp.parsed = [str(x) for x in data.get("_p", data.get("parsed_from_request", []))]
    if ("_p" in data or "parsed_from_request" in data) and not inp.spans_assumed:
        # specs / runs stored before spans were required: their spans were whatever the model used, count them as given
        inp.parsed = [*inp.parsed, *[k for k in SPAN_KEYS if k not in inp.parsed]]
    elif "_p" not in data and "parsed_from_request" not in data:
        # a plain inputs dict (stored run / form / tool arguments): a span that is present was given
        inp.parsed = [*inp.parsed, *[k for k in SPAN_KEYS if data.get(k) is not None and k not in inp.parsed]]
    for name in ("storeys", "bays_x", "bays_y"):
        v = getattr(inp, name)
        if v is not None:
            setattr(inp, name, int(v))
    return inp


def prior_frame3d_spec(context: dict[str, Any] | None) -> dict[str, Any] | None:
    """Latest frame spec found in the project memories passed in the agent context."""
    found = None
    for m in (context or {}).get("memories") or []:
        content = str((m or {}).get("content") or "")
        if content.startswith(SPEC_TAG):
            line = content[len(SPEC_TAG):].split("\n", 1)[0]
            try:
                found = json.loads(line)
            except ValueError:
                continue
    return found


def wants_foundation(user_request: str) -> bool:
    t = _norm(user_request).lower()
    return bool(re.search(r"foundation|footing|فونداسیون|(?<![\u0600-\u06FF])پی(?![\u0600-\u06FF])|تنش\s*مجاز|allowable\s+(?:soil\s+)?bearing", t))


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


def _fa_numbers(t: str) -> str:
    """«سه دهانه» -> «3 دهانه»; Persian digits / decimal separators, ZWNJ, «دهنه»→«دهانه», x/y lookalikes (case kept)."""
    return bays_parser.normalize(t, lower=False)


def _parse_fa_storey_height(t: str, inp: "Frame3dInputs") -> None:
    """«طبقات به ارتفاع ۳.۲ متر» (also cm / mm)."""
    if "storey_height_m" in inp.parsed:
        return
    u = rf"({bays_parser.UNIT_PATTERN})"
    m = re.search(rf"ارتفاع(?:\s*(?:هر|طبقات|طبقه|طبقه\s*ها))?[^\d]{{0,15}}{_NUM}\s*{u}", t) or re.search(
        rf"طبقه(?:\s*ها|ات)?[^\d]{{0,12}}(?:به\s*)?ارتفاع[^\d]{{0,6}}{_NUM}\s*{u}?", t)
    if m:
        v = to_metres(float(m.group(1)), m.group(2) if m.lastindex and m.lastindex >= 2 else None)
        if 1.5 <= v <= 8:
            inp.storey_height_m = v; inp.parsed.append("storey_height_m")


_ALONG = re.compile(
    rf"(\d+)\s*(?:دهانه|bays?)\s*(?:در|به|along|in)?\s*(?:راستای|جهت|امتداد|طول|سمت|the)?\s*{_NUM}\s*"
    rf"({bays_parser.UNIT_PATTERN})(?:ی)?", re.I)


def _parse_bays_along_length(t: str, inp: "Frame3dInputs") -> None:
    """«۱۰۰ دهانه در راستای ۱۰۰۰ متری و ۲۰۰ دهانه در راستای ۲۰۰۰ متری» -> bays_x=100 (10 m), bays_y=200 (10 m).

    The first «N bays along L» is X and the second is Y; the span is L/N.
    """
    hits = [(int(m.group(1)), to_metres(float(m.group(2)), m.group(3))) for m in _ALONG.finditer(t)]
    hits = [(n, L) for n, L in hits if n > 0 and L > 0][:2]
    for (n, L), (ck, sk) in zip(hits, (("bays_x", "bay_x_m"), ("bays_y", "bay_y_m"))):
        setattr(inp, ck, n); setattr(inp, sk, round(L / n, 3)); inp.parsed += [ck, sk]


def parse_frame3d_request(user_request: str) -> Frame3dInputs:
    t = _fa_numbers(_norm(user_request))
    inp = Frame3dInputs()
    m = re.search(r"(\d+)\s*-?\s*(?:stor(?:e)?y|stories|storeys|floors?|طبقه)", t, re.I) or re.search(r"طبقات\s*[:=]?\s*(\d+)", t)
    if m:
        inp.storeys = int(m.group(1)); inp.parsed.append("storeys")
    bp = bays_parser.parse_bays(user_request)
    for key, val in {**bp.counts, **bp.spans}.items():
        setattr(inp, key, val); inp.parsed.append(key)
    if not ({"bays_x", "bays_y"} & set(bp.counts)):
        _parse_bays_along_length(t, inp)
    if not ({"bays_x", "bays_y"} & set(inp.parsed)):
        inp.pending_bays = bp.ambiguous
    _parse_fa_storey_height(t, inp)
    if "storey_height_m" not in inp.parsed:
        mh = re.search(rf"(?:stor(?:e)?y|floor)\s*height\s*(?:of|=|:)?\s*{_NUM}\s*({bays_parser.UNIT_PATTERN})", t, re.I)
        if mh:
            inp.storey_height_m = to_metres(float(mh.group(1)), mh.group(2)); inp.parsed.append("storey_height_m")
    _f(t, (rf"ارتفاع\s*طبقه[^\d]{{0,10}}{_NUM}",), inp, "storey_height_m")
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
    qa = re.search(
        rf"(?:allowable\s+(?:soil\s+)?bearing(?:\s+(?:capacity|pressure|stress))?|bearing\s+(?:capacity|pressure)|soil\s+(?:bearing|allowable)[^\d]{{0,12}}"
        rf"|تنش\s*مجاز(?:\s*خاک)?|ظرفیت\s*باربری(?:\s*مجاز)?(?:\s*خاک)?)[^\d]{{0,20}}{_NUM}\s*(kpa|kn/m2|kg/cm2|mpa|کیلوپاسکال|کیلوگرم)?",
        t, re.I)
    if qa:
        unit = (qa.group(2) or "kpa").lower()
        inp.allowable_bearing_kpa = float(qa.group(1)) * ({"kg/cm2": 98.0665, "mpa": 1000.0, "کیلوگرم": 98.0665}.get(unit, 1.0))
        inp.parsed.append("allowable_bearing_kpa")
    inp.foundation = wants_foundation(t)
    inp.lang = i18n.detect_lang(user_request)
    found = iran2800.parse_2800(t)
    for key, value in found.items():
        setattr(inp, key, value); inp.parsed.append(key)
    if found.keys() & {"zone", "soil"} or iran2800.wants_2800(t):
        inp.seismic_code = "IRAN_2800"
    if re.search(r"mabhas|مبحث\s*(?:9|نهم)|\bdesign\b|طراحی", t, re.I):
        inp.design_code = "MABHAS9"
    pd_req = fu.p_delta_request(t)
    if pd_req:
        inp.p_delta = pd_req; inp.parsed.append("p_delta")
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


def column_dims(inp: Frame3dInputs, storey: int) -> tuple[float, float]:
    s = (inp.group_sections or {}).get(f"C{storey}")
    return (float(s[0]), float(s[1])) if s else (inp.column_b_m, inp.column_h_m)


def beam_dims(inp: Frame3dInputs, storey: int) -> tuple[float, float]:
    s = (inp.group_sections or {}).get(f"B{storey}")
    return (float(s[0]), float(s[1])) if s else (inp.beam_b_m, inp.beam_h_m)


_HEAVY_RUNS = threading.BoundedSemaphore(1)  # large models need ~0.2-1.3 GB: run them one at a time per worker


def run_frame3d(inp: Frame3dInputs, *, with_modal: bool = True, with_foundation: bool = True) -> dict[str, Any]:
    if node_count(inp.storeys, inp.bays_x, inp.bays_y) > BACKGROUND_NODES:
        with _HEAVY_RUNS:
            return _run_frame3d(inp, with_modal=with_modal, with_foundation=with_foundation)
    return _run_frame3d(inp, with_modal=with_modal, with_foundation=with_foundation)


def _run_frame3d(inp: Frame3dInputs, *, with_modal: bool = True, with_foundation: bool = True) -> dict[str, Any]:
    nx, ny, ns = inp.bays_x, inp.bays_y, inp.storeys
    XS = [i * inp.bay_x_m for i in range(nx + 1)]
    YS = [j * inp.bay_y_m for j in range(ny + 1)]
    Z = [k * inp.storey_height_m for k in range(ns + 1)]
    fc, h = inp.fc_mpa, inp.storey_height_m
    Ec = 4700 * math.sqrt(fc) * 1000  # kN/m2
    cb, ch, bb, bh = inp.column_b_m, inp.column_h_m, inp.beam_b_m, inp.beam_h_m

    def _props(b: float, d: float, fac: float) -> tuple[float, float, float, float]:
        return b * d, b * d**3 / 12 * fac, d * b**3 / 12 * fac, torsion_constant_rectangle(b, d) * 0.15

    cprop = {k: _props(*column_dims(inp, k), 0.70) for k in range(1, ns + 1)}
    bprop = {k: _props(*beam_dims(inp, k), 0.35) for k in range(1, ns + 1)}
    sw_beam_k = {k: beam_dims(inp, k)[0] * max(beam_dims(inp, k)[1] - inp.slab_t_m, 0.0) * 25.0 for k in range(1, ns + 1)}
    sw_col_k = {k: cprop[k][0] * h * 25.0 for k in range(1, ns + 1)}
    sw_col = sw_col_k[1]
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
            return panels * inp.dead_kn_m2 * tributary(L, other) + sw_beam_k[k] + (wall[k] if edge else 0.0)
        if case == "L":
            return panels * live[k] * tributary(L, other)
        return 0.0

    supports = [SpaceSupport(_nid(i, j, 0)) for i in range(nx + 1) for j in range(ny + 1)]
    cx, cy = XS[-1] / 2, YS[-1] / 2
    diaphragms = [RigidDiaphragm(f"D{k}", f"L{k}", tuple(_nid(i, j, k) for i in range(nx + 1) for j in range(ny + 1)), cx, cy)
                  for k in range(1, ns + 1)]
    ncol_lvl = (nx + 1) * (ny + 1)
    W: dict[int, float] = {}
    WD: dict[int, float] = {}  # unfactored dead / live storey weights (for the P-Δ gravity load Pu)
    WL: dict[int, float] = {}
    for k in range(1, ns + 1):
        wD = sum(beam_w("D", k, L, o, e) * L for _, _, _, kk, L, o, e in beams if kk == k) + ncol_lvl * (0.5 * sw_col_k[k] + (0.5 * sw_col_k[k + 1] if k < ns else 0.0))
        wL = sum(beam_w("L", k, L, o, e) * L for _, _, _, kk, L, o, e in beams if kk == k)
        W[k] = wD + 0.2 * wL
        WD[k], WL[k] = wD, wL

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
        els = [SpaceElement(cid, a, b, Ec, *cprop[k], metadata={"type": "column"}) for cid, a, b, k in cols]
        els += [SpaceElement(bid, a, b, Ec, *bprop[k], udl_gz=-beam_w(case, k, L, o, e), metadata={"type": "beam"})
                for bid, a, b, k, L, o, e in beams]
        nl: list[SpaceNodalLoad] = []
        if case == "D":
            nl = [SpaceNodalLoad(b, fz=-sw_col_k[k]) for _, _, b, k in cols]
        elif case == "Ex":
            nl = [SpaceNodalLoad(_nid(ci, cj, k), fx=F[k], mz=F[k] * (ecc_x + dyc)) for k in F]  # load at mass centre + e
        elif case == "Ey":
            nl = [SpaceNodalLoad(_nid(ci, cj, k), fy=F[k], mz=-F[k] * (ecc_y + dxc)) for k in F]
        return SpaceFrameModel(f"frame3d-{case}", nodes, els, supports, nl, diaphragms)

    cases = ["D", "L"] + (["Ex", "Ey"] if V > 0 else [])
    base: dict[str, dict[str, Any]] = {}
    equilibrium: dict[str, float] = {}
    lateral_prep: dict[str, Any] = {}

    def solve_case(case: str, m: SpaceFrameModel, prep: dict[str, Any]) -> None:
        lv = list(prep["gravity_load"])
        idx = prep["node_index"]
        for ld in m.nodal_loads:
            b0 = idx[ld.node_id] * DOF_PER_NODE
            for o, v in enumerate((ld.fx, ld.fy, ld.fz, ld.mx, ld.my, ld.mz)):
                lv[b0 + o] += v
        r = recover_space_result(m, prep, lv)
        # elastic end forces (internal actions) of all elements at once: K_local·T·u_e + fixed-end forces
        ends_arr = element_end_forces(prep, r.u_full).tolist()
        tr3 = prep["element_arrays"]["tr"][:, :3, :3]
        udl = np.array([(e.udl_gx, e.udl_gy, e.udl_gz) for e in m.elements], dtype=float)
        w_arr = np.einsum("eij,ej->ei", tr3, udl).tolist()
        ids = [e.id for e in m.elements]
        ends, wloc = dict(zip(ids, ends_arr)), dict(zip(ids, w_arr))
        applied = [sum(getattr(l, c) for l in m.nodal_loads) for c in ("fx", "fy", "fz")]
        for e in m.elements:
            L = math.dist(P[e.start_node_id], P[e.end_node_id])
            applied = [applied[0] + e.udl_gx * L, applied[1] + e.udl_gy * L, applied[2] + e.udl_gz * L]
        reac = [sum(r.reactions[s.node_id][c] for s in supports) for c in range(3)]
        equilibrium[case] = max(abs(a + b) for a, b in zip(applied, reac))
        base[case] = {"res": r, "ends": ends, "w": wloc, "reac": reac,
                      "supp": {s.node_id: [float(x) for x in r.reactions[s.node_id]] for s in supports}}

    lateral_models: dict[str, SpaceFrameModel] = {}
    shared_prep: dict[str, Any] | None = None  # every case has the same stiffness: assemble/factor once
    for case in cases:
        m = model(case)
        if shared_prep is None:
            shared_prep = assemble_space_system(m)
            prep = shared_prep
        else:
            prep = reload_space_loads(shared_prep, m)
        if case in ("Ex", "Ey"):
            if "prep" not in lateral_prep:
                lateral_prep["prep"] = prep; lateral_prep["model"] = m
            lateral_models[case] = m
        solve_case(case, m, prep)
    del shared_prep, prep

    # ---- P-Δ (second-order) -------------------------------------------------------------
    def story_drifts(case: str) -> list[float]:
        prev, out = 0.0, []
        ax = 0 if case == "Ex" else 1
        for k in range(1, ns + 1):
            um = max(abs(base[case]["res"].displacements[_nid(i, j, k)][ax]) for i in range(nx + 1) for j in range(ny + 1))
            out.append(um - prev); prev = um
        return out

    p_delta = {"mode": inp.p_delta, "applied": False, "status": "NOT_APPLICABLE", "rule": P_DELTA_RULE, "warnings": []}
    response_prep = None
    first_drifts: dict[str, list[float]] = {}
    theta_rows: dict[str, list[float]] = {}
    if V > 0:
        cd_pd = seismic_info.get("drift_factor", 0.7 * inp.behaviour_r)
        storey_p = [sum(1.2 * WD[j] + 1.0 * WL[j] for j in range(k, ns + 1)) for k in range(1, ns + 1)]  # Pu: 1.2D + 1.0L above
        for E in ("Ex", "Ey"):
            first_drifts[E] = story_drifts(E)
            theta_rows[E] = [storey_p[k - 1] * first_drifts[E][k - 1] / (sum(F[j] for j in range(k, ns + 1)) * h) for k in range(1, ns + 1)]
        theta_max = {E: max(t) for E, t in theta_rows.items()}
        theta_gov = max(theta_max.values())
        theta_lim = min(0.25, 0.65 / cd_pd) if cd_pd > 0 else 0.25
        pd_required = theta_gov > P_DELTA_IGNORE
        mode = inp.p_delta
        want = mode == "on" or (mode == "auto" and inp.seismic_code == "IRAN_2800" and pd_required)
        p_delta.update({
            "gravity_combo": "1.2D+1.0L", "storey_Pu_kn": storey_p, "theta": {E[1].upper(): t for E, t in theta_rows.items()},
            "theta_max": {E[1].upper(): v for E, v in theta_max.items()}, "theta_governing": theta_gov,
            "theta_ignore_below": P_DELTA_IGNORE, "theta_limit": theta_lim, "required_by_theta": pd_required,
            "drift_first_order_mm": {E[1].upper(): [d * 1000 for d in v] for E, v in first_drifts.items()},
            "approx_amplification_1_over_1_minus_theta": {E[1].upper(): [1 / (1 - t) if t < 1 else None for t in v] for E, v in theta_rows.items()},
            "method": "Second-order elastic analysis: K + K_G with member axial forces frozen from 1.2D+1.0L (linear geometric stiffness of each beam-column)",
            "status": "NOT_REQUIRED", "warnings": [],
        })
        if theta_gov > theta_lim:
            p_delta["warnings"].append("theta_exceeds_limit")
        if want:
            comp = {eid: 1.2 * base["D"]["ends"][eid][0] + 1.0 * base["L"]["ends"][eid][0] for eid in base["D"]["ends"]}
            try:
                prep2 = prepare_second_order(lateral_models["Ex"], lateral_prep["prep"], comp)
            except SpaceFrameSolverError as exc:
                p_delta.update({"status": "UNSTABLE", "message": str(exc), "lambda_cr": (exc.details or {}).get("lambda_cr")})
                p_delta["warnings"].append("unstable")
            else:
                for E in ("Ex", "Ey"):
                    solve_case(E, lateral_models[E], prep2)
                response_prep = prep2
                second_drifts = {E: story_drifts(E) for E in ("Ex", "Ey")}
                p_delta.update({
                    "applied": True, "status": "APPLIED", "lambda_cr": prep2["second_order"]["lambda_cr"],
                    "drift_second_order_mm": {E[1].upper(): [d * 1000 for d in v] for E, v in second_drifts.items()},
                    "amplification": {E[1].upper(): [d2 / d1 if d1 > 0 else 1.0 for d1, d2 in zip(first_drifts[E], second_drifts[E])] for E in second_drifts},
                    "base_shear_amplification": {"X": abs(base["Ex"]["reac"][0]) / V, "Y": abs(base["Ey"]["reac"][1]) / V},
                })
        elif mode == "off":
            p_delta["status"] = "OFF"
        if not p_delta["applied"] and pd_required and p_delta["status"] != "UNSTABLE":
            p_delta["warnings"].append("theta_above_0_1_not_included")

    modal = None
    rs_members: dict[str, dict[str, list[float]]] = {}
    if with_modal and V > 0 and inp.seismic_code == "IRAN_2800":
        modal = _modal_response_spectrum(inp, lateral_prep, nodes, XS, YS, Z, W, (ci, cj, dxc, dyc), V, seismic_info,
                                         response_prep=response_prep)
        rs_members = modal.pop("_members")

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

    rs_design = None
    if rs_members:
        rs_design = _merge_rs_member_forces(rs_members, modal, beams, cols, beam_env, col_env, combos, beam_curve, comb_vec)

    drift = []
    if V > 0:
        cd = seismic_info.get("drift_factor", 0.7 * inp.behaviour_r)
        for E, ax in (("Ex", 0), ("Ey", 1)):
            prev = 0.0
            for k in range(1, ns + 1):
                um = max(abs(base[E]["res"].displacements[_nid(i, j, k)][ax]) for i in range(nx + 1) for j in range(ny + 1))
                d = um - prev; prev = um
                row = {"direction": E[1].upper(), "storey": k, "u_max_mm": um * 1000, "drift_elastic_mm": d * 1000,
                       "ratio_elastic": d / h, "ratio_amplified": cd * d / h,
                       "theta": theta_rows[E][k - 1], "p_delta_applied": p_delta["applied"]}
                d1 = first_drifts[E][k - 1]
                row["drift_first_order_mm"] = d1 * 1000
                row["ratio_amplified_first_order"] = cd * d1 / h
                drift.append(row)
    base_shear = None
    if V > 0:
        base_shear = {
            "W_total_kn": W_tot, "C": C, "V_expected_kn": V,
            "V_reaction_x_kn": abs(base["Ex"]["reac"][0]), "V_reaction_y_kn": abs(base["Ey"]["reac"][1]),
        }
        base_shear["error_pct"] = 100 * max(abs(base_shear["V_reaction_x_kn"] - V), abs(base_shear["V_reaction_y_kn"] - V)) / V
    total_gravity = abs(base["D"]["reac"][2]) + abs(base["L"]["reac"][2])
    result = {
        "geometry": {"XS": XS, "YS": YS, "Z": Z},
        "model": {"nodes": len(nodes), "elements": len(cols) + len(beams), "columns": len(cols), "beams": len(beams),
                  "dof": base["D"]["res"].dof_count, "Ec_mpa": Ec / 1000},
        "W_level_kn": W, "F_level_kn": F, "seismic": seismic_info,
        "combos": list(combos), "equilibrium_error_kn": max(equilibrium.values()),
        "gravity_reaction_kn": {"D": abs(base["D"]["reac"][2]), "L": abs(base["L"]["reac"][2]), "D+L": total_gravity},
        "beams": beam_env, "columns": col_env, "drift": drift, "base_shear": base_shear, "modal": modal,
        "p_delta": p_delta, "rs_design": rs_design,
        "viewer": _viewer_raw(nodes, beams, cols, base, cases, combos, supports),
        # data needed by the ETABS/SAFE/DXF exporters (csi_text_export.py)
        "export": {"reactions": {c: base[c]["supp"] for c in cases}, "combo_factors": combos, "sw_col_kn": sw_col,
                   "beam_udl": {bid: {"D": beam_w("D", k, L, o, e), "L": beam_w("L", k, L, o, e)} for bid, a, b, k, L, o, e in beams},
                   "Ec_kn_m2": Ec, "eccentricity": inp.accidental_ecc, "p_delta_applied": p_delta["applied"]},
    }
    result["foundation_design"] = fnd.design_foundation(inp, result) if with_foundation else None
    return result


def _merge_rs_member_forces(rs_members, modal, beams, cols, beam_env, col_env, combos, beam_curve, comb_vec) -> dict[str, Any]:
    """Fold the scaled response-spectrum member forces into the beam/column design envelopes.

    For each gravity combination used with earthquake (1.2D+1.0L and 0.9D) and each direction the CQC
    amplitude R of every member action is added to the gravity action with the worst sign:
    M = ±|M_g| ± R (end moments), V = |V_g| + R, column P = P_g ± R_P, M = |M_g| + R. R already contains the
    dynamic-base-shear scale factor, so a dynamic base shear below 85 % (regular) / 90 % (irregular) of the
    static value is raised before it is combined. The static-equivalent combinations stay in the envelope, so the
    design is the maximum of both methods. The sum of absolute values is conservative (peaks are not simultaneous).
    """
    gravity = (("1.2D+1.0L", {"D": 1.2, "L": 1.0}), ("0.9D", {"D": 0.9}))
    beam_by_id = {b["id"]: b for b in beam_env}
    n_beam = n_col = 0
    for bid, a, b, k, L, o, e in beams:
        be = beam_by_id[bid]
        M0, _ = beam_curve(combos["1.4D"], bid, L)
        s0 = 1.0 if M0[len(M0) // 2] >= 0 else -1.0
        hit = False
        for dname in ("X", "Y"):
            r = rs_members[dname][bid]
            for gname, gcf in gravity:
                M, Vv = beam_curve(gcf, bid, L)
                cn = f"{gname}±RS{dname}"
                for gm, rm in ((s0 * M[0], r[4]), (s0 * M[-1], r[10])):
                    neg, pos = rm - gm, gm + rm
                    if neg > be["M_neg_end_kn_m"]: be["M_neg_end_kn_m"] = neg; hit = True
                    if pos > be["M_pos_end_kn_m"]: be["M_pos_end_kn_m"] = pos; hit = True
                    if neg > be["M_neg_kn_m"]: be["M_neg_kn_m"] = neg; be["governing"]["M_neg"] = cn
                    if pos > be["M_pos_kn_m"]: be["M_pos_kn_m"] = pos; be["governing"]["M_pos"] = cn
                vm = max(abs(Vv[0]) + abs(r[2]), abs(Vv[-1]) + abs(r[8]))
                if vm > be["V_kn"]: be["V_kn"] = vm; be["governing"]["V"] = cn; hit = True
        n_beam += hit
    col_by_id = {c["id"]: c for c in col_env}
    for cid, a, b, k in cols:
        ce = col_by_id[cid]
        hit = False
        for dname in ("X", "Y"):
            r = rs_members[dname][cid]
            for gname, gcf in gravity:
                f = comb_vec(gcf, "ends", cid)
                for sg in (1.0, -1.0):
                    cn = f"{gname}{'+' if sg > 0 else '-'}RS{dname}"
                    p_val = f[0] + sg * abs(r[0])
                    ends = [(abs(f[4]) + abs(r[4]), abs(f[5]) + abs(r[5])), (abs(f[10]) + abs(r[10]), abs(f[11]) + abs(r[11]))]
                    ce["records"].append({"combo": cn, "seismic": True, "P": p_val, "ends": ends})
                    if p_val > ce["P_kn"]: ce["P_kn"] = p_val; ce["governing"]["P"] = cn; hit = True
                    mu = max(max(x) for x in ends)
                    if mu > ce["M_kn_m"]: ce["M_kn_m"] = mu; ce["governing"]["M"] = cn; hit = True
        n_col += hit
    return {"used": True, "scale_factor": {d: modal["response_spectrum"][d]["scale_factor"] for d in ("X", "Y")},
            "scaled_up_to_minimum": {d: modal["response_spectrum"][d]["scaled_to_minimum"] for d in ("X", "Y")},
            "V_scaled_over_static": {d: modal["response_spectrum"][d]["V_scaled_over_static"] for d in ("X", "Y")},
            "beams_governed_by_rs": n_beam, "columns_governed_by_rs": n_col,
            "combinations": [f"{g}±RS{d}" for d in ("X", "Y") for g, _ in gravity],
            "note": "RS member forces: CQC, 5 % damping, 5 % accidental torsion, scaled to ≥ 85 % (regular) / 90 % (irregular) of V_static"}


G = 9.81
DUCTILITY = {"RC_SMF": "special", "RC_IMF": "intermediate", "RC_OMF": "ordinary"}


def design_mabhas9(inp: "Frame3dInputs", raw: dict[str, Any]) -> dict[str, Any]:
    """Group-wise Mabhas 9 design of beams (storey × direction × edge/interior) and columns (storey × position)."""
    ductility = DUCTILITY.get(inp.system)
    if ductility is None:
        return {"code": "MABHAS9", "status": "NOT_APPLICABLE",
                "message": "Mabhas 9 RC design applies to RC systems only (steel / Mabhas 10 not implemented)."}
    with da.design_overrides(m9, inp.assumptions):
        return _apply_scwb_rule(_design_mabhas9(inp, raw, ductility), da.effective(inp.assumptions)["scwb"])


def _apply_scwb_rule(design: dict[str, Any], rule: str) -> dict[str, Any]:
    """Assumption 'scwb': auto (code default) | check (always governs) | skip (not applicable, reported only)."""
    if rule == "skip":
        design["scwb_status"] = "NOT_APPLIED"
        design["status"] = design["member_status"]
        design["scwb_note"] += " — not applied (project assumption)"
    elif rule == "check" and design.get("scwb_status") == "FAIL":
        design["status"] = "FAIL"
    return design


def _design_mabhas9(inp: "Frame3dInputs", raw: dict[str, Any], ductility: str) -> dict[str, Any]:
    fc, fy = inp.fc_mpa, inp.fy_mpa
    groups: dict[tuple, list[dict]] = {}
    for b in raw["beams"]:
        groups.setdefault((b["storey"], b["direction"], b["position"]), []).append(b)
    beam_rows, beam_by_id = [], {}
    for (k, dirn, pos), members in sorted(groups.items()):
        env = {key: max(m[key] for m in members) for key in ("M_neg_end_kn_m", "M_pos_end_kn_m", "M_pos_mid_kn_m", "V_kn")}
        bb, bh = (x * 1000 for x in beam_dims(inp, k))
        d = m9.design_beam(m_neg_end=env["M_neg_end_kn_m"], m_pos_end=env["M_pos_end_kn_m"], m_pos_mid=env["M_pos_mid_kn_m"],
                           vu=env["V_kn"], b=bb, h=bh, fc=fc, fy=fy, ductility=ductility)
        row = {"group": f"B-{dirn}-S{k}-{pos}", "storey": k, "direction": dirn, "position": pos, "members": len(members),
               "Mu_neg_kn_m": round(env["M_neg_end_kn_m"], 1), "Mu_pos_kn_m": round(max(env["M_pos_end_kn_m"], env["M_pos_mid_kn_m"]), 1),
               "Vu_kn": round(env["V_kn"], 1), "As_top_req_mm2": round(d.get("As_top_req_mm2") or 0), "As_bot_req_mm2": round(d.get("As_bot_req_mm2") or 0),
               "top_bars": d.get("top_bars"), "bottom_bars": d.get("bottom_bars"),
               "stirrups": (d.get("shear") or {}).get("stirrups"), "DC_flexure": round(d["DC_flexure"], 3) if d.get("DC_flexure") is not None else None,
               "DC_shear": round(d["DC_shear"], 3) if d.get("DC_shear") is not None else None, "status": d["status"], "notes": d.get("notes", []),
               "rebar_basis": d.get("rebar_basis", "DESIGN"), "suggested_section": (d.get("suggested_section") or {}).get("text")}
        beam_rows.append(row)
        for m in members:
            beam_by_id[m["id"]] = d
    cgroups: dict[tuple, list[dict]] = {}
    for c in raw["columns"]:
        cgroups.setdefault((c["storey"], c["position"]), []).append(c)
    col_rows, col_by_id = [], {}
    for (k, pos), members in sorted(cgroups.items()):
        cb, ch = (x * 1000 for x in column_dims(inp, k))
        clear = inp.storey_height_m * 1000 - beam_dims(inp, k)[1] * 1000
        d = m9.design_column_group({m["id"]: m["records"] for m in members}, cb, ch, fc, fy, clear)
        gov = d.get("governing") or {}
        col_rows.append({"group": f"C-S{k}-{pos}", "storey": k, "position": pos, "members": len(members),
                         "Pu_kn": round(gov.get("Pu_kn", 0), 1), "Mu_y_kn_m": round(gov.get("Mu_y_kn_m", 0), 1),
                         "Mu_z_kn_m": round(gov.get("Mu_z_kn_m", 0), 1), "governing_combo": gov.get("combo"),
                         "bars": d.get("bars"), "rho_pct": round(d.get("rho", 0) * 100, 2), "ties": (d.get("ties") or {}).get("text"),
                         "DC": round(d["DC"], 3), "status": d["status"], "notes": d.get("notes", []),
                         "rebar_basis": d.get("rebar_basis", "DESIGN"), "suggested_section": (d.get("suggested_section") or {}).get("text")})
        for m in members:
            col_by_id[m["id"]] = (d, m)
    # strong column / weak beam at every joint below the roof
    nx, ny, ns = inp.bays_x, inp.bays_y, inp.storeys
    joints = []
    for k in range(1, ns):
        worst = None; fails = 0; count = 0
        for i in range(nx + 1):
            for j in range(ny + 1):
                mnc = 0.0
                for kk, cid in ((k, f"C{i}_{j}_{k}"), (k + 1, f"C{i}_{j}_{k+1}")):
                    d, m = col_by_id[cid]
                    cb, ch = (x * 1000 for x in column_dims(inp, kk))
                    if "nface" not in d:
                        continue
                    ps = [r["P"] for r in m["records"] if r["seismic"]] or [r["P"] for r in m["records"]]
                    mnc += min(m9.column_moment_resistance(p, bw, bd, d["nface"], d["db"], fc, fy, nominal=True)
                               for p in ps for bw, bd in ((cb, ch), (ch, cb)))
                for dirn, left, right in (("X", f"BX{i-1}_{j}_{k}" if i > 0 else None, f"BX{i}_{j}_{k}" if i < nx else None),
                                          ("Y", f"BY{i}_{j-1}_{k}" if j > 0 else None, f"BY{i}_{j}_{k}" if j < ny else None)):
                    def mn(bid, key):
                        dd = beam_by_id.get(bid) if bid else None
                        return dd.get(key, 0.0) if dd else 0.0
                    mnb = max(mn(left, "Mn_top_kn_m") + mn(right, "Mn_bot_kn_m"), mn(left, "Mn_bot_kn_m") + mn(right, "Mn_top_kn_m"))
                    if mnb <= 0:
                        continue
                    ratio = mnc / mnb; count += 1
                    if ratio < 1.2:
                        fails += 1
                    if worst is None or ratio < worst[0]:
                        worst = (ratio, f"N{i}_{j}_{k}", dirn)
        if worst:
            joints.append({"level": k, "min_ratio": round(worst[0], 3), "joint": worst[1], "direction": worst[2],
                           "joints_checked": count, "joints_below_1_2": fails, "status": "PASS" if fails == 0 else "FAIL"})
    all_rows = beam_rows + col_rows
    max_dc = max([r["DC_flexure"] or 0 for r in beam_rows] + [r["DC_shear"] or 0 for r in beam_rows] + [r["DC"] for r in col_rows])
    n_fail = sum(1 for r in all_rows if r["status"] != "PASS")
    scwb_note = ("mandatory for special frames" if ductility == "special"
                 else "reported as a check; verify applicability for this ductility level")
    scwb_fail = any(j["status"] != "PASS" for j in joints)
    member_status = "PASS" if n_fail == 0 else "FAIL"
    overall = "FAIL" if member_status == "FAIL" or (scwb_fail and ductility == "special") else ("CHECK" if scwb_fail else "PASS")
    return {"code": "MABHAS9", "status": overall, "member_status": member_status,
            "scwb_status": "FAIL" if scwb_fail else "PASS", "ductility": ductility,
            "phi_c": m9.PHI_C, "phi_s": m9.PHI_S, "beams": beam_rows, "columns": col_rows, "scwb": joints,
            "scwb_note": f"ΣMnc ≥ 1.2·ΣMnb ({scwb_note})",
            "summary": {"max_DC": round(max_dc, 3), "groups": len(all_rows), "groups_failing": n_fail,
                        "scwb_min_ratio": min((j["min_ratio"] for j in joints), default=None)},
            "clauses_implemented": m9.CLAUSES_IMPLEMENTED, "clauses_simplified": m9.CLAUSES_SIMPLIFIED,
            "analysis_basis": ("Member forces: envelope of the equivalent static load cases and the response-spectrum (CQC, scaled to the minimum dynamic base shear, ±5% accidental torsion) load cases"
                               if raw.get("rs_design") else
                               "Member forces from the equivalent static load cases (no response-spectrum member forces: modal analysis not available or not Standard 2800)")
                              + ("; second-order P-Δ analysis included" if (raw.get("p_delta") or {}).get("applied") else "; first-order analysis (P-Δ not included)"),
            "special_frame_note": "Special-frame detailing (capacity shear, joint shear, Ash confinement) not implemented" if ductility == "special" else None}


def _modal_response_spectrum(inp, lateral_prep, nodes, XS, YS, Z, W, centre, V_static, info, response_prep=None) -> dict[str, Any]:
    """Modal + response-spectrum analysis on the diaphragm DOFs (ux, uy, rz per storey).

    Lateral stiffness is condensed from the full 3D model by unit loads at each diaphragm
    centre (exact static condensation for massless joints). Storey masses W/g with polar
    inertia m(Lx²+Ly²)/12 about the plan centre (uniform mass distribution assumed).
    Eigen-solution: numpy.linalg.eigh on the mass-normalised stiffness. Modal inertia forces are
    applied to the full 3D model (``response_prep`` = elastic system, or the second-order K+K_G system
    when P-Δ is active) to get drifts and member forces; modes are combined with CQC (5 % damping).
    Accidental torsion: for each direction the modal storey forces are applied with an additional
    torque ±ecc·L_perp·F_k (ecc = ``inp.accidental_ecc``, 5 %); the worse sign governs each result.
    Results are scaled by max(1, k·V_static/V_dynamic) (k = 0.85 regular / 0.90 irregular).
    Member end forces (CQC magnitudes, scaled) are returned under ``_members`` for design.
    """
    ci, cj, dxc, dyc = centre
    prep, model = lateral_prep["prep"], lateral_prep["model"]
    rprep = response_prep or prep
    idx = prep["node_index"]
    n_full = prep["n_full"]
    ns = len(Z) - 1
    nx, ny = len(XS) - 1, len(YS) - 1
    n = 3 * ns

    def load_vec(forces: list[float]) -> np.ndarray:
        lv = np.zeros(n_full)
        for k in range(1, ns + 1):
            fx, fy, mz = forces[3 * (k - 1): 3 * k]
            b0 = idx[_nid(ci, cj, k)] * DOF_PER_NODE
            lv[b0] += fx; lv[b0 + 1] += fy; lv[b0 + 5] += mz + fx * dyc - fy * dxc
        return lv

    def centre_disp(u) -> list[float]:
        out = []
        for k in range(1, ns + 1):
            b0 = idx[_nid(ci, cj, k)] * DOF_PER_NODE
            ux, uy, rz = float(u[b0]), float(u[b0 + 1]), float(u[b0 + 5])
            out += [ux + rz * dyc, uy - rz * dxc, rz]
        return out

    flex_cols = []
    for c0 in range(0, n, SOLVE_CHUNK):  # unit loads at each diaphragm DOF, solved in chunks (bounded memory)
        cols_c = range(c0, min(n, c0 + SOLVE_CHUNK))
        ufl = solve_space_many(prep, [load_vec([1.0 if q == col else 0.0 for q in range(n)]) for col in cols_c])
        flex_cols += [centre_disp(ufl[:, c]) for c in range(len(cols_c))]
    flex = np.array(flex_cols).T
    flex = 0.5 * (flex + flex.T)
    stiff = np.linalg.inv(flex).tolist()
    lx, ly = XS[-1], YS[-1]
    mass = []
    for k in range(1, ns + 1):
        m = W[k] / G
        mass += [m, m, m * (lx * lx + ly * ly) / 12.0]
    modes = generalized_eigen_diag_mass(stiff, mass)
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
    m_modes = rs_mode_count(mode_table)  # all modes for small models; large ones keep the leading modes (≥ 90 % mass)
    rs_omegas = omegas[:m_modes]
    rho = np.array([[1.0 if i == j else cqc_coefficient(omegas[i], omegas[j]) for j in range(m_modes)] for i in range(m_modes)])
    plan = [(ii, jj) for ii in range(nx + 1) for jj in range(ny + 1)]
    top_idx = np.array([[idx[_nid(ii, jj, k)] * DOF_PER_NODE for ii, jj in plan] for k in range(1, ns + 1)])
    bot_idx = np.array([[idx[_nid(ii, jj, k - 1)] * DOF_PER_NODE for ii, jj in plan] for k in range(1, ns + 1)])
    elem_ids = [e.id for e in model.elements]
    rs, members, h = {}, {}, Z[1] - Z[0]
    ecc_by_dir = {"X": inp.accidental_ecc * YS[-1], "Y": inp.accidental_ecc * XS[-1]}
    for dname, off in (("X", 0), ("Y", 1)):
        ecc = ecc_by_dir[dname]
        shears, base_forces = [], []
        for r in rows[:m_modes]:
            phi = r["phi"]
            gamma = sum(mass[i] * phi[i] for i in range(off, n, 3))  # φᵀMφ = 1
            sa = a * iran2800.spectral_b(r["T"], inp.soil, inp.zone) * I / R * G
            forces = [mass[i] * phi[i] * gamma * sa for i in range(n)]
            shears.append(sum(forces[off::3]))
            base_forces.append(forces)
        signs = (1.0, -1.0) if ecc > 0 else (1.0,)
        loads = []
        for sg in signs:
            for forces in base_forces:
                f2 = list(forces)
                for k in range(ns):
                    f2[3 * k + 2] += sg * ecc * forces[3 * k + off]  # accidental torsion ±ecc·F_k
                loads.append(load_vec(f2))
        u_all = solve_space_many(rprep, loads)  # n_full × (len(signs)·m)
        v_dyn = combine_cqc(shears, rs_omegas)
        scale = max(1.0, info["dynamic_scale_min"] * V_static / v_dyn) if v_dyn > 0 else 1.0
        worst_drift = np.zeros(ns)
        member_cqc = np.zeros((len(elem_ids), 12))
        for si_, sg in enumerate(signs):
            u_s = u_all[:, si_ * m_modes:(si_ + 1) * m_modes]  # n_full × m
            dm = u_s[top_idx + off, :] - u_s[bot_idx + off, :]  # ns × nodes × m
            cq = np.sqrt(np.maximum(np.einsum("kpm,mn,kpn->kp", dm, rho, dm), 0.0))
            worst_drift = np.maximum(worst_drift, cq.max(axis=1))
            for e0 in range(0, len(elem_ids), RS_ELEMENT_CHUNK):  # ends_local = (K_local·T)·u_e (no member loads)
                sub = {"element_arrays": {k: v[e0:e0 + RS_ELEMENT_CHUNK] for k, v in rprep["element_arrays"].items()}}
                ends = element_end_forces(sub, u_s)  # E × 12 × m
                member_cqc[e0:e0 + RS_ELEMENT_CHUNK] = np.maximum(
                    member_cqc[e0:e0 + RS_ELEMENT_CHUNK], np.sqrt(np.maximum(np.einsum("ecm,mn,ecn->ec", ends, rho, ends), 0.0)))
        drift_rows = []
        for k in range(ns):
            de = float(worst_drift[k]) * scale
            drift_rows.append({"storey": k + 1, "drift_elastic_mm": de * 1000, "ratio_elastic": de / h,
                               "ratio_amplified": info["drift_factor"] * de / h})
        rs[dname] = {"V_dynamic_kn": v_dyn, "V_static_kn": V_static, "ratio": v_dyn / V_static,
                     "scale_factor": scale, "V_dynamic_scaled_kn": v_dyn * scale, "drift": drift_rows,
                     "accidental_torsion": ecc > 0, "scaled_to_minimum": scale > 1.0 + 1e-9, "V_scaled_over_static": v_dyn * scale / V_static}
        members[dname] = dict(zip(elem_ids, (scale * member_cqc).tolist()))
    modes_90 = {key: next((m["mode"] for m in mode_table if m[f"cum_{key.lower()}_pct"] >= 90.0), None) for key in ("X", "Y")}
    # nodal mode shapes for the viewer animation: static response to the modal inertia forces ω²·M·φ, normalised to 1
    n_shapes = min(MAX_MODE_SHAPES, m_modes)
    u_sh = solve_space_many(prep, [load_vec([mass[q] * rows[i]["phi"][q] * omegas[i] ** 2 for q in range(n)]) for i in range(n_shapes)])
    shapes = []
    for i in range(n_shapes):
        r = rows[i]
        disp = {nd.id: [float(u_sh[idx[nd.id] * DOF_PER_NODE + c, i]) for c in range(3)] for nd in nodes}
        peak = max((max(abs(c) for c in u) for u in disp.values()), default=0.0) or 1.0
        t_row = mode_table[i]
        shapes.append({"mode": i + 1, "T_s": round(r["T"], 4), "freq_hz": round(1.0 / r["T"], 4),
                       "mass_x_pct": round(t_row["mass_x_pct"], 2), "mass_y_pct": round(t_row["mass_y_pct"], 2),
                       "mass_rz_pct": round(t_row["mass_rz_pct"], 2),
                       "disp": {nid: [round(c / peak, 4) for c in u] for nid, u in disp.items()}})
    return {"shapes": shapes, "method": "Modal (condensed diaphragm DOFs, numpy eigh) + Standard 2800 design spectrum A·B·I/R, CQC (5% damping)"
            + (", 5% accidental torsion" if inp.accidental_ecc > 0 else ""),
            "modes": mode_table, "modes_for_90pct": modes_90, "response_spectrum": rs,
            "T_fundamental_s": mode_table[0]["T_s"] if mode_table else None,
            "_members": members}


# --------------------------------------------------------------------------- payload
_LABELS = {
    "storeys": "number of storeys", "bays_x": "number of bays in X", "bays_y": "number of bays in Y",
    "bay_x_m": "bay span in X (m)", "bay_y_m": "bay span in Y (m)",
}
_LABELS_FA = {
    "storeys": "تعداد طبقات", "bays_x": "تعداد دهانه x", "bays_y": "تعداد دهانه y",
    "bay_x_m": "طول دهانه x (متر)", "bay_y_m": "طول دهانه y (متر)",
}


def input_labels(keys: list[str], lang: str) -> list[str]:
    """Friendly labels for raw input keys (never show ``bays_x`` / ``bay_x_m`` to users)."""
    table = _LABELS_FA if lang == "fa" else _LABELS
    return [table.get(k) or fu.friendly_label(k, lang == "fa") for k in keys]


def missing_inputs(inp: Frame3dInputs) -> list[str]:
    """Required geometry: storeys, bay counts and bay spans in X and Y. Counts / spans are never guessed silently;
    spans count as given when the user wrote them (``parsed``) or said "assume defaults" (``spans_assumed``)."""
    names = [name for name in ("storeys", "bays_x", "bays_y") if getattr(inp, name) is None]
    if not inp.spans_assumed:
        names += [name for name in SPAN_KEYS if name not in inp.parsed]
    return names


def _r(v: float, n: int = 2) -> float:
    return round(float(v), n)


def _loc(payload: dict[str, Any]) -> dict[str, Any]:
    """Persian prompt -> Persian free text (status codes / ids / numbers stay as they are)."""
    return i18n.translate_payload(payload) if payload.get("lang") == "fa" else payload


MAX_MODE_SHAPES = 6
MAX_INSPECTOR_MEMBERS = 4000


def _viewer_raw(nodes, beams, cols, base, cases, combos, supports) -> dict[str, Any]:
    """Compact per-case data for the interactive 3D viewer (linear: combos are rebuilt client-side from factors).

    member force row per case: [N (compression +), V at i-end, M at i-end, M at j-end, w (local UDL)];
    M(x) = Mi + (Mj-Mi)x/L + w(x^2 - xL)/2 for the major plane (beams: vertical plane; columns: plane with larger end M).
    """
    def r3(v: float, n: int = 2) -> float:
        return round(float(v), n)
    members = [{"id": bid, "i": a, "j": b, "type": "beam", "storey": k} for bid, a, b, k, *_ in beams] + \
              [{"id": cid, "i": a, "j": b, "type": "column", "storey": k} for cid, a, b, k in cols]
    forces: dict[str, dict[str, list[float]]] = {}
    forces6: dict[str, dict[str, list[float]]] = {}
    disp: dict[str, dict[str, list[float]]] = {}
    # Member inspector: full local end forces (skipped for very large models to keep the payload small).
    with_f6 = len(members) <= MAX_INSPECTOR_MEMBERS
    for c in cases:
        ends, w = base[c]["ends"], base[c]["w"]
        row = {}
        if with_f6:
            # [N, V2, V3, T, M2, M3] at i then j; i-end as the solver's local end force, j-end negated
            # (same sign as the existing N (compression +) / M j convention).
            forces6[c] = {m["id"]: [r3(x) for x in ends[m["id"]][:6]] + [r3(-x) for x in ends[m["id"]][6:12]] for m in members}
        for m in members:
            f = ends[m["id"]]
            if m["type"] == "beam":
                row[m["id"]] = [r3(f[0]), r3(f[2]), r3(f[4]), r3(-f[10]), r3(w[m["id"]][2], 3)]
            else:
                use_y = max(abs(f[4]), abs(f[10])) >= max(abs(f[5]), abs(f[11]))
                mi, mj, v = (f[4], -f[10], f[2]) if use_y else (f[5], -f[11], -f[1])
                row[m["id"]] = [r3(f[0]), r3(v), r3(mi), r3(mj), 0.0]
        forces[c] = row
        d = base[c]["res"].displacements
        disp[c] = {n.id: [r3(d[n.id][0] * 1000, 3), r3(d[n.id][1] * 1000, 3), r3(d[n.id][2] * 1000, 3)] for n in nodes}
    return {
        "nodes": [{"id": n.id, "x": n.x, "y": n.y, "z": n.z} for n in nodes],
        "supports": [s.node_id for s in supports],
        "members": members, "cases": list(cases), "combos": combos,
        "forces": forces, "forces6": forces6, "displacements_mm": disp,
        "reactions": {c: {nid: [r3(x) for x in v] for nid, v in base[c]["supp"].items()} for c in cases},
    }


def _sections_text(inp: "Frame3dInputs") -> str:
    """Uniform sections, or the per-storey (optimized) ones when group_sections is set."""
    if not inp.group_sections:
        return f"C {inp.column_b_m*100:g}×{inp.column_h_m*100:g}, B {inp.beam_b_m*100:g}×{inp.beam_h_m*100:g}"
    def fmt(kind: str, dims) -> str:
        seen: list[str] = []
        for st in range(1, inp.storeys + 1):
            b, h = dims(inp, st)
            t = f"{b*100:g}×{h*100:g}"
            if t not in seen:
                seen.append(t)
        return f"{kind} " + " / ".join(seen)
    return f"{fmt('C', column_dims)}, {fmt('B', beam_dims)}"


def _viewer_payload(raw: dict[str, Any], inp: "Frame3dInputs", design: dict[str, Any] | None, fdn: dict[str, Any] | None) -> dict[str, Any] | None:
    v = raw.get("viewer")
    if not v:
        return None
    nx, ny = inp.bays_x, inp.bays_y
    groups: dict[tuple, dict] = {}
    if design:
        for r in design.get("beams", []):
            groups[("beam", r.get("storey"), r.get("direction"), r.get("position"))] = r
        for r in design.get("columns", []):
            groups[("column", r.get("storey"), None, r.get("position"))] = r
    members = []
    for m in v["members"]:
        ii, jj = (int(x) for x in m["id"][2 if m["type"] == "beam" else 1:].split("_")[:2])
        if m["type"] == "beam":
            d = m["id"][1]
            edge = (jj in (0, ny)) if d == "X" else (ii in (0, nx))
            key = ("beam", m["storey"], d, "edge" if edge else "interior")
            b, h = beam_dims(inp, m["storey"])  # optimizer per-storey sections honoured
            section = f"B{round(b * 100)}x{round(h * 100)}"
        else:
            on_x, on_y = ii in (0, nx), jj in (0, ny)
            key = ("column", m["storey"], None, "corner" if on_x and on_y else "edge" if on_x or on_y else "interior")
            b, h = column_dims(inp, m["storey"])
            section = f"C{round(b * 100)}x{round(h * 100)}"
        g = groups.get(key)
        dc = None
        if g:
            dc = max(x for x in (g.get("DC_flexure"), g.get("DC_shear"), g.get("DC")) if isinstance(x, (int, float))) if any(
                isinstance(g.get(k), (int, float)) for k in ("DC_flexure", "DC_shear", "DC")) else None
        members.append({**m, "section": section, "b": b, "h": h, "group": g.get("group") if g else None,
                        "dc": dc, "design_status": g.get("status") if g else None,
                        "rebar": (f"{g.get('top_bars')} / {g.get('bottom_bars')}" if m["type"] == "beam" else g.get("bars")) if g else None})
    return {**{k: v[k] for k in ("nodes", "supports", "cases", "combos", "forces", "displacements_mm", "reactions")},
            "members": members,
            "forces6": v.get("forces6") or {},
            "material": {"type": "concrete", "fc_mpa": inp.fc_mpa, "fy_mpa": inp.fy_mpa},
            "footings": (fdn or {}).get("footings") or [],
            "diaphragm_levels": list(range(1, inp.storeys + 1)),
            "modes": (raw.get("modal") or {}).get("shapes") or []}


def _finite(o: Any) -> Any:
    """JSON-safe payload (Postgres json rejects Infinity/NaN): ±inf (D/C of an inadequate section) -> ±999, NaN -> 0."""
    if isinstance(o, float):
        if math.isnan(o):
            return 0.0
        return o if math.isfinite(o) else math.copysign(999.0, o)
    if isinstance(o, dict):
        return {k: _finite(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_finite(v) for v in o]
    return o


def build_frame3d_payload(user_request: str, prior_spec: dict[str, Any] | None = None, *,
                          manual_inputs: dict[str, Any] | None = None) -> dict[str, Any] | None:
    payload = _build_frame3d_payload(user_request, prior_spec, manual_inputs=manual_inputs)
    return _finite(payload) if payload is not None else None


def _build_frame3d_payload(user_request: str, prior_spec: dict[str, Any] | None = None, *,
                          manual_inputs: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Analyse a described frame, or re-run the project's last frame when only an export is asked for.

    `manual_inputs` (from the manual Model page form) bypasses prompt parsing; every given key counts as user input."""
    export_formats = requested_export_formats(user_request) if (is_export_request(user_request) or is_frame3d_request(user_request)) else []
    from_memory = False
    model_changes: list[str] = []
    followup_notes: list[str] = []
    a_upd, inp_upd = da.parse_assumptions(user_request) if manual_inputs is None else ({}, {})
    show_assumptions = manual_inputs is None and da.is_show_assumptions(user_request)
    # input-only values (fy, fc, ...) count as an assumption command only on an existing project frame
    animate_mode = requested_mode_shape(user_request) if manual_inputs is None else None
    show_foundation = manual_inputs is None and requested_foundation_view(user_request)
    assumption_cmd = bool(a_upd or show_assumptions or (inp_upd and prior_spec) or animate_mode or show_foundation)
    if manual_inputs is not None:
        inp = inputs_from_dict(manual_inputs)
        inp.parsed = [k for k, v in manual_inputs.items() if v is not None and not k.startswith("_")]
        if not user_request:
            user_request = "فارسی" if manual_inputs.get("lang") == "fa" else "manual"
        export_formats = []
    elif is_frame3d_request(user_request):
        inp = parse_frame3d_request(user_request)
        model_changes = fu.apply_edits(inp, {k: v for k, v in fu.model_edits(user_request).items() if k in fu.GEOMETRY_KEYS})
    elif prior_spec and (fu.is_model_edit(user_request) or (fu.is_param_edit(user_request) and not wants_foundation(user_request))) and not export_formats:
        inp = inputs_from_dict(prior_spec); from_memory = True
        follow = parse_frame3d_request(user_request)
        edits = {k: getattr(follow, k) for k in follow.parsed if k not in ("storeys", "bays_x", "bays_y") or getattr(follow, k) is not None}
        if follow.seismic_code == "IRAN_2800" and "seismic_code" not in edits:
            edits["seismic_code"] = "IRAN_2800"
        own = fu.model_edits(user_request)
        if {"bay_x_m", "bay_y_m"} & set(own):  # «دهانه x را ۶ متر کن» changes X only
            edits = {k: v for k, v in edits.items() if k not in ("bay_x_m", "bay_y_m")}
        edits.update(own)
        model_changes = fu.apply_edits(inp, edits)
        if "_unsupported" in edits:
            followup_notes.append("us_codes")
        if "_units" in edits:
            followup_notes.append("units")
        if inp.group_sections and {"column_b_m", "column_h_m", "beam_b_m", "beam_h_m"} & set(model_changes):
            inp.group_sections = None  # explicit uniform section replaces the optimizer's per-storey groups
    elif fu.is_assume_reply(user_request) and fu.is_frame_followup(user_request):
        inp = parse_frame3d_request(user_request)
        model_changes = fu.apply_edits(inp, fu.model_edits(user_request))
    elif (export_formats or wants_foundation(user_request) or assumption_cmd) and prior_spec:
        inp = inputs_from_dict(prior_spec); from_memory = True
        follow = parse_frame3d_request(user_request)
        if wants_foundation(user_request):
            inp.foundation = True
        if "dxf_rebar" in export_formats or "dxf_foundation" in export_formats or a_upd:
            inp.design_code = "MABHAS9"
        if "dxf_foundation" in export_formats:
            inp.foundation = True
        if show_foundation:
            inp.foundation = True
        if animate_mode:
            inp.seismic_code = "IRAN_2800"  # mode shapes come from the 2800 modal analysis  # detailing is built from the Mabhas 9 design groups
        if "allowable_bearing_kpa" in follow.parsed:
            inp.allowable_bearing_kpa = follow.allowable_bearing_kpa
            inp.parsed = [*inp.parsed, "allowable_bearing_kpa"]
    elif export_formats or assumption_cmd or (wants_foundation(user_request) and is_export_request(user_request)):
        msg = ("No 3D frame analysis was found in this project (needed for the export / foundation design). Describe the frame first, e.g. "
               "`3-storey RC frame, 2x2 bays of 5 m, storey height 3.2 m, zone high, soil II`, then ask for the foundation design or the ETABS/SAFE/AutoCAD export.")
        blank = {"kind": KIND, "label": "3D FRAME ANALYSIS", "status": "MISSING_REQUIRED_INPUT", "missing_inputs": ["frame_model"],
                "message": msg, "warnings": [msg], "export_requested": export_formats, "disclaimer": DISCLAIMER,
                "inputs": {}, "parsed_from_request": [], "defaulted_inputs": [], "lang": i18n.detect_lang(user_request)}
        return _loc(blank)
    else:
        return None
    inp.lang = "fa" if fu.is_finglish(user_request) else i18n.detect_lang(user_request)
    assumed_defaults: list[str] = []
    if manual_inputs is None and fu.is_assume_reply(user_request):
        assumed_defaults = fu.apply_defaults(inp)
    if a_upd:
        inp.assumptions = {**(inp.assumptions or {}), **a_upd}
    for k, v in inp_upd.items():
        setattr(inp, k, v)
        inp.parsed = [*inp.parsed, k]
    changed = set(a_upd) | set(inp_upd)
    inputs = {k: v for k, v in asdict(inp).items() if k not in INTERNAL_FIELDS}
    defaulted = [k for k in inputs if k not in inp.parsed and k not in ("seismic_code", "design_code", "accidental_ecc")]
    common = {
        "kind": KIND, "label": "3D FRAME ANALYSIS", "demo": False,
        "disclaimer": DISCLAIMER_2800 if inp.seismic_code == "IRAN_2800" else DISCLAIMER,
        "solver": "internal_direct_stiffness_3d (app/application/analysis/frame3d_solver.py)",
        "seismic_code": inp.seismic_code, "design_code": inp.design_code,
        "code": _code_label(inp),
        "inputs": inputs, "parsed_from_request": list(inp.parsed), "defaulted_inputs": defaulted,
        "export_requested": export_formats, "model_from_project_memory": from_memory,
        "spec": frame3d_spec(inp), "lang": inp.lang,
        "detailing_assumptions": da.describe(inp.assumptions, inp, inp.lang, changed),
        "assumed_defaults": assumed_defaults, "model_changes": model_changes if from_memory else [],
        "followup_note": _followup_note(inp, assumed_defaults, model_changes if from_memory else [], followup_notes),
        "assumptions_changed": sorted(changed), "animate_mode": animate_mode, "show_foundation": bool(show_foundation), "assumptions_command": "show" if show_assumptions and not changed else ("update" if changed else None),
    }
    missing = missing_inputs(inp)
    if missing:
        fa = inp.lang == "fa"
        labels = input_labels(missing, inp.lang)
        d = fu.DEFAULTS
        pend = inp.pending_bays
        if fa:
            msg = ""
            if pend and {"bays_x", "bays_y"} & set(missing):
                msg = f"{pend} دهانه را دریافت کردم ولی جهت آن مشخص نیست — در جهت x است، در جهت y، یا هر دو؟ "
            msg += "لطفاً این مقادیر را برای ادامه وارد کنید: " + "، ".join(labels) + (
                ". مثال: «۳ دهانه ۵ متری در جهت x و ۲ دهانه ۴ متری در جهت y، ۴ طبقه». هر واحدی بنویسید (متر، سانتی‌متر، میلی‌متر، فوت) به متر تبدیل می‌شود؛ بدون واحد = متر.")
            msg += (f" یا بنویسید «**پیش‌فرض‌ها را فرض کن**» تا با مقادیر معمول ({d['storeys']} طبقه، {d['bays_x']}×{d['bays_y']} دهانه "
                    f"{d['bay_x_m']:g} متری، ارتفاع طبقه {d['storey_height_m']:g} متر، آیین‌نامه‌های ایران) ادامه دهم؛ فرض‌ها (از جمله طول دهانه‌ها) را در نتیجه می‌بینید.")
        else:
            msg = ""
            if pend and {"bays_x", "bays_y"} & set(missing):
                msg = f"I understood {pend} bays but not the direction — in X, in Y, or both? "
            msg += ("Please specify: " + ", ".join(labels)
                    + ". Example: `3 bays of 5 m in x and 2 bays of 4 m in y, 4 storeys`. Any length unit (m, cm, mm, ft) is converted to metres; no unit = metres.")
            msg += (f" Or reply **assume defaults** and I will continue with typical values ({d['storeys']} storeys, {d['bays_x']}x{d['bays_y']} bays of "
                    f"{d['bay_x_m']:g} m, storey height {d['storey_height_m']:g} m, Iranian codes); the assumptions (including the bay spans) are listed in the result.")
        have = {k: getattr(inp, k) for k in ("storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m") if k not in missing}
        return _loc({**common, "spec": "", "status": "MISSING_REQUIRED_INPUT", "missing_inputs": missing, "missing_labels": labels,
                     "pending_bays": pend, "given_inputs": have, "message": msg, "warnings": [msg],
                     "can_assume_defaults": True, "defaults_if_assumed": dict(d), "assume_command": {"en": "assume defaults", "fa": "پیش‌فرض‌ها را فرض کن"}})
    limits = []
    if inp.storeys > MAX_STOREYS: limits.append(f"at most {MAX_STOREYS} storeys")
    if max(inp.bays_x, inp.bays_y) > MAX_BAYS: limits.append(f"at most {MAX_BAYS} bays per direction")
    if (inp.bays_x + 1) * (inp.bays_y + 1) * (inp.storeys + 1) > MAX_NODES: limits.append(f"at most {MAX_NODES} nodes")
    if min(inp.storeys, inp.bays_x, inp.bays_y) < 1: limits.append("at least 1 storey and 1 bay per direction")
    if not (MIN_SPAN_M <= inp.bay_x_m <= MAX_SPAN_M and MIN_SPAN_M <= inp.bay_y_m <= MAX_SPAN_M):
        limits.append(f"bay spans between {MIN_SPAN_M:g} and {MAX_SPAN_M:g} m (got X={inp.bay_x_m:g} m, Y={inp.bay_y_m:g} m; check the unit — default unit is metres)")
    if limits:
        msg = "This chat solver currently supports " + ", ".join(limits) + "."
        return _loc({**common, "status": "UNSUPPORTED_SIZE", "message": msg, "warnings": [msg]})
    try:
        raw = run_frame3d(inp)
    except (SpaceFrameSolverError, ValueError) as exc:
        msg = f"3D frame analysis failed: {exc}"
        return _loc({**common, "status": "FAILED", "message": msg, "warnings": [msg]})

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

    pdr = raw["p_delta"]
    if pdr["status"] == "UNSTABLE":
        warnings.append("P-Δ analysis failed: the gravity load exceeds the elastic critical load of the frame (unstable); the first-order results are shown. Enlarge the columns or add stiffness.")
    if "theta_exceeds_limit" in pdr["warnings"]:
        warnings.append(f"Stability index θ = {pdr['theta_governing']:.3f} exceeds the maximum {pdr['theta_limit']:.3f} (θmax = 0.65/Cd ≤ 0.25, Standard 2800 §3-6): the structure is likely unstable; revise the sections or the system.")
    if "theta_above_0_1_not_included" in pdr["warnings"]:
        warnings.append(f"Stability index θ = {pdr['theta_governing']:.3f} exceeds 0.1 but P-Δ was not included; Standard 2800 §3-6 requires it (add 'with P-delta').")

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
        _p_delta_assumption(raw["p_delta"], is2800),
    ]
    if is2800:
        assumptions += [
            f"Standard 2800 (4th ed.) equivalent static with the empirical period {si['T_formula']} = {si['T_empirical_s']:.3f} s (analytical period not used for C)",
            f"Inelastic drift Δm = Cd·Δe/I ({si['drift_factor_label']}), limit {si['drift_limit']*100:g}% ; drift from the design-force analysis (conservative)",
            "Modal analysis on rigid-diaphragm DOFs with storey masses (D+0.2L)/g and uniform-plate polar inertia; mass centre at plan centre",
            "Response spectrum: 2800 design spectrum A·B1·N·I/R, CQC 5% damping, 5% accidental torsion in the dynamic cases",
            "Dynamic results scaled so V_dynamic ≥ 85% (regular) / 90% (irregular) of V_static; scaled response-spectrum member forces are enveloped with the static ones in design",
        ]
    else:
        assumptions.append(f"Drift amplified by 0.7R with R={inp.behaviour_r:g}; the 2.5% value shown is only a reference, not a 2800 check")
    design = design_mabhas9(inp, raw) if inp.design_code == "MABHAS9" else None
    if design and design.get("status") == "NOT_APPLICABLE":
        warnings.append(design["message"])
    if design and design.get("scwb_status") == "FAIL":
        warnings.append("Strong column / weak beam ratio below 1.2 at some joints (see design table): consider larger columns or less beam steel.")
    if design and design.get("special_frame_note"):
        warnings.append(design["special_frame_note"])
    if design and inp.seismic_code != "IRAN_2800":
        warnings.append("Mabhas 9 design uses the user-supplied seismic C; add Standard 2800 parameters for code-based seismic forces.")
    fdn = raw.get("foundation_design") if (inp.foundation or inp.design_code == "MABHAS9") else None
    if fdn:
        assumptions.append(f"Foundation: isolated square footings under every base column; reactions of the analysis combinations; allowable bearing {fdn['qa_kpa']:g} kPa"
                           + (" (assumed)" if fdn["qa_assumed"] else ""))
        if fdn["qa_assumed"]:
            warnings.append("Allowable soil bearing was not given and 150 kPa is assumed (add e.g. 'allowable bearing 200 kPa' / 'تنش مجاز خاک 200 kPa').")
        if fdn["overlap"] and fdn["overlap"]["overlaps"]:
            warnings.append(f"Foundation footings overlap: {fdn['overlap']['recommendation']}")
    if inp.design_code == "NONE":
        assumptions.append("No member design / code compliance checks requested (add 'design per Mabhas 9')")
    fields = [
        {"label": "Model", "value": f"{inp.storeys} storeys, {inp.bays_x}×{inp.bays_y} bays ({inp.bay_x_m:g}×{inp.bay_y_m:g} m), h={inp.storey_height_m:g} m", "unit": ""},
        {"label": "Elements", "value": f"{raw['model']['columns']} columns, {raw['model']['beams']} beams, {raw['model']['nodes']} nodes", "unit": ""},
        {"label": "Sections", "value": _sections_text(inp), "unit": "cm"},
        {"label": "Seismic weight W", "value": f"{results['seismic_weight_kn']:.1f}", "unit": "kN"},
    ]
    if is2800:
        fields += [
            {"label": "2800 parameters", "value": f"A={si['A']:g} ({si['zone_label']}), soil {si['soil']}, I={si['I']:g}, {si['system_label']} R={si['R']:g}, Cd={si['Cd']:g}", "unit": ""},
            {"label": "T (empirical) / B1·N", "value": f"{si['T_empirical_s']:.3f} s / {si['B1']:.3f}×{si['N']:.3f} = {si['B']:.3f}", "unit": ""},
            {"label": "C = ABI/R (≥ 0.12AI)", "value": f"{si['C']:.4f} (Cmin {si['C_min']:.4f}), k={si['k']:.2f}", "unit": ""},
        ]
    fields.append({"label": "P-Δ / stability index θ", "value": _p_delta_field(raw["p_delta"]), "unit": ""})
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
    if design and design.get("summary"):
        sm = design["summary"]
        fields.append({"label": "Mabhas 9 design", "value": f"{design['status']} — max D/C {sm['max_DC']:.2f}, {sm['groups_failing']}/{sm['groups']} groups failing"
                       + (f", SCWB min {sm['scwb_min_ratio']:.2f}" if sm.get("scwb_min_ratio") is not None else ""), "unit": ""})
    if fdn and fdn.get("rows"):
        fields.append({"label": "Foundation", "value": f"{fdn['status']} — max D/C {fdn['summary']['max_DC']:.2f}, qa {fdn['qa_kpa']:g} kPa"
                       + (" (assumed)" if fdn["qa_assumed"] else ""), "unit": ""})
    fields += [
        {"label": "Beam max M⁻", "value": f"{results['beam_max_M_neg_kn_m']:.1f}", "unit": "kN·m"},
        {"label": "Beam max M⁺", "value": f"{results['beam_max_M_pos_kn_m']:.1f}", "unit": "kN·m"},
        {"label": "Beam max V", "value": f"{results['beam_max_V_kn']:.1f}", "unit": "kN"},
        {"label": "Column max P", "value": f"{results['column_max_P_kn']:.1f}", "unit": "kN"},
    ]
    return _loc({
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
        "p_delta": _p_delta_payload(raw["p_delta"]),
        "rs_design": raw.get("rs_design"),
        "design": design,
        "beam_forces_by_storey": per_storey_beam,
        "column_forces_by_storey": [{"storey": k, "P_kn": _r(max(c["P_kn"] for c in cols if c["storey"] == k)),
                                     "M_kn_m": _r(max(c["M_kn_m"] for c in cols if c["storey"] == k))} for k in range(1, inp.storeys + 1)],
        "base_shear_check": base_shear,
        "gravity_reaction_kn": {k: _r(v) for k, v in raw["gravity_reaction_kn"].items()},
        # member envelopes for a future Mabhas 9 / ACI design module
        "envelopes": {"beams": [{**b, "M_neg_kn_m": _r(b["M_neg_kn_m"]), "M_pos_kn_m": _r(b["M_pos_kn_m"]), "V_kn": _r(b["V_kn"])} for b in beams],
                      "columns": [{k2: v for k2, v in {**c, "P_kn": _r(c["P_kn"]), "M_kn_m": _r(c["M_kn_m"])}.items() if k2 != "records"} for c in cols]},
        "assumptions": assumptions, "warnings": warnings, "fields": fields,
        # ETABS/SAFE/DXF text exports, generated on demand by POST /api/v1/frame3d/export from `inputs`
        "exports": cte.export_descriptors(export_formats),
        "foundation": ({k: v for k, v in fdn.items() if k != "footings"} if fdn else None),
        "viewer": _viewer_payload(raw, inp, design, fdn),
    })


def _p_delta_assumption(pd: dict[str, Any], is2800: bool) -> str:
    st = pd["status"]
    if st == "APPLIED":
        return "P-Δ included: second-order elastic analysis of the lateral cases (K + K_G, member axial forces from 1.2D+1.0L); drifts, reactions and member forces include P-Δ"
    if st == "OFF":
        return "P-Δ not included: switched off by the user (the stability index θ is still reported)"
    if st == "UNSTABLE":
        return "P-Δ not included: the second-order analysis failed (gravity load above the elastic critical load)"
    if st == "NOT_REQUIRED":
        if is2800:
            return "P-Δ not included: stability index θ < 0.1 (Standard 2800 §3-6 allows ignoring it)"
        return "P-Δ not included: the automatic rule applies to Standard 2800 projects only (add 'with P-delta' to include it)"
    return "P-Δ not included: no lateral load case"


def _p_delta_field(pd: dict[str, Any]) -> str:
    if pd["status"] == "NOT_APPLICABLE":
        return "no lateral load case"
    th = pd["theta_max"]
    txt = f"θ max X {th['X']:.3f} / Y {th['Y']:.3f}"
    if pd["applied"]:
        txt += f"; P-Δ included, λcr = {pd['lambda_cr']:.2f}"
    else:
        txt += "; P-Δ not included"
    return txt


def _p_delta_payload(pd: dict[str, Any]) -> dict[str, Any]:
    out = {"mode": pd["mode"], "applied": pd["applied"], "status": pd["status"], "rule": pd["rule"]}
    if "theta" not in pd:
        return out
    out.update({
        "basis": pd["method"],
        "theta": {d: [_r(x, 4) for x in v] for d, v in pd["theta"].items()},
        "theta_max": {d: _r(v, 4) for d, v in pd["theta_max"].items()},
        "theta_limit": _r(pd["theta_limit"], 3), "theta_ignore_below": pd["theta_ignore_below"],
        "required_by_theta": pd["required_by_theta"],
        "storey_Pu_kn": [_r(x) for x in pd["storey_Pu_kn"]],
        "drift_first_order_mm": {d: [_r(x) for x in v] for d, v in pd["drift_first_order_mm"].items()},
        "warnings": pd["warnings"],
    })
    if pd["applied"]:
        out.update({"lambda_cr": _r(pd["lambda_cr"], 3),
                    "drift_second_order_mm": {d: [_r(x) for x in v] for d, v in pd["drift_second_order_mm"].items()},
                    "amplification": {d: [_r(x, 4) for x in v] for d, v in pd["amplification"].items()}})
    return out


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


def _followup_note(inp: "Frame3dInputs", assumed: list[str], changes: list[str], notes: list[str]) -> str:
    fa = inp.lang == "fa"
    parts = []
    if assumed:
        parts.append(("**فرض‌های من (چون مقدار داده نشده بود):** " if fa else "**Assumed (not given):** ") + fu.describe(assumed, inp, fa)
                     + ("." if fa else ". Change any of them in chat, e.g. `storeys 6`, `bay x 6 m`."))
        if fa:
            parts[-1] += " هر کدام را می‌توانید در چت عوض کنید، مثلاً «طبقات را ۶ کن» یا «دهانه x را ۶ متر کن»."
    if changes:
        parts.append(("**تغییرات روی مدل قبلی پروژه:** " if fa else "**Changed on the project's last model:** ") + fu.describe(changes, inp, fa)
                     + (" — مدل دوباره تحلیل شد." if fa else " — model re-analysed."))
    if "us_codes" in notes:
        parts.append("تحلیل قاب در چت فعلاً با آیین‌نامه‌های ایران (۲۸۰۰ و مبحث ۹) انجام می‌شود؛ ACI/ASCE برای این تحلیل هنوز پشتیبانی نمی‌شود."
                     if fa else "Chat frame analysis currently runs with Iranian codes (2800 + Mabhas 9); ACI/ASCE is not supported for it yet.")
    if "units" in notes:
        parts.append("محاسبات این تحلیل با واحد SI (kN، m) است؛ واحد نمایش پروژه را از تنظیمات پروژه عوض کنید."
                     if fa else "This analysis computes in SI (kN, m); change the project display units in the project settings.")
    return "\n\n".join(parts)


def frame3d_markdown(payload: dict[str, Any]) -> str:
    text = _frame3d_markdown_en(payload)
    text = i18n.fa_markdown(text) if payload.get("lang") == "fa" else text
    if payload.get("followup_note"):
        text = payload["followup_note"] + "\n\n" + text
    rows = payload.get("detailing_assumptions") or []
    if rows:
        fa = payload.get("lang") == "fa"
        head = ("### فرض‌های طراحی و آرماتوربندی پروژه" if fa else "### Project design & detailing assumptions")
        hint = ("(* = تغییر در همین پیام؛ برای تغییر بنویسید مثلاً «پوشش ۵۰ میلی‌متر، شاخه ۱۲ متری، قطع آرماتور در ln/4»)" if fa
                else "(* = changed in this message; change with e.g. \"cover 50 mm, 12 m stock bars, cut-off at ln/4\")")
        block = "\n".join([head, *[f"- {r}" for r in rows], hint])
        text = block + "\n\n" + text if payload.get("assumptions_command") else text + "\n\n" + block
    return text


def _frame3d_markdown_en(payload: dict[str, Any]) -> str:
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
    dz = payload.get("design")
    if dz and dz.get("beams"):
        sm = dz["summary"]
        lines += ["", f"#### Mabhas 9 RC design ({dz['ductility']} ductility, φc={dz['phi_c']}, φs={dz['phi_s']}) — **{dz['status']}**, max D/C {sm['max_DC']:.2f}", "",
                  "| Beam group | Mu⁻ | Mu⁺ | Vu | Top | Bottom | Stirrups | D/C M | D/C V |", "|---|---|---|---|---|---|---|---|---|"]
        for b in dz["beams"]:
            lines.append(f"| {b['group']} | {b['Mu_neg_kn_m']} | {b['Mu_pos_kn_m']} | {b['Vu_kn']} | {b['top_bars']} | {b['bottom_bars']} | {b['stirrups']} | {b['DC_flexure']} | {b['DC_shear']} |")
        lines += ["", "| Column group | Pu | Mu,y | Mu,z | Bars | ρ % | Ties | D/C |", "|---|---|---|---|---|---|---|---|"]
        for c in dz["columns"]:
            lines.append(f"| {c['group']} | {c['Pu_kn']} | {c['Mu_y_kn_m']} | {c['Mu_z_kn_m']} | {c['bars']} | {c['rho_pct']} | {c['ties']} | {c['DC']} |")
        if dz["scwb"]:
            lines += ["", f"Strong column / weak beam — {dz['scwb_note']}: " + "; ".join(
                f"level {j['level']}: min {j['min_ratio']} ({j['status']})" for j in dz["scwb"])]
        lines += ["", "Implemented clauses: " + "; ".join(dz["clauses_implemented"]),
                  "Simplified / not checked: " + "; ".join(dz["clauses_simplified"]), ""]
    fd = payload.get("foundation")
    if fd and fd.get("rows"):
        lines += ["", f"#### Foundation design (isolated footings) — **{fd['status']}**, max D/C {fd['summary']['max_DC']:.2f}, "
                  f"allowable bearing {fd['qa_kpa']:g} kPa" + (" (assumed)" if fd["qa_assumed"] else "") + f", net {fd['qa_net_kpa']:g} kPa at Df = {fd['Df_m']:g} m", "",
                  "| Footing group | P service | B × B × h (m) | q max (kPa) | D/C bearing | D/C 1-way | D/C punching | Bars | D/C flexure |", "|---|---|---|---|---|---|---|---|---|"]
        for f_ in fd["rows"]:
            if f_["status"] == "PASS":
                lines.append(f"| {f_['group']} | {f_['P_service_kn']} | {f_['B_m']} × {f_['B_m']} × {f_['h_m']} | {f_['q_max_kpa']} | {f_['bearing_dc']} | "
                             f"{f_['DC_oneway']} | {f_['DC_punching']} | {f_['bars']} | {f_['DC_flexure']} |")
            else:
                lines.append(f"| {f_['group']} | — | FAIL: {'; '.join(f_['notes'])} | | | | | | |")
        if fd.get("overlap"):
            lines += ["", f"Footing clear gap min {fd['overlap']['min_gap_m']:g} m, plan coverage {fd['overlap']['coverage_ratio']:.0%}. {fd['overlap']['recommendation']}"]
        lines += ["", "Implemented clauses: " + "; ".join(fd["clauses_implemented"]), "Simplified / not checked: " + "; ".join(fd["clauses_simplified"]), ""]
    lines += [f"- Beam max M⁻ **{r['beam_max_M_neg_kn_m']:.1f} kN·m** ({r['beam_max_M_neg_id']}), M⁺ {r['beam_max_M_pos_kn_m']:.1f} kN·m, V {r['beam_max_V_kn']:.1f} kN",
              f"- Column max axial P **{r['column_max_P_kn']:.1f} kN** ({r['column_max_P_id']})",
              "", "Assumptions:", *[f"- {a}" for a in payload["assumptions"]]]
    if payload.get("exports"):
        req = [e for e in payload["exports"] if e["requested"]] or payload["exports"]
        lines += ["", ("**Exports ready** (download from the result card): " if payload.get("export_requested") else "Exports available on the result card: ")
                  + ", ".join(f"{e['label']} `{e['filename']}`" for e in req)]
        if payload.get("model_from_project_memory"):
            lines.append("Model re-analysed from the last 3D frame stored in this project.")
        for e in req:
            if e["format"] in ("e2k", "f2k", "s2k") and (e["requested"] or not payload.get("export_requested")):
                lines += [f"- {e['filename']}: " + " ".join(e["notes"])]
    if payload["warnings"]:
        lines += ["", "Warnings:", *[f"- {w}" for w in payload["warnings"]]]
    lines += ["", f"*{payload['disclaimer']}*"]
    return "\n".join(lines)


def frame3d_memory_summary(payload: dict[str, Any]) -> str:
    r = payload.get("results") or {}; ms = payload.get("model_summary") or {}
    spec = (payload.get("spec") or "") + "\n"
    return spec + (f"3D frame analysis: {ms.get('storeys')} storeys, {ms.get('bays_x')}x{ms.get('bays_y')} bays; "
            f"max drift 0.7R {r.get('max_drift_amplified_pct')}% (storey {r.get('max_drift_storey')}), "
            f"beam M- {r.get('beam_max_M_neg_kn_m')} kN·m, column P {r.get('column_max_P_kn')} kN. "
            f"Seismic: {payload.get('seismic_code')}; design: {payload.get('design_code')}.")


def frame_limit_message(inp: "Frame3dInputs") -> str:
    """Name each value that exceeds which solver limit (English / Persian)."""
    en: list[str] = []
    fa: list[str] = []
    for key, v, lo, hi in (("storeys", inp.storeys, 1, MAX_STOREYS), ("bays_x", inp.bays_x, 1, MAX_BAYS),
                           ("bays_y", inp.bays_y, 1, MAX_BAYS)):
        if v is not None and (v < lo or v > hi):
            en.append(f"{input_labels([key], 'en')} = {v} (allowed {lo}–{hi})")
            fa.append(f"{input_labels([key], 'fa')} = {v} (مجاز {lo} تا {hi})")
    nodes = (inp.bays_x + 1) * (inp.bays_y + 1) * (inp.storeys + 1)
    if not en and nodes > MAX_NODES:
        en.append(f"nodes (bays_x+1)×(bays_y+1)×(storeys+1) = {nodes} (max {MAX_NODES})")
        fa.append(f"تعداد گره‌ها = {nodes} (حداکثر {MAX_NODES})")
    return ("Model size outside the solver limits: " + "; ".join(en)
            + " / ابعاد مدل خارج از محدوده حل‌کننده است: " + "؛ ".join(fa))


def run_frame3d_for_export(inputs: dict[str, Any]) -> tuple["Frame3dInputs", dict[str, Any], dict[str, Any] | None]:
    """Re-run the (deterministic) analysis for an export request coming from the result card."""
    inp = inputs_from_dict(inputs)
    if "_p" not in inputs and "parsed_from_request" not in inputs:
        inp.parsed = [k for k, v in inputs.items() if v is not None and not str(k).startswith("_")]  # a stored run's inputs are all given
    miss = missing_inputs(inp)
    if miss:
        raise ValueError("The model is incomplete — not set: " + ", ".join(input_labels(miss, "en"))
                         + ". / اطلاعات مدل کامل نیست؛ وارد نشده: " + "، ".join(input_labels(miss, "fa")))
    if (inp.storeys > MAX_STOREYS or max(inp.bays_x, inp.bays_y) > MAX_BAYS or min(inp.storeys, inp.bays_x, inp.bays_y) < 1
            or (inp.bays_x + 1) * (inp.bays_y + 1) * (inp.storeys + 1) > MAX_NODES):
        raise ValueError(frame_limit_message(inp))
    raw = run_frame3d(inp)
    design = design_mabhas9(inp, raw) if inp.design_code == "MABHAS9" else None
    return inp, raw, design
