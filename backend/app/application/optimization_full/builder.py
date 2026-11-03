"""Neutral-model helpers for the optimizer: build a model from the chat's parametric frame, tag members
(storey, plan position, direction) and assign sections (rectangular RC or steel catalog)."""

from __future__ import annotations

import copy
import math
from typing import Any

from app.application.model_import.catalog import lookup
from app.application.model_import.common import finalize, new_model, rect_props

CONCRETE_MAT = "CONC (optimizer)"
STEEL_MAT = "STEEL (catalog)"
MODIFIERS = {"beam": {"I33": 0.35, "I22": 0.35}, "column": {"I33": 0.70, "I22": 0.70}, "brace": {}}


def rc_name(kind: str, b: float, h: float) -> str:
    return f"{'C' if kind == 'column' else 'B'}{round(b * 100):g}X{round(h * 100):g}"


def ensure_section(model: dict[str, Any], kind: str, cand: Any, fc_mpa: float = 30.0, steel_fy_mpa: float = 240.0) -> str:
    """Adds the candidate (``[b, h]`` metres or a steel catalog name) to model['sections'] and returns its name."""
    if isinstance(cand, str):
        name = cand.upper()
        if name not in model["sections"]:
            p = lookup(name)
            if p is None:
                raise ValueError(f"unknown steel section {cand}")
            model["materials"].setdefault(STEEL_MAT, {"type": "Steel", "E": 2.0e8, "nu": 0.3, "unit_weight": 77.0,
                                                      "Fy": steel_fy_mpa * 1e3})
            model["sections"][name] = {**{k: v for k, v in p.items() if k != "shape"}, "shape": p["shape"], "catalog": p["shape"],
                                       "material": STEEL_MAT, "modifiers": {}}
        return name
    b, h = float(cand[0]), float(cand[1])
    name = rc_name(kind, b, h)
    if name not in model["sections"]:
        model["materials"].setdefault(CONCRETE_MAT, {"type": "Concrete", "E": 4700 * math.sqrt(fc_mpa) * 1000, "nu": 0.2,
                                                     "unit_weight": 25.0, "Fc": fc_mpa * 1e3})
        model["sections"][name] = {"shape": "Rectangular", "material": CONCRETE_MAT, "b": b, "h": h, **rect_props(b, h),
                                   "modifiers": dict(MODIFIERS.get(kind, {}))}
    return name


