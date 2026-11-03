"""Engineer review edits + analysis of an imported model with SAIA's sparse 3D frame engine.

All numbers come from ``engine.FrameEngine`` (releases, rigid diaphragms, P-Delta, modal, response
spectrum per Standard 2800). No LLM is involved.
"""

from __future__ import annotations

import copy
from typing import Any

from app.application.model_import.common import assume, finalize, rect_props, num

DEFAULT_CONCRETE = {"type": "Concrete", "E": 2.35e7, "nu": 0.2, "unit_weight": 25.0}


def review_summary(model: dict[str, Any]) -> dict[str, Any]:
    issues = model.get("issues", [])
    blocking = [i for i in issues if i["severity"] == "blocking" and not i.get("resolved")]
    return {
        "counts": model.get("counts", {}),
        "issues": issues,
        "assumptions": model.get("assumptions", []),
        "blocking": len(blocking),
        "can_analyze": not blocking,
        "requires_confirmation": [i["id"] for i in issues if i["severity"] != "blocking" and not i.get("confirmed")],
    }


def apply_review(model: dict[str, Any], edits: dict[str, Any]) -> dict[str, Any]:
    """Apply the engineer's review edits and return a new model.

    edits = {
      "sections": {name: {"b": m, "h": m} | {"A", "I33", "I22", "J"} , "material"?: name},
      "materials": {name: {"E": kN/m2, "unit_weight": kN/m3, "nu"}},
      "beam_line_loads": [{"pattern": str, "w": kN/m (gravity, +down), "story"?: str}],
      "confirmed": [issue ids]  (approximations accepted by the engineer)
    }
    """
    m = copy.deepcopy(model)
    m["issues"] = [i for i in m["issues"] if i["severity"] != "blocking"]
    for name, e in (edits.get("materials") or {}).items():
        mat = m["materials"].setdefault(name, dict(DEFAULT_CONCRETE))
        for k in ("E", "unit_weight", "nu"):
            v = num(e.get(k))
            if v is not None and v >= 0:
                mat[k] = v
    for name, e in (edits.get("sections") or {}).items():
        sec = m["sections"].setdefault(name, {"shape": "edited", "material": None, "modifiers": {}})
        b, h = num(e.get("b")), num(e.get("h"))
        if b and h and b > 0 and h > 0:
            sec.update(rect_props(b, h), b=b, h=h, shape=sec.get("shape") or "Rectangular (edited)")
        for k in ("A", "I33", "I22", "J"):
            v = num(e.get(k))
            if v and v > 0:
                sec[k] = v
        if e.get("catalog"):
            from app.application.model_import.catalog import lookup
            cat = lookup(e["catalog"])
            if cat:
                sec.update({k: v for k, v in cat.items() if k != "shape"}, shape=cat["shape"], catalog=cat["shape"])
                if not e.get("material"):
                    sec["material"] = sec.get("material") if sec.get("material") in m["materials"] else "STEEL (catalog)"
                    m["materials"].setdefault(sec["material"], {"type": "Steel", "E": 2.0e8, "nu": 0.3, "unit_weight": 77.0})
        if e.get("material"):
            sec["material"] = str(e["material"])
        sec["edited"] = True
    n_added = 0
    for ld in edits.get("beam_line_loads") or []:
        w, pat, story = num(ld.get("w")), str(ld.get("pattern") or "Dead"), ld.get("story")
        if not w:
            continue
        m["load_patterns"].setdefault(pat, {"type": "Dead" if pat.lower().startswith("dead") else "Live" if pat.lower().startswith("live") else "Other", "self_weight": 0.0})
        for mem in m["members"]:
            if mem["type"] == "beam" and (not story or mem.get("story") == story):
                m["member_loads"].append({"member": mem["id"], "pattern": pat, "wx": 0.0, "wy": 0.0, "wz": -w, "added_in_review": True})
                n_added += 1
    if n_added:
        assume(m, f"{n_added} beam line loads were added in the engineer review.", f"{n_added} بار خطی تیر در بازبینی مهندس اضافه شد.")
    if edits.get("seismic"):
        m["seismic"] = {**(m.get("seismic") or {}), **{k: v for k, v in edits["seismic"].items() if v not in (None, "")}}
    if edits.get("wind"):
        m["wind"] = {**(m.get("wind") or {}), **edits["wind"]}
    if "pdelta" in edits:
        m.setdefault("analysis", {})["pdelta"] = bool(edits["pdelta"])
    if edits.get("rigid_diaphragms"):
        m.setdefault("analysis", {})["auto_diaphragm"] = True
    if edits.get("dxf") and m.get("format") == "dxf":
        from app.application.model_import.dxf_import import extrude_plan
        extrude_plan(m, edits["dxf"])
    n_al = 0
    for ld in edits.get("area_loads") or []:
        q, pat, story = num(ld.get("q")), str(ld.get("pattern") or "Dead"), ld.get("story")
        if not q:
            continue
        m["load_patterns"].setdefault(pat, {"type": "Dead" if pat.lower().startswith("dead") else "Live" if pat.lower().startswith("live") else "Other", "self_weight": 0.0})
        for ar in m.get("areas", []):
            if ar.get("kind", "floor") == "floor" and (not story or ar.get("story") == story):
                m.setdefault("area_loads", []).append({"area": ar["id"], "pattern": pat, "q": q, "added_in_review": True})
                n_al += 1
    if n_al:
        assume(m, f"{n_al} floor area loads were added in the engineer review.", f"{n_al} بار سطحی کف در بازبینی مهندس اضافه شد.")
    for aid, ow in (edits.get("one_way") or {}).items():
        for ar in m.get("areas", []):
            if ar["id"] == aid:
                ar["one_way"] = bool(ow)
    m["combos"] = {k: v for k, v in m["combos"].items() if "(assumed)" not in k}
    m["counts"] = {}
    m["issues"] = [i for i in m["issues"] if i["code"] not in ("no_loads",)]
    m = finalize(m)
    if m.get("dxf_plan") and not m["dxf_plan"].get("extruded"):
        from app.application.model_import.common import issue as _issue
        _issue(m, "blocking", "dxf_storeys", "model",
               "The DXF is a 2D plan: confirm the number of storeys, storey height and the column section in the review.",
               "DXF یک پلان دوبعدی است؛ تعداد طبقات، ارتفاع طبقه و مقطع ستون را در بازبینی تأیید کنید.")
    confirmed = set(edits.get("confirmed") or [])
    for i in m["issues"]:
        if i["id"] in confirmed:
            i["confirmed"] = True
    return m


from app.application.model_import.solve import analyze_imported_model  # noqa: E402,F401
