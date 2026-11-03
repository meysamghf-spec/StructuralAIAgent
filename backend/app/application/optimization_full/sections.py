"""Candidate section catalogues and parsing of user section lists (chat text, PDF, Excel, CSV).

Everything is optional: whatever the user does not give falls back to the documented defaults below.
"""

from __future__ import annotations

import io
import re
from typing import Any

from app.application.model_import.catalog import FAMILIES, lookup

_FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")

# ---------------------------------------------------------------- defaults (metres)
DEFAULT_RC_COLUMNS = sorted({(b / 100, h / 100) for b in range(30, 85, 5) for h in range(b, min(2 * b, 100) + 1, 5)},
                            key=lambda s: (s[0] * s[1], s[1]))
DEFAULT_RC_BEAMS = sorted({(b / 100, h / 100) for b in range(25, 65, 5) for h in range(35, 80, 5) if b <= h <= 2.5 * b},
                          key=lambda s: (s[0] * s[1], s[1]))
DEFAULT_STEEL = {
    "beam": [f"IPE{n}" for n in sorted(FAMILIES["IPE"]) if 140 <= n <= 600],
    "column": [f"HEB{n}" for n in sorted(FAMILIES["HEB"]) if 140 <= n <= 600],
    "brace": [f"2UNP{n}" for n in sorted(FAMILIES["UNP"]) if 80 <= n <= 300],
}
DEFAULT_REBAR_MM = [12, 14, 16, 18, 20, 22, 25, 28, 32]
ALL_REBAR_MM = (8, 10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 36, 40)

_KIND_WORDS = {
    "beam": r"(?:تیر(?:ها|‌ها|های|‌های)?|beams?|girders?)",
    "column": r"(?:ستون(?:ها|‌ها|های|‌های)?|columns?)",
    "brace": r"(?:مهاربند(?:ها|‌ها|ی)?|بادبند(?:ها|‌ها)?|braces?|bracings?)",
    "rebar": r"(?:میلگرد(?:ها|‌ها)?|آرماتور(?:ها|‌ها)?|rebars?|bars?|reinforcement)",
}
_STEEL_RE = re.compile(r"\b(2\s*[x×]?\s*)?(IPE|HEA|HEB|HE|UNP|UPN|BOX|PIPE|SHS|RHS|CHS)\s*-?\s*(\d+(?:\.\d+)?)(?:\s*([AB])(?![A-Za-z]))?"
                       r"(?:\s*[x×*]\s*(\d+(?:\.\d+)?))?(?:\s*[x×*]\s*(\d+(?:\.\d+)?))?", re.I)
_RANGE_RE = re.compile(r"\b(2\s*)?(IPE|HEA|HEB|UNP)\s*(\d+)\s*(?:-|–|to|تا|الی)\s*(?:(?:IPE|HEA|HEB|UNP)\s*)?(\d+)", re.I)
_RECT_RE = re.compile(r"(?<![\w.])(\d{2,3}(?:\.\d+)?)\s*[x×*]\s*(\d{2,3}(?:\.\d+)?)(?![\w.])")
_DIA_RE = re.compile(r"(?:Φ|φ|ø|Ø|∅|phi|T|d)\s*(\d{1,2})\b", re.I)
_FC_RE = re.compile(r"(?:\bC|fc'?\s*=?\s*|بتن\s*(?:رده\s*)?C?)\s*(\d{2})\b", re.I)
_FY_RE = re.compile(r"\b(?:A\s*(I{1,4}|[1-4])|S\s*(\d{3})|fy\s*=?\s*(\d{3}))\b", re.I)
_STEEL_GRADE_RE = re.compile(r"\b(?:ST\s*(37|44|52)|S\s*(235|275|355))\b", re.I)
_REBAR_GRADE = {"I": 240, "1": 240, "II": 300, "2": 300, "III": 400, "3": 400, "IV": 500, "4": 500}
_STEEL_FY = {"37": 240, "44": 280, "52": 360, "235": 235, "275": 275, "355": 355}

_POSITION_WORDS = {
    "corner": r"(?:گوشه|corner)", "edge": r"(?:کناری|کنار|پیرامونی|پیرامون|edge|perimeter|exterior)",
    "interior": r"(?:میانی|داخلی|وسط|interior|inner|middle)",
}


def normalize(text: str) -> str:
    return (text or "").translate(_FA_DIGITS).replace("٫", ".").replace("×", "x")


