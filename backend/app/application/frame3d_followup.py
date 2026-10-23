"""Chat follow-ups for the 3D frame: "assume the rest" replies and edits of the project's last model.

Persian, Finglish (Latin-script Persian) and English. Deterministic (works with AI_PROVIDER=stub).

- ``is_assume_reply``: «فرض کن» / "farz kon" / "assume" / "default" / «خودت» / "whatever" ...
- ``merge_with_pending``: a reply to a MISSING_REQUIRED_INPUT question is merged with the pending frame request
  found in the recent user messages, so the agent sees one complete request.
- ``model_edits``: "storeys ro 6 kon", «دهانه x را ۶ متر کن», "columns 50x50", "dead load 7", "Iranian codes" ...
- ``apply_defaults``: fills storeys / bays with documented defaults and returns what was assumed.
"""

from __future__ import annotations

import re
from typing import Any

_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
_N = r"(\d+(?:\.\d+)?)"
_TO = r"\s*(?:ro|ra|rو|را|رو|=|:|to|be|به|بشه|bashe|beshe)?\s*"

DEFAULTS: dict[str, Any] = {"storeys": 4, "bays_x": 3, "bays_y": 3, "bay_x_m": 5.0, "bay_y_m": 5.0, "storey_height_m": 3.2}

_ASSUME = re.compile(
    r"farz\s*(?:kon|kn|konid|begir|bokon)|فرض\s*(?:کن|کنید|بگیر|بگیرید)|\bassume\b|\bassumed?\s+values\b|\bdefaults?\b|"
    r"pish\s*farz|پیش\s*\u200c?\s*فرض|khod(?:e)?t\s*(?:farz|entekhab|bezar)|خودت|خودتان|har\s*chi|هر\s*چی|هرچی|whatever|"
    r"\byou\s+(?:choose|decide|pick)\b|up\s+to\s+you|\btypical\b|معمول(?:ی)?\s*(?:بگیر|بذار|فرض)|ma'?mooli",
    re.I)
_FRAMEISH = re.compile(r"stor(?:e)?y|stories|floor|bays?|frame|model|tabaghe|dahane|ghab|قاب|طبقه|دهانه|مدل|سازه", re.I)
_EDIT_VERB = re.compile(
    r"(?<![a-z])kon(?:id)?\b|(?<![\u0600-\u06FF])کن(?:ید)?(?![\u0600-\u06FF])|bokon|بکن|bezar|بذار|بگذار|beshe|bashe|بشه|باشه|"
    r"taghir|تغییر|avaz|عوض|change|set|make|increase|decrease|use|switch|update|=|\bto\b", re.I)


def norm(text: str) -> str:
    t = (text or "").translate(_PERSIAN_DIGITS).replace("×", "x").replace("*", "x").replace("\u200c", " ")
    return re.sub(r"(?<=\d)[/،,](?=\d)", ".", t)


def is_finglish(text: str) -> bool:
    return bool(re.search(r"\b(?:kon|ro|farz|tabaghe|dahane|sotoon|tir|bede|begir|bezar|metr|chera|lotfan|avaz|taghir)\b", text or "", re.I))


def is_assume_reply(text: str) -> bool:
    return bool(_ASSUME.search(norm(text)))


def _last(pattern: str, t: str):
    found = list(re.finditer(pattern, t, re.I))
    return found[-1] if found else None


def _sec(v1: str, v2: str) -> tuple[float, float]:
    a, b = float(v1), float(v2)
    scale = 0.01 if max(a, b) >= 5 else 1.0  # 50x50 -> cm, 0.5x0.5 -> m
    return round(a * scale, 4), round(b * scale, 4)


