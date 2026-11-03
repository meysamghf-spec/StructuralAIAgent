"""Structural drawing set (S-sheets) generated from a frame3d analysis + Mabhas 9 design.

Generic for any regular RC frame the frame3d solver accepts (any storeys / bays / spans):
  S-101  column layout plan + column schedule (size, longitudinal bars, ties per storey)
  S-102… beam layout plan per storey + beam schedule
  S-201  typical beam longitudinal elevations (top/bottom bars, cut-offs, laps, stirrup zones per Mabhas 9 ductility)
  S-301  column cross-section details (1:20)
  S-401  foundation plan + footing sections / bending schedule (when the foundation design exists)
  S-501  typical frame elevations (one along X, one along Y)
Each sheet is its own DXF with a paper-space layout (border, title block, scale, date, sheet no.) and shared
AIA/NCS-like S-* layers; text uses Arial / Tahoma styles so Persian renders in AutoCAD.
"""
from __future__ import annotations

import io
import math
from dataclasses import dataclass, field
from typing import Any

from app.application import detailing_assumptions as da
from app.application import drawing_standard as ds
from app.application import rebar_detailing as rd

POS_MARK = {"corner": "C1", "edge": "C2", "interior": "C3"}
POS_FA = {"corner": "گوشه", "edge": "کناری", "interior": "میانی"}


@dataclass
class Sheet:
    sheet_no: str
    title_en: str
    title_fa: str
    doc: Any
    scale: int
    notes: list[str] = field(default_factory=list)

    def dxf_text(self) -> str:
        buf = io.StringIO()
        self.doc.write(buf)
        return buf.getvalue()


def _pos(i: int, j: int, nx: int, ny: int) -> str:
    if i in (0, nx) and j in (0, ny):
        return "corner"
    return "edge" if (i in (0, nx) or j in (0, ny)) else "interior"


def _grid(inp) -> tuple[list[float], list[float], list[str], list[str]]:
    xs = [i * inp.bay_x_m * 1000 for i in range(inp.bays_x + 1)]
    ys = [j * inp.bay_y_m * 1000 for j in range(inp.bays_y + 1)]
    return xs, ys, [rd._xl(i) for i in range(len(xs))], [rd._yl(j) for j in range(len(ys))]


def _dims(inp, k: int) -> tuple[tuple[float, float], tuple[float, float]]:
    from app.application.frame3d_chat_analysis import beam_dims, column_dims
    try:
        c, b = column_dims(inp, k), beam_dims(inp, k)
    except Exception:  # noqa: BLE001
        c, b = (inp.column_b_m, inp.column_h_m), (inp.beam_b_m, inp.beam_h_m)
    return (c[0] * 1000, c[1] * 1000), (b[0] * 1000, b[1] * 1000)


def _beam_mark(k: int, direction: str, position: str) -> str:
    return f"B{k}{direction}{1 if position == 'edge' else 2}"


def _new_doc():
    doc = ds.new_document()
    for name, color in rd.LAYERS.items():  # rebar-detail layers reused by the beam elevations
        if name not in doc.layers:
            doc.layers.add(name, color=color, lineweight=rd.LINEWEIGHTS.get(name, 18))
    return doc


def _extents(doc, pad: float) -> tuple[float, float, float, float]:
    from ezdxf import bbox
    box = bbox.extents(e for e in doc.modelspace() if e.dxf.layer != "S-SHEET")
    return (box.extmin.x - pad, box.extmin.y - pad, box.extmax.x + pad, box.extmax.y + pad)


def _finish(doc, name: str, info, title_fa: str, title_en: str, scale: int) -> None:
    ext = _extents(doc, 8 * scale)
    paper = "A3" if (ext[2] - ext[0]) / scale <= ds.PAPER["A3"][0] - 40 and (ext[3] - ext[1]) / scale <= ds.PAPER["A3"][1] - 30 - 75 else "A1"
    ds.add_sheet_tiles(doc, name, ext, info, title_fa, title_en, scale=scale, paper=paper)
    if "Layout1" in doc.layouts:
        doc.layouts.delete("Layout1")


