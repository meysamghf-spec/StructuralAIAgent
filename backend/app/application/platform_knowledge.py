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
from app.application import frame3d_limits as fl
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
    ("/workspace/detailing", "Detailing", "دیتیلینگ", "rebar detailing sheets (beams, columns, schedule) with DXF/PDF downloads",
     "نقشه‌های جزئیات آرماتور (تیر، ستون، جدول) با دانلود DXF/PDF"),
    ("/workspace/foundation", "Foundation", "فونداسیون", "footing design from the frame's column reactions, with foundation and drawing downloads",
     "طراحی پی از واکنش ستون‌های قاب، همراه با دانلود فونداسیون و نقشه‌ها"),
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


# --------------------------------------------------------------------------------------------- identity / matrix / examples
SLOGAN_EN = "Chat with your structural AI"
SLOGAN_FA = "با هوش مصنوعی سازه‌ات گفتگو کن"

# Capability matrix: (id, English, Persian, status). Status: yes | in_progress | partial | no | unconfirmed.
# Owner-maintained: update here when a capability changes status (the test checks every id reaches the prompt).
CAPABILITY_MATRIX: list[tuple[str, str, str, str]] = [
    ("modal_analysis", "Modal (eigenvalue) analysis", "تحلیل مودال", "yes"),
    ("spectrum_2800", "Standard 2800 design response spectrum", "طیف طراحی استاندارد ۲۸۰۰", "yes"),
    ("equivalent_static", "Equivalent static seismic analysis (Standard 2800)", "تحلیل استاتیکی معادل زلزله (استاندارد ۲۸۰۰)", "yes"),
    ("p_delta", "P-Δ (second-order) effects", "اثر P-Δ (مرتبه دوم)", "yes"),
    ("response_spectrum_completion", "Completion of response-spectrum analysis (full combination and reporting)",
     "تکمیل تحلیل طیفی (ترکیب کامل و گزارش)", "yes"),
    ("time_history", "Time-history analysis", "تحلیل تاریخچه زمانی", "no"),
    ("pushover", "Pushover analysis", "تحلیل پوش‌اور", "no"),
    ("nonlinear", "Nonlinear analysis", "تحلیل غیرخطی", "no"),
    ("pile_foundation", "Deep / pile foundation design (only isolated footings are designed today)",
     "طراحی پی عمیق / شمع (فعلاً فقط پی منفرد طراحی می‌شود)", "no"),
    ("steel_connection_design", "Steel connection design (bolted / welded / moment connections)",
     "طراحی اتصالات فولادی (پیچی / جوشی / گیردار)", "no"),
    ("retaining_wall", "Retaining wall design", "طراحی دیوار حائل", "no"),
    ("mabhas9_concrete", "Concrete design to Iranian Mabhas 9", "طراحی بتن طبق مبحث ۹ ایران", "yes"),
    ("mabhas10_steel", "Steel design to Iranian Mabhas 10", "طراحی فولاد طبق مبحث ۱۰ ایران", "in_progress"),
    ("us_codes", "US codes (ACI concrete beam check, AISC steel beam check)", "آیین‌نامه‌های آمریکا (کنترل تیر بتنی ACI و تیر فولادی AISC)", "partial"),
    ("export_e2k", "ETABS .e2k model file", "فایل مدل ETABS (e2k)", "unconfirmed"),
    ("export_f2k", "SAFE .f2k model file", "فایل مدل SAFE (f2k)", "unconfirmed"),
    ("export_s2k", "SAP2000 .s2k model file", "فایل مدل SAP2000 (s2k)", "unconfirmed"),
    ("export_dxf", "DXF drawings", "نقشه‌های DXF", "unconfirmed"),
]
_STATUS_EN = {"yes": "YES (available)", "in_progress": "IN PROGRESS (not available yet)", "partial": "PARTIAL",
              "no": "NO (not supported)", "unconfirmed": "EXISTS, NOT YET CONFIRMED in the real program"}
_STATUS_FA = {"yes": "بله (موجود است)", "in_progress": "در حال توسعه (هنوز در دسترس نیست)", "partial": "نسبی",
              "no": "خیر (پشتیبانی نمی‌شود)", "unconfirmed": "خروجی ساخته می‌شود ولی هنوز در نرم‌افزار واقعی تأیید نشده"}

