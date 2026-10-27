"""Persian (fa) localization of the system-generated chat blocks (cards, headings, step names, statuses).

The chat shows two kinds of text: what the language model writes (it follows the user's language) and what the
platform itself generates (status line, request/result/recommendation/warning headings, workflow steps, progress
steps, action buttons, error cards, prerequisite checklists). The second kind used to be English-only. Everything
here is *language-gated*: English conversations get exactly the strings they always had.

Design
- ``detect_lang`` / ``is_persian``: the language of the user's message (any Arabic-script letter => Persian).
- ``H`` / ``STATUS`` ...: small per-language tables for template pieces.
- ``tr``: exact-phrase + pattern translation for dynamic-but-templated labels (step names, action labels, tool
  details, recommendations of the engines). Unknown text is returned unchanged (never guessed).
- ``localize_metadata``: applies ``tr`` to the user-visible strings in the assistant-message metadata
  (status events, action labels, agent-run steps / tools / errors) so the UI cards are Persian too.
- numbers, units, paths and codes (kN, m, /workspace/model, Mabhas 9, ...) are never altered; the frontend isolates
  them as LTR runs inside RTL text.
"""
from __future__ import annotations

import re
from typing import Any

_ARABIC_SCRIPT = re.compile("[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]")


def is_persian(text: str | None) -> bool:
    # the Arabic semicolon (U+061B) is inserted by the follow-up merger between messages; it is not language evidence
    return bool(_ARABIC_SCRIPT.search((text or "").replace("\u061b", " ")))


def detect_lang(text: str | None) -> str | None:
    """"fa" when the text contains Persian/Arabic letters, "en" for other non-empty text, None when empty."""
    if not (text or "").strip():
        return None
    return "fa" if is_persian(text) else "en"


_LATIN_WORD = re.compile(r"[A-Za-z]{3,}")


def conversation_lang(message: str | None, prior_user_texts: list[str] | None = None) -> str | None:
    """Language the system cards of this turn must use.

    Persian when the message has Persian letters. A message with no words at all in either script (``2``, ``OK``,
    ``/workspace/model``, a bare number/unit) continues the language of the newest earlier user message instead of
    flipping a Persian conversation to English. Otherwise English.
    """
    if is_persian(message):
        return "fa"
    words_only = re.sub(r"\S*/\S*", " ", message or "")  # paths like /workspace/model are not words
    if (message or "").strip() and not _LATIN_WORD.search(words_only):
        for earlier in prior_user_texts or []:  # newest first
            if not (earlier or "").strip():
                continue
            if is_persian(earlier):
                return "fa"
            if _LATIN_WORD.search(re.sub(r"\S*/\S*", " ", earlier)):
                return "en"
            # earlier turn was also just a number/path (or is the current message itself, already stored): keep looking
    return detect_lang(message)


# ---- template pieces ------------------------------------------------------------------------------------------
HEADINGS: dict[str, dict[str, str]] = {
    "status": {"en": "Status", "fa": "وضعیت"},
    "request": {"en": "Request", "fa": "درخواست"},
    "result": {"en": "Result", "fa": "نتیجه"},
    "recommendations": {"en": "Recommendations", "fa": "توصیه‌ها"},
    "warnings": {"en": "Warnings", "fa": "هشدارها"},
    "demo_title": {"en": "Structural analysis (Demo)", "fa": "تحلیل سازه (نمایشی)"},
    "demo_body": {
        "en": "Deterministic simply-supported beam results are available.",
        "fa": "نتایج قطعیِ تیر ساده در دسترس است.",
    },
}


def heading(key: str, lang: str | None) -> str:
    return HEADINGS[key]["fa" if lang == "fa" else "en"]


STATUS_LABELS_FA: dict[str, str] = {
    "queued": "در صف",
    "in_progress": "در حال پردازش",
    "awaiting_approval": "نیازمند تأیید مهندس",
    "blocked": "متوقف — ورودی بیشتری لازم است",
    "completed": "تکمیل شد",
    "failed": "ناموفق",
    "rejected": "رد شد",
    "cancelled": "لغو شد",
}

