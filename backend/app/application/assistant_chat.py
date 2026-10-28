"""Assistant-specific chat replies ("Use this assistant").

When the user opens chat from the Assistants page the request carries an ``assistant`` agent type.
Each assistant answers from the latest deterministic frame3d result of the conversation/project (numbers
come from the engines, never from an LLM). If the message is itself a new model request / edit, the
normal chat engines run instead (``wants_engine``), so assume-defaults and edits keep working.
"""
from __future__ import annotations

from typing import Any, Callable

ASSISTANT_TYPES = (
    "STRUCTURAL_MODELING_AGENT", "LOAD_ASSESSMENT_AGENT", "ANALYSIS_AGENT", "CONCRETE_DESIGN_AGENT",
    "STEEL_DESIGN_AGENT", "SEISMIC_AGENT", "VALIDATION_AGENT", "CAD_AGENT", "REPORTING_AGENT",
    "DOCUMENT_INTERPRETATION_AGENT", "OPTIMIZATION_AGENT", "STRUCTURAL_ENGINEERING_AGENT",
)

TITLES = {
    "STRUCTURAL_MODELING_AGENT": ("Structural Modeling Assistant", "دستیار مدل‌سازی سازه"),
    "LOAD_ASSESSMENT_AGENT": ("Load Assessment Assistant", "دستیار ارزیابی بار"),
    "ANALYSIS_AGENT": ("Structural Analysis Assistant", "دستیار تحلیل سازه"),
    "CONCRETE_DESIGN_AGENT": ("Concrete Design Assistant", "دستیار طراحی بتن"),
    "STEEL_DESIGN_AGENT": ("Steel Design Assistant", "دستیار طراحی فولاد"),
    "SEISMIC_AGENT": ("Seismic Design Assistant", "دستیار طراحی لرزه‌ای"),
    "VALIDATION_AGENT": ("Design Validation Assistant", "دستیار اعتبارسنجی طرح"),
    "CAD_AGENT": ("CAD Coordination Assistant", "دستیار نقشه‌کشی"),
    "REPORTING_AGENT": ("Engineering Report Assistant", "دستیار گزارش مهندسی"),
    "DOCUMENT_INTERPRETATION_AGENT": ("Document Interpretation Assistant", "دستیار تفسیر مدارک"),
    "OPTIMIZATION_AGENT": ("Optimization Assistant", "دستیار بهینه‌سازی"),
    "STRUCTURAL_ENGINEERING_AGENT": ("Structural Engineering Agent", "عامل مهندسی سازه"),
}

