"""Concrete, bilingual prerequisite checklist for optimization (page + chat).

Replaces the vague "optimization is not possible, several steps must be completed first" with one row per
prerequisite: done / missing, why, and how to fix it (link, chat command, or auto-complete with stated defaults).
"""
from __future__ import annotations

from typing import Any

from app.application.frame3d_followup import DEFAULTS as _FRAME_DEFAULTS

_FA_DIGITS = str.maketrans("0123456789.", "۰۱۲۳۴۵۶۷۸۹٫")


def _num(v: float) -> str:
    return f"{v:g}"


def _fa(v: Any) -> str:
    return str(v).translate(_FA_DIGITS)


# Single source of truth: the same DEFAULTS that ``frame3d_followup.apply_defaults`` applies on "assume defaults".
_D = _FRAME_DEFAULTS
_BAYS_EN = f"{_D['bays_x']}x{_D['bays_y']} bays of {_num(_D['bay_x_m'])} m"
_BAYS_FA = f"{_fa(_D['bays_x'])}×{_fa(_D['bays_y'])} دهانه {_fa(_num(_D['bay_x_m']))} متری"

# Example command shown to the user: it describes exactly the frame the defaults produce.
EXAMPLE_COMMAND_EN = f"optimize a {_D['storeys']}-storey frame, {_BAYS_EN}, zone high, soil II"
EXAMPLE_COMMAND_FA = f"قاب {_fa(_D['storeys'])} طبقه با {_BAYS_FA}، پهنه خطر زیاد، خاک نوع ۲ را بهینه کن"

AUTO_ASSUMPTIONS_EN = [
    f"{_D['storeys']} storeys, {_BAYS_EN}, storey height {_num(_D['storey_height_m'])} m",
    "columns 50x50 cm, beams 40x50 cm (typical RC intermediate moment frame)",
    "Iranian codes: Standard 2800 (4th ed.) seismic, Mabhas 6 loads (D, L, E combinations), Mabhas 9 design",
    "allowed sections: the standard catalogue of 5 cm steps (columns 30-90 cm, beams 25x30 to 50x80 cm)",
]
AUTO_ASSUMPTIONS_FA = [
    f"{_fa(_D['storeys'])} طبقه، {_BAYS_FA}، ارتفاع طبقه {_fa(_num(_D['storey_height_m']))} متر",
    "ستون ۵۰×۵۰ و تیر ۴۰×۵۰ سانتی‌متر (قاب خمشی بتنی متوسط معمول)",
    "آیین‌نامه‌های ایران: استاندارد ۲۸۰۰ (ویرایش ۴) برای زلزله، مبحث ۶ برای بارها و ترکیب‌ها، مبحث ۹ برای طراحی",
    "مقاطع مجاز: کاتالوگ استاندارد با گام ۵ سانتی‌متر (ستون ۳۰ تا ۹۰، تیر ۲۵×۳۰ تا ۵۰×۸۰)",
]


def _step(key, done, en, fa, detail_en, detail_fa, action=None, optional=False):
    return {"key": key, "done": bool(done), "optional": optional, "label": {"en": en, "fa": fa},
            "detail": {"en": detail_en, "fa": detail_fa}, "action": action}


def _action(kind, en, fa, href=None, command=None, command_fa=None):
    return {"kind": kind, "label": {"en": en, "fa": fa}, "href": href, "command": command, "command_fa": command_fa}


def _detailing_step(href: str | None = None):
    """Optional last step after Design: rebar detailing sheets (phase 6a) built from the Mabhas 9 design. Never counts as missing."""
    return _step("detailing", False, "Detailing (optional, after design)", "جزئیات‌سازی (اختیاری، پس از طراحی)",
                 "Rebar detailing sheets (DXF) and the structural drawing set are generated from the designed members; not run yet.",
                 "نقشه‌های جزئیات آرماتوربندی (DXF) و نقشه‌های اجرایی سازه از اعضای طراحی‌شده ساخته می‌شوند؛ هنوز اجرا نشده.",
                 _action("chat", "Generate rebar details", "ساخت جزئیات آرماتوربندی", href=href,
                         command="detail the rebar", command_fa="دیتیلینگ آرماتور را بده"),
                 optional=True)


