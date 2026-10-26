"""Platform knowledge for the in-app assistant, GENERATED from the real sources (not hand-written prose).

Sources of truth used here:
  * billing plans / durations / limits  -> ``billing/plans.json`` (via ``billing.plans``)
  * crypto assets, invoice expiry       -> ``billing/crypto.py``
  * export kinds + plan gates           -> ``chat_actions._SPECIFIC`` / ``_FA_LABEL`` / ``_export_allowed``
  * assistants / capability catalog     -> ``platform_assistants`` + ``agent_capability_catalog``
  * Validation / Approval / Memory      -> ``ValidationStatus`` / ``ApprovalStatus`` / ``MemoryType`` enums
  * pages                               -> ``PAGES`` below (mirrors ``frontend/lib/nav.ts``; a pytest parses nav.ts and
                                           fails if a page is missing here)

Three consumers:
  * ``build_platform_knowledge(fa)``  - markdown block injected into the LLM system prompt
  * ``user_context(...)``             - per-user live facts (plan, usage, project, model)
  * ``answer_faq(message, ...)``      - static answer used when the LLM is unreachable (and for "what can't it do")

The model itself NEVER produces engineering numbers: this is stated in both the prompt block and the FAQ.
"""
from __future__ import annotations

import re
from typing import Any

from app.application import chat_actions as ca
from app.application.billing import crypto, plans as billing_plans

# (href, English name, Persian name, English description, Persian description) - mirrors frontend/lib/nav.ts NAV_ITEMS.
PAGES: list[tuple[str, str, str, str, str]] = [
    ("/", "Chat", "گفت‌وگو (صفحه اصلی)", "talk to the platform: engines, optimization, downloads run from chat",
     "گفت‌وگو با پلتفرم: موتورهای محاسباتی، بهینه‌سازی و دانلود خروجی از چت اجرا می‌شود"),
    ("/projects", "Projects", "پروژه‌ها", "create, open and select projects; everything is stored per project",
     "ساخت، باز کردن و انتخاب پروژه؛ همه‌چیز به‌ازای هر پروژه ذخیره می‌شود"),
    ("/projects/new", "New Project", "پروژه جدید", "create a new project", "ساخت پروژه جدید"),
    ("/workspace/model", "Model", "مدل", "structural model summary: members, sections, loads, combinations",
     "خلاصه مدل سازه: اعضا، مقاطع، بارها و ترکیب‌ها"),
    ("/workspace/analysis", "Analysis", "تحلیل", "run linear static analysis of the project's model",
     "اجرای تحلیل استاتیکی خطی مدل پروژه"),
    ("/workspace/results", "Results", "نتایج", "stored analysis and design results", "نتایج ذخیره‌شده تحلیل و طراحی"),
    ("/workspace/design", "Design", "طراحی", "member design checks with the selected code configuration (default: Iranian codes)",
     "کنترل طراحی اعضا با پیکربندی آیین‌نامه انتخاب‌شده (پیش‌فرض: آیین‌نامه‌های ایران)"),
    ("/workspace/cad", "CAD", "نقشه‌ها (CAD)", "drawings produced from results (DXF/PDF)", "نقشه‌های تولیدشده از نتایج (DXF/PDF)"),
    ("/workspace/reports", "Reports", "گزارش‌ها", "calculation reports and downloads", "گزارش محاسبات و دانلودها"),
    ("/workspace/validation", "Validation", "صحت‌سنجی", "checks code configuration and model consistency; CSV/JSON/Markdown report",
     "بررسی پیکربندی آیین‌نامه و سازگاری مدل؛ گزارش CSV/JSON/Markdown"),
    ("/workspace/files", "Files", "فایل‌ها", "uploaded files that can be attached to chat", "فایل‌های بارگذاری‌شده که می‌شود به چت پیوست کرد"),
    ("/workspace/memory", "Memory", "حافظه", "project memory: decisions, assumptions, conversation facts",
     "حافظه پروژه: تصمیم‌ها، فرض‌ها و دانسته‌های گفت‌وگو"),
    ("/workspace/agents", "Assistants", "دستیارها", "the specialised engineering assistants and their capabilities",
     "دستیارهای تخصصی مهندسی و قابلیت‌هایشان"),
    ("/workspace/agents/builder", "Assistant Builder", "سازنده دستیار", "create custom assistants (approval-gated)",
     "ساخت دستیار سفارشی (نیازمند تأیید)"),
    ("/workspace/approvals", "Approvals", "تأییدها", "human sign-off queue: approve or reject", "صف تأیید انسانی: تأیید یا رد"),
    ("/workspace/integrations", "Integrations", "یکپارچه‌سازی", "external tool connectors and their execution log",
     "اتصال به ابزارهای خارجی و گزارش اجرای آن‌ها"),
    ("/workspace/optimization", "Optimization", "بهینه‌سازی", "search lighter/cheaper section sets that still pass (paid plans)",
     "جست‌وجوی مقاطع سبک‌تر/ارزان‌تر که کنترل‌ها را می‌گذرانند (پلن‌های پولی)"),
    ("/workspace/learning", "Learning", "یادگیری", "engineering learning notes derived from reviewed runs",
     "یادداشت‌های آموزشی مهندسی برگرفته از اجراهای بازبینی‌شده"),
    ("/workspace/traceability", "Traceability", "ردیابی", "links between inputs, runs, revisions and approvals",
     "پیوند میان ورودی‌ها، اجراها، بازنگری‌ها و تأییدها"),
    ("/workspace/upgrades", "Upgrades", "ارتقا", "plans, usage and crypto payment", "پلن‌ها، مصرف و پرداخت رمزارزی"),
    ("/workspace/ai", "AI Assistant", "دستیار هوش مصنوعی", "AI provider status", "وضعیت ارائه‌دهندگان هوش مصنوعی"),
    ("/workspace/admin/platform-issues", "Platform Issues", "مشکلات پلتفرم", "administrators only: reported problems and fixes",
     "فقط مدیران: مشکلات گزارش‌شده و اصلاح‌ها"),
]

