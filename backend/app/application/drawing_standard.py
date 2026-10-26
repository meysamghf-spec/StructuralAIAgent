"""Shared drawing standard for every DXF the platform writes (Iranian engineering-office style).

Model space is in millimetres. Each drawing gets a paper-space layout (A1 or A3, scale 1:50 / 1:100 / 1:200)
with border, title block (project, employer, designer, checker, scale, date, sheet no.), revision table and a logo
placeholder, plus a viewport onto its model-space region. Helpers: layers/linetypes/lineweights, text styles
(Latin + Persian-capable), a dimension style, grids with bubbles on both ends and chained + overall DIMENSIONs,
level marks, hatches, tables, bar callouts with leaders, section cut marks and a notes block.

Persian text is shaped (arabic_reshaper) and put in visual order (python-bidi) because AutoCAD's TEXT entity does
neither; the in-app viewer reverses it back for the browser.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Sequence

import ezdxf
from ezdxf.enums import TextEntityAlignment

try:  # optional at import time; required in production (requirements.txt)
    import arabic_reshaper
    from bidi.algorithm import get_display
except Exception:  # pragma: no cover
    arabic_reshaper = None
    get_display = None

# name: (ACI colour, lineweight in 1/100 mm, linetype)
LAYERS: dict[str, tuple[int, int, str]] = {
    "S-AXIS": (1, 18, "CENTER"),          # grid / axis lines
    "S-AXIS-BUBBLE": (7, 25, "Continuous"),
    "S-CONC": (7, 50, "Continuous"),      # concrete outline (thick)
    "S-CONC-HIDDEN": (8, 25, "DASHED"),   # hidden edges (beams under slab, footing outline in plans)
    "S-CONC-HATCH": (8, 9, "Continuous"),
    "S-FOOT": (30, 50, "Continuous"),
    "S-FOOT-HATCH": (31, 9, "Continuous"),
    "S-REBAR-MAIN": (1, 50, "Continuous"),   # longitudinal bars
    "S-REBAR-STIR": (3, 30, "Continuous"),   # stirrups / ties
    "S-REBAR-TEXT": (4, 18, "Continuous"),
    "S-TAG": (2, 25, "Continuous"),          # C1 / B1 / F1 tags
    "S-DIMS": (6, 18, "Continuous"),
    "S-LEVEL": (5, 25, "Continuous"),
    "S-SECTION": (1, 35, "Continuous"),      # A-A cut marks
    "S-TABLE": (7, 25, "Continuous"),
    "S-NOTES": (7, 18, "Continuous"),
    "S-TITLE": (2, 35, "Continuous"),
    "S-BORDER": (7, 70, "Continuous"),
    "S-TITLEBLOCK": (7, 35, "Continuous"),
    "S-VIEWPORT": (8, 9, "Continuous"),
    "S-SHEET": (8, 0, "Continuous"),
}
LATIN, PERSIAN = "SA-LATIN", "SA-PERSIAN"
PAPER = {"A3": (420.0, 297.0), "A1": (841.0, 594.0)}
SCALES = (20, 25, 50, 100, 200)


def fa(text: str) -> str:
    """Shape + reorder Persian for AutoCAD TEXT entities (no-op for pure Latin)."""
    if not text or not any("\u0600" <= ch <= "\u06ff" for ch in text) or arabic_reshaper is None:
        return text
    return get_display(arabic_reshaper.reshape(text))


@dataclass
class TitleInfo:
    project: str = "SAIA project"
    employer: str = "تعیین نشده"
    designer: str = "SAIA"
    checker: str = "تعیین نشده"
    drawing_date: str = field(default_factory=lambda: date.today().isoformat())
    revisions: list[tuple[str, str, str]] = field(default_factory=lambda: [("0", date.today().isoformat(), "Issued for review / جهت بررسی")])
    code: str = "Mabhas 9 / Standard 2800"


def title_info(inp=None, default_project: str = "3D RC frame") -> TitleInfo:
    """Title-block fields from the project record (assumptions set from chat: «کارفرما: …», "checker: …")."""
    rec: dict = {}
    try:
        from app.application import detailing_assumptions as da
        rec = da.effective(getattr(inp, "assumptions", None)) if inp is not None else {}
    except Exception:  # noqa: BLE001 - title block must never break a drawing
        rec = {}
    pick = lambda k, d: (str(rec.get(k)).strip() if rec.get(k) else None) or d  # noqa: E731
    return TitleInfo(project=pick("project_name", getattr(inp, "project_name", None) or default_project),
                     employer=pick("employer", "تعیین نشده"), designer=pick("designer", "SAIA"),
                     checker=pick("checker", "تعیین نشده"))


def new_document() -> Any:
    doc = ezdxf.new("R2010", setup=True)  # setup=True loads CENTER/DASHED linetypes and standard dimstyles
    doc.header["$INSUNITS"] = 4
    doc.header["$LWDISPLAY"] = 1
    doc.header["$LTSCALE"] = 1
    for name, (color, lw, lt) in LAYERS.items():
        doc.layers.add(name, color=color, lineweight=lw, linetype=lt)
    doc.styles.add(LATIN, font="arial.ttf")
    doc.styles.add(PERSIAN, font="tahoma.ttf")  # Tahoma ships with Windows and covers Persian
    for scale in SCALES:
        ds = doc.dimstyles.new(f"SA-1-{scale}")
        k = scale / 100.0
        ds.dxf.dimtxsty = LATIN
        ds.dxf.dimtxt = 2.5 * scale    # 2.5 mm on paper
        ds.dxf.dimasz = 2.0 * scale
        ds.dxf.dimblk = "ARCHTICK"
        ds.dxf.dimexo = 1.5 * scale
        ds.dxf.dimexe = 1.5 * scale
        ds.dxf.dimgap = 1.0 * scale
        ds.dxf.dimdec = 0
        ds.dxf.dimclrd = 6
        ds.dxf.dimclre = 6
        ds.dxf.dimclrt = 7
        ds.dxf.dimtad = 1
        ds.dxf.dimtix = 0
        ds.dxf.dimscale = 1
        _ = k
    return doc


GRID_LEGEND = ("Grids 1,2,3... perpendicular to X", "Grids A,B,C... perpendicular to Y")


class Pen:
    """Drawing helpers in model space (mm), offset by an origin; `scale` sizes annotation for the target plot."""

    def __init__(self, msp, origin=(0.0, 0.0), scale: int = 100) -> None:
        self.msp, self.ox, self.oy, self.scale = msp, origin[0], origin[1], scale

    def p(self, x, y):
        return (self.ox + x, self.oy + y)

    def line(self, layer, a, b, **kw):
        return self.msp.add_line(self.p(*a), self.p(*b), dxfattribs={"layer": layer, **kw})

    def poly(self, layer, pts, closed=False):
        return self.msp.add_lwpolyline([self.p(x, y) for x, y in pts], close=closed, dxfattribs={"layer": layer})

    def rect(self, layer, x0, y0, x1, y1):
        return self.poly(layer, [(x0, y0), (x1, y0), (x1, y1), (x0, y1)], closed=True)

    def circle(self, layer, c, r):
        return self.msp.add_circle(self.p(*c), r, dxfattribs={"layer": layer})

    def text(self, layer, pos, s, h=2.5, align="LEFT", rot=0.0):
        """h in paper mm; Persian strings use the Persian style and are shaped."""
        persian = any("\u0600" <= ch <= "\u06ff" for ch in s)
        t = self.msp.add_text(fa(s), height=h * self.scale, rotation=rot,
                              dxfattribs={"layer": layer, "style": PERSIAN if persian else LATIN})
        t.set_placement(self.p(*pos), align=getattr(TextEntityAlignment, align))
        return t

    def hatch(self, layer, pts, pattern="ANSI31", pscale=None, solid=False):
        h = self.msp.add_hatch(color=LAYERS[layer][0], dxfattribs={"layer": layer})
        if solid:
            h.set_solid_fill(color=LAYERS[layer][0])
        else:
            h.set_pattern_fill(pattern, scale=pscale or self.scale / 4)
        h.paths.add_polyline_path([self.p(x, y) for x, y in pts], is_closed=True)
        return h

    def dim(self, a, b, offset, angle=0.0, text_at: float | None = None):
        """Linear DIMENSION a→b with the dim line `offset` from a (perpendicular to `angle`)."""
        import math
        ux, uy = math.cos(math.radians(angle + 90)), math.sin(math.radians(angle + 90))
        base = (a[0] + ux * offset, a[1] + uy * offset)
        loc = None
        if text_at is not None:  # move the text along the dim line (e.g. off a crossing axis)
            loc = self.p(text_at, base[1] + 1.75 * self.scale) if angle == 0 else self.p(base[0] - 1.75 * self.scale, text_at)
        d = self.msp.add_linear_dim(base=self.p(*base), p1=self.p(*a), p2=self.p(*b), angle=angle, location=loc,
                                    dimstyle=f"SA-1-{self.scale}", dxfattribs={"layer": "S-DIMS"})
        d.render()
        return d

    def chain_dims(self, coords: Sequence[float], fixed: float, offset: float, horizontal: bool, overall: bool = True):
        """Chained dimensions between consecutive coordinates plus the overall dimension one step further out."""
        pt = (lambda c: (c, fixed)) if horizontal else (lambda c: (fixed, c))
        ang = 0.0 if horizontal else 90.0
        sgn = 1 if offset > 0 else -1
        off = offset if horizontal else -offset  # 90° dims measure their offset to the left
        for a, b in zip(coords, coords[1:]):
            self.dim(pt(a), pt(b), off, ang)
        if overall and len(coords) > 2:
            mid = (coords[0] + coords[-1]) / 2
            k = min(range(len(coords) - 1), key=lambda i: abs((coords[i] + coords[i + 1]) / 2 - mid))
            at = (coords[k] + coords[k + 1]) / 2  # text in a bay, never on an intermediate axis
            self.dim(pt(coords[0]), pt(coords[-1]), off + sgn * (6 * self.scale if horizontal else -6 * self.scale), ang, text_at=at)

    def bubble(self, c, label, r=None):
        r = r or 4.0 * self.scale
        self.circle("S-AXIS-BUBBLE", c, r)
        self.text("S-AXIS-BUBBLE", c, label, h=3.5, align="MIDDLE_CENTER")

    def _arrow(self, a, b, label):
        s = self.scale
        self.line("S-NOTES", a, b)
        ux, uy = (b[0] - a[0]), (b[1] - a[1])
        n = math.hypot(ux, uy) or 1.0
        ux, uy = ux / n, uy / n
        hl, hw = 2.5 * s, 1.0 * s
        tip = [b, (b[0] - ux * hl - uy * hw, b[1] - uy * hl + ux * hw), (b[0] - ux * hl + uy * hw, b[1] - uy * hl - ux * hw)]
        self.hatch("S-NOTES", tip, solid=True)
        self.text("S-NOTES", (b[0] + ux * 2.5 * s, b[1] + uy * 2.5 * s), label, h=3.0, align="MIDDLE_CENTER")

    def axis_indicator(self, o, h_label="X", v_label="Y"):
        """UCS-style indicator: two arrows from o (horizontal = h_label, vertical = v_label) and a small origin box."""
        s = self.scale
        self.rect("S-NOTES", o[0] - 1 * s, o[1] - 1 * s, o[0] + 1 * s, o[1] + 1 * s)
        self._arrow(o, (o[0] + 12 * s, o[1]), h_label)
        self._arrow(o, (o[0], o[1] + 12 * s), v_label)

    def north_arrow(self, c, r=5.0):
        s = self.scale
        self.circle("S-NOTES", c, r * s)
        self.hatch("S-NOTES", [(c[0], c[1] + r * s), (c[0] - 1.6 * s, c[1] - r * 0.6 * s), (c[0], c[1] - r * 0.25 * s)], solid=True)
        self.poly("S-NOTES", [(c[0], c[1] + r * s), (c[0] + 1.6 * s, c[1] - r * 0.6 * s), (c[0], c[1] - r * 0.25 * s)], closed=True)
        self.text("S-NOTES", (c[0], c[1] + (r + 3) * s), "N", h=3.5, align="MIDDLE_CENTER")

    def orientation(self, o):
        """Plan orientation block at o: north arrow, XY indicator and the grid-naming legend (footprint ~70 x 50 mm)."""
        s = self.scale
        self.north_arrow((o[0] + 6 * s, o[1] + 30 * s))
        self.axis_indicator((o[0] + 2 * s, o[1] + 4 * s))
        for i, t in enumerate(GRID_LEGEND):
            self.text("S-NOTES", (o[0], o[1] - (5 + 4.5 * i) * s), t, h=2.5)

    def grid(self, xs, ys, xl, yl, ext=None, dims=True):
        """Axis lines (CENTER) with bubbles at both ends and chained + overall dimensions on two sides."""
        ext = ext or 15.0 * self.scale
        r = 4.0 * self.scale
        x0, x1, y0, y1 = xs[0], xs[-1], ys[0], ys[-1]
        for x, lab in zip(xs, xl):
            self.line("S-AXIS", (x, y0 - ext), (x, y1 + ext))
            self.bubble((x, y0 - ext - r), lab)
            self.bubble((x, y1 + ext + r), lab)
        for y, lab in zip(ys, yl):
            self.line("S-AXIS", (x0 - ext, y), (x1 + ext, y))
            self.bubble((x0 - ext - r, y), lab)
            self.bubble((x1 + ext + r, y), lab)
        if dims:
            self.chain_dims(list(xs), y0, -(ext * 0.45), horizontal=True)
            self.chain_dims(list(ys), x0, -(ext * 0.45), horizontal=False)

    def level_mark(self, x, z, z_m: float, side=1):
        """Triangle level symbol with ±0.00 / +3.20 text."""
        s = 2.5 * self.scale
        self.poly("S-LEVEL", [(x, z), (x - s / 2 * side, z + s), (x + s / 2 * side, z + s)], closed=True)
        self.line("S-LEVEL", (x - s * side, z + s), (x + 5 * s * side, z + s))
        txt = "±0.00" if abs(z_m) < 1e-6 else f"{z_m:+.2f}"
        self.text("S-LEVEL", (x + 1.2 * s * side, z + 1.25 * s), txt, h=2.5, align="BOTTOM_LEFT" if side > 0 else "BOTTOM_RIGHT")

    def tag(self, pos, label, h=3.0):
        self.text("S-TAG", pos, label, h=h, align="MIDDLE_CENTER")

    def callout(self, target, at, text, h=2.5):
        """Bar callout such as 3Φ25 L=6200 with a leader from the bar to the text."""
        self.msp.add_leader([self.p(*target), self.p(*at), self.p(at[0] + 2 * self.scale, at[1])],
                            dxfattribs={"layer": "S-REBAR-TEXT"})
        self.text("S-REBAR-TEXT", (at[0] + 3 * self.scale, at[1]), text, h=h, align="MIDDLE_LEFT")

    def section_mark(self, a, b, label="A"):
        """Cut line with two heads and labels A ... A."""
        self.line("S-SECTION", a, b)
        for q in (a, b):
            self.circle("S-SECTION", q, 3.0 * self.scale)
            self.text("S-SECTION", q, label, h=3.0, align="MIDDLE_CENTER")

    def table(self, x, y_top, headers: Sequence[str], rows: Iterable[Sequence[Any]], widths: Sequence[float], title: str | None = None, rh=7.0):
        """Schedule table; widths/rh in paper mm. Returns the bottom y."""
        k = self.scale
        rows = [list(map(str, r)) for r in rows]
        W = sum(widths) * k
        y = y_top
        if title:
            self.text("S-TITLE", (x, y + 3 * k), title, h=4.0)
        allrows = [list(headers)] + rows
        for n, r in enumerate(allrows):
            self.rect("S-TABLE", x, y - rh * k, x + W, y)
            cx = x
            for w, cell in zip(widths, r):
                self.line("S-TABLE", (cx, y), (cx, y - rh * k))
                self.text("S-TABLE" if n else "S-TITLE", (cx + w * k / 2, y - rh * k / 2), cell, h=2.5 if n else 2.8, align="MIDDLE_CENTER")
                cx += w * k
            y -= rh * k
        return y

    def notes(self, x, y_top, title: str, lines: Sequence[str], h=2.5):
        self.text("S-TITLE", (x, y_top), title, h=4.0)
        for i, s in enumerate(lines):
            self.text("S-NOTES", (x, y_top - (i + 1.6) * 1.8 * h * self.scale), s, h=h)
        return y_top - (len(lines) + 2) * 1.8 * h * self.scale


def _hoop_path(x0, y0, x1, y1, r):
    """Closed hoop with bend radius r as (x, y, bulge) vertices (counter-clockwise)."""
    k = math.tan(math.pi / 8)  # bulge of a 90° arc
    return [(x0 + r, y0, 0), (x1 - r, y0, k), (x1, y0 + r, 0), (x1, y1 - r, k), (x1 - r, y1, 0), (x0 + r, y1, k),
            (x0, y1 - r, 0), (x0, y0 + r, k)]


def rc_section(pen: "Pen", ox: float, oy: float, b: float, h: float, cover: float, tie_d: float,
               bars: list[tuple[float, float, float]], groups: list[tuple[str, list[int]]], tie_label: str,
               cross_ties: list[tuple[tuple[float, float], tuple[float, float]]] = (), title: str = "A-A",
               title_fa: str | None = None, axes: str | None = None) -> tuple[float, float, float, float]:
    """Professional RC section (true scale, pen.scale = 20/25): light-hatched outline, closed hoop at the cover with
    135° hooks, filled bars at true diameter, cross-ties, b/h/cover dimensions, grouped callouts outside, title + scale.
    `bars` are (x, y, d) from the section's bottom-left corner. Returns the region (x0, y0, x1, y1) used."""
    s = pen.scale
    P = lambda x, y: (ox + x, oy + y)  # noqa: E731
    outline = [P(0, 0), P(b, 0), P(b, h), P(0, h)]
    pen.poly("S-CONC", outline, closed=True)
    pen.hatch("S-CONC-HATCH", outline, "ANSI31", pscale=s * 1.6)
    # hoop centre line at cover + tie_d/2, inner bend radius 2·tie_d
    c = cover + tie_d / 2
    r = 2 * tie_d + tie_d / 2
    hp = _hoop_path(ox + c, oy + c, ox + b - c, oy + h - c, r)
    pen.msp.add_lwpolyline([(pen.ox + x, pen.oy + y, 0, 0, bu) for x, y, bu in hp], format="xyseb", close=True,
                           dxfattribs={"layer": "S-REBAR-STIR", "const_width": tie_d * 0.9})
    hook = max(6 * tie_d, 75.0)
    tlx, tly = ox + c, oy + h - c  # 135° hooks at the top-left corner, both legs into the core
    ax, ay = tlx + r - r * 0.7071, tly - r + r * 0.7071  # 135° point of the corner bend
    for sgn in (-1, 1):  # two overlapping hook legs, one tie diameter apart, running diagonally into the core
        px, py = ax + sgn * tie_d * 0.5 * 0.7071, ay + sgn * tie_d * 0.5 * 0.7071
        pen.msp.add_lwpolyline([pen.p(px, py), pen.p(px + hook * 0.7071, py - hook * 0.7071)],
                               dxfattribs={"layer": "S-REBAR-STIR", "const_width": tie_d * 0.9})
    for (a, e) in cross_ties:
        ux, uy = e[0] - a[0], e[1] - a[1]
        ln = math.hypot(ux, uy) or 1.0
        ux, uy = ux / ln, uy / ln
        hk = hook * 0.5
        # 135° hooks: each end turns back into the core, legs on opposite sides of the tie
        A0 = (ox + a[0] + (ux - uy) * hk, oy + a[1] + (uy + ux) * hk)
        E0 = (ox + e[0] + (-ux + uy) * hk, oy + e[1] + (-uy - ux) * hk)
        pen.msp.add_lwpolyline([pen.p(*A0), pen.p(ox + a[0], oy + a[1]), pen.p(ox + e[0], oy + e[1]), pen.p(*E0)],
                               dxfattribs={"layer": "S-REBAR-STIR", "const_width": tie_d * 0.9})
    for x, y, d in bars:
        hh = pen.msp.add_hatch(color=LAYERS["S-REBAR-MAIN"][0], dxfattribs={"layer": "S-REBAR-MAIN"})
        hh.set_solid_fill(color=LAYERS["S-REBAR-MAIN"][0])
        hh.paths.add_edge_path().add_arc((pen.ox + ox + x, pen.oy + oy + y), d / 2, 0, 360)
        pen.circle("S-REBAR-MAIN", P(x, y), d / 2)
    # dimensions: b below, h left, cover right
    pen.dim(P(0, 0), P(b, 0), -10 * s)
    pen.dim(P(0, 0), P(0, h), 10 * s, angle=90)
    pen.dim(P(0, 0), P(0, cover), 4 * s, angle=90, text_at=oy - 5 * s)  # clear cover, text below the corner
    # grouped callouts on the right, stacked from the top, outside the section and the cover dimension
    tx = ox + b + 24 * s
    # each callout starts at the bar / hoop edge on the right (callout) side and runs horizontally out of the
    # section; any jog needed to stack the texts happens outside the concrete.
    rows = []
    for lab, idx in groups:
        bx, by, bd = max((bars[i] for i in idx), key=lambda q: (q[0], q[1]))
        rows.append((lab, (ox + bx + bd / 2, oy + by)))
    rows.append((tie_label, (ox + b - c + tie_d / 2, oy + h / 2)))
    rows.sort(key=lambda r: -r[1][1])
    gap, y = 9 * s, None
    for lab, (sx_, sy_) in rows:
        y = sy_ if y is None else min(sy_, y)
        pts = [pen.p(sx_, sy_), pen.p(ox + b + 4 * s, sy_)]
        if abs(y - sy_) > 1:
            pts.append(pen.p(ox + b + 8 * s, y))
        pts.append(pen.p(tx - 1 * s, y))
        pen.msp.add_lwpolyline(pts, dxfattribs={"layer": "S-REBAR-TEXT"})
        pen.circle("S-REBAR-TEXT", (sx_, sy_), 0.6 * s)  # leader dot on the bar
        first, *more = lab.split(" + ")
        pen.text("S-REBAR-TEXT", (tx, y), first, h=3.0, align="MIDDLE_LEFT")
        for m in more:
            y -= 5 * s
            pen.text("S-REBAR-TEXT", (tx, y), "+ " + m, h=3.0, align="MIDDLE_LEFT")
        y -= gap
    # title + scale underneath
    pen.text("S-TITLE", (ox + b / 2, oy - 17 * s), f"SECTION {title}", h=4.0, align="TOP_CENTER")
    pen.text("S-TITLE", (ox + b / 2, oy - 23.5 * s), title_fa or f"برش {title}", h=3.5, align="TOP_CENTER")
    pen.text("S-NOTES", (ox + b / 2, oy - 29 * s), f"1:{s}" + (f"   ({axes})" if axes else ""), h=2.5, align="TOP_CENTER")
    return (ox - 22 * s, oy - 33 * s, tx + 45 * s, max(oy + h + 6 * s, oy + h))


