"""Sections, elevations, site plan, door/window schedule and the cover/assumptions sheet."""
from __future__ import annotations

from collections import Counter

from app.application import drawing_standard as ds

from .drawing import AP, Sheet, _finish, new_doc
from .layout import Layout

MATERIALS = [
    "Facade: travertine stone 2 cm on mortar / نما: سنگ تراورتن",
    "Window frames: UPVC double glazed / پنجره دوجداره UPVC",
    "Railings: steel, h=1.00 m / نرده فلزی",
    "Parapet cap: stone coping / درپوش سنگی جان پناه",
]


def _levels(L: Layout):
    return [(fl.z, fl.name_en, fl.name_fa) for fl in L.floors]


def section_sheet(L: Layout, longitudinal: bool, no: str, info: ds.TitleInfo) -> Sheet:
    """A-A longitudinal (cut along y through the stair) or B-B transverse (cut along x through the core)."""
    doc = new_doc()
    pen = AP(doc.modelspace(), scale=100)
    r = L.rules
    span = L.D if longitudinal else L.W
    ts = r.slab_thickness_m
    H = L.total_height
    sx0, sy0, sx1, sy1 = L.stair
    # ground + foundation
    pen.mline("A-GRND", (-3, 0), (span + 3, 0))
    pen.mpat("A-SECT-CUT", [(-3, 0), (span + 3, 0), (span + 3, -0.4), (-3, -0.4)], pattern="EARTH", sc=8)
    pen.mfill("A-SECT", [(-0.3, -1.4), (span + 0.3, -1.4), (span + 0.3, -0.9), (-0.3, -0.9)])
    # slabs
    for fl in L.floors[1:]:
        q = [(0, fl.z - ts), (span, fl.z - ts), (span, fl.z), (0, fl.z)]
        pen.mfill("A-SECT", q)
    # walls cut at both ends
    te = r.exterior_wall_m if longitudinal else r.party_wall_m
    for x0 in (0.0, span - te):
        pen.mfill("A-SECT", [(x0, 0), (x0 + te, 0), (x0 + te, H + r.parapet_m), (x0, H + r.parapet_m)])
    # stair: flights between each floor
    a, b = (sy0, sy1) if longitudinal else (sx0, sx1)
    for fl, nxt in zip(L.floors, L.floors[1:]):
        if fl.kind == "roof":
            break
        z0, z1 = fl.z, nxt.z
        zm = (z0 + z1) / 2
        f = L.stair_flight_len
        s0 = a + 1.2
        if longitudinal:
            pen.mpoly("A-SECT", [(s0, z0), (s0 + f, zm), (s0 + f + 1.2, zm)])
            pen.mpoly("A-HIDDEN", [(s0 + f, zm), (s0, z1)])
            n = L.risers_per_flight
            pts = []
            for i in range(n):
                x = s0 + i * (f / max(1, n - 1))
                pts += [(x, z0 + i * (zm - z0) / n), (x, z0 + (i + 1) * (zm - z0) / n)]
            pen.mpoly("A-SECT", pts)
        else:
            pen.mrect("A-SECT", a, zm - 0.15, b, zm)
            pen.mline("A-HIDDEN", (a, z0), (a + (b - a) / 2, zm))
    # stair house + parapet
    top = H + r.ground_floor_to_floor_m * 0 + 2.6
    pen.mfill("A-SECT", [(a, top - ts), (b, top - ts), (b, top), (a, top)])
    pen.mline("A-SECT", (a, H), (a, top)); pen.mline("A-SECT", (b, H), (b, top))
    pen.mtext("A-AREA-IDEN", ((a + b) / 2, H + 1.3), "خرپشته STAIR HOUSE", h=2.0)
    # openings in end walls (window cut)
    for fl in L.floors[:-1]:
        for x0 in ((0.0,) if longitudinal else ()):
            pen.mrect("A-ELEV-OPEN", x0, fl.z + r.window_sill_m, x0 + te, fl.z + r.window_head_m)
        if longitudinal:
            pen.mrect("A-ELEV-OPEN", span - te, fl.z + r.window_sill_m, span, fl.z + r.window_head_m)
        lab = fl.name_fa
        pen.mtext("A-AREA-IDEN", (span * 0.35, fl.z + fl.height / 2), f"{lab}  {fl.name_en}", h=2.2)
        pen.mtext("A-AREA-IDEN", (span * 0.35, fl.z + fl.height / 2 - 0.45), f"clear h = {fl.height - ts:.2f} m", h=1.6)
    # level marks + height dims
    for z, en, _fa in _levels(L):
        pen.level_mark(-1.0 * 1000, z * 1000, z, side=-1)
    pen.level_mark(-1.0 * 1000, (H + r.parapet_m) * 1000, H + r.parapet_m, side=-1)
    pen.level_mark(-1.0 * 1000, top * 1000, top, side=-1)
    zs = [fl.z * 1000 for fl in L.floors] + [(H + r.parapet_m) * 1000]
    pen.chain_dims(zs, (span + 0.3) * 1000, -18 * 100, horizontal=False)
    pen.chain_dims([0, span * 1000], -1.4 * 1000, -14 * 100, horizontal=True)
    t_en = "Section A-A (longitudinal)" if longitudinal else "Section B-B (transverse)"
    t_fa = "برش طولی A-A" if longitudinal else "برش عرضی B-B"
    pen.mtext("S-TITLE", (span / 2, top + 1.6), f"{t_fa}  -  {t_en}", h=4.0)
    return _finish(doc, pen, (-6, -2.6, span + 6, top + 2.6), no, t_en, t_fa, info, 100, "section")