# Engines reachable from chat (what the platform really computes). (en, fa, example command en, example command fa)
ENGINES: list[tuple[str, str, str, str]] = [
    ("Beam analysis (simply supported, cantilever, two-span): reactions, Mmax, Vmax, deflection, diagrams",
     "تحلیل تیر (دو سر مفصل، کنسول، دو دهانه): عکس‌العمل، لنگر و برش بیشینه، خیز و نمودارها",
     "simply supported beam 6 m, 20 kN/m", "تیر ساده ۶ متری با بار گسترده ۲۰ کیلونیوتن بر متر"),
    ("Reinforced-concrete beam design check (Iranian Mabhas 9)", "کنترل طراحی تیر بتن‌آرمه (مبحث ۹)",
     "design an RC beam 30x50, 6 m, 25 kN/m", "تیر بتنی ۳۰×۵۰ با دهانه ۶ متر و بار ۲۵ را طراحی کن"),
    ("3D frame analysis (storeys x bays) with Iranian loads and seismic (Standard 2800)",
     "تحلیل قاب سه‌بعدی (طبقه × دهانه) با بارگذاری ایران و زلزله (استاندارد ۲۸۰۰)",
     "3-storey frame, 2x2 bays of 5 m, zone high, soil II", "قاب ۳ طبقه ۲×۲ دهانه ۵ متری، پهنه زیاد، خاک ۲"),
    ("Frame section optimization for cost or weight (paid plans)", "بهینه‌سازی مقاطع قاب برای هزینه یا وزن (پلن‌های پولی)",
     "optimize the frame", "قاب را بهینه کن"),
    ("Drawings: structural drawing set, plans, rebar and foundation details (DXF/PDF)",
     "نقشه‌ها: مجموعه نقشه‌های اجرایی، پلان، آرماتوربندی و فونداسیون (DXF/PDF)",
     "give me the structural drawing set", "نقشه‌های اجرایی را بده"),
]

CHAT_COMMANDS: list[tuple[str, str]] = [
    ("download the outputs / download all outputs", "«خروجی‌ها را دانلود کن» / «همه خروجی‌ها را دانلود کن»"),
    ("export ETABS / SAFE / SAP2000 / DXF", "«خروجی ETABS را بده» / SAFE / SAP2000 / DXF"),
    ("list my projects / open project <name>", "«پروژه‌هایم را نشان بده» / «پروژه <نام> را باز کن»"),
    ("show pending approvals / approve / reject", "«تأییدهای در انتظار را نشان بده» / «تأیید کن» / «رد کن»"),
]


