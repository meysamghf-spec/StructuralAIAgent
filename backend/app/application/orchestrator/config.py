"""Environment-driven settings of the Gemini platform orchestrator (all optional; the default is OFF).

PLATFORM_ORCHESTRATOR_MODE                  off | auto | always        (default: off)
    off     never used: the chat behaves exactly as before.
    auto    only compound / incomplete frame requests go to the model («بساز، تحلیل کن و بهینه کن»); everything else keeps the
            instant rule-based path.
    always  every chat message (except greetings, "how do I" questions and attachments) goes to the model first.
PLATFORM_ORCHESTRATOR_LLM_PROVIDER          preset name (default: gemini; uses LLM_GEMINI_API_KEY)
PLATFORM_ORCHESTRATOR_LLM_MODEL             model override (default: the preset's model, gemini-3.5-flash)
PLATFORM_ORCHESTRATOR_MAX_STEPS             max model rounds per message          (default 6)
PLATFORM_ORCHESTRATOR_MAX_TOOL_CALLS        max tool executions per message       (default 8)
PLATFORM_ORCHESTRATOR_CALL_TIMEOUT_SECONDS  timeout of one model call             (default 25)
PLATFORM_ORCHESTRATOR_TURN_DEADLINE_SECONDS wall-clock budget of one message      (default 100)
PLATFORM_ORCHESTRATOR_OPTIMIZE_BUDGET_SECONDS time budget handed to the optimizer (default 30, max 40)
PLATFORM_ORCHESTRATOR_MAX_TURNS_PER_HOUR    model-driven messages per account/h (per worker; default 40; protects the free tier)
PLATFORM_ORCHESTRATOR_MAX_TOKENS            max output tokens per model call      (default 1500)
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

MODES = ("off", "auto", "always")


def _int(env: Mapping[str, str], name: str, default: int, lo: int, hi: int) -> int:
    try:
        v = int((env.get(name) or "").strip() or default)
    except ValueError:
        v = default
    return max(lo, min(hi, v))


@dataclass(frozen=True)
class OrchestratorSettings:
    mode: str = "off"
    provider: str = "gemini"
    model: str = ""
    max_steps: int = 6
    max_tool_calls: int = 8
    call_timeout_s: float = 25.0
    turn_deadline_s: float = 100.0
    optimize_budget_s: int = 30
    max_turns_per_hour: int = 40
    max_tokens: int = 1500

    @property
    def enabled(self) -> bool:
        return self.mode in ("auto", "always")


def load_settings(env: Mapping[str, str] | None = None) -> OrchestratorSettings:
    env = env if env is not None else os.environ
    mode = (env.get("PLATFORM_ORCHESTRATOR_MODE") or "off").strip().lower()
    if mode not in MODES:
        mode = "off"  # an unknown value must never switch the feature on
    return OrchestratorSettings(
        mode=mode,
        provider=(env.get("PLATFORM_ORCHESTRATOR_LLM_PROVIDER") or "gemini").strip().lower(),
        model=(env.get("PLATFORM_ORCHESTRATOR_LLM_MODEL") or "").strip(),
        max_steps=_int(env, "PLATFORM_ORCHESTRATOR_MAX_STEPS", 6, 1, 12),
        max_tool_calls=_int(env, "PLATFORM_ORCHESTRATOR_MAX_TOOL_CALLS", 8, 1, 20),
        call_timeout_s=float(_int(env, "PLATFORM_ORCHESTRATOR_CALL_TIMEOUT_SECONDS", 25, 3, 90)),
        turn_deadline_s=float(_int(env, "PLATFORM_ORCHESTRATOR_TURN_DEADLINE_SECONDS", 100, 10, 300)),
        optimize_budget_s=_int(env, "PLATFORM_ORCHESTRATOR_OPTIMIZE_BUDGET_SECONDS", 30, 2, 40),
        max_turns_per_hour=_int(env, "PLATFORM_ORCHESTRATOR_MAX_TURNS_PER_HOUR", 40, 1, 10000),
        max_tokens=_int(env, "PLATFORM_ORCHESTRATOR_MAX_TOKENS", 1500, 256, 8000),
    )
