"""Generic DXF modelspace -> SVG preview (works for every sheet type)."""
from __future__ import annotations

import io
import math
from html import escape

COLORS = {1: "#d33", 2: "#b8860b", 3: "#2a2", 4: "#0aa", 5: "#33c", 6: "#a3a", 7: "#111", 8: "#888", 94: "#2a6"}


def dxf_to_svg(doc, max_px: int = 1200) -> str:
    msp = doc.modelspace()
    items, xs, ys = [], [], []

    def col(e):
        layer = doc.layers.get(e.dxf.layer)
        return COLORS.get(abs(layer.color) if layer else 7, "#111")

    for e in msp:
        t = e.dxftype()
        if t == "LINE":
            s, n = e.dxf.start, e.dxf.end
            items.append(("l", (s.x, s.y, n.x, n.y), col(e))); xs += [s.x, n.x]; ys += [s.y, n.y]
        elif t == "LWPOLYLINE":
            pts = [(p[0], p[1]) for p in e.get_points()]
            if e.closed and pts:
                pts.append(pts[0])
            items.append(("p", pts, col(e))); xs += [p[0] for p in pts]; ys += [p[1] for p in pts]
        elif t in ("CIRCLE", "ARC"):
            c, r = e.dxf.center, e.dxf.radius
            a0, a1 = (0, 360) if t == "CIRCLE" else (e.dxf.start_angle, e.dxf.end_angle)
            if a1 < a0:
                a1 += 360
            pts = [(c.x + r * math.cos(math.radians(a0 + (a1 - a0) * i / 24)), c.y + r * math.sin(math.radians(a0 + (a1 - a0) * i / 24))) for i in range(25)]
            items.append(("p", pts, col(e))); xs += [c.x - r, c.x + r]; ys += [c.y - r, c.y + r]
        elif t == "TEXT":
            p = e.dxf.insert
            items.append(("t", (p.x, p.y, e.dxf.height, e.dxf.text), col(e))); xs.append(p.x); ys.append(p.y)
    if not xs:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"></svg>'
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    w, h = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    s = max_px / max(w, h)
    W, H = w * s + 20, h * s + 20
    X = lambda x: 10 + (x - x0) * s
    Y = lambda y: 10 + (y1 - y) * s
    out = io.StringIO()
    out.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W:.0f} {H:.0f}" style="background:#fff">')
    for kind, g, c in items:
        if kind == "l":
            out.write(f'<line x1="{X(g[0]):.1f}" y1="{Y(g[1]):.1f}" x2="{X(g[2]):.1f}" y2="{Y(g[3]):.1f}" stroke="{c}" stroke-width="1.2"/>')
        elif kind == "p":
            pts = " ".join(f"{X(a):.1f},{Y(b):.1f}" for a, b in g)
            out.write(f'<polyline points="{pts}" fill="none" stroke="{c}" stroke-width="1.2"/>')
        else:
            out.write(f'<text x="{X(g[0]):.1f}" y="{Y(g[1]):.1f}" font-size="{max(g[2] * s, 6):.1f}" fill="{c}" font-family="sans-serif">{escape(str(g[3]))}</text>')
    out.write("</svg>")
    return out.getvalue()
