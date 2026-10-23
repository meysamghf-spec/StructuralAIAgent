"""Building program for the architecture phase + bilingual (fa/en) prompt parser and architect-style interview."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from .rules import ArchRules

_DIG = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
_WORDS = {"یک": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "هفت": 7, "هشت": 8, "نه": 9, "ده": 10,
          "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8}
_NUM = r"(\d+(?:\.\d+)?)"


def normalize(text: str) -> str:
    t = (text or "").translate(_DIG).replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    for w, n in sorted(_WORDS.items(), key=lambda kv: -len(kv[0])):
        t = re.sub(rf"(?<![\w]){w}(?=\s*(?:طبقه|واحد|خوابه|خواب|اتاق|-?\s*stor|\s*floor|\s*unit|\s*bed))", str(n), t, flags=re.I)
    return t


@dataclass
class BuildingProgram:
    plot_width_m: float = 10.0          # along the street (x)
    plot_depth_m: float = 25.0          # perpendicular to the street (y)
    street_side: str = "south"          # street is south of the plot ("north-side plot" / ملک شمالی)
    street_width_m: float = 10.0
    floors: int = 4                     # storeys above ground incl. ground (pilotis) floor
    units_per_floor: int = 1
    bedrooms: int = 2
    parking: bool = True
    elevator: bool | None = None        # None -> from rules (elevator_from_floors)
    structure: str = "concrete"         # concrete | steel
    city: str = "Arak"
    project_name: str = "Residential building"
    rules: dict[str, Any] = field(default_factory=dict)

    def rules_obj(self) -> ArchRules:
        return ArchRules.from_overrides(self.rules)

    def has_elevator(self) -> bool:
        return self.elevator if self.elevator is not None else self.floors >= self.rules_obj().elevator_from_floors

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "BuildingProgram":
        ok = {k: v for k, v in (d or {}).items() if k in cls.__dataclass_fields__}
        return cls(**ok)


# questions asked only when the info is missing (fa, en, default description)
QUESTIONS: dict[str, tuple[str, str]] = {
    "plot": ("ابعاد زمین چقدر است؟ (عرض بر گذر × عمق، مثلاً ۱۰×۲۵)", "Plot size? (width on street × depth, e.g. 10x25)"),
    "street_side": ("زمین شمالی است یا جنوبی؟ (گذر در کدام سمت است)", "Is the street on the south (north-side plot) or north?"),
    "street_width": ("عرض گذر چند متر است؟", "Street width (m)?"),
    "floors": ("چند طبقه (با همکف)؟", "How many storeys (incl. ground)?"),
    "units": ("هر طبقه چند واحد؟", "Units per floor?"),
    "bedrooms": ("هر واحد چند خوابه؟", "Bedrooms per unit?"),
    "parking": ("پارکینگ در همکف (پیلوت) لازم است؟", "Parking on the ground floor (pilotis)?"),
    "elevator": ("آسانسور داشته باشد؟", "Elevator?"),
    "structure": ("اسکلت فلزی یا بتنی؟", "Steel or concrete frame?"),
    "city": ("در کدام شهر؟ (برای ضوابط شهرداری)", "Which city (municipal rules)?"),
}


def parse(text: str, base: BuildingProgram | None = None) -> tuple[BuildingProgram, set[str]]:
    """Return (program, keys given in this text). Unknown fields keep `base` (or defaults)."""
    p = BuildingProgram(**(base.to_dict() if base else {}))
    t = normalize(text)
    tl = t.lower()
    got: set[str] = set()
    m = re.search(rf"{_NUM}\s*(?:m|متر|متری)?\s*(?:[x×*]|در|by)\s*{_NUM}", tl)
    if m:
        a, b = float(m.group(1)), float(m.group(2))
        if 4 <= a <= 200 and 4 <= b <= 300:
            p.plot_width_m, p.plot_depth_m = (min(a, b), max(a, b)) if not re.search(r"عرض|width", tl) else (a, b)
            got.add("plot")
    if re.search(r"شمالی|north[- ]?side|north[- ]facing plot|street (?:on|to) the south", tl):
        p.street_side = "south"; got.add("street_side")
    elif re.search(r"جنوبی|south[- ]?side|street (?:on|to) the north", tl):
        p.street_side = "north"; got.add("street_side")
    m = re.search(rf"(?:گذر|کوچه|خیابان|معبر|street|road|alley)\s*(?:به\s*عرض\s*|width\s*|of\s*)?{_NUM}\s*(?:m|متر|متری|meter)", tl) or \
        re.search(rf"{_NUM}\s*(?:m|متر|متری|meter)\s*(?:گذر|کوچه|خیابان|street|road|wide street)", tl)
    if m:
        p.street_width_m = float(m.group(1)); got.add("street_width")
    m = re.search(r"(\d+)\s*(?:طبقه|-?\s*stor(?:e)?y|-?\s*stories|-?\s*floors?|-?\s*level)", tl)
    if m:
        p.floors = max(1, min(20, int(m.group(1)))); got.add("floors")
    m = re.search(r"(\d+)\s*(?:واحد|units?)", tl)
    if m:
        p.units_per_floor = max(1, min(4, int(m.group(1)))); got.add("units")
    elif re.search(r"تک\s*واحد|single[- ]unit", tl):
        p.units_per_floor = 1; got.add("units")
    m = re.search(r"(\d+)\s*(?:خوابه|خواب|اتاق\s*خواب|-?\s*bed(?:room)?s?)", tl)
    if m:
        p.bedrooms = max(1, min(5, int(m.group(1)))); got.add("bedrooms")
    if re.search(r"بدون\s*پارکینگ|no parking|without parking", tl):
        p.parking = False; got.add("parking")
    elif re.search(r"پارکینگ|parking|پیلوت|pilotis", tl):
        p.parking = True; got.add("parking")
    if re.search(r"بدون\s*آسانسور|no (?:elevator|lift)|without (?:elevator|lift)", tl):
        p.elevator = False; got.add("elevator")
    elif re.search(r"آسانسور|elevator|lift", tl):
        p.elevator = True; got.add("elevator")
    if re.search(r"فلزی|steel", tl):
        p.structure = "steel"; got.add("structure")
    elif re.search(r"بتنی|بتن|concrete|\brc\b", tl):
        p.structure = "concrete"; got.add("structure")
    m = re.search(r"(?:در|شهر|in|city)\s+(اراک|تهران|اصفهان|مشهد|شیراز|تبریز|کرج|قم|Arak|Tehran|Isfahan|Mashhad|Shiraz|Tabriz|Karaj|Qom)", t, re.I)
    if m:
        p.city = m.group(1); got.add("city")
    m = re.search(r"سطح\s*اشغال\s*(\d+)|occupancy\s*(\d+)", tl)
    if m:
        p.rules = {**p.rules, "occupancy_pct": float(m.group(1) or m.group(2))}
    return p, got


def missing(got: set[str]) -> list[str]:
    return [k for k in QUESTIONS if k not in got]


def validate(p: BuildingProgram) -> list[str]:
    """Rule checks -> human warnings (the generator still produces a set)."""
    r = p.rules_obj()
    w = []
    if p.plot_width_m < 6:
        w.append("Plot narrower than 6 m: the layout is tight; check the detailed plan.")
    if p.parking and p.plot_width_m < r.stall_w_m * 2 + 0.5:
        w.append("Plot too narrow for two stalls side by side; parking is laid out in tandem.")
    if p.floors >= 6 and not p.has_elevator():
        w.append("6+ storeys without an elevator violates usual rules.")
    return w