def _fa_digits(v: Any) -> str:
    return str(v).translate(str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹"))


def _n(v: Any, fa: bool) -> str:
    return _fa_digits(v) if fa else str(v)


def _lim(v: Any, fa: bool) -> str:
    if v is None:
        return "نامحدود" if fa else "unlimited"
    if v is True:
        return "دارد" if fa else "yes"
    if v is False:
        return "ندارد" if fa else "no"
    return _n(v, fa)


# --------------------------------------------------------------------------------------------- exports
def export_kinds() -> list[dict[str, Any]]:
    """Every export kind the chat can deliver, with the plan ids that allow it (from ``chat_actions``)."""
    cfg = billing_plans.load_config()["plans"]
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for _pat, kind, name, fmt, label in ca._SPECIFIC:
        if name in seen:
            continue
        seen.add(name)
        item = {"kind": kind, "name": name}
        allowed = [p["id"] for p in cfg if ca._export_allowed(item, p["limits"].get("exports"))]
        out.append({"name": name, "kind": kind, "format": fmt, "label_en": label,
                    "label_fa": ca._FA_LABEL.get(name, label), "plans": allowed})
    return out


def _plan_names(ids: list[str], fa: bool) -> str:
    byid = {p["id"]: p for p in billing_plans.load_config()["plans"]}
    allp = list(byid)
    if set(ids) >= set(allp):
        return "همه پلن‌ها" if fa else "all plans"
    return ("، " if fa else ", ").join(byid[i]["name_fa" if fa else "name"] for i in ids)


def section_exports(fa: bool) -> str:
    rows = []
    for k in export_kinds():
        rows.append(f"- {k['label_fa'] if fa else k['label_en']} [{k['name']}]: {_plan_names(k['plans'], fa)}")
    if fa:
        head = "انواع خروجی (برای دریافت در چت بنویسید مثلاً «خروجی ETABS را بده» یا «همه خروجی‌ها را دانلود کن»):"
        tail = ("«همه خروجی‌ها» یک فایل ZIP از همه موارد مجاز پلن است؛ موارد خارج از پلن حذف و در پاسخ گفته می‌شود. "
                "در پلن رایگان مدل‌های ETABS/SAFE/SAP2000 و نقشه‌های DXF بسته است؛ جدول‌ها، تصاویر و گزارش PDF باز است. "
                "این‌ها فایل خروجی‌اند (e2k/f2k/s2k متنی)؛ اتصال زنده به نرم‌افزار دسکتاپ از چت وجود ندارد.")
    else:
        head = "Export kinds (in chat say e.g. \"export ETABS\" or \"download all outputs\"):"
        tail = ("\"All outputs\" builds a ZIP of everything the plan allows; items outside the plan are skipped and the reply says so. "
                "On the Free plan ETABS/SAFE/SAP2000 models and DXF drawings are locked; tables, images and the PDF report are open. "
                "These are exported files (text e2k/f2k/s2k); there is no live link to desktop software from chat.")
    return head + "\n" + "\n".join(rows) + "\n" + tail


# --------------------------------------------------------------------------------------------- billing
def plan_rows() -> list[dict[str, Any]]:
    return billing_plans.load_config()["plans"]


def section_plans(fa: bool) -> str:
    lines = []
    for p in plan_rows():
        L = p["limits"]
        ex = L.get("exports") or []
        name = p["name_fa"] if fa else p["name"]
        price = _n(p["price_usdt"], fa) + (" USDT/ماه" if fa else " USDT/month")
        if fa:
            lines.append(
                f"- {name} [{p['id']}] {price}: پروژه {_lim(L['projects'], fa)}، تحلیل در ماه {_lim(L['analyses_per_month'], fa)}، "
                f"قاب تا {_lim(L['frame_max_storeys'], fa)} طبقه و {_lim(L['frame_max_bays'], fa)} دهانه، "
                f"خروجی نرم‌افزار/DXF: {'، '.join(ex) if ex else 'ندارد'}، بهینه‌سازی: {_lim(L['optimization'], fa)}، "
                f"ورود نقشه AutoCAD در ماه {_lim(L['autocad_imports_per_month'], fa)}، کاربر {_lim(L['seats'], fa)}، "
                f"فضا {_lim(L['storage_mb'], fa)} مگابایت")
        else:
            lines.append(
                f"- {name} [{p['id']}] {price}: projects {_lim(L['projects'], fa)}, analyses/month {_lim(L['analyses_per_month'], fa)}, "
                f"frame up to {_lim(L['frame_max_storeys'], fa)} storeys x {_lim(L['frame_max_bays'], fa)} bays, "
                f"software/DXF exports: {', '.join(ex) if ex else 'none'}, optimization: {_lim(L['optimization'], fa)}, "
                f"AutoCAD imports/month {_lim(L['autocad_imports_per_month'], fa)}, seats {_lim(L['seats'], fa)}, "
                f"storage {_lim(L['storage_mb'], fa)} MB")
    durs = billing_plans.load_config()["durations"]
    d = "، ".join(f"{x['label_fa']}: {_n(x['discount_pct'], fa)}٪ تخفیف" for x in durs) if fa else \
        ", ".join(f"{x['label']}: {x['discount_pct']}% discount" for x in durs)
    return ("پلن‌ها و محدودیت‌ها (از تنظیمات واقعی صورت‌حساب):\n" if fa else "Plans and limits (from the real billing config):\n") \
        + "\n".join(lines) + ("\nمدت اشتراک: " if fa else "\nDurations: ") + d


def crypto_facts() -> dict[str, Any]:
    coins: dict[str, list[str]] = {}
    for a in crypto.ASSETS:
        coins.setdefault(a.coin, []).append(a.standard if a.standard != "native" else a.network)
    live = [a.id for a in crypto.ASSETS if crypto.is_live(a)]
    return {"coins": coins, "expiry_min": crypto.EXPIRY_MIN, "live_assets": live, "test_mode": not live}


def section_payment(fa: bool) -> str:
    f = crypto_facts()
    coins = "؛ ".join(f"{c} ({'، '.join(n)})" for c, n in f["coins"].items()) if fa else \
        "; ".join(f"{c} ({', '.join(n)})" for c, n in f["coins"].items())
    mode_fa = ("اکنون پرداخت در حالت آزمایشی است: فاکتور تستی ساخته می‌شود و دکمه «شبیه‌سازی پرداخت» دارد؛ پرداخت واقعی انجام نمی‌شود."
               if f["test_mode"] else "")
    mode_en = ("Payments are currently in TEST mode: invoices are mock and have a \"Simulate payment\" button; no real money moves."
               if f["test_mode"] else "")
    if fa:
        return (f"پرداخت (فقط رمزارز؛ کارت بانکی، PayPal و درگاه ریالی وجود ندارد). قیمت‌ها به USDT است و تومان فقط مرجع است. "
                f"مراحل: صفحه «ارتقا» (/workspace/upgrades) ← انتخاب پلن (حرفه‌ای/دفتر فنی/سازمانی) و مدت (ماهانه بدون تخفیف، سه‌ماهه ۱۰٪، سالانه ۲۵٪) "
                f"← انتخاب ارز و شبکه ← صدور فاکتور با آدرس/QR و مبلغ دقیق ← پرداخت ← تشخیص خودکار روی بلاک‌چین (دکمه بازبینی) ← فعال‌سازی پلن. "
                f"فاکتور {_n(f['expiry_min'], fa)} دقیقه اعتبار دارد (پرداخت دیرهنگام تا ۲۴ ساعت هنوز تطبیق داده می‌شود)؛ مبلغ باید دقیقاً همان مبلغ فاکتور باشد "
                f"و فقط از شبکه انتخاب‌شده ارسال شود (در ارزهای پایدار یک «برچسب» سنتی در مبلغ برای شناسایی پرداخت است). "
                f"BTC و LTC از طریق BTCPay (از جمله Lightning) پرداخت می‌شوند. تمدید همان پلن، مدت را به انتهای اشتراک اضافه می‌کند؛ "
                f"تمدید خودکار وجود ندارد. ارزها: {coins}. {mode_fa}").strip()
    return (f"Payment (crypto ONLY; no bank card, PayPal or local gateway). Prices are in USDT; toman is reference only. "
            f"Steps: Upgrades page (/workspace/upgrades) -> pick plan (Pro/Office/Enterprise) and duration (monthly 0%, 3 months 10%, yearly 25% off) "
            f"-> pick coin and network -> invoice with address/QR and the exact amount -> pay -> automatic on-chain detection (use the refresh button) "
            f"-> plan activates. The invoice is valid {f['expiry_min']} minutes (a late payment is still matched for up to 24 h); send exactly the invoiced "
            f"amount on the chosen network (for stablecoins a small unique \"cents tag\" in the amount identifies your payment). BTC and LTC go through BTCPay "
            f"(incl. Lightning). Renewing the same plan extends the end date; there is no auto-renew. Coins: {coins}. {mode_en}").strip()


# --------------------------------------------------------------------------------------------- assistants
def assistant_rows() -> list[dict[str, Any]]:
    from app.application import agent_capability_catalog as cat
    from app.application.platform_assistants import PLATFORM_ASSISTANTS

    gated = {p.agent_type: p.requires_human_approval for p in cat.list_agent_capability_profiles()}
    rows = []
    for agent_type, (name, description, caps) in PLATFORM_ASSISTANTS.items():
        rows.append({"key": str(getattr(agent_type, "value", agent_type)), "name": name, "description": description,
                     "capabilities": list(caps), "needs_approval": bool(gated.get(agent_type, False))})
    return rows


def section_assistants(fa: bool) -> str:
    rows = assistant_rows()
    body = "\n".join(f"- {r['name']}{' (needs human approval)' if r['needs_approval'] and not fa else ''}"
                     f"{' (نیازمند تأیید انسانی)' if r['needs_approval'] and fa else ''}: {r['description']} [{', '.join(r['capabilities'])}]" for r in rows)
    return (f"دستیارهای پلتفرم ({len(rows)}؛ صفحه «دستیارها»):\n" if fa else f"Platform assistants ({len(rows)}; Assistants page):\n") + body


# --------------------------------------------------------------------------------------------- validation / approval / memory
def _enum_values(enum_cls: Any) -> list[str]:
    return [m.value for m in enum_cls]


def section_vam(fa: bool) -> str:
    from app.domain.models.human_approval import ApprovalStatus
    from app.domain.models.project_memory import MemoryType
    from app.domain.models.validation import ValidationStatus

    vs = ", ".join(_enum_values(ValidationStatus))
    ap = ", ".join(_enum_values(ApprovalStatus))
    mem = ", ".join(_enum_values(MemoryType))
    if fa:
        return (
            f"صحت‌سنجی (Validation): گزارشی از صحت پروژه (مدل مهندسی، پیکربندی آیین‌نامه، پیکربندی واحدها، نام پروژه و سازگاری مدل سازه)؛ "
            f"وضعیت کلی یکی از {vs} است و موارد با شدت و راه‌حل فهرست می‌شوند؛ خروجی CSV/JSON/Markdown دارد. گزارش است، نه تضمین طراحی.\n"
            f"تأیید (Approval): صف تأیید انسانی برای اقدامات پراثر: ساخت/فعال‌سازی/انتشار/بازگردانی دستیار، تأیید فرض طراحی و "
            f"جایگزینی دستی عضو، تغییر پیکربندی آیین‌نامه/واحد، به‌روزرسانی مدل مهندسی، و مراحل کاری دستیارهای نیازمند تأیید. "
            f"وضعیت‌ها: {ap}. در صفحه «تأییدها» یا در چت («تأییدهای در انتظار را نشان بده»، «تأیید کن»، «رد کن») تصمیم می‌گیرید. "
            f"هر اقدامی خودکار تأیید ندارد؛ فقط مواردِ سیاست تأیید.\n"
            f"حافظه (Memory): پرونده ماندگار هر پروژه از تصمیم‌ها و دانسته‌ها با نوع‌های: {mem}؛ گفت‌وگوهای پروژه هم به‌عنوان CONVERSATION ثبت می‌شود؛ "
            f"صفحه «حافظه» برای جست‌وجو و مرور است.")
    return (
        f"Validation: a report on project health (engineering model, code configuration, unit configuration, project name and structural-model "
        f"consistency); the overall status is one of {vs}, each finding has a severity and a fix; exports CSV/JSON/Markdown. It is a report, not a design guarantee.\n"
        f"Approval: a human sign-off queue for high-impact actions: creating/activating/publishing/rolling back an assistant, approving a design assumption and "
        f"member override, changing code/unit configuration, updating the engineering model, and workflow steps of assistants that need approval. "
        f"Statuses: {ap}. Decide on the Approvals page or in chat (\"show pending approvals\", \"approve\", \"reject\"). "
        f"Not every action is gated, only those the approval policy lists.\n"
        f"Memory: the durable per-project record of decisions and knowledge with types: {mem}; project chat turns are stored as CONVERSATION; "
        f"the Memory page is for browsing and search.")


# --------------------------------------------------------------------------------------------- optimization / limits / pages
def section_optimization(fa: bool) -> str:
    from app.application import optimization_checklist as oc

    pro = next((p for p in plan_rows() if p["limits"].get("optimization") and p["limits"].get("optimization") is not None), None)
    first = pro["name_fa" if fa else "name"] if pro else ""
    if fa:
        return (f"بهینه‌سازی (از پلن {first} به بالا؛ رایگان ندارد): در چت یا صفحه «بهینه‌سازی». چت لازم دارد قاب را توصیف کنید، مثلاً: "
                f"«{oc.EXAMPLE_COMMAND_FA}». هدف (هزینه یا وزن) و قیمت بتن/میلگرد/قالب را هم می‌توانید بدهید. اگر اطلاعات ناقص بود، چک‌لیست "
                f"مرحله‌به‌مرحله می‌دهد و با «فرض‌های پیش‌فرض را بگیر» این فرض‌ها را می‌گذارد: " + "؛ ".join(oc.AUTO_ASSUMPTIONS_FA))
    return (f"Optimization (from the {first} plan up; not on Free): in chat or on the Optimization page. Chat needs the frame described, e.g. "
            f"`{oc.EXAMPLE_COMMAND_EN}`. You may also give the objective (cost or weight) and concrete/rebar/formwork prices. If inputs are missing it "
            f"returns a step-by-step checklist, and \"assume defaults\" applies: " + "; ".join(oc.AUTO_ASSUMPTIONS_EN))


def section_limits(fa: bool) -> str:
    if fa:
        return (
            "محدودیت‌های صادقانه:\n"
            "- هوش مصنوعی هرگز عدد مهندسی تولید نمی‌کند؛ لنگر، برش، خیز، مساحت آرماتور و نسبت‌ها فقط از موتورهای محاسباتی می‌آیند. "
            "اگر موتوری برای کاری نیست، می‌گوید پشتیبانی نمی‌شود، نه اینکه حدس بزند.\n"
            "- موتورهای چت: تیر ساده/کنسول/دو دهانه، تیر بتنی (مبحث ۹)، قاب سه‌بعدی (با سقف طبقه/دهانه هر پلن)، بهینه‌سازی قاب، نقشه‌ها. "
            "کاری که موتور مشخصی در این فهرست ندارد را نباید ادعا کرد؛ توضیح دستیارها توصیف حوزه کارشان است، نه تضمین محاسبه کامل. هر نتیجه باید توسط مهندس مسئول بازبینی شود.\n"
            "- خروجی‌ها کمک‌ابزارند و جایگزین بازبینی و مهر مهندس مسئول نیستند.\n"
            "- پرداخت فقط رمزارزی است؛ پشتیبانی کارت/ریالی ندارد؛ تمدید خودکار ندارد.\n"
            "- خروجی ETABS/SAFE/SAP2000 فایل است نه اتصال زنده؛ بیرون از پلن قفل است.\n"
            "- پاسخ‌های آزاد دستیار از یک سرویس زبانی رایگان می‌آید که ممکن است کند یا در دسترس نباشد؛ در این حالت پاسخ‌های ثابت راهنما داده می‌شود.")
    return (
        "Honest limits:\n"
        "- The AI NEVER produces engineering numbers; moments, shears, deflections, reinforcement areas and ratios come only from the calculation engines. "
        "If no engine covers a task it says it is not supported instead of guessing.\n"
        "- Chat engines: simply supported/cantilever/two-span beams, RC beam (Mabhas 9), 3D frame (storey/bay caps per plan), frame optimization, drawings. "
        "Never claim a calculation that has no engine in this list; assistant descriptions state their area of work, not a guarantee of a complete computation. Every result must be reviewed by the responsible engineer.\n"
        "- Outputs are aids, not a substitute for review and stamp by the responsible engineer.\n"
        "- Payment is crypto only; no card/local gateway; no auto-renew.\n"
        "- ETABS/SAFE/SAP2000 output is a file, not a live link; locked outside the plan.\n"
        "- Free-form assistant replies come from a free language service that can be slow or down; then fixed help answers are used.")


def section_pages(fa: bool) -> str:
    rows = [f"- {p[2] if fa else p[1]} ({p[0]}): {p[4] if fa else p[3]}" for p in PAGES]
    return ("صفحه‌ها:\n" if fa else "Pages:\n") + "\n".join(rows)


def section_engines(fa: bool) -> str:
    rows = [f"- {e[1] if fa else e[0]}. {'مثال' if fa else 'Example'}: «{e[3] if fa else e[2]}»" for e in ENGINES]
    cmds = [f"- {c[1] if fa else c[0]}" for c in CHAT_COMMANDS]
    return (("قابلیت‌های چت:\n" if fa else "Chat capabilities:\n") + "\n".join(rows)
            + ("\nدستورهای مستقیم چت:\n" if fa else "\nDirect chat commands:\n") + "\n".join(cmds))


def build_platform_knowledge(fa: bool = True) -> str:
    """The generated block for the system prompt. Bilingual labels; the model must answer in the user's language."""
    secs = [section_pages(fa), section_engines(fa), section_plans(fa), section_payment(fa), section_exports(fa),
            section_optimization(fa), section_vam(fa), section_assistants(fa), section_limits(fa)]
    head = "## Generated platform facts (authoritative; from the product's own code and config)\n"
    return head + "\n\n".join(secs)


# --------------------------------------------------------------------------------------------- per-user context
def user_context(account_id: str | None, *, project: str | None = None, has_model: bool | None = None) -> dict[str, str]:
    """Live facts about THIS user for the prompt. Never raises."""
    ctx: dict[str, str] = {}
    try:
        from app.application.billing import service as bs

        if account_id:
            plan = bs.current_plan(account_id)
            L = plan["limits"]
            ex = L.get("exports") or []
            used = bs.usage(account_id)
            ctx["plan_id"] = plan["id"]
            ctx["plan"] = f"{plan['name']} ({plan['name_fa']})"
            ctx["plan_limits"] = (
                f"projects {_lim(L['projects'], False)}, analyses/month {_lim(L['analyses_per_month'], False)} "
                f"(used {used.get('analyses', 0)}), frame max {_lim(L['frame_max_storeys'], False)} storeys x "
                f"{_lim(L['frame_max_bays'], False)} bays, exports {', '.join(ex) if ex else 'none'}, "
                f"optimization {_lim(L['optimization'], False)}")
            ctx["limits_enforced"] = "yes" if bs.enforcement_enabled() else "no (all features open)"
    except Exception:  # noqa: BLE001 - context is best effort
        pass
    ctx["project_selected"] = project if project else "none"
    if has_model is not None:
        ctx["model_exists"] = "yes" if has_model else "no"
    return ctx


# --------------------------------------------------------------------------------------------- FAQ (LLM-free answers)
def _norm(text: str) -> str:
    t = (text or "").lower().replace("\u200c", " ").replace("ي", "ی").replace("ك", "ک")
    return t.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))


