"""Provider-agnostic OpenAI-compatible chat client: fallback chain, rate-limit cooldowns, streaming.

Providers are tried in order. A provider that answers 429 (or 5xx / timeout after retries) is put on a
cool-down so later calls skip it; 401/403 (bad/missing key) puts it on a long cool-down. Streaming falls
back to the next provider only if nothing has been emitted yet.
"""

from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class LLMError(Exception):
    def __init__(self, message: str, *, provider: str = "", status: int | None = None, retry_after: float | None = None):
        super().__init__(message)
        self.provider = provider
        self.status = status
        self.retry_after = retry_after


class LLMUnavailableError(LLMError):
    """No provider could answer (none configured, all cooling down, or all failed)."""


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    base_url: str
    model: str
    api_key: str = ""
    keyless: bool = False
    timeout: float = 45.0
    max_tokens: int = 1200
    temperature: float = 0.3
    extra_headers: dict[str, str] = field(default_factory=dict)

    @property
    def usable(self) -> bool:
        return bool(self.base_url and self.model and (self.keyless or self.api_key))


@dataclass
class LLMResult:
    text: str
    provider: str
    model: str
    usage: dict[str, Any] = field(default_factory=dict)


class LLMClient:
    def __init__(
        self,
        providers: list[ProviderConfig],
        *,
        transport: httpx.BaseTransport | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        default_cooldown: float = 60.0,
        auth_cooldown: float = 600.0,
        retries: int = 1,
    ) -> None:
        self._providers = [p for p in providers if p.usable]
        self._transport = transport
        self._clock = clock
        self._sleep = sleep
        self._default_cooldown = default_cooldown
        self._auth_cooldown = auth_cooldown
        self._retries = max(0, retries)
        self._cooldown_until: dict[str, float] = {}
        self._lock = threading.Lock()
        self.last_errors: list[str] = []

    # ---- introspection -------------------------------------------------
    @property
    def configured(self) -> bool:
        return bool(self._providers)

    def status(self) -> list[dict[str, Any]]:
        now = self._clock()
        with self._lock:
            return [
                {
                    "provider": p.name,
                    "model": p.model,
                    "keyless": p.keyless,
                    "cooling_down_s": max(0, round(self._cooldown_until.get(p.name, 0) - now)),
                }
                for p in self._providers
            ]

    # ---- internals -----------------------------------------------------
    def _available(self) -> list[ProviderConfig]:
        now = self._clock()
        with self._lock:
            ready = [p for p in self._providers if self._cooldown_until.get(p.name, 0) <= now]
        # If everything is cooling down, still try the one that recovers first rather than giving up.
        if not ready and self._providers:
            with self._lock:
                ready = [min(self._providers, key=lambda p: self._cooldown_until.get(p.name, 0))]
        return ready

    def _cool(self, name: str, seconds: float) -> None:
        with self._lock:
            self._cooldown_until[name] = self._clock() + max(1.0, seconds)

    def _client(self, p: ProviderConfig) -> httpx.Client:
        return httpx.Client(timeout=p.timeout, transport=self._transport)

    @staticmethod
    def _headers(p: ProviderConfig) -> dict[str, str]:
        h = {"Content-Type": "application/json", **p.extra_headers}
        if p.api_key:
            h["Authorization"] = f"Bearer {p.api_key}"
        return h

    @staticmethod
    def _payload(p: ProviderConfig, messages: list[dict[str, str]], stream: bool, opts: dict[str, Any]) -> dict[str, Any]:
        body: dict[str, Any] = {
            "model": opts.get("model") or p.model,
            "messages": messages,
            "temperature": opts.get("temperature", p.temperature),
            "max_tokens": opts.get("max_tokens", p.max_tokens),
            "stream": stream,
        }
        return body

    @staticmethod
    def _retry_after(resp: httpx.Response) -> float | None:
        raw = resp.headers.get("retry-after")
        try:
            return float(raw) if raw else None
        except ValueError:
            return None

    def _raise_for_status(self, p: ProviderConfig, resp: httpx.Response) -> None:
        if resp.status_code < 400:
            return
        ra = self._retry_after(resp)
        if resp.status_code == 429:
            self._cool(p.name, ra or self._default_cooldown)
        elif resp.status_code in (401, 403):
            self._cool(p.name, self._auth_cooldown)
        elif resp.status_code >= 500:
            self._cool(p.name, min(30.0, ra or 15.0))
        raise LLMError(f"{p.name}: HTTP {resp.status_code}", provider=p.name, status=resp.status_code, retry_after=ra)

    # ---- non-streaming ---------------------------------------------------
    def chat(self, messages: list[dict[str, str]], **opts: Any) -> LLMResult:
        if not self._providers:
            raise LLMUnavailableError("no LLM provider configured")
        self.last_errors = []
        for p in self._available():
            for attempt in range(self._retries + 1):
                try:
                    with self._client(p) as c:
                        resp = c.post(f"{p.base_url.rstrip('/')}/chat/completions", headers=self._headers(p),
                                      json=self._payload(p, messages, False, opts))
                    self._raise_for_status(p, resp)
                    data = resp.json()
                    msg = ((data.get("choices") or [{}])[0].get("message") or {})
                    text = str(msg.get("content") or "").strip()
                    if not text:
                        raise LLMError(f"{p.name}: empty answer", provider=p.name)
                    return LLMResult(text=text, provider=p.name, model=str(data.get("model") or p.model),
                                     usage=data.get("usage") or {})
                except LLMError as exc:
                    self.last_errors.append(str(exc))
                    if exc.status in (429, 401, 403, 400, 404) or attempt >= self._retries:
                        break
                    self._sleep(0.4 * (attempt + 1))
                except (httpx.HTTPError, ValueError) as exc:
                    self.last_errors.append(f"{p.name}: {type(exc).__name__}")
                    if attempt >= self._retries:
                        self._cool(p.name, 15.0)
                        break
                    self._sleep(0.4 * (attempt + 1))
        raise LLMUnavailableError("all LLM providers failed: " + "; ".join(self.last_errors[-4:]))

    # ---- streaming -------------------------------------------------------
    def stream(self, messages: list[dict[str, str]], **opts: Any) -> Iterator[str]:
        """Yield content deltas. Raises LLMUnavailableError if no provider produced a first token."""
        if not self._providers:
            raise LLMUnavailableError("no LLM provider configured")
        self.last_errors = []
        for p in self._available():
            emitted = False
            try:
                with self._client(p) as c:
                    with c.stream("POST", f"{p.base_url.rstrip('/')}/chat/completions", headers=self._headers(p),
                                  json=self._payload(p, messages, True, opts)) as resp:
                        if resp.status_code >= 400:
                            resp.read()
                        self._raise_for_status(p, resp)
                        for line in resp.iter_lines():
                            if not line or not line.startswith("data:"):
                                continue
                            raw = line[5:].strip()
                            if raw == "[DONE]":
                                break
                            try:
                                chunk = json.loads(raw)
                            except json.JSONDecodeError:
                                continue
                            delta = ((chunk.get("choices") or [{}])[0].get("delta") or {})
                            piece = delta.get("content")
                            if piece:
                                emitted = True
                                yield str(piece)
                if emitted:
                    return
                self.last_errors.append(f"{p.name}: empty stream")
            except LLMError as exc:
                self.last_errors.append(str(exc))
            except (httpx.HTTPError, ValueError) as exc:
                self.last_errors.append(f"{p.name}: {type(exc).__name__}")
                if not emitted:
                    self._cool(p.name, 15.0)
                else:
                    return  # cut off mid-answer: keep what was already shown
        raise LLMUnavailableError("all LLM providers failed: " + "; ".join(self.last_errors[-4:]))
