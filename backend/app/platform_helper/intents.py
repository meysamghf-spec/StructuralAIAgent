"""Deterministic intent routing (no LLM needed). The LLM only talks; engines compute.

Intents: ``engineering`` (leave to the platform engines), ``bug_report``, ``issue_status``, ``greeting``, ``platform_help``.
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
_STATUS = re.compile(r"(issue status|status of (my )?(issue|report)s?|my reports|وضعیت گزارش|گزارش(‌| )?های من|وضعیت مشکل)", re.I)
_GREETING = re.compile(r"^\s*(hi|hello|hey|salam|slm|سلام|درود|وقت بخیر|صبح بخیر|عصر بخیر|thanks|thank you|مرسی|ممنون|تشکر)[\s!.،,؟?]*$", re.I)
_HELP = re.compile(
    r"(what can you do|what you can do|what are you|who are you|what do you do|how (do|can) i|how does (the )?platform|what is (this )?(platform|structuralai|saai)|help me|\bhelp\b|where (is|can i find)|"
    r"which page|explain (the )?(platform|page|approval|optimization|validation)|"
    r"چه کاری|چکار می ?کنی|چه کارهایی|چطور|چگونه|کجا|کمک|راهنما|پلتفرم|این صفحه|تایید پروژه|تأیید پروژه|چیست|یعنی چه|معنی)", re.I)
_HOWTO = re.compile(r"^(?:(?:hi|hello|hey|سلام|درود)[\s,،!.]*)?(how (do|can|should) i|how does|where (is|can i)|why (does|is|can'?t)|چطور|چگونه|چرا|کجا|چه جوری)", re.I)
_ENGINEERING = re.compile(
    r"(\d\s*(m|kn|mpa|kn/m|متر|کیلو)|analy[sz]e|design (a|the)|optimi[sz]e|frame|beam|column|slab|footing|storey|story|stories|"
    r"تحلیل|طراحی|بهینه|قاب|تیر|ستون|دال|پی\b|طبقه|دهانه|بار گسترده|مقطع|آرماتور|سازه)", re.I)
_ENGINEERING_VERB = re.compile(r"(analy[sz]e|design|optimi[sz]e|run |calculate|check the|تحلیل کن|طراحی کن|بهینه کن|محاسبه کن|اجرا کن|بررسی کن)", re.I)


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
    if _GREETING.match(n):
        return Intent("greeting")
    has_eng = bool(_ENGINEERING.search(n))
    if _BUG_WORDS.search(n) and len(n) < 400 and not _ENGINEERING_VERB.search(n):
        # a complaint about the product (not an engineering request that happens to contain "error")
        return Intent("bug_report", raw)
    if _HOWTO.match(n) and len(n) < 200:
        return Intent("platform_help")
    if _HELP.search(n) and not _ENGINEERING_VERB.search(n) and (len(n) < 200) and not (has_eng and re.search(r"\d", n)):
        return Intent("platform_help")
    return Intent("engineering")
