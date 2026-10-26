"""HelperService: intent routing + LLM conversation (with graceful stub) + issue reporting.

The LLM never produces engineering numbers; engineering intents are NOT handled here (return ``None`` from ``handle``).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from app.platform_helper.config import HelperSettings, load_settings
from app.platform_helper.intents import Intent, classify, is_persian
from app.platform_helper.issues import (InMemoryIssueStore, IssueNotifier, IssueReport, IssueService, IssueStore,
                                        OPEN_STATUSES)
from app.platform_helper.llm import LLMClient, LLMUnavailableError
from app.platform_helper.prompt import build_system_prompt

logger = logging.getLogger(__name__)

TokenSink = Callable[[str], None]
KnowledgeProvider = Callable[[bool], str]  # (fa) -> generated knowledge markdown
FaqProvider = Callable[[str, bool, "dict[str, str] | None", bool], "str | None"]  # (message, fa, context, allow_overview)

_STUB_HELP_FA = (
    "من دستیار پلتفرم هستم. فعلاً مدل زبانی در دسترس نیست، اما این کارها را همین الان می‌توانم انجام دهم:\n"
    "- تحلیل تیر، قاب سه‌بعدی و طراحی تیر بتنی از داخل چت (مثلاً «قاب سه‌بعدی ۴ طبقه ۳×۳ دهانه»)\n"
    "- بهینه‌سازی قاب (اگر ورودی‌ها ناقص باشد، چک‌لیست و گزینهٔ «پیش‌فرض‌ها را فرض کن» نشان داده می‌شود)\n"
    "- صفحات: مدل، تحلیل، طراحی، بهینه‌سازی، صحت‌سنجی، تأییدها، حافظه، ردگیری\n"
    "- «گزارش مشکل: …» برای ثبت ایراد پلتفرم، و «وضعیت گزارش‌ها» برای دیدن پیگیری آن."
)
_STUB_HELP_EN = (
    "I'm the platform assistant. The language model is temporarily unavailable, but I can still:\n"
    "- analyse beams, 3D frames and design RC beams from chat (e.g. \"3D frame 4 stories 3x3 bays\")\n"
    "- optimise a frame (missing inputs are shown as a checklist with an \"assume defaults\" option)\n"
    "- pages: Model, Analysis, Design, Optimization, Validation, Approvals, Memory, Traceability\n"
    "- \"report a problem: …\" files an issue; \"issue status\" shows its progress."
)


@dataclass
class HelperReply:
    text: str
    intent: str
    provider: str = "rule"
    model: str = ""
    issue_id: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_metadata(self) -> dict[str, Any]:
        md = {"mode": "platform_helper", "intent": self.intent, "provider": self.provider, **self.metadata}
        if self.model:
            md["model"] = self.model
        if self.issue_id:
            md["issue_id"] = self.issue_id
        return md


class HelperService:
    def __init__(self, settings: HelperSettings | None = None, *, llm: LLMClient | None = None,
                 store: IssueStore | None = None, notifier: IssueNotifier | None = None,
                 knowledge_path: str | None = None, product: str = "structuralai",
                 knowledge_provider: KnowledgeProvider | None = None, faq_provider: FaqProvider | None = None) -> None:
        self.settings = settings or load_settings()
        self.llm = llm or LLMClient(self.settings.providers)
        self.store = store or InMemoryIssueStore()
        self.notifier = notifier or IssueNotifier(self.settings.webhook_url, self.settings.webhook_secret,
                                                   self.settings.webhook_retries, product=product)
        self.issues = IssueService(self.store, self.notifier)
        self.knowledge_path = knowledge_path
        # Product-specific hooks (the helper package stays product-agnostic): generated knowledge for the prompt and a
        # static FAQ used when the LLM is unavailable.
        self.knowledge_provider = knowledge_provider
        self.faq_provider = faq_provider

    # ------------------------------------------------------------- public
    def classify(self, message: str) -> Intent:
        return classify(message)

    def handle(self, message: str, history: Iterable[tuple[str, str]] = (), *, account_id: str = "",
               project_id: str = "", conversation_id: str = "", page: str = "chat", context: dict[str, str] | None = None,
               on_token: TokenSink | None = None, force_llm: bool = False) -> HelperReply | None:
        """Return a reply for helper-owned intents; ``None`` means "let the engineering engines handle it"."""
        intent = classify(message)
        if not intent.handled_by_helper and not force_llm:
            return None
        fa = is_persian(message)
        if intent.name == "bug_report":
            return self._bug_report(intent, message, list(history), account_id=account_id, project_id=project_id,
                                    conversation_id=conversation_id, page=page, fa=fa)
        if intent.name == "issue_status":
            return self._issue_status(account_id, fa)
        return self.converse(message, history, intent=intent.name, context=context, fa=fa, on_token=on_token)

    def converse(self, message: str, history: Iterable[tuple[str, str]] = (), *, intent: str = "platform_help",
                 context: dict[str, str] | None = None, fa: bool | None = None, on_token: TokenSink | None = None) -> HelperReply:
        fa = is_persian(message) if fa is None else fa
        extra = ""
        if self.knowledge_provider is not None:
            try:
                extra = self.knowledge_provider(fa)
            except Exception:  # noqa: BLE001 - never let the knowledge block break a reply
                logger.exception("knowledge provider failed")
        msgs: list[dict[str, str]] = [{"role": "system", "content": build_system_prompt(
            knowledge_path=self.knowledge_path, context=context, lang="fa" if fa else "en", extra_knowledge=extra)}]
        for role, content in list(history)[-self.settings.max_history:]:
            if role in ("user", "assistant") and content:
                msgs.append({"role": role, "content": content[:2500]})
        msgs.append({"role": "user", "content": message})
        if not self.llm.configured:
            return self._stub(intent, fa, on_token, message=message, context=context)
        try:
            if on_token is not None:
                parts: list[str] = []
                for piece in self.llm.stream(msgs):
                    parts.append(piece)
                    on_token(piece)
                text = "".join(parts).strip()
                st = self.llm.status()
                return HelperReply(text, intent, provider="llm", model=st[0]["model"] if st else "")
            res = self.llm.chat(msgs)
            return HelperReply(res.text, intent, provider=res.provider, model=res.model)
        except LLMUnavailableError as exc:
            logger.warning("helper LLM unavailable: %s", exc)
            return self._stub(intent, fa, on_token, message=message, context=context)

    def report_issue(self, report: IssueReport) -> tuple[IssueReport, bool]:
        return self.issues.report(report)

    def auto_report(self, title: str, *, error_text: str = "", page: str = "", account_id: str = "", project_id: str = "",
                    conversation_id: str = "", user_message: str = "", severity: str = "medium",
                    suspected_files: list[str] | None = None) -> IssueReport | None:
        """Hook for engine failures. Never raises; deduplicates; records only (no code change)."""
        try:
            issue, _ = self.issues.report(IssueReport(
                title=title, error_text=error_text, page=page, account_id=account_id, project_id=project_id,
                conversation_id=conversation_id, user_message=user_message, severity=severity, source="auto_detected",
                suspected_files=suspected_files or []))
            return issue
        except Exception:  # noqa: BLE001
            logger.exception("auto_report failed")
            return None

    def status(self) -> dict[str, Any]:
        return {"llm_configured": self.llm.configured, "providers": self.llm.status(),
                "webhook_enabled": self.notifier.enabled, "provider_mode": self.settings.provider_mode}

    # ------------------------------------------------------------ internals
    def _faq(self, message: str, intent: str, fa: bool, context: dict[str, str] | None) -> str | None:
        if self.faq_provider is None or intent == "greeting" or not message:
            return None
        try:
            # Overview fallback only for genuine platform questions; free chat keeps the old fallback chain unless a topic matches.
            return self.faq_provider(message, fa, context, intent == "platform_help")
        except Exception:  # noqa: BLE001
            logger.exception("faq provider failed")
            return None

    def _stub(self, intent: str, fa: bool, on_token: TokenSink | None, *, message: str = "",
              context: dict[str, str] | None = None) -> HelperReply:
        faq = self._faq(message, intent, fa, context)
        if faq:
            if on_token:
                on_token(faq)
            return HelperReply(faq, intent, provider="faq")
        if intent == "greeting":
            text = ("سلام! چطور می‌توانم کمکتان کنم؟ می‌توانید تحلیل یا طراحی را از همین چت شروع کنید.\n\n" + _STUB_HELP_FA) if fa else \
                ("Hello! How can I help? You can start an analysis or design right from this chat.\n\n" + _STUB_HELP_EN)
        else:
            text = _STUB_HELP_FA if fa else _STUB_HELP_EN
        if on_token:
            on_token(text)
        return HelperReply(text, intent, provider="stub")

    def _bug_report(self, intent: Intent, message: str, history: list[tuple[str, str]], *, account_id: str, project_id: str,
                    conversation_id: str, page: str, fa: bool) -> HelperReply:
        desc = intent.text or message
        last_assistant = next((c for r, c in reversed(history) if r == "assistant"), "")
        issue, created = self.issues.report(IssueReport(
            title=desc.strip().splitlines()[0][:120] if desc.strip() else "User reported a problem",
            summary=desc, source="user_report", page=page, account_id=account_id, project_id=project_id,
            conversation_id=conversation_id, user_message=message, assistant_excerpt=last_assistant))
        if fa:
            text = (f"مشکل ثبت شد (کد {issue.id[:8]}). " + ("" if created else "این مورد قبلاً گزارش شده بود و شمارندهٔ آن بالا رفت. ")
                    + "مدیر پلتفرم آن را بررسی می‌کند؛ هر اصلاحی فقط پس از تأیید مدیر اعمال می‌شود. "
                    "برای دیدن پیگیری بنویسید «وضعیت گزارش‌ها».")
        else:
            text = (f"Issue recorded (id {issue.id[:8]}). " + ("" if created else "It had already been reported; I bumped its counter. ")
                    + "A platform admin will review it; any fix is applied only after admin approval. "
                    "Type \"issue status\" to follow progress.")
        return HelperReply(text, "bug_report", issue_id=issue.id, metadata={"issue_status": issue.status})

    def _issue_status(self, account_id: str, fa: bool) -> HelperReply:
        items = self.store.list(account_id=account_id or None, limit=8)
        if not items:
            return HelperReply("هنوز گزارشی ثبت نکرده‌اید." if fa else "You have not reported any issues yet.", "issue_status")
        lines = [("**گزارش‌های شما:**" if fa else "**Your reports:**")]
        for i in items:
            lines.append(f"- `{i.id[:8]}` {i.title[:80]} — {i.user_status_message(fa)}" + (f" ({i.fix_pr_url})" if i.fix_pr_url else ""))
        return HelperReply("\n".join(lines), "issue_status", metadata={"open": sum(1 for i in items if i.status in OPEN_STATUSES)})