# Chat examples for every capability: (id, English title, Persian title, English example, Persian example)
EXAMPLES: list[tuple[str, str, str, str, str]] = [
    ("define_beam", "Beam analysis", "تحلیل تیر", "simply supported beam 6 m, uniform load 20 kN/m",
     "تیر ساده با دهانه ۶ متر و بار گسترده ۲۰ کیلونیوتن بر متر"),
    ("define_rc_beam", "RC beam design (Mabhas 9)", "طراحی تیر بتنی (مبحث ۹)", "design a reinforced concrete beam 30x50, 6 m, 25 kN/m",
     "تیر بتن مسلح ۳۰×۵۰ با دهانه ۶ متر و بار ۲۵ را طراحی کن"),
    ("define_frame", "Create and analyse a 3D frame", "ساخت و تحلیل قاب سه‌بعدی", "3D frame 4 stories, 3x3 bays, 5 m by 5 m, storey height 3.2 m",
     "قاب سه‌بعدی ۴ طبقه، ۳×۳ دهانه ۵ متری، ارتفاع طبقه ۳.۲ متر"),
    ("assume_defaults", "Let the platform fill missing inputs", "پر کردن ورودی‌های ناقص توسط پلتفرم", "assume defaults", "پیش‌فرض‌ها را فرض کن"),
    ("edit_inputs", "Change inputs of the current model (re-runs the analysis with the new values)",
     "تغییر ورودی‌های مدل فعلی (تحلیل با مقادیر جدید دوباره اجرا می‌شود)", "set storeys to 6 / bay x = 6 m / columns 50x50 / dead load 7",
     "«تعداد طبقه را ۶ کن» / «دهانه x را ۶ متر کن» / «ستون‌ها ۵۰×۵۰» / «بار مرده ۷»"),
    ("run_task", "Run any engineering task by describing it", "اجرای هر کار مهندسی با توصیف آن", "analyse the frame / design the members / check the beam",
     "قاب را تحلیل کن / اعضا را طراحی کن / تیر را کنترل کن"),
    ("optimization", "Frame optimization (paid plans)", "بهینه‌سازی قاب (پلن‌های پولی)", "optimize the frame for cost", "قاب را برای هزینه بهینه کن"),
    ("download_outputs", "Download every output", "دانلود همه خروجی‌ها", "download all outputs", "همه خروجی‌ها را دانلود کن"),
    ("export_models", "Export a model for ETABS / SAFE / SAP2000 or DXF drawings", "خروجی مدل برای ETABS / SAFE / SAP2000 یا نقشه DXF",
     "export ETABS / export SAFE / export SAP2000 / export DXF", "«خروجی ETABS را بده» / SAFE / SAP2000 / DXF"),
    ("drawings", "Structural drawing set", "مجموعه نقشه‌های سازه", "give me the structural drawing set", "نقشه‌های اجرایی را بده"),
    ("projects_cmd", "Projects", "پروژه‌ها", "list my projects / open project <name>", "«پروژه‌هایم را نشان بده» / «پروژه <نام> را باز کن»"),
    ("approvals_cmd", "Approvals", "تأییدها", "show pending approvals / approve / reject", "«تأییدهای در انتظار را نشان بده» / «تأیید کن» / «رد کن»"),
    ("assistant_switch", "Switch to a specialised assistant", "رفتن به یک دستیار تخصصی", "switch to the optimization assistant",
     "«دستیار بهینه‌سازی را انتخاب کن»"),
    ("attach_files", "Attach files (paperclip in the composer)", "پیوست فایل (گیره در کادر پیام)", "attach a PDF/DXF/photo and say what you want",
     "یک PDF/DXF/عکس پیوست کنید و بگویید چه می‌خواهید"),
    ("report_problem", "Report a problem / see its status", "گزارش مشکل / پیگیری آن", "report a problem: <what happened> / issue status",
     "«گزارش مشکل: <شرح>» / «وضعیت گزارش‌ها»"),
]

