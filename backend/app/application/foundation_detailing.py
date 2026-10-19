"""Foundation detailing sheet set (FD-01 plan + schedule, FD-02 sections + bending schedule), office drawing standard.

Uses the Mabhas 9 footing design (flexure at the column face, one-way and punching shear) from foundation_design and
the project's foundation assumptions (footing cover, Df, lean concrete, bar list) from the generic registry.
"""

from __future__ import annotations

import io
import math
from typing import Any

from app.application import detailing_assumptions as da
from app.application import drawing_standard as ds
from app.application.csi_text_export import _x_label, _y_label, frame_layout

TAG = {"corner": "F1", "edge": "F2", "interior": "F3"}
FA = {"corner": "گوشه", "edge": "کناری", "interior": "میانی"}


def unit_weight(d: float) -> float:
    return d * d / 162.0


def _r10(x: float) -> int:
    return int(math.ceil(x / 10.0) * 10)


def bending_rows(fd: dict[str, Any], inp, A: dict[str, Any], column_bars: dict[str, str]) -> list[dict[str, Any]]:
    """Bar marks per footing type: bottom mesh both ways + column starter bars with 90° hooks."""
    from app.application.rebar_detailing import lap_length, parse_bars

    cover = float(A["footing_cover_mm"])
    rows = []
    for r in fd["rows"]:
        if r.get("status") != "PASS":
            continue
        tag, B, h, db, s = TAG[r["position"]], r["B_m"] * 1000, r["h_m"] * 1000, int(r["db"]), int(r["s_mm"])
        n = int((B - 2 * cover) // s) + 1
        L = _r10(B - 2 * cover + 2 * 12 * db)  # 90° end hooks 12db up the sides
        for way in ("X", "Y"):
            rows.append({"mark": f"{tag}-{way}", "tag": tag, "d": db, "shape": "U (90° hooks)", "length": L, "count": n * r["members"]})
        nb, dbc = parse_bars(column_bars.get(r["position"], "8Φ16"))
        lap = lap_length(dbc, inp.fy_mpa, inp.fc_mpa, False, A["splice_class"], A["psi_t"], A["ld_factor"])
        df = float(A["footing_depth_m"]) * 1000
        Ls = _r10((h - cover - 2 * db) + (df - h) + lap + 12 * dbc)
        rows.append({"mark": f"{tag}-S", "tag": tag, "d": dbc, "shape": "L starter (90° hook)", "length": Ls, "count": nb * r["members"],
                     "lap": lap})
    for row in rows:
        row["weight"] = round(row["length"] / 1000 * row["count"] * unit_weight(row["d"]), 1)
    return rows


def build_foundation_doc(inp, raw: dict[str, Any], design: dict[str, Any] | None = None, info: ds.TitleInfo | None = None):
    fd = (raw or {}).get("foundation_design")
    if not fd or not fd.get("footings"):
        raise ValueError("foundation detailing needs the footing design (ask for 'foundation' in the frame request)")
    A = da.effective(getattr(inp, "assumptions", None))
    info = info or ds.TitleInfo(project="3D RC frame")
    doc = ds.new_document()
    msp = doc.modelspace()
    lay = frame_layout(inp)
    XS, YS = [x * 1000 for x in lay["XS"]], [y * 1000 for y in lay["YS"]]
    W, H = XS[-1], YS[-1]
    nx, ny = inp.bays_x, inp.bays_y
    cb, ch = inp.column_b_m * 1000, inp.column_h_m * 1000
    cover, lean, df = float(A["footing_cover_mm"]), float(A["lean_concrete_mm"]), float(A["footing_depth_m"]) * 1000
    rows = {r["position"]: r for r in fd["rows"] if r.get("status") == "PASS"}
    colbars = {}
    for c in (design or {}).get("columns", []):
        if c["storey"] == 1:
            colbars[c["position"]] = c["bars"]
    scale = ds.choose_sheet(W + 9000, H + 9000)[1]

    # ---------------------------------------------------------------- FD-01: plan with tags, dims to axes, schedule
    pen = ds.Pen(msp, (0, 0), scale)
    bmax = max(f["B_m"] for f in fd["footings"]) * 1000
    ext = max(15 * scale, bmax / 2 + 10 * scale)
    pen.grid(XS, YS, [_x_label(i) for i in range(nx + 1)], [_y_label(j) for j in range(ny + 1)], ext=ext)
    dimmed = set()
    for f in fd["footings"]:
        x, y, B = f["x"] * 1000, f["y"] * 1000, f["B_m"] * 1000
        pts = [(x - B / 2, y - B / 2), (x + B / 2, y - B / 2), (x + B / 2, y + B / 2), (x - B / 2, y + B / 2)]
        pen.poly("S-FOOT", pts, closed=True)
        pen.hatch("S-FOOT-HATCH", pts, "AR-CONC", pscale=scale / 12)
        pen.rect("S-CONC", x - cb / 2, y - ch / 2, x + cb / 2, y + ch / 2)
        pen.tag((x + B / 4, y - B / 4), TAG[f["position"]], h=3)
        if f["position"] not in dimmed:  # dimensions from the axis to both footing edges, once per type
            dimmed.add(f["position"])
            pen.dim((x - B / 2, y + B / 2), (x, y + B / 2), 4 * scale)
            pen.dim((x, y + B / 2), (x + B / 2, y + B / 2), 4 * scale)
            pen.dim((x + B / 2, y - B / 2), (x + B / 2, y), -4 * scale, angle=90)
            pen.dim((x + B / 2, y), (x + B / 2, y + B / 2), -4 * scale, angle=90)
    sched = [(TAG[p], f"{FA[p]} / {p}", f"{r['B_m'] * 1000:.0f}x{r['B_m'] * 1000:.0f}", f"{r['h_m'] * 1000:.0f}",
              f"Φ{r['db']}@{r['s_mm']}", f"Φ{r['db']}@{r['s_mm']}", str(r["members"])) for p, r in rows.items()]
    tx = W + ext + 15 * scale
    pen.table(tx, H, ("Tag", "Type / نوع", "B x L (mm)", "h (mm)", "Bottom X", "Bottom Y", "No."), sched, (14, 30, 28, 16, 24, 24, 10),
              title="FOOTING SCHEDULE / جدول پی‌ها")
    pen.text("S-TITLE", (W / 2, -ext - 12 * scale), "FOUNDATION PLAN / پلان فونداسیون", h=5, align="TOP_CENTER")
    pen.text("S-NOTES", (W / 2, -ext - 20 * scale), f"qa = {fd['qa_kpa']:g} kPa{' (assumed)' if fd['qa_assumed'] else ''} · Df = {df / 1000:g} m · Mabhas 9 footing design", h=2.5, align="TOP_CENTER")
    tx = W + ext + 15 * scale
    ds.add_sheet(doc, "FD-01", (-ext - 10 * scale, -ext - 26 * scale, tx + 160 * scale, H + ext + 10 * scale), info, "FD-01", "پلان و جدول پی‌ها", "FOUNDATION PLAN & SCHEDULE", scale=scale)

    # ---------------------------------------------------------------- FD-02: sections per type + bending schedule
    s2 = 25  # footing sections at 1:25
    ox0 = tx + 400 * scale + 20000
    pen = ds.Pen(msp, (ox0, 0), s2)
    x = 0.0
    from app.application.rebar_detailing import parse_bars

    brow = bending_rows(fd, inp, A, colbars)
    top = 0.0
    for p, r in rows.items():
        B, h, db = r["B_m"] * 1000, r["h_m"] * 1000, int(r["db"])
        nb, dbc = parse_bars(colbars.get(p, "8Φ16"))
        lap = next((b["lap"] for b in brow if b["mark"] == f"{TAG[p]}-S"), 40 * dbc)
        base = 0.0  # underside of footing
        # lean concrete, footing, column stub up to above ground
        pen.rect("S-CONC", x - B / 2 - 100, base - lean, x + B / 2 + 100, base)
        pen.hatch("S-CONC-HATCH", [(x - B / 2 - 100, base - lean), (x + B / 2 + 100, base - lean), (x + B / 2 + 100, base), (x - B / 2 - 100, base)], "AR-SAND", pscale=1)
        fpts = [(x - B / 2, base), (x + B / 2, base), (x + B / 2, base + h), (x - B / 2, base + h)]
        pen.poly("S-FOOT", fpts, closed=True)
        pen.hatch("S-FOOT-HATCH", fpts, "ANSI31", pscale=s2 * 1.6)  # light section hatch
        top_col = df + lap + 400
        pen.poly("S-CONC", [(x - cb / 2, base + h), (x - cb / 2, top_col), (x + cb / 2, top_col), (x + cb / 2, base + h)])
        pen.line("S-CONC-HIDDEN", (x - B / 2 - 600, df), (x + B / 2 + 600, df))  # natural ground / ±0.00
        # bottom mesh: bars along the section as a line with 90° hooks, the other way as dots
        yb = base + cover + db / 2
        pen.poly("S-REBAR-MAIN", [(x - B / 2 + cover, base + h - cover), (x - B / 2 + cover, yb), (x + B / 2 - cover, yb), (x + B / 2 - cover, base + h - cover)])
        n = int((B - 2 * cover) // r["s_mm"]) + 1
        for k in range(n):
            pen.circle("S-REBAR-MAIN", (x - B / 2 + cover + k * r["s_mm"], yb + db), db / 2)
        # column starter bars with 90° hooks resting on the mesh
        for sx in (-1, 1):
            xb = x + sx * (cb / 2 - 40 - dbc / 2)
            ys = yb + 2 * db
            pen.poly("S-REBAR-MAIN", [(xb - sx * 12 * dbc, ys), (xb, ys), (xb, df + lap)])
        pen.dim((x - B / 2, base - lean - 300), (x + B / 2, base - lean - 300), -2 * s2)
        pen.dim((x + B / 2, base), (x + B / 2, base + h), -6 * s2, angle=90)
        pen.dim((x + cb / 2 + 200, df), (x + cb / 2 + 200, df + lap), -4 * s2, angle=90)
        pen.dim((x - B / 2, base), (x - B / 2, base + cover), 5 * s2, angle=90)  # bottom cover
        pen.level_mark(x + B / 2 + 400, df, 0.0)
        pen.level_mark(x + B / 2 + 400, base, -df / 1000)
        pen.callout((x, yb), (x + B / 4, base - lean - 900), f"Φ{db}@{r['s_mm']} L={_r10(B - 2 * cover + 24 * db)} (each way)")
        pen.callout((x + cb / 2 - 60, df + lap / 2), (x + cb / 2 + 700, df + lap * 0.8), f"{nb}Φ{dbc} starter, 90° hook 12Φ, lap {lap}")
        pen.text("S-NOTES", (x - B / 2 - 100, base - lean - 120), f"lean concrete {lean:.0f} / بتن مگر", h=2.0, align="TOP_LEFT")
        pen.text("S-TITLE", (x, base - lean - 1000), f"SECTION {TAG[p]}-{TAG[p]}  ({p})", h=4, align="TOP_CENTER")
        pen.text("S-TITLE", (x, base - lean - 1000 - 6.5 * s2), f"برش {TAG[p]}-{TAG[p]}", h=3.5, align="TOP_CENTER")
        pen.text("S-NOTES", (x, base - lean - 1000 - 12 * s2), f"1:{s2}", h=2.5, align="TOP_CENTER")
        top = max(top, top_col)
        x += B + 3500
    y = -lean - 3000
    table_rows = [(b["mark"], f"Φ{b['d']}", b["shape"], b["length"], b["count"], f"{b['weight']:.1f}") for b in brow]
    total = round(sum(b["weight"] for b in brow), 1)
    table_rows.append(("", "", "TOTAL / وزن کل", "", "", f"{total:.1f}"))
    yb_ = pen.table(0, y - 4000, ("Mark", "Φ (mm)", "Shape / شکل", "Length (mm)", "Count", "Weight (kg)"), table_rows,
                    (22, 16, 44, 24, 16, 24), title="BAR BENDING SCHEDULE - FOOTINGS / جدول وزن میلگرد پی")
    pen.notes(x * 0.55, y - 4000, "GENERAL NOTES / یادداشت‌های عمومی", [
        f"Concrete C{inp.fc_mpa:g}, rebar S{inp.fy_mpa:g}; bottom cover {cover:.0f} mm; lean concrete {lean:.0f} mm.",
        "Footings designed to Mabhas 9: flexure at the column face, one-way shear at d, punching at d/2.",
        f"Founding depth Df = {df / 1000:g} m; allowable bearing qa = {fd['qa_kpa']:g} kPa.",
        "پوشش، عمق پی و بتن مگر از گفتگو قابل تغییر است.",
    ])
    ds.add_sheet_tiles(doc, "FD-02", (ox0 - 3000, yb_ - 2000, ox0 + x + 2000, top + 1500), info,
                       "مقاطع و جدول میلگرد پی", "FOOTING SECTIONS & BENDING SCHEDULE", scale=s2)
    return doc, brow, total


def build_dxf_foundation(inp, raw: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    doc, _, _ = build_foundation_doc(inp, raw, design)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue()
