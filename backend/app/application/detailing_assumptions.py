"""Per-project design / rebar-detailing assumptions, changeable from chat (Persian or English).

Stored inside the project's frame spec (Frame3dInputs.assumptions, persisted in project memory) and applied on the
next run by the Mabhas 9 design (cover, stirrup Φ, allowed bar diameters, ductility, SCWB) and the rebar DXF
(stock length, cut-off rule, splice class, ld/hook factors, ψt, cross-ties, stirrup hook length).
Example: «پوشش ۵۰ میلی‌متر، شاخه ۱۲ متری، قطع آرماتور در ln/4».
"""

from __future__ import annotations

import re
import threading
from contextlib import contextmanager
from typing import Any, Iterator

DEFAULTS: dict[str, Any] = {
    "cover_mm": 40,
    "stock_length_m": 12,
    "cutoff": "ln/3",          # ln/3 | ln/4 | moment
    "splice_class": "B",       # A (1.0 ld) | B (1.3 ld)
    "ld_factor": 1.0,
    "hook_factor": 1.0,
    "psi_t": 1.3,
    "cross_ties": "every",     # every | alternate
    "stirrup_hook_db": 10,
    "stirrup_db": 10,
    "beam_bars": [14, 16, 18, 20, 22, 25],
    "column_bars": [16, 18, 20, 22, 25, 28],
    "ductility": None,         # None = from the lateral system; ordinary | intermediate | special
    "scwb": "auto",            # auto (special: mandatory, else reported) | check | skip
}
DUCTILITY_SYSTEM = {"ordinary": "RC_OMF", "intermediate": "RC_IMF", "special": "RC_SMF"}
_PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")

LABELS = {
    "cover_mm": ("Clear cover", "پوشش بتن", "mm"),
    "stock_length_m": ("Stock bar length", "طول شاخه میلگرد", "m"),
    "cutoff": ("Top-bar cut-off", "قطع آرماتور فوقانی", ""),
    "splice_class": ("Lap splice class", "کلاس وصله پوششی", ""),
    "ld_factor": ("ld factor", "ضریب طول مهاری", "×"),
    "hook_factor": ("Hook ldh factor", "ضریب طول قلاب", "×"),
    "psi_t": ("ψt (top bars)", "ψt میلگرد فوقانی", ""),
    "cross_ties": ("Column cross-ties", "سنجاقی ستون", ""),
    "stirrup_hook_db": ("Stirrup hook extension", "طول قلاب خاموت", "db"),
    "stirrup_db": ("Stirrup / tie Φ", "قطر خاموت", "mm"),
    "beam_bars": ("Allowed beam bars Φ", "قطرهای مجاز تیر", "mm"),
    "column_bars": ("Allowed column bars Φ", "قطرهای مجاز ستون", "mm"),
    "ductility": ("Ductility level", "سطح شکل‌پذیری", ""),
    "scwb": ("Strong column / weak beam", "ستون قوی - تیر ضعیف", ""),
    "fy_mpa": ("fy", "fy", "MPa"),
    "fc_mpa": ("f'c", "f'c", "MPa"),
}


def effective(a: dict[str, Any] | None) -> dict[str, Any]:
    return {**DEFAULTS, **(a or {})}


def _n(text: str) -> str:
    return (text or "").translate(_PERSIAN_DIGITS).replace("\u200c", " ").lower()


def _num(s: str) -> float:
    return float(s)


def _diams(s: str) -> list[int]:
    return sorted({int(x) for x in re.findall(r"\d+", s) if 6 <= int(x) <= 40})


