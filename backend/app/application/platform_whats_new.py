"""Maintained "what's new" source for the in-app assistant.

Add one entry whenever a user-visible feature ships so the assistant can announce it. Newest first. ``refs`` name
feature ids that exist in ``platform_knowledge`` (capability ids, example ids, page hrefs, plan ids, export names or
login option ids); a pytest fails when a ref is unknown or an entry is missing from the generated knowledge.
The assistant only announces what is listed here: do NOT list work that is not merged and live.
"""
from __future__ import annotations

# (month, id, English, Persian, refs)
WHATS_NEW: list[tuple[str, str, str, str, tuple[str, ...]]] = [
    ("2026-10", "pdelta-and-spectrum",
     "The 3D frame analysis now includes P-Δ (second-order) analysis, applied automatically for Standard 2800 projects when the stability index is above 0.1 "
     "(or on request), and a completed response-spectrum analysis with CQC combination and 5% accidental torsion.",
     "تحلیل قاب سه‌بعدی اکنون تحلیل P-Δ (مرتبه دوم) را دارد؛ در پروژه‌های استاندارد ۲۸۰۰ وقتی شاخص پایداری بیش از ۰٫۱ باشد (یا به درخواست) خودکار اعمال می‌شود، "
     "و تحلیل طیفی کامل با ترکیب CQC و خروج از مرکزیت اتفاقی ۵٪ دارد.",
     ("p_delta", "response_spectrum_completion")),
    ("2026-10", "assistant-knows-platform",
     "The assistant now knows the whole platform (pages, plans, payment, exports, limits), explains how-to questions instead of running them, "
     "and can diagnose errors you paste and offer to file a platform issue.",
     "دستیار اکنون کل پلتفرم را می‌شناسد (صفحه‌ها، پلن‌ها، پرداخت، خروجی‌ها، محدودیت‌ها)، پرسش‌های «چطور» را توضیح می‌دهد و اجرا نمی‌کند، "
     "و خطاهای شما را بررسی و در صورت تمایل گزارش مشکل ثبت می‌کند.",
     ("report_problem", "APPROVAL_409")),
    ("2026-10", "chat-optimization-checklist",
     "Optimization in chat shows a step-by-step checklist when inputs are missing, and Iranian projects default to SI units.",
     "بهینه‌سازی در چت وقتی ورودی‌ها ناقص است چک‌لیست مرحله‌به‌مرحله نشان می‌دهد و پروژه‌های ایرانی به‌طور پیش‌فرض واحد SI دارند.",
     ("optimization", "/workspace/optimization")),
    ("2026-10", "crypto-billing",
     "Plans can be upgraded with crypto payment (USDT and other assets) from the Upgrades page; quarterly and yearly durations are discounted.",
     "ارتقای پلن با پرداخت رمزارزی (USDT و ارزهای دیگر) از صفحه «ارتقا» ممکن است؛ مدت سه‌ماهه و سالانه تخفیف دارد.",
     ("/workspace/upgrades", "pro")),
    ("2026-10", "google-signin",
     "Sign-in with Google (shown on the login page when enabled) sits next to email and password; \"Remember me\" keeps you signed in.",
     "ورود با گوگل (در صورت فعال بودن، در صفحه ورود) در کنار ایمیل و رمز عبور است؛ «مرا به خاطر بسپار» شما را وارد نگه می‌دارد.",
     ("login_google", "login_remember")),
]
