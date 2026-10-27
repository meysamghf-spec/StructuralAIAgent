"""Cheap, deterministic gating around the model: which messages go to it (``auto`` mode) and yes/no replies to a confirmation."""

from __future__ import annotations

import re

from app.application import frame3d_chat_analysis as f3
from app.application import frame3d_followup as fu
from app.application.chat_actions import _n

_ZW = "\u200c"

# action families (fa / Finglish / en). A message that asks for two or more different families is a compound command.
_FAMILIES: dict[str, str] = {
    "build": r"بساز|ایجاد|مدل\s*کن|طراحی\s*کن|(?<![a-z])build|create|model it|generate|besaz|bsaz|dorost\s*kon|ijad",
    "analyze": r"تحلیل|آنالیز|analy[sz]e|analysis|tahlil|analiz",
    "design": r"طراحی|کنترل|design|check|tarahi|kontrol",
    "optimize": r"بهینه|optimi[sz]|behine|behineh|minimi[sz]e",
    "export": r"خروجی|دانلود|اکسپورت|e2k|f2k|s2k|dxf|etabs|safe\b|sap|export|download|khoroji|ekhrooji|report|گزارش|نقشه",
    "project": r"پروژه|project|proje\b",
}
_AFFIRM = re.compile(r"^(?:بله|بلی|آره|اره|باشه|باشد|تایید|تأیید|تاييد|اوکی|اکی|درسته|انجام\s*بده|اجرا\s*کن|بزن|ادامه\s*بده|بله\s*انجام\s*بده|"
                     r"ok|okay|yes|yep|yeah|sure|go\s*ahead|do\s*it|confirm(?:ed)?|proceed|bale|are|ba+she|taeed|anjam\s*bede|bede)$", re.I)
_DENY = re.compile(r"^(?:نه|نخیر|خیر|لغو|کنسل|بیخیال|نکن|نمی\s*خوام|no|nope|cancel|stop|never\s*mind|abort|na|nakhair|nakon|lagv)$", re.I)


def _norm(text: str) -> str:
    return _n(text).replace(_ZW, " ").strip(" .!?؟،,؛")


def is_affirmative(text: str) -> bool:
    return bool(_AFFIRM.match(_norm(text)))


def is_negative(text: str) -> bool:
    return bool(_DENY.match(_norm(text)))


def families(text: str) -> set[str]:
    t = _n(text)
    return {name for name, pat in _FAMILIES.items() if re.search(pat, t, re.I)}


def is_trivial(text: str) -> bool:
    """Greetings / thanks / empty: never worth a model call."""
    t = _norm(text)
    return len(t) < 3 or bool(re.fullmatch(r"(?:سلام|درود|hi|hello|hey|salam|مرسی|ممنون|thanks?|thank you|mersi|mamnoon)[ !.]*", t, re.I))


def wants_model(text: str, mode: str) -> bool:
    """off: never. always: everything except trivia. auto: compound requests and frame requests the rule parser cannot complete."""
    if mode not in ("auto", "always") or is_trivial(text):
        return False
    if mode == "always":
        return True
    fams = families(text) - {"design"}  # "design" is implied by a build/analyze request; it alone is not "compound"
    if len(fams) >= 2:
        return True
    try:
        if f3.is_frame3d_request(text) and f3.missing_inputs(f3.parse_frame3d_request(text)):
            return True
        return bool(fu.is_assume_reply(text)) and len(fams) >= 1
    except Exception:  # noqa: BLE001 - a parser hiccup must never block the rule-based path
        return False
