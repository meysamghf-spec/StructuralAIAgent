"""Distribute floor (area) loads to supporting beams by the tributary method.

Each floor polygon is sampled on a fine grid; every sample's load goes to the nearest supporting beam
(the 45-degree yield-line / ETABS "two-way" envelope for rectangles). For one-way slabs (marked
one-way, or auto when a rectangular panel has aspect >= 2, Mabhas 9) only beams parallel to the long side
receive load. The load reaching a beam is binned along its length into piecewise-uniform segments, so
triangular and trapezoidal shapes are represented and the total is exact (rescaled to q x area).
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np

N_BINS = 8
TOL = 1e-3


def polygon_area(pts: np.ndarray) -> float:
    x, y = pts[:, 0], pts[:, 1]
    return 0.5 * abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))))


def _inside(px: np.ndarray, py: np.ndarray, poly: np.ndarray) -> np.ndarray:
    inside = np.zeros(px.shape, dtype=bool)
    n = len(poly)
    for k in range(n):
        x1, y1 = poly[k]
        x2, y2 = poly[(k + 1) % n]
        cond = ((y1 > py) != (y2 > py))
        xint = (x2 - x1) * (py - y1) / ((y2 - y1) if y2 != y1 else 1e-30) + x1
        inside ^= cond & (px < xint)
    return inside


def _on_or_inside(pt: np.ndarray, poly: np.ndarray) -> bool:
    if _inside(np.array([pt[0]]), np.array([pt[1]]), poly)[0]:
        return True
    n = len(poly)
    for k in range(n):
        a, b = poly[k], poly[(k + 1) % n]
        ab = b - a
        L2 = float(ab @ ab)
        t = 0.0 if L2 == 0 else max(0.0, min(1.0, float((pt - a) @ ab) / L2))
        if np.linalg.norm(a + t * ab - pt) < TOL * 10:
            return True
    return False


def is_one_way(poly: np.ndarray) -> tuple[bool, np.ndarray | None]:
    """Rectangle with aspect >= 2 -> (True, long direction unit vector)."""
    if len(poly) != 4:
        return False, None
    e = [poly[(k + 1) % 4] - poly[k] for k in range(4)]
    L = [float(np.linalg.norm(v)) for v in e]
    if min(L) <= 0:
        return False, None
    if abs(e[0] @ e[1]) / (L[0] * L[1]) > 0.02:
        return False, None
    long_i = int(np.argmax(L[:2]))
    short = min(L[0], L[1])
    if max(L[0], L[1]) / short >= 2.0:
        return True, e[long_i] / L[long_i]
    return False, None


def distribute_area(poly: np.ndarray, q: float, beams: list[tuple[str, np.ndarray, np.ndarray]],
                    one_way_dir: np.ndarray | None = None) -> tuple[dict[str, list[tuple[float, float, float]]], float]:
    """poly: (n,2); q: kPa (down +); beams: (id, xy_i, xy_j). Returns {beam: [(a, b, w kN/m down)]}, total kN."""
    area = polygon_area(poly)
    total = q * area
    sup = []
    for bid, a, b in beams:
        if not (_on_or_inside((a + b) / 2, poly) and _on_or_inside(a, poly) and _on_or_inside(b, poly)):
            continue
        d = b - a
        L = float(np.linalg.norm(d))
        if L < TOL:
            continue
        if one_way_dir is not None and abs(float(d @ one_way_dir)) / L < 0.985:
            continue
        sup.append((bid, a, d, L))
    if not sup or area <= 0 or q == 0:
        return {}, total
    lo, hi = poly.min(0), poly.max(0)
    h = math.sqrt(area / 2500.0)
    nx_, ny_ = max(1, round((hi[0] - lo[0]) / h)), max(1, round((hi[1] - lo[1]) / h))
    hx, hy = (hi[0] - lo[0]) / nx_, (hi[1] - lo[1]) / ny_
    hcell = math.sqrt(hx * hy)
    xs = lo[0] + hx * (np.arange(nx_) + 0.5)
    ys = lo[1] + hy * (np.arange(ny_) + 0.5)
    gx, gy = np.meshgrid(xs, ys)
    gx, gy = gx.ravel(), gy.ravel()
    mask = _inside(gx, gy, poly)
    gx, gy = gx[mask], gy[mask]
    if gx.size == 0:
        return {}, total
    P = np.stack([gx, gy], 1)
    dist = np.empty((P.shape[0], len(sup)))
    tpar = np.empty_like(dist)
    for k, (_, a, d, L) in enumerate(sup):
        t = np.clip(((P - a) @ d) / (L * L), 0.0, 1.0)
        proj = a + t[:, None] * d
        dist[:, k] = np.linalg.norm(P - proj, axis=1)
        tpar[:, k] = t
    dmin = dist.min(axis=1, keepdims=True)
    tie = dist <= dmin + 1e-9 * max(1.0, float(dmin.max()))
    share = tie / tie.sum(axis=1, keepdims=True)  # points on a 45-degree line split equally
    w_pt = total / P.shape[0]
    out: dict[str, list[tuple[float, float, float]]] = {}
    for k, (bid, _, _, L) in enumerate(sup):
        sel = share[:, k] > 0
        if not sel.any():
            continue
        # spread each sample over its own cell width along the beam (no aliasing between grid and steps)
        sx = tpar[sel, k] * L
        lo_, hi_ = np.clip(sx - hcell / 2, 0, L), np.clip(sx + hcell / 2, 0, L)
        edges = np.linspace(0, L, N_BINS + 1)
        ov = np.clip(np.minimum(hi_[:, None], edges[None, 1:]) - np.maximum(lo_[:, None], edges[None, :-1]), 0, None)
        tot = ov.sum(axis=1, keepdims=True)
        ov = np.where(tot > 0, ov / np.where(tot > 0, tot, 1), 0)
        ov[tot[:, 0] == 0, np.minimum((sx[tot[:, 0] == 0] / L * N_BINS).astype(int), N_BINS - 1)] = 1.0
        counts = (ov * share[sel, k][:, None]).sum(axis=0)
        dl = L / N_BINS
        segs = [(i * dl, (i + 1) * dl, float(c) * w_pt / dl) for i, c in enumerate(counts) if c]
        out.setdefault(bid, []).extend(segs)
    return out, total


def distribute_model(model: dict[str, Any], patterns: list[str]) -> tuple[dict[str, dict[str, list]], dict[str, list], list[dict[str, Any]]]:
    """-> ({pattern: {member: [(a, b, [wx, wy, wz])]}}, {pattern: [nodal loads]}, per-slab report)."""
    nodes = model["nodes"]
    floors = [a for a in model.get("areas", []) if a.get("kind", "floor") == "floor"]
    by_z: dict[float, list[tuple[str, np.ndarray, np.ndarray]]] = {}
    for mem in model["members"]:
        if mem["type"] != "beam":
            continue
        ni, nj = nodes[mem["i"]], nodes[mem["j"]]
        if abs(ni["z"] - nj["z"]) > TOL:
            continue
        by_z.setdefault(round(ni["z"], 3), []).append((mem["id"], np.array([ni["x"], ni["y"]]), np.array([nj["x"], nj["y"]])))
    asec = model.get("area_sections", {})
    out: dict[str, dict[str, list]] = {p: {} for p in patterns}
    nodal: dict[str, list] = {p: [] for p in patterns}
    report = []
    bz_arr: dict[float, tuple] = {}
    q_idx: dict[tuple[str, str], float] = {}
    for l in model.get("area_loads", []):
        q_idx[(l["area"], l["pattern"])] = q_idx.get((l["area"], l["pattern"]), 0.0) + l["q"]
    for ar in floors:
        pts = np.array([[nodes[n]["x"], nodes[n]["y"]] for n in ar["nodes"] if n in nodes])
        if len(pts) < 3:
            continue
        z = round(sum(nodes[n]["z"] for n in ar["nodes"]) / len(ar["nodes"]), 3)
        ow = ar.get("one_way")
        ow_auto, ow_dir = is_one_way(pts)
        use_ow = ow_auto if ow is None else bool(ow)
        if use_ow and ow_dir is None and len(pts) == 4:
            e0, e1 = pts[1] - pts[0], pts[2] - pts[1]
            ow_dir = (e0 if np.linalg.norm(e0) >= np.linalg.norm(e1) else e1)
            ow_dir = ow_dir / np.linalg.norm(ow_dir)
        sec = asec.get(ar.get("section") or "", {})
        t_slab = sec.get("thickness") or 0.0
        gamma = (model["materials"].get(sec.get("material") or "", {}) or {}).get("unit_weight") or 25.0
        beams = by_z.get(z, [])
        if beams:
            if z not in bz_arr:
                bz_arr[z] = (np.array([b[1] for b in beams]), np.array([b[2] for b in beams]))
            A, B = bz_arr[z]
            lo, hi = pts.min(0) - 10 * TOL, pts.max(0) + 10 * TOL
            ok = np.all((A >= lo) & (A <= hi) & (B >= lo) & (B <= hi), axis=1)
            beams = [beams[k] for k in np.where(ok)[0]]
        unit: dict[bool, tuple] = {}
        rec = {"area": ar["id"], "one_way": bool(use_ow), "area_m2": polygon_area(pts), "supports": 0, "to_nodes": False}
        for pat in patterns:
            q = q_idx.get((ar["id"], pat), 0.0)
            sw = model["load_patterns"].get(pat, {}).get("self_weight") or 0.0
            q += sw * t_slab * gamma
            if not q:
                continue
            if "u" not in unit:  # distribution is linear in q: compute once per slab with q = 1
                us, _ = distribute_area(pts, 1.0, beams, ow_dir if use_ow else None)
                if not us and use_ow:
                    us, _ = distribute_area(pts, 1.0, beams, None)
                unit["u"] = us
            total = q * polygon_area(pts)
            segs = {bid: [(a, b, w * q) for a, b, w in ss] for bid, ss in unit["u"].items()}
            if segs:
                rec["supports"] = max(rec["supports"], len(segs))
                for bid, ss in segs.items():
                    out[pat].setdefault(bid, []).extend((a, b, [0.0, 0.0, -w]) for a, b, w in ss)
            else:
                rec["to_nodes"] = True
                share = total / len(ar["nodes"])
                for n in ar["nodes"]:
                    nodal[pat].append({"node": n, "pattern": pat, "fx": 0, "fy": 0, "fz": -share, "mx": 0, "my": 0, "mz": 0})
        report.append(rec)
    return out, nodal, report