def _plan_scale(inp) -> int:
    w, h = inp.bays_x * inp.bay_x_m * 1000, inp.bays_y * inp.bay_y_m * 1000
    for s in (50, 100, 200):
        if (w + 60 * s) / s <= 780 and (h + 300 * s) / s <= 480:
            return s
    return 200


def _orient(pen: ds.Pen, xs, ys) -> None:
    s = pen.scale
    pen.north_arrow((xs[-1] + 45 * s, ys[-1] + 5 * s))


# ---------------------------------------------------------------- S-101 columns
def sheet_columns(inp, design, info) -> Sheet:
    doc, s = _new_doc(), _plan_scale(inp)
    pen = ds.Pen(doc.modelspace(), (0, 0), s)
    xs, ys, xl, yl = _grid(inp)
    pen.grid(xs, ys, xl, yl)
    (cb, ch), _ = _dims(inp, 1)
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            pos = _pos(i, j, inp.bays_x, inp.bays_y)
            pen.rect("S-CONC", x - cb / 2, y - ch / 2, x + cb / 2, y + ch / 2)
            pen.hatch("S-CONC-HATCH", [(x - cb / 2, y - ch / 2), (x + cb / 2, y - ch / 2), (x + cb / 2, y + ch / 2), (x - cb / 2, y + ch / 2)], solid=True)
            pen.tag((x + cb / 2 + 4 * s, y + ch / 2 + 3 * s), POS_MARK[pos], h=3.0)
    pen.text("S-TITLE", (xs[0], ys[-1] + 32 * s), "COLUMN LAYOUT PLAN / پلان جانمایی ستون‌ها", h=5)
    _orient(pen, xs, ys)
    cols = sorted(design["columns"], key=lambda c: (list(POS_MARK).index(c["position"]), c["storey"]))
    rows = []
    for c in cols:
        (b, h), _ = _dims(inp, c["storey"])
        if not _ok(c.get("bars")) or not c.get("ties"):
            rows.append([POS_MARK[c["position"]], f"S{c['storey']}", f"{b:.0f}x{h:.0f}", "NG - enlarge section", "", "", "", "", c["position"], ""])
            continue
        dt, s0, sm, l0 = rd.parse_spacing(c.get("ties"))
        rows.append([POS_MARK[c["position"]], f"S{c['storey']}", f"{b:.0f}x{h:.0f}", c["bars"], f"{c.get('rho_pct', '')}",
                     f"Φ{dt}@{s0}", f"{l0 or max(b, h, 450):.0f}", f"Φ{dt}@{sm}", c["position"], f"{c.get('DC', '')}"])
    pen.table(xs[0] - 20 * s, ys[0] - 45 * s,
              ["Mark", "Storey", "b x h (mm)", "Long. bars", "ρ %", "Ties end", "l0 (mm)", "Ties mid", "Position", "D/C"],
              rows, [16, 16, 24, 26, 14, 24, 18, 24, 22, 14], title="COLUMN SCHEDULE / جدول ستون‌ها")
    A = da.effective(getattr(inp, "assumptions", None))
    pen.notes(xs[-1] + 30 * s, ys[0] - 45 * s, "NOTES / یادداشت‌ها", [
        f"Concrete C{inp.fc_mpa:g}, rebar S{inp.fy_mpa:g}; clear cover {A['cover_mm']:g} mm",
        "C1 corner, C2 edge, C3 interior column (one design group per storey)",
        "Ties: 135° hooks; confinement zone l0 at both ends (Mabhas 9 ductility)",
        "Laps in the middle half of the clear height only",
        "شماره‌گذاری ستون‌ها مطابق جدول؛ ابعاد به میلی‌متر",
    ])
    _finish(doc, "S-101", info, "پلان ستون‌گذاری و جدول ستون‌ها", "COLUMN LAYOUT + SCHEDULE", s)
    return Sheet("S-101", "Column layout + schedule", "پلان ستون‌گذاری و جدول ستون‌ها", doc, s)