_AGENT_FA: dict[str, str] = {
    "STRUCTURAL_MODELING_AGENT": "دستیار مدل‌سازی سازه",
    "LOAD_ASSESSMENT_AGENT": "دستیار ارزیابی بارها",
    "ANALYSIS_AGENT": "دستیار تحلیل",
    "CONCRETE_DESIGN_AGENT": "دستیار طراحی بتن",
    "STEEL_DESIGN_AGENT": "دستیار طراحی فولاد",
    "OPTIMIZATION_AGENT": "دستیار بهینه‌سازی",
    "SEISMIC_AGENT": "دستیار لرزه‌ای",
    "VALIDATION_AGENT": "دستیار اعتبارسنجی",
    "CAD_AGENT": "دستیار نقشه‌کشی (CAD)",
    "REPORTING_AGENT": "دستیار گزارش‌دهی",
    "DOCUMENT_INTERPRETATION_AGENT": "دستیار تفسیر اسناد",
    "PROMPT_GENERATION_AGENT": "دستیار تولید درخواست",
    "STRUCTURAL_ENGINEERING_AGENT": "دستیار مهندسی سازه",
}


def _title_case_en(agent_value: str) -> str:
    return agent_value.replace("_", " ").title()


# English "Analysis Agent" / "Structural Modeling Agent" -> Persian agent names
_AGENT_EN_TO_FA = {_title_case_en(k): v for k, v in _AGENT_FA.items()}