def checklist_for_readiness(report: dict[str, Any], project_id: str | None = None) -> dict[str, Any]:
    """Page checklist from an OptimizationReadinessReport (dict)."""
    ms = report.get("model_summary") or {}
    pid = f"?project={project_id}" if project_id else ""
    members = int(ms.get("member_count") or 0)
    findings_err = any((f or {}).get("status") == "ERROR" for f in report.get("findings") or [])
    steps = [
        _step("model", members > 0 and not findings_err,
              "Structural model defined", "مدل سازه تعریف شده",
              f"{members} member(s) in the model." if members else "The model has no members yet.",
              f"{members} عضو در مدل وجود دارد." if members else "هنوز هیچ عضوی در مدل تعریف نشده است.",
              None if members and not findings_err else
              _action("auto", "Auto-complete with defaults", "تکمیل خودکار با پیش‌فرض‌ها", href=f"/workspace/model{pid}",
                      command="assume defaults and build the model"),
              ),
        _step("code", report.get("code_configuration_valid", True),
              "Design code configuration valid", "آیین‌نامه‌ها معتبر است",
              "Code configuration is consistent." if report.get("code_configuration_valid", True) else "Code configuration has conflicts.",
              "پیکربندی آیین‌نامه سازگار است." if report.get("code_configuration_valid", True) else "پیکربندی آیین‌نامه تعارض دارد.",
              None if report.get("code_configuration_valid", True) else
              _action("link", "Open Validation", "باز کردن اعتبارسنجی", href=f"/workspace/validation{pid}")),
        _step("loads", int(ms.get("load_case_count") or 0) > 0 and int(ms.get("load_combination_count") or 0) > 0,
              "Loads and load combinations", "بارها و ترکیب بارها",
              f"{ms.get('load_case_count', 0)} load case(s), {ms.get('load_combination_count', 0)} combination(s).",
              f"{ms.get('load_case_count', 0)} حالت بار و {ms.get('load_combination_count', 0)} ترکیب بار.",
              _action("chat", "Ask the chat to add Iranian loads/combos", "درخواست از چت برای افزودن بارها و ترکیب‌ها",
                      command="assume defaults: add dead, live and seismic loads with Mabhas 6 combinations")
              if not (int(ms.get("load_case_count") or 0) > 0 and int(ms.get("load_combination_count") or 0) > 0) else None),
        _step("sections", int(ms.get("section_count") or 0) > 0,
              "Allowed sections (candidate list)", "مقاطع مجاز (فهرست کاندیدا)",
              f"{ms.get('section_count', 0)} section(s) defined." if ms.get("section_count") else
              "No sections defined; the standard catalogue will be used if you auto-complete.",
              f"{ms.get('section_count', 0)} مقطع تعریف شده است." if ms.get("section_count") else
              "مقطعی تعریف نشده؛ با تکمیل خودکار از کاتالوگ استاندارد استفاده می‌شود.",
              _action("auto", "Use the standard section catalogue", "استفاده از کاتالوگ استاندارد مقاطع", href=f"/workspace/model{pid}",
                      command="assume defaults for sections") if not ms.get("section_count") else None),
        _step("analysis", int(report.get("usable_analysis_runs") or 0) > 0,
              "Analysis run completed", "تحلیل انجام شده",
              f"{report.get('usable_analysis_runs', 0)} usable of {report.get('available_analysis_runs', 0)} analysis run(s).",
              f"{report.get('usable_analysis_runs', 0)} تحلیل قابل استفاده از {report.get('available_analysis_runs', 0)}.",
              _action("link", "Run analysis", "اجرای تحلیل", href=f"/workspace/analysis{pid}", command="analyze the model")
              if not int(report.get("usable_analysis_runs") or 0) else None),
        _step("design", int(report.get("usable_design_runs") or 0) > 0,
              "Design run completed (recommended)", "طراحی انجام شده (توصیه می‌شود)",
              f"{report.get('usable_design_runs', 0)} usable of {report.get('available_design_runs', 0)} design run(s).",
              f"{report.get('usable_design_runs', 0)} طراحی قابل استفاده از {report.get('available_design_runs', 0)}.",
              _action("link", "Run design", "اجرای طراحی", href=f"/workspace/design{pid}", command="design the members per Mabhas 9")
              if not int(report.get("usable_design_runs") or 0) else None,
              optional=True),
        _detailing_step(f"/workspace/cad{pid}"),
    ]
    required_done = all(s["done"] for s in steps if not s["optional"] and s["key"] != "analysis") and (
        steps[4]["done"] or steps[5]["done"])
    return _finish(steps, required_done)