_ANY_KIND = re.compile("|".join(f"(?:{rx})" for rx in _KIND_WORDS.values()) + r"|(?:بتن|concrete|steel|فولاد)", re.I)


def _clauses(text: str) -> list[str]:
    """Sentences / lines, further split wherever a new member kind starts («تیرها ...، ستون‌ها ...»)."""
    out: list[str] = []
    for c in re.split(r"[\n;؛]+|(?<=[^\d])\.(?=\s)", normalize(text)):
        starts = [m.start() for m in _ANY_KIND.finditer(c)]
        cuts = [0] + [s for s in starts[1:] if re.search(r"[,،:]\s*$|\s(?:and|و)\s*$", c[:s]) or s > 0]
        cuts = sorted(set(cuts))
        for a, b in zip(cuts, cuts[1:] + [len(c)]):
            seg = c[a:b].strip(" ,،")
            if seg:
                out.append(seg)
    return out


def _kind_of(clause: str) -> str | None:
    low = clause.lower()
    hits = [(m.start(), k) for k, rx in _KIND_WORDS.items() for m in [re.search(rx, low, re.I)] if m]
    return min(hits)[1] if hits else None


def _rect_cm(a: float, b: float) -> tuple[float, float] | None:
    if 15 <= a <= 200 and 15 <= b <= 250:
        return (round(a / 100, 3), round(b / 100, 3))
    if 150 <= a <= 2000 and 150 <= b <= 2500:  # mm
        return (round(a / 1000, 3), round(b / 1000, 3))
    return None


def _steel_names(clause: str) -> list[str]:
    out: list[str] = []
    for m in _RANGE_RE.finditer(clause):
        fam = m.group(2).upper(); lo, hi = sorted((int(m.group(3)), int(m.group(4))))
        dbl = "2" if m.group(1) else ""
        out += [f"{dbl}{fam}{n}" for n in sorted(FAMILIES[fam]) if lo <= n <= hi]
    stripped = _RANGE_RE.sub(" ", clause)
    for m in _STEEL_RE.finditer(stripped):
        dbl, fam, a, ab, b, c = m.groups()
        fam = fam.upper().replace("UPN", "UNP")
        if fam == "HE" and ab:
            fam = "HE" + ab.upper()
        elif fam == "HE":
            continue
        if fam in ("BOX", "SHS", "RHS", "PIPE", "CHS"):
            name = f"{'PIPE' if fam in ('PIPE', 'CHS') else 'BOX'}{a}" + (f"X{b}" if b else "") + (f"X{c}" if c else "")
        else:
            name = f"{'2' if dbl else ''}{fam}{int(float(a))}"
        if lookup(name):
            out.append(name)
    return list(dict.fromkeys(out))


def _rebar(clause: str) -> list[int]:
    nums = [int(x) for x in _DIA_RE.findall(clause)]
    if not nums and re.search(_KIND_WORDS["rebar"], clause, re.I):
        body = re.split(_KIND_WORDS["rebar"], clause, maxsplit=1, flags=re.I)[-1]
        body = re.sub(r"\bA\s*(?:I{1,4}|[1-4])\b|\bS\s*\d{3}\b", " ", body, flags=re.I)
        nums = [int(x) for x in re.findall(r"(?<![\w.])(\d{1,2})(?![\w.])", body)]
    return sorted({n for n in nums if n in ALL_REBAR_MM})


def _selector(clause: str, kind: str) -> dict[str, Any]:
    sel: dict[str, Any] = {}
    low = clause.lower()
    pos = [p for p, rx in _POSITION_WORDS.items() if re.search(rx, low, re.I)]
    if pos:
        sel["positions"] = pos
    m = re.search(r"(?:طبقات|طبقه|storeys?|stories|floors?|levels?)\s*(\d+)\s*(?:-|–|to|تا|الی)\s*(\d+)", low)
    if m:
        a, b = sorted((int(m.group(1)), int(m.group(2))))
        sel["storeys"] = list(range(a, b + 1))
    else:
        m = re.search(r"(?:طبقه|storey|story|floor|level)\s*(\d+)", low)
        if m:
            sel["storeys"] = [int(m.group(1))]
        elif re.search(r"(?:بام|roof)", low):
            sel["storeys"] = ["roof"]
    if kind == "beam":
        m = re.search(r"(?:جهت|راستای|direction|dir\.?)\s*([xy])\b|\b([xy])[- ]?(?:dir|direction)\b", low)
        if m:
            sel["direction"] = (m.group(1) or m.group(2)).upper()
    return sel


