"""Environment-driven configuration (provider-agnostic).

LLM_PROVIDER   auto | stub | none | <preset name> | custom      (default: auto)
LLM_BASE_URL / LLM_API_KEY / LLM_MODEL   primary OpenAI-compatible endpoint (custom, or override of a preset)
LLM_FALLBACKS  comma-separated preset names tried after the primary, e.g. "groq,openrouter,pollinations"
               each preset reads LLM_<NAME>_API_KEY and optionally LLM_<NAME>_MODEL / LLM_<NAME>_BASE_URL
LLM_TIMEOUT_SECONDS, LLM_MAX_TOKENS, LLM_TEMPERATURE
PLATFORM_ISSUE_WEBHOOK_URL / PLATFORM_ISSUE_WEBHOOK_SECRET / PLATFORM_ISSUE_WEBHOOK_RETRIES   optional, off by default
PLATFORM_ISSUE_ADMIN_TOKEN   bearer token for machine access to the issue admin API (Grok Bot)
PLATFORM_ADMIN_ACCOUNTS      comma-separated account ids / e-mails allowed to use the issue admin API as a human
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass, field

from app.platform_helper.llm import ProviderConfig

# name -> (base_url, default model, keyless)
PRESETS: dict[str, tuple[str, str, bool]] = {
    # Key-less (anonymous) — works from the Germany VPS, GPT-OSS-20B; shared anonymous rate limit, no SLA.
    "pollinations": ("https://text.pollinations.ai/openai", "openai-fast", True),
    # Free API keys (no card): best quality / limits first.
    "gemini": ("https://generativelanguage.googleapis.com/v1beta/openai", "gemini-2.5-flash", False),
    "groq": ("https://api.groq.com/openai/v1", "openai/gpt-oss-120b", False),
    "openrouter": ("https://openrouter.ai/api/v1", "openrouter/free", False),
    "nvidia": ("https://integrate.api.nvidia.com/v1", "nvidia/nemotron-3-super-120b-a12b", False),
    "cloudflare": ("", "@cf/openai/gpt-oss-120b", False),  # needs LLM_CLOUDFLARE_BASE_URL (account id in the URL)
    "sambanova": ("https://api.sambanova.ai/v1", "DeepSeek-V3.1", False),
    "mistral": ("https://api.mistral.ai/v1", "mistral-small-latest", False),
    "cerebras": ("https://api.cerebras.ai/v1", "gpt-oss-120b", False),
    "openai": ("https://api.openai.com/v1", "gpt-4o-mini", False),
}


AUTO_ORDER = ["gemini", "groq", "openrouter", "nvidia", "sambanova", "mistral", "cloudflare", "cerebras", "openai", "pollinations"]


@dataclass
class HelperSettings:
    providers: list[ProviderConfig] = field(default_factory=list)
    provider_mode: str = "auto"
    webhook_url: str = ""
    webhook_secret: str = ""
    webhook_retries: int = 3
    admin_token: str = ""
    admin_accounts: frozenset[str] = frozenset()
    max_history: int = 10

    @property
    def llm_configured(self) -> bool:
        return bool(self.providers)

    @property
    def webhook_enabled(self) -> bool:
        return bool(self.webhook_url)


def _provider_from_preset(name: str, env: Mapping[str, str], *, timeout: float, max_tokens: int, temperature: float,
                          key_override: str = "", model_override: str = "", url_override: str = "") -> ProviderConfig | None:
    preset = PRESETS.get(name)
    if preset is None:
        return None
    base, model, keyless = preset
    up = name.upper()
    base = url_override or env.get(f"LLM_{up}_BASE_URL", "") or base
    model = model_override or env.get(f"LLM_{up}_MODEL", "") or model
    key = key_override or env.get(f"LLM_{up}_API_KEY", "")
    headers = {}
    if name == "openrouter":
        headers = {"HTTP-Referer": env.get("LLM_REFERER", "https://structuralai.local"), "X-Title": "SAIA helper"}
    cfg = ProviderConfig(name=name, base_url=base, model=model, api_key=key, keyless=keyless and not key,
                         timeout=timeout, max_tokens=max_tokens, temperature=temperature, extra_headers=headers)
    return cfg if cfg.usable else None


def load_settings(env: Mapping[str, str] | None = None) -> HelperSettings:
    env = env if env is not None else os.environ
    mode = (env.get("LLM_PROVIDER") or "auto").strip().lower()
    timeout = float(env.get("LLM_TIMEOUT_SECONDS") or 45)
    max_tokens = int(env.get("LLM_MAX_TOKENS") or 1200)
    temperature = float(env.get("LLM_TEMPERATURE") or 0.3)
    providers: list[ProviderConfig] = []
    kw = {"timeout": timeout, "max_tokens": max_tokens, "temperature": temperature}

    if mode not in ("stub", "none", "off", "disabled"):
        base, key, model = (env.get("LLM_BASE_URL") or "").strip(), (env.get("LLM_API_KEY") or "").strip(), (env.get("LLM_MODEL") or "").strip()
        if mode in PRESETS:
            p = _provider_from_preset(mode, env, key_override=key, model_override=model, url_override=base, **kw)
            if p:
                providers.append(p)
        elif base and model and (key or mode == "custom_keyless"):
            providers.append(ProviderConfig(name="primary", base_url=base, model=model, api_key=key,
                                            keyless=not key, **kw))
        names = [x.strip().lower() for x in (env.get("LLM_FALLBACKS") or "").split(",") if x.strip()]
        if mode == "auto":
            # Any preset that has its own key configured is used (best first), then the key-less fallback last.
            names += [n for n in AUTO_ORDER if n != "pollinations" and env.get(f"LLM_{n.upper()}_API_KEY")]
            if (env.get("LLM_KEYLESS_FALLBACK") or "1").strip().lower() not in ("0", "false", "no", "off"):
                names.append("pollinations")
        for name in names:
            if any(p.name == name for p in providers):
                continue
            p = _provider_from_preset(name, env, **kw)
            if p:
                providers.append(p)

    return HelperSettings(
        providers=providers,
        provider_mode=mode,
        webhook_url=(env.get("PLATFORM_ISSUE_WEBHOOK_URL") or "").strip(),
        webhook_secret=(env.get("PLATFORM_ISSUE_WEBHOOK_SECRET") or "").strip(),
        webhook_retries=int(env.get("PLATFORM_ISSUE_WEBHOOK_RETRIES") or 3),
        admin_token=(env.get("PLATFORM_ISSUE_ADMIN_TOKEN") or "").strip(),
        admin_accounts=frozenset(
            x.strip().lower() for x in ((env.get("PLATFORM_ADMIN_ACCOUNTS") or "") + "," + (env.get("BILLING_COMPLIMENTARY_ACCOUNTS") or "")).split(",") if x.strip()
        ),
        max_history=int(env.get("LLM_MAX_HISTORY") or 10),
    )