def _facade_openings(L: Layout, line: float):
    """Window/door x-ranges on the facade at y=line per floor."""
    out = []
    for fl in L.floors:
        for o in fl.openings:
            if o.horizontal and abs(o.line - line) < 1e-6:
                out.append((fl, o))
    return out


def elevation_sheet(L: Layout, side: str, no: str, info: ds.TitleInfo) -> Sheet:
    """side: front | back | east | west."""
    doc = new_doc()
    pen = AP(doc.modelspace(), scale=100)
    r = L.rules
    H = L.total_height
    span = L.W if side in ("front", "back") else L.D
    pen.mline("A-GRND", (-3, 0), (span + 3, 0))
    top = H + r.parapet_m
    pen.mpoly("A-ELEV", [(0, 0), (span, 0), (span, top), (0, top)], closed=True)
    # stair house silhouette
    sx0, sy0, sx1, sy1 = L.core
    a, b = (sx0, sx1) if side in ("front", "back") else (sy0, sy1)
    if side in ("back", "west"):
        a, b = span - b, span - a
    pen.mpoly("A-ELEV", [(a, top), (a, H + 2.6 + 0.3), (b, H + 2.6 + 0.3), (b, top)])
    for fl in L.floors[1:]:
        pen.mline("A-ELEV-MATL", (0, fl.z), (span, fl.z))
    pen.mline("A-ELEV", (0, H), (span, H))
    if side in ("front", "back"):
        line = 0.0 if side == "front" else L.D
        for fl, o in _facade_openings(L, line):
            x0, x1 = (o.a0, o.a1) if side == "front" else (span - o.a1, span - o.a0)
            z0 = fl.z + (o.sill if o.kind in ("window",) else 0.0)
            z1 = fl.z + o.head
            pen.mrect("A-ELEV-OPEN", x0, z0, x1, z1)
            if o.kind in ("window", "slider"):
                pen.mline("A-ELEV-OPEN", ((x0 + x1) / 2, z0), ((x0 + x1) / 2, z1))
                pen.mrect("A-ELEV-MATL", x0 - 0.05, z0 - 0.08, x1 + 0.05, z0)
            elif o.kind == "gate":
                for k in range(1, 6):
                    pen.mline("A-ELEV-OPEN", (x0, z0 + k * (z1 - z0) / 6), (x1, z0 + k * (z1 - z0) / 6))
            if o.tag:
                pen.mtext("A-AREA-IDEN", ((x0 + x1) / 2, z1 + 0.2), o.tag, h=1.6)
        if side == "front":
            for fl in L.floors:
                for bc in fl.balconies:
                    pen.mrect("A-BALC", bc.x0, fl.z - 0.15, bc.x1, fl.z)
                    pen.mrect("A-BALC", bc.x0, fl.z, bc.x1, fl.z + 1.0)
                    for k in range(1, int((bc.x1 - bc.x0) / 0.12)):
                        pen.mline("A-BALC", (bc.x0 + k * 0.12, fl.z), (bc.x0 + k * 0.12, fl.z + 1.0))
        pen.mpat("A-ELEV-MATL", [(0, 0), (span, 0), (span, 0.6), (0, 0.6)], pattern="AR-B816", sc=0.5)
    else:
        party = L.side_setback < 0.01
        pen.mpat("A-ELEV-MATL", [(0, 0), (span, 0), (span, top), (0, top)], pattern="ANSI37", sc=40)
        pen.mtext("A-AREA-IDEN", (span / 2, top / 2), "Party wall - no openings / دیوار مشترک با همسایه - بدون بازشو" if party else "Side facade", h=2.5)
    for z, en, _fa in _levels(L):
        pen.level_mark(-1.0 * 1000, z * 1000, z, side=-1)
    pen.level_mark(-1.0 * 1000, top * 1000, top, side=-1)
    pen.chain_dims([fl.z * 1000 for fl in L.floors] + [top * 1000], (span + 0.3) * 1000, -18 * 100, horizontal=False)
    names = {"front": ("Front (street) elevation", "نمای اصلی (رو به گذر)"), "back": ("Back elevation", "نمای پشت"),
             "east": ("East side elevation", "نمای جانبی شرقی"), "west": ("West side elevation", "نمای جانبی غربی")}
    en, fa_ = names[side]
    pen.notes((span + 4) * 1000, top * 1000, "Materials / مصالح", MATERIALS if side in ("front", "back") else MATERIALS[:1] + ["Party wall: cement plaster + isogam / اندود سیمان"], h=2.0)
    pen.mtext("S-TITLE", (span / 2, top + 4.0), f"{fa_}  -  {en}", h=4.0)
    return _finish(doc, pen, (-6, -1.5, span + 26, top + 5), no, en, fa_, info, 100, "elevation")


