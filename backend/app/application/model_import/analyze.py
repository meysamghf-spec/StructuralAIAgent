"""Engineer review edits + analysis of an imported model with SAIA's 3D direct-stiffness solver.

All numbers come from ``frame3d_solver`` (linear elastic, first order). No LLM is involved.
"""

from __future__ import annotations

import copy
from typing import Any

from app.application.analysis.frame3d_solver import (
    SpaceElement, SpaceFrameModel, SpaceFrameSolverError, SpaceNode, SpaceNodalLoad, SpaceSupport,
    assemble_space_system, build_space_load_vector, recover_space_result,
)
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
    m["combos"] = {k: v for k, v in m["combos"].items() if "(assumed)" not in k}
    m["counts"] = {}
    m["issues"] = [i for i in m["issues"] if i["code"] not in ("no_loads",)]
    m = finalize(m)
    confirmed = set(edits.get("confirmed") or [])
    for i in m["issues"]:
        if i["id"] in confirmed:
            i["confirmed"] = True
    return m


def _mat(model: dict[str, Any], sec: dict[str, Any]) -> dict[str, Any]:
    return model["materials"].get(sec.get("material")) or DEFAULT_CONCRETE


def analyze_imported_model(model: dict[str, Any]) -> dict[str, Any]:
    summary = review_summary(model)
    if not summary["can_analyze"]:
        raise ValueError("Resolve the blocking review items before analysis.")
    nodes = [SpaceNode(nid, n["x"], n["y"], n["z"]) for nid, n in model["nodes"].items()]
    used_nodes = {m["i"] for m in model["members"]} | {m["j"] for m in model["members"]}
    nodes = [n for n in nodes if n.id in used_nodes]
    elements: list[SpaceElement] = []
    selfw: dict[str, float] = {}
    for mem in model["members"]:
        sec = model["sections"][mem["section"]]
        mat = _mat(model, sec)
        mod = sec.get("modifiers") or {}
        a = sec["A"] * (mod.get("A") or 1.0)
        i33 = (sec.get("I33") or 0) * (mod.get("I33") or 1.0)
        i22 = (sec.get("I22") or 0) * (mod.get("I22") or 1.0)
        j = (sec.get("J") or 0) * (mod.get("J") or 1.0)
        if i33 <= 0 or i22 <= 0 or j <= 0:
            raise ValueError(f"Section {mem['section']} needs positive I33, I22 and J.")
        elements.append(SpaceElement(mem["id"], mem["i"], mem["j"], mat["E"], a, i33, i22, j, poisson=mat.get("nu") or 0.2,
                                     member_id=mem["id"], metadata={"type": mem["type"]}))
        selfw[mem["id"]] = sec["A"] * (mat.get("unit_weight") or 0.0)
    supports = [SpaceSupport(nid, *flags) for nid, flags in model["supports"].items() if nid in used_nodes and any(flags)]
    fm = SpaceFrameModel("import", nodes, elements, supports)
    try:
        prepared = assemble_space_system(fm)
    except SpaceFrameSolverError as exc:
        raise ValueError(f"The structure is unstable or invalid: {exc}") from exc

    def pattern_loads(pat: str) -> tuple[dict[str, list[float]], list[SpaceNodalLoad]]:
        udl: dict[str, list[float]] = {}
        sw = model["load_patterns"].get(pat, {}).get("self_weight") or 0.0
        if sw:
            for mid, w in selfw.items():
                udl.setdefault(mid, [0.0, 0.0, 0.0])[2] -= sw * w
        for ld in model["member_loads"]:
            if ld["pattern"] == pat:
                u = udl.setdefault(ld["member"], [0.0, 0.0, 0.0])
                u[0] += ld.get("wx", 0.0)
                u[1] += ld.get("wy", 0.0)
                u[2] += ld.get("wz", 0.0)
        nl = [SpaceNodalLoad(ld["node"], ld.get("fx", 0), ld.get("fy", 0), ld.get("fz", 0), ld.get("mx", 0), ld.get("my", 0), ld.get("mz", 0))
              for ld in model["nodal_loads"] if ld["pattern"] == pat and ld["node"] in used_nodes]
        return udl, nl

    vectors: dict[str, list[float]] = {}
    for pat in model["load_patterns"]:
        udl, nl = pattern_loads(pat)
        vectors[pat] = build_space_load_vector(fm, prepared, nl, {k: tuple(v) for k, v in udl.items()})
    cases: dict[str, dict[str, float]] = {f"pattern:{p}": {p: 1.0} for p in model["load_patterns"]}
    cases.update({f"combo:{c}": f for c, f in model["combos"].items()})
    results: dict[str, Any] = {}
    env: dict[str, dict[str, float]] = {}
    for cname, factors in cases.items():
        vec = [0.0] * prepared["n_full"]
        for pat, sf in factors.items():
            for idx, v in enumerate(vectors.get(pat, ())):
                vec[idx] += sf * v
        try:
            res = recover_space_result(fm, prepared, vec)
        except SpaceFrameSolverError as exc:
            raise ValueError(f"The structure is unstable (singular stiffness): check supports and connectivity. {exc}") from exc
        reac = [sum(r[k] for r in res.reactions.values()) for k in range(3)]
        top = max(res.displacements.items(), key=lambda kv: (kv[1][0] ** 2 + kv[1][1] ** 2 + kv[1][2] ** 2), default=(None, (0,) * 6))
        members = {}
        for mid, f in res.member_forces.items():
            members[mid] = {"N": float(f"{f.max_abs_axial:.9g}"), "V": float(f"{f.max_abs_shear:.9g}"), "M": float(f"{f.max_abs_moment:.9g}"), "T": round(abs(f.torsion), 3)}
            if cname.startswith("combo:"):
                e = env.setdefault(mid, {"N": 0.0, "V": 0.0, "M": 0.0, "T": 0.0})
                for k in e:
                    e[k] = max(e[k], members[mid][k])
        results[cname] = {
            "factors": factors,
            "base_reaction_kN": [float(f"{v:.9g}") for v in reac],
            "max_displacement_m": float(f"{res.max_abs_displacement:.9g}"),
            "max_displacement_node": top[0],
            "members": members,
        }
    if not env and results:
        for r in results.values():
            for mid, f in r["members"].items():
                e = env.setdefault(mid, {"N": 0.0, "V": 0.0, "M": 0.0, "T": 0.0})
                for k in e:
                    e[k] = max(e[k], f[k])
    governing = sorted(env.items(), key=lambda kv: -kv[1]["M"])[:15]
    return {
        "engine": "SAIA frame3d direct-stiffness (linear, first order)",
        "units": {"force": "kN", "length": "m", "moment": "kN.m"},
        "counts": model["counts"],
        "cases": results,
        "envelope": env,
        "governing_members": [{"member": k, **v} for k, v in governing],
        "assumptions": model["assumptions"],
        "notes": [
            "Linear static, first-order analysis; no P-Delta, no modal/response spectrum for imported models in this phase.",
            "Member results are max |N|, |V|, |M| along each member (kN, kN.m).",
        ],
    }
