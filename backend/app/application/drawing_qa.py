"""Automated drawing QA: text-over-text and text-over-line detection on every sheet of a DXF document.

Text boxes are estimated from the TTF style metrics (Arial/Tahoma average advance ≈ 0.56·h per glyph, 0.5·h for
Persian presentation forms) and the entity's alignment; dimension texts are taken from the rendered dimension blocks.
A text overlaps a line when a segment crosses its box shrunk by 5 % (touching box edges is allowed).
"""

from __future__ import annotations

import math
from typing import Any, Iterable

Box = tuple[float, float, float, float]

_H = {0: 0.0, 1: 0.5, 2: 1.0, 4: 0.5}          # halign -> fraction of width left of the insert
_V = {0: 0.0, 1: 0.0, 2: 0.5, 3: 1.0}          # valign -> fraction of height below the insert (baseline=0)


def _width(s: str, h: float) -> float:
    w = 0.0
    for ch in s:
        if ch == " ":
            w += 0.3 * h
        elif "\ufb50" <= ch <= "\ufeff" or "\u0600" <= ch <= "\u06ff":
            w += 0.5 * h
        elif ch in "il.,:;|'1":
            w += 0.3 * h
        elif ch.isupper() or ch in "mwMWΦ@%":
            w += 0.72 * h
        else:
            w += 0.56 * h
    return w


