"""Plan import: grid axes, spacings and column positions from a PNG/JPG, PDF or DXF plan -> DRAFT frame model.

Offline-only methods (no heavy dependencies):
  * DXF  - ezdxf: axis-parallel LINE/LWPOLYLINE segments, TEXT/MTEXT labels and dimensions, small closed outlines,
           SOLIDs and HATCHes as columns; units from $INSUNITS or the drawing extents.
  * PDF  - pypdf: vector path operators (m/l/re with the current transformation matrix) + positioned text.
  * image- numpy projection profiles of dark pixels (long horizontal/vertical runs = grid/wall lines), dark-fill
           ratio at each grid intersection = column; dimension text via pytesseract OCR only if it is installed.
The extracted geometry is generic (any number of axes / unequal spacings); the scale comes from dimension text
between adjacent axes, from the prompt («دهانه اول ۵ متر», "first bay 5 m", "total length 15 m"), or is assumed
(median spacing 5 m) with low confidence. Every result is a DRAFT for engineer review.
"""

from __future__ import annotations

import io
import math
import re
from dataclasses import dataclass, field
from statistics import median
from typing import Any

FA_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫", "01234567890123456789.")
Seg = tuple[float, float, float, float]


@dataclass
class Geometry:
    segs: list[Seg] = field(default_factory=list)
    texts: list[tuple[float, float, str]] = field(default_factory=list)
    blobs: list[tuple[float, float, float]] = field(default_factory=list)  # (cx, cy, size): filled rects / column outlines
    unit_m: float | None = None  # metres per source unit when known (DXF)
    raster: Any = None  # dark-pixel mask for images
    source: str = ""


def _letters(i: int) -> str:
    s, n = "", i
    while True:
        s = chr(65 + n % 26) + s
        n = n // 26 - 1
        if n < 0:
            return s