STARTERS: dict[str, tuple[list[str], list[str]]] = {
    "LOAD_ASSESSMENT_AGENT": (
        ["Summarize the load combinations", "Show the loading summary per Mabhas 6 / 2800",
         "3-storey RC frame, 3x3 bays of 5 m, storey height 3.2 m, high hazard, soil II"],
        ["ترکیب بارها را خلاصه کن", "خلاصه بارگذاری طبق مبحث ۶ و ۲۸۰۰",
         "قاب بتنی ۳ طبقه با ۳x۳ دهانه ۵ متر، ارتفاع طبقه ۳.۲، خطر زیاد، خاک ۲"]),
    "ANALYSIS_AGENT": (
        ["Review the analysis results", "Check drift and stability", "Summarize results and member maxima"],
        ["نتایج تحلیل را بررسی کن", "دریفت و پایداری را کنترل کن", "خلاصه نتایج و بیشینه نیروها"]),
    "STRUCTURAL_MODELING_AGENT": (
        ["Summarize the structural model", "4-storey RC frame, 3x3 bays of 5 m, storey height 3.2 m"],
        ["مدل سازه را خلاصه کن", "قاب بتنی ۴ طبقه با ۳x۳ دهانه ۵ متر"]),
    "CONCRETE_DESIGN_AGENT": (
        ["Summarize the Mabhas 9 concrete design", "Which groups fail and why?"],
        ["خلاصه طراحی بتن طبق مبحث نهم", "کدام گروه‌ها رد می‌شوند و چرا؟"]),
    "STEEL_DESIGN_AGENT": (
        ["Analyze a simply supported steel beam, span 6 m, 20 kN/m", "What can and can't the steel assistant do?"],
        ["تیر فولادی ساده با دهانه ۶ متر و بار ۲۰ kN/m را تحلیل کن", "دستیار فولاد چه کارهایی می‌کند و چه کارهایی نمی‌کند؟"]),
    "SEISMIC_AGENT": (
        ["Show the Standard 2800 seismic parameters", "Base shear and storey forces", "Drift check"],
        ["پارامترهای لرزه‌ای استاندارد ۲۸۰۰", "برش پایه و نیروی طبقات", "کنترل دریفت"]),
    "VALIDATION_AGENT": (
        ["Validate this design", "List all warnings and failed checks"],
        ["این طرح را اعتبارسنجی کن", "همه هشدارها و کنترل‌های رد شده را فهرست کن"]),
    "CAD_AGENT": (
        ["What drawings can be produced from this model?", "Generate the structural drawing set"],
        ["از این مدل چه نقشه‌هایی ساخته می‌شود؟", "مجموعه نقشه‌های سازه را تولید کن"]),
    "REPORTING_AGENT": (
        ["Write the engineering report summary", "List the runs available for a report"],
        ["خلاصه گزارش مهندسی را بنویس", "اجراهای آماده گزارش را فهرست کن"]),
    "DOCUMENT_INTERPRETATION_AGENT": (
        ["Attach a PDF/Excel/DXF/image and I will interpret it", "What file types are supported?"],
        ["یک PDF/اکسل/DXF/تصویر پیوست کنید تا تفسیر کنم", "چه فرمت‌هایی پشتیبانی می‌شود؟"]),
    "OPTIMIZATION_AGENT": (
        ["What is missing before optimization can run?", "Optimize the frame sections for cost"],
        ["قبل از بهینه‌سازی چه چیزهایی کم است؟", "مقاطع قاب را برای کاهش هزینه بهینه کن"]),
    "STRUCTURAL_ENGINEERING_AGENT": (
        ["3-storey RC frame, 2x2 bays of 5 m, analyze and design", "Explain the platform to me"],
        ["قاب بتنی ۳ طبقه ۲x۲ دهانه ۵ متر را تحلیل و طراحی کن", "پلتفرم را به من توضیح بده"]),
}


def is_persian(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in text or "")


def normalize_assistant(value: str | None) -> str | None:
    if not value:
        return None
    key = value.strip().upper()
    return key if key in ASSISTANT_TYPES else None


def starters(agent_type: str, fa: bool) -> list[str]:
    pair = STARTERS.get(agent_type) or STARTERS["STRUCTURAL_ENGINEERING_AGENT"]
    return list(pair[1] if fa else pair[0])


def assistant_title(agent_type: str, fa: bool) -> str:
    en, fa_t = TITLES.get(agent_type, (agent_type, agent_type))
    return fa_t if fa else en


def _f(v: Any, nd: int = 2) -> str:
    try:
        return f"{float(v):.{nd}f}"
    except (TypeError, ValueError):
        return "—"


def _status_icon(status: Any) -> str:
    s = str(status or "").upper()
    return "✅" if s in {"PASS", "OK", "COMPLETE"} else ("⚠️" if s in {"CHECK", "WARN"} else ("❌" if s == "FAIL" else "•"))


def _guide(agent_type: str, fa: bool) -> str:
    items = "\n".join(f"- `{s}`" for s in starters(agent_type, fa))
    if fa:
        return (f"**{assistant_title(agent_type, fa)}**\n\nهنوز نتیجهٔ تحلیلی در این گفتگو یا پروژه نیست. "
                f"ابتدا مشخصات قاب را بنویسید (تعداد طبقه و دهانه‌ها کافی است؛ بقیه با پیش‌فرض‌های اعلام‌شده تکمیل می‌شود) "
                f"و بعد این دستیار نتایج را خلاصه می‌کند. نمونه‌ها:\n\n{items}")
    return (f"**{assistant_title(agent_type, fa)}**\n\nThere is no analysis result in this conversation or project yet. "
            f"Describe the frame first (storeys and bays are enough; the rest is completed with stated defaults) "
            f"and this assistant will summarise the results. Examples:\n\n{items}")


