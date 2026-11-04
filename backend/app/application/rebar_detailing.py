"""Construction rebar detailing sheets (DXF, ezdxf) from the Mabhas 9 design groups of the 3D frame.

Sheets (side by side in model space, units = mm, each titled by a TEXT on layer TITLE for the in-app viewer):
  1. Beam elevations: top/bottom bars, cut-offs, hooks/development, lap splices, stirrup zones (2h), sections A-A / B-B
  2. Column elevations + sections: ties, confinement zones l0, lap splice in the middle half
  3. Bar bending schedule (mark, diameter, shape, length, count, weight) + total steel weight
Every sheet has a bilingual (Persian/English) title block.

Code basis vs assumptions is listed in DETAILING_BASIS / DETAILING_ASSUMPTIONS and printed on the sheets.
"""

from __future__ import annotations

import math

import io
import re
from dataclasses import dataclass
from typing import Any

import ezdxf

from app.application import drawing_standard as dstd

from app.application import detailing_assumptions as da
from ezdxf.enums import TextEntityAlignment

STOCK_LENGTH_MM = 12000
FOOTING_DRAW_H = 600  # schematic footing depth drawn under ground-storey columns (details on the FD sheets)
COL_PITCH = 4200
FOOTING_PAD = 2600  # room below a column detail for the footing anchorage + labels
MIN_TEXT = 100  # mm in model space = 2.0 mm on paper at the 1:50 detail scale  # horizontal gap between column details (labels left, lap note right)
COVER_MM = 40
DETAILING_BASIS = [
    "Bars, stirrups, ties, 2h and l0 zones: from the Mabhas 9 design groups of this model (Ch. 9-20/9-21 checks in the app).",
    "Development length ld = fy*psi_t/(2.1*sqrt(fc))*db (db<=18) or /(1.7*sqrt(fc)) (db>=20), psi_t=1.3 top bars, >=300 mm (Mabhas 9 / ACI 318 simplified).",
    "Standard 90 deg hook ldh = 0.24*fy/sqrt(fc)*db >= max(8db,150 mm); hook extension 12db.",
    "Lap splices class B = 1.3*ld; column laps in the middle half of the clear height; no laps inside joints or 2h zones.",
]
DETAILING_ASSUMPTIONS = [
    "Clear cover, stock bar length, cut-off rule, splice class, ld/hook factors, cross-ties, stirrup hooks: project assumptions listed below (defaults 40 mm, 12 m, ln/3, class B, 1.0, every bar, 10db). Unit weight 0.00617*d^2 kg/m.",
    "Top bars: 2 corner bars continuous; extra bars over supports cut off per the project cut-off rule (ln/3, ln/4 or from a parabolic moment diagram).",
    "Bottom bars all continuous, hooked into the end columns; top laps at midspan, bottom laps just outside the 2h zone.",
    "Column cross-ties per project rule (every or alternate intermediate bar, 135 deg hooks); ties continue through the joint at the l0 spacing.",
    "Stirrup/tie cut length = hoop perimeter + 2 hooks of the project stirrup-hook length. Lengths rounded up to 10 mm. One typical member drawn per design group.",
    "Check against the final architectural/structural drawings; a licensed engineer must review before construction.",
]


def unit_weight(d_mm: float) -> float:
    return 0.00617 * d_mm * d_mm


def parse_bars(s: str | None) -> tuple[int, int]:
    m = re.search(r"(\d+)\s*[ΦφØø]\s*(\d+)", s or "")
    if not m:
        raise ValueError(f"cannot read bars {s!r}")
    return int(m.group(1)), int(m.group(2))


def _readable(s: Any) -> bool:
    return bool(re.search(r"(\d+)\s*[ΦφØø]\s*(\d+)", s or ""))