def model_from_frame(inp: Any) -> dict[str, Any]:
    """The chat's regular frame (Frame3dInputs) as a neutral model: slabs as floor areas (tributary distribution),
    walls on edge beams, rigid diaphragms, fixed base, Standard 2800 parameters."""
    nx, ny, ns = int(inp.bays_x), int(inp.bays_y), int(inp.storeys)
    XS = [i * inp.bay_x_m for i in range(nx + 1)]
    YS = [j * inp.bay_y_m for j in range(ny + 1)]
    m = new_model("frame", "chat-frame")
    m["units"]["source"] = "SAIA chat frame"
    nid = lambda i, j, k: f"N{i}_{j}_{k}"  # noqa: E731
    for k in range(ns + 1):
        for i, x in enumerate(XS):
            for j, y in enumerate(YS):
                m["nodes"][nid(i, j, k)] = {"x": x, "y": y, "z": k * inp.storey_height_m}
                if k == 0:
                    m["supports"][nid(i, j, 0)] = [True] * 6
    col = ensure_section(m, "column", [inp.column_b_m, inp.column_h_m], inp.fc_mpa)
    beam = ensure_section(m, "beam", [inp.beam_b_m, inp.beam_h_m], inp.fc_mpa)
    for k in range(1, ns + 1):
        for i in range(nx + 1):
            for j in range(ny + 1):
                on_x, on_y = i in (0, nx), j in (0, ny)
                pos = "corner" if on_x and on_y else "edge" if on_x or on_y else "interior"
                m["members"].append({"id": f"C{i}_{j}_{k}", "i": nid(i, j, k - 1), "j": nid(i, j, k), "type": "column",
                                     "section": col, "storey": k, "position": pos})
                if i < nx:
                    m["members"].append({"id": f"BX{i}_{j}_{k}", "i": nid(i, j, k), "j": nid(i + 1, j, k), "type": "beam",
                                         "section": beam, "storey": k, "direction": "X", "position": "edge" if on_y else "interior"})
                if j < ny:
                    m["members"].append({"id": f"BY{i}_{j}_{k}", "i": nid(i, j, k), "j": nid(i, j + 1, k), "type": "beam",
                                         "section": beam, "storey": k, "direction": "Y", "position": "edge" if on_x else "interior"})
        m["diaphragms"][f"D{k}"] = [nid(i, j, k) for i in range(nx + 1) for j in range(ny + 1)]
    m["load_patterns"] = {"Dead": {"type": "Dead", "self_weight": 1.0}, "Live": {"type": "Live", "self_weight": 0.0}}
    m["area_sections"]["SLAB"] = {"thickness": inp.slab_t_m, "material": CONCRETE_MAT, "type": "Slab"}
    for k in range(1, ns + 1):
        live = inp.roof_live_kn_m2 if k == ns else inp.live_kn_m2
        wall = inp.parapet_kn_m if k == ns else inp.wall_kn_m
        for i in range(nx):
            for j in range(ny):
                aid = f"F{i}_{j}_{k}"
                m["areas"].append({"id": aid, "nodes": [nid(i, j, k), nid(i + 1, j, k), nid(i + 1, j + 1, k), nid(i, j + 1, k)],
                                   "kind": "floor", "section": "SLAB", "story": f"S{k}"})
                m["area_loads"].append({"area": aid, "pattern": "Dead", "q": inp.dead_kn_m2})
                m["area_loads"].append({"area": aid, "pattern": "Live", "q": live})
        for mem in m["members"]:
            if mem["type"] == "beam" and mem["storey"] == k and mem["position"] == "edge" and wall:
                m["member_loads"].append({"member": mem["id"], "pattern": "Dead", "w": wall})
    m["seismic"] = {"zone": getattr(inp, "zone", "HIGH"), "soil": getattr(inp, "soil", "II"),
                    "importance": getattr(inp, "importance", 1.0), "system": getattr(inp, "system", "RC_IMF")}
    m["analysis"] = {"pdelta": True}
    return finalize(m)


def tag_members(model: dict[str, Any]) -> dict[str, Any]:
    """Adds storey / position / direction to imported members that lack them (from geometry)."""
    nodes = model["nodes"]
    zs = sorted({round(n["z"], 2) for n in nodes.values()})
    levels: list[float] = []
    for z in zs:
        if not levels or z - levels[-1] > 0.3:
            levels.append(z)
    xs = [n["x"] for n in nodes.values()]; ys = [n["y"] for n in nodes.values()]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    tol = 0.05

    def storey(z: float) -> int:
        return max(1, min(range(len(levels)), key=lambda k: abs(levels[k] - z)))

    for mem in model["members"]:
        a, b = nodes[mem["i"]], nodes[mem["j"]]
        if "storey" not in mem:
            mem["storey"] = storey(max(a["z"], b["z"]))
        if "position" not in mem:
            on_x = abs(a["x"] - x0) < tol or abs(a["x"] - x1) < tol
            on_y = abs(a["y"] - y0) < tol or abs(a["y"] - y1) < tol
            if mem["type"] == "beam":
                both_x = on_x and (abs(b["x"] - a["x"]) < tol)
                both_y = on_y and (abs(b["y"] - a["y"]) < tol)
                mem["position"] = "edge" if both_x or both_y else "interior"
            else:
                mem["position"] = "corner" if on_x and on_y else "edge" if on_x or on_y else "interior"
        if mem["type"] == "beam" and "direction" not in mem:
            mem["direction"] = "X" if abs(b["x"] - a["x"]) >= abs(b["y"] - a["y"]) else "Y"
    return model


def with_sections(model: dict[str, Any], assign: dict[str, str]) -> dict[str, Any]:
    """Shallow copy of the model with member sections replaced (sections dict must already contain the names)."""
    m = dict(model)
    m["members"] = [{**mem, "section": assign.get(mem["id"], mem["section"])} for mem in model["members"]]
    return m


def clone(model: dict[str, Any]) -> dict[str, Any]:
    return copy.deepcopy(model)