def _load_assessment(p: dict, fa: bool) -> str:
    s = p.get("seismic") or {}
    ms = p.get("model_summary") or {}
    r = p.get("results") or {}
    bs = p.get("base_shear_check") or {}
    combos = ms.get("load_combinations") or []
    inp = p.get("inputs") or {}
    lines = []
    if fa:
        lines += ["### خلاصه بارگذاری", f"- بار مرده {inp.get('dead_kn_m2', '—')} kN/m²، زنده {inp.get('live_kn_m2', '—')} kN/m²، زنده بام {inp.get('roof_live_kn_m2', '—')} kN/m²",
                  f"- بار دیوار {inp.get('wall_kn_m', '—')} kN/m، جان‌پناه {inp.get('parapet_kn_m', '—')} kN/m",
                  f"- وزن لرزه‌ای W = {_f(r.get('seismic_weight_kn'), 1)} kN ({s.get('seismic_weight', 'D + 0.2L')})",
                  f"- ضریب زلزله C = {_f(s.get('C'), 4)} (A={s.get('A', '—')}، خاک {s.get('soil', '—')}، I={s.get('I', '—')}، R={s.get('R', '—')})",
                  f"- برش پایه V = {_f(bs.get('V_expected_kn'), 1)} kN", "", "### ترکیب بارها"]
    else:
        lines += ["### Loading summary", f"- Dead {inp.get('dead_kn_m2', '—')} kN/m², live {inp.get('live_kn_m2', '—')} kN/m², roof live {inp.get('roof_live_kn_m2', '—')} kN/m²",
                  f"- Wall {inp.get('wall_kn_m', '—')} kN/m, parapet {inp.get('parapet_kn_m', '—')} kN/m",
                  f"- Seismic weight W = {_f(r.get('seismic_weight_kn'), 1)} kN ({s.get('seismic_weight', 'D + 0.2L')})",
                  f"- Seismic coefficient C = {_f(s.get('C'), 4)} (A={s.get('A', '—')}, soil {s.get('soil', '—')}, I={s.get('I', '—')}, R={s.get('R', '—')})",
                  f"- Base shear V = {_f(bs.get('V_expected_kn'), 1)} kN", "", "### Load combinations"]
    lines += [f"{i}. `{c}`" for i, c in enumerate(combos, 1)] or ["—"]
    return "\n".join(lines)


def _stability_note(pd: dict | None, fa: bool) -> str:
    """Honest P-Δ / stability line from the analysis payload (``p_delta``)."""
    pd = pd or {}
    th = pd.get("theta_max") or {}
    if not th:
        return ("> پایداری: برای این تحلیل ضریب پایداری θ محاسبه نشده؛ اثر P-Δ باید جداگانه کنترل شود." if fa
                else "> Stability: no stability index θ was computed for this analysis; check P-Δ separately.")
    txt_th = f"θ(X) = {_f(th.get('X'), 3)}, θ(Y) = {_f(th.get('Y'), 3)}"
    if pd.get("applied"):
        lam = _f(pd.get("lambda_cr"), 2)
        return (f"> پایداری: تحلیل مرتبهٔ دوم (P-Δ) انجام شده است ({txt_th}، حد صرف‌نظر ۰٫۱ و حد بیشینه {_f(pd.get('theta_limit'), 3)} طبق بند ۳-۶ استاندارد ۲۸۰۰؛ ضریب بار بحرانی λcr = {lam}). لاغری موضعی عضو (P-δ) در طراحی کنترل نمی‌شود." if fa
                else f"> Stability: second-order (P-Δ) analysis is included ({txt_th}; ignore-limit 0.1 and maximum {_f(pd.get('theta_limit'), 3)} per Standard 2800 §3-6; elastic critical load factor λcr = {lam}). Local member slenderness (P-δ) is not checked in the design.")
    status = pd.get("status")
    if fa:
        why = {"OFF": "خاموش شده است", "UNSTABLE": "ناموفق بود (ناپایدار)"}.get(status, "لازم نبود یا اعمال نشد")
        return f"> پایداری: اثر P-Δ در این تحلیل لحاظ نشده ({why}). {txt_th}؛ اگر θ > ۰٫۱ باشد استاندارد ۲۸۰۰ لحاظ P-Δ را الزامی می‌داند."
    why = {"OFF": "switched off", "UNSTABLE": "failed: unstable"}.get(status, "not required or not applied")
    return f"> Stability: P-Δ is not included in this analysis ({why}). {txt_th}; Standard 2800 requires P-Δ when θ > 0.1."