def site_sheet(L: Layout, no: str, info: ds.TitleInfo) -> Sheet:
    doc = new_doc()
    p = L.program
    pen = AP(doc.modelspace(), scale=200 if p.plot_depth_m > 30 else 100)
    PW, PD = p.plot_width_m, p.plot_depth_m
    sw = p.street_width_m
    south = p.street_side == "south"
    # plot boundary, y = 0 at street edge
    pen.mpoly("C-SITE", [(0, 0), (PW, 0), (PW, PD), (0, PD)], closed=True)
    sy0, sy1 = (-sw, 0) if south else (PD, PD + sw)
    pen.mline("C-SITE", (-6, sy0), (PW + 6, sy0)); pen.mline("C-SITE", (-6, sy1), (PW + 6, sy1))
    pen.mline("A-HIDDEN", (-6, (sy0 + sy1) / 2), (PW + 6, (sy0 + sy1) / 2))
    pen.mtext("C-SITE", (PW / 2, (sy0 + sy1) / 2 + 0.6), f"گذر {sw:g} متری  -  STREET {sw:g} m", h=3.0)
    by0 = PD - L.D if south else 0
    fp = [(L.side_setback, by0), (L.side_setback + L.W, by0), (L.side_setback + L.W, by0 + L.D), (L.side_setback, by0 + L.D)]
    pen.mpat("A-WALL-PATT", fp, pattern="ANSI31", sc=30)
    pen.mpoly("A-ELEV", fp, closed=True)
    pen.mtext("A-AREA-IDEN", (PW / 2, by0 + L.D / 2 + 0.6), f"{p.floors} طبقه  -  {p.floors} STOREYS", h=3.0)
    pen.mtext("A-AREA-IDEN", (PW / 2, by0 + L.D / 2 - 0.6), f"Footprint {L.W * L.D:.1f} m² ({L.W * L.D / (PW * PD) * 100:.0f}% of plot)", h=2.2)
    yard = (0, PD - L.D) if south else (L.D, PD)
    pen.mtext("C-SITE", (PW / 2, (yard[0] + yard[1]) / 2), "حیاط  YARD", h=2.6)
    for k in range(3):
        cx = PW * (k + 1) / 4
        cy = (yard[0] + yard[1]) / 2 + 1.5
        if yard[1] - yard[0] > 3:
            pen.mcircle("C-SITE-VEG", (cx, cy), 0.9); pen.mcircle("C-SITE-VEG", (cx, cy), 0.15)
    ent_y = 0 if south else PD
    pen.mpoly("S-NOTES", [(PW * 0.3, ent_y - (1.5 if south else -1.5)), (PW * 0.3, ent_y)])
    pen.mtext("S-NOTES", (PW * 0.3, ent_y - (2.2 if south else -2.2)), "ENTRY / ورودی", h=2.0)
    pen.chain_dims([0, PW * 1000], 0, -(sw * 1000 + 1500) if south else -1500, horizontal=True)
    pen.chain_dims(sorted({0, (PD - L.D) * 1000 if south else L.D * 1000, PD * 1000}), PW * 1000, -1500 * 2, horizontal=False)
    pen.north_arrow(((PW + 8) * 1000, PD * 1000), r=6)
    r = L.rules
    rows = [("Plot / زمین", f"{PW:g} x {PD:g} m = {PW * PD:.0f} m²"), ("Occupancy / سطح اشغال", f"{L.W * L.D / (PW * PD) * 100:.0f}% (rule {r.occupancy_pct:.0f}% + {r.occupancy_extra_m:g} m)"),
            ("Floors / طبقات", str(p.floors)), ("Total area / زیربنای کل", f"{L.W * L.D * p.floors:.0f} m²"),
            ("Density / تراکم", f"{L.W * L.D * p.floors / (PW * PD) * 100:.0f}%"), ("Street / گذر", f"{sw:g} m ({'south' if south else 'north'})")]
    pen.table((PW + 4) * 1000, (PD - 4) * 1000, ["Item / شرح", "Value / مقدار"], rows, [55, 60], title="Site data / مشخصات ملک")
    ext = (-8, min(-sw, 0) - 4, PW + 30, max(PD, PD + (0 if south else sw)) + 4)
    return _finish(doc, pen, ext, no, "Site plan", "پلان موقعیت (سایت پلان)", info, pen.scale, "site")