# ---------------------------------------------------------------- S-102.. beams per storey
def sheet_beams(inp, design, info, k: int, sheet_no: str) -> Sheet:
    doc, s = _new_doc(), _plan_scale(inp)
    pen = ds.Pen(doc.modelspace(), (0, 0), s)
    xs, ys, xl, yl = _grid(inp)
    pen.grid(xs, ys, xl, yl)
    (cb, ch), (bb, bh) = _dims(inp, k)
    nx, ny = inp.bays_x, inp.bays_y
    for x in xs:
        for y in ys:
            pen.rect("S-CONC", x - cb / 2, y - ch / 2, x + cb / 2, y + ch / 2)
    for j, y in enumerate(ys):  # X beams on lettered grid lines
        mark = _beam_mark(k, "X", "edge" if j in (0, ny) else "interior")
        for i in range(nx):
            a, b = xs[i] + cb / 2, xs[i + 1] - cb / 2
            pen.line("S-CONC", (a, y - bb / 2), (b, y - bb / 2)); pen.line("S-CONC", (a, y + bb / 2), (b, y + bb / 2))
            pen.text("S-TAG", ((a + b) / 2, y + bb / 2 + 2 * s), mark, h=2.5, align="BOTTOM_CENTER")
    for i, x in enumerate(xs):
        mark = _beam_mark(k, "Y", "edge" if i in (0, nx) else "interior")
        for j in range(ny):
            a, b = ys[j] + ch / 2, ys[j + 1] - ch / 2
            pen.line("S-CONC", (x - bb / 2, a), (x - bb / 2, b)); pen.line("S-CONC", (x + bb / 2, a), (x + bb / 2, b))
            pen.text("S-TAG", (x - bb / 2 - 2 * s, (a + b) / 2), mark, h=2.5, align="BOTTOM_CENTER", rot=90)
    z = k * inp.storey_height_m
    pen.text("S-TITLE", (xs[0], ys[-1] + 32 * s), f"BEAM LAYOUT - STOREY {k} (+{z:.2f}) / پلان تیرریزی طبقه {k}", h=5)
    _orient(pen, xs, ys)
    rows = []
    for g in sorted((g for g in design["beams"] if g["storey"] == k), key=lambda g: (g["direction"], g["position"] != "edge")):
        rows.append([_beam_mark(k, g["direction"], g["position"]), g["direction"], g["position"], f"{bb:.0f}x{bh:.0f}",
                     g["top_bars"], g["bottom_bars"], (g.get("stirrups") or "").replace(", ", " / "), g.get("members", ""),
                     f"{max(g.get('DC_flexure') or 0, g.get('DC_shear') or 0):.2f}"])
    pen.table(xs[0] - 20 * s, ys[0] - 45 * s, ["Mark", "Dir", "Position", "b x h", "Top (support)", "Bottom", "Stirrups", "Spans", "D/C"],
              rows, [16, 10, 18, 20, 24, 20, 80, 12, 12], title=f"BEAM SCHEDULE - STOREY {k} / جدول تیرها")
    _finish(doc, sheet_no, info, f"پلان تیرریزی طبقه {k}", f"BEAM LAYOUT STOREY {k}", s)
    return Sheet(sheet_no, f"Beam layout storey {k}", f"پلان تیرریزی طبقه {k}", doc, s)


# ---------------------------------------------------------------- S-201 typical beam elevations
def _ok(bars) -> bool:
    try:
        rd.parse_bars(bars)
        return True
    except ValueError:
        return False