def choose_sheet(width_mm: float, height_mm: float) -> tuple[str, int]:
    """Smallest paper/scale that fits the model region (drawing area excludes the title strip)."""
    for paper in ("A3", "A1"):
        pw, ph = PAPER[paper]
        aw, ah = pw - 30 - 10, ph - 20 - 55  # margins + title-block strip
        for s in (50, 100, 200):
            if width_mm / s <= aw and height_mm / s <= ah:
                return paper, s
    return "A1", 200


def add_sheet(doc, name: str, extents: tuple[float, float, float, float], info: TitleInfo, sheet_no: str,
              title_fa: str, title_en: str, paper: str | None = None, scale: int | None = None) -> Any:
    """Paper-space layout with border, title block, revision table, logo box and a viewport on `extents`."""
    x0, y0, x1, y1 = extents
    # model-space sheet marker (frozen-free tiny text) so the in-app viewer can offer a sheet selector
    doc.modelspace().add_text(f"{name}|{x0:.0f}|{x1:.0f}|{title_en}", height=1, dxfattribs={"layer": "S-SHEET", "insert": (x0, y0)})
    if scale is not None and paper is None:  # annotation was sized for this scale: pick the paper that fits it
        paper = next((p_ for p_ in ("A3", "A1") if (x1 - x0) / scale <= PAPER[p_][0] - 40 and (y1 - y0) / scale <= PAPER[p_][1] - 30 - 75), "A1")
    if paper is None or scale is None:
        paper, scale = choose_sheet(x1 - x0, y1 - y0)
    pw, ph = PAPER[paper]
    lay = doc.layouts.new(name)
    lay.page_setup(size=(pw, ph), margins=(0, 0, 0, 0), units="mm")
    ps = Pen(lay, scale=1)
    ps.rect("S-BORDER", 20, 10, pw - 10, ph - 10)  # 20 mm binding margin
    ps.rect("S-TITLEBLOCK", 5, 5, pw - 5, ph - 5)
    # title strip along the bottom right
    tw, th = 180.0, 52.0
    tx, ty = pw - 10 - tw, 10.0
    ps.rect("S-TITLEBLOCK", tx, ty, tx + tw, ty + th)
    rows = [("Project / پروژه", info.project), ("Employer / کارفرما", info.employer), ("Designer / طراح", info.designer),
            ("Checker / کنترل", info.checker), ("Drawing / عنوان نقشه", f"{title_en}"), ("", title_fa)]
    rh = th / (len(rows) + 1)
    for i, (k, v) in enumerate(rows):
        yy = ty + th - (i + 1) * rh
        ps.line("S-TITLEBLOCK", (tx + 40, yy), (tx + tw, yy))
        ps.text("S-TITLEBLOCK", (tx + 42, yy + rh / 2), k, h=1.8, align="MIDDLE_LEFT")
        ps.text("S-TITLEBLOCK", (tx + 82, yy + rh / 2), v, h=2.2, align="MIDDLE_LEFT")
    ps.line("S-TITLEBLOCK", (tx + 80, ty + rh), (tx + 80, ty + th))
    ps.line("S-TITLEBLOCK", (tx + 40, ty), (tx + 40, ty + th))
    cells = [("Scale / مقیاس", f"1:{scale}"), ("Date / تاریخ", info.drawing_date), ("Sheet / شماره", sheet_no), ("Paper", paper)]
    cw = (tw - 40) / len(cells)
    for i, (k, v) in enumerate(cells):
        cx = tx + 40 + i * cw
        ps.line("S-TITLEBLOCK", (cx, ty), (cx, ty + rh))
        ps.text("S-TITLEBLOCK", (cx + 1.5, ty + rh * 0.72), k, h=1.4, align="MIDDLE_LEFT")
        ps.text("S-TITLEBLOCK", (cx + 1.5, ty + rh * 0.3), v, h=2.0, align="MIDDLE_LEFT")
    # logo placeholder
    ps.rect("S-TITLEBLOCK", tx + 3, ty + 3, tx + 37, ty + th - 3)
    ps.text("S-TITLEBLOCK", (tx + 20, ty + th / 2 + 3), "LOGO", h=3.5, align="MIDDLE_CENTER")
    ps.text("S-TITLEBLOCK", (tx + 20, ty + th / 2 - 4), "محل آرم", h=2.5, align="MIDDLE_CENTER")
    # revision table above the title strip
    ry = ty + th
    rv = [("Rev", "Date / تاریخ", "Description / شرح")] + list(info.revisions)
    rw = (12, 30, tw - 42)
    for i, r in enumerate(reversed(rv)):
        y_ = ry + i * 6
        ps.rect("S-TITLEBLOCK", tx, y_, tx + tw, y_ + 6)
        cx = tx
        for w, c in zip(rw, r):
            ps.line("S-TITLEBLOCK", (cx, y_), (cx, y_ + 6))
            ps.text("S-TITLEBLOCK", (cx + 1.5, y_ + 3), c, h=1.8, align="MIDDLE_LEFT")
            cx += w
    ps.text("S-TITLEBLOCK", (tx, ty - 3.5), f"Code: {info.code} — generated by SAIA, check before construction / قبل از اجرا کنترل شود", h=1.6)
    # viewport
    aw, ah = pw - 30 - 10, ph - 20 - 10 - (th + 6 * len(rv) + 4)
    vy0 = 10 + th + 6 * len(rv) + 4
    vp = lay.add_viewport(center=(20 + 5 + aw / 2, vy0 + ah / 2), size=(aw, ah),
                          view_center_point=((x0 + x1) / 2, (y0 + y1) / 2), view_height=ah * scale,
                          dxfattribs={"layer": "S-VIEWPORT"})
    vp.dxf.status = 1
    lay.dxf.name  # noqa: B018 - touch
    return lay


def add_sheet_tiles(doc, name: str, extents, info: TitleInfo, title_fa: str, title_en: str, scale: int, paper: str = "A1") -> list[str]:
    """Keep the true scale: split a tall/wide region into as many sheets of `paper` as needed (R-01, R-01.2, ...)."""
    x0, y0, x1, y1 = extents
    pw, ph = PAPER[paper]
    aw, ah = (pw - 40) * scale, (ph - 30 - 75) * scale * 0.98
    nx, ny = max(1, math.ceil((x1 - x0) / aw)), max(1, math.ceil((y1 - y0) / ah))
    names = []
    for j in range(ny):
        for i in range(nx):
            n = name if i == j == 0 else f"{name}.{j * nx + i + 1}"
            tile = (x0 + i * aw, y1 - (j + 1) * ah, min(x1, x0 + (i + 1) * aw), y1 - j * ah)
            add_sheet(doc, n, tile, info, n, title_fa, title_en, paper=paper, scale=scale)
            names.append(n)
    return names


def audit(doc) -> int:
    """Number of errors reported by ezdxf's auditor (0 expected)."""
    return len(doc.audit().errors)