def model_edits(text: str) -> dict[str, Any]:
    """Explicit model changes written in Persian / Finglish / English (last mention wins)."""
    t = norm(text).lower()
    e: dict[str, Any] = {}
    # --- storey count
    m = _last(rf"(?:no\.?\s*of\s*)?(?:storeys?|stories|stor(?:e)?y\s*count|floors?|tabaghe?(?:\s*ha|at)?|t[a]?bagh[ae]t|تعداد\s*طبقات|طبقات|طبقه(?:\s*ها)?){_TO}(\d{{1,2}})(?!\s*(?:m\b|metr|متر|\.\d))", t) \
        or _last(r"(\d{1,2})\s*-?\s*(?:tabaghe|طبقه|storeys?|stories|floors?)", t)
    if m:
        e["storeys"] = int(m.group(1))
    # --- bay count / span per direction
    dir_word = r"(?:bays?\s*_?\s*(?:in\s*|along\s*)?|spans?\s*(?:in\s*)?|dahane(?:\s*ha)?\s*(?:ye\s*)?(?:dar\s*)?(?:jahat(?:e)?\s*|rastaye\s*)?|(?:تعداد\s*)?دهانه(?:\s*ها)?(?:\s*ی|\s*های)?\s*(?:در\s*)?(?:جهت\s*|راستای\s*)?)"
    for d in ("x", "y"):
        for m in re.finditer(rf"{dir_word}{d}\b{_TO}{_N}\s*(m\b|metr|meter|متر|متری)?", t, re.I):
            if m.group(2):
                e[f"bay_{d}_m"] = float(m.group(1))
            else:
                e[f"bays_{d}"] = int(float(m.group(1)))
        m = _last(rf"(?:bay|span|dahane|دهانه)\s*(?:width|length|tool|طول)?\s*(?:in\s*)?{d}\b{_TO}{_N}\s*(?:m\b|metr|meter|متر)", t)
        if m:
            e[f"bay_{d}_m"] = float(m.group(1))
    m = _last(rf"(?:bays?|spans?|dahane(?:\s*ha)?|دهانه(?:\s*ها)?)\s*(?:width|length|tool|طول)?{_TO}{_N}\s*(?:m\b|metr|meter|متر)", t)
    if m and not ({"bay_x_m", "bay_y_m"} & set(e)) and not re.search(r"(?:bays?|dahane|دهانه)[^\d]{0,25}[xy]\b", t):
        e["bay_x_m"] = e["bay_y_m"] = float(m.group(1))
    m = _last(r"(\d)\s*x\s*(\d)\s*(?:bays?|dahane|دهانه)", t) or _last(rf"(?:bays?|dahane(?:\s*ha)?|دهانه(?:\s*ها)?){_TO}(\d)\s*x\s*(\d)(?!\s*(?:m\b|متر|metr))", t)
    if m:
        e["bays_x"], e["bays_y"] = int(m.group(1)), int(m.group(2))
    # --- storey height
    m = _last(rf"(?:stor(?:e)?y\s*height|floor\s*height|height\s*of\s*(?:each\s*)?(?:stor(?:e)?y|floor)|ertefa(?:'|e)?\s*(?:e\s*)?(?:tabaghe?(?:\s*ha|at)?)?|ارتفاع(?:\s*هر)?(?:\s*طبقه(?:\s*ها)?|\s*طبقات)?){_TO}{_N}", t)
    if m and 1.5 <= float(m.group(1)) <= 8:
        e["storey_height_m"] = float(m.group(1))
    # --- sections
    for key, words in (("column", r"columns?|sotoon(?:\s*ha)?|soton(?:\s*ha)?|ستون(?:\s*ها)?"), ("beam", r"beams?|tir(?:\s*ha)?|تیر(?:\s*ها)?")):
        m = _last(rf"(?<![a-z\u0600-\u06FF])(?:{words})(?:\s*(?:section|size|ابعاد|maghta|مقطع))?{_TO}{_N}\s*x\s*{_N}", t)
        if m:
            e[f"{key}_b_m"], e[f"{key}_h_m"] = _sec(m.group(1), m.group(2))
    m = _last(rf"(?:slab|dal|دال)\s*(?:thickness|zekhamat|ضخامت)?{_TO}{_N}\s*(?:cm|سانت)?", t)
    if m and 5 <= float(m.group(1)) <= 40:
        e["slab_t_m"] = float(m.group(1)) / 100
    # --- loads / materials
    for key, words, lo, hi in (
        ("dead_kn_m2", r"dead(?:\s*load)?|bar(?:e)?\s*mord(?:e|eh)|بار\s*مرده", 0.5, 30),
        ("live_kn_m2", r"(?<!roof )live(?:\s*load)?|bar(?:e)?\s*zend(?:e|eh)|بار\s*زنده", 0.5, 20),
        ("wall_kn_m", r"wall\s*load|bar(?:e)?\s*divar|بار\s*دیوار", 0, 40),
        ("fc_mpa", r"f'?\s*c|مقاومت\s*بتن|bot[o]?n", 15, 80),
        ("fy_mpa", r"\bfy\b|مقاومت\s*(?:میلگرد|فولاد)", 240, 600),
    ):
        m = _last(rf"(?:{words}){_TO}{_N}", t)
        if m and lo <= float(m.group(1)) <= hi:
            e[key] = float(m.group(1))
    # --- codes
    if re.search(r"iran(?:ian)?\s*codes?|آیین\s*نامه\s*(?:های\s*)?ایران|ayin\s*name\s*(?:ye\s*)?iran|mabhas|مبحث|\b2800\b", t):
        e["seismic_code"] = "IRAN_2800"; e["design_code"] = "MABHAS9"
    elif re.search(r"\baci\b|\basce\b|\bus\s*codes?\b|american\s*codes?|آمریکا", t):
        e["_unsupported"] = "us_codes"
    if re.search(r"\b(?:units?|vahed)\b|واحد", t):
        e["_units"] = "imperial" if re.search(r"imperial|kip|\bft\b|feet|foot|inch|اینچ|فوت|us customary", t) else "si"
    return e