# ---- exact phrases (progress steps, tool cards, actions, errors, engine recommendations) -------------------------
FA_EXACT: dict[str, str] = {
    # progress steps / status events
    "Understanding request": "درک درخواست",
    "Loading project context": "بارگذاری زمینه‌ی پروژه",
    "Reading documents": "خواندن اسناد",
    "Reading attached files": "خواندن فایل‌های پیوست",
    "Running structural analysis": "اجرای تحلیل سازه",
    "Running concrete design": "اجرای طراحی بتن",
    "Running steel design": "اجرای طراحی فولاد",
    "Generating CAD deliverables": "تولید خروجی‌های نقشه (CAD)",
    "Reading engineering documents": "خواندن اسناد مهندسی",
    "Preparing engineering report": "تهیه‌ی گزارش مهندسی",
    "Checking code compliance": "بررسی انطباق با آیین‌نامه",
    "Running optimization": "اجرای بهینه‌سازی",
    "Inspecting structural model": "بررسی مدل سازه",
    "Reviewing project loads": "بازبینی بارهای پروژه",
    "Evaluating seismic parameters": "ارزیابی پارامترهای لرزه‌ای",
    "Running engineering workflow": "اجرای گردش‌کار مهندسی",
    "Validating results": "اعتبارسنجی نتایج",
    "Waiting for approval": "در انتظار تأیید",
    "Final response": "پاسخ نهایی",
    "Building engineering context": "ساخت زمینه‌ی مهندسی",
    "Awaiting human approval": "در انتظار تأیید انسانی",
    "Workflow failed": "گردش‌کار ناموفق بود",
    "Additional input required": "ورودی بیشتری لازم است",
    # errors
    "Engineering workflow failed": "گردش‌کار مهندسی ناموفق بود",
    "Request was rejected": "درخواست رد شد",
    "Request was cancelled": "درخواست لغو شد",
    "Additional input is required": "ورودی بیشتری لازم است",
    "Tool execution failed": "اجرای ابزار ناموفق بود",
    "Capability execution failed": "اجرای قابلیت ناموفق بود",
    "The agent could not complete this engineering step.": "دستیار نتوانست این مرحله‌ی مهندسی را کامل کند.",
    # final-result lines
    "Awaiting engineer approval before results are finalized.": "پیش از نهایی شدن نتایج، منتظر تأیید مهندس است.",
    "Execution is blocked until required inputs are provided.": "اجرا تا ارائه‌ی ورودی‌های لازم متوقف است.",
    "Execution failed.": "اجرا ناموفق بود.",
    "Completed successfully.": "با موفقیت تکمیل شد.",
    # tool titles / details
    "Structural Analysis": "تحلیل سازه",
    "Concrete Design": "طراحی بتن",
    "Steel Design": "طراحی فولاد",
    "CAD Generation": "تولید نقشه (CAD)",
    "Document Analysis": "تحلیل اسناد",
    "Report Generation": "تولید گزارش",
    "Result Validation": "اعتبارسنجی نتایج",
    "Optimization": "بهینه‌سازی",
    "Model Inspection": "بررسی مدل",
    "Load Assessment": "ارزیابی بارها",
    "Seismic Review": "بررسی لرزه‌ای",
    "Engineering capability": "قابلیت مهندسی",
    "Indexed": "نمایه‌سازی شد",
    "Content extracted": "محتوا استخراج شد",
    "Model loaded": "مدل بارگذاری شد",
    "Engineering results available": "نتایج مهندسی در دسترس است",
    "Engineering report generated": "گزارش مهندسی تولید شد",
    "Deterministic beam analysis completed": "تحلیل قطعیِ تیر انجام شد",
    "3D frame analysis completed": "تحلیل قاب سه‌بعدی انجام شد",
    "3D frame analysis waiting for inputs": "تحلیل قاب سه‌بعدی منتظر ورودی است",
    "ACI 318 RC beam check waiting for required inputs": "کنترل تیر بتنی ACI 318 منتظر ورودی‌های لازم است",
    "ACI 318 RC beam check rejected invalid inputs": "کنترل تیر بتنی ACI 318 ورودی نامعتبر را رد کرد",
    "ACI 318 RC beam check unsupported for the configured code": "کنترل تیر بتنی ACI 318 برای آیین‌نامه‌ی تنظیم‌شده پشتیبانی نمی‌شود",
    "ACI 318 RC beam design check failed": "کنترل طراحی تیر بتنی ACI 318 رد شد",
    "ACI 318 RC beam flexure and shear check completed": "کنترل خمش و برش تیر بتنی ACI 318 انجام شد",
    "ACI 318 RC beam check": "کنترل تیر بتنی ACI 318",
    # actions
    "Review approval": "بازبینی تأیید",
    "View Assistants": "مشاهده‌ی دستیارها",
    "View Results": "مشاهده‌ی نتایج",
    "View Reports": "مشاهده‌ی گزارش‌ها",
    "View Memory": "مشاهده‌ی حافظه",
    "View Traceability": "مشاهده‌ی ردیابی",
    "View context": "مشاهده‌ی زمینه",
    "View analysis": "مشاهده‌ی تحلیل",
    "View design": "مشاهده‌ی طراحی",
    "View CAD": "مشاهده‌ی نقشه (CAD)",
    "View report": "مشاهده‌ی گزارش",
    "View validation": "مشاهده‌ی اعتبارسنجی",
    "Current conversation": "گفتگوی فعلی",
    "Project context": "زمینه‌ی پروژه",
    # engine recommendations / warnings (static strings of the handlers)
    "Reply 'assume defaults' to auto-complete the missing steps.":
        "برای تکمیل خودکار مراحل ناقص بنویسید «پیش‌فرض‌ها را فرض کن».",
    "Compare drift and member forces with an ETABS model of the same frame before relying on them.":
        "پیش از اتکا به نتایج، تغییرمکان نسبی طبقات و نیروهای اعضا را با مدل ETABS همین قاب مقایسه کنید.",
    "Next phases: Standard 2800 seismic loads and Mabhas 9 member design.":
        "مراحل بعدی: بارهای لرزه‌ای استاندارد ۲۸۰۰ و طراحی اعضا طبق مبحث ۹.",
    "Re-run the full analysis (with modal check) on the optimal sections before issuing drawings.":
        "پیش از صدور نقشه‌ها، تحلیل کامل (همراه با کنترل مودال) را روی مقاطع بهینه دوباره اجرا کنید.",
    "Treat this as a demonstration of chat-to-calculation flow, not a construction document.":
        "این را نمایشی از جریان «گفتگو تا محاسبه» بدانید، نه مدرک اجرایی.",
    "Next: attach a drawing or specification, then request validation against the project code profile.":
        "گام بعد: یک نقشه یا مشخصات فنی پیوست کنید و اعتبارسنجی با آیین‌نامه‌های پروژه را بخواهید.",
    "Proceed with geometry updates aligned to project requirements.":
        "به‌روزرسانی هندسه را مطابق الزامات پروژه ادامه دهید.",
    "Run the structural engineering workflow on the current project": "اجرای گردش‌کار مهندسی سازه روی پروژه‌ی فعلی",
    "Generate architectural and structural building layout from a brief":
        "تولید چیدمان معماری و سازه‌ای ساختمان از روی شرح پروژه",
    "Set up or revise the structural engineering model": "تنظیم یا بازنگری مدل مهندسی سازه",
    "Evaluate seismic design parameters and lateral system assumptions":
        "ارزیابی پارامترهای طراحی لرزه‌ای و فرض‌های سیستم جانبی",
    "Review and organize project loading assumptions": "بررسی و سازمان‌دهی فرض‌های بارگذاری پروژه",
    "Run or review structural analysis workflows": "اجرا یا بررسی گردش‌کارهای تحلیل سازه",
    "Support concrete member and slab design checks": "پشتیبانی از کنترل طراحی اعضای بتنی و دال",
    "Support steel member sizing and connection review": "پشتیبانی از انتخاب مقطع اعضای فولادی و بررسی اتصالات",
    "Validate configuration, assumptions, and code compliance": "اعتبارسنجی پیکربندی، فرض‌ها و انطباق با آیین‌نامه",
    "Prepare or coordinate engineering drawings and CAD deliverables": "تهیه یا هماهنگی نقشه‌های مهندسی و خروجی‌های CAD",
    "Prepare engineering summaries and deliverable reports": "تهیه خلاصه‌های مهندسی و گزارش‌های تحویلی",
    "Interpret uploaded documents and specifications": "تفسیر اسناد و مشخصات بارگذاری‌شده",
    "Plan and run structural optimization workflows": "برنامه‌ریزی و اجرای گردش‌کارهای بهینه‌سازی سازه",
    "Review missing inputs before applying model changes.":
        "پیش از اعمال تغییرات مدل، ورودی‌های ناقص را بررسی کنید.",
    "Use the Model workspace Generate building action once the pipeline is wired.":
        "پس از آماده شدن خط پردازش، از دکمه‌ی «تولید ساختمان» در صفحه‌ی مدل استفاده کنید.",
    "Review generated geometry, analysis and design in the Model workspace.":
        "هندسه، تحلیل و طراحی تولیدشده را در صفحه‌ی مدل بررسی کنید.",
    "Approve or reject the pending model-change request before treating the model as issued.":
        "پیش از آنکه مدل را صادرشده بدانید، درخواست تغییر مدل را تأیید یا رد کنید.",
    "Confirm occupancy assumptions and environmental loads with the project team.":
        "فرض‌های کاربری و بارهای محیطی را با تیم پروژه تأیید کنید.",
    "Internal 2D gravity analysis completed. Review member forces before design.":
        "تحلیل ثقلی دوبعدیِ داخلی انجام شد. پیش از طراحی، نیروهای اعضا را بررسی کنید.",
    "This is not a 3D ETABS/SAP2000 substitute and does not include wind/seismic.":
        "این جایگزین مدل سه‌بعدی ETABS/SAP2000 نیست و بار باد و زلزله را شامل نمی‌شود.",
    "Connect deterministic design routines before treating results as code-compliant conclusions.":
        "پیش از آنکه نتایج را منطبق با آیین‌نامه بدانید، روال‌های قطعیِ طراحی را متصل کنید.",
    "Connect deterministic optimization routines before treating results as optimized engineering conclusions.":
        "پیش از آنکه نتایج را بهینه‌ی مهندسی بدانید، روال‌های قطعیِ بهینه‌سازی را متصل کنید.",
    "Confirm site class, importance factor, and lateral system before final seismic decisions.":
        "پیش از تصمیم نهایی لرزه‌ای، رده‌ی ساختگاه، ضریب اهمیت و سیستم باربر جانبی را تأیید کنید.",
    "Use DXF drawings when AutoCAD is not installed locally.":
        "اگر AutoCAD نصب نیست، از نقشه‌های DXF استفاده کنید.",
    "Review missing_data entries before issuing the report externally.":
        "پیش از ارسال گزارش به بیرون، موارد ناقص (missing_data) را بررسی کنید.",
    "Upload and process source documents before relying on extracted requirements.":
        "پیش از اتکا به الزامات استخراج‌شده، اسناد مبنا را بارگذاری و پردازش کنید.",
    "Wind and seismic intensities are PRELIMINARY_NOT_CODE placeholders.":
        "شدت باد و زلزله مقادیر موقتِ PRELIMINARY_NOT_CODE هستند، نه مقادیر آیین‌نامه‌ای.",
    "Modeling workflow prepared using current project context.":
        "گردش‌کار مدل‌سازی با زمینه‌ی فعلی پروژه آماده شد.",
    "Building design pipeline is not configured.": "خط پردازش طراحی ساختمان پیکربندی نشده است.",
    "Seismic review scoped to configured standards and project assumptions.":
        "بررسی لرزه‌ای در چارچوب استانداردهای تنظیم‌شده و فرض‌های پروژه انجام شد.",
    "Report generation service is not configured.": "سرویس تولید گزارش پیکربندی نشده است.",
    "Engineering report generated from persisted platform data.": "گزارش مهندسی از داده‌های ذخیره‌شده‌ی پلتفرم تولید شد.",
    "Document interpretation scoped to uploaded project files.": "تفسیر اسناد فقط روی فایل‌های بارگذاری‌شده‌ی پروژه انجام شد.",
}

