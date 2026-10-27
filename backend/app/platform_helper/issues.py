"""Structured platform-issue reports, storage protocol, redaction and the optional signed outbound webhook.

Safety: an issue is only a *record*. Nothing here changes code, deploys or merges. A proposed fix is stored as
text (diff / PR draft) with status ``draft``; a human must approve and merge it elsewhere.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
import threading
import time
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 1
STATUSES = ("open", "triaged", "fix_in_progress", "fix_ready", "awaiting_approval", "resolved", "rejected", "wontfix")
OPEN_STATUSES = ("open", "triaged", "fix_in_progress", "fix_ready", "awaiting_approval")
SEVERITIES = ("low", "medium", "high", "critical")
SOURCES = ("user_report", "auto_detected", "admin")


def utcnow() -> datetime:
    return datetime.now(UTC)


_REDACTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"(?i)bearer\s+[a-z0-9._\-]{12,}"), "Bearer [REDACTED]"),
    (re.compile(r"\b(?:sk|gsk|ghp|github_pat|xox[bp]|AIza)[A-Za-z0-9_\-]{16,}"), "[REDACTED_KEY]"),
    (re.compile(r"(?i)(api[_-]?key|secret|token|password|passwd)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"(?i)(توکن|رمز(?: عبور)?|کلید(?: api)?|پسورد)\s*[:=]\s*\S+"), r"\1=[REDACTED]"),
    (re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"), "[email]"),
    (re.compile(r"\b[A-Fa-f0-9]{32,}\b"), "[hex]"),
]


def redact(text: str | None, limit: int = 4000) -> str:
    out = text or ""
    for pat, repl in _REDACTIONS:
        out = pat.sub(repl, out)
    return out[:limit]


@dataclass
class IssueReport:
    title: str
    summary: str = ""
    category: str = "bug"  # bug | ux | data | performance | other
    severity: str = "medium"
    source: str = "user_report"
    page: str = ""
    conversation_id: str = ""
    project_id: str = ""
    account_id: str = ""
    user_message: str = ""
    assistant_excerpt: str = ""
    error_text: str = ""
    steps_to_reproduce: list[str] = field(default_factory=list)
    expected: str = ""
    actual: str = ""
    suspected_files: list[str] = field(default_factory=list)
    app_version: str = ""
    locale: str = ""
    dedupe_key: str = ""
    # lifecycle / admin fields
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "open"
    occurrences: int = 1
    fix_note: str = ""
    fix_pr_url: str = ""
    proposed_fix: dict[str, Any] = field(default_factory=dict)  # {kind: diff|pr_draft, title, body, diff, status: draft}
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def sanitized(self) -> IssueReport:
        self.title = redact(self.title, 200) or "Untitled issue"
        self.summary = redact(self.summary, 2000)
        self.user_message = redact(self.user_message, 2000)
        self.assistant_excerpt = redact(self.assistant_excerpt, 1500)
        self.error_text = redact(self.error_text, 3000)
        self.actual = redact(self.actual, 1000)
        self.expected = redact(self.expected, 1000)
        self.steps_to_reproduce = [redact(s, 300) for s in self.steps_to_reproduce][:12]
        if self.severity not in SEVERITIES:
            self.severity = "medium"
        if self.source not in SOURCES:
            self.source = "user_report"
        if not self.dedupe_key:
            basis = f"{self.category}|{self.page}|{self.title.lower()}|{(self.error_text or '')[:120]}"
            self.dedupe_key = hashlib.sha256(basis.encode()).hexdigest()[:24]
        return self

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        return d

    def user_status_message(self, fa: bool) -> str:
        """Short sentence the chat shows to the user about this issue."""
        s = self.status
        if fa:
            m = {
                "open": "مشکل ثبت شد و به‌زودی بررسی می‌شود.",
                "triaged": "مشکل بررسی و اولویت‌بندی شد.",
                "fix_in_progress": "در حال آماده‌سازی اصلاح هستیم.",
                "fix_ready": "اصلاح آماده است و منتظر تأیید مدیر پلتفرم است.",
                "awaiting_approval": "اصلاح آماده است و منتظر تأیید مدیر پلتفرم است.",
                "resolved": "مشکل رفع شد.",
                "rejected": "این گزارش رد شد.",
                "wontfix": "این مورد فعلاً اصلاح نمی‌شود.",
            }
        else:
            m = {
                "open": "Issue reported; it will be reviewed shortly.",
                "triaged": "Issue triaged.",
                "fix_in_progress": "A fix is being prepared.",
                "fix_ready": "Fix PR ready — awaiting admin approval.",
                "awaiting_approval": "Fix PR ready — awaiting admin approval.",
                "resolved": "Issue resolved.",
                "rejected": "This report was rejected.",
                "wontfix": "This will not be fixed for now.",
            }
        msg = m.get(s, s)
        if self.fix_note:
            msg += f" — {self.fix_note}" if not fa else f" — {self.fix_note}"
        return msg


class IssueStore(Protocol):
    def add(self, issue: IssueReport) -> IssueReport: ...
    def get(self, issue_id: str) -> IssueReport | None: ...
    def list(self, *, statuses: tuple[str, ...] | None = None, account_id: str | None = None, limit: int = 100) -> list[IssueReport]: ...
    def update(self, issue_id: str, **fields: Any) -> IssueReport | None: ...
    def find_open_by_dedupe(self, dedupe_key: str) -> IssueReport | None: ...
    def delete(self, issue_id: str) -> bool: ...


class InMemoryIssueStore:
    def __init__(self) -> None:
        self._items: dict[str, IssueReport] = {}
        self._lock = threading.Lock()

    def add(self, issue: IssueReport) -> IssueReport:
        with self._lock:
            self._items[issue.id] = issue
        return issue

    def get(self, issue_id: str) -> IssueReport | None:
        return self._items.get(issue_id)

    def list(self, *, statuses=None, account_id=None, limit=100) -> list[IssueReport]:
        items = sorted(self._items.values(), key=lambda i: i.created_at, reverse=True)
        if statuses:
            items = [i for i in items if i.status in statuses]
        if account_id:
            items = [i for i in items if i.account_id == account_id]
        return items[:limit]

    def update(self, issue_id: str, **fields: Any) -> IssueReport | None:
        with self._lock:
            item = self._items.get(issue_id)
            if item is None:
                return None
            for k, v in fields.items():
                if hasattr(item, k):
                    setattr(item, k, v)
            item.updated_at = utcnow()
            return item

    def find_open_by_dedupe(self, dedupe_key: str) -> IssueReport | None:
        for i in self._items.values():
            if i.dedupe_key == dedupe_key and i.status in OPEN_STATUSES:
                return i
        return None

    def delete(self, issue_id: str) -> bool:
        return self._items.pop(issue_id, None) is not None


# ---------------------------------------------------------------- webhook ---------------------------------------
def webhook_payload(event: str, issue: IssueReport, *, product: str = "structuralai") -> dict[str, Any]:
    """Payload schema (version 1) POSTed to PLATFORM_ISSUE_WEBHOOK_URL. See docs/PLATFORM_HELPER.md."""
    d = issue.to_dict()
    return {
        "schema_version": SCHEMA_VERSION,
        "event": event,  # platform_issue.created | platform_issue.updated
        "delivery_id": str(uuid.uuid4()),
        "sent_at": utcnow().isoformat(),
        "product": product,
        "issue": {
            k: d[k]
            for k in (
                "id", "title", "summary", "category", "severity", "source", "status", "page", "conversation_id",
                "project_id", "user_message", "assistant_excerpt", "error_text", "steps_to_reproduce", "expected",
                "actual", "suspected_files", "app_version", "locale", "occurrences", "dedupe_key", "fix_note",
                "fix_pr_url", "proposed_fix", "created_at", "updated_at",
            )
        },
    }


def sign_body(secret: str, timestamp: str, body: bytes) -> str:
    mac = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def verify_signature(secret: str, timestamp: str, body: bytes, signature: str) -> bool:
    return hmac.compare_digest(sign_body(secret, timestamp, body), signature or "")


class IssueNotifier:
    """Optional outbound webhook with HMAC signature and exponential-backoff retries (off unless URL is set)."""

    def __init__(self, url: str = "", secret: str = "", retries: int = 3, *, product: str = "structuralai",
                 transport: httpx.BaseTransport | None = None, sleep: Callable[[float], None] = time.sleep,
                 background: bool = True, timeout: float = 8.0, auth_token: str = "") -> None:
        self.url, self.secret, self.retries = url, secret, max(1, retries)
        self.auth_token = (auth_token or "").strip()
        self.product, self._transport, self._sleep = product, transport, sleep
        self._background, self._timeout = background, timeout
        self.deliveries: list[dict[str, Any]] = []  # recent attempts (status only), for the admin view

    @property
    def enabled(self) -> bool:
        return bool(self.url)

    def notify(self, event: str, issue: IssueReport) -> None:
        if not self.enabled:
            return
        payload = webhook_payload(event, issue, product=self.product)
        if self._background:
            threading.Thread(target=self._deliver, args=(payload,), daemon=True).start()
        else:
            self._deliver(payload)

    def _deliver(self, payload: dict[str, Any]) -> bool:
        body = json.dumps(payload, default=str, separators=(",", ":")).encode()
        for attempt in range(1, self.retries + 1):
            ts = str(int(time.time()))
            headers = {
                "Content-Type": "application/json",
                "X-Platform-Event": payload["event"],
                "X-Platform-Delivery": payload["delivery_id"],
                "X-Platform-Timestamp": ts,
                "User-Agent": "platform-helper/1",
            }
            if self.auth_token:
                headers["Authorization"] = f"Bearer {self.auth_token}"
            if self.secret:
                headers["X-Platform-Signature"] = sign_body(self.secret, ts, body)
            code: int | str = "error"
            try:
                with httpx.Client(timeout=self._timeout, transport=self._transport) as c:
                    resp = c.post(self.url, content=body, headers=headers)
                code = resp.status_code
                if 200 <= resp.status_code < 300:
                    self._log(payload, attempt, code)
                    return True
                if 400 <= resp.status_code < 500 and resp.status_code not in (408, 429):
                    self._log(payload, attempt, code)
                    return False  # permanent client error: do not hammer
            except httpx.HTTPError as exc:
                code = type(exc).__name__
            self._log(payload, attempt, code)
            if attempt < self.retries:
                self._sleep(min(30.0, 2.0 ** attempt))
        logger.warning("platform issue webhook failed after %d attempts", self.retries)
        return False

    def _log(self, payload: dict[str, Any], attempt: int, code: Any) -> None:
        self.deliveries.append({"delivery_id": payload["delivery_id"], "event": payload["event"], "attempt": attempt,
                                "result": code, "at": utcnow().isoformat()})
        del self.deliveries[:-50]


class IssueService:
    """report → dedupe → store → notify; plus admin post-back (status / fix note / PR url)."""

    def __init__(self, store: IssueStore, notifier: IssueNotifier | None = None) -> None:
        self.store = store
        self.notifier = notifier or IssueNotifier()

    def report(self, issue: IssueReport) -> tuple[IssueReport, bool]:
        issue.sanitized()
        existing = self.store.find_open_by_dedupe(issue.dedupe_key)
        if existing is not None:
            updated = self.store.update(existing.id, occurrences=existing.occurrences + 1)
            return (updated or existing), False
        saved = self.store.add(issue)
        self.notifier.notify("platform_issue.created", saved)
        return saved, True

    def post_back(self, issue_id: str, *, status: str | None = None, fix_note: str | None = None,
                  fix_pr_url: str | None = None, proposed_fix: dict[str, Any] | None = None) -> IssueReport | None:
        fields: dict[str, Any] = {}
        if status is not None:
            if status not in STATUSES:
                raise ValueError(f"status must be one of {', '.join(STATUSES)}")
            fields["status"] = status
        if fix_note is not None:
            fields["fix_note"] = redact(fix_note, 1000)
        if fix_pr_url is not None:
            fields["fix_pr_url"] = fix_pr_url[:500]
        if proposed_fix is not None:
            fields["proposed_fix"] = {**proposed_fix, "status": proposed_fix.get("status", "draft")}
        updated = self.store.update(issue_id, **fields)
        if updated is not None:
            self.notifier.notify("platform_issue.updated", updated)
        return updated