def _typical_beams(design) -> list[dict]:
    out = []
    for d in ("X", "Y"):
        gs = [g for g in design["beams"] if g["direction"] == d and _ok(g.get("top_bars")) and _ok(g.get("bottom_bars"))]
        if gs:
            out.append(max(gs, key=lambda g: (rd.parse_bars(g["top_bars"])[0] * rd.parse_bars(g["top_bars"])[1] ** 2, g.get("Mu_neg_kn_m") or 0)))
    return out


def sheet_beam_details(inp, design, info) -> Sheet:
    doc = _new_doc()
    A = da.effective(getattr(inp, "assumptions", None))
    sh = rd._Sheet(doc.modelspace(), 0.0, "S-201")
    rows: list = []
    y = 0.0
    beams = _typical_beams(design)
    for g in beams:
        sh.text("TITLE", (-1500, y + inp.beam_h_m * 1000 + 2700), 250,
                f"TYPICAL BEAM {_beam_mark(g['storey'], g['direction'], g['position'])} ({g['group']}) - {g['top_bars']} top / {g['bottom_bars']} bottom")
        rd._draw_beam(sh, y, g, inp, rows, A)
        y -= inp.beam_h_m * 1000 + 5200
    pen = ds.Pen(doc.modelspace(), (0, 0), 50)
    notes = ["Mabhas 9 (ductility: %s):" % design.get("ductility", "medium"),
             "- first stirrup 50 mm from the column face; confinement zone 2h at both ends",
             "- s(end) <= min(d/4, 8 db(min), 24 dt, 300 mm); s(mid) <= d/2",
             "- at least 2 continuous top and bottom bars over the full length",
             "- extra top bars cut off per project rule (default ln/3 from the face)",
             "- laps outside the confinement zones and away from the joints; class " + str(A["splice_class"]),
             "- stirrups closed with 135° hooks (%g db extension)" % float(A["stirrup_hook_db"]),
             "دیتیل تیپ تیرها؛ برای سایر تیرها میلگردها طبق جدول تیرها"]
    pen.notes(-1500, y - 400, "BEAM DETAILING NOTES / یادداشت‌های تیر", notes)
    # sections of the drawn beams at 1:20 scale-annotated region to the right
    x0 = max(rd._beam_spans(inp, g["direction"])[0] * rd._beam_spans(inp, g["direction"])[1] for g in beams) + 3000 if beams else 0.0
    p20 = ds.Pen(doc.modelspace(), (x0, 0), 20)
    xx = 0.0
    for sp in sh.secs[:6]:
        ds.rc_section(p20, xx, -sp["h"], sp["b"], sp["h"], sp["cover"], sp["tie"], sp["bars"], sp["groups"], sp["tie_label"],
                      sp["ties"], sp["title"], sp["title_fa"], axes=sp.get("axes"))
        xx += sp["b"] + 105 * 20
    _finish(doc, "S-201", info, "دیتیل طولی تیپ تیرها", "TYPICAL BEAM ELEVATIONS & REBAR", 50)
    return Sheet("S-201", "Typical beam elevations & rebar", "دیتیل طولی تیپ تیرها", doc, 50)