# ------------------------------------------------------------------------------------------------- readers
def read_dxf(data: bytes) -> Geometry:
    import ezdxf

    doc = ezdxf.read(io.StringIO(data.decode("utf-8", errors="replace")))
    msp = doc.modelspace()
    g = Geometry(source="dxf")
    units = {1: 0.0254, 2: 0.3048, 4: 0.001, 5: 0.01, 6: 1.0}.get(int(doc.header.get("$INSUNITS", 0) or 0))
    for e in msp:
        t = e.dxftype()
        if t == "LINE":
            a, b = e.dxf.start, e.dxf.end
            g.segs.append((a[0], a[1], b[0], b[1]))
        elif t in ("LWPOLYLINE", "POLYLINE"):
            pts = [(p[0], p[1]) for p in (e.get_points("xy") if t == "LWPOLYLINE" else [v.dxf.location for v in e.vertices])]
            closed = bool(e.closed if t == "LWPOLYLINE" else e.is_closed)
            if closed and len(pts) >= 4:
                xs, ys = [p[0] for p in pts], [p[1] for p in pts]
                w, h = max(xs) - min(xs), max(ys) - min(ys)
                g.blobs.append(((max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2, max(w, h)))
            for p, q in zip(pts, pts[1:] + (pts[:1] if closed else [])):
                g.segs.append((p[0], p[1], q[0], q[1]))
        elif t in ("TEXT", "MTEXT"):
            s = e.dxf.text if t == "TEXT" else e.plain_text()
            p = e.dxf.insert
            if t == "TEXT" and e.dxf.hasattr("align_point") and (e.dxf.halign or e.dxf.valign):
                p = e.dxf.align_point
            g.texts.append((p[0], p[1], s.strip()))
        elif t == "DIMENSION":
            try:
                v = e.get_measurement()
                p = e.dxf.text_midpoint if e.dxf.hasattr("text_midpoint") else e.dxf.defpoint
                g.texts.append((p[0], p[1], f"{float(v):.0f}"))
            except Exception:  # noqa: BLE001
                pass
    if units is None:  # guess: a building plan larger than 300 units is drawn in mm
        xs = [c for s in g.segs for c in (s[0], s[2])] or [0.0]
        units = 0.001 if (max(xs) - min(xs)) > 300 else 1.0
    g.unit_m = units
    return g


def read_pdf(data: bytes) -> Geometry:
    from pypdf import PdfReader
    from pypdf.generic import ContentStream

    reader = PdfReader(io.BytesIO(data))
    page = reader.pages[0]
    g = Geometry(source="pdf")

    def mul(m, n):
        a, b, c, d, e, f = m
        A, B, C, D, E, F = n
        return (a * A + b * C, a * B + b * D, c * A + d * C, c * B + d * D, e * A + f * C + E, e * B + f * D + F)

    def tp(m, x, y):
        return (m[0] * x + m[2] * y + m[4], m[1] * x + m[3] * y + m[5])

    ctm, stack, cur, start, poly = (1, 0, 0, 1, 0, 0), [], None, None, []
    ops = ContentStream(page.get_contents(), reader).operations
    for args, op in ops:
        op = op.decode() if isinstance(op, bytes) else op
        if op == "q":
            stack.append(ctm)
        elif op == "Q":
            ctm = stack.pop() if stack else ctm
        elif op == "cm":
            ctm = mul(tuple(float(a) for a in args), ctm)
        elif op == "m":
            cur = start = tp(ctm, float(args[0]), float(args[1])); poly = [cur]
        elif op == "l" and cur is not None:
            nxt = tp(ctm, float(args[0]), float(args[1]))
            g.segs.append((*cur, *nxt)); cur = nxt; poly.append(nxt)
        elif op == "h" and cur is not None and start is not None:
            g.segs.append((*cur, *start)); cur = start
            if 4 <= len(poly) <= 5:  # closed quad drawn as a path (e.g. matplotlib / most CAD PDF exporters)
                pxs = [p[0] for p in poly]; pys = [p[1] for p in poly]
                g.blobs.append(((max(pxs) + min(pxs)) / 2, (max(pys) + min(pys)) / 2,
                                max(max(pxs) - min(pxs), max(pys) - min(pys))))
        elif op == "re":
            x, y, w, h = (float(a) for a in args)
            p = [tp(ctm, x, y), tp(ctm, x + w, y), tp(ctm, x + w, y + h), tp(ctm, x, y + h)]
            ww = abs(p[2][0] - p[0][0]); hh = abs(p[2][1] - p[0][1])
            g.blobs.append(((p[0][0] + p[2][0]) / 2, (p[0][1] + p[2][1]) / 2, max(ww, hh)))
            for a, b in zip(p, p[1:] + p[:1]):
                g.segs.append((*a, *b))

    def visit(text, cm, tm, font, size):
        s = (text or "").strip()
        if s:
            x, y = tp(cm, tm[4], tm[5])
            g.texts.append((x, y, s))

    page.extract_text(visitor_text=visit)
    return g


def read_image(data: bytes) -> Geometry:
    import numpy as np
    from PIL import Image

    im = Image.open(io.BytesIO(data)).convert("L")
    scale = 1.0
    if max(im.size) > 2400:
        scale = 2400 / max(im.size)
        im = im.resize((int(im.size[0] * scale), int(im.size[1] * scale)))
    a = np.asarray(im)
    g = Geometry(source="image", raster=(a < 110)[::-1])  # flip so y grows upwards like CAD
    try:  # optional OCR of dimension / label text
        import pytesseract

        d = pytesseract.image_to_data(im, output_type=pytesseract.Output.DICT)
        H = a.shape[0]
        for s, x, y, w, h in zip(d["text"], d["left"], d["top"], d["width"], d["height"]):
            if s.strip():
                g.texts.append((x + w / 2, H - (y + h / 2), s.strip()))
    except Exception:  # noqa: BLE001 - OCR is optional
        pass
    return g


# ------------------------------------------------------------------------------------------------- detection
def _cluster(vals: list[tuple[float, float]], tol: float) -> list[tuple[float, float]]:
    """(coord, weight) -> merged (weighted coord, total weight) for coords closer than tol."""
    out: list[list[float]] = []
    for c, w in sorted(vals):
        if out and c - out[-1][2] <= tol:
            o = out[-1]
            o[0] += c * w; o[1] += w; o[2] = c
        else:
            out.append([c * w, w, c])
    return [(o[0] / o[1], o[1]) for o in out if o[1] > 0]


def _axis_lines(g: Geometry) -> tuple[list[float], list[float], float]:
    """Grid lines along X (x = const, vertical in plan) and along Y (y = const)."""
    if g.raster is not None:
        m = g.raster
        cols = m.sum(axis=0).astype(float); rows = m.sum(axis=1).astype(float)
        ys_, xs_ = m.nonzero()
        if len(xs_) == 0:
            return [], [], 1.0
        ext = float(max(xs_.max() - xs_.min(), ys_.max() - ys_.min()))
        vx = [(float(i), float(v)) for i, v in enumerate(cols) if v >= 0.45 * (ys_.max() - ys_.min())]
        vy = [(float(j), float(v)) for j, v in enumerate(rows) if v >= 0.45 * (xs_.max() - xs_.min())]
    else:
        xs = [c for s in g.segs for c in (s[0], s[2])]
        ys = [c for s in g.segs for c in (s[1], s[3])]
        if not xs:
            return [], [], 1.0
        ext = max(max(xs) - min(xs), max(ys) - min(ys)) or 1.0
        tol0 = ext * 0.002
        vxa: dict[int, list[float]] = {}
        vya: dict[int, list[float]] = {}
        for x1, y1, x2, y2 in g.segs:
            if abs(x1 - x2) <= tol0 and abs(y2 - y1) > tol0:
                a = vxa.setdefault(round(x1 / tol0), [0.0, 0.0]); L = abs(y2 - y1); a[0] += L; a[1] += float(x1) * L
            elif abs(y1 - y2) <= tol0 and abs(x2 - x1) > tol0:
                a = vya.setdefault(round(y1 / tol0), [0.0, 0.0]); L = abs(x2 - x1); a[0] += L; a[1] += float(y1) * L
        span_y, span_x = max(ys) - min(ys), max(xs) - min(xs)
        vx = [(a[1] / a[0], a[0]) for a in vxa.values() if a[0] >= 0.4 * span_y]
        vy = [(a[1] / a[0], a[0]) for a in vya.values() if a[0] >= 0.4 * span_x]
    tol = ext * 0.04  # wall / beam outline pairs around an axis merge into the axis
    gx = [c for c, _ in _cluster(vx, tol)]
    gy = [c for c, _ in _cluster(vy, tol)]
    return gx, gy, ext


def _border_trim(g: Geometry, gx: list[float], gy: list[float], ext: float) -> tuple[list[float], list[float]]:
    """Drop sheet borders / viewport frames: an outermost line is kept only if a perpendicular axis runs past it.
    Real grid axes overshoot to their bubbles; frames enclose everything. Applied repeatedly from outside in."""
    if g.raster is not None or not g.segs:
        return gx, gy
    tol = ext * 0.01

    def extent(c: float, vertical: bool) -> tuple[float, float]:
        lo, hi = float("inf"), float("-inf")
        for x1, y1, x2, y2 in g.segs:
            if vertical and abs(x1 - c) <= tol and abs(x2 - c) <= tol:
                lo, hi = min(lo, y1, y2), max(hi, y1, y2)
            elif not vertical and abs(y1 - c) <= tol and abs(y2 - c) <= tol:
                lo, hi = min(lo, x1, x2), max(hi, x1, x2)
        return lo, hi

    gx, gy = list(gx), list(gy)
    for _ in range(6):
        ex = {c: extent(c, True) for c in gx}; ey = {c: extent(c, False) for c in gy}
        drop_x = [c for c in (gx[:1] + gx[-1:]) if not any(lo < c - tol and hi > c + tol for lo, hi in
                                                            (ey[o] for o in gy)) or
                  not any(lo < c - tol for lo, _ in (ey[o] for o in gy)) and c == gx[0] or
                  not any(hi > c + tol for _, hi in (ey[o] for o in gy)) and c == gx[-1]]
        drop_y = [c for c in (gy[:1] + gy[-1:]) if not any(lo < c - tol for lo, _ in (ex[o] for o in gx)) and c == gy[0] or
                  not any(hi > c + tol for _, hi in (ex[o] for o in gx)) and c == gy[-1]]
        if not drop_x and not drop_y:
            break
        gx = [c for c in gx if c not in drop_x]; gy = [c for c in gy if c not in drop_y]
        if len(gx) < 2 or len(gy) < 2:
            break
    return gx, gy


_NUM = re.compile(r"^\s*(\d+(?:[.,]\d+)?)\s*(m|cm|mm|متر)?\s*$")


def _num(s: str) -> tuple[float, str] | None:
    m = _NUM.match(s.translate(FA_DIGITS))
    if not m:
        return None
    return float(m.group(1).replace(",", ".")), (m.group(2) or "")


def _to_m(v: float, unit: str) -> float:
    if unit in ("m", "متر"):
        return v
    if unit == "cm":
        return v / 100
    if unit == "mm":
        return v / 1000
    return v / 1000 if v >= 100 else v / 100 if v >= 25 else v


def _labels(coords: list[float], g: Geometry, along_x: bool, ext: float, default) -> tuple[list[str], int]:
    """Bubble labels: short text (1-2 letters or digits) lying on the axis line beyond the drawing."""
    labels, found = [], 0
    for i, c in enumerate(coords):
        best = None
        for x, y, s in g.texts:
            s2 = s.strip()
            if not re.fullmatch(r"[A-Z]{1,2}|\d{1,2}|[A-Z]\d?'?", s2):
                continue
            d = abs(x - c) if along_x else abs(y - c)
            if d < ext * 0.015 and (best is None or d < best[0]):
                best = (d, s2)
        if best:
            labels.append(best[1]); found += 1
        else:
            labels.append(default(i))
    return labels, found


def _spacing_scale(gx: list[float], gy: list[float], g: Geometry) -> tuple[float | None, int]:
    """metres per source unit from dimension numbers placed between adjacent axes."""
    ratios = []
    for coords, along in ((gx, True), (gy, False)):
        for a, b in zip(coords, coords[1:]):
            for x, y, s in g.texts:
                n = _num(s)
                if not n:
                    continue
                c = x if along else y
                if a + (b - a) * 0.2 < c < b - (b - a) * 0.2:
                    vm = _to_m(*n)
                    if 1.0 <= vm <= 20.0 and abs(vm / (b - a) - (ratios and median(ratios) or vm / (b - a))) <= 0.3 * vm / (b - a):
                        ratios.append(vm / (b - a))
    return (median(ratios), len(ratios)) if ratios else (None, 0)


def _columns(g: Geometry, gx: list[float], gy: list[float], ext: float) -> tuple[list[list[int]], str]:
    present = []
    if g.raster is not None:
        m = g.raster
        r = max(3, int(ext * 0.008))
        for i, x in enumerate(gx):
            for j, y in enumerate(gy):
                w = m[max(0, int(y) - r):int(y) + r + 1, max(0, int(x) - r):int(x) + r + 1]
                if w.size and w.mean() > 0.55:
                    present.append([i, j])
        return present, "dark fill at grid intersections"
    tol = ext * 0.02
    for i, x in enumerate(gx):
        for j, y in enumerate(gy):
            if any(abs(cx - x) < tol and abs(cy - y) < tol and size < ext * 0.08 for cx, cy, size in g.blobs):
                present.append([i, j])
    return present, "closed outlines / filled rectangles at grid intersections"


def _prompt_numbers(text: str) -> dict[str, Any]:
    t = (text or "").translate(FA_DIGITS).lower()
    out: dict[str, Any] = {}
    m = re.search(r"(\d{1,2})\s*(?:-|\s)?(?:stor(?:e)?(?:y|ies|eys)|floors?|طبقه)", t)
    if m:
        out["storeys"] = int(m.group(1))
    m = re.search(r"(?:stor(?:e)?y height|floor height|ارتفاع(?: هر)? طبقه|ارتفاع طبقات)\s*[:=]?\s*(\d+(?:\.\d+)?)", t) or \
        re.search(r"stor(?:e)?(?:y|ies|eys)\s*(?:of|@|,)?\s*(\d(?:\.\d+)?)\s*m\b", t) or \
        re.search(r"طبقه\s*(?:با ارتفاع|،)?\s*(\d(?:\.\d+)?)\s*متر", t)
    if m:
        out["storey_height_m"] = float(m.group(1))
    m = re.search(r"(?:first bay|first span|bay|دهانه(?: اول)?|فاصله محورها)\s*[:=]?\s*(\d+(?:\.\d+)?)\s*(?:m|متر)", t)
    if m:
        out["first_span_m"] = float(m.group(1))
    return out


def extract(data: bytes, filename: str, prompt: str = "") -> dict[str, Any]:
    """-> draft dict (spans, labels, columns, confidences, notes)."""
    ext_ = filename.lower().rsplit(".", 1)[-1]
    if ext_ == "dxf":
        g = read_dxf(data)
    elif ext_ == "pdf":
        g = read_pdf(data)
    elif ext_ in ("png", "jpg", "jpeg", "webp", "gif", "bmp"):
        g = read_image(data)
    else:
        raise ValueError(f"unsupported plan file type: .{ext_}")
    gx, gy, ext = _axis_lines(g)
    gx, gy = _border_trim(g, gx, gy, ext)
    notes: list[str] = []
    if len(gx) < 2 or len(gy) < 2:
        raise ValueError("could not find at least two grid axes in each direction")
    pn = _prompt_numbers(prompt)
    scale, n_dims = (g.unit_m, -1) if g.unit_m else _spacing_scale(gx, gy, g)
    if scale and n_dims != -1:
        notes.append(f"scale from {n_dims} dimension text(s) between axes")
    if not scale and pn.get("first_span_m"):
        scale = pn["first_span_m"] / (gx[1] - gx[0]); notes.append("scale from the first bay given in the prompt")
    scale_conf = 0.95 if n_dims == -1 else 0.85 if n_dims >= 2 else 0.6 if scale else 0.25
    if not scale:
        med = median([b - a for a, b in zip(gx, gx[1:])] + [b - a for a, b in zip(gy, gy[1:])])
        scale = 5.0 / med
        notes.append("no dimension text found: spacings ASSUMED from a 5 m median bay - give one bay in chat")
    sx = [round((b - a) * scale, 2) for a, b in zip(gx, gx[1:])]
    sy = [round((b - a) * scale, 2) for a, b in zip(gy, gy[1:])]
    lx, fx = _labels(gx, g, True, ext, lambda i: str(i + 1))
    ly, fy = _labels(gy, g, False, ext, _letters)
    cols, method = _columns(g, gx, gy, ext)
    if not cols:
        cols = [[i, j] for i in range(len(gx)) for j in range(len(gy))]
        notes.append("no column outlines detected: columns assumed at every grid intersection")
        col_conf = 0.3
    else:
        col_conf = 0.8
        missing = len(gx) * len(gy) - len(cols)
        if missing:
            notes.append(f"{missing} grid intersection(s) without a column (shown hollow); the analysis model still "
                         "places columns at every intersection")
    grid_conf = round(min(0.95, 0.55 + 0.4 * (fx + fy) / (len(gx) + len(gy))), 2)
    return {
        "source": g.source, "filename": filename, "spans_x_m": sx, "spans_y_m": sy, "labels_x": lx, "labels_y": ly,
        "columns": cols, "storeys": pn.get("storeys"), "storey_height_m": pn.get("storey_height_m"),
        "confidence": {"grid": grid_conf, "spacing": scale_conf, "columns": col_conf,
                       "overall": round(min(grid_conf, scale_conf, col_conf), 2)},
        "method": {"dxf": "ezdxf vector parse", "pdf": "pypdf vector + text parse",
                   "image": "pixel projection profiles" + (" + OCR" if g.texts else "")}[g.source] + "; columns: " + method,
        "notes": notes,
    }


# ------------------------------------------------------------------------------------------------- edits
def _axis_index(labels: list[str], name: str) -> int | None:
    name = name.strip().upper()
    return labels.index(name) if name in labels else None


def apply_edits(draft: dict[str, Any], text: str) -> tuple[dict[str, Any], list[str]]:
    """Chat edits on a draft: 'spacing axis 2-3 = 4.5m' / «فاصله محور ۲ تا ۳ = ۴.۵ متر», 'storeys 4' / «۴ طبقه»,
    'storey height 3.5', 'remove column B-2' / «حذف ستون B-2», 'add column B-2', 'scale x2'."""
    t = (text or "").translate(FA_DIGITS)
    d = {**draft, "spans_x_m": list(draft["spans_x_m"]), "spans_y_m": list(draft["spans_y_m"]),
         "columns": [list(c) for c in draft.get("columns", [])], "notes": list(draft.get("notes", []))}
    done: list[str] = []
    for m in re.finditer(r"(?:spacing|distance|span|فاصله|دهانه)\s*(?:between\s*)?(?:axis|axes|grid|محور(?:های)?)?\s*"
                         r"([A-Za-z]{1,2}|\d{1,2})\s*(?:-|–|to|تا|و)\s*([A-Za-z]{1,2}|\d{1,2})\s*(?:=|:|is|به|را)?\s*"
                         r"(\d+(?:\.\d+)?)\s*(m|cm|mm|متر)?", t, re.IGNORECASE):
        a, b, v = m.group(1).upper(), m.group(2).upper(), _to_m(float(m.group(3)), m.group(4) or "m")
        for key, labels in (("spans_x_m", d["labels_x"]), ("spans_y_m", d["labels_y"])):
            ia, ib = _axis_index(labels, a), _axis_index(labels, b)
            if ia is not None and ib is not None and abs(ia - ib) == 1:
                d[key][min(ia, ib)] = round(v, 3); done.append(f"spacing {a}-{b} = {v:g} m")
    m = re.search(r"(\d{1,2})\s*(?:-|\s)?(?:stor(?:e)?(?:y|ies|eys)|floors?|طبقه)|(?:storeys?|stories|floors|تعداد طبقات)\s*[:=]?\s*(\d{1,2})", t, re.I)
    if m:
        d["storeys"] = int(m.group(1) or m.group(2)); done.append(f"storeys = {d['storeys']}")
    m = re.search(r"(?:stor(?:e)?y height|floor height|ارتفاع(?: هر)? طبقه|ارتفاع طبقات)\s*[:=]?\s*(\d+(?:\.\d+)?)", t, re.I)
    if m:
        d["storey_height_m"] = float(m.group(1)); done.append(f"storey height = {d['storey_height_m']:g} m")
    for m in re.finditer(r"(remove|delete|add|حذف|اضافه)\s*(?:column|ستون)\s*([A-Za-z]{1,2})\s*-\s*(\d{1,2})", t, re.I):
        j, i = _axis_index(d["labels_y"], m.group(2)), _axis_index(d["labels_x"], m.group(3))
        if i is None or j is None:
            continue
        if m.group(1).lower() in ("remove", "delete", "حذف"):
            d["columns"] = [c for c in d["columns"] if c != [i, j]]; done.append(f"column {m.group(2).upper()}-{m.group(3)} removed")
        elif [i, j] not in d["columns"]:
            d["columns"].append([i, j]); done.append(f"column {m.group(2).upper()}-{m.group(3)} added")
    m = re.search(r"(?:first bay|first span|دهانه اول)\s*(?:is|=|:|باید)?\s*(\d+(?:\.\d+)?)\s*(m|cm|mm|متر)?", t, re.I)
    if m and d["spans_x_m"]:  # re-scale the whole extraction from one known bay
        f = _to_m(float(m.group(1)), m.group(2) or "m") / d["spans_x_m"][0]
        d["spans_x_m"] = [round(v * f, 3) for v in d["spans_x_m"]]; d["spans_y_m"] = [round(v * f, 3) for v in d["spans_y_m"]]
        done.append(f"re-scaled from first bay = {d['spans_x_m'][0]:g} m")
    m = re.search(r"(?:scale|مقیاس)\s*(?:x|×|\*)\s*(\d+(?:\.\d+)?)", t, re.I)
    if m:
        f = float(m.group(1))
        d["spans_x_m"] = [round(v * f, 3) for v in d["spans_x_m"]]; d["spans_y_m"] = [round(v * f, 3) for v in d["spans_y_m"]]
        done.append(f"all spacings x{f:g}")
    c = dict(d.get("confidence") or {})
    if any(x.startswith(("spacing", "re-scaled", "all spacings")) for x in done):
        c["spacing"] = max(c.get("spacing", 0), 0.9)  # the engineer confirmed the dimensions
        d["notes"] = [n for n in d["notes"] if "ASSUMED" not in n]
    if any(x.startswith("column") for x in done):
        c["columns"] = max(c.get("columns", 0), 0.9)
    if c and done:
        c["overall"] = round(min(c.get("grid", 1), c.get("spacing", 1), c.get("columns", 1)), 2)
        d["confidence"] = c
    return d, done


def is_edit(text: str) -> bool:
    return bool(apply_edits({"spans_x_m": [], "spans_y_m": [], "labels_x": [], "labels_y": [], "columns": []}, text)[1]) or bool(
        re.search(r"(?:spacing|فاصله|دهانه)\s*(?:axis|محور)|(?:remove|add|حذف|اضافه)\s*(?:column|ستون)", (text or "").translate(FA_DIGITS), re.I))


# ------------------------------------------------------------------------------------------------- payload
def frame_inputs(draft: dict[str, Any]) -> dict[str, Any]:
    return {"storeys": draft.get("storeys") or 1, "storey_height_m": draft.get("storey_height_m") or 3.2,
            "spans_x_m": draft["spans_x_m"], "spans_y_m": draft["spans_y_m"],
            "bays_x": len(draft["spans_x_m"]), "bays_y": len(draft["spans_y_m"])}


def payload(draft: dict[str, Any], *, revision: int = 1, edits: list[str] | None = None) -> dict[str, Any]:
    missing = []
    if not draft.get("storeys"):
        missing.append("storeys (e.g. '4 storeys' / «۴ طبقه»)")
    return {
        "kind": "plan_import", "status": "check", "draft": draft, "inputs": {"draft": draft},
        "revision": revision, "edits": edits or [], "missing": missing,
        "frame_inputs": frame_inputs(draft),
        "message": "Imported model is a DRAFT: approve 'Imported model review' on the Approvals page before analysis.",
    }


def summary(p: dict[str, Any]) -> str:
    d = p.get("draft") or {}
    return (f"Imported model review: {len(d.get('spans_x_m', [])) + 1}x{len(d.get('spans_y_m', [])) + 1} axes, "
            f"spans X {d.get('spans_x_m')} / Y {d.get('spans_y_m')} m, {len(d.get('columns', []))} columns, "
            f"{d.get('storeys') or '?'} storeys, confidence {d.get('confidence', {}).get('overall')}")


def markdown(p: dict[str, Any], lang: str = "en") -> str:
    d = p["draft"]; c = d.get("confidence", {})
    gx = " | ".join(f"{a}–{b}: {v:g} m" for a, b, v in zip(d["labels_x"], d["labels_x"][1:], d["spans_x_m"]))
    gy = " | ".join(f"{a}–{b}: {v:g} m" for a, b, v in zip(d["labels_y"], d["labels_y"][1:], d["spans_y_m"]))
    lines = [
        "**Imported model (DRAFT) / مدل وارد شده (پیش‌نویس)**",
        f"Source: {d.get('filename')} ({d.get('method')})",
        f"- Axes along X (numbered): {gx}",
        f"- Axes along Y (lettered): {gy}",
        f"- Columns detected: {len(d.get('columns', []))} of {(len(d['spans_x_m']) + 1) * (len(d['spans_y_m']) + 1)} intersections",
        f"- Storeys: {d.get('storeys') or '— (give it in chat)'}; storey height: {d.get('storey_height_m') or 3.2} m",
        f"- Confidence: grid {c.get('grid')}, spacing {c.get('spacing')}, columns {c.get('columns')} (overall {c.get('overall')})",
    ]
    lines += [f"- Note: {n}" for n in d.get("notes", [])]
    if p.get("edits"):
        lines.append("- Applied edits: " + "; ".join(p["edits"]))
    if p.get("missing"):
        lines.append("- Missing: " + "; ".join(p["missing"]))
    lines += ["", "Edit in chat, e.g. `spacing axis 2-3 = 4.5m`, `remove column B-2`, `4 storeys`, `storey height 3.3`"
              " / «فاصله محور ۲ تا ۳ = ۴.۵ متر»، «حذف ستون B-2»، «۴ طبقه».",
              "An approval item **Imported model review** was created. Approve it on the Approvals page, then ask "
              "`analyze the imported model` / «مدل وارد شده را تحلیل کن». Rejecting it with a reason (e.g. the edits "
              "above) creates a revised draft."]
    return "\n".join(lines)


# ------------------------------------------------------------------------------------------------- preview
def preview_png(draft: dict[str, Any]) -> bytes:
    """Plan preview: axes with bubbles, spacing dims, detected columns (filled) and missing ones (hollow)."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    xs = [0.0]
    for v in draft["spans_x_m"]:
        xs.append(xs[-1] + v)
    ys = [0.0]
    for v in draft["spans_y_m"]:
        ys.append(ys[-1] + v)
    W, H = xs[-1], ys[-1]
    fig, ax = plt.subplots(figsize=(7, 7 * max(H, 1) / max(W, 1) * 0.9 + 1.2))
    e = max(W, H) * 0.12
    for x, lab in zip(xs, draft["labels_x"]):
        ax.plot([x, x], [-e * 0.6, H + e * 0.6], color="#c0392b", lw=0.8, ls="-.")
        for yy in (-e * 0.85, H + e * 0.85):
            ax.add_patch(plt.Circle((x, yy), e * 0.22, fill=False, color="#333")); ax.text(x, yy, lab, ha="center", va="center", fontsize=9)
    for y, lab in zip(ys, draft["labels_y"]):
        ax.plot([-e * 0.6, W + e * 0.6], [y, y], color="#c0392b", lw=0.8, ls="-.")
        for xx in (-e * 0.85, W + e * 0.85):
            ax.add_patch(plt.Circle((xx, y), e * 0.22, fill=False, color="#333")); ax.text(xx, y, lab, ha="center", va="center", fontsize=9)
    for a, b, v in zip(xs, xs[1:], draft["spans_x_m"]):
        ax.annotate("", (a, -e * 0.35), (b, -e * 0.35), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.text((a + b) / 2, -e * 0.3, f"{v:g}", ha="center", va="bottom", fontsize=8)
    for a, b, v in zip(ys, ys[1:], draft["spans_y_m"]):
        ax.annotate("", (-e * 0.35, a), (-e * 0.35, b), arrowprops=dict(arrowstyle="<->", lw=0.6))
        ax.text(-e * 0.3, (a + b) / 2, f"{v:g}", ha="left", va="center", fontsize=8, rotation=90)
    have = {tuple(c) for c in draft.get("columns", [])}
    s = max(W, H) * 0.025
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            ax.add_patch(plt.Rectangle((x - s / 2, y - s / 2), s, s, color="#1f4e79", fill=(i, j) in have, lw=1))
    c = draft.get("confidence", {})
    ax.set_title(f"Imported model DRAFT - {draft.get('filename')}\nconfidence: grid {c.get('grid')} | spacing {c.get('spacing')} | "
                 f"columns {c.get('columns')}", fontsize=9)
    ax.set_aspect("equal"); ax.axis("off")
    buf = io.BytesIO(); fig.savefig(buf, format="png", dpi=110, bbox_inches="tight"); plt.close(fig)
    return buf.getvalue()


# ------------------------------------------------------------------------------------------------- approval adapter
def _adapter_run(inputs: dict[str, Any]) -> dict[str, Any]:
    return payload(inputs["draft"])


def _adapter_intents(text: str, inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    d, done = apply_edits(inputs["draft"], text)
    return {"inputs": {"draft": d}} if done else {}


def register() -> None:
    from app.application import engineering_modules as em

    em.register_adapter(em.ModuleAdapter(kind="plan_import", label="Imported model review", assumption_modules=[],
                                         run=_adapter_run, summary=summary, intents=_adapter_intents,
                                         extra={"reject_hint": REJECT_HINT}))


REJECT_HINT = ("I could not turn the rejection reason into a change to the imported model. Please say what to change, e.g. "
               "'spacing axis 2-3 = 4.5m', 'first bay 6 m', 'remove column B-2', 'add column C-4', '4 storeys', "
               "'storey height 3.3'.\n— دلیل رد را به تغییر مشخصی تبدیل نکردم؛ مثلاً: «فاصله محور ۲ تا ۳ = ۴.۵ متر»، "
               "«دهانه اول ۶ متر»، «حذف ستون B-2»، «۴ طبقه»، «ارتفاع طبقه ۳.۳».")