GEOMETRY_KEYS = ("storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m", "storey_height_m")


def is_geometry_edit(text: str) -> bool:
    return bool(set(model_edits(text)) & set(GEOMETRY_KEYS)) and bool(_EDIT_VERB.search(norm(text)))


def is_model_edit(text: str) -> bool:
    e = {k: v for k, v in model_edits(text).items() if not k.startswith("_")}
    return bool(e) and bool(_EDIT_VERB.search(norm(text)))


def is_frame_followup(text: str) -> bool:
    """Routing hint: an 'assume' reply about the frame or an explicit edit of the frame model."""
    return (is_assume_reply(text) and bool(_FRAMEISH.search(norm(text)))) or is_model_edit(text)


def is_strong_frame_followup(text: str) -> bool:
    """Wins over other agents' keywords: an 'assume' reply about the frame or a storey/bay/height edit."""
    if len(norm(text)) > 80:  # full new requests keep the normal keyword routing
        return False
    return (is_assume_reply(text) and bool(_FRAMEISH.search(norm(text)))) or is_geometry_edit(text)


def merge_with_pending(text: str, previous_user_texts: list[str]) -> str:
    """Reply to a missing-parameters question -> "<pending request>\\n<reply>". `previous_user_texts` newest first."""
    from app.application import frame3d_chat_analysis as f3

    if f3.is_frame3d_request(text) and not f3.missing_inputs(f3.parse_frame3d_request(text)):
        return text
    if not (is_assume_reply(text) or model_edits(text) or re.search(r"\d", norm(text))):
        return text
    for prev in (previous_user_texts or [])[:4]:
        if not prev or prev.strip() == (text or "").strip():
            continue
        if f3.is_frame3d_request(prev) or (is_assume_reply(text) and re.search(r"\bframe\b|قاب|ghab", norm(prev), re.I)):
            inp = f3.parse_frame3d_request(prev)
            if f3.missing_inputs(inp):
                return f"{prev} ؛ {text}"
            return text  # last frame was complete: the reply is an edit of that model
    return text