def _text_box(e) -> tuple[Box, str, float] | None:
    t = e.dxftype()
    if t == "TEXT":
        s, h = e.dxf.text, e.dxf.height
        if not s.strip() or abs(e.dxf.get("rotation", 0)) % 180 not in (0, 0.0) and abs(abs(e.dxf.get("rotation", 0)) - 90) > 1e-6:
            pass
        ha, va = e.dxf.get("halign", 0), e.dxf.get("valign", 0)
        p = e.dxf.align_point if (ha or va) and e.dxf.hasattr("align_point") else e.dxf.insert
        w = _width(s, h)
        x0 = p[0] - _H.get(ha, 0) * w
        y0 = p[1] - _V.get(va, 0) * h - (0.2 * h if va == 0 else 0)
        box = (x0, y0, x0 + w, y0 + h * 1.2)
        rot = round(e.dxf.get("rotation", 0)) % 360
        if rot in (90, 270):  # rotate about the anchor
            ax, ay = p[0], p[1]
            bx = [(ax - (yy - ay), ay + (xx - ax)) for xx, yy in ((box[0], box[1]), (box[2], box[3]))]
            box = (min(b[0] for b in bx), min(b[1] for b in bx), max(b[0] for b in bx), max(b[1] for b in bx))
        return box, s, h
    if t == "MTEXT":
        s, h = e.plain_text(), e.dxf.char_height
        w = _width(s, h)
        p = e.dxf.insert
        ap = e.dxf.get("attachment_point", 1)
        fx = {1: 0, 2: 0.5, 3: 1}[(ap - 1) % 3 + 1]
        fy = {1: 1, 2: 0.5, 3: 0}[(ap - 1) // 3 + 1]
        x0, y0 = p[0] - fx * w, p[1] - fy * h
        box = (x0, y0, x0 + w, y0 + h)
        rot = round(math.degrees(math.atan2(e.dxf.text_direction[1], e.dxf.text_direction[0])) if e.dxf.hasattr("text_direction") else e.dxf.get("rotation", 0)) % 180
        if rot == 90:
            cx, cy = p[0], p[1]
            pts = [(cx - (yy - cy), cy + (xx - cx)) for xx, yy in ((box[0], box[1]), (box[2], box[3]))]
            box = (min(q[0] for q in pts), min(q[1] for q in pts), max(q[0] for q in pts), max(q[1] for q in pts))
        return box, s, h
    return None


def _segments(e) -> Iterable[tuple[tuple[float, float], tuple[float, float]]]:
    t = e.dxftype()
    if t == "LINE":
        yield (e.dxf.start[0], e.dxf.start[1]), (e.dxf.end[0], e.dxf.end[1])
    elif t == "LWPOLYLINE":
        pts = [(p[0], p[1]) for p in e.get_points("xy")]
        if e.closed and pts:
            pts.append(pts[0])
        yield from zip(pts, pts[1:])


def _shrink(b: Box, f: float = 0.05) -> Box:
    dx, dy = (b[2] - b[0]) * f, (b[3] - b[1]) * f
    return (b[0] + dx, b[1] + dy, b[2] - dx, b[3] - dy)


def _overlap(a: Box, b: Box) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def _seg_hits_box(p, q, b: Box) -> bool:
    # Liang–Barsky clip
    x0, y0, x1, y1 = b
    dx, dy = q[0] - p[0], q[1] - p[1]
    t0, t1 = 0.0, 1.0
    for pp, qq in ((-dx, p[0] - x0), (dx, x1 - p[0]), (-dy, p[1] - y0), (dy, y1 - p[1])):
        if pp == 0:
            if qq < 0:
                return False
        else:
            r = qq / pp
            if pp < 0:
                t0 = max(t0, r)
            else:
                t1 = min(t1, r)
            if t0 > t1:
                return False
    return True


def collect(doc, skip_layers=("S-SHEET",)) -> tuple[list[tuple[Box, str, str]], list[tuple[Any, Any, str]]]:
    texts, segs = [], []
    msp = doc.modelspace()

    def visit(e, layer=None):
        lay = layer or e.dxf.layer
        if lay in skip_layers:
            return
        if e.dxftype() == "DIMENSION":
            for v in e.virtual_entities():
                visit(v, lay)
            return
        tb = _text_box(e)
        if tb:
            texts.append((tb[0], tb[1], lay, tb[2]))
            return
        for s in _segments(e):
            segs.append((s[0], s[1], lay))

    for e in msp:
        visit(e)
    return texts, segs


def find_issues(doc, ignore_line_layers: Iterable[str] = ("S-CONC-HATCH", "S-FOOT-HATCH", "CONC_HATCH")) -> list[str]:
    """Text-over-text and text-over-line clashes in model space (all sheets)."""
    texts, segs = collect(doc)
    ign = set(ignore_line_layers)
    issues = []
    boxes = [(_shrink(b), s, l) for b, s, l, _h in texts]
    order = sorted(range(len(boxes)), key=lambda i: boxes[i][0][0])
    for n, i in enumerate(order):  # sweep on x
        bi = boxes[i][0]
        for j in order[n + 1:]:
            bj = boxes[j][0]
            if bj[0] >= bi[2]:
                break
            if _overlap(bi, bj):
                issues.append(f"text/text: {boxes[i][1]!r} x {boxes[j][1]!r}")
    # grid for segments
    cell = 2000.0
    grid: dict[tuple[int, int], list[int]] = {}
    for k, (p, q, lay) in enumerate(segs):
        if lay in ign:
            continue
        for gx in range(int(math.floor(min(p[0], q[0]) / cell)), int(math.floor(max(p[0], q[0]) / cell)) + 1):
            for gy in range(int(math.floor(min(p[1], q[1]) / cell)), int(math.floor(max(p[1], q[1]) / cell)) + 1):
                grid.setdefault((gx, gy), []).append(k)
    for b, s, lay in boxes:
        seen = set()
        for gx in range(int(math.floor(b[0] / cell)), int(math.floor(b[2] / cell)) + 1):
            for gy in range(int(math.floor(b[1] / cell)), int(math.floor(b[3] / cell)) + 1):
                for k in grid.get((gx, gy), ()):
                    if k in seen:
                        continue
                    seen.add(k)
                    p, q, l2 = segs[k]
                    if _seg_hits_box(p, q, b):
                        issues.append(f"text/line: {s!r} ({lay}) x line on {l2} @ ({b[0]:.0f},{b[1]:.0f}) seg {p[0]:.0f},{p[1]:.0f}-{q[0]:.0f},{q[1]:.0f}")
    return issues


def sheet_issues(doc, min_text_mm: float = 1.8) -> list[str]:
    """Per paper-space sheet: the viewport scale must be a standard one and every text in it must be readable."""
    texts, _ = collect(doc)
    issues = []
    for lay in doc.layouts:
        if lay.name == "Model":
            continue
        for vp in lay.query("VIEWPORT"):
            if vp.dxf.get("status", 0) == 1 and vp.dxf.width > 1 and vp.dxf.height > 1:
                scale = vp.dxf.view_height / vp.dxf.height
                cx, cy = vp.dxf.view_center_point[0], vp.dxf.view_center_point[1]
                hw, hh = vp.dxf.width * scale / 2, vp.dxf.height * scale / 2
                if round(scale) not in (1, 20, 25, 50, 100, 200):
                    issues.append(f"{lay.name}: non-standard scale 1:{scale:.1f}")
                for b, txt, l, h in texts:
                    if cx - hw <= b[0] <= cx + hw and cy - hh <= b[1] <= cy + hh:
                        if h / scale < min_text_mm * 0.98 and len(txt) > 0:
                            issues.append(f"{lay.name}: text {txt!r} is {h / scale:.2f} mm on paper")
    return issues
