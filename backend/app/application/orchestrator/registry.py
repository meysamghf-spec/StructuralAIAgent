"""Typed, whitelisted tool registry for the platform orchestrator.

The model can only call tools registered here. Every call goes through :meth:`ToolRegistry.execute`, which in this order
1. rejects unknown tools,
2. validates the arguments against the tool's JSON schema (unknown keys rejected, ranges / enums enforced, numeric strings coerced),
3. checks the prerequisites (project selected, ...),
4. asks for an explicit user confirmation for destructive tools (the *platform* decides this, never the model),
5. de-duplicates identical calls inside one message (idempotency),
6. runs the handler, turning expected errors into a structured result and unexpected ones into a safe message,
7. writes an audit record (``saia.orchestrator.audit`` log line + the message's ``orchestrator.trace`` metadata).

There is deliberately NO tool for payments / billing changes, code edits, shell, SQL or file-system access.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

audit_log = logging.getLogger("saia.orchestrator.audit")
logger = logging.getLogger(__name__)

ACCESS_READ = "read"
ACCESS_WRITE = "write"


class ToolError(Exception):
    """An expected, explainable failure (quota, missing input, not found). Never reported as a platform bug."""

    def __init__(self, code: str, fa: str, en: str, data: dict[str, Any] | None = None, status: str = "error") -> None:
        super().__init__(en)
        self.code, self.fa, self.en, self.data, self.status = code, fa, en, data or {}, status


@dataclass
class ToolResult:
    status: str  # ok | error | invalid_arguments | unknown_tool | confirmation_required | missing_inputs | quota_exceeded | duplicate
    data: dict[str, Any] = field(default_factory=dict)  # compact facts handed back to the model (the only source of numbers)
    text_fa: str = ""  # deterministic user-facing summary (used when the model is unavailable)
    text_en: str = ""
    ui: dict[str, Any] = field(default_factory=dict)  # message metadata for the existing result cards / downloads / project switch

    @property
    def ok(self) -> bool:
        return self.status == "ok"

    def for_model(self) -> str:
        body = {"status": self.status, **self.data}
        return json.dumps(body, ensure_ascii=False, default=str)[:12000]


Handler = Callable[[Any, dict[str, Any]], ToolResult]
ConfirmFn = Callable[[Any, dict[str, Any]], "tuple[str, str] | None"]


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Handler
    access: str = ACCESS_READ
    needs_project: bool = False
    # returns (fa, en) description of the consequence when this exact call needs the user's explicit "yes", else None
    confirm: ConfirmFn | None = None
    # the page / engine this tool maps to, for the docs + the knowledge test
    maps_to: str = ""

    def spec(self) -> dict[str, Any]:
        return {"type": "function", "function": {"name": self.name, "description": self.description,
                                                 "parameters": _strip_for_provider(self.parameters)}}


def _strip_for_provider(schema: Any) -> Any:
    """Providers accept only a JSON-schema subset (no additionalProperties)."""
    if isinstance(schema, dict):
        return {k: _strip_for_provider(v) for k, v in schema.items() if k not in ("additionalProperties",)}
    if isinstance(schema, list):
        return [_strip_for_provider(x) for x in schema]
    return schema


# --------------------------------------------------------------------------------------------- argument validation
class SchemaError(ValueError):
    pass


def _coerce_number(v: Any, path: str) -> float:
    if isinstance(v, bool):
        raise SchemaError(f"{path}: expected a number")
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v.strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٫،", "0123456789..")).replace(",", "."))
        except ValueError:
            pass
    raise SchemaError(f"{path}: expected a number")


def validate(schema: dict[str, Any], value: Any, path: str = "args") -> Any:
    """Validate + normalise ``value`` against the supported JSON-schema subset. Returns the cleaned value."""
    t = schema.get("type")
    if t == "object":
        if not isinstance(value, dict):
            raise SchemaError(f"{path}: expected an object")
        props = schema.get("properties", {})
        extra = sorted(set(value) - set(props))
        if extra and schema.get("additionalProperties", False) is False:
            raise SchemaError(f"{path}: unknown field(s) {extra}; allowed: {sorted(props)}")
        out: dict[str, Any] = {}
        for k, v in value.items():
            if v is None:
                continue  # models often send null for "not provided"
            out[k] = validate(props[k], v, f"{path}.{k}")
        missing = [k for k in schema.get("required", []) if k not in out]
        if missing:
            raise SchemaError(f"{path}: missing required field(s) {missing}")
        return out
    if t == "array":
        if not isinstance(value, list):
            raise SchemaError(f"{path}: expected an array")
        mx = schema.get("maxItems")
        if mx is not None and len(value) > mx:
            raise SchemaError(f"{path}: at most {mx} items")
        return [validate(schema.get("items", {}), x, f"{path}[{i}]") for i, x in enumerate(value)]
    if t == "string":
        if not isinstance(value, str):
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                value = str(value)
            else:
                raise SchemaError(f"{path}: expected a string")
        if len(value) > schema.get("maxLength", 400):
            raise SchemaError(f"{path}: too long")
        if "enum" in schema and value not in schema["enum"]:
            raise SchemaError(f"{path}: must be one of {schema['enum']}")
        return value.strip()
    if t == "boolean":
        if isinstance(value, bool):
            return value
        if isinstance(value, str) and value.lower() in ("true", "false"):
            return value.lower() == "true"
        raise SchemaError(f"{path}: expected true/false")
    if t in ("integer", "number"):
        n = _coerce_number(value, path)
        if t == "integer":
            if abs(n - round(n)) > 1e-9:
                raise SchemaError(f"{path}: expected a whole number")
            n = int(round(n))
        if "minimum" in schema and n < schema["minimum"]:
            raise SchemaError(f"{path}: must be >= {schema['minimum']}")
        if "maximum" in schema and n > schema["maximum"]:
            raise SchemaError(f"{path}: must be <= {schema['maximum']}")
        return n
    raise SchemaError(f"{path}: unsupported schema type {t!r}")  # a registry bug, caught by the unit tests


def args_key(tool: str, args: dict[str, Any]) -> str:
    raw = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
    return f"{tool}:{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


# --------------------------------------------------------------------------------------------- registry
class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> Tool:
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool {tool.name}")
        if tool.parameters.get("type") != "object":
            raise ValueError(f"tool {tool.name}: parameters must be an object schema")
        self._tools[tool.name] = tool
        return tool

    def names(self) -> list[str]:
        return list(self._tools)

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def tools(self) -> list[Tool]:
        return list(self._tools.values())

    def specs(self) -> list[dict[str, Any]]:
        return [t.spec() for t in self._tools.values()]

    def execute(self, ctx: Any, name: str, raw_args: Any) -> ToolResult:
        started = time.monotonic()
        tool = self._tools.get(name)
        args: dict[str, Any] = {}
        result: ToolResult
        if tool is None:
            result = ToolResult("unknown_tool", {"error": f"no such tool: {name}", "available": self.names()},
                                "این کار در پلتفرم تعریف نشده است.", "That operation is not available on the platform.")
        else:
            try:
                if isinstance(raw_args, str):
                    raw_args = json.loads(raw_args) if raw_args.strip() else {}
                args = validate(tool.parameters, raw_args or {}, "args")
                result = self._run(ctx, tool, args)
            except (SchemaError, json.JSONDecodeError) as exc:
                result = ToolResult("invalid_arguments", {"error": str(exc)},
                                    "پارامترهای ابزار نامعتبر بود.", "The tool arguments were invalid.")
        self._audit(ctx, name, args, result, (time.monotonic() - started) * 1000)
        return result

    def _run(self, ctx: Any, tool: Tool, args: dict[str, Any]) -> ToolResult:
        key = args_key(tool.name, args)
        cached = ctx.cache.get(key)
        if cached is not None:
            return ToolResult("duplicate", {**cached.data, "duplicate": True, "note": "identical call already executed in this message; not repeated"},
                              cached.text_fa, cached.text_en)
        if tool.needs_project and not ctx.port.project:
            return ToolResult("error", {"error": "no project selected", "hint": "create_project or open_project first"},
                              "ابتدا یک پروژه باز کنید یا بسازید.", "Open or create a project first.")
        if tool.confirm is not None and key not in ctx.confirmed:
            desc = tool.confirm(ctx, args)
            if desc is not None:
                ctx.pending = {"tool": tool.name, "args": args, "key": key, "fa": desc[0], "en": desc[1]}
                res = ToolResult("confirmation_required",
                                 {"action": desc[1], "instruction": "Nothing was changed. Ask the user to confirm in plain words (yes/no). "
                                                                      "Do NOT call this tool again in this message."},
                                 f"برای ادامه تأیید شما لازم است: {desc[0]} — بنویسید «بله» یا «نه».",
                                 f"I need your confirmation first: {desc[1]} — reply “yes” or “no”.")
                ctx.cache[key] = res
                return res
        try:
            res = tool.handler(ctx, args)
        except ToolError as exc:
            res = ToolResult(exc.status, {"error": exc.en, "code": exc.code, **exc.data}, exc.fa, exc.en)
        except Exception as exc:  # noqa: BLE001 - never leak a stack trace; report it through the existing auto-report mechanism
            logger.exception("orchestrator tool %s failed", tool.name)
            ctx.report_failure(exc)
            res = ToolResult("error", {"error": "internal error while running this tool; it was reported automatically",
                                       "code": "TOOL_INTERNAL_ERROR"},
                             "این مرحله با خطای داخلی روبه‌رو شد؛ خودکار گزارش شد.",
                             "This step hit an internal error; it was reported automatically.")
        if tool.access == ACCESS_WRITE or res.ok:
            ctx.cache[key] = res
        return res

    @staticmethod
    def _audit(ctx: Any, name: str, args: dict[str, Any], result: ToolResult, ms: float) -> None:
        rec = {"tool": name, "status": result.status, "ms": round(ms), "args": _redact(args)}
        if result.status not in ("ok", "duplicate") and result.data.get("error"):
            rec["error"] = str(result.data["error"])[:200]
        ctx.trace.append(rec)
        try:
            audit_log.info(json.dumps({"event": "orchestrator_tool", "account": ctx.port.account_id, "conversation": ctx.port.conversation_id,
                                       **rec}, ensure_ascii=False, default=str))
        except Exception:  # noqa: BLE001 - auditing must never break a turn
            pass


_SENSITIVE = ("password", "token", "secret", "api_key", "authorization")


def _redact(args: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in args.items():
        if any(s in k.lower() for s in _SENSITIVE):
            out[k] = "***"
        elif isinstance(v, str):
            out[k] = v[:120]
        else:
            out[k] = v
    return out