def apply_edits(inp: Any, edits: dict[str, Any]) -> list[str]:
    changed = []
    for k, v in edits.items():
        if k.startswith("_") or not hasattr(inp, k):
            continue
        if getattr(inp, k) != v or k not in inp.parsed:
            setattr(inp, k, v)
            changed.append(k)
        if k not in inp.parsed:
            inp.parsed = [*inp.parsed, k]
    return changed


def apply_defaults(inp: Any) -> list[str]:
    """Fill missing / unparsed geometry with DEFAULTS and Iranian codes; returns the assumed keys."""
    assumed = []
    for k, v in DEFAULTS.items():
        if getattr(inp, k) is None or (k not in inp.parsed and k in ("bay_x_m", "bay_y_m", "storey_height_m")):
            setattr(inp, k, v)
            assumed.append(k)
    for key, (b, h) in (("column", (0.50, 0.50)), ("beam", (0.40, 0.50))):  # typical 4-storey RC IMF sizes
        if f"{key}_b_m" not in inp.parsed and f"{key}_h_m" not in inp.parsed:
            setattr(inp, f"{key}_b_m", b); setattr(inp, f"{key}_h_m", h)
            assumed += [f"{key}_b_m", f"{key}_h_m"]
    if inp.seismic_code != "IRAN_2800" and "seismic_c" not in inp.parsed:
        inp.seismic_code = "IRAN_2800"; assumed.append("seismic_code")
    if inp.design_code != "MABHAS9":
        inp.design_code = "MABHAS9"; assumed.append("design_code")
    return assumed


_LABELS = {
    "storeys": ("number of storeys", "تعداد طبقات", "{}"), "bays_x": ("bays in X", "تعداد دهانه در جهت x", "{}"),
    "bays_y": ("bays in Y", "تعداد دهانه در جهت y", "{}"), "bay_x_m": ("bay length X", "طول دهانه x", "{} m"),
    "bay_y_m": ("bay length Y", "طول دهانه y", "{} m"), "storey_height_m": ("storey height", "ارتفاع طبقه", "{} m"),
    "column_b_m": ("column b", "عرض ستون", "{} m"), "column_h_m": ("column h", "عمق ستون", "{} m"),
    "beam_b_m": ("beam b", "عرض تیر", "{} m"), "beam_h_m": ("beam h", "عمق تیر", "{} m"),
    "slab_t_m": ("slab thickness", "ضخامت دال", "{} m"), "dead_kn_m2": ("dead load", "بار مرده", "{} kN/m²"),
    "live_kn_m2": ("live load", "بار زنده", "{} kN/m²"), "wall_kn_m": ("wall load", "بار دیوار", "{} kN/m"),
    "fc_mpa": ("f'c", "f'c", "{} MPa"), "fy_mpa": ("fy", "fy", "{} MPa"),
    "seismic_code": ("seismic code", "آیین‌نامه زلزله", "{}"), "design_code": ("design code", "آیین‌نامه طراحی", "{}"),
    "zone": ("hazard zone", "پهنه خطر", "{}"), "soil": ("soil type", "نوع خاک", "{}"),
}
_CODE_FA = {"IRAN_2800": "استاندارد ۲۸۰۰ (ویرایش ۴)", "MABHAS9": "مبحث ۹", "ASSUMED_C": "ضریب C کاربر", "NONE": "بدون طراحی"}
_CODE_EN = {"IRAN_2800": "Standard 2800 (4th ed.)", "MABHAS9": "Mabhas 9", "ASSUMED_C": "user C", "NONE": "none"}


def describe(keys: list[str], inp: Any, fa: bool) -> str:
    out = []
    for k in keys:
        en, f, fmt = _LABELS.get(k, (k, k, "{}"))
        v = getattr(inp, k, None)
        if k in ("seismic_code", "design_code"):
            v = (_CODE_FA if fa else _CODE_EN).get(v, v)
        elif isinstance(v, float):
            v = f"{v:g}"
        out.append(f"{f if fa else en}: {fmt.format(v)}")
    return "، ".join(out) if fa else ", ".join(out)