# Login / account options: (id, English, Persian)
LOGIN_OPTIONS: list[tuple[str, str, str]] = [
    ("login_password", "Email and password (create an account at /register, sign in at /login).",
     "ایمیل و رمز عبور (ساخت حساب در /register، ورود در /login)."),
    ("login_google", "Sign in with Google (button on the login page when the operator has enabled it; only your verified email and name are used).",
     "ورود با گوگل (دکمه در صفحه ورود، وقتی فعال باشد؛ فقط ایمیل تأییدشده و نام شما استفاده می‌شود)."),
    ("login_remember", "\"Remember me\" (ticked by default) keeps you signed in on this browser; untick it on shared computers.",
     "«مرا به خاطر بسپار» (به‌طور پیش‌فرض فعال) شما را در این مرورگر وارد نگه می‌دارد؛ در رایانه مشترک آن را بردارید."),
]
PUBLIC_PAGES: list[tuple[str, str, str]] = [
    ("/about", "About SAIA (public landing page)", "درباره سایا (صفحه معرفی عمومی)"),
    ("/login", "Sign in", "ورود"), ("/register", "Create account", "ساخت حساب"),
    ("/privacy", "Privacy policy", "سیاست حریم خصوصی"), ("/terms", "Terms of service", "شرایط استفاده"),
]
# Related products. TrafficLens is a separate sibling product (same assistant framework); stated by the owner, not part of SAIA's code.
RELATED_PRODUCTS: list[tuple[str, str, str, str]] = [
    ("trafficlens", "/traffic/", "TrafficLens: a separate product for traffic engineering at /traffic/. Its assistant is separate; "
     "SAIA's assistant knows only SAIA details, so for TrafficLens questions point the user there.",
     "TrafficLens: محصول جداگانه برای مهندسی ترافیک در /traffic/. دستیار آن جداست؛ دستیار سایا فقط سایا را می‌شناسد و برای پرسش‌های TrafficLens کاربر را به آنجا هدایت می‌کند."),
]