def complete_design(inp, design: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Fill design groups that have no bar arrangement (status FAIL: 'Required bars do not fit in one layer',
    'Section too small', 'No bar arrangement fits') with a Mabhas 9 default so the sheets can still be drawn.

    Beams: the largest one-layer arrangement that fits the web (the most the section can hold) + Mabhas 9 stirrups.
    Columns: the lightest arrangement with rho >= 1 % (Mabhas 9 minimum) + Mabhas 9 ties.
    Every filled group is tagged 'NG' and listed in the returned warnings (shown on the sheets and to the user)."""
    from app.application import mabhas9_rc_design as m9
    out = {**design, "beams": [dict(g) for g in design.get("beams") or []], "columns": [dict(g) for g in design.get("columns") or []]}
    warnings: list[str] = []
    b, h = inp.beam_b_m * 1000, inp.beam_h_m * 1000
    for g in out["beams"]:
        missing = [k for k in ("top_bars", "bottom_bars") if not _readable(g.get(k))]
        if missing:
            best = None
            for db in m9.BEAM_BARS:
                for n in range(2, 9):
                    if (b - 2 * (m9.COVER + m9.STIRRUP_DB) - n * db) / max(n - 1, 1) < max(db, 25.0):
                        break
                    if best is None or n * m9.bar_area(db) > best[2]:
                        best = (n, db, n * m9.bar_area(db))
            n, db, _ = best or (2, 14, 0)
            for k in missing:
                g[k] = f"{n}Φ{db}"
            warnings.append(f"{g.get('group', 'beam')}: {'; '.join(g.get('notes') or ['no design'])} -> drawn with {n}Φ{db} (max one layer), NG: enlarge the section")
            g["detailing_ng"] = True
        elif g.get("rebar_basis") in ("MAX_FEASIBLE", "MINIMUM"):
            # design already provided the NG fill (same rule as above): keep it, tag and warn
            g["detailing_ng"] = True
            warnings.append(f"{g.get('group', 'beam')}: NG -> drawn with {g.get('top_bars')} / {g.get('bottom_bars')} (max one layer), enlarge the section")
        if not re.search(r"[ΦφØø]\s*\d+\s*@\s*\d+", g.get("stirrups") or ""):
            d = h - 60
            s_end = int(min(d / 4, 8 * 14, 24 * m9.STIRRUP_DB, 300) // 25 * 25)
            s_mid = int(min(d / 2, 300) // 25 * 25)
            g["stirrups"] = f"Φ{m9.STIRRUP_DB:g}@{s_end} (2h = {2 * h:.0f} mm), Φ{m9.STIRRUP_DB:g}@{s_mid} elsewhere"
            if not g.get("detailing_ng"):
                warnings.append(f"{g.get('group', 'beam')}: no stirrup design -> Mabhas 9 minimum stirrups")
    cb, ch = inp.column_b_m * 1000, inp.column_h_m * 1000
    clear = inp.storey_height_m * 1000 - h
    for g in out["columns"]:
        if not _readable(g.get("bars")):
            opts = [o for o in m9.column_options(cb, ch) if o[2] / (cb * ch) >= 0.01] or m9.column_options(cb, ch)
            nface, db, _ = opts[0] if opts else (3, 16, 0)
            g["bars"] = f"{4 * nface - 4}Φ{db}"
            g["ties"] = m9.ties(cb, ch, db, clear)["text"]
            warnings.append(f"{g.get('group', 'column')}: {'; '.join(g.get('notes') or ['no design'])} -> drawn with Mabhas 9 minimum {g['bars']} (rho >= 1 %), NG: enlarge the section")
            g["detailing_ng"] = True
        else:
            if g.get("rebar_basis") in ("MAX_FEASIBLE", "MINIMUM"):
                g["detailing_ng"] = True
                warnings.append(f"{g.get('group', 'column')}: NG -> drawn with {g['bars']}, enlarge the section")
            if re.search(r"[ΦφØø]\s*\d+\s*@\s*\d+", g.get("ties") or ""):
                continue
            g["ties"] = m9.ties(cb, ch, parse_bars(g["bars"])[1], clear)["text"]
    out["detailing_warnings"] = warnings
    return out, warnings


def detailing_warning_fa(warnings: list[str]) -> str:
    if not warnings:
        return ""
    return (f"هشدار: {len(warnings)} گروه عضو طراحی آرماتور نداشت (مقطع کوچک است یا آرماتور در یک لایه جا نمی‌شود). "
            "این اعضا با آرماتور پیش‌فرض مبحث ۹ ترسیم و با NG علامت خورده‌اند؛ مقطع را بزرگ کنید و دوباره طراحی کنید.")


def parse_spacing(s: str | None) -> tuple[int, int, int, int | None]:
    """'Φ10@95 (2h = 900 mm), Φ10@175 elsewhere' / 'Φ10@125 over l0 = 458 mm at both ends, Φ10@250 elsewhere'
    -> (d, s_end, s_mid, zone_mm)."""
    pairs = re.findall(r"[ΦφØø]\s*(\d+)\s*@\s*(\d+)", s or "")
    if not pairs:
        raise ValueError(f"cannot read stirrups/ties {s!r}")
    zone = re.search(r"(?:2h|l0)\s*=\s*(\d+)", s or "")
    d, s_end = int(pairs[0][0]), int(pairs[0][1])
    s_mid = int(pairs[1][1]) if len(pairs) > 1 else s_end
    return d, s_end, s_mid, int(zone.group(1)) if zone else None


def _r10(x: float) -> int:
    return int(math.ceil(x / 10.0) * 10)


def dev_length(db: float, fy: float, fc: float, top: bool = False, psi_t: float = 1.3, factor: float = 1.0) -> int:
    k = 2.1 if db <= 18 else 1.7
    return _r10(max(fy * (psi_t if top else 1.0) / (k * math.sqrt(fc)) * db * factor, 300))


def hook_length(db: float, fy: float, fc: float, factor: float = 1.0) -> int:
    return _r10(max(0.24 * fy / math.sqrt(fc) * db * factor, 8 * db, 150))


def lap_length(db: float, fy: float, fc: float, top: bool = False, splice_class: str = "B", psi_t: float = 1.3, factor: float = 1.0) -> int:
    return _r10((1.0 if splice_class == "A" else 1.3) * dev_length(db, fy, fc, top, psi_t, factor))


def cutoff_length(rule: str, ln: float, mu_neg: float, mu_pos: float, n_total: int, n_cont: int, d_eff: float, db: float) -> int:
    """Extension of the extra top bars beyond the support face.
    ln/3 | ln/4: fixed fraction; moment: point where a parabolic moment diagram (uniform load, end moment Mu-,
    span moment Mu+) drops to the capacity share of the continuous bars, plus max(d, 12db) (Mabhas 9 / ACI 12.10.3)."""
    if rule == "ln/4":
        return _r10(ln / 4)
    if rule == "moment" and mu_neg > 0:
        w_l2 = 8 * (mu_neg + max(mu_pos, 0.0))  # w*ln^2 for M(x) = -Mneg + w x (ln - x)/2
        target = mu_neg * n_cont / max(n_total, 1)  # moment carried by the continuous bars alone
        # solve -Mneg + w x(ln-x)/2 = -target  ->  x^2 - ln x + 2(Mneg-target) ln^2 / w_l2 = 0
        c = 2 * (mu_neg - target) * ln * ln / w_l2
        disc = max(ln * ln - 4 * c, 0.0)
        x = (ln - math.sqrt(disc)) / 2
        return _r10(max(x + max(d_eff, 12 * db), ln / 16))
    return _r10(ln / 3)


def zone_positions(f0: float, f1: float, zone: float, s_end: float, s_mid: float, first: float = 50.0) -> list[float]:
    """Stirrup/tie positions between faces f0..f1: s_end over `zone` at both ends, middle spaced evenly at <= s_mid."""
    head, x = [], f0 + first
    while x <= f0 + zone and x <= (f0 + f1) / 2:
        head.append(x); x += s_end
    tail, x = [], f1 - first
    while x >= f1 - zone and x > (f0 + f1) / 2 + 1:
        tail.append(x); x -= s_end
    tail.reverse()
    a, b = head[-1], tail[0] if tail else f1
    n = max(1, math.ceil((b - a) / s_mid))
    mid = [a + (b - a) * i / n for i in range(1, n)]
    return head + mid + tail


def split_bar(total: float, lap: float, centers: list[float], limit: float = STOCK_LENGTH_MM) -> list[tuple[float, float]]:
    """Split a continuous bar [0,total] into stock lengths with laps centred on allowed points."""
    pieces, start = [], 0.0
    while total - start > limit:
        ok = [c for c in centers if c - lap / 2 > start + lap and c + lap / 2 - start <= limit]
        if not ok:
            raise ValueError("no permitted lap-splice location within one stock length")
        c = max(ok)
        pieces.append((start, c + lap / 2))
        start = c - lap / 2
    pieces.append((start, total))
    return pieces


@dataclass
class BarRow:
    mark: str
    member: str
    d: int
    shape: str
    length_mm: int
    count: int

    @property
    def weight_kg(self) -> float:
        return self.length_mm / 1000 * self.count * unit_weight(self.d)


class _Sheet:
    def __init__(self, msp, x0: float, title: str) -> None:
        self.msp, self.x0, self.y0 = msp, x0, 0.0
        self.title = title
        self.secs: list[dict] = []  # RC sections collected for the 1:20 section sheet

    def line(self, layer, a, b):
        self.msp.add_line((self.x0 + a[0], self.y0 + a[1]), (self.x0 + b[0], self.y0 + b[1]), dxfattribs={"layer": layer})

    def poly(self, layer, pts, closed=False):
        self.msp.add_lwpolyline([(self.x0 + x, self.y0 + y) for x, y in pts], close=closed, dxfattribs={"layer": layer})

    def circle(self, layer, c, r):
        self.msp.add_circle((self.x0 + c[0], self.y0 + c[1]), r, dxfattribs={"layer": layer})

    def text(self, layer, p, h, s, center=False, style="LATIN"):
        persian = any("\u0600" <= ch <= "\u06ff" for ch in s)
        style = dstd.PERSIAN if (persian or style == "PERSIAN") else dstd.LATIN
        t = self.msp.add_text(dstd.fa(s), height=max(h, MIN_TEXT), dxfattribs={"layer": layer, "style": style})
        t.set_placement((self.x0 + p[0], self.y0 + p[1]), align=TextEntityAlignment.CENTER if center else TextEntityAlignment.LEFT)


    def callout(self, target, at, s, h=90):
        """Bar callout (e.g. 3Φ25 L=6200) with a leader line from the bar."""
        self.msp.add_leader([(self.x0 + target[0], self.y0 + target[1]), (self.x0 + at[0], self.y0 + at[1]),
                             (self.x0 + at[0] + 150, self.y0 + at[1])], dxfattribs={"layer": "REBAR_TEXT"})
        self.text("REBAR_TEXT", (at[0] + 200, at[1] - h / 2), h, s)

    def dim(self, a, b, offset, vertical=False):
        """Linear DIMENSION (office dim style, 1:50 annotation)."""
        ang = 90 if vertical else 0
        base = (a[0] - offset, a[1]) if vertical else (a[0], a[1] + offset)
        d = self.msp.add_linear_dim(base=(self.x0 + base[0], self.y0 + base[1]), p1=(self.x0 + a[0], self.y0 + a[1]),
                                    p2=(self.x0 + b[0], self.y0 + b[1]), angle=ang, dimstyle="SA-1-50", dxfattribs={"layer": "DIM"})
        d.render()

    def cut(self, x, y_lo, y_hi, label):
        """Section cut mark: vertical cut line with labelled heads at both ends."""
        # office style: cut line with arrow-flag heads (not circles, so they can't be confused with grid bubbles)
        self.line("SECTION", (x, y_lo), (x, y_hi))
        for yy in (y_lo, y_hi):
            self.msp.add_lwpolyline([(self.x0 + x, self.y0 + yy), (self.x0 + x + 220, self.y0 + yy)], dxfattribs={"layer": "SECTION", "const_width": 30})
            self.msp.add_solid([(self.x0 + x + 220, self.y0 + yy + 50), (self.x0 + x + 220, self.y0 + yy - 50), (self.x0 + x + 300, self.y0 + yy)], dxfattribs={"layer": "SECTION"})
            self.text("SECTION", (x + 350, yy - 50), 100, label)

    def hatch(self, layer, pts):
        hh = self.msp.add_hatch(color=8, dxfattribs={"layer": layer})
        hh.set_pattern_fill("ANSI31", scale=8)
        hh.paths.add_polyline_path([(self.x0 + x, self.y0 + y) for x, y in pts], is_closed=True)


LAYERS = {"TITLE": 2, "TITLE_BLOCK": 7, "CONCRETE": 8, "REBAR_MAIN": 1, "REBAR_STIRRUP": 3, "REBAR_TEXT": 4,
          "DIM": 6, "ZONE": 5, "NOTES": 7, "TABLE": 7, "SECTION": 1, "CONC_HATCH": 8,
          "KEYPLAN": 8, "KEYPLAN_HI": 1, "AXIS": 1, "AXIS_BUBBLE": 7}
LINEWEIGHTS = {"CONCRETE": 50, "REBAR_MAIN": 50, "REBAR_STIRRUP": 30, "TITLE_BLOCK": 35, "SECTION": 35}


def _title_block(sh: _Sheet, w: float, h: float, sheet_no: int, fa: str, en: str, project: str) -> None:
    sh.poly("TITLE_BLOCK", [(0, 0), (w, 0), (w, h), (0, h)], closed=True)
    bx, by = w - 9000, 0
    sh.poly("TITLE_BLOCK", [(bx, by), (w, by), (w, by + 2600), (bx, by + 2600)], closed=True)
    for yy in (650, 1300, 1950):
        sh.line("TITLE_BLOCK", (bx, yy), (w, yy))
    sh.text("TITLE_BLOCK", (bx + 200, 2150), 260, f"SAIA - {project}")
    sh.text("TITLE_BLOCK", (bx + 200, 1500), 260, en)
    sh.text("TITLE_BLOCK", (bx + 200, 850), 260, fa, style="PERSIAN")
    sh.text("TITLE_BLOCK", (bx + 200, 200), 200, f"Sheet R-{sheet_no:02d}   Units: mm   Code: Mabhas 9 (Iran)   Status: FOR REVIEW / جهت بررسی", style="PERSIAN")


_FA_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


def _xl(i: int) -> str:
    return str(i + 1)


def _yl(j: int) -> str:
    out, n = "", j
    while True:
        out = chr(65 + n % 26) + out
        n = n // 26 - 1
        if n < 0:
            return out


def beam_lines(inp, g) -> tuple[list[str], str, str]:
    """Grid lines a beam group covers, its span range and the elevation's viewing direction (same naming as the plans)."""
    if g["direction"] == "X":  # beams along X sit on the lettered lines (y = const)
        n = inp.bays_y
        idx = [0, n] if g["position"] == "edge" else list(range(1, n))
        return [_yl(j) for j in idx], f"{_xl(0)}–{_xl(inp.bays_x)}", "Y"
    n = inp.bays_x
    idx = [0, n] if g["position"] == "edge" else list(range(1, n))
    return [_xl(i) for i in idx], f"{_yl(0)}–{_yl(inp.bays_y)}", "X"


def column_points(inp, position: str) -> list[str]:
    nx, ny = inp.bays_x, inp.bays_y
    out = []
    for j in range(ny + 1):
        for i in range(nx + 1):
            p = "corner" if (i in (0, nx) and j in (0, ny)) else "edge" if (i in (0, nx) or j in (0, ny)) else "interior"
            if p == position:
                out.append(f"{_yl(j)}-{_xl(i)}")
    return out


def _key_plan(sh: "_Sheet", ox: float, oy: float, size: float, inp, hi: list[tuple[str, int]]) -> None:
    """Small key plan: all grid lines thin, the member's line(s)/point(s) highlighted. hi: ("X"|"Y"|"P", index...)"""
    W, H = inp.bays_x * inp.bay_x_m, inp.bays_y * inp.bay_y_m
    k = size / max(W, H)
    for i in range(inp.bays_x + 1):
        sh.line("KEYPLAN", (ox + i * inp.bay_x_m * k, oy), (ox + i * inp.bay_x_m * k, oy + H * k))
    for j in range(inp.bays_y + 1):
        sh.line("KEYPLAN", (ox, oy + j * inp.bay_y_m * k), (ox + W * k, oy + j * inp.bay_y_m * k))
    for kind, *v in hi:
        if kind == "X":  # beam along X on lettered line j
            yy = oy + v[0] * inp.bay_y_m * k
            sh.msp.add_lwpolyline([(sh.x0 + ox, sh.y0 + yy), (sh.x0 + ox + W * k, sh.y0 + yy)], dxfattribs={"layer": "KEYPLAN_HI", "const_width": 40})
        elif kind == "Y":
            xx = ox + v[0] * inp.bay_x_m * k
            sh.msp.add_lwpolyline([(sh.x0 + xx, sh.y0 + oy), (sh.x0 + xx, sh.y0 + oy + H * k)], dxfattribs={"layer": "KEYPLAN_HI", "const_width": 40})
        else:
            cx, cy = ox + v[0] * inp.bay_x_m * k, oy + v[1] * inp.bay_y_m * k
            sh.poly("KEYPLAN_HI", [(cx - 60, cy - 60), (cx + 60, cy - 60), (cx + 60, cy + 60), (cx - 60, cy + 60)], closed=True)
    sh.text("KEYPLAN", (ox + W * k / 2, oy - 220), 100, "KEY PLAN", center=True)


def _bubble(sh: "_Sheet", c, label: str, r: float = 200) -> None:
    sh.circle("AXIS_BUBBLE", c, r)
    sh.text("AXIS_BUBBLE", (c[0], c[1] - 55), 110, label, center=True)


def _beam_spans(inp, direction: str) -> tuple[int, float, float]:
    n = inp.bays_x if direction == "X" else inp.bays_y
    L = (inp.bay_x_m if direction == "X" else inp.bay_y_m) * 1000
    col = (inp.column_b_m if direction == "X" else inp.column_h_m) * 1000
    return n, L, col


def _draw_beam(sh: _Sheet, y0: float, g: dict[str, Any], inp, rows: list[BarRow], A: dict[str, Any]) -> float:
    fy, fc = inp.fy_mpa, inp.fc_mpa
    COVER_MM, STOCK = float(A["cover_mm"]), float(A["stock_length_m"]) * 1000
    hookx = float(A["stirrup_hook_db"])
    b, h = inp.beam_b_m * 1000, inp.beam_h_m * 1000
    nt, dt = parse_bars(g["top_bars"])
    nb, dbb = parse_bars(g["bottom_bars"])
    ds, s_end, s_mid, zone = parse_spacing(g["stirrups"])
    zone = zone or int(2 * h)
    nsp, L, col = _beam_spans(inp, g["direction"])
    total = nsp * L  # centre line of end columns
    ln = L - col
    x_end0, x_end1 = -col / 2 + COVER_MM, total + col / 2 - COVER_MM  # bar ends inside end columns
    tag = g["group"] + (" (NG)" if g.get("detailing_ng") else "")
    lines = max(1, round(g["members"] / nsp))  # design "members" counts spans; one continuous beam line has nsp spans
    # concrete outline + columns
    sh.poly("CONCRETE", [(-col / 2, y0), (total + col / 2, y0), (total + col / 2, y0 + h), (-col / 2, y0 + h)], closed=True)
    for k in range(nsp + 1):
        x = k * L
        sh.poly("CONCRETE", [(x - col / 2, y0 - 250), (x - col / 2, y0 + h + 250)])
        sh.poly("CONCRETE", [(x + col / 2, y0 - 250), (x + col / 2, y0 + h + 250)])
    yt, yb = y0 + h - COVER_MM - ds - dt / 2, y0 + COVER_MM + ds + dbb / 2
    hk_t, hk_b = 12 * dt, 12 * dbb
    lt = lap_length(dt, fy, fc, True, A["splice_class"], A["psi_t"], A["ld_factor"])
    lb = lap_length(dbb, fy, fc, False, A["splice_class"], A["psi_t"], A["ld_factor"])
    run = x_end1 - x_end0
    # top continuous (2 bars) with laps at midspans
    top_pieces = split_bar(run, lt, [(k + 0.5) * L - x_end0 for k in range(nsp)], STOCK - hk_t)
    for i, (a, e) in enumerate(top_pieces):
        xa, xe = x_end0 + a, x_end0 + e
        pts = ([(xa, yt - hk_t)] if i == 0 else []) + [(xa, yt), (xe, yt)] + ([(xe, yt - hk_t)] if i == len(top_pieces) - 1 else [])
        sh.poly("REBAR_MAIN", [(x, y + (8 if i % 2 else 0)) for x, y in pts])
        L_bar = _r10(e - a + (hk_t if i == 0 else 0) + (hk_t if i == len(top_pieces) - 1 else 0))
        rows.append(BarRow(f"{tag}-T1{chr(97 + i) if len(top_pieces) > 1 else ''}", tag, dt,
                           "L 90° hooks" if len(top_pieces) == 1 else "straight + hook", L_bar, 2 * lines))
        sh.callout(((xa + xe) / 2, yt), ((xa + xe) / 2 + 300, y0 + h + 620), f"2Φ{dt} L={L_bar} (T1)")
    if len(top_pieces) > 1:
        for a, e in zip(top_pieces[1:], top_pieces[:-1]):
            sh.dim((x_end0 + a[0], yt + 8), (x_end0 + e[1], yt + 8), 470)
    # extra top bars over supports, ln/3 beyond each face
    n_extra = nt - 2
    ext = cutoff_length(A["cutoff"], ln, g.get("Mu_neg_kn_m", 0.0), g.get("Mu_pos_kn_m", 0.0), nt, 2, h - COVER_MM - ds - dt / 2, dt)
    if n_extra > 0:
        for k in range(nsp + 1):
            x = k * L
            a = x_end0 if k == 0 else x - col / 2 - ext
            e = x_end1 if k == nsp else x + col / 2 + ext
            yy = yt - dt - 25
            pts = ([(a, yy - hk_t)] if k == 0 else []) + [(a, yy), (e, yy)] + ([(e, yy - hk_t)] if k == nsp else [])
            sh.poly("REBAR_MAIN", pts)
            sh.text("REBAR_TEXT", (x + col / 2 + 120, y0 + h + 330), 90, f"{n_extra}Φ{dt} (T2) {A['cutoff']}={ext}")
        L_end = _r10(col / 2 - COVER_MM + col / 2 + ext + hk_t)
        L_int = _r10(col + 2 * ext)
        rows.append(BarRow(f"{tag}-T2e", tag, dt, "L 90° hook", L_end, n_extra * 2 * lines))
        if nsp > 1:
            rows.append(BarRow(f"{tag}-T2i", tag, dt, "straight", L_int, n_extra * (nsp - 1) * lines))
    # bottom continuous with laps just outside the 2h zone
    bot_c = [k * L + col / 2 + zone + lb / 2 - x_end0 for k in range(nsp)]
    bot_pieces = split_bar(run, lb, bot_c, STOCK - hk_b)
    for i, (a, e) in enumerate(bot_pieces):
        xa, xe = x_end0 + a, x_end0 + e
        pts = ([(xa, yb + hk_b)] if i == 0 else []) + [(xa, yb), (xe, yb)] + ([(xe, yb + hk_b)] if i == len(bot_pieces) - 1 else [])
        sh.poly("REBAR_MAIN", [(x, y - (8 if i % 2 else 0)) for x, y in pts])
        L_bar = _r10(e - a + (hk_b if i == 0 else 0) + (hk_b if i == len(bot_pieces) - 1 else 0))
        rows.append(BarRow(f"{tag}-B1{chr(97 + i) if len(bot_pieces) > 1 else ''}", tag, dbb,
                           "L 90° hooks" if len(bot_pieces) == 1 else "straight + hook", L_bar, nb * lines))
        # leader drops in the gap between the end-zone and mid-zone spacing labels (never through a label)
        xt = min((k * L + col / 2 + zone + 150 for k in range(nsp)), key=lambda v: abs(v - (xa + xe) / 2))
        xt = min(max(xt, xa + 100), xe - 100)
        sh.callout((xt, yb), (xt + 60, y0 - 1000), f"{nb}Φ{dbb} L={L_bar} (B1)")
    for a, e in zip(bot_pieces[1:], bot_pieces[:-1]):
        sh.dim((x_end0 + a[0], yb - 8), (x_end0 + e[1], yb - 8), -330)
    # stirrups
    n_st = 0
    for k in range(nsp):
        f0, f1 = k * L + col / 2, (k + 1) * L - col / 2
        xs = zone_positions(f0, f1, zone, s_end, s_mid)
        n_st += len(xs)
        for x in xs:
            sh.line("REBAR_STIRRUP", (x, y0 + COVER_MM), (x, y0 + h - COVER_MM))
        for za, zb, lab in ((f0, f0 + zone, f"Φ{ds}@{s_end}"), (f0 + zone, f1 - zone, f"Φ{ds}@{s_mid}  (ends 2h={zone})"), (f1 - zone, f1, f"Φ{ds}@{s_end}")):
            sh.line("ZONE", (za, y0 - 250), (zb, y0 - 250))
            sh.line("ZONE", (za, y0 - 320), (za, y0 - 180))
            sh.text("REBAR_TEXT", ((za + zb) / 2, y0 - 620), 90, lab, center=True)
    st_len = _r10(2 * (b - 2 * COVER_MM) + 2 * (h - 2 * COVER_MM) + 2 * hookx * ds)
    rows.append(BarRow(f"{tag}-S1", tag, ds, "closed stirrup 135°", st_len, n_st * lines))
    ld_t = dev_length(dt, fy, fc, True, A["psi_t"], A["ld_factor"])
    ldh_t = hook_length(dt, fy, fc, A["hook_factor"])
    glines, span, view = beam_lines(inp, g)
    rep, others = glines[0], glines[1:]
    for k in range(nsp + 1):  # grid bubbles above the support columns
        lab = _xl(k) if g["direction"] == "X" else _yl(k)
        _bubble(sh, (k * L, y0 + h + 950), lab)
    fa_span = span.replace("–", " تا ").translate(_FA_DIGITS)
    sh.text("TITLE", (-col / 2, y0 + h + 1700), 160,
            f"BEAM ON GRID {rep} ({span}), along {g['direction']}, STORY {g['storey']}" + (f"  (typ. for: {', '.join(glines)})" if others else ""))
    sh.text("TITLE", (total + col / 2 + 300, y0 + h + 1700), 140,
            f"تیر محور {rep} ({fa_span}) - جهت {g['direction']} - طبقه {str(g['storey']).translate(_FA_DIGITS)}")
    hi = [("X", ord(l[-1]) - 65) if g["direction"] == "X" else ("Y", int(l) - 1) for l in glines]
    _key_plan(sh, total + col / 2 + 1500, y0 - 200, 1600, inp, hi)
    sh.text("REBAR_TEXT", (-col / 2, y0 + h + 1400), 100,
            f"{tag} (elevation viewed along +{view})  {lines} line(s) x {nsp} spans  {b:.0f}x{h:.0f}   top {g['top_bars']} (T1 2Φ{dt} cont. + T2)  bottom {g['bottom_bars']} (B1)   "
            f"ld,top={ld_t}  ldh={ldh_t} (avail. {col - COVER_MM:.0f})")
    # section cut marks on the elevation: A-A at the first support face, B-B at the first midspan
    sh.cut(col / 2 + 250, y0 - 150, y0 + h + 150, "A")
    sh.cut(L / 2, y0 - 150, y0 + h + 150, "B")
    # sections A-A (support) and B-B (midspan) are drawn at 1:20 on sheet R-04
    for lab, ntop, sp in (("A", nt, s_end), ("B", 2, s_mid)):
        bars, groups = [], []
        for n, d, yy, nm in ((ntop, dt, h - COVER_MM - ds - dt / 2, "top"), (nb, dbb, COVER_MM + ds + dbb / 2, "bottom")):
            xa, xb = COVER_MM + ds + d / 2, b - COVER_MM - ds - d / 2
            idx = []
            for i in range(n):
                idx.append(len(bars)); bars.append((xa + (xb - xa) * (i / (n - 1) if n > 1 else 0.5), yy, d))
            groups.append((f"{nm} {n}Φ{d:g}", idx))
        sh.secs.append(dict(b=b, h=h, cover=COVER_MM, tie=ds, bars=bars, groups=groups, tie_label=f"stirrup Φ{ds:g}@{sp:g}",
                            ties=[], axes=f"b along {'Y' if g['direction'] == 'X' else 'X'}, h vertical; beam along {g['direction']}", title=f"{lab}-{lab} ({tag} {'support' if lab == 'A' else 'midspan'})",
                            title_fa=f"برش {lab}-{lab} {'تکیه‌گاه' if lab == 'A' else 'وسط دهانه'}"))
    return total + col / 2 + 3600


def _column_bar_positions(n: int, b: float, h: float, inset: float) -> list[tuple[float, float]]:
    """n bars around a b x h perimeter (4 corners + the rest split between faces in proportion to side length)."""
    extra = max(n - 4, 0)
    nb_side = int(round(extra * b / (2 * (b + h))))
    nh_side = extra // 2 - nb_side
    pts = []
    xs = [inset + (b - 2 * inset) * i / (nb_side + 1) for i in range(nb_side + 2)]
    ys = [inset + (h - 2 * inset) * i / (nh_side + 1) for i in range(1, nh_side + 1)]
    for x in xs:
        pts += [(x, inset), (x, h - inset)]
    for y in ys:
        pts += [(inset, y), (b - inset, y)]
    return pts[:n] if len(pts) >= n else pts


def _draw_column(sh: _Sheet, x0: float, g: dict[str, Any], inp, rows: list[BarRow], A: dict[str, Any]) -> float:
    fy, fc = inp.fy_mpa, inp.fc_mpa
    COVER_MM = float(A["cover_mm"])
    hookx = float(A["stirrup_hook_db"])
    b, h = inp.column_b_m * 1000, inp.column_h_m * 1000
    H, hb = inp.storey_height_m * 1000, inp.beam_h_m * 1000
    n, d = parse_bars(g["bars"])
    dt, s0, s, l0 = parse_spacing(g["ties"])
    l0 = l0 or int(max(b, h, (H - hb) / 6, 450))
    lap = lap_length(d, fy, fc, False, A["splice_class"], A["psi_t"], A["ld_factor"])
    tag = g["group"] + (" (NG)" if g.get("detailing_ng") else "")
    clear = H - hb
    # elevation (floor at y=0 .. beam soffit at clear .. top of beam at H)
    sh.poly("CONCRETE", [(x0, 0), (x0 + b, 0), (x0 + b, H), (x0, H)], closed=True)
    sh.line("CONCRETE", (x0 - 300, clear), (x0 + b + 300, clear))
    sh.line("CONCRETE", (x0 - 300, H), (x0 + b + 300, H))
    lap_lo = clear / 4 + (clear / 2 - lap) / 2  # lap centred in the middle half
    if lap > clear / 2:
        lap_lo = clear / 4
    # every longitudinal bar seen in elevation (both faces + middle bars), offset by cover + tie
    inset = COVER_MM + dt + d / 2
    face_x = sorted({round(px, 1) for px, _ in _column_bar_positions(n, b, h, inset)})
    ground = g["storey"] == 1
    for xp in face_x:
        xb = x0 + xp
        sgn = 1 if xp < b / 2 else -1  # crank towards the core
        if ground:  # anchorage into the footing with a 90° hook on the bottom mesh
            yh = -FOOTING_DRAW_H + 75 + 40
            sh.poly("REBAR_MAIN", [(xb - sgn * 12 * d, yh), (xb, yh), (xb, lap_lo + lap)])
        else:  # bar from the storey below ends after the lap
            sh.line("REBAR_MAIN", (xb, -300), (xb, lap_lo + lap))
        # this storey's bar: cranked by one diameter over the lap, back on line above it (1:6 crank)
        sh.poly("REBAR_MAIN", [(xb + sgn * d, lap_lo), (xb + sgn * d, lap_lo + lap), (xb, lap_lo + lap + 6 * d), (xb, H)])
        # starter into the storey above (shown dashed beyond the top of the beam)
        sh.msp.add_line((sh.x0 + xb, sh.y0 + H), (sh.x0 + xb, sh.y0 + H + 450),
                        dxfattribs={"layer": "REBAR_MAIN", "linetype": "DASHED"})
    if ground:
        sh.poly("CONCRETE", [(x0 - 600, -FOOTING_DRAW_H), (x0 + b + 600, -FOOTING_DRAW_H), (x0 + b + 600, 0), (x0 - 600, 0)], closed=True)
        sh.text("REBAR_TEXT", (x0 - 550, -FOOTING_DRAW_H - 160), 70, "footing (see FD sheets) / پی")
    sh.text("REBAR_TEXT", (x0 + b + 950, lap_lo + lap / 2), 90, f"lap {lap}")
    sh.text("REBAR_TEXT", (x0 + b + 950, lap_lo + lap / 2 - 150), 70, "(middle half, cranked bar)")
    sh.text("REBAR_TEXT", (x0 + b + 150, H + 150), 70, "starter bars to storey above")
    sh.dim((x0 + b, lap_lo), (x0 + b, lap_lo + lap), -(b * 0 + 700), vertical=True)
    sh.dim((x0 + b, 0), (x0 + b, lap_lo), -(700), vertical=True)
    xi = x0 + face_x[0]
    ys = zone_positions(0, clear, l0, s0, s)
    y = clear + s0
    while y < H:
        ys.append(y); y += s0  # through the joint
    for y in ys:
        sh.line("REBAR_STIRRUP", (x0 + COVER_MM, y), (x0 + b - COVER_MM, y))
    for za, zb, lab in ((0, l0, f"l0={l0}: Φ{dt}@{s0}"), (l0, clear - l0, f"Φ{dt}@{s}"), (clear - l0, clear, f"l0: Φ{dt}@{s0}")):
        sh.line("ZONE", (x0 - 250, za), (x0 - 250, zb))
        sh.line("ZONE", (x0 - 320, za), (x0 - 180, za))
        sh.text("REBAR_TEXT", (x0 - 1300, (za + zb) / 2), 80, lab)
    pts_ = column_points(inp, g["position"])
    sh.text("TITLE", (x0 - 1300, H + 1150), 140, f"COLUMN {pts_[0]}, STORY {g['storey']}")
    sh.text("REBAR_TEXT", (x0 - 1300, H + 900), 100, "typ. for: " + ", ".join(pts_[:4]) + (" ..." if len(pts_) > 4 else ""))
    ij = [(ord(p_.split("-")[0][-1]) - 65, int(p_.split("-")[1]) - 1) for p_ in pts_]
    _key_plan(sh, x0 - 1100, H + 1600, 1300, inp, [("P", i, j) for j, i in ij])
    sh.text("REBAR_TEXT", (x0 - 1300, H + 560), 120, tag)
    sh.text("REBAR_TEXT", (x0 - 1300, H + 380), 90, f"{g['members']} col.  {b:.0f}x{h:.0f}  {g['bars']}")
    # section
    oy = H + 900
    sh.line("SECTION", (x0 - 200, clear / 2), (x0 + b + 200, clear / 2))
    sh.text("SECTION", (x0 - 200, clear / 2 + 40), 80, "C")
    sh.text("SECTION", (x0 + b + 120, clear / 2 + 40), 80, "C")
    sh.callout((xi + 14, H * 0.8), (x0 + b + 250, H * 0.85), f"{n}Φ{d} L={_r10(H + lap)}")
    inset = COVER_MM + dt + d / 2
    pts = _column_bar_positions(n, b, h, inset)
    n_cross, ties = 0, []
    step = 2 if A["cross_ties"] == "alternate" else 1  # alternate: every other intermediate bar (corner bars are hooped)
    c = COVER_MM + dt / 2
    for px in sorted({p[0] for p in pts if inset + 1 < p[0] < b - inset - 1})[::step]:
        ties.append(((px, c), (px, h - c))); n_cross += 1
    for py in sorted({p[1] for p in pts if inset + 1 < p[1] < h - inset - 1})[::step]:
        ties.append(((c, py), (b - c, py))); n_cross += 1
    sh.secs.append(dict(b=b, h=h, cover=COVER_MM, tie=dt, bars=[(px, py, d) for px, py in pts],
                        groups=[(f"{len(pts)}Φ{d:g}", list(range(len(pts))))],
                        tie_label=f"hoop Φ{dt:g}@{s0:g} (l0) / @{s:g}" + (f" + {n_cross} cross-ties" if n_cross else ""),
                        ties=ties, axes="b along X, h along Y", title=f"C-C ({tag})", title_fa="برش C-C ستون"))
    hoop = _r10(2 * (b - 2 * COVER_MM) + 2 * (h - 2 * COVER_MM) + 2 * hookx * dt)
    rows.append(BarRow(f"{tag}-V1", tag, d, "straight (lap above floor)", _r10(H + lap), n * g["members"]))
    rows.append(BarRow(f"{tag}-H1", tag, dt, "closed hoop 135°", hoop, len(ys) * g["members"]))
    if n_cross:
        rows.append(BarRow(f"{tag}-H2", tag, dt, "cross-tie 135°/90°", _r10(max(b, h) - 2 * COVER_MM + 2 * hookx * dt), n_cross * len(ys) * g["members"]))
    return x0 + b + COL_PITCH


def _schedule(sh: _Sheet, rows: list[BarRow], top: float, max_rows: int = 10**6) -> tuple[float, float]:
    """Bar schedule; wraps into side-by-side table blocks of at most `max_rows` rows. Returns (total kg, width)."""
    cols = [("Mark", 3200), ("Φ (mm)", 1100), ("Shape / شکل", 3300), ("Length (mm)", 1500), ("Count", 1100), ("Weight (kg)", 1500)]
    rh = 230
    widths = [w for _, w in cols]
    W = sum(widths)
    nblk = max(1, -(-len(rows) // max_rows))
    per = -(-len(rows) // nblk) if rows else 1
    y_end = top
    for k in range(nblk):
        ox, y, part = k * (W + 1300), top, rows[k * per:(k + 1) * per]
        sh.poly("TABLE", [(ox, y), (ox + W, y), (ox + W, y - rh), (ox, y - rh)], closed=True)
        x = ox
        for name, w in cols:
            sh.text("TABLE", (x + 60, y - rh + 60), 110, name, style="PERSIAN"); x += w
        y -= rh
        for r in part:
            vals = [r.mark, str(r.d), r.shape, str(r.length_mm), str(r.count), f"{r.weight_kg:.1f}"]
            x = ox
            for v, w in zip(vals, widths):
                sh.text("TABLE", (x + 60, y - rh + 60), 100, v); x += w
            y -= rh
            sh.line("TABLE", (ox, y), (ox + W, y))
        xx = ox
        for w in widths[:-1]:
            xx += w; sh.line("TABLE", (xx, top), (xx, y))
        sh.line("TABLE", (ox, top), (ox, y)); sh.line("TABLE", (ox + W, top), (ox + W, y))
        y_end = min(y_end, y)
    y = y_end
    by_d: dict[int, float] = {}
    for r in rows:
        by_d[r.d] = by_d.get(r.d, 0) + r.weight_kg
    y -= 350
    for d in sorted(by_d):
        sh.text("TABLE", (0, y), 130, f"Φ{d}: {by_d[d]:.1f} kg"); y -= 230
    total = sum(by_d.values())
    sh.text("TABLE", (0, y - 80), 180, f"TOTAL STEEL / وزن کل میلگرد: {total:.1f} kg  (+ waste not included)", style="PERSIAN")
    return total, nblk * (W + 1300)


def build_rebar_doc(inp, design: dict[str, Any], project: str = "3D frame") -> tuple[Any, list[BarRow], float]:
    if not design or not design.get("beams"):
        raise ValueError("rebar detailing needs the Mabhas 9 design (design_code MABHAS9)")
    design, _warn = complete_design(inp, design)
    A = da.effective(getattr(inp, "assumptions", None))
    doc = dstd.new_document()  # shared office standard: linetypes, lineweights, Latin + Persian text styles
    for name, color in LAYERS.items():
        if name not in doc.layers:
            doc.layers.add(name, color=color, lineweight=LINEWEIGHTS.get(name, 18))
    msp = doc.modelspace()
    rows: list[BarRow] = []
    beams, columns = design["beams"], design["columns"]
    # layout sizes
    nsp_max = max(_beam_spans(inp, g["direction"])[0] * _beam_spans(inp, g["direction"])[1] for g in beams)
    beam_row_h = inp.beam_h_m * 1000 + 3700
    sheet_w = max(nsp_max + 10000, len(columns) * (inp.column_b_m * 1000 + COL_PITCH) + 3000, 12500, 20000)
    pitch = max(sheet_w + 4000, 90000.0)  # A1 viewport at 1:100 must not show the neighbouring sheet
    heights = [len(beams) * beam_row_h + 6000, inp.storey_height_m * 1000 + inp.column_h_m * 1000 + 6500, 0]
    # Pages are filled densely and evenly: an A1 sheet at 1:50 holds ~780 x 720 mm of drawing (39 m x 36 m model).
    PAGE_W, PAGE_H = 38500.0, 23500.0
    info = dstd.title_info(inp, project)
    pages: list[tuple[_Sheet, float, float, str, str, str]] = []  # (sheet, width, height, name, fa, en)
    # R-01 beams: rows split evenly over as few pages as possible, pages side by side in model space
    bw = nsp_max + 10000
    order = sorted(beams, key=lambda g: (g["direction"], -g["storey"], g["position"]))
    rpp = max(1, int((PAGE_H - 4200 - 2400) // beam_row_h))
    npg = math.ceil(len(order) / rpp)
    per = math.ceil(len(order) / npg)
    beam_sheets = []
    for j in range(npg):
        sh = _Sheet(msp, 0.0, "R-01")
        sh.y0 = -j * 60000.0  # pages stacked far apart so a viewport never shows its neighbour
        chunk = order[j * per:(j + 1) * per]
        y = 3500.0
        for g in reversed(chunk):  # first beam of the page at the top
            _draw_beam(sh, y + 700, g, inp, rows, A)
            y += beam_row_h
        beam_sheets.append(sh)
        pages.append((sh, bw, y + 1200, "R-01" if j == 0 else f"R-01.{j + 1}", "نقشه آرماتوربندی تیرها", "BEAM REINFORCEMENT DETAILS"))
    # R-02 columns: details wrapped into balanced rows
    s2 = _Sheet(msp, pitch, "R-02")
    cw = inp.column_b_m * 1000 + COL_PITCH
    col_row_h = inp.storey_height_m * 1000 + 2900 + FOOTING_PAD
    cols_sorted = sorted(columns, key=lambda g: (g["storey"], g["position"]))
    cpr = max(1, int((PAGE_W - 3000) // cw))
    nrows = math.ceil(len(cols_sorted) / cpr)
    cpr = math.ceil(len(cols_sorted) / nrows)
    for r in range(nrows):
        s2.y0 = 4200.0 + (nrows - 1 - r) * col_row_h
        x = 1800.0
        for g in cols_sorted[r * cpr:(r + 1) * cpr]:
            x = _draw_column(s2, x, g, inp, rows, A)
    s2.y0 = 0.0
    col_h = 4200.0 + nrows * col_row_h - FOOTING_PAD + 1500
    pages.append((s2, cpr * cw + 3000, col_h, "R-02", "نقشه آرماتوربندی ستون‌ها", "COLUMN REINFORCEMENT DETAILS"))
    # R-03 schedule + notes, sized to its own content
    s3 = _Sheet(msp, 2 * pitch, "R-03")
    notes = (["[code] " + s for s in DETAILING_BASIS] + ["[assumed] " + s for s in DETAILING_ASSUMPTIONS]
             + (["NOT DESIGNED / NG (drawn with Mabhas 9 defaults - enlarge the section and redesign):"] + ["  " + w for w in _warn] + [detailing_warning_fa(_warn)] if _warn else [])
             + ["PROJECT ASSUMPTIONS (change from chat):"] + ["  " + r for r in da.describe(A, inp, "en")])
    import textwrap
    notes = [w for n_ in notes for w in (textwrap.wrap(n_, 105, subsequent_indent="    ") or [""])]
    by_d_lines = len({r.d for r in rows}) * 230 + 900
    max_rows = int((PAGE_H - 4500 - by_d_lines) // 230)
    nblk = max(1, -(-len(rows) // max_rows))
    H3 = max(-(-len(rows) // nblk) * 230 + by_d_lines + 1000, len(notes) * 260 + 2400) + 3500
    total, tw = _schedule(s3, rows, H3 - 1600, max_rows)
    for i, s in enumerate(notes):
        s3.text("NOTES", (tw + 200, H3 - 1600 - i * 260), 120, s)
    gen = [f"Concrete C{inp.fc_mpa:g} (f'c = {inp.fc_mpa:g} MPa)   Rebar S{inp.fy_mpa:g} (fy = {inp.fy_mpa:g} MPa)",
           f"Clear cover {A['cover_mm']:g} mm   Lap splices class {A['splice_class']} (lengths on the drawing)   Stock length {A['stock_length_m']:g} m",
           "Hooks: stirrups/ties 135° with the extension shown; all dimensions in mm",
           "بتن و میلگرد طبق مبحث نهم؛ پوشش و طول وصله طبق یادداشت‌ها"]
    for i, s_ in enumerate(["GENERAL NOTES / یادداشت‌های عمومی"] + gen):
        s3.text("NOTES", (tw + 200, 2900 + (len(gen) - i) * 300), 160 if i == 0 else 120, s_)
    pages.append((s3, tw + 8200, H3, "R-03", "جدول مشخصات و وزن میلگردها", "BAR BENDING SCHEDULE"))
    for sh, wk, hk, name, fa, en in pages:
        sh.text("TITLE", (0, hk - 600), 420, f"{name} {en}", center=False)
        opn = dstd.Pen(msp, (sh.x0, sh.y0), 50)
        opn.north_arrow((wk - 1500, hk - 900))
        opn.axis_indicator((wk - 3500, hk - 1300))
        hk += 300
        dstd.add_sheet_tiles(doc, name, (sh.x0 - 1500, sh.y0, sh.x0 + wk, sh.y0 + hk), info, fa, en, scale=50)
    s1 = beam_sheets[0]
    s1.secs = [sp for sh in beam_sheets for sp in sh.secs]
    # R-04: every section at 1:20, laid out in rows
    secs = s1.secs + s2.secs
    if secs:
        width_lim = 760 * 20
        lines_, cur, x = [], [], 0.0  # 1) wrap sections into rows of the sheet width
        for sp in secs:
            w = sp["b"] + 105 * 20
            if cur and x + w > width_lim:
                lines_.append(cur); cur, x = [], 0.0
            cur.append(sp); x += w
        lines_.append(cur)
        row_hs = [max(sp["h"] for sp in ln_) + 50 * 20 + 25 * 20 for ln_ in lines_]
        usable = (594 - 30 - 75) * 20 * 0.98 - 16 * 20 - 1200
        npg, acc = 1, 0.0  # 2) as few pages as possible, rows split evenly
        for rh_ in row_hs:
            if acc + rh_ > usable:
                npg += 1; acc = 0.0
            acc += rh_
        per = -(-len(lines_) // npg)
        for pg in range(npg):
            pen = dstd.Pen(msp, (3 * pitch, -pg * 40000.0), 20)
            regs, rows_y = [], 0.0
            for ln_, rh_ in zip(lines_[pg * per:(pg + 1) * per], row_hs[pg * per:(pg + 1) * per]):
                x = 0.0
                for sp in ln_:
                    regs.append(dstd.rc_section(pen, x + 25 * 20, rows_y - sp["h"], sp["b"], sp["h"], sp["cover"], sp["tie"], sp["bars"],
                                                sp["groups"], sp["tie_label"], sp["ties"], sp["title"], sp["title_fa"], axes=sp.get("axes")))
                    x += sp["b"] + 105 * 20
                rows_y -= rh_
            if not regs:
                continue
            X0 = min(r[0] for r in regs); Y0 = min(r[1] for r in regs); X1 = max(r[2] for r in regs); Y1 = max(r[3] for r in regs)
            name = "R-04" if pg == 0 else f"R-04.{pg + 1}"
            pen.text("S-TITLE", (X0, Y1 + 8 * 20), f"{name} REINFORCED CONCRETE SECTIONS 1:20", h=5.0)
            dstd.add_sheet_tiles(doc, name, (pen.ox + X0 - 400, pen.oy + Y0 - 400, pen.ox + X1 + 400, pen.oy + Y1 + 16 * 20 + 400), info,
                                 "برش‌های تیر و ستون", "BEAM & COLUMN SECTIONS", scale=20)
    return doc, rows, total


def build_dxf_rebar(inp, raw: dict[str, Any] | None = None, design: dict[str, Any] | None = None) -> str:
    doc, _, _ = build_rebar_doc(inp, design or {})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue()