# ---------------------------------------------------------------- S-301 column sections
def sheet_column_sections(inp, design, info) -> Sheet:
    doc = _new_doc()
    scratch = _new_doc()
    A = da.effective(getattr(inp, "assumptions", None))
    sh = rd._Sheet(scratch.modelspace(), 0.0, "tmp")
    seen, groups = set(), []
    for c in sorted(design["columns"], key=lambda c: (list(POS_MARK).index(c["position"]), c["storey"])):
        if not _ok(c.get("bars")):
            continue
        key = (c["position"], c["bars"], c.get("ties"))
        if key in seen:
            continue
        seen.add(key)
        groups.append(c)
        rd._draw_column(sh, 0.0, c, inp, [], A)
    pen = ds.Pen(doc.modelspace(), (0, 0), 20)
    x, y, row_h, width = 0.0, 0.0, 0.0, 0.0
    for c, sp in zip(groups, sh.secs):
        if x > 0 and x + sp["b"] + 1800 > 12000:  # wrap rows (A1 at 1:20)
            x, y = 0.0, y - row_h
            row_h = 0.0
        stories = sorted({cc["storey"] for cc in design["columns"] if (cc["position"], cc["bars"], cc.get("ties")) == (c["position"], c["bars"], c.get("ties"))})
        title = f"{POS_MARK[c['position']]}  S{stories[0]}" + (f"-S{stories[-1]}" if len(stories) > 1 else "")
        ds.rc_section(pen, x, y - sp["h"], sp["b"], sp["h"], sp["cover"], sp["tie"], sp["bars"], sp["groups"], sp["tie_label"],
                      sp["ties"], title, f"برش ستون {POS_FA[c['position']]}", axes=sp.get("axes"))
        x += sp["b"] + 2200
        width = max(width, x)
        row_h = max(row_h, sp["h"] + 1600)
    pen.text("S-TITLE", (0, 1300), "COLUMN CROSS-SECTIONS 1:20 / برش ستون‌ها", h=5)
    _finish(doc, "S-301", info, "دیتیل مقاطع ستون‌ها", "COLUMN SECTION DETAILS", 20)
    return Sheet("S-301", "Column section details", "دیتیل مقاطع ستون‌ها", doc, 20)


# ---------------------------------------------------------------- S-401 foundation
def sheet_foundation(inp, raw, design, info) -> Sheet | None:
    fd = (raw or {}).get("foundation_design")
    if not fd or not fd.get("footings"):
        return None
    from app.application.foundation_detailing import build_foundation_doc
    doc = build_foundation_doc(inp, raw, design, info)
    if isinstance(doc, tuple):
        doc = doc[0]
    if "Layout1" in doc.layouts:
        doc.layouts.delete("Layout1")
    return Sheet("S-401", "Foundation plan + footing details", "پلان فونداسیون و دیتیل پی‌ها", doc, 50)


# ---------------------------------------------------------------- S-501 frame elevations
def sheet_frame_elevation(inp, design, info) -> Sheet:
    doc, s = _new_doc(), 100
    msp = doc.modelspace()
    xs, ys, xl, yl = _grid(inp)
    H = inp.storey_height_m * 1000
    Z = [k * H for k in range(inp.storeys + 1)]
    cmark = {}
    for c in design["columns"]:
        cmark[(c["storey"], c["position"])] = c["bars"]
    ox = 0.0
    for direction, coords, labels, line_lab in (("X", xs, xl, yl[0]), ("Y", ys, yl, xl[0])):
        pen = ds.Pen(msp, (ox, 0), s)
        ext = 10 * s
        for c, lab in zip(coords, labels):
            pen.line("S-AXIS", (c, -ext), (c, Z[-1] + ext))
            pen.bubble((c, Z[-1] + ext + 4 * s), lab)
        pen.chain_dims(coords, -ext, -6 * s, horizontal=True)
        n = len(coords) - 1
        for k in range(1, inp.storeys + 1):
            (cb, ch), (bb, bh) = _dims(inp, k)
            cw = cb if direction == "X" else ch
            for i, c in enumerate(coords):
                pen.rect("S-CONC", c - cw / 2, Z[k - 1], c + cw / 2, Z[k] - bh)
                pos = "corner" if i in (0, n) else "edge"
                pen.text("S-TAG", (c + cw / 2 + 1.5 * s, (Z[k - 1] + Z[k]) / 2), f"{POS_MARK[pos]} {cmark.get((k, pos), '')}", h=2.0, rot=90,
                         align="BOTTOM_CENTER")
            pen.rect("S-CONC", coords[0] - cw / 2, Z[k] - bh, coords[-1] + cw / 2, Z[k])
            pen.text("S-TAG", ((coords[0] + coords[1]) / 2, Z[k] - bh - 2 * s), _beam_mark(k, direction, "edge"), h=2.5, align="TOP_CENTER")
            pen.level_mark(coords[-1] + cw / 2 + 12 * s, Z[k], Z[k] / 1000)
        pen.level_mark(coords[-1] + 12 * s, 0, 0.0)
        pen.line("S-FOOT", (coords[0] - 3 * s, 0), (coords[-1] + 3 * s, 0))
        for a, b in zip(Z, Z[1:]):
            pen.dim((coords[0] - 20 * s, a), (coords[0] - 20 * s, b), 0, 90)
        pen.text("S-TITLE", (coords[0], Z[-1] + ext + 14 * s), f"FRAME ELEVATION ON GRID {line_lab} (along {direction}) / نمای قاب محور {line_lab}", h=4)
        ox += coords[-1] + 70 * s
    _finish(doc, "S-501", info, "نمای قاب‌های تیپ", "TYPICAL FRAME ELEVATIONS", s)
    return Sheet("S-501", "Typical frame elevations", "نمای قاب‌های تیپ", doc, s)