_VALIDATION_FA = {
    "Not Run": "اجرا نشده",
    "Pass": "قبول",
    "Warning": "هشدار",
    "Error": "خطا",
    "Requires Engineer Review": "نیازمند بازبینی مهندس",
    "Validated": "اعتبارسنجی شد",
    "Invalid": "نامعتبر",
    "Incomplete": "ناقص",
    "Partially Validated": "تا حدی اعتبارسنجی شد",
    "Requires Local Software": "نیازمند نرم‌افزار محلی",
}

_PATTERNS: list[tuple[re.Pattern[str], Any]] = [
    (re.compile(r"^Open (.+ Agent)$"), lambda m: "باز کردن " + _AGENT_EN_TO_FA.get(m.group(1), m.group(1))),
    (re.compile(r"^Rejected: (.+)$", re.S), lambda m: f"رد شد: {m.group(1)}"),
    (re.compile(r"^Completed with status (.+)\.$"), lambda m: f"با وضعیت {m.group(1)} تکمیل شد."),
    (re.compile(r"^Project: (.+)$"), lambda m: f"پروژه: {m.group(1)}"),
    (re.compile(r"^(\d+) indexed documents?$"), lambda m: f"{m.group(1)} سند نمایه‌شده"),
    (re.compile(r"^(\d+) pages?$"), lambda m: f"{m.group(1)} صفحه"),
    (re.compile(r"^(\d+) relevant sections? found$"), lambda m: f"{m.group(1)} بخش مرتبط پیدا شد"),
    (re.compile(r"^(\d+) members? in model$"), lambda m: f"{m.group(1)} عضو در مدل"),
    (re.compile(r"^(\d+) load combinations? found$"), lambda m: f"{m.group(1)} ترکیب بار پیدا شد"),
    (re.compile(r"^(\d+) artifacts? produced$"), lambda m: f"{m.group(1)} خروجی تولید شد"),
    (re.compile(r"^Flexure (PASS|FAIL)$"), lambda m: "خمش: " + ("قبول" if m.group(1) == "PASS" else "مردود")),
    (re.compile(r"^Shear (PASS|FAIL)$"), lambda m: "برش: " + ("قبول" if m.group(1) == "PASS" else "مردود")),
    (re.compile(r"^Validation: (.+)$"), lambda m: f"اعتبارسنجی: {_VALIDATION_FA.get(m.group(1), m.group(1))}"),
    (re.compile(r"^Authorized tools: (.+)$"), lambda m: f"ابزارهای مجاز: {m.group(1)}"),
    (re.compile(r"^Capability: (.+)$"), lambda m: f"قابلیت: {m.group(1)}"),
]


