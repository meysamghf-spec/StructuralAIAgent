"""Assumption keys of the RC frame modules (Mabhas 9 design, rebar detailing, Standard 2800), registered in the
common assumptions registry, plus the thin helpers the 3D-frame module uses. Parsing is the shared registry parser.
Example prompt: «پوشش ۵۰ میلی‌متر، شاخه ۱۲ متری، قطع آرماتور در ln/4».
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Any, Iterator

from app.application import assumptions_registry as reg
from app.application.assumptions_registry import AssumptionSpec as S

DUCTILITY_SYSTEM = {"ordinary": "RC_OMF", "intermediate": "RC_IMF", "special": "RC_SMF"}

reg.register_module("rebar_detailing", [
    S("cover_mm", "number", 40, "Clear cover", "پوشش بتن", "mm", (15, 100),
      (r"(?:clear )?cover", r"پوشش(?: بتن)?", r"کاور"), unit_scale={"cm": 10, "سانت": 10, "میلی": 1}),
    S("stock_length_m", "number", 12, "Stock bar length", "طول شاخه میلگرد", "m", (6, 18),
      (r"(?:stock|bar) length", r"stock bars?", r"شاخه(?: ی| های)?", r"طول شاخه"), value_before_alias=True),
    S("cutoff", "choice", "ln/3", "Top-bar cut-off", "قطع آرماتور فوقانی", "", None, (r"cut.?off", r"قطع"),
      {"moment": r"moment diagram|from (?:the )?moment|نمودار لنگر|از روی لنگر", "ln/4": r"l\s*n\s*/\s*4", "ln/3": r"l\s*n\s*/\s*3"},
      standalone_choices=True),
    S("splice_class", "choice", "B", "Lap splice class", "کلاس وصله پوششی", "", None, (r"splice", r"\blap\b", r"وصله"),
      {"A": r"(?:class|کلاس|رده|نوع)\s*(?:a|الف)\b", "B": r"(?:class|کلاس|رده|نوع)\s*(?:b|ب)\b"}),
    S("ld_factor", "number", 1.0, "ld factor", "ضریب طول مهاری", "×", (0.5, 3),
      (r"\bld\s*(?:factor|x)", r"development (?:length )?factor", r"ضریب طول (?:مهاری|گیرایی)")),
    S("hook_factor", "number", 1.0, "Hook ldh factor", "ضریب طول قلاب", "×", (0.5, 3), (r"hook (?:length )?factor", r"ضریب (?:طول )?قلاب")),
    S("psi_t", "number", 1.3, "ψt (top bars)", "ψt میلگرد فوقانی", "", (1.0, 1.5), (r"(?:ψ|psi)\s*_?t",)),
    S("cross_ties", "choice", "every", "Column cross-ties", "سنجاقی ستون", "", None, (r"cross.?ties?", r"سنجاقی"),
      {"alternate": r"alternate|every other|یکی در میان", "every": r"every|all|همه|تمام|هر"}),
    S("stirrup_hook_db", "int", 10, "Stirrup hook extension", "طول قلاب خاموت", "db", (6, 16),
      (r"(?:stirrup|tie|hoop) hooks?", r"قلاب (?:خاموت|تنگ)")),
])
reg.register_module("mabhas9", [
    S("stirrup_db", "int", 10, "Stirrup / tie Φ", "قطر خاموت", "mm", (8, 16),
      (r"(?:stirrups?|ties|hoops?)\s*(?:diameter)?\s*(?=[φΦø])", r"stirrup diameter", r"(?:خاموت|تنگ)\s*(?=[φΦø])", r"قطر خاموت")),
    S("beam_bars", "list", [14, 16, 18, 20, 22, 25], "Allowed beam bars Φ", "قطرهای مجاز تیر", "mm", (10, 32),
      (r"beams? bars?", r"bars? for beams?", r"میلگرد(?:های)? (?:مجاز )?تیر")),
    S("column_bars", "list", [16, 18, 20, 22, 25, 28], "Allowed column bars Φ", "قطرهای مجاز ستون", "mm", (12, 36),
      (r"columns? bars?", r"bars? for columns?", r"میلگرد(?:های)? (?:مجاز )?ستون")),
    S("ductility", "choice", None, "Ductility level", "سطح شکل‌پذیری", "", None, (r"ductility", r"moment frame", r"شکل ?پذیری"),
      {"special": r"special|زیاد|ویژه", "intermediate": r"intermediate|متوسط", "ordinary": r"ordinary|کم|معمولی"},
      side_effects={k: {"system": v} for k, v in DUCTILITY_SYSTEM.items()}),
    S("scwb", "choice", "auto", "Strong column / weak beam", "ستون قوی - تیر ضعیف", "", None, (r"scwb", r"strong.?column", r"ستون قوی"),
      {"skip": r"skip|off|not applicable|n/?a|غیرفعال|اعمال نشود|نادیده|لازم نیست", "check": r"check|\bon\b|apply|mandatory|اعمال شود|فعال|کنترل"}),
    S("fy_mpa", "number", 400, "fy", "fy", "MPa", (240, 600), (r"\bfy",), target="input", field_name="fy_mpa"),
    S("fc_mpa", "number", 30, "f'c", "f'c", "MPa", (15, 70), (r"\bf'?c\b", r"مقاومت (?:فشاری )?بتن"), target="input", field_name="fc_mpa"),
])
reg.register_module("iran2800", [
    S("importance", "number", 1.0, "Importance factor I", "ضریب اهمیت", "", (0.8, 1.4), (r"importance(?: factor)?", r"ضریب اهمیت"),
      target="input", field_name="importance"),
    S("behaviour_r", "number", 5.0, "Behaviour factor R", "ضریب رفتار", "", (1.5, 8), (r"behaviou?r factor", r"\br\s*=", r"ضریب رفتار"),
      target="input", field_name="behaviour_r"),
])
reg.register_module("foundation", [
    S("allowable_bearing_kpa", "number", 150, "Allowable soil bearing", "تنش مجاز خاک", "kPa", (50, 800),
      (r"allowable (?:soil )?bearing", r"bearing capacity", r"تنش مجاز(?: خاک)?", r"ظرفیت باربری"), target="input", field_name="allowable_bearing_kpa"),
])
FRAME_MODULES = ["rebar_detailing", "mabhas9", "iran2800", "foundation"]


def effective(a: dict[str, Any] | None) -> dict[str, Any]:
    return {**reg.defaults(FRAME_MODULES), **(a or {})}


def parse_assumptions(text: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """-> (assumption record updates, Frame3dInputs updates) via the shared registry parser."""
    parsed, _ = reg.parse(text, FRAME_MODULES)
    return reg.split_targets(parsed)


def is_show_assumptions(text: str) -> bool:
    return reg.is_show_command(text)


def is_assumption_update(text: str) -> bool:
    a, inp = parse_assumptions(text)
    return bool(a or inp)


def describe(a: dict[str, Any] | None, inp: Any = None, lang: str = "en", changed: set[str] | None = None) -> list[str]:
    fields = dict(vars(inp)) if inp is not None and hasattr(inp, "__dict__") else {}
    rec = dict(a or {})
    if rec.get("ductility") is None and fields.get("system"):
        rec["ductility"] = {v: k for k, v in DUCTILITY_SYSTEM.items()}.get(fields["system"])
    return reg.describe(FRAME_MODULES, rec, fields, lang, changed)


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