def _analysis(p: dict, fa: bool) -> str:
    r = p.get("results") or {}
    s = p.get("seismic") or {}
    bs = p.get("base_shear_check") or {}
    modal = p.get("modal") or {}
    drift = r.get("max_drift_amplified_pct")
    lim = float(s.get("drift_limit") or 0.025) * 100
    ok = drift is not None and float(drift) <= lim
    eq = r.get("equilibrium_error_kn")
    if fa:
        return "\n".join([
            "### بازبینی تحلیل", f"- تعادل: خطای مجموع نیروها {_f(eq, 6)} kN ({'✅ قابل قبول' if eq is not None and abs(float(eq)) < 1 else '⚠️ بررسی شود'})",
            f"- دریفت بیشینه (تشدیدشده) {_f(drift, 2)}٪ در طبقه {r.get('max_drift_storey', '—')} جهت {r.get('max_drift_direction', '—')} — حد مجاز {_f(lim, 2)}٪ {'✅' if ok else '❌'}",
            f"- کنترل برش پایه: {_status_icon(bs.get('status'))} {bs.get('status', '—')} (V واکنش {_f(bs.get('V_reaction_x_kn'), 1)} در برابر V مورد انتظار {_f(bs.get('V_expected_kn'), 1)} kN)",
            f"- پریود اصلی (مودال) T1 = {_f(modal.get('T_fundamental_s'), 3)} s، تجربی {_f(s.get('T_empirical_s'), 3)} s",
            f"- بیشینه لنگر تیر {_f(r.get('beam_max_M_neg_kn_m'), 1)} kN·m، برش تیر {_f(r.get('beam_max_V_kn'), 1)} kN",
            f"- بیشینه نیروی محوری ستون {_f(r.get('column_max_P_kn'), 1)} kN، لنگر ستون {_f(r.get('column_max_M_kn_m'), 1)} kN·m",
            "", _stability_note(p.get("p_delta"), True)])
    return "\n".join([
        "### Analysis review", f"- Equilibrium: force-sum error {_f(eq, 6)} kN ({'✅ acceptable' if eq is not None and abs(float(eq)) < 1 else '⚠️ check'})",
        f"- Max amplified drift {_f(drift, 2)}% at storey {r.get('max_drift_storey', '—')} direction {r.get('max_drift_direction', '—')} — limit {_f(lim, 2)}% {'✅' if ok else '❌'}",
        f"- Base-shear check: {_status_icon(bs.get('status'))} {bs.get('status', '—')} (reaction {_f(bs.get('V_reaction_x_kn'), 1)} vs expected {_f(bs.get('V_expected_kn'), 1)} kN)",
        f"- Fundamental period (modal) T1 = {_f(modal.get('T_fundamental_s'), 3)} s, empirical {_f(s.get('T_empirical_s'), 3)} s",
        f"- Max beam moment {_f(r.get('beam_max_M_neg_kn_m'), 1)} kN·m, beam shear {_f(r.get('beam_max_V_kn'), 1)} kN",
        f"- Max column axial {_f(r.get('column_max_P_kn'), 1)} kN, column moment {_f(r.get('column_max_M_kn_m'), 1)} kN·m",
        "", _stability_note(p.get("p_delta"), False)])


def _model(p: dict, fa: bool) -> str:
    ms = p.get("model_summary") or {}
    inp = p.get("inputs") or {}
    keys = ("storeys", "bays_x", "bays_y", "bay_x_m", "bay_y_m", "storey_height_m", "column_b_m", "column_h_m", "beam_b_m", "beam_h_m", "fc_mpa", "fy_mpa")
    head = "### مدل سازه" if fa else "### Structural model"
    rows = [f"- {k}: {inp.get(k)}" for k in keys if inp.get(k) is not None]
    cnt = f"\n- nodes {ms.get('nodes')}, elements {ms.get('elements')} (columns {ms.get('columns')}, beams {ms.get('beams')}), DOF {ms.get('dof')}"
    return head + "\n" + "\n".join(rows) + cnt