def tr(text: Any, lang: str | None) -> Any:
    """Persian text for a known template string; anything unknown (or any non-fa lang) is returned unchanged."""
    if lang != "fa" or not isinstance(text, str) or not text:
        return text
    hit = FA_EXACT.get(text)
    if hit is not None:
        return hit
    if text in _AGENT_EN_TO_FA:
        return _AGENT_EN_TO_FA[text]
    for pattern, fn in _PATTERNS:
        m = pattern.match(text)
        if m:
            return fn(m)
    return text


def status_label(progress: str, fallback: str, lang: str | None) -> str:
    if lang == "fa":
        return STATUS_LABELS_FA.get(progress, fallback)
    return fallback


# ---- metadata -------------------------------------------------------------------------------------------------
def _tr_item(item: Any, keys: tuple[str, ...], lang: str) -> Any:
    if isinstance(item, dict):
        return {k: (tr(v, lang) if k in keys else v) for k, v in item.items()}
    return item


def localize_agent_run(agent_run: dict[str, Any] | None, lang: str | None) -> dict[str, Any] | None:
    """Translate the user-visible strings of an agent_run view (steps, tools, error, capability)."""
    if lang != "fa" or not isinstance(agent_run, dict):
        return agent_run
    out = dict(agent_run)
    out["steps"] = [_tr_item(s, ("label",), "fa") for s in agent_run.get("steps") or []]
    out["selected_capability"] = tr(agent_run.get("selected_capability"), "fa")
    tools = []
    for tool in agent_run.get("tools") or []:
        if not isinstance(tool, dict):
            tools.append(tool)
            continue
        t = dict(tool)
        t["name"] = tr(t.get("name"), "fa")
        t["details"] = [_tr_item(d, ("label",), "fa") for d in t.get("details") or []]
        t["actions"] = [_tr_item(a, ("label",), "fa") for a in t.get("actions") or []]
        if isinstance(t.get("error"), dict):
            t["error"] = _tr_item(t["error"], ("title", "reason"), "fa")
        tools.append(t)
    out["tools"] = tools
    if isinstance(agent_run.get("error"), dict):
        out["error"] = _tr_item(agent_run["error"], ("title", "reason"), "fa")
    ctx = agent_run.get("context")
    if isinstance(ctx, dict):
        out["context"] = {**ctx, "capability": tr(ctx.get("capability"), "fa")}
    return out


def localize_metadata(metadata: dict[str, Any], lang: str | None) -> dict[str, Any]:
    """Persian status events / action labels / agent-run strings; the ``lang`` is recorded for the UI."""
    metadata = dict(metadata)
    if lang in ("fa", "en"):
        metadata["lang"] = lang
    if lang != "fa":
        return metadata
    metadata["status_events"] = [tr(e, "fa") for e in metadata.get("status_events") or []]
    metadata["actions"] = [_tr_item(a, ("label",), "fa") for a in metadata.get("actions") or []]
    metadata["selected_capability"] = tr(metadata.get("selected_capability"), "fa")
    metadata["agent_run"] = localize_agent_run(metadata.get("agent_run"), "fa")
    return metadata