# ---------------------------------------------------------------- set
def build_structural_set(inp, raw: dict[str, Any], design: dict[str, Any] | None, project: str | None = None) -> tuple[list[Sheet], list[str]]:
    if not design or not design.get("beams") or not design.get("columns"):
        raise ValueError("structural drawings need the Mabhas 9 design of the frame (design_code MABHAS9)")
    info = ds.title_info(inp, project or "3D RC frame")
    sheets: list[Sheet] = [sheet_columns(inp, design, info)]
    for k in range(1, inp.storeys + 1):
        sheets.append(sheet_beams(inp, design, info, k, f"S-{101 + k}"))
    sheets.append(sheet_beam_details(inp, design, info))
    sheets.append(sheet_column_sections(inp, design, info))
    notes: list[str] = []
    ng = [g["group"] for g in design["beams"] + design["columns"] if not _ok(g.get("bars") or g.get("top_bars"))]
    if ng:
        notes.append("no reinforcement found for " + ", ".join(ng[:8]) + (" …" if len(ng) > 8 else "") + " — enlarge those sections and regenerate")
    try:
        f = sheet_foundation(inp, raw, design, info)
    except ValueError as exc:
        f, _ = None, notes.append(f"foundation sheet skipped: {exc}")
    if f:
        sheets.append(f)
    elif not notes:
        notes.append("foundation sheet skipped: no footing design in this run")
    sheets.append(sheet_frame_elevation(inp, design, info))
    return sheets, notes


def render_pdf(sheets: list[Sheet]) -> bytes:
    """Combined PDF preview: every paper-space layout of every sheet, one page each."""
    import pymupdf
    from ezdxf.addons.drawing import Frontend, RenderContext, layout as dlayout
    from ezdxf.addons.drawing import pymupdf as pmb
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration

    out = pymupdf.open()
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK, min_lineweight=0.12)
    for sh in sheets:
        for lay in sh.doc.layouts:
            if lay.name.lower() == "model" or len(lay) == 0:
                continue
            be = pmb.PyMuPdfBackend()
            Frontend(RenderContext(sh.doc), be, config=cfg).draw_layout(lay, finalize=True)
            w, h = lay.dxf.paper_width or 420, lay.dxf.paper_height or 297
            page = dlayout.Page(w, h, dlayout.Units.mm)
            data = be.get_pdf_bytes(page)
            out.insert_pdf(pymupdf.open("pdf", data))
    return out.tobytes(deflate=True)


# ---------------------------------------------------------------- storage (CAD jobs + set dir)
def _sets_root():
    from .service import _root
    p = _root() / "structural_sets"
    p.mkdir(parents=True, exist_ok=True)
    return p