def _seismic(p: dict, fa: bool) -> str:
    s = p.get("seismic") or {}
    fl = s.get("F_level_kn") or {}
    dc = p.get("drift_check")
    head = "### پارامترهای لرزه‌ای (استاندارد ۲۸۰۰)" if fa else "### Seismic parameters (Standard 2800)"
    body = [f"- A={s.get('A')} ({s.get('zone_label')}), soil {s.get('soil')}, I={s.get('I')}, {s.get('system_label')} R={s.get('R')}, Cd={s.get('Cd')}",
            f"- T = {_f(s.get('T_empirical_s'), 3)} s, B = {_f(s.get('B'), 3)}, C = {_f(s.get('C'), 4)} (Cmin {_f(s.get('C_min'), 4)}), k = {s.get('k')}",
            "- " + ("نیروی طبقات" if fa else "Storey forces") + ": " + ", ".join(f"{k}: {_f(v, 1)} kN" for k, v in fl.items()),
            f"- {'کنترل دریفت' if fa else 'Drift check'}: {_status_icon(dc)} {dc}"]
    return head + "\n" + "\n".join(body)


def _concrete(p: dict, fa: bool) -> str:
    d = p.get("design") or {}
    if not d:
        return ("طراحی بتن هنوز اجرا نشده است. بنویسید: «طبق مبحث نهم طراحی کن»." if fa
                else "Concrete design has not been run. Say: \"design per Mabhas 9\".")
    sm = d.get("summary") or {}
    fdn = p.get("foundation") or {}
    head = "### طراحی بتن (مبحث نهم)" if fa else "### Concrete design (Mabhas 9)"
    out = [f"- {'وضعیت' if fa else 'Status'}: {_status_icon(d.get('status'))} {d.get('status')} ({'اعضا' if fa else 'members'}: {d.get('member_status')}, SCWB: {d.get('scwb_status')})",
           f"- max D/C = {sm.get('max_DC')}, {sm.get('groups_failing')}/{sm.get('groups')} {'گروه رد' if fa else 'groups failing'}, SCWB min = {sm.get('scwb_min_ratio')}"]
    if fdn:
        out.append(f"- {'پی' if fa else 'Foundation'}: {_status_icon(fdn.get('status'))} {fdn.get('status')}, qa {fdn.get('qa_kpa')} kPa" + (" (assumed)" if fdn.get("qa_assumed") else ""))
    return head + "\n" + "\n".join(out)


def _steel(p: dict, fa: bool) -> str:
    return ("دستیار فولاد فقط تحلیل الاستیک یک تیر تکی را انجام می‌دهد (واکنش‌ها، لنگر، برش، خیز)؛ مثال: «تیر فولادی ساده با دهانه ۶ متر و بار ۲۰ kN/m را تحلیل کن». کنترل ظرفیت مقطع فولادی، اتصالات و طراحی قاب فولادی هنوز در این پلتفرم موجود نیست و گزارش نمی‌شود."
            if fa else "The steel assistant only does elastic analysis of a single beam (reactions, moment, shear, deflection), e.g. \"analyze a simply supported steel beam, span 6 m, 20 kN/m\". Steel section capacity checks, connections and steel-frame design are not available on this platform yet and are not reported.")


def _validation(p: dict, fa: bool) -> str:
    items = [("drift", p.get("drift_check")), ("base shear", (p.get("base_shear_check") or {}).get("status")),
             ("Mabhas 9", (p.get("design") or {}).get("status")), ("SCWB", (p.get("design") or {}).get("scwb_status")),
             ("foundation", (p.get("foundation") or {}).get("status"))]
    rows = [f"- {_status_icon(v)} {k}: {v}" for k, v in items if v]
    warns = [f"- ⚠️ {w}" for w in (p.get("warnings") or [])]
    head = "### اعتبارسنجی" if fa else "### Validation"
    note = ("\n\n> این اعتبارسنجی محاسباتی است؛ تأیید نهایی مهندسی با مهندس مسئول است." if fa
            else "\n\n> This is a computational validation; final engineering approval rests with the responsible engineer.")
    return head + "\n" + "\n".join(rows + warns) + note


