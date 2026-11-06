"""Shared parser for bay counts and bay spans in chat messages (Persian, Finglish-free, English).

Understands, for both X and Y:
  «۲ دهانه در جهت x»  «تعداد دهانه در جهت x برابر ۲»  «۳ دهانه ۵ متری»  «دو دهنه»  «۶۰۰ سانتی‌متر»
  "2-bay"  "3 bays of 5 m"  "2 bays in x and 1 bay in y"  "bays_x = 2"  "span x 600 cm"  "x=2, y=1"
  short follow-up answers such as «۲ در x و ۱ در y» (merged with the pending request by the caller)

Lengths are converted to metres with ``length_units`` (default unit: metre). A bare count without a direction
("3 bays", «سه دهانه») is *not* guessed: it is reported in ``BayParse.ambiguous`` so the caller can ask which direction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.application.length_units import NUM_PATTERN, UNIT_PATTERN, normalize_digits, to_metres

FA_NUM_WORDS = {"یک": 1, "یه": 1, "دو": 2, "سه": 3, "چهار": 4, "پنج": 5, "شش": 6, "شیش": 6, "هفت": 7, "هشت": 8, "نه": 9,
                "ده": 10, "یازده": 11, "دوازده": 12, "سیزده": 13, "چهارده": 14, "پانزده": 15, "پونزده": 15, "شانزده": 16,
                "هفده": 17, "هجده": 18, "نوزده": 19, "بیست": 20}
EN_NUM_WORDS = {"one": 1, "single": 1, "two": 2, "double": 2, "three": 3, "triple": 3, "four": 4, "five": 5, "six": 6, "seven": 7,
                "eight": 8, "nine": 9, "ten": 10}
_NOUNS_AHEAD = r"(?:دهانه|دهنه|طبقه|متر|سانت|عدد|تا\b|ستون|تیر|bays?|spans?|stor|floors?|in\b|along\b|on\b|در\s*(?:جهت\s*)?[xy]|[xy]\b)"
_FA_WORD_RE = re.compile(r"(?<![\u0600-\u06FF])(" + "|".join(sorted(FA_NUM_WORDS, key=len, reverse=True)) + r")(?=\s*" + _NOUNS_AHEAD + ")")
_EN_WORD_RE = re.compile(r"\b(" + "|".join(EN_NUM_WORDS) + r")(?=[\s-]*(?:bays?|spans?|stor|floors?|in\s+[xy]\b))", re.I)


def normalize(text: str, *, lower: bool = True) -> str:
    """Digits, ZWNJ, Arabic letter variants, «دهنه»→«دهانه», number words → a lower-case string the patterns below expect."""
    t = normalize_digits(text).replace("ي", "ی").replace("ك", "ک").replace("×", "x").replace("*", "x")
    t = re.sub(r"دهنه", "دهانه", t)
    t = _FA_WORD_RE.sub(lambda m: str(FA_NUM_WORDS[m.group(1)]), t)
    t = _EN_WORD_RE.sub(lambda m: str(EN_NUM_WORDS[m.group(1).lower()]), t)
    t = re.sub(r"(?<![\u0600-\u06FF])ایکس(?![\u0600-\u06FF])", "x", t)
    t = re.sub(r"(?<![\u0600-\u06FF])وای(?![\u0600-\u06FF])", "y", t)
    return t.lower() if lower else t


NOUN = r"(?:bays?|spans?|دهانه)"
SUF = r"(?:\s*(?:ها|های|ی|ای))?"
INTRO = r"(?:of|@|at|each|spaced\s+at|به\s*طول|به\s*عرض|هر\s*کدام|هرکدام|به\s*اندازه)"
PREP = r"(?:in|along|on|for|towards?)"
KEY = r"(?:جهت|راستا\s*ی?|امتداد|محور|سمت)"


def _dir(name: str, *, bare: bool = False) -> str:
    core = (rf"(?:{PREP}\s+(?:the\s+)?(?:global\s+)?|در\s+(?:{KEY}\s*)?|{KEY}\s*)(?P<{name}>[xy])(?![a-z0-9_])(?:[\s-]*(?:direction|dir|axis))?"
            rf"|(?<![a-z0-9_])(?P<{name}b>[xy])[\s-]*(?:direction|dir|axis)\b")
    if bare:
        core += rf"|(?<![a-z0-9_])(?P<{name}c>[xy])(?![a-z0-9_])"
    return rf"(?:{core})"


def _span(s: str) -> str:
    return (rf"(?:\s*(?:{INTRO}\s*(?P<n{s}>{NUM_PATTERN})\s*(?P<u{s}>{UNIT_PATTERN})?|(?P<m{s}>{NUM_PATTERN})\s*(?P<v{s}>{UNIT_PATTERN})))")


_COUNT = rf"(?P<c>\d+)(?![\d.])\s*(?:-|\s)?\s*(?:تا\s*)?{NOUN}{SUF}"
_BOTH = re.compile(r"(?:each|both|every|all|the\s+two)\s*(?:the\s*)?(?:horizontal\s*)?directions?|هر\s*دو\s*(?:جهت|راستا|طرف)|دو\s*جهت|هر\s*جهت")
_LONE = re.compile(rf"^\W*(?:only\s*|just\s*|فقط\s*)?(?:(?:in|along|direction|dir)\s*|در\s*|{KEY}\s*)?(?:(?P<d>[xy])(?:[\s-]*(?:direction|dir|axis|جهت|راستا))?|(?P<both>{_BOTH.pattern}|both|هر\s*دو|همه|هردو|یکسان))\W*$")


@dataclass
class BayParse:
    counts: dict[str, int] = field(default_factory=dict)   # {"bays_x": 2, "bays_y": 1}
    spans: dict[str, float] = field(default_factory=dict)  # {"bay_x_m": 5.0} (metres)
    ambiguous: int | None = None                          # a bay count with no direction
    ambiguous_span: float | None = None
    units_seen: list[str] = field(default_factory=list)

    @property
    def keys(self) -> list[str]:
        return [*self.counts, *self.spans]


def _letter(m: re.Match, name: str) -> str | None:
    for suffix in ("", "b", "c"):
        try:
            v = m.group(name + suffix)
        except IndexError:
            continue
        if v:
            return v
    return None


def _sp(m: re.Match, s: str) -> float | None:
    for n, u in ((f"n{s}", f"u{s}"), (f"m{s}", f"v{s}")):
        try:
            if m.group(n):
                return to_metres(float(m.group(n)), m.group(u))
        except IndexError:
            continue
    return None


def _mask(t: str, m: re.Match) -> str:
    return t[:m.start()] + " " * (m.end() - m.start()) + t[m.end():]


def parse_bays(text: str) -> BayParse:
    """Parse bay counts / spans from a (possibly merged) message. Never raises; unknown wording gives an empty result."""
    out = BayParse()
    raw_segments = [s for s in re.split(r"[؛;\n]", text or "") if s.strip()]
    t = normalize(text)
    work = t
    mc = out.counts
    ms = out.spans

    def put_count(d: str, n: int) -> None:
        if 1 <= n <= 99:
            mc.setdefault(f"bays_{d}", n)

    def put_span(d: str, v: float | None) -> None:
        if v is not None and v > 0:
            ms.setdefault(f"bay_{d}_m", v)

    # 1. "2x3 bays" / "bays 2x3" (+ optional "of 5 m")
    for pat in (rf"(\d+)\s*x\s*(\d+)(?![\d.])\s*{NOUN}{SUF}(?P<sp>{_span('a')})?", rf"{NOUN}{SUF}\s*[:=]?\s*(\d+)\s*x\s*(\d+)(?![\d.]|\s*x|\s*(?:{UNIT_PATTERN}))(?P<sp>{_span('a')})?"):
        for m in re.finditer(pat, work):
            put_count("x", int(m.group(1))); put_count("y", int(m.group(2)))
            v = _sp(m, "a")
            if v:
                put_span("x", v); put_span("y", v)
            work = _mask(work, m)

    for m in re.finditer(rf"(?<![a-z0-9])bays?[_\s]?([xy])\s*[=:]\s*(\d+)(?![\d.])(?!\s*(?:{UNIT_PATTERN}))", work):
        put_count(m.group(1), int(m.group(2))); work = _mask(work, m)
    for m in re.finditer(rf"(?<![a-z0-9])(?:bay|span)[_\s]?([xy])(?:[_\s]?m)?\s*[=:]\s*(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})?", work):
        put_span(m.group(1), to_metres(float(m.group("num")), m.group("unit"))); work = _mask(work, m)

    # 2. label + direction + value: «تعداد دهانه در جهت x برابر ۲», "bays in x = 2", «طول دهانه x ۶ متر», "bay span in y: 600 cm"
    lab = (rf"(?P<len>(?:طول|عرض|length|width|size)\s*(?:of\s*)?(?:each\s*|هر\s*)?)?(?:(?:تعداد|number\s+of|no\.?\s*of)\s*)?{NOUN}{SUF}\s*"
           rf"{_dir('d', bare=True)}\s*(?:is|are|of|=|:|برابر(?:\s*با)?|است|باشد|را|به|می\s*باشد)?\s*"
           rf"(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})?")
    for m in re.finditer(lab, work):
        if not m.group("len") and re.search(r"\d\s*(?:-|تا)?\s*$", work[:m.start()]):
            continue  # «2 دهانه در جهت y 4.5 متری»: the noun belongs to a count, handled by the count steps
        d = _letter(m, "d")
        unit, num = m.group("unit"), float(m.group("num"))
        if unit or m.group("len") or (num != int(num)):
            put_span(d, to_metres(num, unit))
            if unit:
                out.units_seen.append(unit)
        else:
            put_count(d, int(num))
        work = _mask(work, m)
    # 2b. «... در جهت y برابر ۱» (the noun was given once before)
    for m in re.finditer(rf"{_dir('d')}\s*(?:is|=|:|برابر(?:\s*با)?|است)\s*(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})?(?!\s*(?:-|تا)?\s*{NOUN})", work):
        d, num = _letter(m, "d"), float(m.group("num"))
        if m.group("unit") or num != int(num):
            put_span(d, to_metres(num, m.group("unit")))
        else:
            put_count(d, int(num))
        work = _mask(work, m)

    # 3. direction first: «در جهت x، ۳ دهانه ۵ متری», "in x: 3 bays of 5 m", "x direction 3 bays"
    for m in re.finditer(rf"{_dir('d')}\s*[:،,=-]?\s*(?P<c>\d+)(?![\d.])\s*(?:-|\s)?\s*(?:تا\s*)?{NOUN}{SUF}(?P<sp>{_span('a')})?", work):
        if re.search(rf"\d\s*(?:-|تا)?\s*{NOUN}{SUF}(?:{_span('z')})?\s*$", work[:m.start()]):
            continue  # «2 bays in x, 3 bays in y»: that count belongs to the direction before it (step 4)
        d = _letter(m, "d")
        put_count(d, int(m.group("c")))
        put_span(d, _sp(m, "a"))
        work = _mask(work, m)

    # 3b. «3 bays x 5 m», «۳ دهانه y ۶ متر»: count, bare direction letter, span
    for m in re.finditer(rf"(?P<c>\d+)(?![\d.])\s*{NOUN}{SUF}\s*(?<![a-z0-9_])(?P<d>[xy])(?![a-z0-9_])\s*[:=]?\s*(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})", work):
        put_count(m.group("d"), int(m.group("c")))
        put_span(m.group("d"), to_metres(float(m.group("num")), m.group("unit")))
        out.units_seen.append(m.group("unit"))
        work = _mask(work, m)

    # 4. count [span] direction [span]: "3 bays in x", «۳ دهانه ۵ متری در جهت x», "2 in x", «۲ در x»
    pat4 = (rf"(?P<c>\d+)(?![\d.]|\s*(?:{UNIT_PATTERN}))\s*(?:-|\s)?\s*(?:تا\s*)?(?:{NOUN}{SUF})?(?P<sa>{_span('a')})?\s*[،,]?\s*(?:and\s*)?"
            rf"{_dir('d')}(?P<sb>{_span('b')})?")
    for m in re.finditer(pat4, work):
        d = _letter(m, "d")
        put_count(d, int(m.group("c")))
        put_span(d, _sp(m, "a") or _sp(m, "b"))
        work = _mask(work, m)

    # 5. span then direction: "5 m in x", «۶۰۰ سانتی‌متر در جهت y»
    for m in re.finditer(rf"(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})\s*(?:long\s*|wide\s*|spans?\s*|bays?\s*|طول\s*|دهانه\s*)?{_dir('d')}", work):
        put_span(_letter(m, "d"), to_metres(float(m.group("num")), m.group("unit"))); out.units_seen.append(m.group("unit"))
        work = _mask(work, m)

    # 6. remaining «N bays [of L]» without a direction
    both = bool(_BOTH.search(work))
    remaining = list(re.finditer(rf"{_COUNT}(?P<sp>{_span('a')})?", work))
    for m in remaining:
        n = int(m.group("c"))
        v = _sp(m, "a")
        if both:
            put_count("x", n); put_count("y", n)
            if v:
                put_span("x", v); put_span("y", v)
        else:
            if out.ambiguous is None:
                out.ambiguous = n
            if v and out.ambiguous_span is None:
                out.ambiguous_span = v
        work = _mask(work, m)
    # a span with no direction: "bays of 5 m", «دهانه ۵ متری», "5 m bays"
    for pat in (rf"{NOUN}{SUF}\W{{0,10}}?(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})",
                rf"(?P<num>{NUM_PATTERN})\s*(?P<unit>{UNIT_PATTERN})\s*(?:{NOUN})"):
        for m in re.finditer(pat, work):
            v = to_metres(float(m.group("num")), m.group("unit"))
            out.units_seen.append(m.group("unit"))
            if out.ambiguous_span is None:
                out.ambiguous_span = v
            work = _mask(work, m)
    if out.ambiguous_span is not None and not ({"bay_x_m", "bay_y_m"} & set(ms)):
        ms["bay_x_m"] = ms["bay_y_m"] = out.ambiguous_span
    elif out.ambiguous_span is not None:
        for d in "xy":
            ms.setdefault(f"bay_{d}_m", out.ambiguous_span)

    # 7. short answers in the last segment: "x=2, y=1", «x 2 و y 1», «۲ در ۱», "2 by 1"
    last = normalize(raw_segments[-1]).strip() if raw_segments else ""
    if len(last) <= 40 and not ({"bays_x", "bays_y"} <= set(mc)):
        for m in re.finditer(rf"(?<![a-z0-9_])(?P<d>[xy])\s*[=:]?\s*(?P<c>\d+)(?![\d.]|\s*(?:{UNIT_PATTERN}))", last):
            put_count(m.group("d"), int(m.group("c")))
        m = re.fullmatch(r"\W*(\d+)\s*(?:x|در|by|و|and|,|،)\s*(\d+)\W*", last)
        if m and not mc:
            put_count("x", int(m.group(1))); put_count("y", int(m.group(2)))
    # 8. a later lone answer resolves a pending direction: "x" / «فقط جهت y» / «هر دو جهت»
    if len(raw_segments) > 1 and out.ambiguous is not None and not mc:
        lm = next((x for x in (_LONE.match(normalize(seg).strip()) for seg in reversed(raw_segments[1:])) if x), None)
        if lm:
            n = out.ambiguous
            if lm.group("both"):
                put_count("x", n); put_count("y", n)
            elif lm.group("d"):
                put_count(lm.group("d"), n)
            if mc:
                out.ambiguous = None
    if mc and out.ambiguous is not None and len(mc) < 2 and len(raw_segments) <= 1:
        pass  # keep the pending count visible so the caller can mention it
    elif mc and len(mc) == 2:
        out.ambiguous = None
    return out