_TOPICS: list[tuple[str, str]] = [
    ("limits", r"نمی ?تواند|نمیتواند|نمیتونه|نمی ?تونه|چه کارهایی را نمی|محدودیت|limitation|\blimits?\b|can'?t|cannot|not able|unsupported|"
               r"چه چیزی.{0,12}(?:نیست|نمی)"),
    ("billing", r"پرداخت|ارتقا|پلن|اشتراک|قیمت|تعرفه|billing|payment|\bpay\b|\bplans?\b|pricing|\bprice|upgrade|subscription|کریپتو|crypto|"
                r"usdt|btc|bitcoin|بیت ?کوین|تتر|رمز ?ارز|invoice|فاکتور|تخفیف|discount"),
    ("optimization", r"بهینه|optimi[sz]"),
    ("validation", r"اعتبار ?سنجی|صحت ?سنجی|validation|validate"),
    ("approval", r"تایید|تأیید|approval|approve|تاییدیه"),
    ("memory", r"حافظه|\bmemory\b"),
    ("assistants", r"دستیار|assistants?|agents?|ایجنت|عامل ها"),
    ("outputs", r"etabs|ایتبس|ای ?تبس|e2k|\bsafe\b|سیف|sap ?2000|ساپ|s2k|f2k|dxf|اتوکد|autocad|خروجی|export|اکسپورت|دانلود|download|\bzip\b|زیپ|"
               r"\bpdf\b|اکسل|excel|نقشه"),
    ("overview", r"چه کار|چه کارهایی|what can you|what do you|امکانات|قابلیت|صفحات|pages|features|راهنما|\bhelp\b|کمک|چیکار"),
]
_TOPIC_RX = {k: re.compile(v) for k, v in _TOPICS}
_OFFER_FA = {"outputs": "اگر می‌خواهید همین الان اجرا شود، بنویسید: «خروجی ETABS را بده» یا «همه خروجی‌ها را دانلود کن».",
             "optimization": "برای اجرا همین‌جا بنویسید: «{ex}».",
             "approval": "برای دیدن صف: «تأییدهای در انتظار را نشان بده».",
             "billing": "برای ارتقا به صفحه «ارتقا» بروید: /workspace/upgrades.",
             "validation": "برای دیدن گزارش پروژه به صفحه «صحت‌سنجی» بروید: /workspace/validation."}
