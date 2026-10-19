"""Construction rebar detailing sheets (DXF, ezdxf) from the Mabhas 9 design groups of the 3D frame.

Sheets (side by side in model space, units = mm, each titled by a TEXT on layer TITLE for the in-app viewer):
  1. Beam elevations: top/bottom bars, cut-offs, hooks/development, lap splices, stirrup zones (2h), sections A-A / B-B
  2. Column elevations + sections: ties, confinement zones l0, lap splice in the middle half
  3. Bar bending schedule (mark, diameter, shape, length, count, weight) + total steel weight
Every sheet has a bilingual (Persian/English) title block.

Code basis vs assumptions is listed in DETAILING_BASIS / DETAILING_ASSUMPTIONS and printed on the sheets.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass
from typing import Any

import ezdxf

from app.application import drawing_standard as dstd

from app.application import detailing_assumptions as da
from ezdxf.enums import TextEntityAlignment

STOCK_LENGTH_MM = 12000
FOOTING_DRAW_H = 600  # schematic footing depth drawn under ground-storey columns (details on the FD sheets)
COL_PITCH = 2900  # horizontal gap between column details (labels left, lap note right)
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

    def line(self, layer, a, b):
        self.msp.add_line((self.x0 + a[0], self.y0 + a[1]), (self.x0 + b[0], self.y0 + b[1]), dxfattribs={"layer": layer})

    def poly(self, layer, pts, closed=False):
        self.msp.add_lwpolyline([(self.x0 + x, self.y0 + y) for x, y in pts], close=closed, dxfattribs={"layer": layer})

    def circle(self, layer, c, r):
        self.msp.add_circle((self.x0 + c[0], self.y0 + c[1]), r, dxfattribs={"layer": layer})

    def text(self, layer, p, h, s, center=False, style="LATIN"):
        persian = any("\u0600" <= ch <= "\u06ff" for ch in s)
        style = dstd.PERSIAN if (persian or style == "PERSIAN") else dstd.LATIN
        t = self.msp.add_text(dstd.fa(s), height=h, dxfattribs={"layer": layer, "style": style})
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
        self.line("SECTION", (x, y_lo), (x, y_hi))
        for yy in (y_lo, y_hi):
            self.circle("SECTION", (x, yy), 110)
            self.text("SECTION", (x, yy - 45), 90, label, center=True)

    def hatch(self, layer, pts):
        hh = self.msp.add_hatch(color=8, dxfattribs={"layer": layer})
        hh.set_pattern_fill("ANSI31", scale=8)
        hh.paths.add_polyline_path([(self.x0 + x, self.y0 + y) for x, y in pts], is_closed=True)


LAYERS = {"TITLE": 2, "TITLE_BLOCK": 7, "CONCRETE": 8, "REBAR_MAIN": 1, "REBAR_STIRRUP": 3, "REBAR_TEXT": 4,
          "DIM": 6, "ZONE": 5, "NOTES": 7, "TABLE": 7, "SECTION": 1, "CONC_HATCH": 8}
LINEWEIGHTS = {"CONCRETE": 50, "REBAR_MAIN": 50, "REBAR_STIRRUP": 30, "TITLE_BLOCK": 35, "SECTION": 35}


def _title_block(sh: _Sheet, w: float, h: float, sheet_no: int, fa: str, en: str, project: str) -> None:
    sh.poly("TITLE_BLOCK", [(0, 0), (w, 0), (w, h), (0, h)], closed=True)
    bx, by = w - 9000, 0
    sh.poly("TITLE_BLOCK", [(bx, by), (w, by), (w, by + 2600), (bx, by + 2600)], closed=True)
    for yy in (650, 1300, 1950):
        sh.line("TITLE_BLOCK", (bx, yy), (w, yy))
    sh.text("TITLE_BLOCK", (bx + 200, 2150), 260, f"StructuralAIAgent - {project}")
    sh.text("TITLE_BLOCK", (bx + 200, 1500), 260, en)
    sh.text("TITLE_BLOCK", (bx + 200, 850), 260, fa, style="PERSIAN")
    sh.text("TITLE_BLOCK", (bx + 200, 200), 200, f"Sheet R-{sheet_no:02d}   Units: mm   Code: Mabhas 9 (Iran)   Status: FOR REVIEW / جهت بررسی", style="PERSIAN")


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
    tag = g["group"]
    lines = max(1, round(g["members"] / nsp))  # design "members" counts spans; one continuous beam line has nsp spans
    # concrete outline + columns
    sh.poly("CONCRETE", [(-col / 2, y0), (total + col / 2, y0), (total + col / 2, y0 + h), (-col / 2, y0 + h)], closed=True)
    for k in range(nsp + 1):
        x = k * L
        sh.poly("CONCRETE", [(x - col / 2, y0 - 700), (x - col / 2, y0 + h + 700)])
        sh.poly("CONCRETE", [(x + col / 2, y0 - 700), (x + col / 2, y0 + h + 700)])
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
        sh.callout(((xa + xe) / 2, yt), ((xa + xe) / 2 + 300, y0 + h + 700), f"2Φ{dt} L={L_bar} (T1)")
    if len(top_pieces) > 1:
        for a, e in zip(top_pieces[1:], top_pieces[:-1]):
            sh.text("REBAR_TEXT", (x_end0 + a[0], yt + 120), 90, f"lap {lt}")
            sh.dim((x_end0 + a[0], yt + 8), (x_end0 + e[1], yt + 8), 380)
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
            sh.text("REBAR_TEXT", (x - col / 2, y0 + h + 160), 100, f"{n_extra}Φ{dt} (T2) {A['cutoff']}={ext}")
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
        sh.callout(((xa + xe) / 2 - 400, yb), ((xa + xe) / 2 - 100, y0 - 650), f"{nb}Φ{dbb} L={L_bar} (B1)")
    for a, e in zip(bot_pieces[1:], bot_pieces[:-1]):
        sh.text("REBAR_TEXT", (x_end0 + a[0], yb - 200), 90, f"lap {lb}")
        sh.dim((x_end0 + a[0], yb - 8), (x_end0 + e[1], yb - 8), -330)
    # stirrups
    n_st = 0
    for k in range(nsp):
        f0, f1 = k * L + col / 2, (k + 1) * L - col / 2
        xs = zone_positions(f0, f1, zone, s_end, s_mid)
        n_st += len(xs)
        for x in xs:
            sh.line("REBAR_STIRRUP", (x, y0 + COVER_MM), (x, y0 + h - COVER_MM))
        for za, zb, lab in ((f0, f0 + zone, f"2h={zone}: Φ{ds}@{s_end}"), (f0 + zone, f1 - zone, f"Φ{ds}@{s_mid}"), (f1 - zone, f1, f"Φ{ds}@{s_end}")):
            sh.line("ZONE", (za, y0 - 250), (zb, y0 - 250))
            sh.line("ZONE", (za, y0 - 320), (za, y0 - 180))
            sh.text("REBAR_TEXT", ((za + zb) / 2, y0 - 450), 90, lab, center=True)
    st_len = _r10(2 * (b - 2 * COVER_MM) + 2 * (h - 2 * COVER_MM) + 2 * hookx * ds)
    rows.append(BarRow(f"{tag}-S1", tag, ds, "closed stirrup 135°", st_len, n_st * lines))
    ld_t = dev_length(dt, fy, fc, True, A["psi_t"], A["ld_factor"])
    ldh_t = hook_length(dt, fy, fc, A["hook_factor"])
    sh.text("REBAR_TEXT", (-col / 2, y0 + h + 420), 140,
            f"{tag}  {lines} line(s) x {nsp} spans  {b:.0f}x{h:.0f}   top {g['top_bars']} (T1 2Φ{dt} cont. + T2)  bottom {g['bottom_bars']} (B1)   "
            f"ld,top={ld_t}  ldh={ldh_t} (avail. {col - COVER_MM:.0f})")
    # section cut marks on the elevation: A-A at the first support face, B-B at the first midspan
    sh.cut(col / 2 + 250, y0 - 150, y0 + h + 150, "A")
    sh.cut(L / 2, y0 - 150, y0 + h + 150, "B")
    # sections A-A (support) and B-B (midspan)
    sx = total + col / 2 + 900
    for j, (lab, ntop) in enumerate((("A-A support", nt), ("B-B midspan", 2))):
        ox = sx + j * (b + 900)
        sh.poly("CONCRETE", [(ox, y0), (ox + b, y0), (ox + b, y0 + h), (ox, y0 + h)], closed=True)
        sh.hatch("CONC_HATCH", [(ox, y0), (ox + b, y0), (ox + b, y0 + h), (ox, y0 + h)])
        sh.poly("REBAR_STIRRUP", [(ox + COVER_MM, y0 + COVER_MM), (ox + b - COVER_MM, y0 + COVER_MM),
                                  (ox + b - COVER_MM, y0 + h - COVER_MM), (ox + COVER_MM, y0 + h - COVER_MM)], closed=True)
        for n, d, yy in ((ntop, dt, yt), (nb, dbb, yb)):
            xa, xb = ox + COVER_MM + ds + d / 2, ox + b - COVER_MM - ds - d / 2
            for i in range(n):
                sh.circle("REBAR_MAIN", (xa + (xb - xa) * (i / (n - 1) if n > 1 else 0.5), yy), d / 2)
        sh.text("REBAR_TEXT", (ox + b / 2, y0 - 250), 90, lab, center=True)
        sh.text("REBAR_TEXT", (ox + b / 2, y0 + h + 120), 80, f"{ntop}Φ{dt}", center=True)
        sh.text("REBAR_TEXT", (ox + b / 2, y0 - 130), 80, f"{nb}Φ{dbb}", center=True)
    return sx + 2 * (b + 900)


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
    tag = g["group"]
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
        sh.msp.add_line((sh.x0 + xb, sh.y0 + H), (sh.x0 + xb, sh.y0 + H + lap_lo * 0.5 + 300),
                        dxfattribs={"layer": "REBAR_MAIN", "linetype": "DASHED"})
    if ground:
        sh.poly("CONCRETE", [(x0 - 600, -FOOTING_DRAW_H), (x0 + b + 600, -FOOTING_DRAW_H), (x0 + b + 600, 0), (x0 - 600, 0)], closed=True)
        sh.text("REBAR_TEXT", (x0 - 550, -FOOTING_DRAW_H + 80), 70, "footing (see FD sheets) / پی")
    sh.text("REBAR_TEXT", (x0 + b + 150, lap_lo + lap / 2), 90, f"lap {lap}")
    sh.text("REBAR_TEXT", (x0 + b + 150, lap_lo + lap / 2 - 150), 70, "(middle half, cranked bar)")
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
    sh.text("REBAR_TEXT", (x0 - 1300, H + 560), 120, tag)
    sh.text("REBAR_TEXT", (x0 - 1300, H + 380), 90, f"{g['members']} col.  {b:.0f}x{h:.0f}  {g['bars']}")
    # section
    oy = H + 900
    sh.poly("CONCRETE", [(x0, oy), (x0 + b, oy), (x0 + b, oy + h), (x0, oy + h)], closed=True)
    sh.hatch("CONC_HATCH", [(x0, oy), (x0 + b, oy), (x0 + b, oy + h), (x0, oy + h)])
    sh.text("SECTION", (x0 + b / 2, oy - 160), 90, "C-C", center=True)
    sh.line("SECTION", (x0 - 200, clear / 2), (x0 + b + 200, clear / 2))
    sh.text("SECTION", (x0 - 200, clear / 2 + 40), 80, "C")
    sh.text("SECTION", (x0 + b + 120, clear / 2 + 40), 80, "C")
    sh.callout((xi + 14, H * 0.8), (x0 + b + 250, H * 0.85), f"{n}Φ{d} L={_r10(H + lap)}")
    sh.poly("REBAR_STIRRUP", [(x0 + COVER_MM, oy + COVER_MM), (x0 + b - COVER_MM, oy + COVER_MM),
                              (x0 + b - COVER_MM, oy + h - COVER_MM), (x0 + COVER_MM, oy + h - COVER_MM)], closed=True)
    inset = COVER_MM + dt + d / 2
    pts = _column_bar_positions(n, b, h, inset)
    for px, py in pts:
        sh.circle("REBAR_MAIN", (x0 + px, oy + py), d / 2)
    n_cross = 0
    step = 2 if A["cross_ties"] == "alternate" else 1  # alternate: every other intermediate bar (corner bars are hooped)
    for px in sorted({p[0] for p in pts if inset + 1 < p[0] < b - inset - 1})[::step]:
        sh.line("REBAR_STIRRUP", (x0 + px, oy + COVER_MM), (x0 + px, oy + h - COVER_MM)); n_cross += 1
    for py in sorted({p[1] for p in pts if inset + 1 < p[1] < h - inset - 1})[::step]:
        sh.line("REBAR_STIRRUP", (x0 + COVER_MM, oy + py), (x0 + b - COVER_MM, oy + py)); n_cross += 1
    sh.text("REBAR_TEXT", (x0 + b / 2, oy + h + 120), 80, f"{len(pts)}Φ{d} + hoop Φ{dt}", center=True)
    hoop = _r10(2 * (b - 2 * COVER_MM) + 2 * (h - 2 * COVER_MM) + 2 * hookx * dt)
    rows.append(BarRow(f"{tag}-V1", tag, d, "straight (lap above floor)", _r10(H + lap), n * g["members"]))
    rows.append(BarRow(f"{tag}-H1", tag, dt, "closed hoop 135°", hoop, len(ys) * g["members"]))
    if n_cross:
        rows.append(BarRow(f"{tag}-H2", tag, dt, "cross-tie 135°/90°", _r10(max(b, h) - 2 * COVER_MM + 2 * hookx * dt), n_cross * len(ys) * g["members"]))
    return x0 + b + COL_PITCH


def _schedule(sh: _Sheet, rows: list[BarRow], top: float) -> float:
    cols = [("Mark", 3200), ("Φ (mm)", 1100), ("Shape / شکل", 3300), ("Length (mm)", 1500), ("Count", 1100), ("Weight (kg)", 1500)]
    rh, x, y = 230, 0.0, top
    widths = [w for _, w in cols]
    W = sum(widths)
    sh.poly("TABLE", [(0, y), (W, y), (W, y - rh), (0, y - rh)], closed=True)
    for name, w in cols:
        sh.text("TABLE", (x + 60, y - rh + 60), 110, name, style="PERSIAN"); x += w
    y -= rh
    for r in rows:
        vals = [r.mark, str(r.d), r.shape, str(r.length_mm), str(r.count), f"{r.weight_kg:.1f}"]
        x = 0.0
        for v, w in zip(vals, widths):
            sh.text("TABLE", (x + 60, y - rh + 60), 100, v); x += w
        y -= rh
        sh.line("TABLE", (0, y), (W, y))
    xx = 0.0
    for w in widths[:-1]:
        xx += w; sh.line("TABLE", (xx, top), (xx, y))
    sh.line("TABLE", (0, top), (0, y)); sh.line("TABLE", (W, top), (W, y))
    by_d: dict[int, float] = {}
    for r in rows:
        by_d[r.d] = by_d.get(r.d, 0) + r.weight_kg
    y -= 350
    for d in sorted(by_d):
        sh.text("TABLE", (0, y), 130, f"Φ{d}: {by_d[d]:.1f} kg"); y -= 230
    total = sum(by_d.values())
    sh.text("TABLE", (0, y - 80), 180, f"TOTAL STEEL / وزن کل میلگرد: {total:.1f} kg  (+ waste not included)", style="PERSIAN")
    return total


def build_rebar_doc(inp, design: dict[str, Any], project: str = "3D frame") -> tuple[Any, list[BarRow], float]:
    if not design or not design.get("beams"):
        raise ValueError("rebar detailing needs the Mabhas 9 design (design_code MABHAS9)")
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
    beam_row_h = inp.beam_h_m * 1000 + 2400
    sheet_w = max(nsp_max + 8000, len(columns) * (inp.column_b_m * 1000 + COL_PITCH) + 3000, 12500, 20000)
    pitch = max(sheet_w + 4000, 90000.0)  # A1 viewport at 1:100 must not show the neighbouring sheet
    heights = [len(beams) * beam_row_h + 6000, inp.storey_height_m * 1000 + inp.column_h_m * 1000 + 6500, 0]
    # sheet 1: beams
    s1 = _Sheet(msp, 0, "R-01")
    y = 3500.0
    for g in sorted(beams, key=lambda g: (g["direction"], -g["storey"], g["position"]), reverse=False):
        _draw_beam(s1, y + 700, g, inp, rows, A)
        y += beam_row_h
    # sheet 2: columns
    s2 = _Sheet(msp, pitch, "R-02")
    x = 1800.0
    s2.y0 = 4200.0  # above the title block
    for g in sorted(columns, key=lambda g: (g["storey"], g["position"])):
        x = _draw_column(s2, x, g, inp, rows, A)
    # sheet 3: schedule
    s3 = _Sheet(msp, 2 * pitch, "R-03")
    heights[2] = len(rows) * 230 + 3000 + 3500 + 2500
    H = max(heights)
    s2.y0 = 0.0
    total = _schedule(s3, rows, H - 1600)
    notes = (["[code] " + s for s in DETAILING_BASIS] + ["[assumed] " + s for s in DETAILING_ASSUMPTIONS]
             + ["PROJECT ASSUMPTIONS (change from chat):"] + ["  " + r for r in da.describe(A, inp, "en")])
    for i, s in enumerate(notes):
        s3.text("NOTES", (13200, H - 1600 - i * 260), 120, s)
    titles = [("نقشه آرماتوربندی تیرها", "BEAM REINFORCEMENT DETAILS"),
              ("نقشه آرماتوربندی ستون‌ها", "COLUMN REINFORCEMENT DETAILS"),
              ("جدول مشخصات و وزن میلگردها", "BAR BENDING SCHEDULE")]
    gen = [f"Concrete C{inp.fc_mpa:g} (f'c = {inp.fc_mpa:g} MPa)   Rebar S{inp.fy_mpa:g} (fy = {inp.fy_mpa:g} MPa)",
           f"Clear cover {A['cover_mm']:g} mm   Lap splices class {A['splice_class']} (lengths on the drawing)   Stock length {A['stock_length_m']:g} m",
           "Hooks: stirrups/ties 135° with the extension shown; all dimensions in mm",
           "بتن و میلگرد طبق مبحث نهم؛ پوشش و طول وصله طبق یادداشت‌ها"]
    for i, s_ in enumerate(["GENERAL NOTES / یادداشت‌های عمومی"] + gen):
        s3.text("NOTES", (13200, 2900 + (len(gen) - i) * 300), 160 if i == 0 else 120, s_)
    info = dstd.TitleInfo(project=project)
    for k, (sh, (fa, en)) in enumerate(zip((s1, s2, s3), titles), start=1):
        sh.text("TITLE", (0.25 * pitch, H + 600), 420, f"R-{k:02d} {en}", center=False)
        sh.poly("TITLE_BLOCK", [(0, 0), (sheet_w, 0), (sheet_w, H + 1500), (0, H + 1500)], closed=True)
        scale = next((sc for sc in (50, 100, 200) if sheet_w / sc <= 800 and (H + 1500) / sc <= 450), 200)
        dstd.add_sheet(doc, f"R-{k:02d}", (sh.x0, 0.0, sh.x0 + sheet_w, H + 1500), info, f"R-{k:02d}", fa, en, paper="A1", scale=scale)
    return doc, rows, total


def build_dxf_rebar(inp, raw: dict[str, Any] | None = None, design: dict[str, Any] | None = None) -> str:
    doc, _, _ = build_rebar_doc(inp, design or {})
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue()
