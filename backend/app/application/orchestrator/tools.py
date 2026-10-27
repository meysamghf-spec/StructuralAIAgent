"""The whitelisted operations the orchestrator may run. Each wraps an EXISTING deterministic platform function.

Adding a tool: define it here, register it in :func:`build_registry`, document it in docs/GEMINI_PLATFORM_ORCHESTRATOR.md
(the knowledge test fails otherwise). There is no tool for billing / payments, code edits, shell, SQL or files.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from app.application import chat_actions as ca
from app.application import frame3d_chat_analysis as f3
from app.application import frame3d_followup as fu
from app.application import frame_optimizer as fopt
from app.application.billing import service as billing
from app.application.orchestrator import summaries as sm
from app.application.orchestrator.registry import ACCESS_READ, ACCESS_WRITE, Tool, ToolError, ToolRegistry, ToolResult

ZONES = ["VERY_HIGH", "HIGH", "MODERATE", "LOW"]
SOILS = ["I", "II", "III", "IV"]
SYSTEMS = ["RC_SMF", "RC_IMF", "RC_OMF"]
EXPORT_NAMES = ["e2k", "f2k", "s2k", "structural_set", "dxf_rebar", "dxf_foundation", "dxf_plans", "xlsx_tables",
                "figures_png", "report_pdf", "report_json"]

_EXPORT_ROWS = {  # tool name -> (kind, name, format, label) as in chat_actions._SPECIFIC
    "e2k": ("model", "e2k", "e2k", "ETABS model (.e2k)"), "f2k": ("model", "f2k", "f2k", "SAFE model (.f2k)"),
    "s2k": ("model", "s2k", "s2k", "SAP2000 model (.s2k)"),
    "structural_set": ("drawing", "structural_set", "pdf", "Structural drawing set (PDF)"),
    "dxf_rebar": ("drawing", "dxf_rebar", "dxf", "Rebar details (DXF)"),
    "dxf_foundation": ("drawing", "dxf_foundation", "dxf", "Foundation details (DXF)"),
    "dxf_plans": ("drawing", "dxf_plans", "dxf", "Plans (DXF)"),
    "xlsx_tables": ("table", "all", "xlsx", "All tables (Excel)"),
    "report_pdf": ("report", "report_pdf", "pdf", "Calculation report (PDF)"),
    "report_json": ("report", "report_json", "json", "Raw results (JSON)"),
}


def _num(lo: float, hi: float, desc: str, integer: bool = False) -> dict[str, Any]:
    return {"type": "integer" if integer else "number", "minimum": lo, "maximum": hi, "description": desc}


# --------------------------------------------------------------------------------------------- helpers
def _quota(exc: billing.QuotaExceededError, fa: bool) -> ToolError:
    return ToolError("QUOTA_EXCEEDED",
                     "سقف طرح فعلی شما پر شده است؛ از صفحه Upgrades ارتقا دهید." if fa else exc.message,
                     exc.message, {"quota": exc.details}, status="quota_exceeded")


def _guard_quota(ctx: Any, fn: Any, *a: Any) -> None:
    try:
        fn(*a)
    except billing.QuotaExceededError as exc:
        raise _quota(exc, ctx.fa) from exc


def _inputs_dict(inp: f3.Frame3dInputs, fa: bool) -> dict[str, Any]:
    d = {k: v for k, v in asdict(inp).items() if k != "parsed"}
    d["lang"] = "fa" if fa else "en"
    return d


def _too_large(inp: f3.Frame3dInputs) -> list[str]:
    out: list[str] = []
    if inp.storeys > f3.MAX_STOREYS:
        out.append(f"at most {f3.MAX_STOREYS} storeys")
    if max(inp.bays_x, inp.bays_y) > f3.MAX_BAYS:
        out.append(f"at most {f3.MAX_BAYS} bays per direction")
    if (inp.bays_x + 1) * (inp.bays_y + 1) * (inp.storeys + 1) > f3.MAX_NODES:
        out.append(f"at most {f3.MAX_NODES} nodes")
    return out


def _describe(inp: dict[str, Any] | None, fa: bool) -> str:
    return sm.model_line(inp, fa) if inp else ""


# --------------------------------------------------------------------------------------------- read tools
def _get_platform_state(ctx: Any, args: dict[str, Any]) -> ToolResult:
    port = ctx.port
    model = ctx.current_model()
    usage = port.usage_snapshot()
    data = {"project": port.project, "has_model": model is not None, "model": sm.model_digest(model) if model else None,
            "pending_approvals": port.pending_approvals(), "plan_and_usage": usage,
            "frame_limits": {"max_storeys": f3.MAX_STOREYS, "max_bays_per_direction": f3.MAX_BAYS, "max_nodes": f3.MAX_NODES},
            "defaults_if_missing": fu.DEFAULTS}
    fa_txt = (f"پروژه: {port.project['name'] if port.project else 'ندارد'} | مدل: {_describe(model, True) or 'ندارد'}")
    en_txt = (f"Project: {port.project['name'] if port.project else 'none'} | model: {_describe(model, False) or 'none'}")
    return ToolResult("ok", data, fa_txt, en_txt)


def _platform_knowledge(ctx: Any, args: dict[str, Any]) -> ToolResult:
    from app.application import platform_knowledge as pk

    text = pk.build_platform_knowledge(ctx.fa, args["question"])
    return ToolResult("ok", {"knowledge": text[:5000],
                             "rule": "Answer capability questions ONLY from this text; if a capability is not listed, say it is not available."},
                      "", "")


def _list_projects(ctx: Any, args: dict[str, Any]) -> ToolResult:
    projects = ctx.port.list_projects()
    names = "، ".join(p["name"] for p in projects) or "—"
    return ToolResult("ok", {"projects": [{"name": p["name"]} for p in projects][:30], "current": (ctx.port.project or {}).get("name")},
                      f"پروژه‌های شما: {names}", f"Your projects: {names}")


def _get_current_model(ctx: Any, args: dict[str, Any]) -> ToolResult:
    model = ctx.current_model()
    if model is None:
        return ToolResult("ok", {"has_model": False, "defaults_if_missing": fu.DEFAULTS},
                          "هنوز مدلی در این گفتگو/پروژه نیست.", "There is no model in this chat/project yet.")
    return ToolResult("ok", {"has_model": True, "model": sm.model_digest(model)}, _describe(model, True), _describe(model, False))


def _list_approvals(ctx: Any, args: dict[str, Any]) -> ToolResult:
    items = ctx.port.pending_approvals()
    txt_fa = "\n".join(f"{i}. {s}" for i, s in enumerate(items, 1)) or "موردی منتظر تایید نیست."
    txt_en = "\n".join(f"{i}. {s}" for i, s in enumerate(items, 1)) or "Nothing is waiting for approval."
    return ToolResult("ok", {"pending": items, "note": "Approving or rejecting is a human sign-off: tell the user to say «تایید کن» / “approve” themselves."},
                      txt_fa, txt_en)


# --------------------------------------------------------------------------------------------- project tools
def _open_project(ctx: Any, args: dict[str, Any]) -> ToolResult:
    projects = ctx.port.list_projects()
    q = args["name"].strip().lower()
    hit = next((p for p in projects if p["name"].strip().lower() == q), None) or next((p for p in projects if q in p["name"].lower()), None)
    if hit is None:
        names = [p["name"] for p in projects[:10]]
        raise ToolError("PROJECT_NOT_FOUND", f"پروژه‌ای با نام «{args['name']}» پیدا نشد.", f"No project matches “{args['name']}”.", {"your_projects": names})
    proj = ctx.port.open_project(hit["id"])
    ctx.ui["project_switch"] = {"id": proj["id"], "name": proj["name"]}
    ctx.model_loaded = False  # the model of the opened project is looked up lazily
    return ToolResult("ok", {"opened": proj["name"]}, f"پروژه «{proj['name']}» باز شد.", f"Opened project “{proj['name']}”.")


def _create_project(ctx: Any, args: dict[str, Any]) -> ToolResult:
    name = args.get("name") or ("پروژه جدید" if ctx.fa else "New project")
    try:
        proj = ctx.port.create_project(name)
    except billing.QuotaExceededError as exc:
        raise _quota(exc, ctx.fa) from exc
    ctx.ui["project_switch"] = {"id": proj["id"], "name": proj["name"]}
    ctx.model_loaded = False
    ctx.model = None
    return ToolResult("ok", {"created_and_opened": proj["name"]}, f"پروژه «{proj['name']}» ساخته و باز شد.", f"Created and opened project “{proj['name']}”.")


# --------------------------------------------------------------------------------------------- engineering tools
_ANALYZE_PROPS: dict[str, Any] = {
    "mode": {"type": "string", "enum": ["edit", "new"],
             "description": "edit (default): change only the given fields of the current model. new: build a fresh model (asks the user to confirm when a model exists)."},
    "assume_defaults": {"type": "boolean", "description": "true: fill any missing geometry with the documented defaults (4 storeys, 3x3 bays of 5 m, 3.2 m height) and say so. Use it whenever the user did not give numbers."},
    "storeys": _num(1, 10, "number of storeys", True),
    "bays_x": _num(1, 6, "number of bays in X", True), "bays_y": _num(1, 6, "number of bays in Y", True),
    "bay_x_m": _num(1.5, 15, "bay length in X [m]"), "bay_y_m": _num(1.5, 15, "bay length in Y [m]"),
    "storey_height_m": _num(2.2, 6, "storey height [m]"),
    "column_b_cm": _num(20, 150, "column width [cm]"), "column_h_cm": _num(20, 150, "column depth [cm]"),
    "beam_b_cm": _num(15, 100, "beam width [cm]"), "beam_h_cm": _num(20, 150, "beam depth [cm]"),
    "slab_t_cm": _num(8, 40, "slab thickness [cm]"),
    "fc_mpa": _num(15, 70, "concrete f'c [MPa]"), "fy_mpa": _num(240, 600, "rebar fy [MPa]"),
    "dead_kn_m2": _num(0, 30, "floor dead load [kN/m2]"), "live_kn_m2": _num(0, 20, "floor live load [kN/m2]"),
    "roof_live_kn_m2": _num(0, 20, "roof live load [kN/m2]"), "wall_kn_m": _num(0, 40, "perimeter wall line load [kN/m]"),
    "parapet_kn_m": _num(0, 20, "roof parapet line load [kN/m]"),
    "seismic_code": {"type": "string", "enum": ["IRAN_2800", "ASSUMED_C"], "description": "IRAN_2800 = Standard 2800 4th ed. (default); ASSUMED_C = user-given base shear coefficient seismic_c"},
    "seismic_c": _num(0.01, 0.6, "base shear coefficient C (only with ASSUMED_C)"),
    "behaviour_r": _num(1, 12, "behaviour factor R (ASSUMED_C only)"),
    "zone": {"type": "string", "enum": ZONES, "description": "seismic hazard zone (A=0.35/0.30/0.25/0.20)"},
    "soil": {"type": "string", "enum": SOILS, "description": "site soil type"},
    "importance": _num(0.8, 1.4, "importance factor I"),
    "system": {"type": "string", "enum": SYSTEMS, "description": "RC moment frame ductility: RC_SMF special, RC_IMF intermediate, RC_OMF ordinary"},
    "design_code": {"type": "string", "enum": ["MABHAS9", "NONE"], "description": "MABHAS9 = member design to Mabhas 9 (default); NONE = analysis only"},
    "foundation": {"type": "boolean", "description": "also design isolated footings"},
    "allowable_bearing_kpa": _num(50, 1000, "allowable soil bearing [kPa]"),
    "p_delta": {"type": "string", "enum": ["auto", "on", "off"], "description": "second-order P-Delta effect"},
    "detailing": {"type": "object", "description": "rebar detailing / title block assumptions", "properties": {
        "cover_mm": _num(15, 100, "clear cover [mm]"), "stirrup_db": _num(8, 16, "stirrup diameter [mm]", True),
        "stock_length_m": _num(6, 18, "stock bar length [m]"),
        "project_name": {"type": "string", "maxLength": 80}, "employer": {"type": "string", "maxLength": 80}, "designer": {"type": "string", "maxLength": 80}}},
}
_CM_FIELDS = {"column_b_cm": "column_b_m", "column_h_cm": "column_h_m", "beam_b_cm": "beam_b_m", "beam_h_cm": "beam_h_m", "slab_t_cm": "slab_t_m"}
_DIRECT_FIELDS = ("storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m", "storey_height_m", "fc_mpa", "fy_mpa", "dead_kn_m2", "live_kn_m2",
                  "roof_live_kn_m2", "wall_kn_m", "parapet_kn_m", "seismic_code", "seismic_c", "behaviour_r", "zone", "soil", "importance",
                  "system", "design_code", "foundation", "allowable_bearing_kpa", "p_delta")


def _is_fresh(ctx: Any, args: dict[str, Any]) -> bool:
    cur = ctx.current_model()
    if cur is None or args.get("mode") == "new":
        return True
    return bool(f3.missing_inputs(f3.inputs_from_dict(cur)))


def _confirm_analyze(ctx: Any, args: dict[str, Any]) -> tuple[str, str] | None:
    cur = ctx.current_model()
    if cur is None or args.get("mode") != "new" or f3.missing_inputs(f3.inputs_from_dict(cur)):
        return None
    fa_t = f"مدل فعلی ({_describe(cur, True)}) با یک مدل جدید جایگزین شود. (تحلیل‌های قبلی در تاریخچه می‌مانند.)"
    en_t = f"replace the current model ({_describe(cur, False)}) with a new one (earlier runs stay in the history)."
    return fa_t, en_t


def _build_inputs(ctx: Any, args: dict[str, Any]) -> tuple[f3.Frame3dInputs, list[str], bool]:
    fresh = _is_fresh(ctx, args)
    given: dict[str, Any] = {k: args[k] for k in _DIRECT_FIELDS if k in args}
    for src, dst in _CM_FIELDS.items():
        if src in args:
            given[dst] = round(args[src] / 100.0, 4)
    inp = f3.Frame3dInputs() if fresh else f3.inputs_from_dict(ctx.current_model() or {})
    for k, v in given.items():
        setattr(inp, k, v)
    if args.get("detailing"):
        inp.assumptions = {**(inp.assumptions or {}), **args["detailing"]}
    assumed: list[str] = []
    if fresh:
        inp.parsed = list(given)
        if f3.missing_inputs(inp) and not args.get("assume_defaults"):
            miss = f3.missing_inputs(inp)
            raise ToolError("MISSING_INPUTS", f"داده‌های لازم ناقص است: {', '.join(miss)}", f"Missing required inputs: {', '.join(miss)}",
                            {"missing": miss, "defaults_available": fu.DEFAULTS,
                             "hint": "Call again with assume_defaults=true (preferred) or ask the user only for these."}, status="missing_inputs")
        assumed = fu.apply_defaults(inp)
        for explicit in ("seismic_code", "design_code"):  # apply_defaults must not override what the user asked for
            if explicit in given:
                setattr(inp, explicit, given[explicit])
                assumed = [a for a in assumed if a != explicit]
    return inp, assumed, fresh


def _analyze_frame(ctx: Any, args: dict[str, Any]) -> ToolResult:
    inp, assumed, fresh = _build_inputs(ctx, args)
    inp.lang = "fa" if ctx.fa else "en"
    problems = _too_large(inp)
    if problems:
        raise ToolError("MODEL_TOO_LARGE", "اندازهٔ مدل از حد مجاز تحلیل در چت بیشتر است: " + "؛ ".join(problems),
                        "Model exceeds the chat analysis limits: " + "; ".join(problems), {"limits": problems})
    d = _inputs_dict(inp, ctx.fa)
    _guard_quota(ctx, ctx.port.check_frame_size, d)
    _guard_quota(ctx, ctx.port.consume_analysis)
    payload = f3.build_frame3d_payload("", None, manual_inputs=d)
    if not isinstance(payload, dict) or payload.get("kind") != "frame3d_analysis" or not payload.get("results"):
        raise ToolError("ANALYSIS_FAILED", "تحلیل کامل نشد: " + str((payload or {}).get("message", "")), "The analysis did not complete: " + str((payload or {}).get("message", "")),
                        {"engine_message": str((payload or {}).get("message", ""))[:300]})
    ctx.set_model(payload.get("inputs") or d)
    ctx.payload = payload
    ctx.assumed = sorted(set(ctx.assumed) | set(assumed))
    digest = sm.analysis_digest(payload, assumed)
    digest["model_was_new"] = fresh
    return ToolResult("ok", digest, f3.frame3d_markdown(payload), f3.frame3d_markdown(payload), ui={"engineering_results": payload})


def _optimize_frame(ctx: Any, args: dict[str, Any]) -> ToolResult:
    _guard_quota(ctx, ctx.port.require_optimization)
    cur = ctx.current_model()
    assumed: list[str] = []
    if cur is None or f3.missing_inputs(f3.inputs_from_dict(cur)):
        if not args.get("assume_defaults"):
            raise ToolError("NO_MODEL", "برای بهینه‌سازی باید ابتدا مدلی وجود داشته باشد.", "There is no model to optimize yet.",
                            {"hint": "Call analyze_frame first, or call optimize_frame with assume_defaults=true.", "defaults_available": fu.DEFAULTS},
                            status="missing_inputs")
        inp = f3.Frame3dInputs()
        assumed = fu.apply_defaults(inp)
    else:
        inp = f3.inputs_from_dict(cur)
    inp.lang = "fa" if ctx.fa else "en"
    _guard_quota(ctx, ctx.port.check_frame_size, _inputs_dict(inp, ctx.fa))
    budget = min(float(args.get("time_budget_s") or ctx.settings.optimize_budget_s), float(ctx.settings.optimize_budget_s))
    options: dict[str, Any] = {"time_budget_s": budget, "objective": args.get("objective", "cost")}
    res = fopt.optimize_frame(inp, options)
    ctx.payload = res
    ctx.assumed = sorted(set(ctx.assumed) | set(assumed))
    digest = sm.optimization_digest(res)
    if assumed:
        digest["assumed_by_platform"] = assumed
    text = fopt.optimization_markdown(res, "fa" if ctx.fa else "en")
    return ToolResult("ok", digest, text, text, ui={"engineering_results": res})


def _export_files(ctx: Any, args: dict[str, Any]) -> ToolResult:
    fa = ctx.fa
    cur = ctx.current_model()
    assumed: list[str] = []
    if cur is None:
        cur, assumed = ca.default_frame_inputs(fa)
        ctx.assumed = sorted(set(ctx.assumed) | set(assumed))
    if fa:
        cur = {**cur, "lang": "fa"}
    names = args.get("files") or []
    if args.get("everything"):
        spec: dict[str, Any] = {"zip": True, "items": []}
    else:
        if not names:
            raise ToolError("NO_FILES", "نوع فایل مشخص نشده است.", "No file type given.", {"allowed": EXPORT_NAMES})
        items: list[dict[str, str]] = []
        for n in dict.fromkeys(names):
            if n == "figures_png":
                items += [{"kind": "figure", "name": k, "format": "png", "label": f"{lab} (PNG)"} for k, lab in ca._FIGURES_ALL]
            else:
                kind, name, fmt, label = _EXPORT_ROWS[n]
                items.append({"kind": kind, "name": name, "format": fmt, "label": label})
        spec = {"zip": False, "items": items}
    spec, withheld = ca.apply_plan(spec, ctx.port.plan_exports(), fa)
    text, meta = ca.downloads_reply(spec, cur, fa=fa, assumed=assumed, withheld=withheld,
                                    project_id=(ctx.port.project or {}).get("id"))
    ctx.ui["chat_downloads"] = meta["chat_downloads"]
    data = {"prepared": [i["label"] for i in spec["items"]] if not spec["zip"] else ["ZIP with all outputs"],
            "withheld_by_plan": withheld, "assumed_by_platform": assumed,
            "honesty": ("ETABS/SAFE/SAP2000 import files are generated from public command references and were NOT yet verified inside the real "
                        "programs: tell the user to check the model after import.") if any(n in ("e2k", "f2k", "s2k") for n in names) else None,
            "delivery": "The download buttons appear under your message automatically."}
    return ToolResult("ok", {k: v for k, v in data.items() if v}, text, text, ui={})


def _analyze_beam(ctx: Any, args: dict[str, Any]) -> ToolResult:
    from app.application import general_beam_engine as gbe

    res = gbe.analyze_beam_prompt(args["description"])
    if not isinstance(res, dict):
        raise ToolError("BEAM_NOT_UNDERSTOOD", "مشخصات تیر قابل تشخیص نبود (دهانه، بار، تکیه‌گاه).", "I could not read a beam from that description (span, load, supports).")
    payload = res.get("payload") or res.get("engineering_results")
    md = str(res.get("markdown") or res.get("content") or "")
    ui = {"engineering_results": payload} if isinstance(payload, dict) else {}
    if isinstance(payload, dict):
        ctx.payload = payload
    data = {"markdown_summary": md[:2500], "assumptions": res.get("assumptions")}
    return ToolResult("ok", {k: v for k, v in data.items() if v}, md, md, ui=ui)


# --------------------------------------------------------------------------------------------- registry
def build_registry() -> ToolRegistry:
    r = ToolRegistry()
    obj = lambda props, req=None: {"type": "object", "properties": props, **({"required": req} if req else {})}  # noqa: E731
    r.register(Tool("get_platform_state", "Current project, whether a model exists, its key inputs, plan limits/usage and pending approvals. Call first when unsure of the state.",
                    obj({}), _get_platform_state, ACCESS_READ, maps_to="context"))
    r.register(Tool("platform_knowledge", "Look up what the platform can and cannot do (pages, engines, exports, plan limits, chat commands). Use before answering capability questions.",
                    obj({"question": {"type": "string", "maxLength": 300}}, ["question"]), _platform_knowledge, ACCESS_READ, maps_to="help"))
    r.register(Tool("list_projects", "List the user's projects.", obj({}), _list_projects, ACCESS_READ, maps_to="projects"))
    r.register(Tool("open_project", "Open one of the user's existing projects by (part of) its name; the chat then works inside it.",
                    obj({"name": {"type": "string", "maxLength": 120}}, ["name"]), _open_project, ACCESS_WRITE, maps_to="projects"))
    r.register(Tool("create_project", "Create a new project and open it. Project limits of the plan apply.",
                    obj({"name": {"type": "string", "maxLength": 120}}), _create_project, ACCESS_WRITE, maps_to="projects"))
    r.register(Tool("get_current_model", "Inputs of the current 3D frame model (geometry, sections, loads, codes), or none.", obj({}), _get_current_model, ACCESS_READ, maps_to="frame3d"))
    r.register(Tool("analyze_frame", "Create or modify the 3D RC frame model and run the full analysis: units are SI (m, kN, MPa); seismic Standard 2800 (4th ed.), "
                    "design Mabhas 9, optional footings. Fields not given keep their current/default values. Returns the numeric results to explain. "
                    "Max 10 storeys, 6 bays per direction.", obj(_ANALYZE_PROPS), _analyze_frame, ACCESS_WRITE, confirm=_confirm_analyze, maps_to="frame3d"))
    r.register(Tool("optimize_frame", "Optimize the current frame's member sections (fully-stressed design + genetic algorithm, Mabhas 9 + 2800 drift constraints). Takes up to ~30 s. "
                    "Needs a model (or assume_defaults=true). Plan feature 'optimization' applies.",
                    obj({"objective": {"type": "string", "enum": ["cost", "weight"]}, "time_budget_s": _num(5, 40, "time budget [s]", True),
                         "assume_defaults": {"type": "boolean"}}), _optimize_frame, ACCESS_WRITE, maps_to="optimizer"))
    r.register(Tool("export_files", "Prepare downloads for the current model: ETABS e2k, SAFE f2k, SAP2000 s2k, drawings (PDF/DXF), Excel tables, PNG figures, calculation report. "
                    "Plan export limits apply. Buttons are attached to the reply automatically.",
                    obj({"files": {"type": "array", "maxItems": 11, "items": {"type": "string", "enum": EXPORT_NAMES}},
                         "everything": {"type": "boolean", "description": "true: one ZIP with all outputs"}}), _export_files, ACCESS_WRITE, maps_to="downloads"))
    r.register(Tool("analyze_beam", "Single-beam analysis from a plain description (span, loads, supports, section); numbers come from the engine.",
                    obj({"description": {"type": "string", "maxLength": 400}}, ["description"]), _analyze_beam, ACCESS_WRITE, maps_to="beam"))
    r.register(Tool("list_approvals", "List items waiting for human approval in the current project (read-only; approving stays a user action).",
                    obj({}), _list_approvals, ACCESS_READ, maps_to="approvals"))
    return r


_REGISTRY: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_registry()
    return _REGISTRY