# "Diagnose errors": (id, trigger regex, cause EN, cause FA, what to do EN, what to do FA). Built from the platform's real error codes.
DIAGNOSE: list[tuple[str, str, str, str, str, str]] = [
    ("QUOTA_EXCEEDED", r"quota_exceeded|\b402\b|quota|plan limit|limit reached|سهمیه|به سقف|محدودیت پلن",
     "Your plan's limit was reached (HTTP 402): projects, analyses per month, frame size or a locked feature.",
     "به سقف پلن شما رسیده‌اید (کد ۴۰۲): تعداد پروژه، تحلیل ماهانه، اندازه قاب یا قابلیت قفل.",
     "Open Upgrades (/workspace/upgrades) to see usage and upgrade, or reduce the model size.",
     "صفحه «ارتقا» (/workspace/upgrades) را باز کنید تا مصرف را ببینید و ارتقا دهید، یا اندازه مدل را کم کنید."),
    ("RATE_LIMITED", r"rate_limited|\b429\b|too many (sign-?in|attempts|requests)|تلاش‌?های? (زیاد|ناموفق)|ورود.*بیش از حد",
     "Too many failed sign-in attempts from this address (HTTP 429); a temporary lock protects accounts.",
     "تلاش‌های ناموفق ورود از این آدرس زیاد بوده (کد ۴۲۹)؛ قفل موقت برای حفاظت از حساب‌هاست.",
     "Wait a few minutes and try again with the correct password.", "چند دقیقه صبر کنید و با رمز درست دوباره تلاش کنید."),
    ("REQUIRES_ANALYSIS", r"requires_analysis|run analysis|نیاز به تحلیل|ابتدا تحلیل",
     "Design/optimization needs a completed analysis of the current model first.",
     "طراحی/بهینه‌سازی ابتدا به تحلیل کامل مدل فعلی نیاز دارد.",
     "Run the analysis first (describe the model in chat, or the Analysis page), then retry.",
     "ابتدا تحلیل را اجرا کنید (مدل را در چت توصیف کنید یا صفحه «تحلیل»)، سپس دوباره تلاش کنید."),
    ("MISSING_REQUIRED_INPUT", r"missing_required_input|missing input|ورودی.*(ناقص|کم)|اطلاعات.*ناقص",
     "A required input is missing (for example span, loads, storeys or bays).",
     "یک ورودی لازم کم است (مثلاً دهانه، بار، تعداد طبقه یا دهانه‌ها).",
     "Give the missing values, or type \"assume defaults\" / «پیش‌فرض‌ها را فرض کن».",
     "مقادیر کم را بدهید یا بنویسید «پیش‌فرض‌ها را فرض کن»."),
    ("UNSUPPORTED_CODE", r"unsupported_code|unsupported|پشتیبانی نمی|پشتیبانی‌?نمی",
     "The requested code/check has no engine yet (see the capability matrix; US codes are partial).",
     "برای آیین‌نامه/کنترل درخواستی هنوز موتوری نیست (ماتریس قابلیت‌ها را ببینید؛ آیین‌نامه‌های آمریکا نسبی‌اند).",
     "Use a supported code (Iranian codes are the default) or ask what is supported.",
     "از آیین‌نامه پشتیبانی‌شده استفاده کنید (پیش‌فرض: ایران) یا بپرسید چه چیزی پشتیبانی می‌شود."),
    ("APPROVAL_409", r"\b409\b|conflict|already (approved|rejected|decided)|قبلا.*(تایید|رد)",
     "The approval item already has a decision (HTTP 409), often from a double click or a second tab.",
     "برای این مورد قبلاً تصمیم ثبت شده (کد ۴۰۹)، معمولاً به‌خاطر دوبار کلیک یا تب دیگر.",
     "Refresh Approvals (/workspace/approvals) and read the item's current status.",
     "صفحه «تأییدها» (/workspace/approvals) را تازه کنید و وضعیت فعلی مورد را بخوانید."),
    ("AUTH_401_403", r"\b401\b|\b403\b|unauthori[sz]ed|forbidden|session expired|نشست.*منقضی|دسترسی.*(ندارید|مجاز)",
     "Your session expired (401) or you do not have access to that project/page (403; some pages are admin-only).",
     "نشست شما منقضی شده (۴۰۱) یا به آن پروژه/صفحه دسترسی ندارید (۴۰۳؛ برخی صفحه‌ها فقط مدیر).",
     "Sign in again; ask the project owner for access if it is someone else's project.",
     "دوباره وارد شوید؛ اگر پروژه دیگری است از مالک آن دسترسی بخواهید."),
    ("EXPORT_LOCKED", r"export.*(locked|not available|plan)|خروجی.*(بسته|قفل|پلن)|e2k|f2k|s2k|dxf",
     "ETABS/SAFE/SAP2000/DXF exports are locked on plans whose exports list does not include them.",
     "خروجی ETABS/SAFE/SAP2000/DXF در پلن‌هایی که در فهرست خروجی‌شان نیست قفل است.",
     "Check your plan (Current session) and Upgrades; tables, figures and the PDF report are always open.",
     "پلن خود را بررسی کنید و از «ارتقا» استفاده کنید؛ جدول‌ها، تصاویر و گزارش PDF همیشه باز است."),
    ("PAYMENT_PENDING", r"payment|paid|invoice|پرداخت|فاکتور|تراکنش|not (detected|activated)|فعال نشد",
     "A crypto payment is only matched when the exact invoice amount arrives on the chosen network; invoices last 30 minutes (late payments are matched up to 24 hours) and need confirmations.",
     "پرداخت رمزارزی فقط وقتی تطبیق می‌خورد که مبلغ دقیق فاکتور در شبکه انتخاب‌شده برسد؛ فاکتور ۳۰ دقیقه اعتبار دارد (پرداخت دیرهنگام تا ۲۴ ساعت تطبیق می‌خورد) و تأیید شبکه لازم است.",
     "Use the recheck button on the Upgrades page; if the amount or network was wrong or time passed, file a platform issue with the invoice time and amount.",
     "دکمه بازبینی در صفحه «ارتقا» را بزنید؛ اگر مبلغ/شبکه اشتباه بود یا زمان گذشته، با زمان و مبلغ فاکتور گزارش مشکل ثبت کنید."),
    ("SLOW_TIMEOUT", r"timeout|timed out|slow|stuck|hang|کند|گیر کرد|تایم ?اوت|بالا نمی",
     "Optimization has a ~35 s time budget in chat, and free-form AI replies may be slow when the language service is busy.",
     "بهینه‌سازی در چت حدود ۳۵ ثانیه زمان دارد و پاسخ‌های آزاد هوش مصنوعی وقتی سرویس زبانی شلوغ است کند می‌شود.",
     "Retry once; large frames are better optimized from the Optimization page.", "یک بار دوباره تلاش کنید؛ برای قاب‌های بزرگ از صفحه «بهینه‌سازی» استفاده کنید."),
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
                f"قاب تا {_lim(L['frame_max_storeys'] or fl.MAX_STOREYS, fa)} طبقه و {_lim(L['frame_max_bays'] or fl.MAX_BAYS, fa)} دهانه، "
                f"خروجی نرم‌افزار/DXF: {'، '.join(ex) if ex else 'ندارد'}، بهینه‌سازی: {_lim(L['optimization'], fa)}، "
                f"ورود نقشه AutoCAD در ماه {_lim(L['autocad_imports_per_month'], fa)}، کاربر {_lim(L['seats'], fa)}، "
                f"فضا {_lim(L['storage_mb'], fa)} مگابایت")
        else:
            lines.append(
                f"- {name} [{p['id']}] {price}: projects {_lim(L['projects'], fa)}, analyses/month {_lim(L['analyses_per_month'], fa)}, "
                f"frame up to {_lim(L['frame_max_storeys'] or fl.MAX_STOREYS, fa)} storeys x {_lim(L['frame_max_bays'] or fl.MAX_BAYS, fa)} bays, "
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
            f"صفحه «حافظه» برای جست‌وجو و مرور است.\n"
            f"صفحه‌ها: /workspace/validation ، /workspace/approvals ، /workspace/memory.")
    pages_line = "Pages: /workspace/validation, /workspace/approvals, /workspace/memory."
    return (
        f"Validation: a report on project health (engineering model, code configuration, unit configuration, project name and structural-model "
        f"consistency); the overall status is one of {vs}, each finding has a severity and a fix; exports CSV/JSON/Markdown. It is a report, not a design guarantee.\n"
        f"Approval: a human sign-off queue for high-impact actions: creating/activating/publishing/rolling back an assistant, approving a design assumption and "
        f"member override, changing code/unit configuration, updating the engineering model, and workflow steps of assistants that need approval. "
        f"Statuses: {ap}. Decide on the Approvals page or in chat (\"show pending approvals\", \"approve\", \"reject\"). "
        f"Not every action is gated, only those the approval policy lists.\n"
        f"Memory: the durable per-project record of decisions and knowledge with types: {mem}; project chat turns are stored as CONVERSATION; "
        f"the Memory page is for browsing and search.\n" + pages_line)


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


