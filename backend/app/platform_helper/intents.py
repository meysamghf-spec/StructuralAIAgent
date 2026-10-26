"""Deterministic intent routing (no LLM needed). The LLM only talks; engines compute.

Intents: ``engineering`` (leave to the platform engines), ``bug_report`` (explicit "report a problem: ..."), ``diagnose`` (an error the
user describes: explain + offer to file), ``report_it`` ("report it"), ``issue_status``, ``greeting``, ``platform_help``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789")


def normalize(text: str) -> str:
    t = (text or "").translate(_ARABIC_DIGITS).replace("ي", "ی").replace("ك", "ک").replace("\u200c", " ")
    return re.sub(r"\s+", " ", t).strip().lower()


def is_persian(text: str) -> bool:
    return any("\u0600" <= ch <= "\u06ff" for ch in (text or ""))


_BUG_PREFIX = re.compile(r"^\s*(?:گزارش\s*(?:مشکل|باگ|خطا)|report\s*(?:a\s*)?(?:problem|bug|issue)|bug\s*report|مشکل\s*پلتفرم)\s*[:：\-]?\s*(?P<rest>.*)$", re.I | re.S)
_BUG_WORDS = re.compile(
    r"(\bbug\b|doesn'?t work|not working|isn'?t working|broken|crash|stack ?trace|\berror\b|failed|can'?t (approve|submit|send|open|upload)|"
    r"باگ|کار نمی ?کند|کار نمیکنه|کار نمی ?کنه|خراب|ارور|خطا|نمی ?شود|نمیشه|نمی ?تونم|نمیتونم|مشکل داره|ایراد)", re.I)
_ERROR_CODES = re.compile(
    r"(quota_exceeded|rate_limited|requires_analysis|missing_required_input|unsupported_code|"
    r"(?:error|http|status|code|خطای?|کد)\s*[:#]?\s*(?:40[1-3]|409|429|5\d\d)\b|\b(?:40[1-3]|409|429|50[0-4])\s*(?:error|conflict|خطا)|"
    r"internal server error|bad gateway|service unavailable|gateway timeout|timed out|timeout|traceback|unhandled exception|"
    r"تایم ?اوت|خطای سرور)", re.I)
_NAMED_CODES = re.compile(r"(quota_exceeded|rate_limited|requires_analysis|missing_required_input|unsupported_code)", re.I)
_REPORT_IT = re.compile(r"^\s*(?:(?:yes|ok|okay|sure|please|بله|آره|اره|باشه|لطفا)[\s,،!.]*)*(?:report it|file it|file (?:an? )?(?:issue|report)|log it|"
                        r"گزارش(?:ش)?(?: را| رو)? (?:کن|کنید|ثبت کن|بده)|ثبت(?:ش)?(?: کن| کنید)|گزارش مشکل)\s*[.!؟?]*\s*$", re.I)
_STATUS = re.compile(r"(issue status|status of (my )?(issue|report)s?|my reports|وضعیت گزارش|گزارش(‌| )?های من|وضعیت مشکل)", re.I)
_GREETING = re.compile(r"^\s*(hi|hello|hey|salam|slm|سلام|درود|وقت بخیر|صبح بخیر|عصر بخیر|thanks|thank you|مرسی|ممنون|تشکر)[\s!.،,؟?]*$", re.I)
_HELP = re.compile(
    r"(what can you do|what you can do|what are you|who are you|what do you do|how (do|can) i|how does (the )?platform|what is (this )?(platform|structuralai|saia)|help me|\bhelp\b|where (is|can i find)|"
    r"which page|explain (the )?(platform|page|approval|optimization|validation)|"
    r"چه کاری|چکار می ?کنی|چه کارهایی|چطور|چگونه|کجا|کمک|راهنما|پلتفرم|این صفحه|تایید پروژه|تأیید پروژه|چیست|یعنی چه|معنی)", re.I)
_HOWTO = re.compile(r"^(?:(?:hi|hello|hey|سلام|درود)[\s,،!.]*)?(how (do|can|should) i|how does|where (is|can i)|why (does|is|can'?t)|چطور|چگونه|چرا|کجا|چه جوری)", re.I)
_ENGINEERING = re.compile(
    r"(\d\s*(m|kn|mpa|kn/m|متر|کیلو)|analy[sz]e|design (a|the)|optimi[sz]e|frame|beam|column|slab|footing|storey|story|stories|"
    r"تحلیل|طراحی|بهینه|قاب|تیر|ستون|دال|پی\b|طبقه|دهانه|بار گسترده|مقطع|آرماتور|سازه)", re.I)
_ENGINEERING_VERB = re.compile(r"(analy[sz]e|design|optimi[sz]e|run |calculate|check the|تحلیل کن|طراحی کن|بهینه کن|محاسبه کن|اجرا کن|بررسی کن)", re.I)


# "How do I / چطور / what is / چیست / explain": a request for an EXPLANATION, even when it mentions an action word such as
# export / download / دانلود / بده. Genuine commands ("download the outputs", «خروجی‌ها را دانلود کن») do not match.
_Q_STRONG = re.compile(
    r"(?:^|[\s,،!.:؛;(«\"'])(?:how (?:do|does|did|can|could|should|would|to|is|are|much|many)\b|how'?s\b|what (?:is|are|does|do|exactly)\b|"
    r"what'?s\b|what (?:can|could|cannot|can'?t)\b|explain\b|tell me (?:about|how|what)\b|where (?:is|are|can|do|does)\b|why\b|"
    r"which (?:plan|page|format|formats|export)\b|"
    r"چطور|چگونه|چه ?جوری|چه ?طوری|چیست|چیه|چی هست|یعنی چه|یعنی چی|چه فرقی|فرقش|توضیح|معنی|منظور از|"
    r"چه کارهایی|چه کاری|چه چیزهایی|چه چیزی|چی کار)", re.I)
_Q_WEAK = re.compile(
    r"(?:\bcan i\b|\bcould i\b|\bis it possible\b|\bis there\b|\bdoes (?:it|the|saia|this)\b|\bdo you (?:support|have)\b|"
    r"کجاست|کجا|چرا|آیا|امکان دارد|ممکن است|می ?شود|میشه|می ?توان\b)", re.I)
_POLITE_CMD = re.compile(
    r"(?:\b(?:can|could|would|will) you\b|\bplease\b|لطفا|لطفاً|می ?توانید|می ?تونید|می ?توانی|میتونی|می ?تونی|بتوانید|میشه|می ?شود).{0,120}"
    r"(?:بده|بدی|بدهید|بفرست|کنی|کنید|بگیر|بگیری|بسازی|بسازید|دانلود|download|export|give|send|generate|run)", re.I)


# Words that make an explain question about THE PLATFORM (not about structural engineering in general:
# "what is structural drift?" stays a general-chat question).
_PLATFORM_TOPIC = re.compile(
    r"(export|download|zip\b|etabs|time ?history|pushover|nonlinear|p-?delta|spectrum|\bmodal\b|log ?in|sign ?in|sign ?up|google|traffic|what'?s new|"
    r"تاریخچه ?زمانی|پوش ?اور|غیرخطی|طیف|مودال|ورود(?![یا-ی])|ثبت ?نام|گوگل|ترافیک|تازه|جدید|حریم|شرایط استفاده|\bsafe\b|sap ?2000|\bdxf\b|\bpdf\b|excel|report|validation|approv|memory|billing|\bplans?\b|pricing|price|"
    r"crypto|usdt|bitcoin|btc|upgrade|subscri|optimi[sz]|workspace|\bpage\b|\bproject|upload|\bassistants?\b|agents?\b|"
    r"capabilit|limitation|\b(?:can'?t|cannot|can) (?:it|you|saia|the (?:platform|app))\b|what can (?:it|you|saia)\b|what (?:it|you) can|saia|platform|"
    r"دانلود|خروجی|اعتبارسنجی|تایید|تأیید|حافظه|پرداخت|پلن|اشتراک|قیمت|کریپتو|رمزارز|ارتقا|بهینه|پروژه|صفحه|دستیار|عامل|آپلود|"
    r"محدودیت|امکانات|قابلیت|پلتفرم|سامانه|نمی ?توان|چه کارهایی|چه کاری|چه چیزهایی|چه کارایی)", re.I)


def is_platform_explain_question(message: str) -> bool:
    """An explain question that is about the platform: it beats the action regexes and gets an explanation."""
    n = normalize(message)
    return is_explain_question(n) and bool(_PLATFORM_TOPIC.search(n))


def is_explain_question(message: str) -> bool:
    """True for how-to / what-is / explain questions. Engineering requests with numbers are never explain questions."""
    n = normalize(message)
    if not n or len(n) > 240:
        return False
    if _ENGINEERING.search(n) and re.search(r"\d", n):
        return False
    if _Q_STRONG.search(n):
        return True
    asked = n.endswith("?") or n.endswith("؟") or "؟" in n or "?" in n
    return bool(asked and _Q_WEAK.search(n) and not _POLITE_CMD.search(n))


@dataclass(frozen=True)
class Intent:
    name: str
    text: str = ""  # for bug_report: the description after the prefix

    @property
    def handled_by_helper(self) -> bool:
        return self.name != "engineering"


def classify(message: str) -> Intent:
    raw = (message or "").strip()
    n = normalize(raw)
    if not n:
        return Intent("engineering")
    m = _BUG_PREFIX.match(raw)
    if m:
        return Intent("bug_report", (m.group("rest") or "").strip())
    if _STATUS.search(n):
        return Intent("issue_status")
    if _REPORT_IT.match(n):
        return Intent("report_it")
    if _GREETING.match(n):
        return Intent("greeting")
    has_eng = bool(_ENGINEERING.search(n))
    if len(n) < 400 and (_NAMED_CODES.search(n) or ((_BUG_WORDS.search(n) or _ERROR_CODES.search(n)) and not _ENGINEERING_VERB.search(n))):
        # a complaint about the product (not an engineering request that happens to contain "error")
        # a problem the user describes: the helper explains the likely cause and (for real errors) files it automatically
        return Intent("diagnose", raw)
    if _HOWTO.match(n) and len(n) < 200:
        return Intent("platform_help")
    if is_platform_explain_question(n):
        return Intent("platform_help")
    if _HELP.search(n) and not _ENGINEERING_VERB.search(n) and (len(n) < 200) and not (has_eng and re.search(r"\d", n)):
        return Intent("platform_help")
    return Intent("engineering")
