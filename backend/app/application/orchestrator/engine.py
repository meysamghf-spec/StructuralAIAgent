"""The bounded tool-calling loop. ``run_turn`` returns ``(reply, metadata)`` or ``None`` (= use the rule-based pipeline)."""

from __future__ import annotations

import json
import logging
import re
import threading
import time
from collections import defaultdict, deque
from typing import Any

from app.application import chat_actions as ca
from app.application import frame3d_followup as fu
from app.application.orchestrator import intent
from app.application.orchestrator.config import OrchestratorSettings, load_settings
from app.application.orchestrator.context import PlatformPort, TurnContext
from app.application.orchestrator.llm import OrchestratorUnavailable, ToolLLM, get_llm
from app.application.orchestrator.prompt import build_system_prompt
from app.application.orchestrator.registry import ToolRegistry, ToolResult
from app.application.orchestrator.tools import get_registry

logger = logging.getLogger(__name__)
audit_log = logging.getLogger("saia.orchestrator.audit")

_FINGLISH = re.compile(r"\b(?:besaz|bsaz|tahlil|analiz|behine|behineh|ghab|tabaghe|tabage|dahane|dahaneh|sotoon|khorooji|khoroji|lotfan|mikham|"
                       r"bokon|bezan|bede|begir|ro|ra|va|ham)\b", re.I)

_hits: dict[str, deque[float]] = defaultdict(deque)
_hits_lock = threading.Lock()


def is_persian_chat(text: str, history: list[dict[str, str]] | None = None) -> bool:
    if ca.is_fa(text) or fu.is_finglish(text) or len(_FINGLISH.findall(text or "")) >= 2:
        return True
    return False


def rate_limited(account_id: str, limit: int, now: float | None = None) -> bool:
    """Sliding one-hour window per account (per worker process). Registers the hit when allowed."""
    now = time.monotonic() if now is None else now
    with _hits_lock:
        q = _hits[account_id]
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= limit:
            return True
        q.append(now)
        return False


def reset_rate_limits() -> None:
    with _hits_lock:
        _hits.clear()


def _history_messages(history: list[dict[str, str]], limit: int = 8) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for m in history[-limit:]:
        role = m.get("role")
        content = str(m.get("content") or "").strip()
        if role not in ("user", "assistant") or not content:
            continue
        if len(content) > 700:
            content = content[:700] + " …[truncated]"
        out.append({"role": role, "content": content})
    return out


def _state_for_prompt(ctx: TurnContext) -> dict[str, Any]:
    port = ctx.port
    model = ctx.current_model()
    from app.application.orchestrator import summaries as sm

    return {"project": (port.project or {}).get("name") or "none (analysis still works without a project; downloads/memory need one)",
            "model_in_chat": sm.model_line(model, False) if model else "none yet",
            "user_language": "Persian" if ctx.fa else "English", "plan_and_usage": port.usage_snapshot()}


def _compose_degraded(ctx: TurnContext, results: list[tuple[str, ToolResult]], note: bool) -> str:
    fa = ctx.fa
    parts: list[str] = []
    for _name, r in results:
        txt = (r.text_fa if fa else r.text_en).strip()
        if txt and r.status in ("ok", "confirmation_required", "error", "missing_inputs", "quota_exceeded") and txt not in parts:
            parts.append(txt)
    body = "\n\n---\n\n".join(parts)
    if ctx.assumed:
        body += ("\n\n**فرض‌های پلتفرم:** " if fa else "\n\n**Assumptions made by the platform:** ") + ", ".join(ctx.assumed)
    if note:
        body = (("دستیار هوشمند در این لحظه پاسخ نداد؛ نتایج خام کارها در ادامه است.\n\n" if fa else
                 "The AI assistant did not answer just now; here are the raw results of the steps that ran.\n\n") + body)
    return body.strip()


def _metadata(ctx: TurnContext, calls: int, provider: str, model: str, degraded: bool) -> dict[str, Any]:
    orch: dict[str, Any] = {"llm_calls": calls, "provider": provider, "model": model, "degraded": degraded, "trace": ctx.trace[:20]}
    if ctx.payload is not None and ctx.model:
        orch["model"] = ctx.model  # newest frame inputs, so the next turn continues from this model even after a compound turn
    if ctx.pending:
        orch["pending"] = {k: ctx.pending[k] for k in ("tool", "args", "key", "fa", "en")}
    meta: dict[str, Any] = {"mode": "orchestrated", "intent": "orchestrated", "orchestrator": orch}
    meta.update(ctx.ui)
    if ctx.assumed:
        meta["assumed_defaults"] = ctx.assumed
    return meta


