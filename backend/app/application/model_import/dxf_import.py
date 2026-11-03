"""DXF (ASCII) -> SAIA neutral model. Geometry only: members come from LINE / POLYLINE entities and their
layer names; sections and loads are asked for in the engineer review.

Layer keywords (case-insensitive, English or Persian): COL / COLUMN / ستون -> column, BEAM / GIRDER / تیر
-> beam, BRACE / مهاربند -> brace, SLAB / FLOOR / دال / سقف -> floor outline. Lines on other layers are
classified by direction (vertical = column, horizontal = beam, inclined = brace) and listed as approximated.
A layer named like a catalog profile (IPE300, HEB200, BOX200x10 ...) gives that section directly.
A 2D plan (all Z equal) is extruded to storeys: column positions are small closed polylines / circles /
points on a column layer, otherwise every beam intersection; the review confirms storey count and height.
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np

from app.application.model_import.common import assume, issue, new_model

INSUNITS = {1: 0.0254, 2: 0.3048, 4: 1e-3, 5: 1e-2, 6: 1.0, 14: 0.1}
KW = (("column", re.compile(r"col|ستون|column|pillar", re.I)), ("brace", re.compile(r"brac|مهاربند|bracing|diag", re.I)),
      ("beam", re.compile(r"beam|girder|تیر|joist", re.I)), ("slab", re.compile(r"slab|floor|دال|سقف|deck", re.I)))


def _pairs(text: str) -> list[tuple[int, str]]:
    lines = text.splitlines()
    out = []
    for k in range(0, len(lines) - 1, 2):
        try:
            out.append((int(lines[k].strip()), lines[k + 1].strip()))
        except ValueError:
            continue
    return out


def read_entities(text: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    pairs = _pairs(text)
    header: dict[str, Any] = {}
    ents: list[dict[str, Any]] = []
    section = None
    cur: dict[str, Any] | None = None
    var = None
    poly: dict[str, Any] | None = None
    for code, val in pairs:
        if code == 0:
            if cur is not None:
                if cur["type"] == "VERTEX" and poly is not None:
                    poly["pts"].append(tuple(cur.get(k, 0.0) for k in ("x", "y", "z")))
                elif cur["type"] == "POLYLINE":
                    poly = cur
                    poly["pts"] = []
                elif cur["type"] == "SEQEND" and poly is not None:
                    ents.append(poly)
                    poly = None
                elif cur["type"] in ("LINE", "LWPOLYLINE", "CIRCLE", "POINT", "3DFACE", "INSERT"):
                    ents.append(cur)
            cur = None
            if val == "SECTION":
                section = "?"
            elif val == "ENDSEC":
                section = None
            elif section == "ENTITIES" or (section == "BLOCKS" and False):
                cur = {"type": val, "layer": "0", "lw": []}
            continue
        if section == "?" and code == 2:
            section = val
            continue
        if section == "HEADER":
            if code == 9:
                var = val
            elif var and code in (70, 1, 10, 20, 30):
                header.setdefault(var, val)
            continue
        if cur is None:
            continue
        try:
            f = float(val)
        except ValueError:
            f = None
        if code == 8:
            cur["layer"] = val
        elif cur["type"] == "LWPOLYLINE" and code in (10, 20):
            if code == 10:
                cur["lw"].append([f, 0.0])
            elif cur["lw"]:
                cur["lw"][-1][1] = f
        elif code == 38 and f is not None:
            cur["elev"] = f
        elif code == 70 and f is not None:
            cur["flags"] = int(f)
        elif code in (10, 20, 30, 11, 21, 31, 12, 22, 32, 13, 23, 33, 40) and f is not None:
            cur[{10: "x", 20: "y", 30: "z", 11: "x1", 21: "y1", 31: "z1", 12: "x2", 22: "y2", 32: "z2", 13: "x3", 23: "y3", 33: "z3", 40: "r"}[code]] = f
    return header, ents


def _kind(layer: str) -> str | None:
    for k, rx in KW:
        if rx.search(layer):
            return k
    return None


def parse_dxf(filename: str, data: bytes) -> dict[str, Any]:
    m = new_model("dxf", filename)
    if data[:22].startswith(b"AutoCAD Binary DXF"):
        issue(m, "blocking", "dxf_binary", "model", "Binary DXF is not supported - save as ASCII DXF.", "DXF باینری پشتیبانی نمی‌شود؛ به‌صورت DXF متنی (ASCII) ذخیره کنید.")
        return m
    text = data.decode("utf-8", errors="replace")
    if "\x00" in text[:200]:
        text = data.decode("utf-16", errors="replace")
    header, ents = read_entities(text)
    code = int(float(header.get("$INSUNITS", 0) or 0))
    scale = INSUNITS.get(code)
    segs: list[tuple[str, np.ndarray, np.ndarray]] = []
    outlines: list[tuple[str, np.ndarray]] = []
    colpts: list[np.ndarray] = []
    for e in ents:
        lay = e["layer"]
        t = e["type"]
        if t == "LINE":
            segs.append((lay, np.array([e.get("x", 0), e.get("y", 0), e.get("z", 0)]), np.array([e.get("x1", 0), e.get("y1", 0), e.get("z1", 0)])))
        elif t in ("LWPOLYLINE", "POLYLINE"):
            z = e.get("elev", e.get("z", 0.0)) if t == "LWPOLYLINE" else 0.0
            pts = [np.array([p[0], p[1], z]) for p in e["lw"]] if t == "LWPOLYLINE" else [np.array(p) for p in e.get("pts", [])]
            closed = bool(e.get("flags", 0) & 1)
            if len(pts) < 2:
                continue
            k = _kind(lay)
            if closed and k in ("slab", None) and len(pts) >= 3 and k == "slab":
                outlines.append((lay, np.array(pts)))
                continue
            if closed and k == "column":
                colpts.append(np.mean(pts, axis=0))
                continue
            for a, b in zip(pts, pts[1:] + ([pts[0]] if closed else [])):
                segs.append((lay, a, b))
        elif t in ("CIRCLE", "POINT", "INSERT") and _kind(lay) == "column":
            colpts.append(np.array([e.get("x", 0), e.get("y", 0), e.get("z", 0)]))
        elif t == "3DFACE" and _kind(lay) == "slab":
            pts = [np.array([e.get(f"x{s}", 0), e.get(f"y{s}", 0), e.get(f"z{s}", 0)]) for s in ("", "1", "2", "3")]
            pts = [np.array([e.get("x", 0), e.get("y", 0), e.get("z", 0)])] + [np.array([e.get(f"x{s}", 0), e.get(f"y{s}", 0), e.get(f"z{s}", 0)]) for s in ("1", "2", "3")]
            outlines.append((lay, np.array(pts)))
    if not segs:
        issue(m, "blocking", "dxf_empty", "model", "No LINE/POLYLINE entities were found in the DXF.", "هیچ خط یا پلی‌لاینی در DXF پیدا نشد.")
        return m
    allp = np.array([p for _, a, b in segs for p in (a, b)])
    ext = float(np.ptp(allp, axis=0).max())
    if scale is None:
        scale = 1e-3 if ext > 500 else 1e-2 if ext > 150 else 1.0
        issue(m, "approximated", "dxf_units", "model", f"DXF has no drawing units ($INSUNITS) - {'mm' if scale == 1e-3 else 'cm' if scale == 1e-2 else 'm'} assumed from the drawing size.",
              f"واحد نقشه ($INSUNITS) در DXF نیست؛ از روی ابعاد نقشه {'میلی‌متر' if scale == 1e-3 else 'سانتی‌متر' if scale == 1e-2 else 'متر'} فرض شد.")
    m["units"]["source"] = {1e-3: "mm", 1e-2: "cm", 1.0: "m", 0.0254: "in", 0.3048: "ft", 0.1: "dm"}.get(scale, str(scale))
    segs = [(lay, a * scale, b * scale) for lay, a, b in segs if np.linalg.norm(b - a) * scale > 1e-3]
    outlines = [(lay, o * scale) for lay, o in outlines]
    colpts = [c * scale for c in colpts]
    zs = np.array([p[2] for _, a, b in segs for p in (a, b)])
    plan = float(np.ptp(zs)) < 1e-3
    unknown_layers = set()
    lines = []
    for lay, a, b in segs:
        k = _kind(lay)
        d = b - a
        L = float(np.linalg.norm(d))
        if k in (None, "slab"):
            if k is None:
                unknown_layers.add(lay)
            k = "column" if abs(d[2]) / L > 0.99 else "beam" if abs(d[2]) / L < 0.01 else "brace"
        lines.append((lay, k, a, b))
    if unknown_layers:
        issue(m, "approximated", "dxf_layers", ", ".join(sorted(unknown_layers))[:80],
              f"Layers without a member keyword ({', '.join(sorted(unknown_layers))[:120]}): lines classified by direction (vertical=column, horizontal=beam, inclined=brace).",
              f"لایه‌های بدون کلیدواژه‌ی عضو ({', '.join(sorted(unknown_layers))[:120]}): خطوط بر اساس جهت دسته‌بندی شدند (قائم=ستون، افقی=تیر، مایل=مهاربند).")
    if plan:
        m["dxf_plan"] = {"lines": [(lay, k, a[:2].tolist(), b[:2].tolist()) for lay, k, a, b in lines if k == "beam"],
                         "columns": [c[:2].tolist() for c in colpts],
                         "outlines": [(lay, o[:, :2].tolist()) for lay, o in outlines],
                         "z0": float(zs[0]), "extruded": False}
        _build_plan(m, storeys=1, height=3.0, column_section=None)
        issue(m, "blocking", "dxf_storeys", "model",
              "The DXF is a 2D plan: confirm the number of storeys, storey height and the column section in the review (1 storey x 3.0 m shown).",
              "DXF یک پلان دوبعدی است؛ تعداد طبقات، ارتفاع طبقه و مقطع ستون را در بازبینی تأیید کنید (فعلاً ۱ طبقه × ۳٫۰ متر).")
    else:
        _build_3d(m, lines, outlines)
    nsec = {mem["section"] for mem in m["members"]}
    assume(m, f"DXF geometry: {len(m['members'])} members from {len(nsec)} layers. Sections, materials and loads are not in a DXF - they come from the engineer review.",
           f"هندسه‌ی DXF: {len(m['members'])} عضو از {len(nsec)} لایه. مقطع، مصالح و بار در DXF نیست و در بازبینی مهندس تعیین می‌شود.")
    return m


class _Nodes:
    def __init__(self, m: dict[str, Any], tol: float = 5e-3) -> None:
        self.m, self.tol, self.keys = m, tol, {}

    def get(self, p) -> str:
        key = tuple(int(round(v / self.tol)) for v in p)
        if key in self.keys:
            return self.keys[key]
        nid = f"N{len(self.keys) + 1}"
        self.keys[key] = nid
        self.m["nodes"][nid] = {"x": round(float(p[0]), 4), "y": round(float(p[1]), 4), "z": round(float(p[2]), 4)}
        return nid


def _split(m: dict[str, Any], lines: list[tuple[str, str, np.ndarray, np.ndarray]], nodes: _Nodes) -> None:
    pts = {}
    for _, _, a, b in lines:
        pts[nodes.get(a)] = a
        pts[nodes.get(b)] = b
    P = np.array(list(pts.values()))
    ids = list(pts.keys())
    n = 0
    for lay, k, a, b in lines:
        d = b - a
        L2 = float(d @ d)
        t = (P - a) @ d / L2
        proj = a + t[:, None] * d
        dist = np.linalg.norm(P - proj, axis=1)
        sel = np.where((dist < 5e-3) & (t > 1e-6) & (t < 1 - 1e-6))[0]
        cuts = [0.0] + sorted(float(t[s]) for s in sel) + [1.0]
        for t0, t1 in zip(cuts, cuts[1:]):
            if t1 - t0 < 1e-9:
                continue
            i, j = nodes.get(a + t0 * d), nodes.get(a + t1 * d)
            if i == j:
                continue
            if k == "column" and m["nodes"][i]["z"] > m["nodes"][j]["z"]:
                i, j = j, i
            n += 1
            m["members"].append({"id": f"{k[0].upper()}{n}", "i": i, "j": j, "type": k, "section": lay, "label": lay})
    del ids


def _faces(m: dict[str, Any]) -> list[list[str]]:
    """Minimal closed faces of the horizontal beam graph at each level (planar half-edge walk)."""
    nodes = m["nodes"]
    adj: dict[str, set[str]] = {}
    for mem in m["members"]:
        if mem["type"] == "beam":
            adj.setdefault(mem["i"], set()).add(mem["j"])
            adj.setdefault(mem["j"], set()).add(mem["i"])
    ang = {}
    for u, vs in adj.items():
        ang[u] = sorted(vs, key=lambda v: math.atan2(nodes[v]["y"] - nodes[u]["y"], nodes[v]["x"] - nodes[u]["x"]))
    seen = set()
    faces = []
    for u in adj:
        for v in adj[u]:
            if (u, v) in seen:
                continue
            face = [u]
            a, b = u, v
            ok = True
            for _ in range(64):
                seen.add((a, b))
                lst = ang[b]
                k = lst.index(a)
                c = lst[(k - 1) % len(lst)]
                a, b = b, c
                if a == u and b == v:
                    break
                face.append(a)
            else:
                ok = False
            if not ok or len(face) < 3:
                continue
            xy = np.array([[nodes[n]["x"], nodes[n]["y"]] for n in face])
            area2 = float(np.dot(xy[:, 0], np.roll(xy[:, 1], -1)) - np.dot(xy[:, 1], np.roll(xy[:, 0], -1)))
            if area2 > 1e-6:  # counter-clockwise = interior face
                faces.append(face)
    return faces


def _build_3d(m: dict[str, Any], lines, outlines) -> None:
    nodes = _Nodes(m)
    _split(m, lines, nodes)
    _add_areas(m, outlines)


def _add_areas(m: dict[str, Any], outlines) -> None:
    from app.application.model_import.slabs import _inside
    faces = _faces(m)
    zlev = lambda f: round(m["nodes"][f[0]]["z"], 3)  # noqa: E731
    if outlines:
        keep = []
        for f in faces:
            c = np.mean([[m["nodes"][n]["x"], m["nodes"][n]["y"]] for n in f], axis=0)
            for _, o in outlines:
                if abs(float(o[:, 2].mean()) - zlev(f)) < 0.05 if o.shape[1] == 3 else True:
                    if _inside(np.array([c[0]]), np.array([c[1]]), o[:, :2])[0]:
                        keep.append(f)
                        break
        faces = keep
        how = "inside the slab outlines"
    else:
        how = "every closed beam panel (no slab layer)"
    for k, f in enumerate(faces):
        if len({round(m["nodes"][n]["z"], 3) for n in f}) != 1:
            continue
        m["areas"].append({"id": f"S{k + 1}", "nodes": f, "kind": "floor", "section": "SLAB", "story": f"z={zlev(f):g}", "one_way": None})
    if m["areas"]:
        m["area_sections"]["SLAB"] = {"material": None, "thickness": None, "type": "Slab"}
        issue(m, "approximated", "dxf_slabs", str(len(m["areas"])),
              f"{len(m['areas'])} floor panels were detected ({how}); enter floor loads (kPa) in the review - they go to the beams by tributary area.",
              f"{len(m['areas'])} چشمه‌ی کف شناسایی شد ({'داخل محدوده‌ی دال' if outlines else 'همه‌ی چشمه‌های بسته‌ی تیرها'})؛ بار سطحی کف (kPa) را در بازبینی وارد کنید؛ به روش سطح بارگیر به تیرها می‌رسد.")


def _build_plan(m: dict[str, Any], storeys: int, height: float, column_section: str | None) -> None:
    plan = m["dxf_plan"]
    m["nodes"], m["members"], m["areas"], m["supports"] = {}, [], [], {}
    nodes = _Nodes(m)
    lines = []
    for s in range(1, storeys + 1):
        z = s * height
        for lay, k, a, b in plan["lines"]:
            lines.append((lay, "beam", np.array([a[0], a[1], z]), np.array([b[0], b[1], z])))
    cols = [np.array(c) for c in plan["columns"]]
    if not cols:
        ends: dict[tuple, int] = {}
        for _, _, a, b in plan["lines"]:
            for p in (a, b):
                key = (round(p[0], 2), round(p[1], 2))
                ends[key] = ends.get(key, 0) + 1
        cols = [np.array(k) for k in ends]
        plan["auto_columns"] = True
    for s in range(1, storeys + 1):
        for c in cols:
            lines.append((column_section or "COLUMN", "column", np.array([c[0], c[1], (s - 1) * height]), np.array([c[0], c[1], s * height])))
    _split(m, lines, nodes)
    for nid, n in m["nodes"].items():
        if abs(n["z"]) < 1e-6:
            m["supports"][nid] = [True] * 6
    outl = [(lay, np.array([[p[0], p[1], s * height] for p in o])) for s in range(1, storeys + 1) for lay, o in plan["outlines"]]
    _add_areas(m, outl)
    m["dxf_plan"]["storeys"], m["dxf_plan"]["height"] = storeys, height
    if plan.get("auto_columns"):
        issue(m, "approximated", "dxf_columns", "model", "No column layer/symbols in the plan: columns were placed at every beam end/intersection.",
              "در پلان لایه یا نماد ستون نبود؛ ستون‌ها در همه‌ی انتها/تقاطع‌های تیر قرار داده شدند.")


def extrude_plan(m: dict[str, Any], e: dict[str, Any]) -> None:
    if not m.get("dxf_plan"):
        return
    try:
        n = max(1, min(60, int(float(e.get("storeys") or m["dxf_plan"].get("storeys") or 1))))
        h = float(e.get("height") or m["dxf_plan"].get("height") or 3.0)
    except (TypeError, ValueError):
        return
    if not 1.5 <= h <= 10:
        return
    keep_loads = m.get("area_loads", [])
    _build_plan(m, n, h, e.get("column_section") or None)
    m["member_loads"], m["nodal_loads"] = [], []
    m["area_loads"] = [ld for ld in keep_loads if any(a["id"] == ld["area"] for a in m["areas"])]
    m["dxf_plan"]["extruded"] = True
    assume(m, f"DXF plan extruded to {n} storeys x {h:g} m; base nodes fixed.", f"پلان DXF به {n} طبقه × {h:g} متر تعمیم داده شد؛ گره‌های پای ستون گیردار.")