DESC = {"D1": ("Entrance door, security / درب ورودی ضد سرقت", "Steel"), "D2": ("Room door / درب اتاق", "Wood / MDF"),
        "D3": ("Wet-room / storage door / درب سرویس", "PVC / wood"), "D4": ("Roof door / درب بام", "Steel"),
        "D5": ("Balcony sliding door / درب کشویی بالکن", "UPVC double glazed"), "G1": ("Parking gate / درب پارکینگ", "Steel, motorised"),
        "W1": ("Living window / پنجره پذیرایی", "UPVC double glazed"), "W2": ("Bedroom/kitchen window / پنجره اتاق", "UPVC double glazed"),
        "W3": ("Bath/WC window / پنجره سرویس", "UPVC, obscure glass"), "W4": ("Stair window / پنجره راه پله", "UPVC")}


def schedule_sheet(L: Layout, no: str, info: ds.TitleInfo) -> Sheet:
    doc = new_doc()
    pen = AP(doc.modelspace(), scale=100)
    cnt: Counter = Counter()
    size: dict[str, tuple[float, float, float]] = {}
    for fl in L.floors:
        for o in fl.openings:
            if not o.tag:
                continue
            cnt[o.tag] += 1
            w = round(o.a1 - o.a0, 2)
            h = round(o.head - o.sill, 2)
            size.setdefault(o.tag, (w, h, o.sill))
    rows = []
    for tag in sorted(cnt):
        w, h, sill = size[tag]
        d, mat = DESC.get(tag, (tag, ""))
        rows.append((tag, d, f"{w:.2f}", f"{h:.2f}", f"{sill:.2f}", mat, cnt[tag]))
    pen.table(0, 0, ["Tag", "Description / شرح", "W (m)", "H (m)", "Sill", "Material / جنس", "No."], rows, [14, 80, 16, 16, 14, 45, 12], title="Door & window schedule / جدول درها و پنجره‌ها", rh=8)
    # elevation thumbnails
    x = 0.0
    for tag in sorted(cnt):
        w, h, sill = size[tag]
        y0 = -(len(rows) + 3) * 0.8 - 4
        pen.mrect("A-ELEV-OPEN", x, y0, x + w, y0 + h)
        if tag.startswith("W") or tag == "D5":
            pen.mline("A-ELEV-OPEN", (x + w / 2, y0), (x + w / 2, y0 + h))
        else:
            pen.mpoly("A-DOOR", [(x, y0), (x + w, y0 + h / 2), (x, y0 + h)])
        pen.mtext("A-AREA-IDEN", (x + w / 2, y0 - 0.5), tag, h=2.5)
        x += max(w, 1.0) + 1.2
    return _finish(doc, pen, (-1, -(len(rows) + 3) * 0.8 - 6, 20, 2), no, "Door / window schedule", "جدول درها و پنجره‌ها", info, 100, "schedule")


def cover_sheet(L: Layout, sheets: list[tuple[str, str, str]], no: str, info: ds.TitleInfo, checks: list[tuple[str, str, str, str]]) -> Sheet:
    doc = new_doc()
    pen = AP(doc.modelspace(), scale=100)
    p = L.program
    y = 0.0
    pen.mtext("S-TITLE", (0, 2.0), f"{p.project_name} - {p.city}", h=6, align="MIDDLE_LEFT")
    pen.mtext("S-TITLE", (0, 0.8), "مجموعه نقشه‌های معماری  -  Architectural drawing set", h=4, align="MIDDLE_LEFT")
    y = pen.table(0, -0.5 * 1000, ["Sheet", "Title", "عنوان"], sheets, [20, 70, 70], title="Sheet index / فهرست نقشه‌ها") / 1000
    y = pen.table(0, (y - 2.5) * 1000, ["Rule / ضابطه", "Required", "Provided", "OK"], checks, [70, 45, 45, 12], title="Code & municipal checks (configurable) / کنترل ضوابط") / 1000
    pen.notes(0, (y - 2.5) * 1000, "Assumptions / فرضیات", L.assumptions + [f"WARNING: {w}" for w in L.warnings], h=2.0)
    h = 1.5 + (len(sheets) + len(checks) + len(L.assumptions) + len(L.warnings) + 8) * 0.9
    return _finish(doc, pen, (-1, -h - 2, 22, 3), no, "Cover, index, rules & assumptions", "فهرست، ضوابط و فرضیات", info, 100, "cover")