def parse_assumptions(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """-> (assumption updates, Frame3dInputs updates such as fy_mpa / fc_mpa / system)."""
    t = _n(text)
    a: dict[str, Any] = {}
    inp: dict[str, Any] = {}
    m = re.search(r"(?:clear )?cover\D{0,12}?(\d+(?:\.\d+)?)\s*(mm|cm)?|پوشش(?: بتن)?\D{0,12}?(\d+(?:\.\d+)?)\s*(میلی|سانت|mm|cm)?", t)
    if m:
        v, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        a["cover_mm"] = _num(v) * (10 if unit in ("cm", "سانت") else 1)
    m = re.search(r"(?:stock|bar) length\D{0,8}(\d+(?:\.\d+)?)|(\d+(?:\.\d+)?)\s*m(?:etre|eter)?\s+(?:stock|bars?\b)|شاخه(?: ی| های)?\s*(\d+(?:\.\d+)?)\s*متر|طول شاخه\D{0,8}(\d+(?:\.\d+)?)", t)
    if m:
        a["stock_length_m"] = _num(next(g for g in m.groups() if g))
    if re.search(r"moment diagram|from (?:the )?moment|نمودار لنگر|از روی لنگر", t):
        a["cutoff"] = "moment"
    else:
        m = re.search(r"l\s*n\s*/\s*([34])", t)
        if m:
            a["cutoff"] = f"ln/{m.group(1)}"
    m = re.search(r"(?:splice|lap|وصله)[^\n.،,]{0,25}?(?:class|کلاس|رده|نوع)\s*(a|b|الف|ب)\b", t)
    if m:
        a["splice_class"] = "A" if m.group(1) in ("a", "الف") else "B"
    m = re.search(r"(?:\bld\b|development)\s*(?:length\s*)?(?:factor|ضریب|x|×)\s*=?\s*(\d+(?:\.\d+)?)|ضریب طول (?:مهاری|گیرایی)\s*=?\s*(\d+(?:\.\d+)?)", t)
    if m:
        a["ld_factor"] = _num(m.group(1) or m.group(2))
    m = re.search(r"hook (?:length )?factor\s*=?\s*(\d+(?:\.\d+)?)|ضریب (?:طول )?قلاب\s*=?\s*(\d+(?:\.\d+)?)", t)
    if m:
        a["hook_factor"] = _num(m.group(1) or m.group(2))
    m = re.search(r"(?:ψ|psi)\s*_?t\s*=?\s*(\d+(?:\.\d+)?)", t)
    if m:
        a["psi_t"] = _num(m.group(1))
    if re.search(r"cross.?ties?[^\n.]{0,25}(?:alternate|every other)|سنجاقی[^\n.]{0,25}یکی در میان", t):
        a["cross_ties"] = "alternate"
    elif re.search(r"cross.?ties?[^\n.]{0,25}(?:every|all) (?:intermediate )?bars?|سنجاقی[^\n.]{0,25}(?:همه|تمام|هر)", t):
        a["cross_ties"] = "every"
    m = re.search(r"(?:stirrup|tie|hoop) hooks?\D{0,15}?(\d+)\s*(?:d\b|db|×?\s*d)|قلاب (?:خاموت|تنگ)\D{0,12}?(\d+)\s*(?:d|db|برابر)", t)
    if m:
        a["stirrup_hook_db"] = int(m.group(1) or m.group(2))
    m = re.search(r"(?:stirrups?|ties|hoops?|خاموت|تنگ)\s*(?:diameter|قطر)?\s*[Φφø]\s*(\d+)\b(?!\s*@)|(?:stirrup|tie|خاموت) diameter\D{0,5}(\d+)|قطر خاموت\D{0,5}(\d+)", t)
    if m:
        a["stirrup_db"] = int(next(g for g in m.groups() if g))
    for key, word in (("beam_bars", r"beams?|تیر"), ("column_bars", r"columns?|ستون")):
        m = re.search(rf"(?:(?:{word})\s*(?:bars?|میلگرد(?:های)?)|(?:bars?|میلگرد(?:های)?)\s*(?:مجاز\s*)?(?:for\s*)?(?:{word}))[^\n.]{{0,20}}?([Φφø]?\s*\d+(?:\s*(?:,|،|و|and|/|-)\s*[Φφø]?\s*\d+)+)", t)
        if m:
            ds = _diams(m.group(1))
            if ds:
                a[key] = ds
    m = re.search(r"\b(ordinary|intermediate|special)\b(?:\s*(?:ductility|moment frame|frame))?|شکل ?پذیری\s*(کم|معمولی|متوسط|زیاد|ویژه)", t)
    if m and (m.group(2) or re.search(r"ductility|moment frame|frame|شکل", t)):
        word = m.group(1) or {"کم": "ordinary", "معمولی": "ordinary", "متوسط": "intermediate", "زیاد": "special", "ویژه": "special"}[m.group(2)]
        a["ductility"] = word
        inp["system"] = DUCTILITY_SYSTEM[word]
    if re.search(r"(?:scwb|strong.?column|ستون قوی)[^\n.]{0,30}(?:skip|off|not applicable|n/?a|غیرفعال|اعمال نشود|نادیده|لازم نیست)", t):
        a["scwb"] = "skip"
    elif re.search(r"(?:scwb|strong.?column|ستون قوی)[^\n.]{0,30}(?:check|on|apply|mandatory|اعمال شود|فعال|کنترل)", t):
        a["scwb"] = "check"
    m = re.search(r"\bfy\s*=?\s*(\d{3})", t)
    if m:
        inp["fy_mpa"] = _num(m.group(1))
    m = re.search(r"\bf'?c\s*=?\s*(\d{2})\b|مقاومت (?:فشاری )?بتن\D{0,6}(\d{2})", t)
    if m:
        inp["fc_mpa"] = _num(m.group(1) or m.group(2))
    return a, inp


_SHOW = r"show (?:the )?(?:current )?assumptions|list (?:the )?assumptions|current assumptions|what are the assumptions|فرض.?ها(?:ی فعلی)?(?: را)? نشان|فرضیات(?: را)? نشان|فرض.?های فعلی|نمایش فرض"


def is_show_assumptions(text: str) -> bool:
    return bool(re.search(_SHOW, _n(text)))


def is_assumption_update(text: str) -> bool:
    a, inp = parse_assumptions(text)
    return bool(a or inp)


def _fmt(key: str, v: Any) -> str:
    if isinstance(v, list):
        return ", ".join(f"Φ{x}" for x in v)
    if key == "splice_class":
        return f"{v} ({'1.0' if v == 'A' else '1.3'}·ld)"
    if key == "ductility" and v is None:
        return "from lateral system"
    if isinstance(v, float) and v.is_integer():
        return f"{int(v)}"
    return f"{v}"


def describe(a: dict[str, Any] | None, inp: Any = None, lang: str = "en", changed: set[str] | None = None) -> list[str]:
    e = effective(a)
    rows = []
    if inp is not None:
        e = {**e, "fy_mpa": getattr(inp, "fy_mpa", None), "fc_mpa": getattr(inp, "fc_mpa", None)}
        if e["ductility"] is None:
            e["ductility"] = {v: k for k, v in DUCTILITY_SYSTEM.items()}.get(getattr(inp, "system", ""), None)
    for key in LABELS:
        if key not in e:
            continue
        en, fa, unit = LABELS[key]
        mark = " *" if changed and key in changed else ""
        rows.append(f"{fa if lang == 'fa' else en}: {_fmt(key, e[key])}{(' ' + unit) if unit and unit != '×' else ''}{mark}")
    return rows


_LOCK = threading.Lock()


@contextmanager
def design_overrides(m9: Any, a: dict[str, Any] | None) -> Iterator[None]:
    """Temporarily apply cover / stirrup Φ / allowed diameters to the Mabhas 9 design module (serialised)."""
    e = effective(a)
    with _LOCK:
        saved = (m9.COVER, m9.STIRRUP_DB, m9.BEAM_BARS, m9.COLUMN_BARS)
        m9.COVER, m9.STIRRUP_DB = float(e["cover_mm"]), float(e["stirrup_db"])
        m9.BEAM_BARS, m9.COLUMN_BARS = tuple(e["beam_bars"]), tuple(e["column_bars"])
        try:
            yield
        finally:
            m9.COVER, m9.STIRRUP_DB, m9.BEAM_BARS, m9.COLUMN_BARS = saved