def parse_section_lists(text: str) -> dict[str, Any]:
    """-> {beams: [[b,h] m | steel name], columns, braces, rebar_mm, materials{fc_mpa, fy_mpa, steel_fy_mpa}, member_types[]}.

    Example: «ستون‌ها 40x40, 40x60, 50x50؛ تیرها 30x40 تا ... ؛ میلگرد 16 18 20؛ بتن C30؛ ستون‌های گوشه طبقات 1 تا 3: 50x50, 50x60»
    """
    res: dict[str, Any] = {"beams": [], "columns": [], "braces": [], "rebar_mm": [], "materials": {}, "member_types": [], "found": False}
    for clause in _clauses(text):
        kind = _kind_of(clause)
        rects = [r for a, b in _RECT_RE.findall(clause) if (r := _rect_cm(float(a), float(b)))]
        steels = _steel_names(clause)
        bars = _rebar(clause) if kind == "rebar" or re.search(r"Φ|φ|ø|Ø|∅|phi", clause, re.I) else []
        if bars:
            res["rebar_mm"] = sorted(set(res["rebar_mm"]) | set(bars))
        if m := _FC_RE.search(clause):
            if 15 <= int(m.group(1)) <= 70 and re.search(r"بتن|concrete|\bC\d{2}\b|fc", clause, re.I):
                res["materials"]["fc_mpa"] = float(m.group(1))
        if m := _FY_RE.search(clause):
            g = m.group(1) or ""
            fy = _REBAR_GRADE.get(g.upper()) if g else float(m.group(2) or m.group(3))
            if fy and (kind == "rebar" or g or m.group(3)):
                res["materials"]["fy_mpa"] = float(fy)
        if m := _STEEL_GRADE_RE.search(clause):
            res["materials"]["steel_fy_mpa"] = float(_STEEL_FY[m.group(1) or m.group(2)])
        if kind in (None, "rebar"):
            continue
        cands = [list(r) for r in rects] + steels
        if not cands:
            continue
        sel = _selector(clause, kind)
        if sel:
            name = re.split(r"[:：]", clause)[0].strip()[:40] or f"{kind}-group"
            res["member_types"].append({"name": name, "type": kind, **sel, "candidates": cands})
        else:
            key = {"beam": "beams", "column": "columns", "brace": "braces"}[kind]
            for c in cands:
                if c not in res[key]:
                    res[key].append(c)
    res["found"] = bool(res["beams"] or res["columns"] or res["braces"] or res["rebar_mm"] or res["materials"] or res["member_types"])
    return res


def extract_text(filename: str, data: bytes) -> str:
    """Plain text of an attached section table: .xlsx/.xlsm (all sheets), .csv/.txt, .pdf (text layer)."""
    low = (filename or "").lower()
    if low.endswith((".xlsx", ".xlsm")):
        from openpyxl import load_workbook

        wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        lines = []
        for ws in wb.worksheets:
            header = ""
            for row in ws.iter_rows(values_only=True):
                cells = [str(c).strip() for c in row if c is not None and str(c).strip()]
                if not cells:
                    continue
                if _kind_of(" ".join(cells)) and not _RECT_RE.search(" ".join(cells)) and not _steel_names(" ".join(cells)):
                    header = cells[0]  # a header row like "Columns" applies to the rows below it
                    continue
                lines.append(f"{header} {' '.join(cells)}".strip())
        return "\n".join(lines)
    if low.endswith(".pdf"):
        from pypdf import PdfReader

        return "\n".join((p.extract_text() or "") for p in PdfReader(io.BytesIO(data)).pages[:30])
    return data.decode("utf-8", errors="replace")


def merge_lists(*parts: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"beams": [], "columns": [], "braces": [], "rebar_mm": [], "materials": {}, "member_types": []}
    for p in parts:
        if not p:
            continue
        for k in ("beams", "columns", "braces"):
            out[k] += [c for c in p.get(k) or [] if c not in out[k]]
        out["rebar_mm"] = sorted(set(out["rebar_mm"]) | set(p.get("rebar_mm") or []))
        out["materials"].update(p.get("materials") or {})
        out["member_types"] += p.get("member_types") or []
    return out