_OFFER_EN = {"outputs": "To run it now, type: \"export ETABS\" or \"download all outputs\".",
             "optimization": "To run it here, type: \"{ex}\".",
             "approval": "To see the queue: \"show pending approvals\".",
             "billing": "To upgrade, open the Upgrades page: /workspace/upgrades.",
             "validation": "To see your project's report, open the Validation page: /workspace/validation."}


def match_topics(message: str) -> list[str]:
    t = _norm(message)
    scores = {k: len(set(rx.findall(t))) for k, rx in _TOPIC_RX.items()}
    best = max(scores.values())
    if best == 0:
        return []
    top = [k for k, _ in _TOPICS if scores[k] == best]
    if "overview" in top and len(top) > 1:
        top.remove("overview")
    return top[:3]


_SW = {"e2k": "ETABS", "f2k": "SAFE", "s2k": "SAP2000"}


def _highlight_export(message: str, fa: bool) -> str:
    t = message.lower()
    for pat, _k, name, _f, label in ca._SPECIFIC[:3]:
        if re.search(pat, t):
            plans_ok = [k for k in export_kinds() if k["name"] == name][0]["plans"]
            lab = ca._FA_LABEL.get(name, label) if fa else label
            if fa:
                return f"{lab}: در پلن‌های {_plan_names(plans_ok, True)} موجود است؛ در چت بنویسید «خروجی {name.upper()} را بده»."
            return f"{lab}: available on {_plan_names(plans_ok, False)}; in chat type \"export {_SW[name]}\"."
    return ""