def section_identity(fa: bool) -> str:
    if fa:
        return (f"سایا (SAIA): «{SLOGAN_FA}». سایا یک پلتفرم مهندسی سازه گفتگومحور است: نیاز را در چت می‌گویید و موتورهای محاسباتی قطعی کار را انجام می‌دهند؛ "
                "تحلیل، طراحی، صحت‌سنجی مستقل، تأیید مهندس و حافظه پروژه. هوش مصنوعی فقط توضیح می‌دهد و مسیر می‌دهد، محاسبه نمی‌کند.")
    return (f"SAIA: \"{SLOGAN_EN}\". SAIA is a chat-first structural engineering platform: you say what you need in chat and deterministic engines do "
            "the work: analysis, design, independent validation, engineer approval and project memory. The AI only explains and routes; it does not calculate.")


def section_matrix(fa: bool) -> str:
    st = _STATUS_FA if fa else _STATUS_EN
    rows = [f"- [{i}] {f if fa else e}: {st[k]}" for i, e, f, k in CAPABILITY_MATRIX]
    head = "ماتریس صادقانه قابلیت‌ها (مرجع؛ چیزی را بیشتر از این ادعا نکنید):" if fa else "Honest capability matrix (authoritative; never claim more than this):"
    tail = ("«در حال توسعه» یعنی هنوز در دسترس نیست؛ فقط وقتی در «تازه‌ها» اعلام شده باشد منتشر شده است." if fa else
            "\"In progress\" means not available yet; it is released only once it appears in What's new.")
    return head + "\n" + "\n".join(rows) + "\n" + tail


