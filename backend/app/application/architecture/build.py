"""Program -> layout -> sheets -> files (DXF per sheet, PNG previews, combined PDF, ZIP)."""
from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Any

from app.application import drawing_standard as ds

from . import drawing, views
from .layout import Layout, generate
from .program import BuildingProgram


def checks(L: Layout) -> list[tuple[str, str, str, str]]:
    p, r = L.program, L.rules
    occ_allowed = r.occupancy_depth(p.plot_depth_m)
    stalls = sum(len(f.stalls) for f in L.floors)
    units = p.units_per_floor * max(0, p.floors - (1 if r.pilotis_ground_floor and p.parking else 0))
    clear = min(f.height for f in L.floors[:-1]) - r.slab_thickness_m
    rise_ok = 0.60 <= 2 * r.riser_m + r.tread_m <= 0.65
    out = [
        (f"Occupancy depth / سطح اشغال {r.occupancy_pct:g}% + {r.occupancy_extra_m:g} m", f"<= {occ_allowed:.2f} m", f"{L.D:.2f} m", "OK" if L.D <= occ_allowed + 1e-6 else "NO"),
        ("Parking / پارکینگ", f"{units * r.parking_per_unit:.0f}", str(stalls), "OK" if stalls >= units * r.parking_per_unit or not p.parking else "NO"),
        ("Clear height / ارتفاع مفید", f">= {r.min_clear_height_m:.2f} m", f"{clear:.2f} m", "OK" if clear >= r.min_clear_height_m - 1e-6 else "NO"),
        ("Stair width / عرض پله", ">= 1.10 m", f"{r.stair_width_m:.2f} m", "OK" if r.stair_width_m >= 1.1 else "NO"),
        ("Blondel 2R+G", "0.60-0.65 m", f"{2 * r.riser_m + r.tread_m:.2f} m", "OK" if rise_ok else "NO"),
        (f"Elevator from {r.elevator_from_floors} floors / آسانسور", "yes" if p.floors >= r.elevator_from_floors else "optional", "yes" if L.shaft else "no", "OK" if (L.shaft or p.floors < r.elevator_from_floors) else "NO"),
        ("Parapet / جان پناه", f">= {r.parapet_m:.2f} m", f"{r.parapet_m:.2f} m", "OK"),
    ]
    for fl in L.floors:
        for rm in fl.rooms:
            mins = {"bedroom": r.min_bedroom_m2, "master": r.min_master_bedroom_m2, "living": r.min_living_m2, "kitchen": r.min_kitchen_m2, "bath": r.min_bath_m2}
            if rm.kind in mins and rm.area < mins[rm.kind] - 1e-6:
                out.append((f"{rm.en} ({fl.name_en}) min area", f">= {mins[rm.kind]:g} m²", f"{rm.area:.1f} m²", "NO"))
    return out


def build_sheets(p: BuildingProgram, info: ds.TitleInfo | None = None) -> tuple[Layout, list[drawing.Sheet]]:
    L = generate(p)
    info = info or ds.TitleInfo(project=p.project_name, code="Mabhas 4 / municipal rules")
    sheets: list[drawing.Sheet] = []
    sheets.append(views.site_sheet(L, "C-101", info))
    typ_done = False
    n = 101
    for fl in L.floors:
        if fl.kind == "roof":
            continue
        if fl.kind == "typical":
            if typ_done:
                continue
            typ_done = True
            same = [f for f in L.floors if f.kind == "typical"]
            if len(same) > 1:
                fl = drawing.Floor(fl.index, fl.kind, f"Typical floor plan (floors {same[0].index}-{same[-1].index})", f"پلان طبقات تیپ ({same[0].index} تا {same[-1].index})", fl.z, fl.height, fl.rooms, fl.openings, fl.balconies, fl.stalls)
        n += 1 if sheets[-1].kind == "plan" else 0
        sheets.append(drawing.plan_sheet(L, fl, f"A-{n}", info))
    sheets.append(drawing.plan_sheet(L, L.floors[-1], "A-201", info))
    sheets.append(views.section_sheet(L, True, "A-301", info))
    sheets.append(views.section_sheet(L, False, "A-302", info))
    for i, side in enumerate(("front", "back", "east", "west")):
        sheets.append(views.elevation_sheet(L, side, f"A-40{i + 1}", info))
    sheets.append(views.schedule_sheet(L, "A-601", info))
    index = [("A-000", "Cover, index, rules", "فهرست و ضوابط")] + [(s.no, s.title_en, s.title_fa) for s in sheets]
    sheets.insert(0, views.cover_sheet(L, index, "A-000", info, checks(L)))
    return L, sheets