def run_turn(port: PlatformPort, text: str, history: list[dict[str, str]], *, settings: OrchestratorSettings | None = None,
             llm: ToolLLM | None = None, registry: ToolRegistry | None = None, pending: dict[str, Any] | None = None,
             gate: bool = True) -> tuple[str, dict[str, Any]] | None:
    settings = settings or load_settings()
    if not settings.enabled:
        return None
    if gate and not intent.wants_model(text, settings.mode):
        # a pending yes/no must still be honoured in auto mode
        if not (pending and (intent.is_affirmative(text) or intent.is_negative(text))):
            return None
    if ca.parse_approval_command(text) is not None or ca.parse_assistant_switch(text) is not None:
        return None  # human sign-off and assistant switching stay explicit rule-based user commands
    fa = is_persian_chat(text, history)
    registry = registry or get_registry()
    ctx = TurnContext(port=port, settings=settings, fa=fa)
    results: list[tuple[str, ToolResult]] = []
    user_for_model = text

    # ---- a destructive call is waiting for the user's yes / no (decided here, by deterministic checks, never by the model)
    if pending:
        if intent.is_negative(text):
            msg = "باشه، انجام نشد و چیزی تغییر نکرد." if fa else "Okay — cancelled, nothing was changed."
            return msg, {"mode": "orchestrated", "intent": "orchestrated", "orchestrator": {"cancelled": pending.get("tool"), "llm_calls": 0}}
        if intent.is_affirmative(text):
            ctx.confirmed.add(str(pending.get("key")))
            res = registry.execute(ctx, str(pending["tool"]), pending.get("args") or {})
            results.append((str(pending["tool"]), res))
            ctx.ui.update(res.ui)
            user_for_model = (f"[platform] The user confirmed with “{text}”. The platform executed {pending['tool']} after that confirmation. "
                              f"Result: {res.for_model()}. Explain the outcome to the user and continue the remaining part of the original request if any.")
        # anything else: the pending action silently lapses and the message is treated as a new request

    if rate_limited(port.account_id, settings.max_turns_per_hour):
        logger.warning("orchestrator rate limit reached for an account; using the rule-based path")
        return None
    llm = llm or get_llm(settings)

    try:
        messages: list[dict[str, Any]] = [{"role": "system", "content": build_system_prompt(fa, text, _state_for_prompt(ctx))},
                                          *_history_messages(history), {"role": "user", "content": user_for_model}]
        specs = registry.specs()
        deadline = time.monotonic() + settings.turn_deadline_s
        calls = tool_runs = 0
        provider = model = ""
        final = ""
        degraded = False
        for step in range(settings.max_steps):
            last_round = step == settings.max_steps - 1 or tool_runs >= settings.max_tool_calls
            if results and time.monotonic() > deadline:
                degraded = True
                break
            try:
                out = llm.chat(messages, specs, tool_choice="none" if last_round else "auto")
            except OrchestratorUnavailable as exc:
                logger.info("orchestrator model unavailable (%s)", exc)
                if not results:
                    return None  # nothing ran yet -> the rule-based pipeline answers as before
                degraded = True
                break
            calls += 1
            provider, model = str(out.get("provider", provider)), str(out.get("model", model))
            msg = out["message"]
            tcs = msg.get("tool_calls") or []
            if not tcs:
                final = str(msg.get("content") or "").strip()
                break
            if last_round:  # asked for a tool although tools were switched off -> stop and summarise ourselves
                degraded = True
                break
            messages.append(msg)  # verbatim (provider extras such as Gemini's thought signature must be echoed back)
            for tc in tcs:
                fn = tc.get("function") or {}
                name = str(fn.get("name") or "")
                if tool_runs >= settings.max_tool_calls:
                    res = ToolResult("error", {"error": "tool-call budget for this message is exhausted; summarise what is done"},
                                     "بودجهٔ مراحل این پیام تمام شد.", "The step budget for this message is exhausted.")
                else:
                    tool_runs += 1
                    res = registry.execute(ctx, name, fn.get("arguments") or "{}")
                    if res.status not in ("duplicate",):
                        results.append((name, res))
                    if res.ok:
                        ctx.ui.update(res.ui)
                messages.append({"role": "tool", "tool_call_id": tc.get("id") or name, "content": res.for_model()})
        else:
            degraded = bool(results)
        if not final:
            if not results:
                return None
            degraded = True
        text_out = final if final else _compose_degraded(ctx, results, note=True)
        if not final and ctx.pending and not results:
            text_out = ctx.pending["fa" if fa else "en"]
        audit_log.info(json.dumps({"event": "orchestrator_turn", "account": port.account_id, "conversation": port.conversation_id,
                                   "llm_calls": calls, "tool_calls": tool_runs, "degraded": degraded, "pending": bool(ctx.pending)}))
        return text_out, _metadata(ctx, calls, provider, model, degraded)
    except Exception as exc:  # noqa: BLE001 - the orchestrator must never take the chat down: report + fall back to the rules
        logger.exception("orchestrator turn failed")
        ctx.report_failure(exc)
        if results:
            return _compose_degraded(ctx, results, note=True), _metadata(ctx, 0, "", "", True)
        return None