def section_examples(fa: bool) -> str:
    rows = [f"- [{i}] {f if fa else e}: «{ef if fa else ee}»" for i, e, f, ee, ef in EXAMPLES]
    return ("دستورهای نمونه در چت (برای هر قابلیت):\n" if fa else "Example chat commands (one per capability):\n") + "\n".join(rows)


def section_login(fa: bool) -> str:
    rows = [f"- [{i}] {f if fa else e}" for i, e, f in LOGIN_OPTIONS]
    pub = [f"- {h}: {f if fa else e}" for h, e, f in PUBLIC_PAGES]
    rel = [f"- [{i}] {f if fa else e}" for i, _h, e, f in RELATED_PRODUCTS]
    return (("ورود و حساب:\n" if fa else "Sign-in and account:\n") + "\n".join(rows)
            + ("\nصفحه‌های عمومی (بدون ورود):\n" if fa else "\nPublic pages (no sign-in):\n") + "\n".join(pub)
            + ("\nمحصولات مرتبط:\n" if fa else "\nRelated products:\n") + "\n".join(rel))


def section_whats_new(fa: bool, limit: int = 6) -> str:
    from app.application.platform_whats_new import WHATS_NEW

    rows = [f"- {m} [{i}]: {f if fa else e}" for m, i, e, f, _r in WHATS_NEW[:limit]]
    return ("تازه‌ها (فقط همین‌ها را به‌عنوان قابلیت جدید اعلام کنید):\n" if fa else
            "What's new (announce only these as new):\n") + "\n".join(rows)


def section_diagnose(fa: bool) -> str:
    rows = [f"- [{i}] {f if fa else e} {('اقدام' if fa else 'Do')}: {df if fa else de}" for i, _rx, e, f, de, df in DIAGNOSE]
    if fa:
        head = ("عیب‌یابی خطا (صادقانه): وقتی کاربر خطایی گزارش می‌کند، با کمک این فهرست و متن خطا محتمل‌ترین علت و راه‌حل را همین‌جا توضیح بده. "
                "قطعی ادعا نکن؛ بگو «احتمالاً». خطاهای واقعی پلتفرم را سامانه خودش خودکار گزارش می‌کند و خودش جملهٔ «این خطا خودکار گزارش شد» را "
                "در پایان پاسخ اضافه می‌کند؛ از کاربر نخواه گزارش کند و خودت نگو که گزارش شد. محدودیت‌های عادی پلن گزارش نمی‌شوند. "
                "دستیار نمی‌تواند کد را تغییر دهد، سایت را اصلاح یا سرور را راه‌اندازی کند و نباید چنین ادعایی بکند؛ "
                "مدیر پلتفرم گزارش را بررسی می‌کند و هر اصلاح فقط پس از تأیید مدیر اعمال می‌شود.")
    else:
        head = ("Error diagnosis (honest): when the user reports an error, use this list and the error text to explain the most likely cause and the fix right here. "
                "Do not be certain; say \"probably\". The platform itself files real errors automatically and appends the line \"This error was reported "
                "automatically\" to your reply; do not ask the user to report it and do not say it was reported yourself. Normal plan limits are not filed. "
                "The assistant CANNOT change code, fix the site or touch servers and must never claim it can; a platform admin reviews filed issues "
                "and any fix is applied only after admin approval.")
    return head + "\n" + "\n".join(rows)


# Expected behaviour of the plan system: explained, but not filed as a platform bug unless the user says it is unexpected.
EXPECTED_LIMIT_CODES = frozenset({"QUOTA_EXCEEDED", "RATE_LIMITED", "EXPORT_LOCKED", "PAYMENT_PENDING"})
_UNEXPECTED_CUE = re.compile(
    r"even though|although|but i (?:have|already|paid|am)|i (?:already )?paid|already upgraded|not used|never used|should (?:work|be allowed)|"
    r"با اینکه|با وجود|پرداخت کرده|پرداخت کردم|ارتقا دادم|ارتقا داده|استفاده نکرده|نباید", re.I)
_OCCURRED = re.compile(
    r"\bi (?:get|got|see|saw|keep|am getting|have)\b|\b(?:gives?|shows?|says?|returns?|throws?|appears?|happened|happens|keeps?)\b|"
    r"not working|doesn'?t work|isn'?t working|broken|crash|failed|می ?دهد|می ?گیرم|گرفتم|می ?بینم|نشان می|میده|میگیرم|داد\b|رخ داد|کار نمی|نمیشه|نمی ?شود|خراب", re.I)