def generate_and_store(inputs: dict[str, Any], *, owner: str, project_id: str | None, project_name: str | None = None,
                       save_project_file=None, with_pdf: bool = True) -> dict[str, Any]:
    """Run the frame, build the set, store each sheet as a CAD job + one combined PDF; optionally save to project Files."""
    import json
    import uuid
    from datetime import datetime, timezone

    from app.application.frame3d_chat_analysis import run_frame3d_for_export
    from . import service

    inputs = {**(inputs or {}), "design_code": "MABHAS9", "foundation": True}
    inp, raw, design = run_frame3d_for_export(inputs)
    sheets, notes = build_structural_set(inp, raw, design, project_name)
    sid = uuid.uuid4().hex
    d = _sets_root() / sid
    d.mkdir()
    items = []
    for sh in sheets:
        job = service.save_job(sh.doc, {"sheet_no": sh.sheet_no, "title": sh.title_en, "title_fa": sh.title_fa, "scale": f"1:{sh.scale}",
                                        "set_id": sid}, kind="structural", owner=owner, source=f"{sh.sheet_no} {sh.title_en}",
                               project_id=project_id)
        items.append({"sheet_no": sh.sheet_no, "title": sh.title_en, "title_fa": sh.title_fa, "scale": f"1:{sh.scale}",
                      "job_id": job["id"], "filename": f"{sh.sheet_no}.dxf", "file_id": None})
    pdf_ok = False
    if with_pdf:
        try:
            (d / "set.pdf").write_bytes(render_pdf(sheets))
            pdf_ok = True
        except Exception as exc:  # noqa: BLE001 - DXFs remain usable without the preview
            notes.append(f"PDF preview failed: {exc}")
    pdf_file_id = None
    if save_project_file and project_id:
        for it in items:
            try:
                fid = save_project_file(f"structural-{it['filename']}", (service._root() / it["job_id"] / "drawing.dxf").read_bytes(), "application/dxf")
                it["file_id"] = fid
                if fid:
                    service.set_project_file(it["job_id"], fid)
            except Exception:  # noqa: BLE001
                pass
        if pdf_ok:
            try:
                pdf_file_id = save_project_file("structural-drawing-set.pdf", (d / "set.pdf").read_bytes(), "application/pdf")
            except Exception:  # noqa: BLE001
                pdf_file_id = None
    meta = {"id": sid, "owner": owner, "project_id": project_id, "created_at": datetime.now(timezone.utc).isoformat(),
            "sheets": items, "notes": notes, "pdf": pdf_ok, "pdf_file_id": pdf_file_id,
            "frame": {"storeys": inp.storeys, "bays_x": inp.bays_x, "bays_y": inp.bays_y, "bay_x_m": inp.bay_x_m,
                      "bay_y_m": inp.bay_y_m, "storey_height_m": inp.storey_height_m}}
    (d / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")
    return meta


def list_sets(owner: str, project_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
    import json
    out = []
    for f in _sets_root().glob("*/meta.json"):
        try:
            m = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if m.get("owner") == owner and (not project_id or m.get("project_id") == project_id):
            out.append(m)
    out.sort(key=lambda m: m.get("created_at", ""), reverse=True)
    return out[:limit]


def set_dir(sid: str, owner: str):
    import json
    import re
    if not re.fullmatch(r"[0-9a-f]{32}", sid or ""):
        raise FileNotFoundError(sid)
    d = _sets_root() / sid
    if json.loads((d / "meta.json").read_text(encoding="utf-8")).get("owner") != owner:
        raise FileNotFoundError(sid)
    return d


_WANT = (r"نقشه[‌\s]*(ها|های)?[‌\s]*(ی)?[‌\s]*(اجرایی|سازه|دیتیل|جزئیات)|دیتیل[‌\s]*(ها)?[‌\s]*(ی)?[‌\s]*(سازه|اجرایی|تیر|ستون|آرماتور)|"
         r"(structural|construction|shop)\s+(detail\s+)?(drawings?|sheets?|details?|drawing\s+set)|"
         r"structural\s+drawing\s+set|detail\s+drawings?|s-sheets")


def wants_structural_set(text: str) -> bool:
    import re
    return bool(re.search(_WANT, text or "", re.I))
