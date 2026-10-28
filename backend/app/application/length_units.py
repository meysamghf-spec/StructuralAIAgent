"""Length units typed by users (chat and forms) -> metres.

One shared helper for every parser. The default unit is the metre: a bare number is metres; any unit the user
writes (m, cm, mm, ft, in, Persian / Arabic words, Persian digits and decimal separators) is converted
automatically. Conversion factors come from ``unit_conversion_service`` so there is a single table.
"""

from __future__ import annotations

import re

from app.application.unit_conversion_service import UnitConversionService
from app.domain.models.units import EngineeringQuantityType

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫٬", "01234567890123456789.,")

# canonical unit -> spellings (lower case, ZWNJ already replaced by a space, no dots)
_SPELLINGS: dict[str, tuple[str, ...]] = {
    "mm": ("mm", "millimeters", "millimeter", "millimetres", "millimetre", "میلی متر", "میلیمتر", "میلی‌متر"),
    "cm": ("cm", "centimeters", "centimeter", "centimetres", "centimetre", "سانتی متر", "سانتیمتر", "سانتی‌متر", "سانت"),
    "ft": ("ft", "feet", "foot", "فوت"),
    "in": ("inches", "inch", "اینچ"),
    "m": ("meters", "meter", "metres", "metre", "متر", "m"),
}
_ALIAS: dict[str, str] = {}
for _canon, _names in _SPELLINGS.items():
    for _n in _names:
        _ALIAS[_n.replace("\u200c", " ")] = _canon

_ALT = "|".join(re.escape(k).replace(r"\ ", r"\s*") for k in sorted(_ALIAS, key=len, reverse=True))
# regex fragment (no capture group inside): a length unit, optionally with the Persian «ی» suffix («متری»)
UNIT_PATTERN = rf"(?:{_ALT})(?:ی)?(?![A-Za-z\u0621-\u064A\u066E-\u06D3])"
NUM_PATTERN = r"\d+(?:\.\d+)?"
LENGTH_RE = re.compile(rf"(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})", re.I)

UNIT_CHOICES = ("m", "cm", "mm", "ft")
_SVC = UnitConversionService()


def normalize_digits(text: str) -> str:
    """Persian / Arabic-Indic digits -> ASCII, Persian decimal separator -> '.', ZWNJ -> space."""
    t = (text or "").translate(PERSIAN_DIGITS).replace("\u200c", " ")
    return re.sub(r"(?<=\d)[/،,](?=\d)", ".", t)


def canonical_unit(unit: str | None) -> str:
    """Spelling -> 'm' | 'cm' | 'mm' | 'ft' | 'in'. Empty / unknown -> 'm' (metres are the default unit)."""
    if not unit:
        return "m"
    u = re.sub(r"\s+", " ", unit.strip().lower().replace("\u200c", " ").replace(".", ""))
    if u.endswith("ی") and u[:-1] in _ALIAS:
        u = u[:-1]
    return _ALIAS.get(u, _ALIAS.get(u.replace(" ", ""), "m"))


def to_metres(value: float, unit: str | None = None) -> float:
    """Convert ``value`` written in ``unit`` (default metres) to metres."""
    canon = canonical_unit(unit)
    if canon == "m":
        return float(value)
    return round(_SVC.convert(float(value), from_unit=canon, to_unit="m", quantity_type=EngineeringQuantityType.LENGTH).value, 6)


def parse_length_m(text: str) -> float | None:
    """'600 cm' -> 6.0, '۶۰۰۰ میلی‌متر' -> 6.0, '5 متری' -> 5.0, '12 ft' -> 3.6576, '5' -> 5.0 (metres), else None."""
    t = normalize_digits(text).strip()
    m = LENGTH_RE.search(t)
    if m:
        return to_metres(float(m.group("num")), m.group("unit"))
    m = re.fullmatch(rf"\s*({NUM_PATTERN})\s*", t)
    return float(m.group(1)) if m else None
