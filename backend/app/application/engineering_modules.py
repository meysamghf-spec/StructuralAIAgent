"""Common run interface for engineering modules (structure-type independent).

Each module registers a ModuleAdapter keyed by its result payload `kind`:
  run(inputs) -> payload          re-runs the module from stored inputs (+ inputs["assumptions"])
  summary(payload) -> str         one-line result summary for approval items
  intents(text, inputs) -> dict   design-change intents in a rejection reason ("increase column size", "use Φ20"...)
                                  returned as {"inputs": {...}, "assumptions": {...}}
The shared assumptions registry supplies the key/value changes; the approval/revision workflow
(revision_workflow.py) only talks to this interface, never to a specific structure type.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Callable

from app.application import assumptions_registry as reg
from app.application.assumptions_registry import AssumptionSpec as S


@dataclass
class ModuleAdapter:
    kind: str
    label: str
    assumption_modules: list[str]
    run: Callable[[dict[str, Any]], dict[str, Any]]
    summary: Callable[[dict[str, Any]], str]
    intents: Callable[[str, dict[str, Any]], dict[str, dict[str, Any]]] = lambda text, inputs: {}
    completed: Callable[[dict[str, Any]], bool] = lambda p: str(p.get("status", "")).lower() in ("completed", "pass", "fail", "check")
    extra: dict[str, Any] = field(default_factory=dict)


_ADAPTERS: dict[str, ModuleAdapter] = {}


def register_adapter(adapter: ModuleAdapter) -> None:
    _ADAPTERS[adapter.kind] = adapter


def adapter_for(kind: str | None) -> ModuleAdapter | None:
    _ensure_builtin()
    return _ADAPTERS.get(kind or "")


def kinds() -> list[str]:
    _ensure_builtin()
    return list(_ADAPTERS)


def parse_changes(adapter: ModuleAdapter, text: str, inputs: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    """Shared parser + module intents -> (input changes, assumption changes, range errors)."""
    parsed, errors = reg.parse(text, adapter.assumption_modules)
    a, inp = reg.split_targets(parsed)
    it = adapter.intents(text, inputs) or {}
    inp.update(it.get("inputs", {}))
    a.update(it.get("assumptions", {}))
    return inp, a, errors


def apply_changes(inputs: dict[str, Any], inp: dict[str, Any], a: dict[str, Any]) -> dict[str, Any]:
    new = {**inputs, **inp}
    if a:
        new["assumptions"] = {**(inputs.get("assumptions") or {}), **a}
    return new


def diff(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for k in sorted(set(old) | set(new)):
        if k == "assumptions":
            oa, na = old.get(k) or {}, new.get(k) or {}
            rows += [{"key": f"assumptions.{kk}", "old": oa.get(kk), "new": na.get(kk)} for kk in sorted(set(oa) | set(na)) if oa.get(kk) != na.get(kk)]
        elif isinstance(old.get(k), dict) and isinstance(new.get(k), dict):
            o, n = old[k], new[k]
            rows += [{"key": f"{k}.{kk}", "old": o.get(kk), "new": n.get(kk)} for kk in sorted(set(o) | set(n))
                     if o.get(kk) != n.get(kk) and kk not in ("confidence", "notes")]
        elif k not in ("parsed_from_request", "_p", "lang") and old.get(k) != new.get(k):
            rows.append({"key": k, "old": old.get(k), "new": new.get(k)})
    return rows


# ---------------------------------------------------------------------------------------------- built-ins
_STEP = 0.05  # m, section size increment for "increase ... size"


def _n(t: str) -> str:
    return reg.norm(t)


def _frame_intents(text: str, inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    t = _n(text)
    out: dict[str, Any] = {}
    a: dict[str, Any] = {}
    col = r"columns?|ستون"
    beam = r"beams?|تیر"
    bigger = r"increase|bigger|larger|enlarge|deeper|too small|undersized|افزایش|بزرگ|عمیق|کوچک است"
    for which, (wb, wh) in ((col, ("column_b_m", "column_h_m")), (beam, ("beam_b_m", "beam_h_m"))):
        m = re.search(rf"(?:{which})[^\d\n]{{0,12}}(\d{{2,3}})\s*x\s*(\d{{2,3}})\s*(cm|mm|سانت)?", t)
        if m:
            k = 0.001 if m.group(3) == "mm" else 0.01
            out[wb], out[wh] = float(m.group(1)) * k, float(m.group(2)) * k
        elif re.search(rf"(?:{bigger})[^.\n]{{0,25}}(?:{which})|(?:{which})[^.\n]{{0,25}}(?:{bigger})", t):
            if which == col:
                out[wb] = round(float(inputs.get(wb, 0.4)) + _STEP, 3)
            out[wh] = round(float(inputs.get(wh, 0.4)) + _STEP, 3)
    if re.search(r"drift[^.\n]{0,25}(?:high|exceed|large|too|fail)|دریفت[^.\n]{0,15}(?:زیاد|بالا|مجاز)|جابه?جایی[^.\n]{0,15}زیاد", t):
        for k in ("column_b_m", "column_h_m"):
            out.setdefault(k, round(float(inputs.get(k, 0.4)) + _STEP, 3))
        out.setdefault("beam_h_m", round(float(inputs.get("beam_h_m", 0.45)) + _STEP, 3))
    m = re.search(r"(?:use|only|با|از|فقط)\s*(?:bars?\s*|میلگرد\s*)?[Φφø]\s*(\d{2})", t)
    if m:
        d = int(m.group(1))
        if re.search(col, t):
            a["column_bars"] = [d]
        if re.search(beam, t) or not re.search(col, t):
            a["beam_bars"] = [d]
    return {"inputs": out, "assumptions": a}


def _frame_run(inputs: dict[str, Any]) -> dict[str, Any]:
    from app.application.frame3d_chat_analysis import build_frame3d_payload

    return build_frame3d_payload("", manual_inputs=inputs) or {}


def _frame_summary(p: dict[str, Any]) -> str:
    i, d = p.get("inputs") or {}, p.get("design") or {}
    s = (d.get("summary") or {})
    return (f"3D frame {i.get('storeys')} storeys {i.get('bays_x')}x{i.get('bays_y')} bays, C {i.get('column_b_m', 0)*100:g}x{i.get('column_h_m', 0)*100:g}"
            f", B {i.get('beam_b_m', 0)*100:g}x{i.get('beam_h_m', 0)*100:g} cm"
            + (f" — Mabhas 9 {d.get('status')} (max D/C {s.get('max_DC')})" if d.get("status") else "")
            + (f", drift {p.get('drift_check')}" if p.get("drift_check") else ""))


reg.register_module("aisc360", [
    S("fy_ksi", "number", 50, "Steel Fy", "تنش تسلیم فولاد", "ksi", (36, 100), (r"\bfy",), target="input", field_name="fy_ksi"),
    S("zx_in3", "number", None, "Plastic modulus Zx", "اساس مقطع پلاستیک", "in3", (1, 4000), (r"\bzx",), target="input", field_name="zx_in3"),
    S("span_m", "number", None, "Span", "دهانه", "m", (0.5, 50), (r"\bspan", r"دهانه"), target="input", field_name="span_m"),
    S("uniform_load_kn_m", "number", None, "Uniform load", "بار گسترده", "kN/m", (0.01, 1000), (r"(?:uniform )?load", r"بار(?: گسترده)?"),
      target="input", field_name="uniform_load_kn_m"),
])


def _aisc_run(inputs: dict[str, Any]) -> dict[str, Any]:
    from app.application.aisc_steel_beam_check import run_aisc_steel_beam_check
    from app.application.service_factory import build_code_engine_service

    params = {k: v for k, v in inputs.items() if k in ("span_m", "uniform_load_kn_m", "fy_ksi", "zx_in3", "mu_kipft") and v is not None}
    o = run_aisc_steel_beam_check(user_request="Check this steel beam per AISC 360-22 flexure", parameters=params,
                                  context={}, code_engine=build_code_engine_service())
    return o.payload if o else {}


def _aisc_intents(text: str, inputs: dict[str, Any]) -> dict[str, dict[str, Any]]:
    t = _n(text)
    if re.search(r"increase|heavier|bigger|larger|deeper|too small|fails?|overstress|افزایش|بزرگ|سنگین", t) and inputs.get("zx_in3"):
        return {"inputs": {"zx_in3": round(float(inputs["zx_in3"]) * 1.25, 1)}}
    return {}


def _aisc_summary(p: dict[str, Any]) -> str:
    i, r = p.get("inputs") or {}, p.get("results") or {}
    return f"AISC 360-22 steel beam Zx={i.get('zx_in3')} in3, Fy={i.get('fy_ksi')} ksi, span {i.get('span_m')} m — {p.get('status')} (U={r.get('governing_utilization')})"


_BUILTIN = False


def _ensure_builtin() -> None:
    global _BUILTIN
    if _BUILTIN:
        return
    _BUILTIN = True
    from app.application import detailing_assumptions as da

    register_adapter(ModuleAdapter("frame3d_analysis", "3D frame (2800 / Mabhas 9 / rebar)", da.FRAME_MODULES,
                                   _frame_run, _frame_summary, _frame_intents,
                                   completed=lambda p: p.get("status") == "completed"))
    register_adapter(ModuleAdapter("aisc_steel_beam", "AISC 360 steel beam", ["aisc360"], _aisc_run, _aisc_summary, _aisc_intents,
                                   completed=lambda p: p.get("status") in ("PASS", "FAIL")))
    from app.application import plan_import

    plan_import.register()
