"""PDF / image -> DXF (sheet X-001). Free libraries only: PyMuPDF, OpenCV, ezdxf."""
from __future__ import annotations

import math
from typing import Any

import numpy as np

from .standards import SheetType, add_title_block, setup_doc

MAX_SEGMENTS = 20000


def _pdf_vector_segments(data: bytes):
    import pymupdf as fitz

    pdf = fitz.open(stream=data, filetype="pdf")
    page = pdf[0]
    segs, texts = [], []
    H = page.rect.height
    for d in page.get_drawings():
        for it in d["items"]:
            op = it[0]
            if op == "l":
                a, b = it[1], it[2]
                segs.append((a.x, H - a.y, b.x, H - b.y))
            elif op == "re":
                r = it[1]
                for (ax, ay, bx, by) in ((r.x0, r.y0, r.x1, r.y0), (r.x1, r.y0, r.x1, r.y1), (r.x1, r.y1, r.x0, r.y1), (r.x0, r.y1, r.x0, r.y0)):
                    segs.append((ax, H - ay, bx, H - by))
            elif op == "c":  # bezier -> chord
                a, b = it[1], it[4]
                segs.append((a.x, H - a.y, b.x, H - b.y))
            elif op == "qu":
                q = it[1]
                pts = [q.ul, q.ur, q.lr, q.ll, q.ul]
                for p, n in zip(pts, pts[1:]):
                    segs.append((p.x, H - p.y, n.x, H - n.y))
    for x0, y0, x1, y1, txt, *_ in page.get_text("words"):
        texts.append((x0, H - y1, (y1 - y0), txt))
    pix = None
    if not segs:  # scanned PDF -> rasterize
        pix = page.get_pixmap(dpi=150)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
        pix = img[:, :, :3][:, :, ::-1].copy()
    pts_per_mm = 72 / 25.4
    return segs, texts, pix, pts_per_mm


def _raster_segments(img_bgr):
    import cv2

    h, w = img_bgr.shape[:2]
    scale = 1600 / max(h, w)
    if scale < 1:
        img_bgr = cv2.resize(img_bgr, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 12)
    bw = cv2.morphologyEx(bw, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    edges = cv2.Canny(bw, 50, 150)
    H, W = gray.shape
    min_len = max(15, int(min(H, W) * 0.03))
    lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=60, minLineLength=min_len, maxLineGap=8)
    segs = []
    if lines is not None:
        for x0, y0, x1, y1 in np.asarray(lines).reshape(-1, 4).tolist():
            ang = math.degrees(math.atan2(y1 - y0, x1 - x0)) % 180
            # snap near-orthogonal lines (plans are mostly orthogonal)
            if ang < 4 or ang > 176:
                ym = (y0 + y1) / 2; y0 = y1 = ym
            elif abs(ang - 90) < 4:
                xm = (x0 + x1) / 2; x0 = x1 = xm
            segs.append((float(x0), float(H - y0), float(x1), float(H - y1)))
    return _dedupe(segs), (W, H)


def _dedupe(segs, tol=4.0):
    out, seen = [], set()
    for s in segs:
        key = tuple(int(round(v / tol)) for v in s)
        rkey = (key[2], key[3], key[0], key[1])
        if key in seen or rkey in seen:
            continue
        seen.add(key); out.append(s)
    return out


def vectorize(data: bytes, filename: str, *, real_width_m: float | None = None) -> tuple[Any, dict[str, Any]]:
    import cv2

    name = (filename or "").lower()
    is_pdf = name.endswith(".pdf") or data[:4] == b"%PDF"
    texts: list = []
    method = ""
    if is_pdf:
        segs, texts, raster, unit = _pdf_vector_segments(data)
        if segs:
            method = "pdf_vector (PyMuPDF)"
        else:
            segs, _ = _raster_segments(raster); texts = []
            method = "pdf_scanned -> raster (OpenCV Canny + Hough)"
    else:
        arr = np.frombuffer(data, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            raise ValueError("Unsupported image. Upload a PDF, JPG or PNG.")
        segs, _ = _raster_segments(img)
        method = "raster (OpenCV Canny + Hough)"
    segs = [s for s in segs if math.hypot(s[2] - s[0], s[3] - s[1]) > 1e-6][:MAX_SEGMENTS]
    if not segs:
        raise ValueError("No lines were found. Try a sharper, well-lit, straight-on photo.")
    xs = [v for s in segs for v in (s[0], s[2])]; ys = [v for s in segs for v in (s[1], s[3])]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    width_units = max(x1 - x0, 1e-6)
    if real_width_m and real_width_m > 0:
        k = real_width_m / width_units; scale_note = f"scaled so drawing width = {real_width_m} m"
    else:
        k = 20.0 / width_units; scale_note = "scale unknown: drawing width normalised to 20 m - rescale in CAD"
    T = lambda x, y: ((x - x0) * k, (y - y0) * k)
    doc = setup_doc(); msp = doc.modelspace()
    longest = max(math.hypot(s[2] - s[0], s[3] - s[1]) for s in segs)
    major = minor = 0
    for s in segs:
        L = math.hypot(s[2] - s[0], s[3] - s[1])
        layer = "X-VECT-MAJR" if L >= 0.12 * longest else "X-VECT-MINR"
        major += layer == "X-VECT-MAJR"; minor += layer == "X-VECT-MINR"
        msp.add_line(T(s[0], s[1]), T(s[2], s[3]), dxfattribs={"layer": layer})
    for tx, ty, th, txt in texts[:2000]:
        msp.add_text(txt, height=max(th * k * 0.8, 0.05), dxfattribs={"layer": "X-VECT-TEXT"}).set_placement(T(tx, ty))
    W, H = (x1 - x0) * k, (y1 - y0) * k
    add_title_block(msp, 0, 0, W, H, title=f"Vectorized: {filename or 'upload'}"[:60], sheet_no=SheetType.VECTORIZED.value,
                    notes="NOT FOR CONSTRUCTION - engineer review required")
    summary = {
        "sheet": SheetType.VECTORIZED.value, "method": method, "segments": len(segs),
        "major_lines": major, "minor_lines": minor, "texts": len(texts),
        "extent_m": [round(W, 2), round(H, 2)], "scale_note": scale_note,
        "warnings": ["Automatic vectorization is approximate: check walls, openings and scale before use."]
        + (["Photo input: perspective is not corrected - shoot straight-on."] if not is_pdf else []),
    }
    return doc, summary