_SERVER_ERR = re.compile(r"\b5\d\d\b|internal server|server error|traceback|exception|crash|خطای سرور|سرور", re.I)


def diagnose_decision(message: str):
    """Should this error report be auto-filed? Real platform/engine errors yes; expected plan limits and pure
    "what does X mean" questions no."""
    from app.platform_helper.intents import is_explain_question
    from app.platform_helper.service import DiagnoseDecision

    t = _norm(message)
    rows = diagnose_matches(message)
    codes = tuple(r[0] for r in rows)
    severity = "high" if _SERVER_ERR.search(t) or codes == ("SLOW_TIMEOUT",) and re.search(r"stuck|گیر|hang", t) else "medium"
    category = "performance" if codes == ("SLOW_TIMEOUT",) else "bug"
    if is_explain_question(message) and not _OCCURRED.search(t):
        return DiagnoseDecision(codes, False, "explain_only", severity, category)
    if codes and all(c in EXPECTED_LIMIT_CODES for c in codes) and not _UNEXPECTED_CUE.search(t):
        return DiagnoseDecision(codes, False, "expected_limit", severity, category)
    return DiagnoseDecision(codes, True, "error", severity, category)


def diagnose_matches(message: str) -> list[tuple[str, str, str, str, str, str]]:
    t = _norm(message)
    return [row for row in DIAGNOSE if re.search(row[1], t, re.I)]


_CORE = ("identity", "matrix", "limits", "whats_new")
_SECTION_FN = {"identity": section_identity, "matrix": section_matrix, "limits": section_limits, "whats_new": section_whats_new,
               "examples": section_examples, "pages": section_pages, "engines": section_engines, "plans": section_plans,
               "payment": section_payment, "exports": section_exports, "optimization": section_optimization, "vam": section_vam,
               "assistants": section_assistants, "login": section_login, "diagnose": section_diagnose}
_TOPIC_SECTIONS: dict[str, tuple[str, ...]] = {
    "limits": (), "capabilities": (), "billing": ("plans", "payment"), "optimization": ("optimization", "examples"),
    "validation": ("vam",), "approval": ("vam",), "memory": ("vam",), "assistants": ("assistants",),
    "outputs": ("exports", "examples"), "overview": ("pages", "engines", "examples"), "diagnose": ("diagnose",),
    "login": ("login",), "whatsnew": (), "commands": ("examples",), "pages": ("pages",),
}


def selected_sections(message: str | None) -> list[str]:
    """Section names for a question: the compact core + only the sections the question is about."""
    if message is None:
        return list(_SECTION_FN)
    names = list(_CORE)
    topics = match_topics(message) or ["overview"]
    for t in topics:
        for n in _TOPIC_SECTIONS.get(t, ()):
            if n not in names:
                names.append(n)
    return names