def _cad(p: dict, fa: bool) -> str:
    return ("از این مدل می‌توان مجموعه نقشه (پلان، مقاطع، جداول آرماتور) تولید کرد. بنویسید «مجموعه نقشه‌های سازه را تولید کن» یا صفحه CAD را باز کنید."
            if fa else "A drawing set (plans, sections, schedules) can be produced from this model. Say \"generate the structural drawing set\" or open the CAD page.")


def _reporting(p: dict, fa: bool) -> str:
    r = p.get("results") or {}
    d = p.get("design") or {}
    return (("### خلاصه گزارش\n" if fa else "### Report summary\n") +
            f"- {p.get('label')}: W={_f(r.get('seismic_weight_kn'), 1)} kN, drift={_f(r.get('max_drift_amplified_pct'), 2)}% ({p.get('drift_check')}), "
            f"design={d.get('status', 'n/a')}\n- " + ("گزارش کامل از صفحه Reports قابل دریافت است." if fa else "The full report is available from the Reports page."))


def _optimization(p: dict, fa: bool) -> str:
    return ("برای بهینه‌سازی، مدل و تحلیل و طراحی باید کامل باشد. بنویسید «بهینه‌سازی کن» تا پیش‌نیازهای جاافتاده فهرست شود یا خودکار با پیش‌فرض‌ها تکمیل شود."
            if fa else "Optimization needs a model, analysis and design. Say \"optimize\" to list missing prerequisites or auto-complete them with defaults.")


SUMMARIZERS: dict[str, Callable[[dict, bool], str]] = {
    "LOAD_ASSESSMENT_AGENT": _load_assessment, "ANALYSIS_AGENT": _analysis, "STRUCTURAL_MODELING_AGENT": _model,
    "SEISMIC_AGENT": _seismic, "CONCRETE_DESIGN_AGENT": _concrete, "STEEL_DESIGN_AGENT": _steel,
    "VALIDATION_AGENT": _validation, "CAD_AGENT": _cad, "REPORTING_AGENT": _reporting, "OPTIMIZATION_AGENT": _optimization,
}


def wants_engine(text: str, *, has_attachments: bool, prior_user_texts: list[str]) -> bool:
    """True when the message must go to the regular engines (new/edited model, optimization, beam, files)."""
    if has_attachments:
        return True
    from app.application import frame3d_followup as fu
    from app.application import frame_optimizer as fopt
    from app.application import general_beam_engine as gbe
    from app.application.frame3d_chat_analysis import is_frame3d_request

    merged = fu.merge_with_pending(text, prior_user_texts)
    if is_frame3d_request(merged) or fu.is_frame_followup(merged) or fopt.is_optimize_request(text):
        return True
    try:
        return gbe.analyze_beam_prompt(text) is not None
    except Exception:  # noqa: BLE001
        return False


def assistant_reply(agent_type: str, text: str, payload: dict[str, Any] | None) -> tuple[str, dict[str, Any]]:
    fa = is_persian(text)
    if agent_type in ("DOCUMENT_INTERPRETATION_AGENT", "STRUCTURAL_ENGINEERING_AGENT") or agent_type not in SUMMARIZERS:
        body = _guide(agent_type, fa) if agent_type == "DOCUMENT_INTERPRETATION_AGENT" else _guide("STRUCTURAL_ENGINEERING_AGENT", fa)
        return body, {"mode": "assistant", "assistant": agent_type, "starters": starters(agent_type, fa)}
    if agent_type in ("STEEL_DESIGN_AGENT", "CAD_AGENT", "OPTIMIZATION_AGENT") or payload:
        body = SUMMARIZERS[agent_type](payload or {}, fa)
    else:
        body = _guide(agent_type, fa)
    meta: dict[str, Any] = {"mode": "assistant", "assistant": agent_type, "starters": starters(agent_type, fa)}
    if payload and agent_type not in ("STEEL_DESIGN_AGENT", "CAD_AGENT"):
        meta["source_kind"] = payload.get("kind")
    return body, meta


def latest_payload_from_messages(messages) -> dict[str, Any] | None:
    for m in reversed(list(messages)):
        md = m.metadata or {}
        eng = md.get("engineering_results")
        if isinstance(eng, dict) and eng.get("kind") == "frame3d_analysis":
            return eng
    return None