def _replay(doc):
    from ezdxf.addons.drawing import Frontend, RenderContext
    from ezdxf.addons.drawing.config import BackgroundPolicy, ColorPolicy, Configuration
    from ezdxf.addons.drawing.pymupdf import PyMuPdfBackend
    be = PyMuPdfBackend()
    cfg = Configuration(background_policy=BackgroundPolicy.WHITE, color_policy=ColorPolicy.BLACK, lineweight_scaling=1.0)
    Frontend(RenderContext(doc), be, config=cfg).draw_layout(doc.modelspace(), finalize=True, filter_func=lambda e: e.dxf.layer != "S-SHEET")
    return be


def render(doc, png_path: Path | None, width_px: int = 2400) -> bytes:
    """Render model space; writes a PNG (if path) and returns single-page PDF bytes (A3 landscape fit)."""
    from ezdxf.addons.drawing import layout
    import pymupdf
    be = _replay(doc)
    pdf = be.get_pdf_bytes(layout.Page(420, 297, layout.Units.mm, margins=layout.Margins.all(6)), settings=layout.Settings(fit_page=True))
    if png_path is not None:
        d = pymupdf.open(stream=pdf, filetype="pdf")
        pg = d[0]
        z = width_px / pg.rect.width
        pg.get_pixmap(matrix=pymupdf.Matrix(z, z), alpha=False).save(str(png_path))
    return pdf


def write_set(p: BuildingProgram, out: Path, info: ds.TitleInfo | None = None, png: bool = True) -> dict[str, Any]:
    out.mkdir(parents=True, exist_ok=True)
    L, sheets = build_sheets(p, info)
    meta: dict[str, Any] = {"program": p.to_dict() if hasattr(p, "to_dict") else {}, "assumptions": L.assumptions, "warnings": L.warnings,
                            "checks": [list(c) for c in checks(L)], "sheets": []}
    pngs = []
    for s in sheets:
        f = out / f"{s.no}.dxf"
        s.doc.saveas(f)
        item = {"no": s.no, "title_en": s.title_en, "title_fa": s.title_fa, "kind": s.kind, "scale": s.scale, "dxf": f.name}
        if png:
            pf = out / f"{s.no}.png"
            try:
                pdf_b = render(s.doc, pf)
            except Exception as exc:  # noqa: BLE001 - previews are optional, the DXF is the deliverable
                meta.setdefault("warnings", []).append(f"Preview rendering unavailable ({type(exc).__name__}); DXF files only.")
                png = False
                meta["sheets"].append(item)
                continue
            (out / f"{s.no}.pdf").write_bytes(pdf_b)
            item["png"] = pf.name
            item["pdf"] = f"{s.no}.pdf"
            pngs.append(out / f"{s.no}.pdf")
        meta["sheets"].append(item)
    if pngs:
        import pymupdf
        pdf = pymupdf.open()
        for pf in pngs:
            pdf.insert_pdf(pymupdf.open(pf))
        pdf.save(out / "architectural-set.pdf")
        meta["pdf"] = "architectural-set.pdf"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for s in meta["sheets"]:
            z.write(out / s["dxf"], s["dxf"])
        if meta.get("pdf"):
            z.write(out / meta["pdf"], meta["pdf"])
    (out / "architectural-set.zip").write_bytes(buf.getvalue())
    meta["zip"] = "architectural-set.zip"
    return meta
