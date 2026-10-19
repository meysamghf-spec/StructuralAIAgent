"""Professional general-arrangement drawings (plans, foundation, elevations, schedules) using drawing_standard.

Sheets (one paper-space layout each, model space in mm):
  S-0k  story plan k: axes with bubbles on both ends, chained + overall dimensions, hatched column sections with
        tags C1.., beams (dashed, under the slab) with tags B1.. and sizes;
  S-10  column schedule and beam schedule tables (sizes + Mabhas 9 reinforcement when designed);
  S-F1  foundation plan: hatched footings with tags F1.., footing dimensions, footing schedule;
  E-xx  elevations per grid line with level marks (±0.00, +3.20 ...) and storey dimensions.
"""

from __future__ import annotations

import io
from typing import Any

from app.application import drawing_standard as ds
from app.application.csi_text_export import _x_label, _y_label, frame_layout

POS_TAG = {"corner": "C1", "edge": "C2", "interior": "C3"}
POS_FA = {"corner": "گوشه", "edge": "کناری", "interior": "میانی"}
FTG_TAG = {"corner": "F1", "edge": "F2", "interior": "F3"}


def _pos(i, j, nx, ny) -> str:
    return "corner" if (i in (0, nx) and j in (0, ny)) else "edge" if (i in (0, nx) or j in (0, ny)) else "interior"


def _beam_tag(direction: str, edge: bool) -> str:
    return {("X", True): "B1", ("X", False): "B2", ("Y", True): "B3", ("Y", False): "B4"}[(direction, edge)]