def build_platform_knowledge(fa: bool = True, message: str | None = None) -> str:
    """The generated block for the system prompt. ``message=None`` -> everything; else only the sections the question needs."""
    secs = [_SECTION_FN[n](fa) for n in selected_sections(message)]
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
                f"(used {used.get('analyses', 0)}), frame max {_lim(L['frame_max_storeys'] or fl.MAX_STOREYS, False)} storeys x "
                f"{_lim(L['frame_max_bays'] or fl.MAX_BAYS, False)} bays, exports {', '.join(ex) if ex else 'none'}, "
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
    ("diagnose", r"خطا|ارور|باگ|کار نمی ?کن|نمی ?شود|نمیشه|مشکل|\berror\b|\bbug\b|failed|not working|doesn'?t work|broken|crash|\b(?:40[0-9]|42[0-9]|50[0-9])\b|"
                 r"timeout|exception|traceback"),
    ("capabilities", r"time ?history|pushover|nonlinear|non-linear|p-?delta|p-?Δ|second.order|response spectrum|spectrum|\bmodal\b|eigen|equivalent static|"
                     r"mabhas|مبحث|aisc|\baci\b|\bcode\b|آیین ?نامه|طیف|مودال|غیرخطی|پوش ?اور|تاریخچه ?زمانی|استاتیکی معادل|مرتبه دوم|ایتبس واقعی|"
                     r"real (?:etabs|program)|تایید نشده|پشتیبانی|support"),
    ("login", r"log ?in|sign ?in|sign ?up|register|google|گوگل|remember me|به خاطر بسپار|رمز ?عبور|password|ورود(?![یا-ی])|ثبت ?نام|حساب کاربری|account"),
    ("whatsnew", r"what'?s new|new features?|changelog|release notes|تازه|جدید|آپدیت|به ?روز ?رسانی"),
    ("commands", r"دستور|command|example|مثال|چطور بنویسم|what (?:do|should) i (?:type|say)|تغییر ورود|change (?:the )?inputs?|edit (?:the )?model"),
    ("pages", r"صفحه|\bpages?\b|\bmenu\b|منو|کجاست|where (?:is|can i)|about page|privacy|terms|حریم خصوصی|شرایط"),
    ("overview", r"چه کار|چه کارهایی|what can you|what do you|امکانات|قابلیت|صفحات|pages|features|راهنما|\bhelp\b|کمک|چیکار"),
]
_TOPIC_RX = {k: re.compile(v) for k, v in _TOPICS}
_DIAG_WORDS = _TOPICS[[k for k, _ in _TOPICS].index("diagnose")][1]
_OFFER_FA = {"outputs": "اگر می‌خواهید همین الان اجرا شود، بنویسید: «خروجی ETABS را بده» یا «همه خروجی‌ها را دانلود کن».",
             "optimization": "برای اجرا همین‌جا بنویسید: «{ex}».",
             "approval": "برای دیدن صف: «تأییدهای در انتظار را نشان بده».",
             "billing": "برای ارتقا به صفحه «ارتقا» بروید: /workspace/upgrades.",
             "validation": "برای دیدن گزارش پروژه به صفحه «صحت‌سنجی» بروید: /workspace/validation.",
             }
_OFFER_EN = {"outputs": "To run it now, type: \"export ETABS\" or \"download all outputs\".",
             "optimization": "To run it here, type: \"{ex}\".",
             "approval": "To see the queue: \"show pending approvals\".",
             "billing": "To upgrade, open the Upgrades page: /workspace/upgrades.",
             "validation": "To see your project's report, open the Validation page: /workspace/validation.",
             }


def match_topics(message: str) -> list[str]:
    t = _norm(message)
    scores = {k: len(set(rx.findall(t))) for k, rx in _TOPIC_RX.items()}
    best = max(scores.values())
    if best == 0:
        return []
    if scores.get("diagnose"):  # an error report is diagnosed first, whatever else it mentions
        return ["diagnose"]
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
        parts = [section_limits(fa), section_matrix(fa)]
    elif topic == "capabilities":
        parts = [section_matrix(fa)]
    elif topic == "login":
        parts = [section_login(fa)]
    elif topic == "whatsnew":
        parts = [section_whats_new(fa)]
    elif topic == "commands":
        parts = [section_examples(fa)]
    elif topic == "pages":
        parts = [section_pages(fa)]
    elif topic == "diagnose":
        rows = diagnose_matches(message)
        if rows:
            parts = [("محتمل‌ترین علت:" if fa else "Most likely cause:") + "\n" + "\n".join(
                f"- {f if fa else e}\n  {('اقدام' if fa else 'Do')}: {df if fa else de}" for _i, _rx, e, f, de, df in rows[:3])]
        else:
            parts = [("از این پیام نمی‌توانم علت را قطعی تشخیص دهم؛ علت‌های رایج:" if fa else
                      "I cannot pin the cause from this message; common causes:") + "\n" + "\n".join(
                f"- {f if fa else e}" for _i, _rx, e, f, _de, _df in DIAGNOSE)]
        parts.append("من نمی‌توانم کد یا سایت را تغییر دهم یا اصلاح کنم؛ فقط می‌توانم علت را توضیح دهم. خطاهای واقعی پلتفرم خودکار برای مدیر پلتفرم گزارش می‌شوند."
                     if fa else "I cannot change code or fix the site; I can only explain the cause. Real platform errors are reported to the platform admin automatically.")
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