def _finish(steps: list[dict[str, Any]], ready: bool) -> dict[str, Any]:
    missing = [s for s in steps if not s["done"] and not s["optional"]]
    return {
        "ready": ready,
        "steps": steps,
        "missing_keys": [s["key"] for s in missing],
        "auto_complete": {"available": not ready, "assumptions": {"en": AUTO_ASSUMPTIONS_EN, "fa": AUTO_ASSUMPTIONS_FA},
                          "command": {"en": "assume defaults", "fa": "پیش‌فرض‌ها را فرض کن"}},
    }


def checklist_for_chat(*, has_frame: bool, partial_missing: list[str] | None = None) -> dict[str, Any]:
    """Chat checklist: the in-chat optimizer re-analyses and re-designs internally, so only the frame is mandatory."""
    from app.application.frame3d_followup import friendly_label

    partial_missing = partial_missing or []
    partial_en = [friendly_label(k, False) for k in partial_missing]
    partial_fa = [friendly_label(k, True) for k in partial_missing]
    model_detail_en = ("The frame is described." if has_frame else
                       "No frame described yet" + (f" (missing: {', '.join(partial_en)})" if partial_missing else "") + ".")
    model_detail_fa = ("قاب توصیف شده است." if has_frame else
                       "هنوز قابی توصیف نشده" + (f" (کم: {'، '.join(partial_fa)})" if partial_missing else "") + ".")
    cmd = EXAMPLE_COMMAND_EN
    steps = [
        _step("model", has_frame, "Structural model (storeys, bays, spans)", "مدل سازه (طبقات، دهانه‌ها)", model_detail_en, model_detail_fa,
              None if has_frame else _action("chat", "Describe the frame", "توصیف قاب", command=cmd, command_fa=EXAMPLE_COMMAND_FA)),
        _step("loads", True, "Loads and combinations", "بارها و ترکیب بارها",
              "Mabhas 6 loads and the 2800 combinations are applied automatically.",
              "بارهای مبحث ۶ و ترکیب‌های ۲۸۰۰ به‌صورت خودکار اعمال می‌شوند."),
        _step("sections", True, "Allowed sections", "مقاطع مجاز",
              "The standard catalogue (5 cm steps) is searched; you can restrict it in chat.",
              "کاتالوگ استاندارد (گام ۵ سانتی‌متر) جست‌وجو می‌شود؛ می‌توانید در چت محدودش کنید."),
        _step("analysis", True, "Analysis", "تحلیل", "Run inside the optimization loop (full 3D re-analysis per candidate).",
              "داخل حلقه بهینه‌سازی انجام می‌شود (تحلیل کامل سه‌بعدی برای هر کاندیدا)."),
        _step("design", True, "Design (Mabhas 9)", "طراحی (مبحث ۹)", "Checked inside the loop for every candidate.",
              "برای هر کاندیدا داخل حلقه کنترل می‌شود."),
        _detailing_step(),
    ]
    return _finish(steps, has_frame)


def checklist_markdown(check: dict[str, Any], lang: str = "en", *, extra_assumptions: list[str] | None = None) -> str:
    fa = lang == "fa"
    lines = ["### بهینه‌سازی: پیش‌نیازها" if fa else "### Optimization prerequisites", ""]
    for s in check["steps"]:
        mark = "✅" if s["done"] else ("➖" if s["optional"] else "❌")
        lines.append(f"- {mark} **{s['label']['fa' if fa else 'en']}** — {s['detail']['fa' if fa else 'en']}")
        a = s.get("action")
        if a and not s["done"]:
            how = (a.get("command_fa") if fa else None) or a.get("command") or a.get("href") or ""
            lines.append(f"  - ↳ {a['label']['fa' if fa else 'en']}: `{how}`")
    if not check["ready"]:
        lines += ["", ("برای تکمیل خودکار بنویسید: «**پیش‌فرض‌ها را فرض کن**». فرض‌ها:" if fa
                       else "To auto-complete, reply **assume defaults**. Assumptions I will use:")]
        lines += [f"  - {x}" for x in (check["auto_complete"]["assumptions"]["fa" if fa else "en"])]
    if extra_assumptions:
        lines += [""] + extra_assumptions
    return "\n".join(lines)