def build_structural_doc(inp, raw: dict[str, Any], design: dict[str, Any] | None = None, info: ds.TitleInfo | None = None):
    info = info or ds.TitleInfo(project=getattr(inp, "project_name", None) or "3D RC frame")
    doc = ds.new_document()
    msp = doc.modelspace()
    lay = frame_layout(inp)
    XS = [x * 1000 for x in lay["XS"]]
    YS = [y * 1000 for y in lay["YS"]]
    Z = [z * 1000 for z in lay["Z"]]
    nx, ny, ns = inp.bays_x, inp.bays_y, inp.storeys
    cb, ch = inp.column_b_m * 1000, inp.column_h_m * 1000
    bb, bh = inp.beam_b_m * 1000, inp.beam_h_m * 1000
    xl, yl = [_x_label(i) for i in range(nx + 1)], [_y_label(j) for j in range(ny + 1)]
    W, H = XS[-1], YS[-1]
    cols = {(c["storey"], c["position"]): c for c in (design or {}).get("columns", [])}
    beams = {(b["storey"], b["direction"], b["position"]): b for b in (design or {}).get("beams", [])}
    sheets: list[tuple[str, tuple, str, str]] = []
    scale = ds.choose_sheet(W + 9000, H + 9000)[1]
    pitch = max(W, H, Z[-1]) + 420 * scale
    slot = [0]

    def region() -> ds.Pen:
        pen = ds.Pen(msp, (slot[0] * pitch, 0.0), scale)
        slot[0] += 1
        return pen

    def ext(pen, x0, y0, x1, y1):
        return (pen.ox + x0, pen.oy + y0, pen.ox + x1, pen.oy + y1)

    m = 22 * scale  # annotation margin around a plan (bubbles + dims)

    # ---------------------------------------------------------------- story plans
    for k in range(1, ns + 1):
        pen = region()
        pen.grid(XS, YS, xl, yl)
        for i, x in enumerate(XS):
            for j, y in enumerate(YS):
                pts = [(x - cb / 2, y - ch / 2), (x + cb / 2, y - ch / 2), (x + cb / 2, y + ch / 2), (x - cb / 2, y + ch / 2)]
                pen.poly("S-CONC", pts, closed=True)
                pen.hatch("S-CONC-HATCH", pts, "ANSI31", pscale=scale / 8)
                pen.tag((x + cb / 2 + 3 * scale, y + ch / 2 + 2.5 * scale), POS_TAG[_pos(i, j, nx, ny)], h=2.8)
        for _name, mid, _a, _b, dirn in lay["lines"]:
            i, j = (int(v) for v in mid[2:].split("_"))
            if dirn == "X":
                a, b_ = XS[i] + cb / 2, XS[i + 1] - cb / 2
                y = YS[j]
                pen.line("S-CONC-HIDDEN", (a, y - bb / 2), (b_, y - bb / 2))
                pen.line("S-CONC-HIDDEN", (a, y + bb / 2), (b_, y + bb / 2))
                tag = _beam_tag("X", j in (0, ny))
                pen.text("S-TAG", ((a + b_) / 2, y + bb / 2 + 1.5 * scale), f"{tag} {bb:.0f}x{bh:.0f}", h=2.5, align="BOTTOM_CENTER")
            else:
                a, b_ = YS[j] + ch / 2, YS[j + 1] - ch / 2
                x = XS[i]
                pen.line("S-CONC-HIDDEN", (x - bb / 2, a), (x - bb / 2, b_))
                pen.line("S-CONC-HIDDEN", (x + bb / 2, a), (x + bb / 2, b_))
                tag = _beam_tag("Y", i in (0, nx))
                pen.text("S-TAG", (x - bb / 2 - 1.5 * scale, (a + b_) / 2), f"{tag} {bb:.0f}x{bh:.0f}", h=2.5, align="BOTTOM_CENTER", rot=90)
        title_fa, title_en = f"پلان طبقه {k} (تراز {Z[k] / 1000:+.2f})", f"STORY {k} PLAN  (+{Z[k] / 1000:.2f})"
        pen.text("S-TITLE", (W / 2, -m - 4 * scale), title_en, h=5, align="TOP_CENTER")
        pen.text("S-TITLE", (W / 2, -m - 12 * scale), title_fa, h=4.5, align="TOP_CENTER")
        pen.text("S-NOTES", (W / 2, -m - 19 * scale), f"Scale 1:{scale} · columns {cb:.0f}x{ch:.0f} · beams {bb:.0f}x{bh:.0f} mm", h=2.5, align="TOP_CENTER")
        sheets.append((f"S-{k:02d}", ext(pen, -m, -m - 24 * scale, W + m, H + m), title_fa, title_en))

    # ---------------------------------------------------------------- schedules
    pen = region()
    y = 0.0
    crow = []
    for k in range(ns, 0, -1):
        for pos in ("corner", "edge", "interior"):
            c = cols.get((k, pos))
            crow.append((POS_TAG[pos], f"{k}", f"{cb:.0f}x{ch:.0f}", c["bars"] if c else "-", (c["ties"].split(" over")[0] if c and c.get("ties") else "-"),
                         f"{c['DC']:.2f}" if c else "-"))
    y = pen.table(0, y, ("Tag", "Story", "b x h (mm)", "Long. bars", "Ties", "D/C"), crow, (18, 16, 30, 30, 34, 16),
                  title="COLUMN SCHEDULE / جدول ستون‌ها")
    brow = []
    for k in range(ns, 0, -1):
        for dirn in ("X", "Y"):
            for edge, pos in ((True, "edge"), (False, "interior")):
                b_ = beams.get((k, dirn, pos))
                brow.append((_beam_tag(dirn, edge), f"{k}", f"{bb:.0f}x{bh:.0f}", b_["top_bars"] if b_ else "-", b_["bottom_bars"] if b_ else "-",
                             (b_["stirrups"] or "-").split(" (")[0] if b_ else "-"))
    y2 = pen.table(170 * scale, 0, ("Tag", "Story", "b x h (mm)", "Top", "Bottom", "Stirrups"), brow, (18, 16, 30, 26, 26, 34),
                   title="BEAM SCHEDULE / جدول تیرها")
    bottom = min(y, y2)
    pen.notes(0, bottom - 15 * scale, "GENERAL NOTES / یادداشت‌های عمومی", [
        f"Concrete C{inp.fc_mpa:g} (f'c = {inp.fc_mpa:g} MPa), rebar S{inp.fy_mpa:g} (fy = {inp.fy_mpa:g} MPa).",
        "Dimensions in mm, levels in m. Tags: C1 corner / C2 edge / C3 interior columns; B1/B2 X-edge/interior, B3/B4 Y-edge/interior beams.",
        "بتن و میلگرد طبق مبحث نهم مقررات ملی ساختمان؛ ابعاد به میلیمتر و ترازها به متر.",
    ])
    sheets.append(("S-10", ext(pen, -5 * scale, bottom - 60 * scale, 340 * scale, 15 * scale), "جداول ستون و تیر", "COLUMN & BEAM SCHEDULES"))

    # ---------------------------------------------------------------- foundation
    fd = (raw or {}).get("foundation_design")
    if fd and fd.get("footings"):
        pen = region()
        pen.grid(XS, YS, xl, yl)
        rows = {r["position"]: r for r in fd["rows"]}
        done_dim = set()
        for f in fd["footings"]:
            x, y, B = f["x"] * 1000, f["y"] * 1000, f["B_m"] * 1000
            pts = [(x - B / 2, y - B / 2), (x + B / 2, y - B / 2), (x + B / 2, y + B / 2), (x - B / 2, y + B / 2)]
            pen.poly("S-FOOT", pts, closed=True)
            pen.hatch("S-FOOT-HATCH", pts, "AR-CONC", pscale=scale / 12)
            pen.rect("S-CONC", x - cb / 2, y - ch / 2, x + cb / 2, y + ch / 2)
            pen.tag((x, y - B / 2 + 4 * scale), FTG_TAG[f["position"]], h=3)
            if f["position"] not in done_dim:  # dimension one footing of each type
                done_dim.add(f["position"])
                pen.dim((x - B / 2, y + B / 2), (x + B / 2, y + B / 2), 5 * scale)
        frow = [(FTG_TAG[p], POS_FA[p] + " / " + p, f"{r['B_m'] * 1000:.0f}x{r['B_m'] * 1000:.0f}", f"{r['h_m'] * 1000:.0f}", r["bars"], str(r["members"]), r["status"])
                for p, r in rows.items()]
        pen.table(W + m + 10 * scale, H, ("Tag", "Type", "B x L (mm)", "h (mm)", "Bars (bottom)", "No.", "Check"), frow,
                  (14, 30, 28, 16, 38, 10, 16), title="FOOTING SCHEDULE / جدول پی‌ها")
        pen.text("S-TITLE", (W / 2, -m - 4 * scale), f"FOUNDATION PLAN  qa = {fd['qa_kpa']:g} kPa" + (" (assumed)" if fd["qa_assumed"] else ""), h=5, align="TOP_CENTER")
        pen.text("S-TITLE", (W / 2, -m - 12 * scale), "پلان فونداسیون", h=4.5, align="TOP_CENTER")
        sheets.append(("S-F1", ext(pen, -m, -m - 20 * scale, W + m + 170 * scale, H + m), "پلان فونداسیون", "FOUNDATION PLAN"))

    # ---------------------------------------------------------------- elevations
    def elevation(name, coords, labels, depth_label):
        pen = region()
        L = coords[-1]
        top = Z[-1]
        for c in coords:
            pen.line("S-AXIS", (c, -12 * scale), (c, top + 10 * scale))
            pen.bubble((c, -12 * scale - 4 * scale), labels[coords.index(c)])
        for k in range(1, ns + 1):
            for c in coords:  # columns as double lines
                pen.rect("S-CONC", c - cb / 2, Z[k - 1] + (bh if k > 1 else 0) * 0, c + cb / 2, Z[k] - bh)
            for a, b_ in zip(coords, coords[1:]):
                pts = [(a + cb / 2, Z[k] - bh), (b_ - cb / 2, Z[k] - bh), (b_ - cb / 2, Z[k]), (a + cb / 2, Z[k])]
                pen.poly("S-CONC", pts, closed=True)
                pen.hatch("S-CONC-HATCH", pts, "ANSI31", pscale=scale / 8)
            for c in coords:
                pen.rect("S-CONC", c - cb / 2, Z[k] - bh, c + cb / 2, Z[k])
        pen.line("S-CONC", (coords[0] - 6 * scale, 0), (L + 6 * scale, 0))
        for k in range(ns + 1):
            pen.level_mark(L + 10 * scale, Z[k], Z[k] / 1000)
        pen.chain_dims(Z, coords[0], -14 * scale, horizontal=False)
        pen.chain_dims(coords, 0, -24 * scale, horizontal=True, overall=True)
        pen.text("S-TITLE", (L / 2, -42 * scale), f"ELEVATION ON AXIS {name}", h=5, align="TOP_CENTER")
        pen.text("S-TITLE", (L / 2, -50 * scale), f"نمای قاب محور {name}", h=4.5, align="TOP_CENTER")
        sheets.append((f"E-{name}", ext(pen, -30 * scale, -56 * scale, L + 45 * scale, top + 18 * scale), f"نمای محور {name}", f"ELEVATION AXIS {name}"))

    for j, lab in enumerate(yl):
        elevation(lab, XS, xl, "X")
    for i, lab in enumerate(xl):
        elevation(lab, YS, yl, "Y")

    for name, extents, tfa, ten in sheets:
        ds.add_sheet(doc, name, extents, info, name, tfa, ten)
    return doc, [s[0] for s in sheets]


def build_dxf_plans(inp, raw: dict[str, Any], design: dict[str, Any] | None = None) -> str:
    doc, _ = build_structural_doc(inp, raw, design)
    buf = io.StringIO()
    doc.write(buf)
    return buf.getvalue()