def _gate_note(topic: str, ctx: dict[str, str] | None, fa: bool) -> str:
    if not ctx or not ctx.get("plan_id"):
        return ""
    pid = ctx["plan_id"]
    byid = {p["id"]: p for p in plan_rows()}
    name = byid[pid]["name_fa" if fa else "name"] if pid in byid else pid
    L = byid.get(pid, {}).get("limits", {})
    if topic == "outputs" and not L.get("exports"):
        return (f"پلن فعلی شما «{name}» است و مدل‌های ETABS/SAFE/SAP2000 و DXF در آن بسته است؛ جدول‌ها، تصاویر و گزارش PDF باز است."
                if fa else f"You are on the {name} plan: ETABS/SAFE/SAP2000 models and DXF are locked; tables, images and the PDF report are open.")
    if topic == "optimization" and not L.get("optimization"):
        return (f"پلن فعلی شما «{name}» است و بهینه‌سازی در آن بسته است."
                if fa else f"You are on the {name} plan, where optimization is locked.")
    return ""


def faq_topic_text(topic: str, fa: bool, message: str = "", ctx: dict[str, str] | None = None) -> str:
    from app.application import optimization_checklist as oc

    if topic == "outputs":
        body = section_exports(fa)
        hl = _highlight_export(message, fa)
        parts = [hl, body] if hl else [body]
    elif topic == "billing":
        parts = [section_payment(fa), section_plans(fa)]
    elif topic == "optimization":
        parts = [section_optimization(fa)]
    elif topic in ("validation", "approval", "memory"):
        key = {"validation": 0, "approval": 1, "memory": 2}[topic]
        parts = [section_vam(fa).split("\n")[key]]
    elif topic == "assistants":
        parts = [section_assistants(fa)]
    elif topic == "limits":
        parts = [section_limits(fa)]
    else:
        parts = [section_engines(fa), section_pages(fa)]
    gate = _gate_note(topic, ctx, fa)
    if gate:
        parts.insert(0, gate)
    offer = (_OFFER_FA if fa else _OFFER_EN).get(topic, "")
    if offer:
        parts.append(offer.format(ex=oc.EXAMPLE_COMMAND_FA if fa else oc.EXAMPLE_COMMAND_EN))
    return "\n\n".join(p for p in parts if p)


def answer_faq(message: str, fa: bool, ctx: dict[str, str] | None = None, *, allow_overview: bool = True) -> str | None:
    """Static answer generated from the knowledge. None when no topic matches and ``allow_overview`` is False."""
    topics = match_topics(message)
    if not topics:
        if not allow_overview:
            return None
        topics = ["overview"]
    if topics == ["overview"] and not allow_overview:
        return None
    intro = ("پاسخ راهنما (بدون هوش مصنوعی؛ از اطلاعات خود پلتفرم):" if fa else
             "Help answer (no AI used; generated from the platform's own facts):")
    return intro + "\n\n" + "\n\n".join(faq_topic_text(t, fa, message, ctx) for t in topics)
